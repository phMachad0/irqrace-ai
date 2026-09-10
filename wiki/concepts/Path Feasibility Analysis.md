---
type: concept
tags: [wiki, concept]
sources: ["[[IntRace (paper)]]", "[[SDRacer (paper)]]"]
updated: 2026-08-17
status: draft
---

# Path Feasibility Analysis

The expensive last filter: given a candidate pair or triple that matched a pattern, decide
whether any real execution can reach both accesses in the required order.

Most static false positives in this literature die here. Typical shape, from
[[IntRace (paper)]]'s Racebench case No.3: the task reaches its access only when `i ≠ 2`,
while the ISR's access sits under a contradictory condition, so the interleaving is
unreachable and the reported race is spurious. IntRace cut that case from 10 warnings to 1.

**How IntRace does it** (§3.3): build a symbolic summary of each ISR, splice the
high-priority block into the low-priority block at the preemption point — turning the
concurrent question into a reachability question over a serialized program — construct the
path constraints, and discharge them with Z3. Loop unfolding depth is user-specified.

**Cost.** IntRace spends **69.70%** of total analysis time in this stage (versus 8.87% for
pattern matching and 21.43% for concurrency-relationship analysis), and it removes **86.2%**
of what reaches it. That trade — most of the time for most of the precision — is the central
empirical result to carry into the thesis.

**Alternatives to solving.** [[SDRacer (tool)]] answers the same question by *execution*:
force the interrupt to fire at the candidate point on a virtual platform and see whether the
state is reachable. The BMC tools answer it by construction — an unsatisfiable formula means
the path was infeasible — which is why [[NIChecker (tool)]] and [[BMC4AV (tool)]] have no
separate feasibility stage.

Note the shared trick across every approach here: **turn a concurrent program into a
sequential one and ask a reachability question**. IntRace splices blocks,
[[Lazy Sequentialization]] does it wholesale, Du et al. do it for verification. The
differences are in how faithfully interrupt semantics survive the transformation.

## Only a solver may discard

For [[Thesis Goal]] this stage has a special status: an `UNSAT` result is a **proof** that the
interleaving cannot occur, and [[Soundness and False Negatives]] permits a filter to drop a
candidate only on such a proof. That makes path feasibility the last component in the pipeline
allowed to remove anything — and it makes the LLM triage stage a *ranker*, not a filter, since
its judgement is not a proof ([[Pipeline Design]]).

**The stage is therefore fixed in the pipeline, ahead of the LLM** ([[Pipeline Design]]). It is
not an ablation option, for three compounding reasons: it is the only sound filter in the
design; it removes 86.2% of what reaches it, which is what makes per-candidate LLM triage
affordable at all (~13 candidates per program reaching the model instead of ~95); and it matches
[[LLift (paper)]]'s architecture, where symbolic execution runs first and the LLM receives only
the undecided residue.

The corollary is that the solver's *failures* are as informative as its successes. LLift exists
because UBITect's symbolic execution timed out on 40% of cases, and those timeouts were where
the real bugs hid. So a **timeout or unsupported construct must be recorded as `inconclusive`
and passed on**, never silently treated as `SAT` or dropped as noise — and the solver's partial
progress belongs in the context record handed to the LLM.

Related: [[Symbolic Execution]], [[Bounded Model Checking]], [[Precision Metrics]].
