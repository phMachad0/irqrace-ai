## Harmfulness

Judge harmfulness only after feasibility, and only for the value the
interleaving changes. Which value that is depends on the pattern:

| Pattern | What the interleaving changes |
| --- | --- |
| `RWR` | `A1` and `A2` read different values in one run of the local flow. |
| `WWR` | `A2` reads `B`'s value instead of the one `A1` wrote. |
| `WRW` | `B` reads the intermediate value `A1` wrote, which `A2` then replaces. |
| `RWW` | `B`'s write is lost: `A2` overwrites it, often with a value computed from `A1`'s read. |

The interleaving is **harmful** if that value -- through assignments, in any
flow -- reaches a branch condition, an array index, a dereferenced address, a
call, persistent shared state or an output, or if two values that should agree
(the two reads of `RWR`) are used together. A branch that is evaluated before
the changed value exists does not count.

It is **benign** only for a specific, checkable reason, such as: the changed
value is discarded (stored in a local that is never read and whose address is
not taken); the lost write in `RWW` is never read by anyone; every value the
location can hold leads to the same behaviour. `value_use` in the provenance
says where each relevant read's value goes within its function. "It looks like a
counter" is not a reason. If the use is in code you cannot see, the answer is
`uncertain`, not `benign`.

A defect being *deliberate* -- a variable the programmer knowingly left
unsynchronised -- is a benignity claim, and it needs evidence in the code, not a
guess about intent.
