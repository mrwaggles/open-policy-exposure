#!/usr/bin/env python3
"""Senate LDA connector - lobbying disclosure filings via the public LDA API v1 (no key).
https://lda.gov/api/v1/ - Tier C advocacy records: establishes reported advocacy, not materiality."""
import json, hashlib, os, time, urllib.request, urllib.parse

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
COMPANIES = [
    ("meta", "Meta Platforms"),
    ("uber", "Uber Technologies"),
    ("xom", "Exxon Mobil"),
]
try:
    from registry import load as _load_reg
    _reg = _load_reg()
    if _reg:
        COMPANIES = [(co, cfg["lda_name"]) for co, cfg in _reg.items() if cfg.get("lda_name")]
except Exception:
    pass

def get(url):
    import urllib.error
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OpenPolicyExposure research build"})
            with urllib.request.urlopen(req, timeout=60) as r: return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                time.sleep(8 * (attempt + 1)); continue
            raise

def store(company, uuid, data, label):
    d = os.path.join(RAW, company, "lda"); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"lda-{uuid}.json")
    with open(p, "wb") as f: f.write(data)
    meta = {"doc_id": f"{company}/lda-{uuid}", "slug": label, "source": "Senate LDA API v1",
            "source_url": f"https://lda.gov/api/v1/filings/{uuid}/",
            "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    with open(p + ".meta.json", "w") as f: json.dump(meta, f, indent=2)
    return p

for company, name in COMPANIES:
    picked = []
    for year in (2026, 2025):
        q = urllib.parse.urlencode({"client_name": name, "filing_year": year, "page_size": 100})
        res = json.loads(get(f"https://lda.gov/api/v1/filings/?{q}"))
        results = list(res.get("results", []))
        while res.get("next"):  # LDA paginates at 25/page; follow next so in-house reports beyond page 1 are not missed
            res = json.loads(get(res["next"]))
            results += res.get("results", [])
        reports = [r for r in results if r["filing_type_display"].endswith("Report") and r["client"]["name"].upper().startswith(name.upper().split()[0])]
        if not reports: continue
        reports.sort(key=lambda r: r.get("dt_posted") or "", reverse=True)  # API default order is not newest-first
        inhouse = [r for r in reports if name.split()[0].upper() in r["registrant"]["name"].upper()]
        firms = sorted([r for r in reports if r not in inhouse and r.get("income")], key=lambda r: -float(r["income"]))
        picked = (inhouse[:1] + firms[:2])[:3]
        if picked:
            print(f"{company}: using filing_year {year}")
            break
    for r in picked:
        uuid = r["filing_uuid"]
        if os.path.exists(os.path.join(RAW, company, "lda", f"lda-{uuid}.json")):
            print(f"  (cached {uuid[:8]})"); continue
        data = get(f"https://lda.gov/api/v1/filings/{uuid}/")
        store(company, uuid, data, "lobbying-report")
        d = json.loads(data)
        acts = d.get("lobbying_activities", [])
        issues = sorted({a.get("general_issue_code_display","") for a in acts})
        amt = d.get("income") or d.get("expenses")
        print(f"  {d['filing_year']} {d['filing_period_display'][:12]} reg={d['registrant']['name'][:34]:34s} amt={amt} issues={issues}")
        for a in acts[:6]:
            desc = (a.get("description") or "")[:110].replace("\n"," ")
            print(f"    - {desc}")
        time.sleep(3)
