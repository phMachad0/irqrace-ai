## Asking for what you lack

The context record ships the layers that are always useful: the accesses, the
flows, the call paths, the masking state and the enclosing function bodies. It
deliberately does **not** ship a precomputed slice. Anything else you need, ask
for, and it will be supplied before you answer.

Emit requests as a JSON array in a fenced ```request block, then stop. Do not
answer in the same turn as a request. You may request more than one item at a
time, and you may request again after receiving replies.

```request
[{"kind": "function_definition", "args": {"function": "handle_packet"}}]
```

Available `kind` values and their required arguments:

| `kind` | Required `args` |
| --- | --- |
| `function_definition` | `function` |
| `isr_body` | `flow` |
| `masking_state_at` | `file`, `line` |
| `macro_expansion` | `macro` (optionally `file`, `line` to pick the expansion site) |
| `all_accesses_to` | `variable` |
| `all_call_paths` | `function` |
| `type_definition` | `type_name` |
| `global_declaration` | `variable` |

A reply may come back as not found. That is an answer, and rule 2 of the
self-validation checklist applies to it: a definition you could not obtain is
one that may access the shared variable.

Ask for what would change your answer. Do not ask for context you will not use
-- what you request, how often, and how deep is measured, and that measurement
is what decides the shape of the context record.
