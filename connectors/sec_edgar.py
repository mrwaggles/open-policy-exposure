#!/usr/bin/env python3
"""SEC EDGAR connector: fetches company submissions + latest 10-K primary document.
Stores raw bytes with sha256, retrieval timestamp, source URL. EDGAR APIs are
unauthenticated per https://www.sec.gov/search-filings/edgar-application-programming-interfaces
"""
import json, hashlib, os, sys, time, urllib.request, re, html

UA = {"User-Agent": "OpenPolicyExposure research build contact: chwa@mail.instinct.com"}
RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

COMPANIES = [
    {"id": "meta", "name": "Meta Platforms, Inc.", "cik": "0001326801", "ticker": "META"},
    {"id": "uber", "name": "Uber Technologies, Inc.", "cik": "0001543151", "ticker": "UBER"},
    {"id": "xom",  "name": "Exxon Mobil Corporation", "cik": "0000034088", "ticker": "XOM"},
]

try:
    _cf = os.path.join(os.path.dirname(__file__), "..", "data", "companies.json")
    _orgs = json.load(open(_cf))["organizations"]
    COMPANIES = [{"id": o["company_id"], "name": o["name"], "cik": o["cik"], "ticker": o["ticker"]} for o in _orgs]
except Exception:
    pass
if len(sys.argv) > 1:
    COMPANIES = [c for c in COMPANIES if c["id"] in sys.argv[1:]]
    if not COMPANIES:
        raise SystemExit(f"no matching company in {sys.argv[1:]}")

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def store(company_id, doc_id, url, data, kind, extra=None):
    d = os.path.join(RAW, company_id)
    os.makedirs(d, exist_ok=True)
    fname = f"{doc_id}.{kind}"
    path = os.path.join(d, fname)
    with open(path, "wb") as f:
        f.write(data)
    meta = {
        "doc_id": f"{company_id}/{doc_id}",
        "source": "SEC EDGAR",
        "source_url": url,
        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }
    if extra: meta.update(extra)
    with open(path + ".meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    return meta

def html_to_text(b):
    s = b.decode("utf-8", "ignore")
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def extract_section(text, start_pat, end_pats, min_len=4000):
    m = re.search(start_pat, text, re.I)
    if not m: return None
    start = m.start()
    end = len(text)
    for ep in end_pats:
        em = re.search(ep, text[start + min_len:], re.I)
        if em:
            end = start + min_len + em.start()
            break
    return text[start:end].strip()

def main():
    index = []
    for c in COMPANIES:
        subs_url = f"https://data.sec.gov/submissions/CIK{c['cik']}.json"
        subs = fetch(subs_url)
        store(c["id"], "submissions", subs_url, subs, "json")
        sj = json.loads(subs)
        rec = sj["filings"]["recent"]
        tenk = None
        for form, acc, date, doc in zip(rec["form"], rec["accessionNumber"], rec["filingDate"], rec["primaryDocument"]):
            if form == "10-K":
                tenk = (acc, date, doc); break
        if not tenk:
            print(f"NO 10-K for {c['id']}"); continue
        acc, fdate, prim = tenk
        acc_nodash = acc.replace("-", "")
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(c['cik'])}/{acc_nodash}/{prim}"
        existing = os.path.join(RAW, c["id"], f"10k-{acc_nodash}.html")
        existing_meta = existing + ".meta.json"
        if os.path.exists(existing) and os.path.exists(existing_meta):
            try:
                m = json.load(open(existing_meta))
                if m.get("sha256") == hashlib.sha256(open(existing, "rb").read()).hexdigest():
                    text = html_to_text(open(existing, "rb").read())
                    rf = extract_section(text, r"Item\s+1A\.?\s*Risk Factors", [r"Item\s+1B\.?\s*Unresolved", r"Item\s+2\.?\s*Properties"])
                    lp = extract_section(text, r"Item\s+3\.?\s*Legal Proceedings", [r"Item\s+4\.?\s*Mine Safety", r"Item\s+5\.?\s*Market"], min_len=200)
                    index.append({"company": c, "accession": acc, "filing_date": fdate, "doc_url": doc_url,
                                  "full_chars": len(text), "rf_chars": len(rf or ""), "lp_chars": len(lp or "")})
                    print(f"{c['id']}: 10-K {fdate} acc={acc} (hash-verified, skip re-download)")
                    continue
            except Exception:
                pass
        doc = fetch(doc_url)
        store(c["id"], f"10k-{acc_nodash}", doc_url, doc, "html",
              {"form": "10-K", "accession": acc, "filing_date": fdate, "primary_document": prim})
        text = html_to_text(doc)
        with open(os.path.join(RAW, c["id"], f"10k-{acc_nodash}.txt"), "w") as f:
            f.write(text)
        rf = extract_section(text, r"Item\s+1A\.?\s*Risk Factors", [r"Item\s+1B\.?\s*Unresolved", r"Item\s+2\.?\s*Properties"])
        lp = extract_section(text, r"Item\s+3\.?\s*Legal Proceedings", [r"Item\s+4\.?\s*Mine Safety", r"Item\s+5\.?\s*Market"], min_len=200)
        for name, sec in (("risk-factors", rf), ("legal-proceedings", lp)):
            if sec:
                with open(os.path.join(RAW, c["id"], f"10k-{acc_nodash}.{name}.txt"), "w") as f:
                    f.write(sec)
        index.append({"company": c, "accession": acc, "filing_date": fdate, "doc_url": doc_url,
                      "full_chars": len(text), "rf_chars": len(rf or ""), "lp_chars": len(lp or "")})
        print(f"{c['id']}: 10-K {fdate} acc={acc} full={len(text)} rf={len(rf or '')} lp={len(lp or '')}")
        time.sleep(0.4)
    with open(os.path.join(RAW, "edgar_index.json"), "w") as f:
        json.dump(index, f, indent=2)

if __name__ == "__main__":
    main()
