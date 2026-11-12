## Evaluation variant: confidence from a fixed rubric

This section replaces any free choice of the `confidence` number, in either question, and nothing
else. The number is read off the table below from what your answer rests on.

Before you give the number, list the facts your verdict depends on and sort each one:

- **shown** -- the record establishes it: numbered source lines, a field of the record, a `writers`
  list with status `proven`, a configuration fact marked `assumed_from_config`, or a value the rules
  above leave unconstrained.
- **defaulted** -- the record leaves it open and you applied a safe default the rules above state:
  unknown masking treated as enabled, an unavailable body assumed to access the variable, a guard
  over a `writers` list with status `unknown` treated as satisfiable, a use in code you cannot see
  treated as possible.
- **assumed** -- anything else: a value, a path or a body you did not see and no default covers, a
  reading of the program's intent, or a solver witness's values where they rest on the aspects listed
  in `unconstrained`.

| Level | The verdict rests on | `confidence` |
| --- | --- | --- |
| A | shown facts only | 0.95 |
| B | shown facts and one defaulted fact | 0.85 |
| C | shown facts and two or more defaulted facts | 0.75 |
| D | at least one assumed fact | 0.60 |
| E | the verdict is `uncertain`, and one missing fact would decide it | 0.45 |
| F | the verdict is `uncertain`, and more than one missing fact would be needed | 0.30 |

End your reasoning with one line, `Rubric: <level>; defaulted: <facts or none>; assumed: <facts or
none>`, and give exactly the number the table assigns to that level. The level describes the
evidence, not how sure you feel: two answers that rest on the same kinds of fact get the same number.
