#!/usr/bin/env python3
"""EUR-Lex connector (Tier A, EU primary law). Keyless: Cellar SPARQL endpoint
resolves CELEX -> work -> EN expression -> XHTML manifestation URI, then the
manifestation is fetched over REST. Immutable snapshot + .meta.json sidecar,
same envelope as the other connectors."""
import json, os, re, time, hashlib, datetime, urllib.request, urllib.parse

ROOT = os.path.join(os.path.dirname(__file__), "..")
UA = {"User-Agent": "open-policy-exposure-demo/0.2 (research; contact: chwa@mail.instinct.com)"}
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"

ACTS = [
    ("meta", "32022R2065", "Digital Services Act (Regulation (EU) 2022/2065)"),
    ("meta", "32022R1925", "Digital Markets Act (Regulation (EU) 2022/1925)"),
    ("uber", "32024L2831", "Platform Work Directive (Directive (EU) 2024/2831)"),
    ("xom",  "32024R1787", "EU Methane Regulation (Regulation (EU) 2024/1787)"),
    ("xom",  "32022L2464", "Corporate Sustainability Reporting Directive (Directive (EU) 2022/2464)"),
]

def get(url, accept=None):
    h = dict(UA)
    if accept: h["Accept"] = accept
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def sparql(q):
    url = SPARQL + "?" + urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"})
    return json.loads(get(url))["results"]["bindings"]

def main():
    for co, celex, label in ACTS:
        outdir = os.path.join(ROOT, "data/raw", co, "eu")
        os.makedirs(outdir, exist_ok=True)
        q = ('prefix cdm: <http://publications.europa.eu/ontology/cdm#> prefix xsd: <http://www.w3.org/2001/XMLSchema#> '
             'select ?manif ?date where { ?w cdm:resource_legal_id_celex "%s"^^xsd:string . '
             'OPTIONAL { ?w cdm:work_date_document ?date } '
             '?expr cdm:expression_belongs_to_work ?w . '
             '?expr cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> . '
             '?manif cdm:manifestation_manifests_expression ?expr . '
             '?manif cdm:manifestation_type ?type . FILTER(str(?type)="xhtml") } limit 5' % celex)
        b = sparql(q)
        if not b:
            print(f"MISS {celex}: no xhtml manifestation"); continue
        manif = b[0]["manif"]["value"]
        doc_date = b[0].get("date", {}).get("value", "unknown")
        raw = get(manif, accept="application/xhtml+xml,text/html")
        base = os.path.join(outdir, f"eu-{celex}")
        with open(base + ".html", "wb") as f:
            f.write(raw)
        text = re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="ignore"))
        text = re.sub(r"\s+", " ", text).strip()
        with open(base + ".txt", "w", encoding="utf-8") as f:
            f.write(text)
        meta = {
            "source": "EUR-Lex Cellar SPARQL + REST",
            "doc_id": celex,
            "label": label,
            "source_url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
            "cellar_manifestation": manif,
            "publication_date": doc_date[:10] if doc_date != "unknown" else "unknown",
            "retrieved_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        with open(base + ".html.meta.json", "w") as f:
            json.dump(meta, f, indent=1)
        print(f"OK {celex} -> {co} ({len(raw)} bytes, {len(text)} chars text)")
        time.sleep(1)  # be polite to the endpoint

if __name__ == "__main__":
    main()
