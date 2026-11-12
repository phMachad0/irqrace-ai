# SYNTHETIC data — not a measurement

Every number in this directory is **invented**. It exists only so that
`tests/test_thesis_figures.py` can run `scripts/thesis-figures.py` end to end and
check that each figure F1–F11 is produced.

- Case names are `synthetic_case_NNN_001`, run ids start with `SYNTHETIC-`, the
  published tools are `ToolA-sintetico`, `ToolB-sintetico`, `ToolC-sintetico`,
  and the manifest says `"commit": "SYNTHETIC"`.
- The counts (8 cases, 16 bug points, 10 traps) are not Racebench's. The label-set
  keys (`53/33`, `48/38`, `2.2`) are reused only because the script names its
  axes from them.
- **Nothing rendered from these files may go into `monografia/figuras/`** or into
  the thesis. Render them into a scratch directory.

Regenerate with `python tests/fixtures/thesis-figures/make_synthetic.py`
(seeded, so the output is stable). The file formats are documented in the
docstring of `scripts/thesis-figures.py`; `cases.csv` is deliberately absent, so
the test also covers F9's fallback.
