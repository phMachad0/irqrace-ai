# C3 — run store layout

**Owner:** Track A. **Consumers:** Track A, Track B, Track C. **Frozen:** 2026-08-31.

A run is a directory, not a session. It survives the browser tab, it is readable without the
UI, and it is what makes a number quotable ([[Dashboard Design]] R42).

```
runs/<run_id>/
  manifest.json              C3 manifest schema — config hash, tool version, build flags,
                             semantics echo, model + date, per-stage funnel counts
  config.yaml                the C1 file, copied verbatim; what the CLI reads
  build/
    whole.bc                 linked whole-program bitcode
    build.log
  stage1/candidates.jsonl    C2 records, stage1 (no masking, no solver verdict)
  stage2/candidates.jsonl    C2 records, stage2 (masking + preemption filled in)
  solver/results.jsonl       one SolverResult per candidate id: unsat | sat | inconclusive
  context/<cand_id>.json     the full C2 context record handed to Track B
  llm/<cand_id>/turns.jsonl  full conversation, including C4 requests and replies
  repair/<cand_id>/patch.diff
  eval/report.json           recall gate, trap rejection, inspection ratio, match table
  log.ndjson                 C3 log-event schema
```

## Rules

1. **`<run_id>`** is `<subject>-<UTC yyyymmddThhmmssZ>-<6 hex>`. Sortable, unique, greppable.
2. **NDJSON everywhere a file grows.** The UI polls a growing file while a job is still
   running; `jsonl` files are append-only during a stage and never rewritten.
3. **One JSON object per line, no pretty-printing** in `.jsonl`. `manifest.json`,
   `eval/report.json` and `context/*.json` are pretty-printed, because humans read them.
4. **`manifest.json` is rewritten in place** as stages complete. It is the only file that is.
5. **A candidate id never changes** across `stage1/`, `stage2/`, `solver/`, `context/`,
   `llm/`, `repair/`. It is the join key for the whole store, and it is content-addressed
   (see C2 `fingerprint`).
6. **Only `solver/results.jsonl` may record a drop.** A candidate present in
   `stage1/candidates.jsonl` and absent from `stage2/candidates.jsonl` must have a stage-2
   line explaining the proof; a candidate absent from `context/` must have an `unsat` in
   `solver/results.jsonl`. Anything else is a silent recall loss and the lint must catch it.
7. **Runs are immutable once `manifest.stages[*].status` are all terminal.** Re-analysis after
   a repair is a *new run*, cross-linked from `repair/`, which is what makes the regression
   check in the re-verification step a diff between two runs.
8. **A SQLite index** (`runs/index.db`) over the run directories gives the explorer filtering
   and sorting without loading everything into memory. It is a cache: deleting it must lose
   nothing, and it is rebuildable from the directories alone.

## Synthetic runs

Track C builds against a hand-written run directory conforming to this layout from week 2, so
it is never blocked on Track A. `contracts/examples/run-fixture/` is that directory, and
`irqrace runstore validate <dir>` checks any run against this contract.
