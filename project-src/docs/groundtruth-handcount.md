# Hand count — certifying the ground-truth parser

The Roadmap requires hand-counting at least five cases before any number the
parser produces is trusted, because a strict parser silently reads 28 bug points
where a tolerant one reads 48 and neither raises an error
([[Open Questions]], [[Soundness and False Negatives]] §7b).

Method: read the annotation block of each case with the parser output hidden,
write down what is there, then diff. The five cases were chosen to be
**adversarial rather than representative** — between them they exercise every
grammar and every known defect in the annotations.

**Caveat on independence.** The same person wrote the parser and this count, so
this establishes that the parser reads what a careful reader reads, not that both
are right. Pedro spot-checks two of the five ([[Roadmap]] W2). Cases 019 and 022
are the two worth checking, because they are the two where the count depends on a
judgement rather than on transcription.

| Case | Why it is here | Hand count | Parser | Agree |
| --- | --- | --- | --- | --- |
| `svp_simple_001_001` | accesses juxtaposed with no separators; full-width colon in the trap header | 1 bug, 2 traps | 1, 2 | yes |
| `svp_simple_016_001` | missing closing bracket; access kind contradicts the source; **no trap section at all** | 3 bugs, 0 traps | 3, 0 | yes |
| `svp_simple_019_001` | every annotation's line numbers are wrong | 1 bug, 4 traps | 1, 4 | yes |
| `svp_simple_022_001` | **bug list with no header**; trap section headed `可能误报` | 4 bugs, 3 traps | 4, 3 | yes |
| `svp_simple_031_001` | fields reversed — line-then-type — throughout | 3 bugs, 0 traps | 3, 0 | yes |
| **total** | | **12 bugs, 9 traps** | **12, 9** | **yes** |

---

## `svp_simple_001_001` — 1 bug, 2 traps

```
//bug点:
//1.svp_simple_001_001_global_array <W#32>,<R#55>,<W#35>
//误报点：
//1.svp_simple_001_001_global_var<W#43><R#63><W#44>
//2.svp_simple_001_001_global_array<W#32><R#60><W#35>
```

One numbered entry under `//bug点:`, two under `//误报点：`. The trap header ends
in a **full-width colon** `：`, not the ASCII one the bug header uses; a parser
keyed on `:` finds no trap section and reads 1 bug, 0 traps.

Both trap entries write their three accesses with **no separator at all** —
`<W#43><R#63><W#44>` — while the bug entry uses commas. A parser that splits on
commas reads one access per trap, not three.

Trap 1's middle access names line 63, which is `int reader2;`, a declaration. The
read is the next statement, on line 64. Corrected in the errata.

## `svp_simple_016_001` — 3 bugs, 0 traps

```
//bug点:
//1.svp_simple_016_001_global_var1<W#24>,<R#33>,<R#25>
//2.svp_simple_016_001_global_var1<R#25>,<W#33,<R#26>
//3.svp_simple_016_001_global_var1<R#26>,<W#33>,<R#27>
```

Three entries, and the file ends there — **there is no trap section**, which is
worth stating explicitly because absence is what a parser is least likely to get
right. The three bug points are the three reads of `global_var1` in the expression
spread over lines 25–27, each paired with the single write in `isr_1` at line 33.

Entry 2's middle access is `<W#33,` — the closing bracket is missing and a comma
appears where it should be. A parser that requires `>` reads two accesses here.

Entry 1 calls line 33 a **read**. Line 33 is `svp_simple_016_001_global_var1 = 0x09;`,
a write, and the file's own entries 2 and 3 annotate the same line as `<W#33>`.
Corrected in the errata; this is the one correction the wiki had already noticed.

## `svp_simple_019_001` — 1 bug, 4 traps

```
//bug点:
//1.svp_simple_019_001_global_var1<R#45>,<W#65>,<R#54>
//误报点:
//1.svp_simple_019_001_global_var2<R#40>,<W#61>,<R#42>
//2.svp_simple_019_001_global_var1<R#45>,<W#65>,<R#49>
//3.svp_simple_019_001_global_var1<R#49>,<W#65>,<R#54>
//4.svp_simple_019_001_global_condition3<R#48><W#63>,<R#53>
```

The count is unambiguous — one entry, then four. The *content* is not: none of
the annotated ISR writes names a line that writes anything. Line 65 is
`idlerun();`, line 61 is blank, line 63 is blank. The three writes are at 71, 67
and 69 respectively, each exactly six lines later, and the reads drift by 0, 2, 3
and 5 lines depending on where they sit. The reconstruction — six lines added to
`main` when two guarded blocks gained braces and an `enable_isr(1)` — is set out
in `bench/racebench-errata.yaml`.

Trap 4 also mixes separators within one entry: `<R#48><W#63>,<R#53>`.

**This is the case to spot-check.** Not for the count, which is plain, but because
the errata rewrites four of its five annotations, and because the six inserted
lines are semantically significant: `enable_isr(1)` is what makes the reads at 51
and 59 preemptible despite the `disable_isr(1)` above them. If the annotations
predate that edit, the bug/trap **labels** may be stale as well as the line
numbers. The errata deliberately does not touch the labels.

## `svp_simple_022_001` — 4 bugs, 3 traps

```
// 1: svp_simple_022_001_global_var1 <W, #32>, <W,#66>, <R,#55>
// 2: svp_simple_022_001_global_var1 <R, #55>, <W,#66>, <R,#58>
// 3: svp_simple_022_001_global_var1 <R, #58>, <W,#66>, <R,#63>
// 4: svp_simple_022_001_global_var1 <R, #63>, <W,#66>, <R,#39>

// 可能误报
// 1: svp_simple_022_001_global_var1 <W, #32>, <W,#66>, <R,#39>
// 2: svp_simple_022_001_global_var1 <R, #55>, <W,#66>, <R,#56>
// 3: svp_simple_022_001_global_var1 <R, #55>, <W,#66>, <R,#63>
```

**The first four entries have no section header.** Nothing above them says
`bug点`. They are read as bug points, on two grounds: the file's only header,
`可能误报`, sits below them and introduces its own separate list, and the suite's
consistent ordering everywhere else is bugs first, traps second. Reading them as
traps instead would move four entries out of the bug column and change the suite
total from 48 to 44.

The trap header is `可能误报` — "possible false positive" — and not the
`误报点` every other case uses. Entries are numbered `1:` with a colon, not `1.`.

Three entries call line 58 or 56 a read; both are plain assignments in the two
branches of `func_3`. Corrected in the errata.

**This is the other case to spot-check**, because the four headerless entries are
a judgement rather than a transcription, and four of the suite's 48 bug points
rest on it.

## `svp_simple_031_001` — 3 bugs, 0 traps

```
// bug点：
// 1.svp_simple_031_001_tc_block_rcvd_bytes_ch1 <#46,R> <#90,W>,<#83,R>
// 2.svp_simple_031_001_tc_block_rcvd_bytes_ch1 <#83,R> <#90,W>,<#85,R>
// 3.svp_simple_031_001_tc_block_rcvd_bytes_ch1 <#85,R> <#90,W>,<#65,R>
```

Three entries, no trap section. Every access is written **line first, type
second** — `<#46,R>` rather than `<R#46>` — which is the fourth grammar and
unique to this case. A parser that assumes type-first either reads nothing here
or, worse, reads the line number as an access type and the type as a line.

Separators are mixed within each entry: a space between the first two accesses, a
comma between the second and third.
