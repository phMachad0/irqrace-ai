## Evaluation variant: a `feasible` answer carries its witness

This section sharpens the Ambiguity rule above and replaces nothing else: "show the interleaving"
there means writing the witness below.

Answer `feasible` only if your reasoning contains, under the heading `Witness:`, one concrete
execution that forms the interleaving, with all four of these items:

1. **Arrival.** The point in the local flow, after `A1` and before `A2`, at which the remote flow
   starts, cited by line. If the execution needs more than one activation, or a nested preemption,
   list each one in order with the line where it lands.
2. **Masking there.** The masking state at that point -- which interrupt numbers are masked and which
   are not -- and the statements, in any flow, that leave it so. If the remote flow can run only
   because an earlier activation or another flow unmasked it, name that step.
3. **Values.** For every guard that `A1`, `B` or `A2` sits under, and every index or pointer they go
   through, the value it takes in this execution and the store or initialiser that produces it. A
   value the rules above leave unconstrained may be chosen freely; say which one you chose.
4. **Effect at the accesses.** What the three accesses then read or write on the one location: the
   two values the reads of `A1` and `A2` disagree on, the value of `B` that `A2` reads, the write of
   `B` that `A2` erases, or the intermediate value `B` reads. A later use of that value is not
   required.

If you cannot fill every item from the record, answer `uncertain` and say which item is missing.
A missing item is not a reason for `infeasible`, which still needs the single blocking element. A
solver `sat` result is not a witness by itself: its execution may rest on values listed in
`unconstrained`, so use it only if you can fill the four items from the code.
