| prompt configuration | openai:openai/gpt-oss-120b recall | trap rej. | insp. ratio |
| --- | --- | --- | --- |
| `simple` | 100.0% | 80.0% | 65.0% |
| `+domain` | 100.0% | 80.0% | 75.0% |

**openai:openai/gpt-oss-120b**
- no prompt caching - cost is not comparable with a cached backend
- cost: unpriced backend; tokens only
- bug points bucketed `likely_benign` (passes the gate, sinks the Inspection Ratio): {'simple': ['cb612ba9bbc8a08a2', 'c6756411eeb134a3c', 'c8972847f02fab758'], '+domain': ['c1a015d2f1d307ead', 'cb612ba9bbc8a08a2', 'c6756411eeb134a3c', 'c8972847f02fab758']}
- protocol violations: {'simple': 5, '+domain': 9}

