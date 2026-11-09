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


import pytest  # noqa: E402


@pytest.fixture(scope="session")
def tk_root():
    """One Tk root for the whole session: a second ``tk.Tk()`` after the first is
    destroyed corrupts the Tcl/Tk DLL state on Windows."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass
