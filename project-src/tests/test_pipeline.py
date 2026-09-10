"""End-to-end W1 checks: the suite compiles, and SVF sees what it should.

Skipped when the toolchain is not built, so the unit tests still run on a
machine without clang-14, SVF or the benchmark.
"""
import pytest
from conftest import BENCH_CONFIGS, SUITE

from irqrace.build import build
from irqrace.config import Config
from irqrace.probe import probe
from irqrace.runstore import RunStore
from irqrace.toolchain import detect

TC = detect()
pytestmark = [
    pytest.mark.skipif(not TC.ok, reason=f"toolchain incomplete: {TC.problems}"),
    pytest.mark.skipif(not (SUITE / "README.md").exists(), reason="racebench not present"),
]

CONFIGS = sorted(BENCH_CONFIGS.glob("*.yaml"))


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_case_compiles_to_bitcode(path, tmp_path):
    """W1 done-when, first half: every one of the 31 simple cases compiles."""
    cfg = Config.load(path)
    result = build(cfg, tmp_path / "build")
    assert result.bitcode.exists() and result.bitcode.stat().st_size > 0
    assert result.translation_units == 2  # the case, plus common.c


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_svf_sees_the_module_and_the_config_matches_it(path, tmp_path):
    """W1 done-when, second half: SVF lists the globals, and the C1 interrupt
    model validates against the built bitcode in both directions (R7)."""
    cfg = Config.load(path)
    result = build(cfg, tmp_path / "build")
    report = probe(result.bitcode, cfg)

    assert report["globals_count"] > 0
    assert all(g["has_debug_info"] for g in report["globals"])
    # Every candidate must map back to a source range, so every load, store and
    # call the analysis will look at needs a DILocation.
    assert report["mappable_with_debug_loc"] == report["mappable_instructions"]

    errors = [w for w in report["warnings"] if w.get("severity") == "error"]
    assert not errors, errors

    # The masking primitives are externals in this suite; the analysis models
    # them rather than descending into them.
    assert "enable_isr" in report["functions_declared_only"]


def test_build_refuses_to_drop_debug_info(tmp_path):
    """-g is not a preference. Without it the context record cannot be built."""
    cfg = Config.load(CONFIGS[0])
    cfg.build["flags"] = ["-O0"]
    with pytest.raises(Exception, match="-g"):
        build(cfg, tmp_path / "build")


def test_a_full_run_directory_passes_its_own_contract(tmp_path):
    cfg = Config.load(CONFIGS[0])
    store = RunStore.create(cfg, run_root=tmp_path)
    result = build(cfg, store.root / "build")
    report = probe(result.bitcode, cfg)

    m = store.read_manifest()
    m["build"] = {
        "cc": cfg.build["cc"], "linker": cfg.build["linker"],
        "flags": list(cfg.build["flags"]),
        "translation_units": result.translation_units,
        "functions_with_bodies": report["functions_with_bodies"],
        "functions_declared_only": report["functions_declared_only"],
        "bitcode": "build/whole.bc", "bitcode_sha256": result.bitcode_sha256,
    }
    store.write_manifest(m)
    store.set_stage("build", "ok", wall_ms=1)

    assert store.check() == []
    assert store.read_manifest()["config_hash"] == cfg.hash()


def test_only_one_racebench_case_uses_function_pointers(tmp_path):
    """A W1 measurement, kept as a regression guard.

    Indirect calls are the recall-critical construct for stage 1: reachability
    is only as good as the call graph, and an unresolved target set must never
    be read as "calls nothing". Exactly one of the 31 simple cases actually
    dispatches through function pointers -- ``svp_simple_029_001``, which assigns
    three of them in an init routine and calls them from both the task and the
    ISR. That case is therefore the one to test stage 1's indirect-call handling
    on, and the other 30 cannot exercise it at all.

    Getting to this number needed a fix that is easy to miss: ``common.h``
    declares ``init()``, ``idlerun()`` and ``rand()`` K&R-style, with no
    parameter list, so after linking every call to them goes through a bitcast
    and ``CallBase::getCalledFunction()`` returns null. Before stripping those
    casts all 31 subjects looked like they used function pointers.
    """
    with_indirect = []
    for path in CONFIGS:
        cfg = Config.load(path)
        out = tmp_path / cfg.name
        report = probe(build(cfg, out).bitcode, cfg)
        assert report["direct_calls_through_cast"] > 0, (
            f"{cfg.name}: no calls through a cast -- the K&R prototypes in "
            "common.h should produce some; has the suite or the build changed?"
        )
        if report["indirect_call_sites"] > 0:
            with_indirect.append(cfg.name)
    assert with_indirect == ["svp_simple_029_001"], with_indirect
