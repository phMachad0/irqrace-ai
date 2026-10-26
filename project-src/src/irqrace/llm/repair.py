"""Stage B — proposing an interrupt-specific fix, with a required witness.

``wiki/Roadmap.md`` W7. The last stage before re-verification, and the one that
connects the two literatures this project sits between: [[SDRacer (paper)]] is
the only concurrency source that repairs and [[SkipAnalyzer (paper)]] the only
LLM source that does, and neither has met the other.

Three things shape the design, all from ``wiki/concepts/LLM-Assisted Repair.md``.

**The witness is required, and it comes first.** [[SAST-Genius (paper)]]'s
reusable idea is that its model produces a proof-of-concept rather than a
verdict: an artifact can be checked, a claim cannot. The analogue here is a
concrete interleaving -- the preemption point, the firing flow, the order of
the three accesses, and the state that differs from every serial execution.
That is checkable against the masking analysis and encodable as a CBMC
assertion, and a fix whose author cannot state it is fixing the wrong thing.

**The vocabulary is closed and interrupt-specific.** [[SDRacer (paper)]] §4
enumerates it. A model reaching for a mutex has fallen back on thread
concurrency, which does not apply under asymmetric preemption, so
:class:`Strategy` does not offer one.

**Logic Rate is scored on effect, not text.** [[SkipAnalyzer (paper)]] compares
patches to hand-written fixes and reports 97.3% on Null Dereference; its own
stated limitation is that "logically correct" therefore means an author agreed. Comparing
diffs textually would score formatting. :func:`logic_rate` instead compares
what the patch *does* -- strategy, the interrupts it masks, and the region it
covers -- against the reference fix, so two patches that protect the same
interval with the same interrupts agree even when written differently.

**Latency is a correctness property**, which is why ``latency_note`` is
mandatory rather than advisory. SDRacer measured repair overhead below 0.09 on
9 of 11 subjects and markedly worse on two, because disabling interrupts
changed the main task's control flow. A patch that masks interrupts across a
long loop has traded a race for a deadline miss.
"""

from __future__ import annotations

import dataclasses
import enum
import functools
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from irqrace import contracts
from irqrace.llm.annotations import locate_suite
from irqrace.llm.backends import ChatRequest
from irqrace.llm.client import (
    MAX_TOKENS,
    Conversation,
    TriageClient,
    evidence_hash,
    render_record,
)
from irqrace.llm.prompts import FULL, PromptConfig, _read


class Strategy(str, enum.Enum):
    """The closed repair vocabulary. No mutex, by construction."""

    #: disable_isr(n) before A1, enable_isr(n) after A2.
    mask_interval = "mask_interval"
    #: Widen a critical section that already exists nearby.
    extend_section = "extend_section"
    #: Merge two adjacent sections whose gap is the defect.
    merge_sections = "merge_sections"


class Witness(BaseModel):
    """The interleaving that makes this a defect. Required, and stated first."""

    firing_flow: str = Field(
        description="Which flow preempts, by id — e.g. 'isr_2'."
    )
    preemption_point: str = Field(
        description=(
            "Where it fires, with a line number: between which two statements "
            "of the interrupted flow."
        )
    )
    access_order: list[str] = Field(
        description="Execution order of the accesses by role, e.g. ['A1','B','A2']."
    )
    divergence: str = Field(
        description=(
            "The value or state after this interleaving that differs from every "
            "serial execution. This is what makes it a defect rather than a "
            "reordering."
        )
    )


class Patch(BaseModel):
    """A proposed fix. Field order is the order the model must think in."""

    reasoning: str
    witness: Witness
    strategy: Strategy
    masked_irqs: list[int] = Field(
        description="Interrupt numbers the patch masks. -1 means all."
    )
    covers_from_line: int
    covers_to_line: int
    latency_note: str = Field(
        description=(
            "What the critical section now covers, and whether it is bounded. "
            "Required even when the answer is 'a few statements'."
        )
    )
    diff: str = Field(description="Unified diff against the file as given.")


