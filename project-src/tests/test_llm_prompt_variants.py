"""The T3 prompt variants: each is ``+racebench`` with exactly one change.

``wiki/Lucas Tasks.md`` (T3) compares prompts by how each one changes the
result. A difference between two rows has one cause only if the rows differ in
one asset or one flag, and only if the baselines they are compared against are
still the prompts that were measured. Both are checked here.
"""

from irqrace.llm.prompts import EXPERIMENTAL

#: The two baselines' identities at commit 2063144, the state that T3's first
#: comparison measures. A change here means a baseline prompt changed -- an
#: edited asset, a reordered row -- and every number reported under the old
#: hash then belongs to another prompt. Update only together with a new run.
BASELINE_HASHES = {
    "+racebench": "acd08354c0bc7f0d",
    "+racebench+c4": "90a18ccc93f98b59",
}


def test_the_baselines_are_the_measured_prompts():
    for name, expected in BASELINE_HASHES.items():
        assert EXPERIMENTAL[name].hash() == expected, name
