# Evaluation (demo-scale, honest limits)

The paper's Stage 3 exit condition is that assisted extraction beats keyword and
whole-document baselines on recall and evidence precision, measured against a
two-expert gold standard (Stage 1). That full benchmark needs human experts and
is out of scope for this build. What follows is the smaller evaluation this
demo can honestly run, with method and numbers.

## What was measured (2026-09-12)

**Extractor recall proxy vs the curated case set.** Treating the 7 curated
cases' 33 evidence spans as a mini gold set: how many spans contain at least
one of the candidate extractor's issue-pattern hits?

| case | surfaced | missed |
|---|---|---|
| meta-coppa | 3 | 1 |
| meta-ftc-antitrust | 1 | 2 |
| meta-kosa | 2 | 2 |
| uber-av-framework | 3 | 1 |
| uber-driver-classification | 5 | 3 |
| xom-climate-disclosure | 1 | 2 |
| xom-methane | 3 | 4 |
| **total** | **18/33 (55%)** | |

Reading: the keyword-window extractor reliably surfaces issue-vocabulary
passages but misses structured facts - XBRL revenue figures, lobbying filing
metadata, dated policy events - that carry no issue keywords. That is the
expected shape of a recall-oriented keyword stage and exactly why the paper
routes candidates through review instead of publishing them. It also argues for
the paper's planned second extractor type (event/entity extraction) before any
automation scales.

**Evidence precision of the pipeline.** 55/55 published evidence spans are
machine-verified verbatim against hashed snapshots at every build (100% by
construction - the gate fails the build otherwise). Citation exactness for
resolved links is not separately sampled yet.

**Candidate precision.** Not scored: precision requires accept/reject review
judgments on the 18 candidates, which is human review work per REVIEW.md. The
queue is published unreviewed rather than scored by its own generator.

## What is deliberately not claimed

- No inter-rater reliability (single demo analyst; the paper wants two experts).
- No temporal-stability result (one change window only).
- No claim that the 55% proxy meets or fails the paper's 85% candidate-recall
  threshold - the proxy measures span-level pattern hits, not case-level
  candidate recall, and the gold set is demo-scale.
