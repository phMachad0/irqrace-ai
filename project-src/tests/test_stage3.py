"""Stage 3 -- path feasibility -- on small C programs and on Racebench.

The first half compiles tiny programs with the same clang the pipeline uses and
runs stages 1-3 on them, one soundness rule per test. Three of the tests pin
bugs the recall gate and the audit of every UNSAT verdict found while stage 3
was being written (W6-W7 diary): a volatile load counted as a write, a
preemption just before A2 that hid A2, and the back edge crossed once in total
instead of once per phase.

The second half is Racebench: the gate taken on what reaches the LLM, and the
specific verdicts the diary argues for.
"""
import json

import pytest
from conftest import BENCH_CONFIGS, ERRATA, SUITE

from irqrace.build import build
from irqrace.config import Config
from irqrace.evaluation import match_subject
from irqrace.groundtruth import load_suite
from irqrace.runstore import RunStore
from irqrace.stage1_driver import STAGE1_PATH, stage1
from irqrace.stage2 import stage2
from irqrace.stage3 import STAGE3_PATH, stage3
from irqrace.toolchain import detect

TC = detect()
pytestmark = pytest.mark.skipif(
    not TC.ok or not STAGE1_PATH.exists() or not STAGE3_PATH.exists(),
    reason="analysis binaries not built")

PRELUDE = """\
void disable_isr(int);
void enable_isr(int);
int rand(void);
"""

FLOWS = [
    {"id": "main", "kind": "task", "entry": "t_main", "priority": 0},
    {"id": "isr_1", "kind": "isr", "entry": "t_isr_1", "irq": 1, "priority": 1},
    {"id": "isr_2", "kind": "isr", "entry": "t_isr_2", "irq": 2, "priority": 2},
]


def run_c(tmp_path, body, *, flows=("main", "isr_1"), timeout_ms=10000):
    """Compile `body`, run stages 1-3, return the run store."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "t.c"
    src.write_text(PRELUDE + body)
    cfg = Config.from_dict({
        "subject": {"name": "t", "source_root": str(tmp_path), "sources": ["t.c"]},
        "flows": [f for f in FLOWS if f["id"] in flows],
        "masking": {"primitives": [{"function": "disable_isr", "effect": "disable"},
                                   {"function": "enable_isr", "effect": "enable"}]},
        "externals": {"models": [{"function": "rand", "effect": "none"}]},
        "analysis": {"solver": {"timeout_ms": timeout_ms}},
    })
    store = RunStore.create(cfg, run_root=tmp_path / "runs")
    result = build(cfg, store.root / "build")
    stage1(cfg, store, result.bitcode)
    stage2(cfg, store)
    stage3(cfg, store, result.bitcode)
    return store


def line_of(body, marker):
    """1-based line in the compiled file of the line containing `marker`."""
    for i, text in enumerate((PRELUDE + body).splitlines(), 1):
        if marker in text:
            return i
    raise AssertionError(marker)


def verdict(store, *lines):
    """The solver's verdict on the candidate at these lines, or the stage that
    dropped it before the solver saw it."""
    for c in store.read_candidates("stage2"):
        if [a["source"]["line"] for a in c["accesses"]] == list(lines):
            for row in (store.root / "solver" / "results.jsonl").read_text().splitlines():
                r = json.loads(row)
                if r["candidate_id"] == c["id"]:
                    return r
    for d in store.read_drops():
        if d["lines"] == list(lines):
            return {"verdict": f"stage2:{d['reason']}"}
    for c in store.read_candidates("stage1"):
        if [a["source"]["line"] for a in c["accesses"]] == list(lines):
            raise AssertionError("candidate lost between stage 1 and stage 2")
    raise AssertionError(f"no candidate at lines {lines}")


# -- the encoding -------------------------------------------------------------


def test_a_volatile_read_is_not_a_write(tmp_path):
    """LLVM counts a volatile load as may-write-to-memory. Read that way, an ISR
    that only reads a volatile array "writes everything", interference havocs
    main's loop counter between the guard and the index, and the index trap is
    no longer refutable. Every shared global in Racebench is volatile."""
    body = """\
