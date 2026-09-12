# Open Policy Exposure

An evidence-first system for identifying the public policy developments that can
materially affect a company - built directly from the design paper
**"Corporate Public Policy Exposure Architecture"** (review edition, 11 September 2026).

This repository implements the paper's **Stage 2 slice** (evidence foundation) with a
working piece of Stage 4 (categorical assessment + reviewable brief), end to end:

- **5 diverse US public companies** - Meta Platforms (digital platform),
  Uber Technologies (labor marketplace), Exxon Mobil (energy producer),
  Pfizer (biopharma), Walmart (retail)
- **5 official connectors** - SEC EDGAR (submissions, filing documents, XBRL
  companyfacts/companyconcept), the Federal Register API v1, the Congress.gov API
  v3, the Senate LDA API v1 (Tier C advocacy records), and EUR-Lex Cellar (EU
  primary law). CMS.gov program pages are snapshotted ad hoc when CMS blocks
  direct retrieval from the build environment
- **9 exposure cases** joining business activity, jurisdiction, policy mechanism,
  business effect, and exact evidence
- **77 evidence spans**, every one machine-validated as verbatim text inside the
  hashed raw snapshot it cites, at build time
- **Categorical assessment dimensions** (business exposure, policy process status,
  intervention type, time horizon, evidence confidence, coverage) - no composite scores
- **A static web brief** where a reader can click from any conclusion to the exact
  source passage, the official source URL, the retrieval timestamp, and the SHA-256
  of the snapshot the span was verified against

## Design rules inherited from the paper

1. **Evidence before synthesis.** A conclusion cannot exist without linked evidence
   spans and source metadata. The build fails loudly if any span marker does not
   resolve uniquely to verbatim snapshot text (the citation-exactness gate).
2. **No composite scores.** Assessments are categorical dimensions with a written
   rationale. Any future sort key stays private.
3. **Direct vs. inferred.** Mechanism-chain steps state whether a source says the
   thing directly or the system infers it.
4. **Uncertainty stays visible.** Financial linkage follows the evidence ladder;
   product-level exposure that filings don't support is labeled **Unknown**,
   and coverage gaps are printed on the brief, not smoothed over.
5. **Change as a first-class object.** Cases carry dated policy events
   (adopted -> implemented -> revoked -> extended), so direction of travel is
   explicit - see the ExxonMobil methane case: rule adopted, fee implemented,
   fee revoked under the Congressional Review Act, deadlines extended.

## Repository layout

```
connectors/           source connectors (raw snapshot retrieval, hashed + timestamped)
  sec_edgar.py          SEC EDGAR: submissions, latest 10-K, risk factors, legal proceedings, XBRL facts
  federal_register.py   Federal Register API v1: selected rule/notice documents with full text
  congress_gov.py       Congress.gov API v3: bill metadata, actions, CRS summaries
  senate_lda.py         Senate LDA API v1: lobbying disclosure filings (Tier C advocacy)
data/
  companies.json        organizations + business activities (company map, paper step one)
  cases/                exposure cases (schema follows the paper's minimum exposure case schema)
  raw/                  immutable raw snapshots + .meta.json (source URL, retrieval time, sha256)
build/
  build_site.py         span resolution + verbatim validation + site data emission
docs/                   static web brief (vanilla JS, no dependencies; GitHub Pages /docs source)
```

## Run it

Raw snapshots under `data/raw/` are git-ignored build artifacts: connectors
regenerate them from the official APIs, and `build_site.py` re-validates every
span against the fresh snapshots, so a clean clone reproduces the full evidence
store with matching hashes.

```bash
python3 connectors/sec_edgar.py          # fetch EDGAR snapshots (respects sec.gov fair access)
python3 connectors/federal_register.py   # fetch Federal Register snapshots
python3 connectors/congress_gov.py       # fetch Congress.gov snapshots (DEMO_KEY or own key)
python3 build/build_site.py              # validate spans, emit site/data.json
cd docs && python3 -m http.server 8000   # open http://localhost:8000
```

