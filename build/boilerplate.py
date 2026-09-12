#!/usr/bin/env python3
"""Boilerplate analysis (paper Stage 6): how much of each 10-K risk-factor
section carries over unchanged year over year. High similarity = boilerplate
risk (paper's boilerplate trap); surfaced so readers can discount repeated
generic disclosure."""
import re, difflib, json, os

ROOT = os.path.join(os.path.dirname(__file__), "..")
PAIRS = {
 "meta": ("data/raw/meta/10k-000132680125000017.risk-factors.txt", "data/raw/meta/10k-000162828026003942.risk-factors.txt"),
 "uber": ("data/raw/uber/10k-000154315125000008.risk-factors.txt", "data/raw/uber/10k-000154315126000015.risk-factors.txt"),
 "xom":  ("data/raw/xom/10k-000003408825000010.risk-factors.txt", "data/raw/xom/10k-000003408826000045.risk-factors.txt"),
}
def sentences(t):
    t = re.sub(r"\s+", " ", t)
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z(\u2022])", t) if len(p.strip()) > 60]
out = {"metric": "share of FY2024 risk-factor sentences carried into FY2025 verbatim or near-verbatim (difflib ratio >= 0.9)",
       "note": "High carryover = boilerplate risk: repeated generic disclosure is not new evidence of a changing exposure (paper: boilerplate trap).",
       "window": "FY2024 10-K -> FY2025 10-K risk factors", "companies": {}}
for co, (old, new) in PAIRS.items():
    o, n = sentences(open(os.path.join(ROOT, old)).read()), sentences(open(os.path.join(ROOT, new)).read())
    sm = difflib.SequenceMatcher(None, o, n, autojunk=False)
    kept = sum(1 for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag == "equal" for _ in o[i1:i2])
    out["companies"][co] = {"sentences_fy2024": len(o), "sentences_fy2025": len(n),
                            "carried_over": kept, "carryover_share": round(kept / max(len(o), 1), 3)}
with open(os.path.join(ROOT, "data/boilerplate.json"), "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out["companies"], indent=1))
