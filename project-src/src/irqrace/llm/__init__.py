"""Track B — the LLM triage and repair stage.

Downstream of the solver, upstream of the report. The rule this package exists
to enforce: **a solver may drop a candidate; the LLM may not**
(``wiki/Thesis Goal.md``). Triage ranks, explains and buckets; the report keeps
everything.

Module map:

* :mod:`~irqrace.llm.verdict` -- the output contract. Four buckets, derived from
  two narrow questions rather than chosen by the model.
* :mod:`~irqrace.llm.prompts` -- the five ablation rows, as compositions of
  markdown assets.
* :mod:`~irqrace.llm.fixtures` -- the labelled evaluation set (Roadmap W1).
* :mod:`~irqrace.llm.backends` -- the provider seam. ``from_spec("ollama:...")``
  selects a model; the harness never imports an SDK. This is what lets the same
  prompt configuration be measured against several models, which is how
  [[LLift (paper)]]'s "prompt architecture dominates model choice" becomes a
  claim this project tests rather than cites.
* :mod:`~irqrace.llm.resolver` -- C4, the progressive-prompting backend.
* :mod:`~irqrace.llm.client` -- the harness that runs one row.
* :mod:`~irqrace.llm.cache` / :mod:`~irqrace.llm.cost` -- result cache and the
  cost model.
* :mod:`~irqrace.llm.scoring` -- recall gate, trap rejection, Inspection Ratio,
  consistency.
"""

from irqrace.llm.backends import Backend, from_spec
from irqrace.llm.verdict import Bucket, Feasibility, Harmfulness, Triage, bucket_of

__all__ = [
    "Backend",
    "Bucket",
    "Feasibility",
    "Harmfulness",
    "Triage",
    "bucket_of",
    "from_spec",
]
