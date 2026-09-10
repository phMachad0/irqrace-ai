---
type: concept
tags: [wiki, concept]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-23
status: solid
---

# Precision Metrics

The vocabulary every paper here uses, and the place where cross-paper comparison quietly
breaks down.

| Metric | Definition | Answers |
| --- | --- | --- |
| #WN | warnings reported | how much triage the user faces |
| #TP / #FP | true / false positives | — |
| #FN | false negatives | what was missed |
| **Precision** | #TP / #WN | how much of the output is real |
| **Hit rate (recall)** | #TP / #Vio | how much of the truth was found |
| **FP rate** | #FP / #WN | — |
| **Inspection Ratio** | (TP + FP) / (TP + FP + TN + FN) | how much a reviewer must read |

## Inspection Ratio — the right headline for a recall-first tool

From [[Reducing False Alarms (paper)]], and the only effort-aware metric anywhere in this wiki.
It measures the share of the candidate set (or codebase) a reviewer must examine to find the
actionable defects. Its virtue for [[Thesis Goal]] is that it **cannot be improved by
discarding candidates the way precision can**: recall is held at 100% by construction and the
Inspection Ratio carries the cost, so the two numbers together describe the tool honestly where
precision alone would flatter it. In that paper's Big-Vul run it falls from 50.49% to 2.44%
while recall falls from 46.90% to 40.66% — the precision figure alone would have told you only
the good half.

## Why the numbers do not compose

1. **#Vio is a judgement call, not a constant.** Every hit rate divides by an assumed
   ground truth. On the same 18 real-world programs, [[NIChecker (paper)]] works with 37–47
   violations and [[BMC4AV (paper)]] with 94. On [[Racebench]], NIChecker counts 54 atomicity
   violations, BMC4AV counts 38 over a 25-case subset, and [[IntRace (paper)]] counts 50
   *data races*. See [[Contradictions]].
2. **Precision without recall flatters.** NIChecker reports 100% precision and 0 FP on the
   real-world suite; BMC4AV's re-count puts its hit rate at 39.4%. A tool that only inspects
   variables the user nominated can be perfectly precise and still miss most of the bugs.
   Always demand both numbers.
3. **"No false negatives" usually means "manual inspection found none."** That is the basis
   in [[SDRacer (paper)]] and [[IntRace (paper)]]. For the BMC tools, absence of a
   counterexample is only relative to the unwind bound `u` and round bound `r` — see
   [[Bounded Model Checking]].
4. **Runtimes mix re-runs with copied numbers.** IntRace vs Rchecker, NIChecker vs
   intAtom/Rchecker, and BMC4AV vs intAtom/CPA4AV/NIChecker all include figures lifted from
   other papers on other hardware, because the baseline binaries were unobtainable. Each
   paper says so; summaries of them usually do not.
5. **On [[Racebench]], false positives are planted on purpose.** 33 of the 38 traps sit in
   the 31 simple cases, marked `//误报点`, several of them correctly protected by
   `disable_isr`/`enable_isr` ([[Racebench (documentation)]]). Precision measured there is
   *trap avoidance on adversarial code*, which is a real but narrow result — and the
   [[NASAC 2019 Prototype Competition]] scored a false positive at −3 against +2 for a
   detection, so the whole field's precision-first instinct is downstream of a scoring
   function that priced recall at zero.
6. **Benign defects are counted differently.** BMC4AV excludes `(R,W,W)` as benign; IntRace
   names unclassified benign races as a cause of its own false positives; SDRacer inspected
   its reported races and judged them all harmful.

7. **Counting units differ between per-variable and per-instance.** The
   [[Real-World Program Benchmark]]'s shipped ground truth counts one entry per shared variable
   (45 entries) while [[BMC4AV (paper)]] counts access-triple instances (94). Neither is wrong;
   quoting one against the other is ([[Contradictions]] #1).
8. **For LLM stages, add the model, the date and the prompt configuration.** Every model
   comparison in the LLM branch is already obsolete, and
   [[LLift (paper)]]'s ablation shows the same model moving from 0.15 to 1.00 recall on
   configuration alone — so a number without its prompt design describes nothing
   ([[Prompt Architecture]]). Report **consistency** (agreement across repeated runs) alongside
   accuracy, since a verdict that changes between runs is not a usable result.

Practical rule for this wiki: quote a metric only with its ground-truth assumption, its
counting unit, its hardware, and whether the number was re-run or copied — and, for LLM
results, the model, date and prompt configuration.
