## Evaluation variant: a remote write that changes nothing

For one case, this section **overrides** two rules above: "its effect need not be observable" and
"answer `benign` only for a shape outside the four". Feasibility is not in question here; the case
concerns only whether the interleaving matters.

The interleaving is `benign` when **both** of these hold:

1. `B` is a write that stores the value the location already holds when `B` executes -- shown from
   the stores and the initialiser that can precede it, in every execution in which `B` lands between
   `A1` and `A2`; and
2. the local flow writes the location again between `A1` and `A2` on every path.

Then name it in `criterion_matched` as `remote write of the value already stored, rewritten before
A2`, citing the lines that show both parts. If either part cannot be shown from the record -- the
stored value may differ, or some path reaches `A2` without the local rewrite -- this section does not
apply and the rules above stand.
