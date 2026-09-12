#!/usr/bin/env python3
"""Federal Register connector (free public API, no key) - selected document set."""
import json, hashlib, os, time, urllib.request

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
DOCS = [
    ("meta", "2025-05904", "coppa-final-rule"),
    ("uber", "2024-00067", "ic-final-rule-2024"),
    ("uber", "2026-03962", "ic-proposed-rule-2026"),
    ("uber", "2026-15483", "av-framework-2026"),
    ("xom",  "2024-26643", "wec-final-rule"),
    ("xom",  "2025-08688", "wec-cra-revocation"),
    ("xom",  "2025-14531", "methane-deadline-extension"),
    ("xom",  "2026-11091", "sec-climate-rescission-proposal"),
    ("pfe",  "2026-14583", "ira-negotiation-notice-2026"),
    ("pfe",  "2024-23418", "ira-negotiation-final-guidance"),
    ("wmt",  "2025-15010", "reciprocal-tariff-rates-eo"),
    ("wmt",  "2025-17507", "reciprocal-tariff-scope-modification"),
]
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "OpenPolicyExposure research build"})
    with urllib.request.urlopen(req, timeout=120) as r: return r.read()

for company, docnum, slug in DOCS:
    meta = json.loads(get(f"https://www.federalregister.gov/api/v1/documents/{docnum}.json"))
    raw = None
    if meta.get("raw_text_url"):
        try: raw = get(meta["raw_text_url"]).decode("utf-8","ignore")
        except Exception as e: print(f"raw fail {docnum}: {e}")
    d = os.path.join(RAW, company, "fr"); os.makedirs(d, exist_ok=True)
    data = json.dumps(meta, indent=2).encode()
    with open(os.path.join(d, f"fr-{docnum}.json"), "wb") as f: f.write(data)
    m = {"doc_id": f"{company}/fr-{docnum}", "slug": slug, "source": "Federal Register API",
         "source_url": meta.get("html_url"), "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    if raw:
        with open(os.path.join(d, f"fr-{docnum}.txt"), "w") as f: f.write(raw)
        m["raw_text_sha256"] = hashlib.sha256(raw.encode()).hexdigest(); m["raw_text_bytes"] = len(raw)
    with open(os.path.join(d, f"fr-{docnum}.json.meta.json"), "w") as f: json.dump(m, f, indent=2)
    print(f"{company} {docnum} [{meta.get('type')}] {meta.get('publication_date')} {meta.get('title','')[:70]} raw={len(raw or '')}")
    time.sleep(0.4)
