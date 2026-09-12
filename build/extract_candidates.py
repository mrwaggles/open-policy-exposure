#!/usr/bin/env python3
"""Stage 3 (assisted extraction) candidate generator.

Deterministic keyword-window extractor: scans immutable raw snapshots per company,
surfaces sentence-level passages matching issue patterns, and emits UNREVIEWED
candidates. Candidates are not findings: the paper's workflow routes them into
human review (REVIEW.md). Spans are machine-verified verbatim by build_site.py
exactly like curated evidence. Dedupes against already-curated case evidence."""
import json, os, re, glob, hashlib, datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")

# issue patterns per company: (issue hint, [regexes]) - deliberately recall-oriented
ISSUES = {
 "meta": [
  ("children and teen privacy / safety", [r"\bCOPPA\b", r"Children'?s Online Privacy", r"\bminors?\b", r"\bteens?\b"]),
  ("antitrust and competition", [r"\bantitrust\b", r"\bcompetition law", r"\bmonopol"]),
  ("platform regulation", [r"\bKOSA\b", r"Kids Online Safety", r"\bSection 230\b", r"Digital Markets Act", r"\bDMA\b", r"Digital Services Act", r"\bDSA\b"]),
 ],
 "uber": [
  ("driver classification", [r"independent contractor", r"\bclassification\b.*\bdrivers?\b", r"\bgig\b", r"Proposition 22", r"\bemployment status\b"]),
  ("autonomous vehicles", [r"autonomous vehicle", r"\bAVs?\b", r"self-driving"]),
  ("EU platform work rules", [r"platform work", r"presumption of employment", r"platform worker"]),
 ],
 "pfe": [
  ("drug pricing and negotiation", [r"maximum fair price", r"Medicare Drug Price Negotiation", r"\bIRA\b", r"Inflation Reduction Act", r"price setting"]),
  ("EU pharmaceutical legislation", [r"regulatory data protection", r"marketing authori[sz]ation", r"pharmaceutical legislation", r"\bEMA\b", r"European Medicines Agency"]),
 ],
 "wmt": [
  ("tariffs and import costs", [r"\btariffs?\b", r"ad valorem duties", r"reciprocal tariff", r"import(?:s|ed|ing)? .*dut(?:y|ies)"]),
  ("minimum wage and labor", [r"minimum wage", r"Raise the Wage", r"\bhourly wage", r"\bwages?\b"]),
  ("EU supply chain due diligence", [r"due diligence", r"Corporate Sustainability Due Diligence", r"\bCSDDD\b", r"supply chain .*human rights"]),
 ],
 "xom": [
  ("methane regulation", [r"\bmethane\b", r"\bOGMP\b", r"New Source Performance Standards", r"\bOOOO\b"]),
  ("climate disclosure", [r"climate-related", r"greenhouse gas", r"\bGHG\b", r"Scope [123]", r"emissions? (?:reporting|disclosure|reduction)"]),
  ("carbon policy", [r"carbon (?:tax|price|pricing)", r"cap-and-trade", r"emissions trading"]),
  ("EU methane obligations", [r"leak detection and repair", r"\bLDAR\b", r"venting and flaring"]),
  ("EU sustainability reporting", [r"sustainability reporting", r"double materiality", r"\bCSRD\b"]),
 ],
}
GENERIC_ISSUES = [
 ("regulatory activity (generic)", [r"\brulemaking\b", r"\bregulation\b", r"\bcompliance\b", r"\benforcement\b"]),
 ("legislation and appropriations (generic)", [r"\bact\b", r"\bbill\b", r"\bappropriat", r"\bstatut"]),
]
try:
    _reg = json.load(open(os.path.join(ROOT, "data", "registry.json"))).get("companies", {})
    for _co, _cfg in _reg.items():
        if _cfg.get("issues"):
            ISSUES[_co] = [(h, rs) for h, rs in _cfg["issues"]]
except Exception:
    pass

AUTH = re.compile(r"\b(FTC|SEC|EPA|DOJ|Congress|Commission|Act|Rule|regulation|directive|court)\b")
NUM = re.compile(r"\$|%|\b\d{4}\b|\b\d+(?:\.\d+)?\s?(?:billion|million)\b", re.I)

def sentences(t):
    t = re.sub(r"\s+", " ", t)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(\u2022])", t)
    return [p.strip() for p in parts if 80 <= len(p.strip())]

def meta_for(txt_path):
    base = re.sub(r"\.txt$", "", txt_path)
    base = re.sub(r"\.(risk-factors|legal-proceedings)$", "", base)
    hits = sorted(glob.glob(base + ".*.meta.json"))
    return hits[0] if hits else None

