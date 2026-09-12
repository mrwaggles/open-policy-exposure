#!/usr/bin/env python3
"""Stage 5 (monitoring) slice: source freshness, hash integrity, and connector
coverage. The paper's coverage trap: a missing connector must never read as
absence of government activity, so coverage is shown per company per source
class. Hash re-verification detects snapshot corruption/drift. Emits
data/freshness.json; build_site.py folds it into the payload."""
import json, os, glob, hashlib, datetime, re

ROOT = os.path.join(os.path.dirname(__file__), "..")
TODAY = datetime.date.today()

# freshness targets in days, from the source registry cadences
TARGETS = {"edgar": 45, "federal_register": 30, "congress": 30, "lda": 100, "eur_lex": 180}

def source_class(meta, path):
    src = (meta.get("source") or "").lower()
    p = path.lower()
    if "edgar" in src or "sec" in src or "/10k" in p or "companyfacts" in p or "submissions" in p: return "edgar"
    if "federal" in src or "/fr/" in p or os.path.basename(p).startswith("fr-"): return "federal_register"
    if "congress" in src: return "congress"
    if "eur-lex" in src or "/eu/" in p: return "eur_lex"
    if "lda" in src or "lda" in os.path.basename(p): return "lda"
    return "other"

def main():
    docs, failures = [], []
    for mp in sorted(glob.glob(os.path.join(ROOT, "data/raw/**/*.meta.json"), recursive=True)):
        meta = json.load(open(mp))
        target = mp[:-len(".meta.json")]
        retrieved = meta.get("retrieved_at", "")[:10]
        age = None
        if retrieved:
            try: age = (TODAY - datetime.date.fromisoformat(retrieved)).days
            except ValueError: pass
        rec = {
            "doc": os.path.relpath(target, os.path.join(ROOT, "data/raw")),
            "source_class": source_class(meta, target),
            "retrieved_at": retrieved or None,
            "age_days": age,
            "sha256": meta.get("sha256") or meta.get("raw_text_sha256"),
            "hash_ok": None,
        }
        if os.path.exists(target) and rec["sha256"]:
            h = hashlib.sha256(open(target, "rb").read()).hexdigest()
            rec["hash_ok"] = (h == rec["sha256"])
            if not rec["hash_ok"]:
                failures.append(f"HASH MISMATCH {rec['doc']}")
        elif rec["sha256"] and not os.path.exists(target):
            # parsed .txt artifacts are covered by their source document's hash
            rec["hash_ok"] = None
        docs.append(rec)

    bad_hash = [d for d in docs if d["hash_ok"] is False]
    stale = []
    for d in docs:
        t = TARGETS.get(d["source_class"])
        if t and d["age_days"] is not None and d["age_days"] > t:
            stale.append(d)

    # coverage matrix per company per source class (from actual snapshot dirs)
    classes = ["edgar", "federal_register", "congress", "lda", "eur_lex"]
    coverage = {}
    for co in sorted(os.listdir(os.path.join(ROOT, "data/raw"))):
        codir = os.path.join(ROOT, "data/raw", co)
        if not os.path.isdir(codir): continue
        present = set()
        for mp in glob.glob(os.path.join(codir, "**/*.meta.json"), recursive=True):
            present.add(source_class(json.load(open(mp)), mp[:-10]))
        coverage[co] = {c: (c in present) for c in classes}

    out = {
        "checked_at": TODAY.isoformat(),
        "documents": len(docs),
        "hash_verified": sum(1 for d in docs if d["hash_ok"] is True),
        "hash_failures": len(bad_hash),
        "stale": [{"doc": s["doc"], "age_days": s["age_days"], "target_days": TARGETS.get(s["source_class"])} for s in stale],
        "freshness_targets_days": TARGETS,
        "coverage": coverage,
        "coverage_note": "Coverage is shown, not assumed: a missing source class for a company means the connector has not retrieved it - never that no government activity exists (paper: coverage trap).",
        "docs": docs,
    }
    with open(os.path.join(ROOT, "data/freshness.json"), "w") as f:
        json.dump(out, f, indent=1)
    for f_ in failures: print(f_)
    print(f"MONITOR: {len(docs)} docs, {out['hash_verified']} hash-verified, {len(bad_hash)} failures, {len(stale)} stale")
    if bad_hash: raise SystemExit("HASH INTEGRITY FAILURE - see above")

if __name__ == "__main__":
    main()
