# Reviewer guidance (paper section 7)

This demo treats expert review as part of the system, not an afterthought. Every
published case carries a review record; the build gate refuses to publish a case
whose review record is missing or violates the rules below.

## Roles

- **demo-analyst** - the demo maintainer acting as primary reviewer.
- A **second reviewer** is required for consequential cases (see below). Until a
  real second human reviews one, its status stays `pending_second_review` and the
  UI says so. We do not fake the second review.

## Consequential case rule

A case is consequential - and therefore needs two reviewers - when any of:

- business exposure is **Core**,
- policy process status is **Adopted or adjudicated** or **Implementation**,
- intervention type includes **Structural**.

The build gate enforces this: a consequential case cannot publish as `approved`
on a single reviewer.

## Review workflow for candidates (Stage 3)

1. Triage the candidate queue by source tier, issue hint, and extraction confidence.
2. Open the exact span, then the official source one click away. Confirm the
   company entity, jurisdiction, authority, and that the passage says what the
   pattern thought it said.
3. Promote, merge into an existing case, or reject. Rejections stay in the queue
   with a reason; promotions become evidence on a case with role
   supporting/limiting/contradictory.
4. Record the reviewer, time, and reason. Corrections append a new history entry;
   nothing is erased.

## Change classification

Structural diffs are computed first (paper: compare structurally before applying
models). Page-number, footnote, and table-of-contents artifacts are discarded
before any human classifies a surfaced change. Classifications in
`data/changes.json` are review decisions, each with a review record.

## Category edge cases (from the paper's red team list)

- **Proposal trap**: a bill or consultation is never "Adopted or adjudicated".
- **Date trap**: delayed effective dates and stayed orders keep their real stage.
- **Boilerplate trap**: repeated generic disclosure with no new mechanism is not a change.
- **Advocacy mismatch**: Tier C lobbying data establishes reported advocacy only, never materiality.
- **Financial trap**: consolidated revenue is not product exposure; unallocatable stays Unknown.
