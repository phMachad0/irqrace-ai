# Masking semantics, and the trap in computing them per flow

Written in W1, from the first fixture built by hand. It records a rule the
pipeline has to obey from stage 2 onward, and the concrete case that proves it.

## The rule

Stage 2 asks two questions about interrupt masking, and they are different
questions ([[Pair-Triple Unification]]):

* **point property**, for pairs — is interrupt *n* masked *at* access `A`?
* **interval property**, for triples — is interrupt *n* masked *throughout*
  `[A₁, A₂]`?

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
