# The real-world program benchmark, vendored

This directory is a copy of the 18 interrupt-driven "real-world" programs that
NIChecker and BMC4AV both evaluate on (`wiki/benchmarks/Real-World Program Benchmark.md`),
kept inside irqrace so that every clone carries the exact programs, priorities and
ground truth the project's numbers are measured against.

| | |
| --- | --- |
| Upstream | https://github.com/zhvngyuan/NIChecker |
| Commit | `40267c0fd12d4eef05f37e5e93f3ae00fa5b22e2` (2026-01-19, "Update README.md") |
| Path upstream | `NIChecker_Experiments/benchmark2_atomicity_violations/<program>/` |
| Vendored | 2026-10-29, by `git show` of that commit; only `main.c`, `priority.info` and `violation.info` of each program, plus `LICENSE` |
| Licence | Apache-2.0 (`LICENSE`, upstream's). The programs are themselves derived from other code (Linux drivers, a Volvo brake-by-wire model, industrial logger firmware); upstream states no further terms. |

Upstream's program directories also hold files its own toolchain generated
(`_mt_main.c`, `seq_istLab__mt_main.c`, slices, result directories); they are
outputs of NIChecker, not inputs, and are not copied.

## Which copy, and why

The same 18 programs ship a second time inside the BMC4AV artifact
(`Real-world-Programs/`), and **the two copies are not the same**: `main.c` and
`priority.info` differ in all 18, the priorities disagree in five programs
(`logger2`, `logger3`, `i8xx_tco_1`, `wdt_pci_1`, `wdt_pci_2`), and `violation.info`
differs in `i8xx_tco_1`. This copy (NIChecker's) was chosen on the project's direction,
2026-10-29: it is the original distribution, the one the `violation.info` ground truth
was written for, and its `main` keeps the program's real masking (`disable_isr(-1)` /
`enable_isr(-1)`) where BMC4AV's replaces it with a CBMC thread harness. BMC4AV's
priorities for the five disputed programs are recorded in `../realworld-errata.yaml`
and run as a second configuration rather than discarded.

## Local changes

**None to the files.** Six programs do not compile as shipped (`EINVAL`, `NULL`,
`wdt_ctr_port` undeclared; `wdtpci_lock0`, a typo for `wdtpci_lock`). They are made
to compile by preprocessor definitions in their generated C1 build flags, listed
with their evidence in `../realworld-errata.yaml`, so every file here stays
byte-identical to upstream. Any future change to a file goes into this directory
as its own commit, with an entry here.
