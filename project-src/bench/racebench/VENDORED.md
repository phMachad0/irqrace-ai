# Racebench, vendored

This directory is a copy of the Racebench interrupt-race benchmark, kept inside
irqrace so that every clone carries the exact suite — and the exact ground truth —
the project's numbers were measured against.

| | |
| --- | --- |
| Upstream | https://github.com/chenruibuaa/racebench |
| Commit | `ec1d8280b21a2236527063fd2bc27d075cc7ad14` (2019-12-04, "Update svp_simple_019_001.c") |
| Vendored | 2026-10-29, by `git archive` of that commit; nothing else from upstream |
| Licence | **upstream ships none.** Copyright stays with the Racebench authors; it is redistributed here unchanged except for the files listed below, for research reproducibility. |

Everything under this directory except this file is upstream's, apart from the
changes below. irqrace reads it through `irqrace.racebench.locate_suite()`
(`IRQRACE_RACEBENCH` overrides it, to run against another copy on purpose).

## Local changes

Both were made on the project's direction and are committed in irqrace's history
as a separate commit on top of the pristine import, so `git log -p -- bench/racebench`
shows them. Do not revert them: every number dated 2026-10-28 or later depends on
them. Before that date the suite lived in a separate checkout one directory above
the vault, with the same two changes uncommitted there.

1. **`svp_simple_006_001.c` source patch, 2026-10-22** — in both `2.1/` and
   `2.1_remarks/`. See `bench/racebench-errata.yaml`, entry `svp_simple_006_001`.
2. **Relabel, 2026-10-28** — five planted false positives ("traps") became bug
   points, because each is reachable under the suite's own README (an interrupt
   may preempt the main program or a lower-priority interrupt whenever it is
   enabled, at any moment and any number of times):

   | Case | Was | Now |
   | --- | --- | --- |
   | `svp_simple_001` | trap 1 `global_var <W#43><R#63><W#44>` | bug 2, read on line 64 |
   | `svp_simple_019` | traps 2–4, lines drifted from the `2.1` copy | bugs 2–4, lines of this file |
   | `svp_simple_020` | trap 1 | bug 3 |

   The simple cases went from **48 bug points / 38 traps to 53 / 33**. Reasons,
   case by case: `bench/racebench-errata.yaml` (note `relabel_2026_10_28`),
   `docs/evaluation-protocol.md` ("Relabel, 2026-10-28"), and the wiki page
   `wiki/benchmarks/Racebench.md`.