@dataclasses.dataclass(frozen=True)
class ReferenceFix:
    """A hand-written fix, for Logic Rate. The ground truth of this stage."""

    candidate_id: str
    strategy: Strategy
    masked_irqs: frozenset[int]
    covers_from_line: int
    covers_to_line: int
    #: Why this is the right fix, and what a plausible wrong one looks like.
    rationale: str
    #: Set when masking the obvious interrupt alone leaves a hole.
    also_mask_note: str = ""


REPAIR_TASK = (
    "This candidate has been judged a real defect. Propose a fix."
)


def default_repair_prompt() -> str:
    """The contents of ``prompts/repair.md``."""
    return _read("repair.md")


@functools.lru_cache(maxsize=1)
def _patch_schema_hash() -> str:
    blob = json.dumps(Patch.model_json_schema(), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _repair_config_hash(config: PromptConfig, repair_prompt: str) -> str:
    blob = f"repair:{config.hash()}:{hashlib.sha256(repair_prompt.encode('utf-8')).hexdigest()}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class RepairClient:
    """Runs the repair stage. Shares the backend seam and cache with triage."""

    def __init__(self, config: PromptConfig = FULL, **kwargs: Any):
        # Composition over inheritance: repair reuses the triage client's
        # backend handling, accounting, caching and transcript writing, and
        # differs only in the prompt and the schema.
        self._triage = TriageClient(config, **kwargs)

    @property
    def backend(self):
        return self._triage.backend

    @property
    def spend(self):
        return self._triage.spend

    @property
    def caveats(self) -> list[str]:
        return self._triage.caveats

    def repair(
        self,
        record: dict[str, Any],
        repair_prompt: str | None = None,
        *,
        sample: int = 0,
        run_dir: Path | None = None,
    ) -> Patch:
        """Propose one patch. Raises rather than returning a partial fix."""
        contracts.validate("c2", record, what=f"candidate {record.get('id')}")
        prompt_text = (
            repair_prompt if repair_prompt is not None else default_repair_prompt()
        )
        cfg_hash = _repair_config_hash(self._triage.config, prompt_text)
        fingerprint = record["fingerprint"]

        evidence = evidence_hash(record)

        cached = self._triage.cache.get(
            fingerprint,
            cfg_hash,
            self.backend.spec,
            sample,
            _patch_schema_hash(),
            evidence,
        )
        if cached is not None:
            patch = Patch.model_validate(cached)
            if run_dir is not None:
                _write_repair_artifacts(run_dir, record["id"], patch)
            return patch

        self.spend.candidates += 1
        system = f"{self._triage.config.system_prompt()}\n\n---\n\n{prompt_text}"
        user_msg = f"{REPAIR_TASK}\n\n{render_record(record)}"

        convo = Conversation(candidate_id=record["id"])
        convo.add("user", user_msg, stage="repair", turn=0)

        response = self._triage._call(
            ChatRequest(
                system=system,
                messages=[{"role": "user", "content": user_msg}],
                schema=Patch.model_json_schema(),
                schema_name="Patch",
                max_tokens=MAX_TOKENS,
                temperature=self._triage.temperature,
            )
        )
        if response.parsed is None:
            raise RuntimeError("the backend returned no structured patch")

        patch = Patch.model_validate(response.parsed)
        convo.add(
            "assistant",
            patch.model_dump(mode="json"),
            stage="repair",
            structured=True,
            backend=self.backend.spec,
            structured_mode=(
                response.structured_mode.value if response.structured_mode else None
            ),
        )

        if run_dir is not None:
            _write_repair_artifacts(run_dir, record["id"], patch, convo=convo)

        self._triage.cache.put(
            fingerprint,
            cfg_hash,
            self.backend.spec,
            patch.model_dump(mode="json"),
            sample,
            _patch_schema_hash(),
            evidence,
        )
        return patch


def _write_repair_artifacts(
    run_dir: Path,
    candidate_id: str,
    patch: Patch,
    *,
    convo: Conversation | None = None,
) -> None:
    if convo is not None:
        llm_dir = run_dir / "llm" / candidate_id
        llm_dir.mkdir(parents=True, exist_ok=True)
        with (llm_dir / "repair-turns.jsonl").open("w", encoding="utf-8") as fh:
            for turn in convo.turns:
                fh.write(json.dumps(turn, ensure_ascii=False) + "\n")

    rep_dir = run_dir / "repair" / candidate_id
    rep_dir.mkdir(parents=True, exist_ok=True)
    diff_text = patch.diff if patch.diff.endswith("\n") else patch.diff + "\n"
    (rep_dir / "patch.diff").write_text(diff_text, encoding="utf-8")
    (rep_dir / "patch.json").write_text(
        json.dumps(patch.model_dump(mode="json"), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )


# -- scoring ---------------------------------------------------------------

#: A unified-diff hunk header. Used only to check the diff is a diff.
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*$", re.M)


def is_wellformed_diff(diff: str) -> bool:
    """Cheap structural check: does this look like a unified diff at all?

    Not Syntax Rate. A patch that is not a diff cannot be applied, let alone
    compiled, and catching that needs no toolchain.
    """
    return bool(_HUNK.search(diff)) and any(
        line.startswith(("+", "-")) for line in diff.splitlines()
    )


def apply_unified_diff(source_text: str, diff_text: str) -> str | None:
    """Apply a unified diff to ``source_text`` in memory.

    Returns the patched source text, or ``None`` if the diff is malformed or
    its hunks do not apply cleanly within the file bounds.
    """
    if not is_wellformed_diff(diff_text):
        return None
    src_lines = source_text.splitlines()
    diff_lines = diff_text.splitlines()

    hunks: list[tuple[int, list[str]]] = []
    current_start: int | None = None
    current_body: list[str] = []

    for line in diff_lines:
        if line.startswith(("---", "+++", "diff ", "index ")):
            continue
        m = _HUNK.match(line)
        if m:
            if current_start is not None:
                hunks.append((current_start, current_body))
            current_start = int(m.group(1))
            current_body = []
            continue
        if current_start is not None:
            current_body.append(line)
    if current_start is not None:
        hunks.append((current_start, current_body))
    if not hunks:
        return None

    out: list[str] = []
    cursor = 0  # 0-based index into src_lines
    for start_1based, body in hunks:
        idx = max(0, start_1based - 1)
        if idx < cursor or idx > len(src_lines):
            return None
        out.extend(src_lines[cursor:idx])
        cursor = idx
        for raw in body:
            if not raw:
                if cursor < len(src_lines) and src_lines[cursor] == "":
                    out.append(src_lines[cursor])
                    cursor += 1
                continue
            prefix, content = raw[0], raw[1:]
            if prefix == " ":
                if cursor >= len(src_lines):
                    return None
                out.append(src_lines[cursor])
                cursor += 1
            elif prefix == "-":
                if cursor >= len(src_lines):
                    return None
                cursor += 1
            elif prefix == "+":
                out.append(content)
            elif prefix == "\\":
                continue
            else:
                return None

    out.extend(src_lines[cursor:])
    return "\n".join(out) + ("\n" if source_text.endswith("\n") else "")


def make_compile_checker(
    records_by_id: dict[str, dict[str, Any]],
    *,
    suite: Path | None = None,
    cc: str | None = None,
) -> Callable[[Patch], bool | None]:
    """Build a ``compile_check`` callback for :func:`syntax_rate`.

    Looks up a C compiler (`clang-14`, `clang`, or `gcc`) and the Racebench
    source tree. When either is absent on the current machine, the returned
    callable returns ``None`` so :func:`syntax_rate` reports ``None`` ("not
    measured") rather than a vacuous pass.
    """
    compiler = cc or next(
        (shutil.which(c) for c in ("clang-14", "clang", "gcc") if shutil.which(c)),
        None,
    )
    suite_dir = suite or locate_suite()

    # Map Patch object id or candidate lookup
    patch_to_record: dict[int, dict[str, Any]] = {}

    def _check(patch: Patch, record: dict[str, Any] | None = None) -> bool | None:
        if compiler is None or suite_dir is None or not suite_dir.is_dir():
            return None
        rec = record or patch_to_record.get(id(patch))
        if rec is None:
            return None
        rel = rec["accesses"][0]["source"]["file"]
        src_path = suite_dir / rel
        if not src_path.is_file():
            return None
        patched = apply_unified_diff(
            src_path.read_text(encoding="utf-8", errors="replace"), patch.diff
        )
        if patched is None:
            return False
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".c", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(patched)
            tmp_path = Path(tmp.name)
        try:
            proc = subprocess.run(
                [
                    compiler,
                    "-fsyntax-only",
                    f"-I{suite_dir}",
                    f"-I{src_path.parent}",
                    str(tmp_path),
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return proc.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return None
        finally:
            tmp_path.unlink(missing_ok=True)

    _check.bind = lambda patches: patch_to_record.update(  # type: ignore[attr-defined]
        {id(p): records_by_id[cid] for cid, p in patches.items() if cid in records_by_id}
    )
    return _check


def syntax_rate(
    patches: dict[str, Patch], compile_check
) -> tuple[float | None, list[str]]:
    """Fraction of patches a parser accepts.

    ``compile_check`` takes a :class:`Patch` and returns ``True`` if the
    patched source parses, or ``None`` if it could not run -- no compiler, no
    source tree. **A checker that cannot run yields ``None``, never a pass**:
    reporting an unmeasured Syntax Rate of 100% is the same silent success the
    recall gate guards against.
    """
    if hasattr(compile_check, "bind"):
        compile_check.bind(patches)
    results, failed = [], []
    for cid, patch in patches.items():
        outcome = compile_check(patch)
        if outcome is None:
            return None, []
        results.append(bool(outcome))
        if not outcome:
            failed.append(cid)
    return (sum(results) / len(results) if results else 0.0), failed


def logic_rate(
    patches: dict[str, Patch], references: dict[str, ReferenceFix]
) -> tuple[float, list[str]]:
    """Fraction of patches whose *effect* matches the hand-written fix.

    Compared on strategy, masked interrupts and covered region rather than on
    diff text, because two correct patches can be written differently and a
    textual comparison would score formatting.

    ``extend_section`` and ``mask_interval`` are accepted for one another when
    the covered region and the interrupts agree: whether a fix widens an
    existing critical section or opens a new one around the same interval is a
    style difference, and the reference names the tidier of the two.
    """
    equivalent = {Strategy.mask_interval, Strategy.extend_section}
    matched, missed = [], []
    for cid, patch in patches.items():
        ref = references.get(cid)
        if ref is None:
            missed.append(f"{cid}: no reference fix")
            continue
        irqs = set(patch.masked_irqs)
        masks_all = -1 in irqs or irqs >= ref.masked_irqs
        ok = (
            (patch.strategy == ref.strategy
             or {patch.strategy, ref.strategy} <= equivalent)
            and masks_all
            and patch.covers_from_line <= ref.covers_from_line
            and patch.covers_to_line >= ref.covers_to_line
        )
        matched.append(ok)
        if not ok:
            missed.append(
                f"{cid}: proposed {patch.strategy.value} masking "
                f"{sorted(patch.masked_irqs)} over "
                f"[{patch.covers_from_line}, {patch.covers_to_line}]; reference is "
                f"{ref.strategy.value} masking {sorted(ref.masked_irqs)} over "
                f"[{ref.covers_from_line}, {ref.covers_to_line}]"
            )
    return (sum(matched) / len(matched) if matched else 0.0), missed


def witness_problems(patch: Patch, record: dict[str, Any]) -> list[str]:
    """Check the witness against the record, mechanically.

    This is the half of validation that needs no solver: does the named firing
    flow exist and is it the one the analysis says preempts, and is the access
    order a permutation with the remote access between the local pair? A
    witness that fails here is wrong regardless of how good the diff looks.
    """
    problems = []
    flows = {f["id"] for f in record["flows"]}
    if patch.witness.firing_flow not in flows:
        problems.append(
            f"witness names flow {patch.witness.firing_flow!r}, which is not in "
            f"the record ({', '.join(sorted(flows))})"
        )
    remote = record.get("preemption", {}).get("preempting_flow")
    if remote and patch.witness.firing_flow != remote:
        problems.append(
            f"witness names {patch.witness.firing_flow!r} as the preempting flow; "
            f"the analysis says {remote!r}"
        )
    order = patch.witness.access_order
    if sorted(order) != ["A1", "A2", "B"]:
        problems.append(f"access order {order} is not a permutation of A1, B, A2")
    elif order.index("B") != 1:
        problems.append(
            f"access order {order} does not place the remote access between the "
            "local pair, so it does not describe an atomicity violation"
        )
    return problems


@dataclasses.dataclass(frozen=True)
class RepairScore:
    """Summary of a repair evaluation over the bug-point fixtures (Roadmap W7)."""

    n_repaired: int
    n_expected: int
    wellformed_rate: float
    malformed_diffs: tuple[str, ...]
    witness_rate: float
    witness_failures: dict[str, list[str]]
    syntax_rate: float | None
    syntax_failures: tuple[str, ...]
    logic_rate: float
    logic_missed: tuple[str, ...]

    @property
    def coverage(self) -> float:
        return self.n_repaired / self.n_expected if self.n_expected else 1.0

    @property
    def complete(self) -> bool:
        return self.n_repaired > 0 and self.coverage >= 1.0

    def report(self) -> str:
        lines = []
        if not self.complete:
            lines.append(
                f"INCOMPLETE — {self.n_repaired}/{self.n_expected} bug points "
                f"repaired ({self.coverage:.0%})."
            )
        syn_str = (
            "unmeasured (no C compiler or suite on this machine)"
            if self.syntax_rate is None
            else f"{self.syntax_rate:.1%} ({self.n_repaired - len(self.syntax_failures)}/{self.n_repaired})"
        )
        lines += [
            f"well-formed diff: {self.wellformed_rate:.1%} "
            f"({self.n_repaired - len(self.malformed_diffs)}/{self.n_repaired})",
            f"witness check:    {self.witness_rate:.1%} "
            f"({self.n_repaired - len(self.witness_failures)}/{self.n_repaired} mechanically valid)",
            f"Syntax Rate:      {syn_str}",
            f"Logic Rate:       {self.logic_rate:.1%} "
            f"({self.n_repaired - len(self.logic_missed)}/{self.n_repaired} match reference effect)",
        ]
        if self.witness_failures:
            lines.append("  [!] witness problems:")
            for cid, probs in self.witness_failures.items():
                for p in probs:
                    lines.append(f"      {cid}: {p}")
        if self.logic_missed:
            lines.append("  [!] logic rate misses:")
            for m in self.logic_missed:
                lines.append(f"      {m}")
        return "\n".join(lines)


def score_repairs(
    patches: dict[str, Patch],
    records_by_id: dict[str, dict[str, Any]],
    references: dict[str, ReferenceFix],
    *,
    n_expected: int | None = None,
    compile_check: Callable[[Patch], bool | None] | None = None,
) -> RepairScore:
    """Compute all W7 repair metrics over ``patches``."""
    n = len(patches)
    expected = len(references) if n_expected is None else n_expected

    malformed = tuple(
        cid for cid, p in patches.items() if not is_wellformed_diff(p.diff)
    )
    wf_rate = (n - len(malformed)) / n if n else 0.0

    wit_fails: dict[str, list[str]] = {}
    for cid, p in patches.items():
        if cid in records_by_id:
            probs = witness_problems(p, records_by_id[cid])
            if probs:
                wit_fails[cid] = probs
    wit_rate = (n - len(wit_fails)) / n if n else 0.0

    checker = compile_check or make_compile_checker(records_by_id)
    syn_rate, syn_failed = syntax_rate(patches, checker)
    log_rate, log_missed = logic_rate(patches, references)

    return RepairScore(
        n_repaired=n,
        n_expected=expected,
        wellformed_rate=wf_rate,
        malformed_diffs=malformed,
        witness_rate=wit_rate,
        witness_failures=wit_fails,
        syntax_rate=syn_rate,
        syntax_failures=tuple(syn_failed),
        logic_rate=log_rate,
        logic_missed=tuple(log_missed),
    )
