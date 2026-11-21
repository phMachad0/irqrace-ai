# The scan with `gpt-oss-120b` on Groq's free tier (2026-11-21) — partial, not for the monograph

Pedro's direction: a free, non-Anthropic model on the same comparisons; recorded as is, kept out
of the monograph for now. Backend `openai:openai/gpt-oss-120b` with `IRQRACE_OPENAI_BASE_URL`
pointing at Groq (from `project-src/.env`, not in git). Same prompt, scorer and disguised copy
(copy B, `racebench-disguise.py --seed 2026 --compilable`) as the Sonnet runs in
`disguised-pipeline-20261121`. `--max-tokens 4000` (Groq counts requested output against the
per-minute limit), one call at a time.

## Limits met

Response headers on 2026-11-21: 1,000 requests and **8,000 tokens per minute**. The daily token
limit is not in the headers; the run stopped being served at **200,616 tokens** for the day, which
matches a 200,000-token daily cap.

- **The scan per file fits**: about 2–3 k tokens per call, ten minutes per run of 31 calls.
- **The one-prompt scan cannot run**: about 15 k tokens of input in one request.
- **irqrace cannot run**: in this tokenizer (about 3.15 characters per token, calibrated on one
  call), 164 of 166 per-candidate feasibility prompts and all 44 checklist prompts exceed 8,000
  tokens of input (median 8.8 k and 12.2 k; the largest checklist 52.6 k), and a whole run needs
  1.4–2.7 M tokens, against 200 k a day. It needs a paid tier or another provider.

## What ran

| Run | Outcome |
| --- | --- |
| per file 1 | complete; `program_22` failed Groq's JSON validation (`json_validate_failed`, empty generation) and counts as no findings |
| per file 2 | complete |
| per file 3 | **stopped at 19/31** on the daily cap (`scan-disguised-per-file-3-daily-limit/`, two cases rate-limited); not scored, to be re-run whole |
| one prompt 1 | started after the cap, stopped (`scan-disguised-one-prompt-1-daily-limit/`); could not run on this tier anyway |

## Results (disguised copy B, per file)

| | `gpt-oss-120b`, run 1 | `gpt-oss-120b`, run 2 | Sonnet low, n = 3 (`disguised-pipeline-20261121`) |
| --- | --- | --- | --- |
| Bug points found (53/33) | 28 | 34 | 48–52 |
| Traps reported | 5 | 10 | 6–10 |
| NASAC score /106 | 41 | 38 | 70–86 |
| Bug points (48/38) | 27/48 | 32/48 | 44–48 |
| Findings matching no annotation | 39 | 32 | 21–30 |
| Input / output tokens | 28.8 k / 55.8 k | 29.9 k / 60.7 k | 75–79 k / 26–28 k |
| Wall time | 578 s | 601 s | 68–75 s |

Token counts are in each model's own tokenizer and do not compare directly. Output exceeds
input about twofold: most of it is the model's reasoning (Groq reports `reasoning_tokens`).

`gpt-oss-120b` finds a bit over half of the bug points with this prompt, against nearly all for
Sonnet at low effort.
