| prompt configuration | openai:openai/gpt-oss-120b recall | trap rej. | insp. ratio |
| --- | --- | --- | --- |
| `simple` | 100.0% | 70.0% | 65.0% |
| `+domain` | 100.0% | 50.0% | 75.0% |

**openai:openai/gpt-oss-120b**
- no prompt caching - cost is not comparable with a cached backend
- cost: unpriced backend; tokens only
- harmfulness asked and reported, **not scored**: Racebench annotates program facts, so a feasible candidate counts as found
- bug points reported `likely_benign`: {'simple': ['cb612ba9bbc8a08a2', 'c6756411eeb134a3c', 'c8972847f02fab758'], '+domain': ['c1a015d2f1d307ead', 'cb612ba9bbc8a08a2', 'c6756411eeb134a3c', 'c8972847f02fab758']}
- protocol violations: {'simple': 5, '+domain': 9}

