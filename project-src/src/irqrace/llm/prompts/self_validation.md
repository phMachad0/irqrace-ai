## Check your answer against these rules before you give it

These rules add no information. They restate what the analysis already assumes,
and they lean deliberately toward the safe answer. Apply each one to the answer
you are about to give, and change the answer if any of them fires.

1. **Unknown masking means enabled.** If the masking state along any path
   reaching an access is `unknown`, treat the interrupt as enabled there. An
   interrupt is disabled only when it is disabled on *every* path.
2. **An unavailable definition may access the variable.** If you could not
   obtain the body of a function on a call path, assume it accesses the shared
   variable. Do not conclude that a flow is clean because you could not see
   inside it.
3. **Equal priority means either may preempt.** Do not resolve an equal-priority
   pair in favour of the order that makes the candidate go away.
4. **`uncertain` is always a safe answer.** It costs a reviewer one candidate to
   read. `infeasible` on a real defect hides it, and nothing downstream will
   catch that. When you are weighing `infeasible` against `uncertain`, choose
   `uncertain` unless you can name the single element that makes the
   interleaving impossible.

State explicitly which of these four you checked and what each one did to your
answer.
