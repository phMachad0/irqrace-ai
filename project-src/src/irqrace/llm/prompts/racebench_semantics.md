## Benchmark semantics (evaluation variant)

This program follows an interrupt-race benchmark with its own notion of a defect and of execution.
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
  never used, is overwritten or is discarded still completes it, and so does code that looks deliberate.
- **Same location means the same storage.** Distinct array elements and struct fields are different
  locations; union members overlap and are one. An access through a pointer or pointer parameter hits
  the object pointed to *at that moment* -- possibly a local of another flow -- so retargeting first
  moves it. Evaluate indices and pointers within the interleaving you judge; `volatile` decides nothing.
- **A1 and A2 must be adjacent.** If on **every** path from A1 to A2 the same flow accesses the location
  again, the benchmark counts the finer triples, not this one: answer `infeasible` and name the
  intervening access as the blocking element. This narrows the feasibility question above. If the
  intervening access is on some paths only, the triple stands.
- **Every evaluated occurrence is an access.** Two reads in one condition are two accesses; a
  read-modify-write is a read then a write, enough for A1 and A2 alone; passing a shared variable by
  value reads it at the call. A flow's sequence continues into callees; B may be in an ISR's callee.

### Execution model

- One main flow runs at the lowest priority and never preempts. An ISR may preempt the main flow or a
  **strictly lower-priority** ISR whenever it is unmasked, at an indeterminate moment and position, an
  indeterminate number of times (zero, one or several, possibly inside one interval), never periodically.
  Nesting is allowed: a preempting ISR may itself be preempted by a higher one.
- **Equal priority does not preempt**: such ISRs run in either order but never interrupt each other
  (both still preempt lower flows). This replaces the domain rules' equal-priority row and
  self-validation rule 3 here. Priority is the configured one, larger meaning higher; masking
  primitives take the **interrupt number**, a separate attribute that need not equal the priority.
- The benchmark's initialisation call unmasks every interrupt. Nothing is stated about the state before
  it: use the record's masking state there and never assume masked.
- Masking one interrupt number stops only that ISR from starting; the all-interrupts form masks or
  unmasks every one. Masking state is **global and persistent**: a mask or unmask by any flow, ISRs
  included, holds for all flows, survives the return of the flow that did it, and lasts until some flow
  changes it. An ISR may unmask any interrupt, including a higher-priority one that then preempts it.
- A call that only idles or delays is neither synchronisation nor the only place interrupts arrive.
  Values from a random-number call or a hardware register are unconstrained.

### What the planted false positives test

Sequences that resemble a defect but cannot form one: those in the domain rules (one critical section
over the whole interval, a lower-priority remote flow, a guard never true, a statement that runs once,
an operand never evaluated), B on another element, field or object, A1 and A2 not adjacent, and:

- Local and remote guards that cannot both hold because the values they test were fixed earlier --
  unless a flow that may run between the two guards can change those values. Check every writer.
- An ISR only another flow can unmask, where that flow on every path first stores a value that disables
  the ISR's access, and nothing can restore it before the interval ends.

### Ambiguity

Follow the arrival model over the program's apparent intent. An ISR may fire before the main flow's
first masking call, and each activation starts from the masking state earlier activations or other
flows left; an argument that needs an ISR to start masked, or to run only once, proves nothing. If you
can show the interleaving on one location in one of the four shapes, it is a defect; if you can neither
show it nor name the single blocking element, answer `uncertain`.

### Harmfulness

This **replaces** the harmfulness criterion above and its checklist. A feasible interleaving in one of the four
shapes is `harmful`: name the shape and what goes wrong -- reads that disagree, a read that sees B's
value, B's write lost, an intermediate value observed. An unused or overwritten reader, or
deliberate-looking code, is no reason for `benign`; answer `benign` only for a shape outside the four.
