#!/usr/bin/env python3
"""Congress.gov API connector (api.data.gov key; DEMO_KEY works at low rate limits).
https://api.congress.gov/ - stores bill metadata + actions as hashed snapshots."""
import json, hashlib, os, time, urllib.request

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
KEY = os.environ.get("CONGRESS_API_KEY", "DEMO_KEY")
BILLS = [
    ("meta", "s", 1748, "kids-online-safety-act"),
    ("uber", "hr", 1319, "modern-worker-empowerment-act"),
    ("xom",  "hjres", 35, "wec-cra-disapproval"),
    ("pfe",  "hr", 6166, "expand-drug-price-negotiation"),
    ("wmt",  "hr", 2743, "raise-the-wage-act-2025"),
]
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "OpenPolicyExposure research build"})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()

CACHE = os.environ.get("CONGRESS_CACHE") == "1"
for company, btype, num, slug in BILLS:
    dc = os.path.join(RAW, company, "congress")
    if CACHE and os.path.exists(os.path.join(dc, f"{btype}{num}-bill.json")):
        print(f"{company}: {btype.upper()}{num} cached, skipping"); continue
    base = f"https://api.congress.gov/v3/bill/119/{btype}/{num}"
    bill = get(f"{base}?api_key={KEY}&format=json")
    actions = get(f"{base}/actions?api_key={KEY}&format=json&limit=50")
    d = os.path.join(RAW, company, "congress"); os.makedirs(d, exist_ok=True)
    for kind, data in (("bill", bill), ("actions", actions)):
        p = os.path.join(d, f"{btype}{num}-{kind}.json")
        with open(p, "wb") as f: f.write(data)
        meta = {"doc_id": f"{company}/congress-{btype}{num}-{kind}", "slug": slug,
                "source": "Congress.gov API v3", "source_url": f"https://www.congress.gov/bill/119th-congress/{ {'s':'senate','hr':'house','hjres':'house-joint'}[btype] }-bill/{num}" if btype!='hjres' else f"https://www.congress.gov/bill/119th-congress/house-joint-resolution/{num}",
                "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        with open(p + ".meta.json", "w") as f: json.dump(meta, f, indent=2)
    bj = json.loads(bill)["bill"]
    aj = json.loads(actions).get("actions", [])
    print(f"{company}: {btype.upper()}{num} '{bj.get('title','')[:60]}' introduced {bj.get('introducedDate')}; {len(aj)} actions; latest: {aj[0]['text'][:70] if aj else '?'}")
    time.sleep(1)
