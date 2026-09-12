#!/usr/bin/env python3
"""Add a company to the exposure pipeline on demand.

Registers the company in data/companies.json and data/registry.json, then runs
the same pipeline every company flows through:
  source retrieval -> candidate extraction -> monitoring snapshot -> build gate.

Retrieval reality and honesty rules:
- SEC EDGAR auto-discovers the latest 10-K and XBRL revenue when reachable
  (some egress IPs are 403-blocked; the company is then registered with
  revenue pending and the gap is labeled, never fabricated).
- Federal Register auto-discovers documents mentioning the company name
  (--fr-terms to refine). Congress/EUR-Lex/LDA docs are registered manually
  via flags; LDA needs a name (--lda-name) and an unblocked route.
- The new company enters with ZERO curated cases. Extractor output lands in
  the unreviewed candidate queue only; cases require human curation (REVIEW.md).

Usage:
  python3 build/add_company.py --id acme --name "Acme Corp" --cik 0000000000 \
      --ticker ACME --structure "..." [--fr-terms "Acme"] [--lda-name "Acme"] \
      [--eu-act 32024L1760 "Label"] [--bill hr 1234 "slug"] [--no-pipeline]
"""
import argparse, json, os, re, subprocess, sys, time, hashlib, urllib.request, urllib.parse

ROOT = os.path.join(os.path.dirname(__file__), "..")
UA = {"User-Agent": "OpenPolicyExposure research build contact: chwa@mail.instinct.com"}

def get(url, timeout=90):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def run(step, args):
    print(f"--- {step}")
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    sys.stdout.write((r.stdout or "")[-800:])
    if r.returncode != 0:
        sys.stderr.write((r.stderr or "")[-800:])
        raise SystemExit(f"step failed: {step}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--cik", required=True)
    ap.add_argument("--ticker", default="")
    ap.add_argument("--structure", default="")
    ap.add_argument("--fr-terms", default=None, help="FR search terms; default = company name")
    ap.add_argument("--fr-limit", type=int, default=3)
    ap.add_argument("--lda-name", default=None)
    ap.add_argument("--eu-act", action="append", nargs=2, metavar=("CELEX", "LABEL"), default=[])
    ap.add_argument("--bill", action="append", nargs=3, metavar=("TYPE", "NUM", "SLUG"), default=[])
    ap.add_argument("--no-pipeline", action="store_true")
    a = ap.parse_args()
    co = a.id.strip().lower()
    if not re.fullmatch(r"[a-z0-9-]+", co):
        raise SystemExit("--id must be lowercase letters/digits/dashes")
    a.cik = a.cik.zfill(10)

    cpath = os.path.join(ROOT, "data", "companies.json")
    comps = json.load(open(cpath))
    if any(o["company_id"] == co for o in comps["organizations"]):
        raise SystemExit(f"company '{co}' already registered")

    rpath = os.path.join(ROOT, "data", "registry.json")
    reg = json.load(open(rpath)) if os.path.exists(rpath) else {"version": 1, "companies": {}}
    entry = reg["companies"].setdefault(co, {})
    if a.lda_name: entry["lda_name"] = a.lda_name
    for celex, label in a.eu_act:
        entry.setdefault("eu_acts", []).append([celex, label])
    for bt, num, slug in a.bill:
        entry.setdefault("congress_bills", []).append([bt, int(num), slug])

    pending, added = [], []

    # --- revenue via EDGAR XBRL companyconcept (auto) ---
    revenue, revenue_source = None, "Pending - SEC EDGAR not reachable from this environment at add time"
    try:
        for tag in ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"):
            j = json.loads(get(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{a.cik}/us-gaap/{tag}.json"))
            usd = (j.get("units") or {}).get("USD", [])
            ann = [e for e in usd if e.get("form") == "10-K" and e.get("fp") == "FY"
                   and (time.mktime(time.strptime(e["end"], "%Y-%m-%d")) - time.mktime(time.strptime(e["start"], "%Y-%m-%d"))) > 300*86400]
            if ann:
                e = ann[-1]
                revenue = e["val"]
                revenue_source = f"SEC EDGAR XBRL companyconcept, us-gaap:{tag}, 10-K (period {e['start']} to {e['end']}, filed {e.get('filed')})"
                break
    except Exception as ex:
        pending.append(f"SEC EDGAR XBRL revenue ({type(ex).__name__})")
    if revenue is not None: added.append(f"revenue ${revenue/1e9:.1f}B")

    # --- EDGAR latest 10-K snapshot (auto, via the standard connector) ---
    comps["organizations"].append({
        "company_id": co, "name": a.name, "ticker": a.ticker, "cik": a.cik,
        "type": "US public company", "structure": a.structure or "Pending company map",
        "fy2025_consolidated_revenue_usd": revenue, "revenue_source": revenue_source,
        "business_activities": []})
    json.dump(comps, open(cpath, "w"), indent=2)

    # --- Federal Register auto-discovery ---
    terms = a.fr_terms or a.name
    try:
        q = urllib.parse.urlencode([("conditions[term]", terms), ("per_page", a.fr_limit),
                                    ("order", "newest")] +
                                   [("fields[]", f) for f in ("document_number", "title", "type", "publication_date")])
        res = json.loads(get(f"https://www.federalregister.gov/api/v1/documents.json?{q}"))
        for d in res.get("results", [])[:a.fr_limit]:
            slug = re.sub(r"[^a-z0-9]+", "-", d["title"].lower())[:48].strip("-")
            entry.setdefault("fr_docs", []).append([d["document_number"], slug])
        added.append(f"{len(res.get('results', [])[:a.fr_limit])} FR docs discovered")
    except Exception as ex:
        pending.append(f"Federal Register discovery ({type(ex).__name__})")

    json.dump(reg, open(rpath, "w"), indent=2)

    # --- run the shared pipeline ---
    if not a.no_pipeline:
        env = dict(os.environ, CONGRESS_CACHE="1")
        def runc(step, args):
            print(f"--- {step}")
            r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, env=env)
            sys.stdout.write((r.stdout or "")[-600:])
            if r.returncode != 0:
                pending.append(f"{step} failed")
                sys.stderr.write((r.stderr or "")[-400:])
        runc("sec_edgar", ["python3", "connectors/sec_edgar.py", co])
        runc("federal_register", ["python3", "connectors/federal_register.py"])
        if entry.get("congress_bills"): runc("congress_gov", ["python3", "connectors/congress_gov.py"])
        if entry.get("eu_acts"): runc("eur_lex", ["python3", "connectors/eur_lex.py"])
        if entry.get("lda_name"): runc("senate_lda", ["python3", "connectors/senate_lda.py"])
        run("extract_candidates", ["python3", "build/extract_candidates.py"])
        run("monitor", ["python3", "build/monitor.py"])
        run("build_site (gate)", ["python3", "build/build_site.py"])

    print(f"ADDED {co}: {'; '.join(added) or 'registered'}")
    if pending:
        print(f"PENDING (labeled, not fabricated): {'; '.join(pending)}")
    print("NOTE: 0 curated cases - extractor output enters the unreviewed candidate queue only; cases require human curation per REVIEW.md")

if __name__ == "__main__":
    main()
