"""W8 end-to-end integration over a C3 RunStore and CLI."""

import json

from irqrace import cli, contracts
from irqrace.config import Config
from irqrace.llm import cache as cache_mod
from irqrace.llm.backends import (
    Backend,
    Capabilities,
    ChatRequest,
    ChatResponse,
    StructuredMode,
    Usage,
)
from irqrace.llm.cache import Cache
from irqrace.llm.fixtures import load_all
from irqrace.llm.pipeline import (
    prepare_context,
    read_triages,
    repair_store,
    triage_store,
)
from irqrace.llm.prompts import FULL
from irqrace.llm.repair import Patch, Strategy, Witness
from irqrace.llm.verdict import Bucket, Feasibility, Harmfulness
from irqrace.runstore import RunStore

FIXTURES = load_all()
PAIR = [f for f in FIXTURES if f.subject == "svp_simple_001_001"]
BUG, TRAP = sorted(PAIR, key=lambda f: f.label)


class FakeBackend(Backend):
    provider = "fake"

    def __init__(self, answers=()):
        super().__init__("v1")
        self._answers = list(answers)
        self.requests: list[ChatRequest] = []

    @property
    def capabilities(self):
        return Capabilities(structured=StructuredMode.native_schema, prompt_caching=True)

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        ans = self._answers.pop(0)
        payload = ans.model_dump(mode="json") if isinstance(ans, Patch) else ans
        usage = Usage(
            input_tokens=800,
            output_tokens=200,
            cache_read_tokens=600,
            price_in=5.0,
            price_out=25.0,
        )
        return ChatResponse(
            text=json.dumps(payload),
            parsed=payload,
            structured_mode=StructuredMode.native_schema,
            usage=usage,
        )


def _feas(verdict=Feasibility.feasible, conf=0.9):
    return {
        "reasoning": "isr_2 preempts the interval",
        "blocking_element": None if verdict is Feasibility.feasible else "disable_isr(2)",
        "verdict": verdict.value,
        "confidence": conf,
    }


def _harm(verdict=Harmfulness.harmful, conf=0.9):
    return {
        "reasoning": "indexes an array",
        "criterion_matched": "indexes an array",
        "verdict": verdict.value,
        "confidence": conf,
    }


def _patch() -> Patch:
    return Patch(
        reasoning="mask both irqs 1 and 2 across the loop",
        witness=Witness(
            firing_flow=BUG.record["preemption"]["preempting_flow"],
            preemption_point="between lines 32 and 35",
            access_order=["A1", "B", "A2"],
            divergence="reader observes torn element",
        ),
        strategy=Strategy.mask_interval,
        masked_irqs=[1, 2],
        covers_from_line=32,
        covers_to_line=35,
        latency_note="bounded 4-iteration loop",
        diff="@@ -31,3 +31,5 @@\n+  disable_isr(1);\n   x = 1;\n+  enable_isr(1);\n",
    )


def _seed_store(tmp_path, run_id="r-w8-test") -> RunStore:
    cfg_path = cli.REPO_ROOT / "bench" / "configs" / "svp_simple_001_001.yaml"
    cfg = Config.load(cfg_path)
    store = RunStore.create(cfg, run_root=tmp_path, run_id=run_id)
    store.append_candidates("stage1", [BUG.record, TRAP.record])
    store.set_stage("stage1", "ok", candidates_in=2, candidates_out=2, dropped_with_proof=0)
    return store


def test_prepare_context_writes_per_candidate_c2_records(tmp_path):
    store = _seed_store(tmp_path)
    records = prepare_context(store)
    assert len(records) == 2
    for r in records:
        p = store.root / "context" / f"{r['id']}.json"
        assert p.is_file()
        contracts.validate("c2", json.loads(p.read_text(encoding="utf-8")))
    assert store.check() == []


def test_triage_and_repair_store_preserve_c3_rule_6_and_manifest(tmp_path):
    store = _seed_store(tmp_path)
    cache = Cache(tmp_path / "cache")

    # FULL config uses decomposition: BUG gets (feasible, harmful), TRAP gets (infeasible,)
    triage_backend = FakeBackend(
        [_feas(Feasibility.feasible), _harm(Harmfulness.harmful), _feas(Feasibility.infeasible)]
    )
    summary = triage_store(
        store,
        config=FULL,
        backend=triage_backend,
        cache=cache,
        resolver_mode="mock",
    )
    assert summary["candidates_in"] == 2
    assert summary["candidates_out"] == 2
    assert summary["buckets"]["likely_real"] == 1
    assert summary["buckets"]["likely_infeasible"] == 1

    # Rule 6: every candidate emitted by stage 1 has a context & triage record
    assert store.check() == []
    contracts.validate("c3-manifest", store.read_manifest())
    triages = read_triages(store)
    assert len(triages) == 2
    assert triages[0].candidate_id == BUG.candidate_id
    assert triages[0].bucket is Bucket.likely_real

    # Stage 3: only likely_real candidates are repaired by default
    repair_backend = FakeBackend([_patch()])
    rep_summary = repair_store(
        store,
        config=FULL,
        backend=repair_backend,
        cache=cache,
    )
    assert set(rep_summary["patches"].keys()) == {BUG.candidate_id}
    assert (store.root / "repair" / BUG.candidate_id / "patch.diff").is_file()
    assert (store.root / "repair" / BUG.candidate_id / "patch.json").is_file()
    assert not (store.root / "repair" / TRAP.candidate_id / "patch.diff").exists()

    manifest = store.read_manifest()
    contracts.validate("c3-manifest", manifest)
    stages = {s["name"]: s for s in manifest["stages"]}
    assert stages["triage"]["status"] == "ok"
    assert stages["triage"]["dropped_with_proof"] == 0
    assert stages["repair"]["status"] == "ok"
    assert stages["repair"]["candidates_out"] == 1
    assert store.check() == []


def test_cli_llm_triage_and_repair_commands_over_cached_store(monkeypatch, tmp_path):
    from irqrace.llm import backends

    monkeypatch.setitem(backends.REGISTRY, "fake", lambda model: FakeBackend([]))

    store = _seed_store(tmp_path)
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(cache_mod, "DEFAULT_DIR", cache_dir)

    # Pre-warm cache using FakeBackend so CLI succeeds offline
    triage_store(
        store,
        config=FULL,
        backend=FakeBackend(
            [_feas(Feasibility.feasible), _harm(Harmfulness.harmful), _feas(Feasibility.infeasible)]
        ),
        cache=Cache(cache_dir),
        resolver_mode="mock",
    )
    repair_store(
        store,
        config=FULL,
        backend=FakeBackend([_patch()]),
        cache=Cache(cache_dir),
    )

    store2 = _seed_store(tmp_path, run_id="r-w8-cli")
    rc1 = cli.main(
        [
            "llm",
            "triage",
            str(store2.root),
            "--backend",
            "fake:v1",
            "--resolver",
            "mock",
        ]
    )
    assert rc1 == 0

    rc2 = cli.main(
        [
            "llm",
            "repair",
            str(store2.root),
            "--backend",
            "fake:v1",
        ]
    )
    assert rc2 == 0
    assert store2.check() == []