`build_site.py` exits non-zero naming the offending evidence item if any span
cannot be verified verbatim - that is the paper's evidence-precision and
citation-exactness discipline enforced as a build gate.

## What this slice deliberately does NOT do (paper stage gates)

- No LLM candidate generation yet (Stage 3) - cases here are analyst-authored
  against retrieved sources; spans are machine-verified.
- **Change detection**: structural sentence-level diff between consecutive 10-K
  risk-factor sections; surfaced candidates are analyst-classified with evidence
  on both sides and shown as "Changes since previous review" on each company brief.
- No review workflow, versioning UI, or change alerts (Stages 4-5).
- No Senate LDA / EU connectors yet (connector matrix roadmap).
- No peer comparison or boilerplate analysis (Stage 6).

## Source tiers in use

| Tier | Source | Used for |
|------|--------|----------|
| A | Federal Register + Congress.gov (official APIs) | Formal status, dates, mechanism text |
| B | SEC EDGAR filings + XBRL | Company statements, financial facts, disclosed proceedings |
| C | Senate LDA filings | Reported advocacy only - never evidence of materiality |

Retrieved: 11 September 2026 (US Pacific). All documents are public records.
Not investment, legal, or policy advice.

## Review workflow and candidates (Stage 3-4 slice)

- `REVIEW.md` - reviewer guidance: consequential-case rule, category edge cases
  from the paper's red-team list, candidate triage workflow.
- Every case carries `assessment_version` and a `review` block (reviewers,
  status, append-only history). The build gate refuses to publish a case with a
  missing or inconsistent review record, and a consequential case (Core
  exposure, Adopted/Implementation status, or Structural intervention) cannot
  publish as approved on a single reviewer - those show "needs 2nd review" in
  the UI instead of faking a second human.
- `build/extract_candidates.py` - deterministic keyword-window extractor that
  scans the immutable snapshots and emits `data/candidates.json`: unreviewed
  candidate passages with confidence and issue hints. Candidates are verified
  verbatim by the same build gate but are never shown as findings - they render
  in a separate, clearly labeled candidate queue per company.
- `build/change_detect.py` - structural 10-K diffs with artifact suppression
  (page numbers, TOCs) and advisory classification suggestions; the published
  `data/changes.json` classifications are human review decisions with review
  records.

## Add a company (dynamic pipeline)

The pipeline is not hardcoded to the five benchmark companies. Per-company
source configuration lives in `data/registry.json` (Federal Register docs,
Congress bills, EUR-Lex acts, LDA registrant name, extractor issue patterns);
connectors and the candidate extractor read it, and any company with raw
snapshots is scanned even without tuned patterns (generic fallback).

- CLI: `python3 build/add_company.py --id acme --name "Acme Corp" --cik 0000000000`
  registers the company, auto-discovers SEC EDGAR revenue + latest 10-K and
  Federal Register documents, runs the full pipeline (retrieval -> candidates
  -> monitoring -> build gate), and labels anything unreachable as pending
  instead of fabricating it.
- UI: the site's "Add a company" panel generates that command and links to the
  repo's `Add Company` GitHub Actions workflow, which runs the same pipeline
  in CI and commits the result (repo write access required).
- Honesty rules are structural: a new company enters with zero curated cases;
  extractor output is unreviewed candidates only, never findings. Cases require
  human curation per `REVIEW.md`.

## Read API (Stage 7 slice)

`docs/data.json` is the stable read API: the complete payload (companies, cases
with resolved evidence spans, changes, candidates, freshness, boilerplate) as
one versioned JSON document. `assessment_version` versions the payload schema;
each case carries its own `assessment_version` and review history. Live at
`https://mrwaggles.github.io/open-policy-exposure/data.json` (and the surge
mirror). The static site is a thin client over this document.
