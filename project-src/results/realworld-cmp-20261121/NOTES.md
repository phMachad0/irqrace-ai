# Real-world suite: irqrace (pool + by variable) against the LLM-only scan (2026-11-21)

The comparison run on Racebench, repeated on the 18 real-world programs
(`bench/realworld`, NIChecker's copy, official configs with the priority errata). All arms use
`claude-cli:sonnet@low`. **irqrace n = 1** (one run costs about 13 M input tokens); **the scans
n = 3 each**.

## Setup

| Arm | What | Notes |
| --- | --- | --- |
| irqrace | static stages frozen 2026-11-21 (`runs-realworld-20261121`, the 18 official configs: 1980 → 1037 → 972, gate 45/45), then triage with pool + by variable + omission retry (`tmp-combo-timeout.patch`) | row **`+self-validation`**, the production row: `+racebench` states Racebench's arrival model (equal priorities do not preempt), which these configs and their ground truth contradict. Pool of 4 as 2 cases × 2 conversations (with 1 per case, `wdt_pci_3`'s 175 candidates would be the critical path); `claude -p` timeout raised to 1,200 s through `IRQRACE_CLAUDE_TIMEOUT` (added in the patch) |
| scan, per file | `scripts/scan-measure.py per-file --realworld` | 18 calls, 4 at a time |
| scan, one prompt | `scripts/scan-measure.py one-prompt --realworld` | all 18 programs in one request |

The scan gets each program's `main.c` numbered, its flows and priorities from the same config,
the masking API, and the real-world semantics: an ISR may preempt a flow of lower **or equal**
priority, and the initial masking state is unknown (as the configs say). `blink1`–`blink3` end with
their answers in comments (`//violations`, `//true violations`, `//false positive`); those blocks
are cut before the model sees the file. The programs are **not** disguised: the planted variables
are called `test_global_var1`, `test_global_array` and so on.

Scoring is per `violation.info` entry, line errata applied, with `irqrace.realworld.match`, the unit
of the recall gate: same variable and pattern, and the same lines for an instance entry. 45
`true violation` entries ("bug points" below), 14 `false violation` entries ("traps"). Neither
side can be scored for precision beyond the 14 annotated traps: the ground truth is not exhaustive
(Semana 9 §3.9), so findings matching no entry are counted, not judged.

## Results

| | irqrace, `likely_real` | irqrace, not infeasible | scan per file (n = 3) | scan one prompt (n = 3) |
| --- | --- | --- | --- | --- |
| Entries found (of 45) | **21** | **45** | 43–45 | 9–36 |
| Annotated traps reported (of 14) | 2 | 9 | 5–10 | 2–9 |
| Entries called infeasible | 0 | — | — | — |
| Items reported | 368 candidates | 813 candidates | 144–166 findings | 19–95 findings |
| Matching no entry | 316 | 712 | 84–95 | 9–48 |
| Calls | 215 | | 18 | 1 |
| Input tokens | **13.1 M** | | 203–230 k | 173 k |
| Output tokens | 378 k | | 34–35 k | 3–18 k |
| Wall time | 813 s (static stages run once beforehand; 16 min in the 2026-10-30 official run) | | 72–81 s | 21–113 s |

irqrace's buckets over the 972 candidates: 368 `likely_real`, 390 `likely_benign`, 55 `uncertain`,
159 `likely_infeasible`. The static stages keep all 45 entries, the triage calls none of them
infeasible, and none was left untriaged.

## Reading it

1. **The production row judges the planted violations harmless.** 24 of the 45 entries fall in
   `likely_benign`, almost all on `test_global_var*` and `test_global_array` (for instance `brake1`
   #1, `i8xx_tco_1` #1, `wdt_pci_1` #1). This suite's ground truth, like Racebench's, counts the
   interleaving itself as the defect, and the planted reads feed nothing; the production harm
   criterion is right by its own terms and wrong by the suite's. It is the problem the `+racebench`
   row was written for, and a real-world row with the same "the interleaving is the defect"
   semantics and the real-world arrival model does not exist yet. Read on feasibility alone
   ("not infeasible"), irqrace has all 45, as the project's metrics define for production rows.
2. **The triage removes almost nothing here.** The not-infeasible view keeps 813 of 972 candidates
   and all 9 annotated traps the static stages let through; `likely_real` keeps 2 of them. On
   Racebench the triage turned 11 traps into 2–4 with every bug point on top; here the same move
   costs 24 entries.
3. **The per-file scan is strong on this suite too, and these files are not disguised.** 43–45 of
   45 entries with 5–10 traps, at 1/60 of the input. The planted names (`test_global_var1`) and the
   suite's public history are the same caveats as on Racebench before the disguise.
4. **The one-prompt scan is unreliable at this size.** 340 k characters in one request: 35 and 36
   entries in two runs, and in the third the model returned 19 findings in 3 k output tokens (9
   entries), stopping early.
5. **Cost.** One irqrace run here is 13.1 M input tokens, 6.5 times the Racebench run with the same
   configuration, for 972 candidates against 166; the checklist sends the long `provenance.entries`
   per item (`scan-estimate-20261121`).

n = 1 for irqrace: the two readings above are one draw.

## The 972 static candidates, examined (same day)

On Pedro's question whether the static stage lets through more than it should. Counts over the
official run root (`runs-realworld-20261121`, 18 programs), checked against `violation.info` with
the gate's matcher.

- **The priority logic is right.** In all 972 candidates B's flow is an ISR whose priority is
  higher than, or equal to, the flow of A1/A2. 968 have A1/A2 inside an ISR; `main` masks every
  interrupt around its initialisation, so only 4 involve it.
- **Equal-priority preemption is half of the set.** 476 candidates (49%) exist only because the
  configs say `equal_priority_preemption: true`. Only 2 of the 45 entries depend on it, both in
  `i8xx_tco_1` (#1 `test_global_var1 rwr`, #3 `tco_expect_close wwr`), whose `closer1`/`closer2`
  share priority 4. [[NIChecker (paper)]]'s own semantics say equal priorities do not preempt
  (Semana 9 §3.9; [[Contradictions]] #10). Off everywhere: 972 → 496 candidates, 43/45 entries.
  Off everywhere except `i8xx_tco_1`: 972 → 522, 45/45 — but choosing that per program from the
  ground truth is circular unless the platform's semantics justify it.
- **The same line triple appears under several flow pairs.** Handlers that run the same code
  (`closer1`…`closer4`) multiply each triple: 972 records hold 794 distinct
  (variable, A1, B, A2) line triples. Merging them, with every flow pair kept on the merged
  record, drops nothing.
- **Few triples are covered by an adjacent one.** A WWR whose A1 is followed, on every path, by
  another write of the same flow before A2 is the adjacent triple's defect, not a new one. A text
  check finds 209 candidates with some access in between, but most are conditional
  (`brake1` line 388, `if (i == MAX_LENGTH + 1) test_global_array[TRIGGER] = 1;`) and do not kill
  A1's value; dropping all 209 would lose 4 entries (`test_global_array wwr` in `brake1`,
  `i2c_pca_isa_3`, `i8xx_tco_1`, `wdt_pci_2`). Only about 60 have an unconditional write in
  between, and none of them is an entry's only candidate. Doing this soundly needs a must-write
  check on the CFG (dominance), in stage 2.
- **Combined:** equal priority off except `i8xx_tco_1`, merged triples, adjacent triples only:
  972 → 448 candidates with 45/45 entries.

What the stage reports is faithful to the configured model; the volume comes from that model —
eight handlers per driver at assigned priorities, equal ones allowed to preempt — and from the
copies of one handler body.
