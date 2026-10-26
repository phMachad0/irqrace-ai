# Masking semantics, and the trap in computing them per flow

Written in W1, from the first fixture built by hand. It records a rule the
pipeline has to obey from stage 2 onward, and the concrete case that proves it.

## The rule

Stage 2 asks one masking question of every candidate, the **interval
property**: is interrupt *n* masked *throughout* `[A₁, A₂]`? What holds at `A₁`
or at `A₂` alone is recorded as evidence and never answers it — masked at both
accesses does not mean masked in between.

The recall-safe direction is stated in [[Pipeline Design]]: an interrupt counts
as masked at a point **only if it is masked on every path reaching that point**.
"Masked on some path" turns into a dropped real defect. That much is already in
the wiki. What follows is the part that is easy to get wrong even after reading
it.

## The trap

`svp_simple_001_001` has one annotated bug point:

```
//1.svp_simple_001_001_global_array <W#32>,<R#55>,<W#35>
```

The main task writes the array in a loop at line 32, writes it again in a second
loop at line 35, and `isr_2` reads it at line 55. So `A₁` and `A₂` are in the
main task and `B` is in `isr_2`.

Now look at the main task's own control flow. Line 28 is `disable_isr(2)`, and
nothing in the main task ever re-enables interrupt 2. On every path through main,
at every point of the interval `[32, 35]`, interrupt 2 is masked. A stage-2
masking analysis that walks the CFG of the flow containing `A₁` and `A₂` — the
obvious implementation — concludes `disabled_throughout = {2}`, decides `isr_2`
cannot run in the interval, and discards the candidate.

**That candidate is an annotated bug point.** Discarding it is a recall loss on
day one of stage 2, on case 1 of 31.

What the local analysis misses is that `isr_1` is still enabled, has lower
priority than `isr_2` but higher than the main task, and does this:

```c
void svp_simple_001_001_isr_1() {
  idlerun();
  svp_simple_001_001_global_flag = 1;
  svp_simple_001_001_global_var = 0;
  svp_simple_001_001_global_var = 1;
  enable_isr(2);          /* line 46 */
  idlerun();
}
```

`isr_1` preempts the main task somewhere inside `[32, 35]`, sets the flag that
guards the read at line 55, calls `enable_isr(2)`, and `isr_2` — priority 2,
strictly higher than `isr_1`'s 1 — preempts *it* and performs the read. The
masking that looked like a proof is not one.

This is the pattern [[LLM Stage Design]]'s table calls *"ISR re-enables a
lower-priority interrupt inside itself"*, except here it re-enables a
**higher**-priority one, and the consequence is stronger: it invalidates a
masking fact established in a different flow.

## The corrected rule

> Interrupt *n* is masked throughout `[A₁, A₂]` only if
> **(a)** *n* is masked at every point of every path from `A₁` to `A₂` in the
> local flow, **and**
> **(b)** no flow that may itself execute within that interval re-enables *n*.

Clause (b) is transitive and has to be computed to a fixpoint: the flows that may
execute within the interval are those not masked under clause (a), which depends
on (b). Start from "everything may run" and tighten, never the other way round —
starting from "nothing may run" and loosening would report a proof before it has
one.

`common.defs.schema.json` carries this in two fields: `disabled_throughout` means
the conjunction of (a) and (b), and `reenabled_within_interval_by` names the
flows that made clause (b) fail. The contract does not offer a field for "masked
according to the local CFG", deliberately: there is no honest use for that value
on its own.

## Why the trap in the same file is a trap

The planted false positive immediately below the bug point is the mirror image:

```
//1.svp_simple_001_001_global_var<W#43><R#63><W#44>
```

Here `A₁` and `A₂` are `isr_1`'s two writes at lines 43 and 44, and `B` is
`isr_2`'s read. `isr_2` has the higher priority, so preemption is possible on
priority grounds — but interrupt 2 was masked by the main task at line 28 and
`isr_1` only re-enables it at line 46, **after both writes**. Clause (a) holds
over `[43, 44]`, and clause (b) holds too, because the only flow that could
re-enable interrupt 2 inside that interval is `isr_1` itself and it does not do
so until afterwards. One critical section covers the whole interval: the trap
shape from the pattern table, and provably infeasible.