volatile int a[10];
void t_main(void) {
  for (int i = 0; i < 10; i++)
    if (i == 7) a[i] = 1;            /* W */
}
void t_isr_1(void) { int r = a[3];   /* R */ }
"""
    store = run_c(tmp_path, body)
    assert verdict(store, line_of(body, "/* W */"), line_of(body, "/* R */"))["verdict"] == "unsat"


def test_a_preemption_just_before_a2_does_not_hide_a2(tmp_path):
    """Two adjacent writes in an ISR, a higher ISR reading in between: the only
    preemption point is the boundary right before A2. One flag for both
    decisions at that position made A2 unselectable and this real violation
    UNSAT -- the shape of svp_simple_001_001's first trap."""
    body = """\
volatile int v;
void t_main(void) { }
void t_isr_1(void) {
  v = 0;                             /* A1 */
  v = 1;                             /* A2 */
}
void t_isr_2(void) { int r = v;      /* B */ }
"""
    store = run_c(tmp_path, body, flows=("main", "isr_1", "isr_2"))
    r = verdict(store, line_of(body, "/* A1 */"), line_of(body, "/* B */"),
                line_of(body, "/* A2 */"))
    assert r["verdict"] == "sat"


def test_the_same_statement_in_a_loop_reaches_a_later_iteration(tmp_path):
    """A1 and A2 are one read in a loop: the interval runs across the back edge,
    which the search must cross -- once to reach the preemption and once more,
    after it, to reach A2 (Soundness Assumptions G2)."""
    body = """\
volatile int x;
void t_main(void) {
  int r;
  for (int k = 0; k < 2; k++)
    r = x;                           /* R */
}
void t_isr_1(void) { x = 1;          /* W */ }
"""
    store = run_c(tmp_path, body)
    r_line, w_line = line_of(body, "/* R */"), line_of(body, "/* W */")
    assert verdict(store, r_line, w_line, r_line)["verdict"] == "sat"


def test_the_back_edge_is_crossed_once_per_phase(tmp_path):
    """A1 at the end of an iteration, the only unmasked window in the middle of
    the next one, A2 at the start of the one after: the back edge must be
    crossed once to reach the preemption and once more to reach A2. Allowing
    one crossing in total refutes this real violation."""
    body = """\
volatile int x;
void t_main(void) {
  int r1, r2;
  disable_isr(1);
  for (int k = 0; k < 3; k++) {
    r2 = x;                          /* A2 */
    enable_isr(1);
    disable_isr(1);
    r1 = x;                          /* A1 */
  }
}
void t_isr_1(void) { x = 1;          /* W */ }
"""
    store = run_c(tmp_path, body)
    r = verdict(store, line_of(body, "/* A1 */"), line_of(body, "/* W */"),
                line_of(body, "/* A2 */"))
    assert r["verdict"] == "sat"


def test_loop_havoc_keeps_the_guard_inside_the_body(tmp_path):
    """svp_simple_001_001's second trap: the loop counter is havocked at the
    header, but `i == 9999` still holds at the store it guards, so a read of
    element 1000 cannot be the B of that triple -- and a read of 9999 can."""
    body = """\
volatile int a[10000];
void t_main(void) {
  for (int i = 0; i < 10000; i++) a[i] = 0;                /* A1 */
  for (int i = 0; i < 10000; i++) if (i == 9999) a[i] = 1; /* A2 */
}
void t_isr_1(void) {
  int r = a[1000];                   /* B1000 */
  int s = a[9999];                   /* B9999 */
}
"""
    store = run_c(tmp_path, body)
    a1, a2 = line_of(body, "/* A1 */"), line_of(body, "/* A2 */")
    assert verdict(store, a1, line_of(body, "/* B1000 */"), a2)["verdict"] == "unsat"
    assert verdict(store, a1, line_of(body, "/* B9999 */"), a2)["verdict"] == "sat"


