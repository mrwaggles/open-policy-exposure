#!/usr/bin/env python3
"""Build step: resolves every evidence span against the immutable raw snapshots,
validates verbatim presence (citation-exactness gate), and emits the static site data.
Fails loudly if any span cannot be verified."""
import json, os, re, sys, hashlib

ROOT = os.path.join(os.path.dirname(__file__), "..")

def normalize(s):
    return re.sub(r"\s+", " ", s).strip()

def resolve_span(ev):
    with open(os.path.join(ROOT, ev["doc_path"]), encoding="utf-8", errors="ignore") as f:
        doc = normalize(f.read())
    start, end = ev["span"]["start"], ev["span"]["end"]
    starts = [m.start() for m in re.finditer(re.escape(start), doc)]
    if not starts:
        raise SystemExit(f"SPAN FAIL {ev['evidence_id']}: start marker not found: {start[:60]!r}")
    cands = []
    for i in starts:
        j = doc.find(end, i)
        if j >= 0:
            cands.append(doc[i:j + len(end)])
    if not cands:
        raise SystemExit(f"SPAN FAIL {ev['evidence_id']}: end marker not found after start: {end[:60]!r}")
    if len(set(cands)) > 1:
        raise SystemExit(f"SPAN FAIL {ev['evidence_id']}: start marker matched {len(starts)} times with differing spans: {start[:60]!r}")
    text = cands[0]  # multiple identical matches = duplicated record, citation still exact
    text = re.sub(r"<[^>]+>", "", text)  # strip source markup for display; verification ran on raw text
    truncated = False
    if len(text) > 1500:
        text = text[:1497] + "..."; truncated = True
    with open(os.path.join(ROOT, ev["meta_path"])) as f:
        meta = json.load(f)
    return {
        "evidence_id": ev["evidence_id"], "tier": ev["tier"], "role": ev["role"],
        "doc_label": ev["doc_label"], "location": ev["location"],
        "exact_text": text, "truncated": truncated,
        "source_url": meta.get("source_url") or ev.get("source_url"),
        "publication_date": ev["publication_date"],
        "retrieved_at": meta.get("retrieved_at"),
        "sha256": meta.get("sha256") or meta.get("raw_text_sha256"),
        "supports": ev["supports"],
    }

