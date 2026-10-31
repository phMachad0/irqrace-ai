## You may ask for more code

The context record holds what the static stages judged relevant, but they can
miss what your answer depends on: a helper they did not include, a macro, a
type, another access to the variable. **You can ask for any of these.** Asking
is optional and never counts against your answer. Ask whenever you would
otherwise be guessing; if the record is enough, answer directly.

Before you settle on `infeasible` or `benign`, check what that answer rests on.
If it rests on code you have not read, ask for that code first.

To ask, emit a JSON array in a fenced ```request block, then stop. Do not answer
in the same turn as a request. You may request several items at a time, and you
may request again after receiving replies.

```request
[{"kind": "function_definition", "args": {"function": "handle_packet"}}]
```

Available `kind` values and their required arguments:

| `kind` | Required `args` |
| --- | --- |
| `function_definition` | `function` |
| `isr_body` | `flow` |
| `macro_expansion` | `macro` (optionally `file`, `line` to pick the expansion site) |
| `all_accesses_to` | `variable` |
| `all_call_paths` | `function` |
| `type_definition` | `type_name` |
| `global_declaration` | `variable` |

A reply may come back `not_found`. That is an answer too: a definition you could
not obtain may access the shared variable, so its absence cannot support
`infeasible` or `benign`.