def test_an_unreachable_guard_refutes(tmp_path):
    """svp_simple_002_001's first trap: `i == N + 1` inside `i < N`."""
    body = """\
volatile int x;
void t_main(void) {
  for (int i = 0; i < 10; i++)
    if (i == 11) x = 1;              /* W */
}
void t_isr_1(void) { int r = x;      /* R */ }
"""
    store = run_c(tmp_path, body)
    assert verdict(store, line_of(body, "/* W */"), line_of(body, "/* R */"))["verdict"] == "unsat"


def test_a_global_nobody_writes_keeps_its_initializer(tmp_path):
    """svp_simple_005_001's and 003's traps: a guard on a flag that is
    initialised and never written is decided by the initializer..."""
    body = """\
volatile int flag = 0;
volatile int x;
void t_main(void) { if (flag == 1) x = 1;   /* W */ }
void t_isr_1(void) { int r = x;              /* R */ }
"""
    store = run_c(tmp_path, body)
    assert verdict(store, line_of(body, "/* W */"), line_of(body, "/* R */"))["verdict"] == "unsat"


def test_a_flow_that_may_run_breaks_the_initializer(tmp_path):
    """... unless a flow that may run before the guard writes it (interference)."""
    body = """\
volatile int flag = 0;
volatile int x;
void t_main(void) { if (flag == 1) x = 1;   /* W */ }
void t_isr_1(void) { int r = x;              /* R */ }
void t_isr_2(void) { flag = 1; }
"""
    store = run_c(tmp_path, body, flows=("main", "isr_1", "isr_2"))
    assert verdict(store, line_of(body, "/* W */"), line_of(body, "/* R */"))["verdict"] == "sat"


def test_masking_shields_a_value_from_interference(tmp_path):
    """Interference comes from stage 2's run sets, so it respects masking: isr_1
    writes the flag, but it is masked between main's `flag = 0` and the guard,
    and isr_2 -- which may run there -- does not write it."""
    masked = """\
volatile int flag;
volatile int x;
void t_main(void) {
  disable_isr(1);
  flag = 0;
  if (flag == 1) x = 1;              /* W */
  enable_isr(1);
}
void t_isr_1(void) { flag = 1; }
void t_isr_2(void) { int r = x;      /* R */ }
"""
    store = run_c(tmp_path, masked, flows=("main", "isr_1", "isr_2"))
    assert verdict(store, line_of(masked, "/* W */"), line_of(masked, "/* R */"))["verdict"] == "unsat"
    unmasked = masked.replace("  disable_isr(1);\n", "")
    store = run_c(tmp_path / "u", unmasked, flows=("main", "isr_1", "isr_2"))
    assert verdict(store, line_of(unmasked, "/* W */"),
                   line_of(unmasked, "/* R */"))["verdict"] == "sat"


def test_dead_code_is_refuted_and_fixing_the_typo_flips_it(tmp_path):
    """A loop whose condition never changes never exits, so a read guarded by a
    value the loop never reaches is dead and its triple UNSAT; correct the
    condition and the same triple is SAT."""
    body = """\
volatile int v;
void t_main(void) {
  int r1, r2;
  for (int i = 0; i < 5; i++)
    for (int j = 0; i < 5; j++)
      if (i == j) {
        if (i == 0) r1 = v;          /* R0 */
        else if (i == 4) r2 = v;     /* R4 */
      }
}
void t_isr_1(void) { v = 0;          /* W */ }
"""
    spec = ("/* R0 */", "/* W */", "/* R4 */")
    store = run_c(tmp_path / "typo", body)
    assert verdict(store, *(line_of(body, m) for m in spec))["verdict"] == "unsat"
    fixed = body.replace("i < 5; j++", "j < 5; j++")
    store = run_c(tmp_path / "fixed", fixed)
    assert verdict(store, *(line_of(fixed, m) for m in spec))["verdict"] == "sat"


# -- what the solver may not do -------------------------------------------------


