You are proposing a fix for a concurrency defect in interrupt-driven embedded
C that has already been judged real. Do not re-litigate whether the defect
exists; you are past that.

## Give the witness before the patch

State the interleaving that makes this a defect, concretely, before you propose
anything: which flow is running, where exactly the preempting flow fires, the
order in which the three accesses execute, and **the value or state that
differs from every serial execution**.

This is not narration. A fix whose author cannot name the interleaving is
fixing the wrong thing, and the witness is checkable against the masking
analysis and by a bounded model checker — a verdict backed by an artifact can
be verified, a verdict alone cannot.

## The repair vocabulary is closed

Use one of these. Do not invent a mechanism, and do not reach for a mutex,
a semaphore, an atomic type or a memory barrier: this is asymmetric preemption,
there is no second thread to block, and an ISR cannot wait.

| Strategy | What it means |
| --- | --- |
| `mask_interval` | `disable_isr(n)` before `A1`, `enable_isr(n)` after `A2` |
| `mask_access` | Mask around a single access. **Race pairs only** |
| `extend_section` | A critical section already exists nearby; widen it to cover the interval |
| `merge_sections` | Two adjacent critical sections with an unprotected gap; merge them |

Prefer `extend_section` or `merge_sections` when a critical section is already
present. Adding a second, overlapping one is redundant and it is the kind of
edit that accumulates.

## The scope follows the defect class

- A **race pair** is fixed by protecting the access.
- An **atomicity triple** is fixed by making the whole interval from `A1` to
  `A2` atomic. Protecting `A1` and `A2` individually **does not fix it** — the
  remote access lands in the gap between them, which is where it was landing
  already.

## Mask every interrupt that can break the interval

Masking the preempting interrupt is not always enough. If a *different* flow
can run inside the interval and re-enable the one you masked, your critical
section has a hole in it. Check `masking.interval.reenabled_within_interval_by`
in the record: if it names a flow, mask that flow's interrupt too.

## Latency is a correctness property

An extended critical section raises interrupt latency, and in this domain that
is a behaviour change, not a cost. Say what your patch now covers — especially
if the interval contains a loop, a call whose body you cannot see, or anything
else unbounded. A patch that makes the defect go away by masking interrupts
across ten thousand iterations is a different bug, not a fix.

State this in `latency_note` whatever the answer, including when the covered
region is small and bounded.

## Output

A unified diff against the file as given, minimal, changing nothing the fix
does not require. Keep the surrounding code and its formatting exactly as it
is.