def main():
    with open(os.path.join(ROOT, "data/companies.json")) as f:
        companies = json.load(f)["organizations"]
    cases = []
    n_spans = 0
    for fn in sorted(os.listdir(os.path.join(ROOT, "data/cases"))):
        if not fn.endswith(".json"): continue
        with open(os.path.join(ROOT, "data/cases", fn)) as f:
            case = json.load(f)
        rv = case.get("review")
        if not rv or rv.get("status") not in ("approved", "pending_second_review") or not rv.get("reviewers") or not rv.get("history"):
            raise SystemExit(f"REVIEW GATE FAIL {case['case_id']}: missing or invalid review record (REVIEW.md)")
        cons = (case["dimensions"]["business_exposure"] == "Core"
                or case["dimensions"]["policy_process_status"] in ("Adopted or adjudicated", "Implementation")
                or "Structural" in case["dimensions"]["intervention_type"])
        if cons != rv.get("consequential"):
            raise SystemExit(f"REVIEW GATE FAIL {case['case_id']}: consequential flag {rv.get('consequential')} disagrees with dimensions")
        if cons and rv["status"] == "approved" and len(rv["reviewers"]) < 2:
            raise SystemExit(f"REVIEW GATE FAIL {case['case_id']}: consequential case cannot be approved on one reviewer")
        if not case.get("assessment_version"):
            raise SystemExit(f"REVIEW GATE FAIL {case['case_id']}: missing assessment_version")
        case["evidence"] = [resolve_span(ev) for ev in case["evidence"]]
        n_spans += len(case["evidence"])
        cases.append(case)
    changes = None
    ch_path = os.path.join(ROOT, "data/changes.json")
    if os.path.exists(ch_path):
        with open(ch_path) as f:
            changes = json.load(f)
        for item in changes["items"]:
            cs = item["current_span"]
            ev = dict(cs)
            ev.update({"evidence_id": item["change_id"] + "-current", "tier": "B", "role": "supporting", "supports": []})
            item["current_span"] = resolve_span(ev)
        n_spans += len(changes["items"])

    candidates = None
    cand_path = os.path.join(ROOT, "data/candidates.json")
    if os.path.exists(cand_path):
        with open(cand_path) as f:
            candidates = json.load(f)
        for item in candidates["items"]:
            sp = item["span"]
            ev = {k: sp[k] for k in ("doc_path", "meta_path", "doc_label", "location", "tier", "publication_date")}
            ev["span"] = {"start": sp["start"], "end": sp["end"]}
            ev.update({"evidence_id": item["candidate_id"] + "-span", "role": "candidate",
                       "supports": ["candidate passage - unreviewed"]})
            item["span"] = resolve_span(ev)
        n_spans += len(candidates["items"])

    freshness = None
    fr_path = os.path.join(ROOT, "data/freshness.json")
    if os.path.exists(fr_path):
        with open(fr_path) as f:
            freshness = json.load(f)
        if freshness["hash_failures"]:
            raise SystemExit("MONITOR GATE FAIL: hash failures present - refusing to publish")

    payload = {
        "system": "Open Policy Exposure - evidence-first demo (Stage 2-4 slice)",
        "assessment_version": "v0.2.0",
        "extractor": "analyst-authored cases; spans machine-validated against immutable snapshots",
        "source_registry": [
            {"source": "SEC EDGAR submissions + filing documents + XBRL companyfacts", "tier": "B", "access": "unauthenticated JSON APIs", "cadence": "event-driven + daily reconciliation"},
            {"source": "Federal Register API v1", "tier": "A", "access": "unauthenticated REST API", "cadence": "daily"},
            {"source": "Congress.gov API v3", "tier": "A", "access": "api.data.gov key (DEMO_KEY at low rate limits)", "cadence": "daily + event driven"},
            {"source": "Senate LDA API v1", "tier": "C", "access": "unauthenticated REST API", "cadence": "quarterly + updates"},
            {"source": "EUR-Lex Cellar SPARQL + REST", "tier": "A", "access": "unauthenticated SPARQL + content negotiation", "cadence": "event-driven + periodic"},
        ],
        "dimension_legend": {
            "business_exposure": ["Limited", "Meaningful", "Core", "Unknown"],
            "policy_process_status": ["Signal", "Agenda", "Proposal", "Formal process", "Adopted or adjudicated", "Implementation"],
            "intervention_type": ["Disclosure", "Compliance", "Product design", "Cost or tax", "Market access", "Liability", "Structural"],
            "time_horizon": ["Current", "Near term", "Medium term", "Long term", "Unclear"],
            "evidence_confidence": ["Low", "Medium", "High"],
            "coverage": ["Sufficient", "Material gaps", "Insufficient"],
        },
        "companies": companies,
        "review_policy": {
            "summary": "Expert review is part of the system (paper section 7). Consequential cases (Core exposure, Adopted/Implementation status, or Structural intervention) require a second reviewer; until one reviews them they show as pending second review. See REVIEW.md.",
            "consequential_rule": "business_exposure=Core OR policy_process_status in (Adopted or adjudicated, Implementation) OR intervention_type includes Structural",
            "statuses": ["approved", "pending_second_review"],
        },
        "cases": cases,
        "changes": changes,
        "candidates": candidates,
        "freshness": freshness,
        "boilerplate": json.load(open(os.path.join(ROOT, "data/boilerplate.json"))) if os.path.exists(os.path.join(ROOT, "data/boilerplate.json")) else None,
    }
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "data.json"), "w") as f:
        json.dump(payload, f, indent=1)
    print(f"BUILD OK: {len(cases)} cases, {n_spans} evidence spans all verified verbatim")

if __name__ == "__main__":
    main()
