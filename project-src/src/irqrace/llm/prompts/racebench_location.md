## Evaluation variant: settle the location first

This section replaces no rule above. It fixes the order in which you reason: the same-location
question is answered before any question of timing, masking or priority.

Begin your reasoning with a paragraph headed `Location:` that does two things.

1. For each of `A1`, `B` and `A2`, state the storage it touches: the variable and, through an array
   index or a pointer, the element or object. Evaluate each index and pointer **at the moment that
   access executes in the interleaving you are judging**, after every store any flow makes to it
   before that moment -- including stores the remote flow makes before `B`, and, for `A2`, stores
   the remote flow made while it preempted the local one.
2. Conclude with one of three lines: `same storage`; `different storage on every path`, citing the
   index or pointer values and the code that fixes them; or `cannot pin down`.

`different storage on every path` is a blocking element: answer `infeasible` and name it.
`cannot pin down` means the location may be shared, so continue as if it were. `same storage` settles
the question and is no reason for doubt about the rest of the answer. Only after this paragraph judge
whether `B` can land between `A1` and `A2`.
