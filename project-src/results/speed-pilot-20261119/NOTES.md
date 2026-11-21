# Speed pilot — `+racebench` with Haiku and with Sonnet at low effort (2026-11-19)

Pilot, **n = 1 per backend**, not the protocol's n = 3. Baseline numbers are M1's
(`results/m1/`, Lucas's machine, 2026-11-15/16), not re-run here.

> **The raw runs and the scorer's CSVs are lost.** They lived in a worktree under the session's
> `/tmp` scratchpad, which was cleared between 2026-11-19 and 2026-11-21. The numbers below were
> transcribed from the scorer's output (`scripts/bench-triage-report.py ... --allow-failed`) and
> the per-case `spend:` lines on 2026-11-19, before the loss. They cannot be re-scored; a re-run
> would be a new measurement.

| | |
| --- | --- |
| Static stages | frozen on 2026-11-19 from commit `ddd5a65` (dirty: the claude-cli effort suffix only), Linux; 53/53 bug points, 11/33 traps, 166 records — same as M1's freeze |
| Row | `+racebench` |
| Backends | `claude-cli:haiku` (answered by `claude-haiku-5-5`), `claude-cli:sonnet@low` (`claude-sonnet-5-5`, `--effort low`) |
| Workers | 4 conversations per case, cases in series |

## Incidents, kept as `uncertain` (nothing re-run)

- Haiku: 11 candidates failed the CLI's structured output ("Failed to provide valid structured
  output after 5 attempts", missing `verdict`/`confidence`). 5 of them are bug points.
- Sonnet low: 2 safeguard refusals ("Sonnet 5.5's safeguards flagged this message"). 1 is a bug
  point (019 bug#3), 1 a trap (007 trap#1).

## Results (53/33 labels, full suite)

| | M1 `+racebench` (default effort, n=3) | Sonnet low (n=1) | Haiku (n=1) |
| --- | --- | --- | --- |
| Bug points in `likely_real` | 53/53 | 52/53 (the miss is the refusal) | 47/53 (5 schema failures, 1 `likely_benign`: 024 bug#1) |
| Bug points called infeasible | 0 | 0 | 0 |
| Traps in `likely_real` | 2 | 2 | 2 |
| NASAC score (`likely_real`) | 100 | 98 | 88 |
| Inspection Ratio | 0.69 ± 0.02 | 0.63 | 0.72 |
| Calls | ≈304 | 304 | 289 |
| Input tokens (incl. cache) | ≈3.5 M | 3.48 M | 5.64 M |
| Output tokens | ≈296 k | 229 k | 754 k |
| Output tokens per call | ≈975 | 754 | 2,608 |
| Latency per call | — (not in M1's CSVs) | 8.8 s | 14.8 s |
| Wall time (triage) | ≈978 s | 943 s | 1,584 s |

The two traps in `likely_real` are case 022's `trap#1` and `trap#3` in all three columns.

Average concurrency (sum of call latencies / wall time): 2.8 of 4 (Sonnet low), 2.7 of 4 (Haiku).
Cases run in series and most have fewer than 4 records, so the workers sit idle at each case
boundary. This is what the global-pool experiment (`results/speed-20261121/`) tests.