def test_recursion_is_inconclusive_never_a_drop(tmp_path):
    body = """\
volatile int x;
void f(int n) { if (n) f(n - 1); x = 1;   /* W */ }
void t_main(void) { f(3); }
void t_isr_1(void) { int r = x;           /* R */ }
"""
    store = run_c(tmp_path, body)
    r = verdict(store, line_of(body, "/* W */"), line_of(body, "/* R */"))
    assert r["verdict"] in ("inconclusive", "sat")
    if r["verdict"] == "inconclusive":
        assert r["reason"].startswith("unsupported-construct:recursion")
    assert store.check() == []


def test_a_timeout_is_inconclusive_and_the_candidate_reaches_the_llm(tmp_path):
    body = """\
volatile int x;
void t_main(void) { x = 1;            /* W */ }
void t_isr_1(void) { int r = x;       /* R */ }
"""
    store = run_c(tmp_path, body, timeout_ms=0)
    r = verdict(store, line_of(body, "/* W */"), line_of(body, "/* R */"))
    assert r["verdict"] == "inconclusive" and r["reason"] == "timeout"
    ctx = store.read_contexts()
    assert ctx and all(c["solver_result"]["verdict"] == "inconclusive" for c in ctx)
    assert store.check() == []


# -- Racebench ------------------------------------------------------------------

racebench = pytest.mark.skipif(not (SUITE / "README.md").exists(), reason="racebench not present")
CONFIGS = sorted(BENCH_CONFIGS.glob("*.yaml"))

@pytest.fixture(scope="module")
def ground_truth():
    return load_suite(SUITE, ERRATA)


def through_stage3(name, run_root):
    cfg = Config.load(BENCH_CONFIGS / f"{name}.yaml")
    store = RunStore.create(cfg, run_root=run_root)
    result = build(cfg, store.root / "build")
    stage1(cfg, store, result.bitcode)
    stage2(cfg, store)
    stage3(cfg, store, result.bitcode)
    return store


def by_lines(store, *lines):
    for c in store.read_candidates("stage2"):
        if [a["source"]["line"] for a in c["accesses"]] == list(lines):
            for row in (store.root / "solver" / "results.jsonl").read_text().splitlines():
                r = json.loads(row)
                if r["candidate_id"] == c["id"]:
                    return r["verdict"]
    return None


@racebench
@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_recall_gate_on_what_reaches_the_llm(path, tmp_path, ground_truth):
    """W6-W7 done-when: every annotated bug point reaches the LLM."""
    store = through_stage3(path.stem, tmp_path)
    rep = match_subject(ground_truth.by_case(path.stem).all, store.read_contexts(),
                        subject=path.stem)
    assert rep.bugs_detected == len(rep.bug_matches), [
        (a.kind, a.index, a.lines) for a in rep.missed]
    assert store.check() == []


@racebench
@pytest.mark.parametrize("name,lines,expected", [
    ("svp_simple_001_001", (32, 60, 35), "unsat"),  # index 1000 vs 9999
    ("svp_simple_001_001", (43, 64, 44), "sat"),    # reachable: W5 finding
    ("svp_simple_002_001", (35, 44, 37), "unsat"),  # i == N + 1 inside i < N
    ("svp_simple_002_001", (37, 44, 39), "unsat"),  # elements 9999 and 0
    ("svp_simple_008_001", (33, 52, 48), "unsat"),  # elements 3 and 4
    ("svp_simple_010_001", (43, 53, 44), "unsat"),  # struct fields at 0 and 4
    ("svp_simple_011_001", (34, 43, 36), "unsat"),  # *u moved from var2 to var3
    ("svp_simple_019_001", (40, 67, 42), "unsat"),  # para values only main writes
    ("svp_simple_020_001", (37, 44, 40), "sat"),    # reachable: W7 finding
    ("svp_simple_029_001", (80, 83, 80), "unsat"),  # elements 36 and 37
])
def test_racebench_verdicts(name, lines, expected, tmp_path):
    store = through_stage3(name, tmp_path)
    assert by_lines(store, *lines) == expected
