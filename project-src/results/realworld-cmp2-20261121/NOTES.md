# Real-world suite, second comparison: equal priority off, the `+interleaving` row (2026-11-21)

Same day as `realworld-cmp-20261121`, after two changes on Pedro's direction:

1. **Equal-priority preemption off on the real-world suite except `i8xx_tco_1`**
   (`bench/realworld-errata.yaml`, `semantics`; commit `9a9b19e`). Static run
   (`runs-realworld-eqoff-20261121`): 1980 → 587 → **484** candidates (972 before), gate **45/45**,
   8 of 14 false-violation entries reaching the context (9 before).
2. **The `+interleaving` row** (commit `c3665e5`): the production row plus a generic asset carrying
   `+racebench`'s notion of a defect (the interleaving itself, in four shapes, on one location,
   union members included) and taking the execution model from the context record instead of
   stating Racebench's. Nothing in it names a suite, a program or a variable.

All arms `claude-cli:sonnet@low`. **irqrace n = 1**, pool + by variable + omission retry
(`tmp-combo.patch`, the version of `realworld-cmp-20261121` with the new row copied in), 2 cases ×
2 conversations, `claude -p` timeout 1,200 s. **Scans n = 3 each**, with each program's
equal-priority setting now stated beside its flows (the first comparison said "lower or equal" for
every program).

## Results (45 true-violation entries, 14 false)

| | irqrace `likely_real` | scan per file | scan one prompt |
| --- | --- | --- | --- |
| Entries found | **45** | 44–45 | 12–34 |
| Entries called infeasible | 0 | — | — |
| False-violation entries reported | 6 | 5–7 | 0–9 |
| Items reported | 354 candidates | 136–144 findings | 19–98 findings |
| Matching no entry | 260 | 75–81 | 7–49 |
| Calls | 158 | 18 | 1 |
| Input tokens | **6.43 M** | 204–221 k | 173 k |
| Output tokens | 209 k | 33–34 k | 4–17 k |
| Wall time | 496 s | 72–81 s | 29–106 s |

irqrace's buckets over the 484 candidates: 354 `likely_real`, 5 `uncertain`, 125 `likely_infeasible`,
none `likely_benign`. False violations in `likely_real`: `blink3` #5, and `test_global_var2` in
`brake2`, `i2c_pca_isa_2`, `i8xx_tco_1`, `wdt_pci_1`, `wdt_pci_2`.

## Against the first comparison

| | first (equal on, `+self-validation`) | second (equal off but `i8xx_tco_1`, `+interleaving`) |
| --- | --- | --- |
| Static candidates | 972 | 484 |
| irqrace entries in `likely_real` | 21 | **45** |
| irqrace false violations in `likely_real` | 2 | 6 |
| irqrace input tokens | 13.1 M | 6.43 M |
| irqrace wall time | 813 s | 496 s |
| Scan per file, entries | 43–45 | 44–45 |
| Scan per file, false violations | 5–10 | 5–7 |

- **The row was the problem.** The 24 entries the production row put in `likely_benign` are in
  `likely_real` with `+interleaving`, and none is called infeasible. The price is four more
  false-violation entries on top (2 → 6), mostly `test_global_var2`, the planted near-miss of each
  program.
- **Halving the static set halved the cost** (13.1 M → 6.4 M input tokens, 813 → 496 s) without
  losing an entry.
- **irqrace and the per-file scan now meet on this suite**: 45 against 44–45 entries, 6 against
  5–7 false violations. The scan still reads 30× less input; it also reports far fewer items
  (136–144 findings against 354 candidates on top), and nothing proves its misses.
- **The one-prompt scan stays unreliable** at 340 k characters: 12, 34 and 29 entries, with two runs
  stopping early (4 k and 7 k output tokens).

n = 1 for irqrace.
