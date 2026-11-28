# The LLM-only reading on a disguised copy of the 18 real-world programs (2026-11-23)

The real-world comparison (`realworld-cmp2-20261121`) gave the scans the programs as distributed,
whose planted variables are named `test_global_var1` and so on. Pedro asked whether that biased the
scans. Same prompt, scorer, backend (`claude-cli:sonnet@low`) and configs (equal-priority
preemption off except `i8xx_tco_1`) as there; **n = 3 per mode**.

## The copy

`scripts/realworld-disguise.py --seed 2026` (outside git; regenerates identically;
`disguise-index.json` says which program is which):

- comments removed, `blink1`–`3`'s trailing answers with them; code the preprocessor skips
  (`#if 0`, `#if FULL_CODE`, `#ifdef CONFIG_WDT_501_PCI`, ...: none of those macros is defined)
  removed; blank lines dropped, so every line moves;
- renamed, from clang's AST with each program's own defines: every file-scope variable
  (`v_<word>`), every function defined in the file (`fn_<word>`; ISR entries `irq_<word>`), the
  macros the file defines (`K_<WORD>`), type names (`t_<word>`), fields (`f_<word>`) and enum
  constants (`E_<WORD>`); any remaining identifier containing `wdt`, `tco`, `pca`, `brake`,
  `logger`, `blink`, `i2c`, `watchdog` or `test_global` (`x_<word>`); string literals become `"msg"`;
- kept: `main`, the masking API, locals and parameters, and kernel/libc API functions
  (`spin_lock`, `outb`, `udelay`, `clear_bit`, ...), whose names say what they do, not which program;
- programs become `program_NN`.

Checks: no identifying substring left in any file; each disguised file parses with the same number
of clang errors as its original (0 with `-Wno-return-type`); all 48 line references of the instance
entries map; every ground-truth variable is renamed; an oracle built from the ground truth scores
45/45. The copy is 3,408 lines and 90 k characters for the one-prompt request, against 10,633 lines
and 340 k characters as distributed.

## Results (three runs each, against the original programs' runs in `realworld-cmp2-20261121`)

| | per file, original | **per file, disguised** | one prompt, original | **one prompt, disguised** |
| --- | --- | --- | --- | --- |
| Entries found (of 45) | 44–45 | **44–45** | 12–34 | **30–34** |
| False violations reported (of 14) | 5–7 | **5–7** | 0–9 | **2–9** |
| Findings | 136–144 | 128–138 | 19–98 | 61–130 |
| Input tokens | 204–221 k | 78 k | 173 k | 47 k |
| Output tokens | 33–34 k | 32–33 k | 4–17 k | 11–24 k |
| Wall time | 72–81 s | 71–74 s | 29–106 s | 67–143 s |

Median runs (by entries found, then fewer false violations): per file 44/45 with 6 false, 136
findings, 78 k input, 73 s; one prompt 33/45 with 9 false, 80 findings, 47 k input, 88 s.

## Reading it

- **On this suite the disguise does not move the per-file scan.** Entries and false violations
  are unchanged, unlike Racebench, where the disguise raised the per-file scan's traps from 1–4 to
  6–10. The planted names did not drive the result here.
- **The one-prompt scan improves**, from 12–34 to 30–34 entries and no run stopping early: removing
  comments and dead code cut the request to about a quarter.
- **The input gap with irqrace widens** (6.4 M against 78 k for the per-file scan, about 80×),
  because the disguised files lose their comments and dead code while the context records do not
  change.
