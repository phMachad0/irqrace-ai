# M1 — the two Racebench baselines, 3 runs each

How this batch was produced, beyond what `manifest.json` records. The scored output is the rest of
this directory (`report.md`, the CSVs). Raw runs are in `runs/` (git-ignored, local only).

## What was run

| | |
| --- | --- |
| Static stages | frozen once: `runs/frozen-20261115`, commit `a639158`, clean tree, WSL Ubuntu-22.04, 31/31 cases ok |
| Triage | `runs/m1-20261115/<row>/<k>/`: each pair triages its own copy of the frozen root |
| Rows | `+racebench`, `+racebench+c4` |
| Runs | n = 3 independent runs per row (copies, not `--samples` voting) |
| Backend | `claude-cli:sonnet`, 4 conversations per case |
| Labels | 53 bug points / 33 traps (relabel 2026-10-28) |
| Scored | `scripts/bench-triage-report.py runs/m1-20261115/*/* --results results/m1 --allow-failed` |

The frozen run reproduces the M0 check of 2026-11-12: 53/53 bug points, 11/33 traps reaching the
LLM, 166 records (S1 = 73/106).

## Incidents, and how each was handled

**Subscription rate limit (HTTP 429, "5-hour limit").** Hit five times. Each time, the pair in
progress was marked `failed` and **moved aside, never deleted**, into `runs/m1-20261115-failed/`.
The pair was then re-run from scratch, from a fresh copy of the frozen root, once the window reset.
No pair in this directory mixes cases from two attempts.

| Moved aside | Cases lost to 429 |
| --- | --- |
| `+racebench+c4/1-ratelimit` | 10 |
| `+racebench/2-ratelimit-20261115T233153` | 22 |
| `+racebench+c4/2-ratelimit-20261116T043432` | 7 |
| `+racebench/3-ratelimit-20261116T093357` | 16 |
| `+racebench+c4/3-ratelimit-20261116T143252` | 9 |

**One safeguard refusal, kept (Lucas, 2026-11-16).** In `+racebench/3`, the backend refused one
candidate: `svp_simple_022_001`, `c816f84ad1fed7de0`, triple `W56 W66 R39` (WWR). The message was
"Sonnet 5.5's safeguards flagged this message". The candidate is **unannotated**. The tool kept it as
`uncertain`, so it is still reported: there is no recall cost, and no bug-point or trap score
changes. In the other five runs it is `likely_infeasible` (conf 0.90–0.95). The run was accepted as
is, rather than re-run, because discarding a run for an incident would choose which data count.
Its `batch.json` still says `failed`, as the runner wrote it, which is why it is scored with
`--allow-failed`. A note sits next to it at `runs/m1-20261115/+racebench/3/ACCEPTED.md`.
That is 1 refusal in about 2,770 calls over the six accepted runs.

## Environment fixes the freeze needed (no code change)

- `irqrace pipeline` imports the desktop UI, so the WSL venv needed `python3-tk` (apt) and
  `pymupdf` (the `ui` extra). Until both were installed, the freeze's first two attempts failed on
  every case (`runs/frozen-20261115-failed-tk`, `-failed-pymupdf`).
- WSL's git, without `core.autocrlf`, saw the Windows checkout as 374 modified files, which made
  `git_dirty` a false positive. The freeze ran with `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.autocrlf
  GIT_CONFIG_VALUE_0=true`, and then reported `git_dirty: false`.

## Gate M1 (Lucas, 2026-11-16)

1. **S2 = `+racebench`.** Both rows keep 53/53. `+racebench` scores 100/100/100 against
   `+c4`'s 100/97/100. It has κ 0.96–0.98 between runs, against 0.89–0.91, and costs half: about
   304 calls and 3.5 M input tokens per run, against about 619 and 7.3 M.
2. **`likely_real` is the headline reading.**
3. **The ±3-point noise band holds as a ceiling.** `+racebench` has sd 0. `+c4` ranges over 97–100.
