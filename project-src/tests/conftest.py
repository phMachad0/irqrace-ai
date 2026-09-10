import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

EXAMPLES = REPO / "contracts" / "examples"
BENCH_CONFIGS = REPO / "bench" / "configs"
SUITE = Path("/home/pedro/Documentos/tcc/racebench/2.1_remarks")
