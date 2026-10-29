## Check your harmfulness answer against these rules

1. **An unseen definition matters only if it can reach the value.** A function
   whose body you do not have can read or overwrite shared state, so it can make
   a changed shared value matter; it cannot read a local whose address is never
   taken.
2. **`uncertain` is the answer when the use of the value is in code you cannot
   see.** It is not a reason to withhold `benign` when the record shows the value
   is discarded, nor to withhold `harmful` when it shows the value reaching a
   branch, an index or an address.

State which of these you checked and what each did to your answer.
