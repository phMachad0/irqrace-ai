# Contracts — frozen 2026-08-31 (W1, days 1–3)

Four contracts, written as schema files with examples rather than as prose, so that Track A and
Track B can work in parallel and Track C can build against synthetic data
([[Roadmap]], *The idea that makes parallel work possible*).

| | Contract | File | Owner | Consumers |
| --- | --- | --- | --- | --- |
| **C1** | configuration file — interrupt model + analysis settings | `c1-config.schema.json` | A | A, C |
| **C2** | **context record** — one JSON object per candidate | `c2-context-record.schema.json` | A | B, C |
| **C3** | run store layout — directories, NDJSON, manifest | `c3-run-store.md`, `c3-manifest.schema.json`, `c3-log-event.schema.json` | A | B, C |
| **C4** | context request protocol — progressive-prompt requests and replies | `c4-context-request.schema.json`, `c4-context-reply.schema.json` | B | A |

`common.defs.schema.json` holds the definitions the four share — source ranges, flows,
accesses, masking states, call paths, provenance, solver results. Change it and you change all
four; that is the point, and it is why it is small.

## Versioning

Every instance document carries `schema_version` (`c1/1.0.0`, `c2/1.0.0`, …). **C2 is the
critical one** — it is the seam between the two people. The Roadmap's stated response to
contract churn is to freeze C2 by decree and *version it rather than renegotiate it*, so:

- **Patch** (`1.0.x`) — documentation only, no field changes.
- **Minor** (`1.x.0`) — new optional fields. Consumers written against `1.0.0` keep working.
- **Major** (`x.0.0`) — anything else. Requires the Monday interlock, and both sides state what
  broke.

Producers write the highest version they implement; consumers accept anything with the same
major version and ignore unknown fields. `additionalProperties: false` is set on the schemas so
that *typos* are caught during development — validation is run with
`irqrace contracts validate`, and forward-compatibility is a consumer-side rule, not a schema
rule.

## The five decisions these schemas encode

These are not stylistic. Each one is a recall decision taken in the wiki, made structural here
so it cannot be quietly reversed in code:

1. **Masking is three-valued** (`disabled` / `enabled` / `unknown`), and an interrupt is
   `disabled` only if it is disabled on *every* path. There is deliberately no boolean
   `is_masked` field to reach for ([[Pipeline Design]], stage 2).
2. **The interval property is separate from the point property.** Triples carry
   `masking.interval`; pairs do not. Answering one and inferring the other is the mistake
   [[Pair-Triple Unification]] exists to prevent.
3. **The solver verdict has four values, not two** — `unsat`, `sat`, `inconclusive`,
   `not_run` — and `inconclusive` requires a `reason`. Collapsing it into either decided
   outcome loses exactly the information the LLM stage exists to exploit.
4. **`provenance` is mandatory on every context record.** Partial evidence must be marked *as*
   partial; a model shown incomplete evidence declares candidates infeasible confidently, and
   that miss is invisible afterwards ([[LLM Stage Design]]).
5. **There is no `slice` field, and there is not meant to be one.** Context is retrieved on
   demand through C4 ([[Program Slicing]]). If a slice field ever appears, that decision has
   been reversed without anyone deciding to reverse it.

A sixth, structural rather than semantic: **`fingerprint` depends only on subject, class,
variable and access locations** — never on run id, timing or solver output — because Track B's
result cache is keyed by it.

## Examples

`examples/` holds one valid instance of each, all drawn from `svp_simple_001_001`, and a
`run-fixture/` directory conforming to C3. They are validated by `tests/test_contracts.py`, so
an example that drifts from its schema fails the build rather than misleading a reader.

The C2 example is the annotated bug point of `svp_simple_001_001`:
`svp_simple_001_001_global_array <W#32>,<R#55>,<W#35>` — a real `(W,R,W)` atomicity violation
where the main task writes the array in two separate loops and `isr_2` reads it in between.
The trap in the same file, `svp_simple_001_001_global_var <W#43><R#63><W#44>`, is
`examples/c2-trap.json`: `isr_1` writes the variable twice and `isr_2` reads it, but `isr_2`
has *higher* priority and is masked by `disable_isr(2)` in the main task until `isr_1` itself
calls `enable_isr(2)` — after both writes. Having both a real defect and its neighbouring trap
as fixtures is what makes schema gaps show up while they are cheap to fix.