The two candidates differ *only* in where the interval sits relative to line 46.
Any implementation that gets one of them right and the other wrong is not
modelling the interval property; it is guessing.

Both are shipped as fixtures — `contracts/examples/c2-bugpoint.json` and
`contracts/examples/c2-trap.json` — so that stage 2 can be tested against the
distinction as soon as it exists.

## Correction (2026-10-22, W5): the trap is not provably infeasible

Written when stage 2 was implemented, and left below the original text rather
than edited into it, because the reasoning above is how the mistake reads from
the inside.

**The bug-point half of this page stands.** Stage 2 keeps
`<W#32>,<R#55>,<W#35>`, and for exactly the reason given: computed from main's
CFG alone, irq 2 is masked over `[32, 35]`; with `isr_1`'s `enable_isr(2)`
applied wherever `isr_1` may run, it is not. The run's context record says so
and names `isr_1` in `reenabled_within_interval_by`.

**The trap half does not.** The argument for `<W#43><R#63><W#44>` — "interrupt 2
was masked by the main task at line 28 and `isr_1` only re-enables it at line
46, after both writes" — silently assumes that `isr_1` always *starts* with
irq 2 masked. Racebench's README says an interrupt may fire whenever it is
enabled, at an indeterminate moment and position, **an indeterminate number of
times**. Under that model `isr_1` may start with irq 2 unmasked in two
independent ways:

1. **Before main's `disable_isr(2)`.** `init()`, called at line 26, runs
   `enable_isr(-1)`, and main masks irq 2 only at line 28. `isr_1` may fire in between —
   indeed before `init()` too, with `initial_state: all-enabled` — and then
   irq 2 is unmasked throughout its writes at 43 and 44.
2. **After an earlier activation of itself.** `isr_1`'s `enable_isr(2)` at line
   46 is a global unlock and persists after it returns. A second activation of
   `isr_1` starts with irq 2 unmasked even if main masked it before `isr_1`
   could ever fire.

In both, `isr_2` (priority 2 > 1) may preempt `isr_1` between the two writes
and read the intermediate value. The interleaving is reachable; a sound stage 2
keeps the candidate, and a correct solver should answer SAT, not UNSAT.

The rule this adds is **Soundness Assumptions F8**: *an ISR's masking state on
entry is the union of the states at every point where it may fire, in every
flow* — never the state at the point the interval's author had in mind. Route 2
also rests on **F7**: an ISR's enables may persist after it returns.

What changed because of it:

* `contracts/examples/c2-trap.json` and `c2-bugpoint.json` now carry the masking
  and preemption blocks stage 2 actually emits. The originals reported the
  *local* view at each access (`disabled: [2]` at main's line 32) — the value
  this page warns against, and the one stage 2 cannot soundly produce.
* `contracts/examples/run-fixture/` no longer has the solver return UNSAT on this
  trap. The UNSAT example is now the file's *second* trap,
  `<W#32><R#60><W#35>` (`c2-trap-array-index.json`), where it is true: `B` reads
  element 1000 and `A₂` writes only element 9999.
* The label itself is **not** changed. Correcting a label is re-deciding the
  ground truth rather than reading it — the same line the errata draws for
  `svp_simple_019_001` (Soundness Assumptions I3). It is recorded as an open
  question and in [[Contradictions]].

### And the fixpoint direction

This page also said clause (b) must be computed "starting from 'everything may
run' and tightening, never the other way round". Both directions are sound *at
convergence*; the difference is what an intermediate iterate means. Descending
from top gives a sound answer at every step, but on a finite lattice it may stop
at a fixpoint strictly larger than the least one when flows may preempt each
other cyclically (equal priorities, re-entrancy). `irqrace.masking` therefore
computes the **least** fixpoint by ascending iteration and **never returns an
unconverged iterate**: hitting the round bound raises instead of answering
(`test_an_intermediate_iterate_is_never_returned`). The concern this page
raised — reporting a proof before having one — is met by that rule rather than
by the direction.
