## This request is a checklist

Earlier sections describe one candidate. This request carries **every candidate on one shared
variable** of the same program, listed as `<item>` entries inside `<checklist>`. The fields they
share are in `<shared_context>` and the source bodies are given once; each item carries only the
fields where it differs (its accesses, call paths, masking state, solver verdict, pattern). An
item plus the shared context is the whole context record of that candidate. Everything said
above about one candidate applies to each item.

Work in two parts, in this order.

**1. Shared findings.** Before judging any item, state the facts that hold for the variable as a
whole, each with an identifier (`F1`, `F2`, ...) and line numbers: which flows access the
variable and which of them can preempt which; every masking region that covers its accesses and
which flows may unmask inside it; the values the writers list allows for each guard on it (only
when the list is `proven`); for arrays and pointers, which accesses can address the same storage.
A fact you cannot establish is not a finding: leave it out.

**2. One answer per item.** Then answer every item, by its id, exactly once.

- Judge each item on its own lines. A shared finding decides an item only if you say **which of
  the item's accesses it covers**: an item is blocked by a masking region only if its A1-to-A2
  interval lies inside that region and its B is in a flow the region masks.
- Items that look alike are still separate questions. They differ in B, in the path or in the
  interval; check the difference before reusing an argument.
- `infeasible` needs the single blocking element, cited with the item's own line numbers.
- If you cannot settle an item, answer `uncertain` for it. Do not let one hard item lower your
  care on the others, and do not skip any.

Do not answer an id that is not in the checklist, and do not merge items. The analyzer checks
that every id is answered once; an item left out is reported as uncertain.
