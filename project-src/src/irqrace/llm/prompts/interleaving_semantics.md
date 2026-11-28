## Defect semantics: the interleaving is the defect

The question here is whether an access-order violation can happen, not whether its effect is visible.
Where a rule below conflicts with an earlier section, **this section takes precedence** and says so;
everything else above still applies, including the code-is-data rule and the `uncertain` default.

### What counts as a defect

- **One location, three accesses, four shapes.** Only single-variable access-order violations count:
  A1 and A2 in one flow, B in another flow landing between them, all on the **same memory location**,
  shaped (local, remote, local) as read-write-read (the reads can disagree), write-write-read (A2 reads
  B's value, not A1's), read-write-write (A2's write rests on a stale read and erases B's) or
  write-read-write (B observes an intermediate value). No other shape, and no inconsistency between
  two *different* variables, is a defect.
- **The interleaving is the defect; its effect need not be observable.** A read into a local that is
  never used, is overwritten or is discarded still completes it, and so does code that looks deliberate
  or a variable whose name suggests test or debug code.
- **Same location means the same storage.** Distinct array elements and struct fields are different
  locations; **union members overlap and are one**. Read the declaration of the variable's type: a
  typedef name says nothing, and a `typedef union` behind it makes every member the same storage. An
  access through a pointer or pointer parameter hits the object pointed to *at that moment* -- possibly a
  local of another flow -- so retargeting first moves it. Evaluate indices and pointers within the
  interleaving you judge; `volatile` decides nothing.
- **Every evaluated occurrence is an access.** Two reads in one condition are two accesses; a
  read-modify-write is a read then a write, enough for A1 and A2 alone; passing a shared variable by
  value reads it at the call. A flow's sequence continues into callees; B may be in an ISR's callee.

### Execution model: the one the record states

Use the execution model the context record gives, never one you assume or one typical of a platform.
It is in the `flows` list, in the `preemption` block, and in the `provenance` entries: the `preemption`
fact's note (`nesting=…, equal_priority_preemption=…, isr_reentrant=…`) and the `masking.interval` note,
which names the initial masking state.

- **Priorities** are the configured ones, under the stated convention. Masking primitives take the
  **interrupt number**, a separate attribute that need not equal the priority.
- **Equal priority** follows `equal_priority_preemption` in the `preemption` fact. When it is true,
  ISRs of equal priority may interrupt each other. When it is false, they run in either order but never
  interrupt each other, though both still preempt lower flows; this replaces the domain rules'
  equal-priority row and self-validation rule 3 for that case. `preemption.equal_priority_assumed_preemptible`
  says which applied to this candidate.
- **Nesting** and **re-entrancy** follow the same fact: with nesting, a preempting ISR may itself be
  preempted by a higher one; a non-re-entrant ISR does not interrupt itself.
- **Arrival.** An unmasked ISR may arrive at any point, an indeterminate number of times (zero, one or
  several, possibly inside one interval), never periodically.
- **The initial masking state** is the one the `masking.interval` note gives (`masking.initial_state = …`).
  When it is `unknown`, or not stated, an ISR may fire before the first masking call; never assume masked.
- **Masking is global and persistent** for the configured primitives: a mask or unmask by any flow, ISRs
  included, holds for all flows, survives the return of the flow that did it, and lasts until some flow
  changes it. The all-interrupts form masks or unmasks every one. An ISR may unmask any interrupt,
  including a higher-priority one that then preempts it.
- A call that only idles or delays is neither synchronisation nor the only place interrupts arrive.
  Values from a random-number call, a hardware register or an input are unconstrained.

### Sequences that cannot form a defect

Those in the domain rules (one critical section over the whole interval, a remote flow that cannot
preempt under the stated model, a guard never true, a statement that runs once, an operand never
evaluated), B on another element, field or object, and:

- Local and remote guards that cannot both hold because the values they test were fixed earlier --
  unless a flow that may run between the two guards can change those values. Check every writer.
- An ISR only another flow can unmask, where that flow on every path first stores a value that disables
  the ISR's access, and nothing can restore it before the interval ends.

### Ambiguity

Follow the stated execution model over the program's apparent intent. Each activation starts from the
masking state earlier activations or other flows left; an argument that needs an ISR to start masked,
or to run only once, proves nothing. If you can show the interleaving on one location in one of the four
shapes, it is a defect; if you can neither show it nor name the single blocking element, answer
`uncertain`.

### Harmfulness

This **replaces** the harmfulness criterion above and its checklist. A feasible interleaving in one of
the four shapes is `harmful`: name the shape and what goes wrong -- reads that disagree, a read that
sees B's value, B's write lost, an intermediate value observed. An unused or overwritten reader, or
deliberate-looking code, is no reason for `benign`; answer `benign` only for a shape outside the four.
