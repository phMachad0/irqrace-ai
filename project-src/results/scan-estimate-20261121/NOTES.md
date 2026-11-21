# Input tokens: irqrace's triage against "ask the model to read every file" (estimate, 2026-11-21)

**An estimate. No model was called for the scan side, and the scan's recall is unknown.**
`scripts/scan-token-estimate.py` counts characters exactly and converts them at 2.41 characters
per token, calibrated on M1 (`+racebench/1`: 8,479,763 characters of prompt, 3,519,824 input
tokens reported). Plain C usually packs more characters per token than this JSON-heavy mix, so
the scan side is also given at 3.5 (assumed, not calibrated). Output tokens are not estimated.

Check on the calibration: for the per-variable checklist on Racebench the script predicts
1.79 M input tokens, and the measured run (`results/speed-20261121/by-variable`) reported
1.93 M (+8%).

| Suite | Candidates reaching the LLM | Source characters |
| --- | --- | --- |
| Racebench (31 cases, sources from `2.1/`, without the remark comments) | 166 | 60,593 |
| Real-world (18 programs, official configs, run 2026-11-21: 1980 → 1037 → 972, gate 45/45) | 972 | 279,081 |

## Racebench (`racebench.md`)

| | conversations | input tokens |
| --- | --- | --- |
| irqrace, one per triple (today) | 166 | 3.53 M (measured: 3.45–3.55 M) |
| irqrace, one per interval | 138 | 2.95 M |
| irqrace, one per variable (checklist) | 44 | 1.79 M (measured: 1.93 M) |
| scan, every file once, with the triage system prompt | 31 | 0.14–0.21 M |
| scan, every file once, no system prompt | 31 | 0.02–0.03 M |

## Real-world suite (`realworld.md`)

| | conversations | input tokens |
| --- | --- | --- |
| irqrace, one per triple | 972 | 29.2 M |
| irqrace, one per interval | 312 | 9.2 M |
| irqrace, one per variable (checklist) | 109 | 12.2 M |
| scan, every file once, with the triage system prompt | 18 | 0.15–0.22 M |
| scan, every file once, no system prompt | 18 | 0.08–0.12 M |

The tool's side assumes the harmfulness question is asked for 138/166 of the candidates, as in
M1; on real code with the production prompt that share may differ.

## Why the checklist loses to the interval grouping on real code

Each checklist item carries every field where it differs from its siblings, and one field
dominates: `provenance.entries`, about 7.8 k characters per real-world record, 75% of the
per-item text. A two-level split of shared fields saved under 4% (tried, not kept as the
default: `render_checklist(depth=)` in the experiment). The interval grouping sends one record
and a one-line list of the other Bs, so it pays for the long record once. Compacting
`provenance.entries` per item is the lever if the checklist is pursued on real code.

## Reading it

- With the same system prompt, the scan reads 9–25× fewer input tokens than triage on Racebench
  and 40–190× fewer on the real-world suite, depending on the grouping and the ratio. On these
  programs the files are small and many candidates share one file, so this is the expected
  outcome, not a surprise.
- The comparison says nothing about quality: the scan gives no recall guarantee, its output was
  not measured, and nothing ties its findings to proofs. A measured scan (one call per file,
  structured list of triples, scored with the same matcher) would put a recall number next to
  these token counts.
- What changes the balance on a large repository is the ratio of source size to candidate count.
  The scan grows with every line of code; triage grows with candidates, which depend on shared
  variables touched by interrupt handlers. This suite does not measure that ratio.
