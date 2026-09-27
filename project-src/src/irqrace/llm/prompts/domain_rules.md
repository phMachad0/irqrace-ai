## When a preemption is actually possible

Your prior on concurrency comes largely from threads, and it is wrong here.
Under asymmetric preemption there is no happens-before relation to reason with
and no lock to find. The patterns below add to your ordinary reasoning about
the program; they do not replace it. Before applying any of them, check that
each access can execute at all.

**The priority convention in this codebase is: a larger number is a higher
priority.** The published literature disagrees with itself on this point, so
take the numbers in the context record at face value and apply this convention,
not one you may recall.

| Pattern | Verdict |
| --- | --- |
| One of the accesses sits under a guard that is **never true** -- a condition on a value the program never produces, or a loop bound that excludes it | **Infeasible** -- that access never executes, so the interleaving cannot be formed. Only if you can show *why* the guard is never true, citing where the values it tests come from. A guard you cannot evaluate from the record is satisfiable. |
| Both local accesses sit inside **one** critical section that covers the whole interval between them | **Infeasible.** The remote flow cannot fire in the interval. |
| Each local access sits in its **own** critical section, with an unprotected gap between them | **Still a real atomicity violation.** There is no data race on either access, and the gap is exactly where the remote access lands. Protecting both endpoints is not protecting the interval. |
| The preempting flow has **strictly lower** priority | **Infeasible** -- it cannot preempt. |
| The preempting flow has **equal** priority | **Possible.** Equal-priority preemption is unresolved in this project's assumption list. Treat it as able to preempt. |
| The interrupt is not yet enabled at this point in the flow | **Infeasible only if it is disabled on every path** that reaches the point. Disabled on the path you happened to read is not enough. |
| The same statement inside a loop serves as both `A1` and `A2` | **A valid triple** *if the statement can execute twice.* Two iterations of one statement are two accesses. |
| The same statement serves as both `A1` and `A2`, but executes **once** | **Infeasible.** Check the guard and the loop bounds before applying the rule above: a statement under a condition satisfiable by one iteration, or a variable named twice in one expression where only one occurrence is evaluated, supplies one access and not two. |
| An ISR **re-enables** a lower-priority interrupt inside itself | Masking is **dynamic**. A critical section in the local flow can be punctured by a flow that runs inside it; check `masking.interval.reenabled_within_interval_by` before trusting an interval. |

## Harmfulness

Judge harmfulness only after feasibility, and only by this criterion:

- The shared variable **feeds a branch condition** -> harmful.
- The shared variable is **used as an array index or dereferenced as a pointer**
  -> harmful.
- Otherwise, state the specific reason the interleaving cannot affect observable
  behaviour. "It looks like a counter" is not a reason. If you cannot name one,
  the answer is `uncertain`, not `benign`.

A defect being *deliberate* -- a variable the programmer knowingly left
unsynchronised -- is a benignity claim, and it needs evidence in the code, not a
guess about intent.