def tier_label(path):
    n = os.path.basename(path)
    if n.startswith("fr-"): return "A", "Federal Register document"
    if "10k" in n: return "B", "SEC 10-K filing section" if "." in n.replace("10k-","").split(".")[0] else "SEC 10-K filing"
    if n.startswith("lda"): return "C", "Senate LDA filing"
    if n.startswith("eu-"): return "A", "EUR-Lex act (EU primary law)"
    return "B", "source document"

def anchor(doc_text, win):
    """Pick start/end markers that resolve to exactly one span in the doc."""
    doc = re.sub(r"\s+", " ", doc_text)
    for n in (48, 96, 160, 240):
        start, end = win[:n], win[-n:]
        if len(start) < n and len(win) < 2 * n:
            start, end = win[:max(20, len(win)//2)], win[-max(20, len(win)//2):]
        starts = [m.start() for m in re.finditer(re.escape(start), doc)]
        cands = set()
        for i in starts:
            j = doc.find(end, i)
            if j >= 0: cands.add(doc[i:j + len(end)])
        if len(cands) == 1:
            return start, end
    return None

def main():
    # already-curated evidence text for dedupe (normalized)
    curated = []
    for fn in glob.glob(os.path.join(ROOT, "docs/data.json")):
        d = json.load(open(fn))
        for c in d.get("cases", []):
            for ev in c.get("evidence", []):
                curated.append(re.sub(r"\s+", " ", ev.get("exact_text", "")).strip())
    items, seen = [], set()
    # every company with raw snapshots is scanned; companies without tuned
    # patterns fall back to the generic set so a newly added company flows through
    scan = dict(ISSUES)
    rawroot = os.path.join(ROOT, "data/raw")
    for co in os.listdir(rawroot):
        if os.path.isdir(os.path.join(rawroot, co)) and co not in scan:
            scan[co] = GENERIC_ISSUES
    for co, issues in scan.items():
        hits_per_co = []
        for txt in sorted(glob.glob(os.path.join(ROOT, "data/raw", co, "**/*.txt"), recursive=True)):
            meta = meta_for(txt)
            if not meta: continue
            text = open(txt, encoding="utf-8", errors="ignore").read()
            tier, base_label = tier_label(txt)
            for s in sentences(text):
                matched = sorted({h for h, pats in issues for p in pats if re.search(p, s, re.I)})
                if not matched: continue
                ns = re.sub(r"\s+", " ", s).strip()
                if any(ns in cur or cur in ns for cur in curated if cur): continue
                if ns in seen: continue
                seen.add(ns)
                hits_per_co.append((len(matched) + bool(AUTH.search(s)) + bool(NUM.search(s)), matched, s, txt, meta, tier, base_label))
        hits_per_co.sort(key=lambda x: -x[0])
        eu_hits = [h for h in hits_per_co if "/eu/" in h[3]]
        us_hits = [h for h in hits_per_co if "/eu/" not in h[3]]
        # jurisdiction diversity quota (paper: coverage bias) - reserve slots for EU sources
        picked = us_hits[:4] + eu_hits[:2] if eu_hits else us_hits[:6]
        for i, (score, matched, s, txt, meta, tier, base_label) in enumerate(picked):
            win = s  # full sentence; display truncation is handled by the build validator
            anch = anchor(open(txt, encoding="utf-8", errors="ignore").read(), win)
            if not anch: continue  # no unambiguous anchor in doc - skip
            items.append({
                "candidate_id": f"cand-{co}-{i+1:02d}",
                "company_id": co,
                "status": "unreviewed",
                "extraction_method": "keyword-window v1 (deterministic regex over snapshots)",
                "confidence": "medium" if len(matched) >= 2 or (AUTH.search(s) and NUM.search(s)) else "low",
                "issue_hints": matched,
                "span": {
                    "doc_path": os.path.relpath(txt, ROOT),
                    "meta_path": os.path.relpath(meta, ROOT),
                    "doc_label": f"{base_label} ({os.path.basename(txt)})",
                    "location": "sentence window around pattern match",
                    "tier": tier,
                    "start": anch[0],
                    "end": anch[1],
                    "publication_date": json.load(open(os.path.join(ROOT, meta))).get("publication_date") or json.load(open(os.path.join(ROOT, meta))).get("filing_date", "unknown"),
                },
            })
    out = {
        "generated_at": datetime.date.today().isoformat(),
        "extractor": "keyword-window v1 (deterministic regex over immutable snapshots)",
        "note": "UNREVIEWED CANDIDATES - machine-surfaced passages awaiting human review per REVIEW.md. Not findings.",
        "items": items,
    }
    with open(os.path.join(ROOT, "data/candidates.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(f"CANDIDATES: {len(items)} across {len(scan)} companies")

if __name__ == "__main__":
    main()
