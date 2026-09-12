#!/usr/bin/env python3
"""Structural change detection between consecutive 10-K risk-factor sections.
Sentence-level diff first (paper: compare structurally before applying models);
classification of surfaced changes is analyst-applied with evidence on both sides."""
import re, difflib, json

PAIRS = {
 "meta": ("data/raw/meta/10k-000132680125000017.risk-factors.txt", "data/raw/meta/10k-000162828026003942.risk-factors.txt"),
 "uber": ("data/raw/uber/10k-000154315125000008.risk-factors.txt", "data/raw/uber/10k-000154315126000015.risk-factors.txt"),
 "xom":  ("data/raw/xom/10k-000003408825000010.risk-factors.txt", "data/raw/xom/10k-000003408826000045.risk-factors.txt"),
}
def sentences(t):
    t=re.sub(r"\s+"," ",t)
    parts=re.split(r"(?<=[.!?])\s+(?=[A-Z(•\u2022])",t)
    return [p.strip() for p in parts if len(p.strip())>60]
def specificity(s):
    score=0
    if re.search(r"\$|\d{4}|%|\b\d+\b",s): score+=1
    if re.search(r"\b(Act|Rule|Commission|FTC|SEC|EPA|DOJ|EU|DSA|DMA|COPPA|Proposition|Congress|court|lawsuit|regulation)\b",s): score+=1
    if len(s)>200: score+=1
    return score
for co,(old,new) in PAIRS.items():
    o,n=sentences(open(old).read()),sentences(open(new).read())
    sm=difflib.SequenceMatcher(None,o,n,autojunk=False)
    added,removed=[],[]
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag in ("insert","replace"):
            added+= [s for s in n[j1:j2] if s not in o]
        if tag in ("delete","replace"):
            removed+=[s for s in o[i1:i2] if s not in n]
    added=sorted(set(added),key=lambda s:-specificity(s))[:12]
    removed=sorted(set(removed),key=lambda s:-specificity(s))[:6]
    print(f"\n##### {co}: +{len(added)} added (top by specificity), -{len(removed)} removed")
    for s in added[:8]: print(f"  + {s[:180]}")
    for s in removed[:4]: print(f"  - {s[:150]}")
