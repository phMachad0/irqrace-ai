import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from irqrace.racebench import locate_suite  # noqa: E402

EXAMPLES = REPO / "contracts" / "examples"
BENCH_CONFIGS = REPO / "bench" / "configs"
ERRATA = REPO / "bench" / "racebench-errata.yaml"
#: The vendored suite (bench/racebench), or IRQRACE_RACEBENCH when set.
SUITE = locate_suite() or Path("bench/racebench/2.1_remarks")
