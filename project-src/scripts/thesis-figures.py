#!/usr/bin/env python3
"""Generate the monograph's evaluation figures F1-F11 from versioned CSVs.

    python scripts/thesis-figures.py --data results/thesis
    python scripts/thesis-figures.py --data results/thesis --only F1,F5 --png

Every figure in the results section of the monograph comes out of this script,
never out of a hand-drawn file, so the thesis cannot hold a number the CSVs do
not. Rerunning it regenerates every figure. Requires the ``figures`` extra
(``pip install -e .[figures]``, i.e. matplotlib).

Output: one vector PDF per figure (``F1-recall-armadilhas.pdf`` ...) in
``--out`` (default ``<repo>/monografia/figuras/``), plus ``thesis-figures.json``
recording, for each figure, the inputs, run ids, label set, prompt row and
number of runs it used -- what the figure's ``\\fonte{}`` should name. ``--png``
also writes a PNG preview of each figure and ``--grey`` a greyscale preview, to
check legibility on a black-and-white print.

A figure whose inputs are missing is **skipped with a message**, not faked;
the other figures are still produced, and the exit code is 0 unless a figure
fails with an error.

Input files (in ``--data``)
===========================

The six files below are produced by the measurement scripts (T1-T3); their
columns are fixed. Empty cells are read as missing.

``runs.csv`` -- one row per (run, label set, case subset, view):
    run_id, system (S1|S2), prompt_row, sample, labels, case_subset, view,
    bug_points_total, bug_points_detected, traps_total, traps_reported,
    unannotated_reported, uncertain, score, score_max, recall, precision,
    inspection_ratio_mean, llm_calls, tokens_in, tokens_out, backend_failures,
    wall_s, static_s, llm_s
``patterns.csv``:
    run_id, labels, case_subset, view, pattern, bug_points_total,
    bug_points_detected
``items.csv`` -- one row per labelled item or candidate, per run:
    run_id, prompt_row, sample, case, item_kind (bug|trap|unannotated),
    item_id, triple, pattern, fate (stage1_absent|stage2|solver|llm),
    feasibility, bucket, confidence
``agreement.csv``:
    prompt_row, run_a, run_b, field, n_shared, agreement, kappa
``published.csv`` -- S0, one row per published number:
    tool, reported_by, cases, ground_truth, defect_class, metric, value,
    rerun_or_copied, hardware, source
``manifest.json`` -- the run manifest; copied by reference into
    ``thesis-figures.json`` (its ``commit``/``model`` keys, when present).

Value conventions this script relies on:

- ``labels``: ``53/33`` (2.1 relabelled, the headline), ``48/38`` (2.1 as
  distributed), ``2.2`` (the extended ground truth). Other strings are shown
  verbatim.
- ``view`` (the reading of "reported"): ``likely_real`` (headline),
  ``not_infeasible``, ``static_only`` (= S1). S1 rows may carry any view.
- ``recall``, ``precision``, ``inspection_ratio_mean``: fractions in [0, 1].
- ``bucket``: ``likely_real``, ``uncertain``, ``likely_benign``,
  ``likely_infeasible`` (empty when ``fate`` is not ``llm``).
- ``pattern``: ``RWR``, ``WWR``, ``WRW``, ``RWW`` (``(R,W,R)`` also accepted).
- ``published.csv`` ``metric``: ``recall`` (or ``hit_rate``) and
  ``traps_reported`` (or ``fp``, ``false_positives``) for F1;
  ``recall_RWR`` ... ``recall_RWW`` for F4. A recall above 1 is read as a
  percentage.
- ``items.csv`` is scored under ``--labels``: the item kinds of a run are
  those of the label set the figures are drawn for.

Optional extra inputs, defined here
-----------------------------------

``labels22.csv`` -- the Racebench 2.2 adjudication (T2), one row per
adjudicated unannotated candidate, read by F10 and F11:
    case        -- the case, as in ``items.csv``
    item_id     -- the candidate's ``item_id`` in ``items.csv`` (unannotated)
    verdict     -- ``bug`` | ``trap`` | ``not_defect`` | ``undecided``
    group       -- the equivalence class under the written equivalence rule:
                   rows sharing a ``group`` are one distinct defect. Empty
                   means a class of its own.

``cases.csv`` -- per-case Inspection Ratio, read by F9 when present:
    run_id, case, ir_static, ir_triage
  Without it, F9 computes both from ``items.csv``: the triage order is the
  scorer's (bucket, then confidence descending, bug points last among ties),
  and the static order is **the row order of items.csv within each case**,
  which is then assumed to be the record order. The script prints a warning
  when it falls back.

Figures
=======

F1  recall x traps reported, S0/S1/S2, marker = ground truth scored on
F2  candidate funnel by stage, stacked bug points / traps / unannotated
F3  trap disposition: the stage that removed each trap, per run
F4  recall per pattern, grouped bars per system
F5  NASAC score per system under each label set, min-max over runs
F6  prompt forest plot: score, traps reported, IR, with the baseline band
F7  flip heatmap: labelled items x (prompt, run), coloured by bucket
F8  cost x score per prompt (LLM calls; tokens)
F9  Inspection Ratio per case, S1 vs S2, paired
F10 Racebench 2.2 composition per case
F11 where the triage put the bugs nobody had labelled

Style: labels in Portuguese, Latin Modern (the thesis font) when MiKTeX/TeX Live
provides it, a fixed colour per system in every figure (S0 neutral grey with
hatching, S1 dark blue, S2 orange: separated under colour-vision deficiency and
in greyscale), no pie or 3D charts, min-max error bars wherever there is more
than one run, and the label set written on the axis.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO.parent / "monografia" / "figuras"
DEFAULT_DATA = REPO / "results" / "thesis"

# --- vocabulary ---------------------------------------------------------------

LABEL_NAMES = {
    "53/33": "Racebench 2.1 reetiquetado (53/33)",
    "48/38": "Racebench 2.1 conforme distribuído (48/38)",
    "2.2": "Racebench 2.2, gabarito estendido",
}
LABEL_ORDER = ["48/38", "53/33", "2.2"]
SHORT_LABEL = {"48/38": "2.1 conforme distribuído\n(48/38)", "53/33": "2.1 reetiquetado\n(53/33)",
               "2.2": "2.2, gabarito\nestendido"}

SYSTEM_NAMES = {
    "S0": "S0, resultados publicados",
    "S1": "S1, etapa estática",
    "S2": "S2, estática + triagem",
}
# One colour per system, in every figure. Validated for colour-vision
# deficiency (blue/orange) and separated in greyscale (luma ~70 / ~137 / ~200).
# S0 is neutral on purpose -- it is the reference, not a competitor drawn by us
# -- and always carries hatching as its second channel.
COLOR = {"S0": "#c8c8c8", "S1": "#184f95", "S2": "#eb6834"}
EDGE = {"S0": "#4d4d4d", "S1": "#184f95", "S2": "#b4471c"}
HATCH = {"S0": "///", "S1": None, "S2": None}
INK = "#1f1f1f"
MUTED = "#5c5c5c"
GRID = "#e3e3e3"

PATTERNS = ["RWR", "WWR", "WRW", "RWW"]
BUCKETS = ["likely_real", "uncertain", "likely_benign", "likely_infeasible"]
BUCKET_NAMES = {
    "likely_real": "provavelmente real",
    "uncertain": "incerto",
    "likely_benign": "provavelmente benigno",
    "likely_infeasible": "provavelmente inviável",
}
BUCKET_LETTER = {"likely_real": "R", "uncertain": "U", "likely_benign": "B",
                 "likely_infeasible": "I", "static": "–"}
# Diverging around the neutral "uncertain": blue = kept high, orange = pushed
# down. Every cell also carries its letter, so the encoding survives greyscale.
BUCKET_COLOR = {"likely_real": "#1c5cab", "uncertain": "#d4d4d4",
                "likely_benign": "#f4b393", "likely_infeasible": "#b5401a",
                "static": "#f2f2f2"}

FATES = ["stage1_absent", "stage2", "solver", "llm_low", "reported"]
FATE_NAMES = {
    "stage1_absent": "não gerada (estágio 1)",
    "stage2": "descartada no estágio 2",
    "solver": "refutada pelo Z3",
    "llm_low": "rebaixada pela triagem",
    "reported": "reportada",
}
# An ordinal ramp along the pipeline for the rejections (light = earliest),
# and the S2 orange, hatched, for the one outcome that costs points.
FATE_COLOR = {"stage1_absent": "#cde2fb", "stage2": "#86b6ef",
              "solver": "#3987e5", "llm_low": "#184f95", "reported": "#eb6834"}
FATE_HATCH = {"reported": "xx"}

VIEW_BUCKETS = {
    "likely_real": {"likely_real"},
    "not_infeasible": {"likely_real", "uncertain", "likely_benign"},
    "static_only": set(BUCKETS),
}
VIEW_NAMES = {
    "likely_real": "reportado = grupo provavelmente real",
    "not_infeasible": "reportado = não julgado inviável",
    "static_only": "reportado = tudo o que chega à triagem",
}

V22 = ["bug", "trap", "not_defect", "undecided"]

FIGURE_FILES = {
    "F1": "F1-recall-armadilhas", "F2": "F2-funil", "F3": "F3-disposicao-armadilhas",
    "F4": "F4-recall-por-padrao", "F5": "F5-pontuacao", "F6": "F6-prompts-floresta",
    "F7": "F7-mudancas-de-grupo", "F8": "F8-custo-pontuacao", "F9": "F9-inspection-ratio",
    "F10": "F10-composicao-2-2", "F11": "F11-novos-defeitos-por-grupo",
}

WIDTH = 6.3  # inches: the thesis text block is 16 cm wide


class Skip(Exception):
    """The figure's inputs are missing; say which, and move on."""


# --- small helpers ------------------------------------------------------------

def br(x: float, nd: int = 1) -> str:
    """A number in Brazilian notation (decimal comma)."""
    return f"{x:.{nd}f}".replace(".", ",")


def num(v):
    if v is None:
        return None
    v = str(v).strip()
    if v == "" or v.upper() in {"NA", "NAN", "NONE", "-"}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def norm_pattern(p: str) -> str:
    return re.sub(r"[^RW]", "", (p or "").upper())


def norm_labels(v: str) -> str:
    return re.sub(r"\s+", "", v or "")


def label_name(v: str) -> str:
    return LABEL_NAMES.get(norm_labels(v), f"rótulos {v}")


def case_short(case: str) -> str:
    m = re.search(r"(\d{3})(?:_\d{3})?$", case or "")
    return m.group(1) if m else (case or "?")


def spread(values: list[float]) -> tuple[float, float, float]:
    """(mean, min, max). The thesis reports min-max, not a confidence interval:
    with n = 3 the spread is all the data supports."""
    return statistics.mean(values), min(values), max(values)


def load_csv(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k}
                for row in csv.DictReader(fh)]


class Data:
    def __init__(self, root: Path):
        self.root = root
        self.runs = load_csv(root / "runs.csv")
        self.patterns = load_csv(root / "patterns.csv")
        self.items = load_csv(root / "items.csv")
        self.agreement = load_csv(root / "agreement.csv")
        self.published = load_csv(root / "published.csv")
        self.labels22 = load_csv(root / "labels22.csv")
        self.cases = load_csv(root / "cases.csv")
        mpath = root / "manifest.json"
        self.manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else None

    def need(self, *names: str) -> None:
        missing = [n for n in names if getattr(self, n.split(".")[0]) is None]
        if missing:
            raise Skip("falta " + ", ".join(f"{m}.csv" for m in missing))


# --- style ----------------------------------------------------------------------

def setup_style():
    import logging
    import matplotlib
    matplotlib.use("Agg")
    # fontTools complains about the Latin Modern OTFs' zero timestamps on embed.
    logging.getLogger("fontTools").setLevel(logging.ERROR)
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    family = None
    kpse = shutil.which("kpsewhich")
    if kpse:
        names = ["lmroman10-regular.otf", "lmroman10-bold.otf",
                 "lmroman10-italic.otf", "lmroman10-bolditalic.otf"]
        try:
            out = subprocess.run([kpse, *names], capture_output=True, text=True,
                                 timeout=20).stdout.split()
        except (OSError, subprocess.SubprocessError):
            out = []
        for path in out:
            if Path(path).exists():
                font_manager.fontManager.addfont(path)
                family = "Latin Modern Roman"
    if family is None:
        available = {f.name for f in font_manager.fontManager.ttflist}
        for cand in ("Latin Modern Roman", "CMU Serif", "STIXGeneral", "DejaVu Serif"):
            if cand in available:
                family = cand
                break
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": [family or "DejaVu Serif", "STIXGeneral", "DejaVu Serif"],
        "mathtext.fontset": "cm" if family == "Latin Modern Roman" else "stix",
        "font.size": 9.5,
        "axes.titlesize": 10,
        "axes.labelsize": 9.5,
        "legend.fontsize": 8.5,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.5,
        "grid.linestyle": "-",
        "axes.axisbelow": True,
        "legend.frameon": False,
        "hatch.linewidth": 0.6,
        "hatch.color": EDGE["S0"],
        "pdf.fonttype": 42,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.04,
        "axes.unicode_minus": False,
    })
    return plt, family


def pct_formatter(nd: int = 0):
    from matplotlib.ticker import FuncFormatter
    return FuncFormatter(lambda v, _: br(v * 100, nd) + "%")


def br_formatter(nd: int | None = None):
    """Decimal-comma ticks; by default integers bare and fractions with one
    decimal, so 22.5 never prints as a second "22"."""
    from matplotlib.ticker import FuncFormatter
    if nd is None:
        return FuncFormatter(lambda v, _: br(v, 0) if abs(v - round(v)) < 1e-9 else br(v, 1))
    return FuncFormatter(lambda v, _: br(v, nd))


def note(fig, text: str):
    """A small note under the plot: what the bars mean, n, the reading. Placed
    by :func:`place_note` once everything else is drawn, so it never overlaps a
    legend set below the axes."""
    fig._thesis_note = text


def place_note(fig) -> None:
    import textwrap
    text = getattr(fig, "_thesis_note", None)
    if not text:
        return
    renderer = fig.canvas.get_renderer()
    bbox = fig.get_tightbbox(renderer)  # inches
    w, h = fig.get_size_inches()
    chars = int(min(w, bbox.width) * 72 / 3.5)  # ~3.5 pt per character at 7.5 pt
    y = (bbox.y0 - 0.06) / h
    fig.text(bbox.x0 / w, y, textwrap.fill(text, chars), ha="left", va="top",
             fontsize=7.5, color=MUTED, transform=fig.transFigure, linespacing=1.25)


def subset_name(subset: str) -> str:
    return "todos os casos simples" if subset == "all" else f"subconjunto {subset}"


# --- selection ------------------------------------------------------------------

class Ctx:
    def __init__(self, data: Data, args):
        self.d = data
        self.labels = norm_labels(args.labels)
        self.subset = args.subset
        self.view = args.view
        self.baseline = args.baseline_prompt
        self._s2 = args.s2_prompt

    @property
    def s2_prompt(self) -> str:
        if self._s2:
            return self._s2
        if not self.d.runs:
            raise Skip("falta runs.csv")
        counts = Counter(r["prompt_row"] for r in self.d.runs if r.get("system") == "S2")
        if not counts:
            raise Skip("runs.csv sem linhas de S2")
        best = max(sorted(counts), key=lambda k: counts[k])
        self._s2 = best
        print(f"  (S2 = linha de prompt {best!r}; use --s2-prompt para outra)")
        return best

    def runs(self, system: str, labels: str | None = None, prompt: str | None = None,
             view: str | None = None, subset: str | None = None) -> list[dict]:
        labels = norm_labels(labels or self.labels)
        subset = subset or self.subset
        out, seen = [], set()
        for r in self.d.runs or []:
            if r.get("system") != system or norm_labels(r.get("labels")) != labels:
                continue
            if r.get("case_subset") != subset:
                continue
            if system == "S2" and r.get("view") != (view or self.view):
                continue
            # S1 comes out of S2's runs (its "everything reaching the LLM"
            # reading), so it is taken from the same prompt row's runs when the
            # row names one; a standalone S1 row (no prompt) is always kept.
            if prompt is not None and r.get("prompt_row") and r.get("prompt_row") != prompt:
                continue
            if r["run_id"] in seen:  # S1 may carry several views; one is enough
                continue
            seen.add(r["run_id"])
            out.append(r)
        return out

    def items_for(self, run_ids: set[str]) -> list[dict]:
        return [i for i in self.d.items or [] if i["run_id"] in run_ids]

    def describe(self) -> dict:
        return {"labels": self.labels, "case_subset": self.subset, "view": self.view}


def stat(rows: list[dict], key: str, scale: float = 1.0):
    vals = [num(r.get(key)) for r in rows]
    vals = [v * scale for v in vals if v is not None]
    return spread(vals) if vals else None


def errbar(s):
    """Asymmetric error for matplotlib from (mean, lo, hi)."""
    return [[s[0] - s[1]], [s[2] - s[0]]]


# --- F1 -------------------------------------------------------------------------

def published_points(ctx: Ctx) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for r in ctx.d.published or []:
        key = (r["tool"], r["reported_by"], r["cases"], r["ground_truth"])
        g = groups.setdefault(key, {"tool": r["tool"], "reported_by": r["reported_by"],
                                    "cases": r["cases"], "ground_truth": r["ground_truth"],
                                    "copied": r.get("rerun_or_copied", "")})
        metric, val = r["metric"].strip().lower(), num(r["value"])
        if val is None:
            continue
        if metric in {"recall", "hit_rate"}:
            g["recall"] = val / 100 if val > 1 else val
        elif metric in {"traps_reported", "fp", "false_positives"}:
            g["fp"] = val
    return list(groups.values())


def fig_f1(plt, ctx: Ctx):
    ctx.d.need("runs", "published")
    pts = [p for p in published_points(ctx) if "recall" in p and "fp" in p]
    for p in published_points(ctx):
        if "recall" not in p or "fp" not in p:
            print(f"  F1: {p['tool']} ({p['reported_by']}) sem recall e armadilhas; omitido")
    ours = []
    for lab in LABEL_ORDER + sorted({norm_labels(r["labels"]) for r in ctx.d.runs} - set(LABEL_ORDER)):
        if lab == "2.2":
            continue  # no published tool has a 2.2 score; F5 carries it
        s1 = ctx.runs("S1", labels=lab, prompt=ctx.s2_prompt)
        s2 = ctx.runs("S2", labels=lab, prompt=ctx.s2_prompt)
        for sysname, rows in (("S1", s1), ("S2", s2)):
            if rows:
                ours.append((sysname, lab, stat(rows, "traps_reported"), stat(rows, "recall"), len(rows)))
    if not ours and not pts:
        raise Skip("nenhum ponto com recall e armadilhas")

    gts = []
    for p in pts:
        gts.append(p["ground_truth"])
    gts += [lab for _, lab, *_ in ours]
    markers = ["o", "s", "^", "D", "v", "P", "X", "h"]
    marker_of = {}
    for g in gts:
        if g not in marker_of:
            marker_of[g] = markers[len(marker_of) % len(markers)]

    fig, ax = plt.subplots(figsize=(WIDTH, 3.6))
    for p in pts:
        ax.scatter(p["fp"], p["recall"], s=52, marker=marker_of[p["ground_truth"]],
                   facecolor=COLOR["S0"], edgecolor=EDGE["S0"], hatch=HATCH["S0"],
                   linewidth=0.8, zorder=3)
        who = p["tool"] if p["reported_by"] in ("", p["tool"]) else f"{p['tool']} (seg. {p['reported_by']})"
        tag = f"{who}\n{p['cases']} casos" + (", copiado" if "cop" in p["copied"].lower() else "")
        ax.annotate(tag, (p["fp"], p["recall"]), xytext=(6, -2), textcoords="offset points",
                    fontsize=7, color=MUTED, va="top")
    for sysname, lab, sx, sy, n in ours:
        ax.errorbar(sx[0], sy[0], xerr=errbar(sx) if n > 1 else None,
                    yerr=errbar(sy) if n > 1 else None, fmt="none",
                    ecolor=EDGE[sysname], elinewidth=0.8, capsize=2.5, zorder=3)
        ax.scatter(sx[0], sy[0], s=58, marker=marker_of[lab], facecolor=COLOR[sysname],
                   edgecolor="white", linewidth=1.2, zorder=4)
    ax.set_xlabel("armadilhas reportadas (falsos positivos relatados, no caso de S0)")
    ax.set_ylabel("recall")
    ax.yaxis.set_major_formatter(pct_formatter())
    ax.xaxis.set_major_formatter(br_formatter())
    ax.set_ylim(min([0.0] + [p["recall"] for p in pts]) - 0.02, 1.06)
    ax.set_xlim(left=-0.8)

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    sys_handles = [Patch(facecolor=COLOR[s], edgecolor=EDGE[s], hatch=HATCH[s], label=SYSTEM_NAMES[s])
                   for s in ("S0", "S1", "S2")]
    gt_handles = [Line2D([], [], linestyle="", marker=m, markersize=6.5, markerfacecolor="white",
                         markeredgecolor=INK, label=(label_name(g) if g in LABEL_NAMES else f"gabarito do artigo: {g}"))
                  for g, m in marker_of.items()]
    leg1 = ax.legend(handles=sys_handles, loc="lower right", title="sistema (cor)", title_fontsize=8)
    ax.add_artist(leg1)
    ax.legend(handles=gt_handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2,
              title="gabarito em que o ponto foi medido (marcador)", title_fontsize=8)
    reps = sorted({n for *_, n in ours})
    note(fig, f"S1, S2: {subset_name(ctx.subset)}, {VIEW_NAMES[ctx.view]} para S2 (linha {ctx.s2_prompt}); "
              f"barras: mínimo e máximo de n = {', '.join(map(str, reps)) or '–'} execuções. "
              "S0: números dos artigos, cada um no próprio subconjunto e gabarito.")
    return fig, {"run_ids": sorted({r['run_id'] for lab in LABEL_ORDER for s in ('S1', 'S2')
                                    for r in ctx.runs(s, labels=lab, prompt=ctx.s2_prompt)}),
                 "published_rows": len(ctx.d.published)}


# --- F2 -------------------------------------------------------------------------

def fig_f2(plt, ctx: Ctx):
    ctx.d.need("runs", "items")
    s2 = ctx.runs("S2", prompt=ctx.s2_prompt)
    if not s2:
        raise Skip(f"nenhuma execução S2 com rótulos {ctx.labels}, linha {ctx.s2_prompt}")
    run_ids = [r["run_id"] for r in s2]
    by_run = defaultdict(list)
    for it in ctx.items_for(set(run_ids)):
        by_run[it["run_id"]].append(it)
    if not by_run:
        raise Skip("items.csv sem itens dessas execuções")
    first = by_run[run_ids[0]] if run_ids[0] in by_run else next(iter(by_run.values()))
    kinds = ["bug", "trap", "unannotated"]
    kind_names = {"bug": "pontos de defeito", "trap": "armadilhas", "unannotated": "candidatos não anotados"}
    kind_color = {"bug": COLOR["S1"], "trap": "#e0e0e0", "unannotated": "#86b6ef"}
    kind_hatch = {"bug": None, "trap": "xx", "unannotated": None}
    stages = [("Estágio 1\n(candidatos)", lambda i: i["fate"] != "stage1_absent"),
              ("Estágio 2\n(prioridade e\nmascaramento)", lambda i: i["fate"] in ("solver", "llm")),
              ("Estágio 3\n(Z3: chega à triagem)", lambda i: i["fate"] == "llm")]
    counts = [[sum(1 for i in first if i["item_kind"] == k and f(i)) for k in kinds] for _, f in stages]
    total_bugs = sum(1 for i in first if i["item_kind"] == "bug")

    reported = VIEW_BUCKETS[ctx.view]
    per_run = []
    for rid in run_ids:
        its = by_run.get(rid, [])
        per_run.append([sum(1 for i in its if i["item_kind"] == k and i["fate"] == "llm"
                            and i.get("bucket") in reported) for k in kinds])
    s2_mean = [statistics.mean(c[j] for c in per_run) for j in range(3)]
    s2_tot = [sum(c) for c in per_run]

    labels = [s[0] for s in stages] + [f"Triagem\n({BUCKET_NAMES['likely_real'] if ctx.view == 'likely_real' else ctx.view})"]
    data = counts + [s2_mean]
    fig, ax = plt.subplots(figsize=(WIDTH, 3.4))
    x = range(len(labels))
    bottom = [0.0] * len(labels)
    for j, k in enumerate(kinds):
        vals = [row[j] for row in data]
        ax.bar(x, vals, bottom=bottom, width=0.58, color=kind_color[k], hatch=kind_hatch[k],
               edgecolor="white", linewidth=1.0, label=kind_names[k])
        bottom = [b + v for b, v in zip(bottom, vals)]
    if len(s2_tot) > 1 and max(s2_tot) > min(s2_tot):
        m, lo, hi = spread(s2_tot)
        ax.errorbar(len(labels) - 1, bottom[-1], yerr=[[m - lo], [hi - m]], fmt="none",
                    ecolor=INK, elinewidth=0.8, capsize=3)
    for xi, row in enumerate(data):
        bugs = row[0]
        txt = f"{br(bugs, 0) if xi < 3 else br(bugs, 1)}/{total_bugs} defeitos\n{br(row[1], 0) if xi < 3 else br(row[1], 1)} armadilhas"
        ax.text(xi, bottom[xi] + max(bottom) * 0.02, txt, ha="center", va="bottom", fontsize=7.5, color=INK)
    ax.set_xticks(list(x), labels)
    ax.set_ylabel(f"itens\n({label_name(ctx.labels)})")
    ax.set_ylim(0, max(bottom) * 1.22)
    ax.yaxis.set_major_formatter(br_formatter())
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", ncol=1)
    note(fig, f"Estágios 1 a 3: execução estática congelada (determinística). Triagem: média de "
              f"n = {len(run_ids)} execuções da linha {ctx.s2_prompt}"
              + ("; barra: mínimo e máximo do total." if len(run_ids) > 1 else "."))
    return fig, {"run_ids": run_ids}


# --- F3 -------------------------------------------------------------------------

def trap_fate(item: dict, reported: set) -> str:
    f = item["fate"]
    if f == "llm":
        return "reported" if item.get("bucket") in reported else "llm_low"
    return f if f in FATES else "stage1_absent"


def fig_f3(plt, ctx: Ctx):
    ctx.d.need("runs", "items")
    s2 = ctx.runs("S2", prompt=ctx.s2_prompt)
    run_ids = [r["run_id"] for r in s2]
    traps = defaultdict(dict)
    for it in ctx.items_for(set(run_ids)):
        if it["item_kind"] == "trap":
            traps[(it["case"], it["item_id"])][it["run_id"]] = it
    if not traps:
        raise Skip("nenhuma armadilha nas execuções S2 escolhidas")
    reported = VIEW_BUCKETS[ctx.view]
    order = {f: k for k, f in enumerate(FATES)}
    rows = []
    for key, per in traps.items():
        fates = [trap_fate(per[r], reported) if r in per else None for r in run_ids]
        worst = max(order[f] for f in fates if f)
        rows.append((key, fates, worst))
    rows.sort(key=lambda r: (r[2], r[0][0], r[0][1]))
    n = len(run_ids)
    fig, ax = plt.subplots(figsize=(WIDTH, 0.9 + 0.17 * len(rows)))
    for y, (key, fates, _) in enumerate(rows):
        for k, f in enumerate(fates):
            if f is None:
                continue
            ax.barh(y, 1.0 / n, left=k / n, height=0.72, color=FATE_COLOR[f], hatch=FATE_HATCH.get(f),
                    edgecolor="white", linewidth=1.0)
    ax.set_yticks(range(len(rows)), [f"{case_short(k[0])} · {k[1]}" for k, _, _ in rows], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xticks([(k + 0.5) / n for k in range(n)], [f"execução {k + 1}" for k in range(n)])
    ax.xaxis.tick_top()
    ax.grid(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(length=0)
    ax.set_ylabel(f"armadilhas\n({label_name(ctx.labels)})")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=FATE_COLOR[f], hatch=FATE_HATCH.get(f), edgecolor="white", label=FATE_NAMES[f])
                       for f in FATES], loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=3, fontsize=7.5)
    counts = Counter(f for _, fates, _ in rows for f in fates if f)
    note(fig, f"Uma linha por armadilha, uma faixa por execução (linha {ctx.s2_prompt}, n = {n}); "
              f"{VIEW_NAMES[ctx.view]}. Totais por execução: "
              + "; ".join(f"{FATE_NAMES[f]} {br(counts[f] / n, 1)}" for f in FATES) + ".")
    return fig, {"run_ids": run_ids, "traps": len(rows)}


# --- F4 -------------------------------------------------------------------------

def fig_f4(plt, ctx: Ctx):
    ctx.d.need("runs", "patterns")
    systems_of, prompt_of = defaultdict(set), {}
    for r in ctx.d.runs:
        systems_of[r["run_id"]].add(r["system"])
        prompt_of[r["run_id"]] = r.get("prompt_row", "")
    s2_prompt = ctx.s2_prompt
    vals = {"S1": defaultdict(list), "S2": defaultdict(list)}
    for p in ctx.d.patterns:
        rid = p["run_id"]
        if rid not in systems_of or norm_labels(p["labels"]) != ctx.labels or p["case_subset"] != ctx.subset:
            continue
        if prompt_of[rid] and prompt_of[rid] != s2_prompt:
            continue
        # S1 and S2 may share a run id (S1 is S2's "reaching the LLM" reading):
        # the view tells them apart.
        if p["view"] == "static_only" or "S2" not in systems_of[rid]:
            s = "S1"
        elif p["view"] == ctx.view:
            s = "S2"
        else:
            continue
        tot, det = num(p["bug_points_total"]), num(p["bug_points_detected"])
        if tot:
            key = (p["run_id"], norm_pattern(p["pattern"]))
            vals[s][norm_pattern(p["pattern"])].append((key, det / tot))
    # one value per (run, pattern) -- S1 rows repeated per view collapse here
    for s in vals:
        for pat in vals[s]:
            vals[s][pat] = list(dict(vals[s][pat]).values())
    pub = defaultdict(dict)
    for r in ctx.d.published or []:
        m = re.match(r"recall[_:]?\(?([RW,]+)\)?$", r["metric"].strip(), re.I)
        if m and num(r["value"]) is not None:
            v = num(r["value"])
            pub[(r["tool"], r["cases"], r["ground_truth"])][norm_pattern(m.group(1))] = v / 100 if v > 1 else v
    if not any(vals[s] for s in vals) and not pub:
        raise Skip("patterns.csv sem linhas para esses rótulos e subconjunto")
    groups = [("S0", k) for k in pub] + [("S1", None), ("S2", None)]
    groups = [g for g in groups if g[0] == "S0" or vals[g[0]]]
    fig, ax = plt.subplots(figsize=(WIDTH, 3.0))
    width = 0.8 / len(groups)
    hatches = ["///", "\\\\\\", "...", "xx"]
    for gi, (s, key) in enumerate(groups):
        xs = [pi - 0.4 + width * (gi + 0.5) for pi in range(len(PATTERNS))]
        if s == "S0":
            ys = [pub[key].get(p) for p in PATTERNS]
            for x, y, p in zip(xs, ys, PATTERNS):
                if y is None:
                    ax.text(x, 0.01, "n/d", ha="center", va="bottom", fontsize=6.5, color=MUTED, rotation=90)
                    continue
                ax.bar(x, y, width=width * 0.92, color=COLOR["S0"], edgecolor=EDGE["S0"],
                       hatch=hatches[(gi) % len(hatches)], linewidth=0.6)
                if y < 0.05:  # a zero bar is the finding (a blind spot): make it visible
                    ax.text(x, y + 0.015, br(y * 100, 0) + "%", ha="center", va="bottom", fontsize=7, color=INK)
            continue
        for x, p in zip(xs, PATTERNS):
            if not vals[s].get(p):
                continue
            m, lo, hi = spread(vals[s][p])
            ax.bar(x, m, width=width * 0.92, color=COLOR[s], edgecolor="white", linewidth=0.8)
            if m < 0.05:
                ax.text(x, m + 0.015, br(m * 100, 0) + "%", ha="center", va="bottom", fontsize=7, color=INK)
            if hi > lo:
                ax.errorbar(x, m, yerr=[[m - lo], [hi - m]], fmt="none", ecolor=INK, elinewidth=0.8, capsize=2)
    ax.set_xticks(range(len(PATTERNS)), [f"({','.join(p)})" for p in PATTERNS])
    ax.yaxis.set_major_formatter(pct_formatter())
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("recall no padrão")
    ax.set_xlabel(f"padrão $(A_1, B, A_2)$; S1 e S2: {label_name(ctx.labels)}")
    ax.grid(axis="x", visible=False)
    from matplotlib.patches import Patch
    handles = []
    for gi, (s, key) in enumerate(groups):
        if s == "S0":
            handles.append(Patch(facecolor=COLOR["S0"], edgecolor=EDGE["S0"], hatch=hatches[gi % len(hatches)],
                                 label=f"{key[0]} ({key[1]} casos, gabarito {key[2]}, conforme o artigo)"))
        else:
            handles.append(Patch(facecolor=COLOR[s], label=SYSTEM_NAMES[s]))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, fontsize=7.5)
    n = max([len(v) for s in vals for v in vals[s].values()] or [0])
    note(fig, f"S2: linha {s2_prompt}, {VIEW_NAMES[ctx.view]}; barras: mínimo e máximo de n = {n} execuções. "
              "S0 é medido no subconjunto e no gabarito do próprio artigo.")
    fig.subplots_adjust(bottom=0.3)
    return fig, {"published_groups": [list(k) for k in pub]}


# --- F5 -------------------------------------------------------------------------

def fig_f5(plt, ctx: Ctx):
    ctx.d.need("runs")
    present = {norm_labels(r["labels"]) for r in ctx.d.runs}
    labs = [l for l in LABEL_ORDER if l in present] + sorted(present - set(LABEL_ORDER))
    series = {}
    for s in ("S1", "S2"):
        for lab in labs:
            rows = ctx.runs(s, labels=lab, prompt=ctx.s2_prompt)
            rows = [r for r in rows if num(r["score"]) is not None and num(r["score_max"])]
            if rows:
                pctv = [num(r["score"]) / num(r["score_max"]) for r in rows]
                raw = [num(r["score"]) for r in rows]
                series[(s, lab)] = (spread(pctv), spread(raw), num(rows[0]["score_max"]), len(rows))
    if not series:
        raise Skip("runs.csv sem pontuação para S1/S2")
    labs = [l for l in labs if any((s, l) in series for s in ("S1", "S2"))]
    fig, ax = plt.subplots(figsize=(WIDTH, 3.0))
    width = 0.34
    for si, s in enumerate(("S1", "S2")):
        for li, lab in enumerate(labs):
            if (s, lab) not in series:
                continue
            (m, lo, hi), (rm, rlo, rhi), smax, n = series[(s, lab)]
            x = li + (si - 0.5) * width
            ax.bar(x, m, width=width * 0.92, color=COLOR[s], edgecolor="white", linewidth=0.8,
                   label=SYSTEM_NAMES[s] if li == 0 else None)
            if hi > lo:
                ax.errorbar(x, m, yerr=[[m - lo], [hi - m]], fmt="none", ecolor=INK, elinewidth=0.8, capsize=3)
            txt = f"{br(rm, 1 if n > 1 else 0)}/{br(smax, 0)}"
            ax.text(x, max(hi, 0) + 0.025, txt, ha="center", va="bottom", fontsize=7.5, color=INK)
    ax.set_xticks(range(len(labs)), [SHORT_LABEL.get(l, l) for l in labs])
    ax.set_xlabel("gabarito do Racebench em que a pontuação é calculada")
    ax.set_ylabel("pontuação NASAC\n(% do máximo do gabarito)")
    ax.yaxis.set_major_formatter(pct_formatter())
    lo_all = min(min(v[0][1] for v in series.values()), 0)
    ax.set_ylim(lo_all, 1.12)
    ax.axhline(0, color=MUTED, linewidth=0.6)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.13), ncol=2)
    ns = sorted({v[3] for v in series.values()})
    note(fig, f"+2 por defeito detectado, −3 por armadilha reportada; rótulo: média/máximo. S2: linha "
              f"{ctx.s2_prompt}, {VIEW_NAMES[ctx.view]}; barras: mínimo e máximo de n = "
              f"{', '.join(map(str, ns))} execuções. Gabarito 2.2: S0 não tem pontuação.")
    return fig, {"labels": labs}


# --- F6 -------------------------------------------------------------------------

def prompt_rows(ctx: Ctx) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for r in ctx.d.runs or []:
        if (r["system"] == "S2" and norm_labels(r["labels"]) == ctx.labels
                and r["case_subset"] == ctx.subset and r["view"] == ctx.view):
            out[r["prompt_row"]].append(r)
    return out


def prompt_order(rows: dict, baseline: str) -> list[str]:
    rest = sorted(p for p in rows if p != baseline)
    return ([baseline] if baseline in rows else []) + rest


def fig_f6(plt, ctx: Ctx):
    ctx.d.need("runs")
    rows = prompt_rows(ctx)
    if len(rows) < 2:
        raise Skip("menos de duas linhas de prompt em runs.csv")
    order = prompt_order(rows, ctx.baseline)
    smax = num(next(iter(rows.values()))[0]["score_max"])
    metrics = [("score", f"pontuação NASAC (máx. {br(smax, 0) if smax else '?'})", 1.0, br_formatter()),
               ("traps_reported", "armadilhas reportadas", 1.0, br_formatter()),
               ("inspection_ratio_mean", "$\\it{Inspection\\ Ratio}$ médio", 1.0, pct_formatter())]
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH, 0.9 + 0.36 * len(order)), sharey=True)
    # Recall veto: a bug point called infeasible, i.e. missing from the "not
    # infeasible" reading (a bug in `uncertain` is not a veto).
    loses = {r["prompt_row"] for r in ctx.d.runs
             if r["system"] == "S2" and r["view"] == "not_infeasible"
             and norm_labels(r["labels"]) == ctx.labels and r["case_subset"] == ctx.subset
             and num(r["bug_points_detected"]) is not None and num(r["bug_points_total"]) is not None
             and num(r["bug_points_detected"]) < num(r["bug_points_total"])}
    for ax, (key, title, scale, fmt) in zip(axes, metrics):
        base = stat(rows.get(ctx.baseline, []), key, scale)
        if base:
            ax.axvspan(base[1], base[2], color=COLOR["S2"], alpha=0.13, linewidth=0)
            ax.axvline(base[0], color=EDGE["S2"], linewidth=0.8, linestyle=(0, (3, 2)))
        for y, p in enumerate(order):
            s = stat(rows[p], key, scale)
            if not s:
                continue
            n = len(rows[p])
            if n > 1:
                ax.hlines(y, s[1], s[2], color=EDGE["S2"], linewidth=1.4)
            ax.plot(s[0], y, marker="o", markersize=6, color=COLOR["S2"], markeredgecolor="white",
                    markeredgewidth=1.0, zorder=3)
        ax.set_title(title, fontsize=8.5)
        ax.xaxis.set_major_formatter(fmt)
        ax.grid(axis="y", visible=False)
    kappa = defaultdict(list)
    for a in ctx.d.agreement or []:
        if a.get("field") == "bucket" and num(a.get("kappa")) is not None:
            kappa[a["prompt_row"]].append(num(a["kappa"]))
    names = [p + (" †" if p in loses else "") + (" (base)" if p == ctx.baseline else "")
             + (f"\n$\\kappa$ médio {br(statistics.mean(kappa[p]), 2)}" if kappa.get(p) else "") for p in order]
    axes[0].set_yticks(range(len(order)), names)
    axes[0].invert_yaxis()
    ns = sorted({len(v) for v in rows.values()})
    note(fig, f"Ponto: média; traço: mínimo e máximo de n = {', '.join(map(str, ns))} execuções; faixa e linha "
              f"tracejada: a linha de base ({ctx.baseline}). {label_name(ctx.labels)}, {VIEW_NAMES[ctx.view]}."
              + (" † perde ao menos um ponto de defeito em alguma execução (veto de recall)." if loses else ""))
    return fig, {"prompts": order, "recall_veto": sorted(loses)}


# --- F7 -------------------------------------------------------------------------

def fig_f7(plt, ctx: Ctx, show_all: bool = False):
    ctx.d.need("runs", "items")
    rows = prompt_rows(ctx)
    if not rows:
        raise Skip("nenhuma execução S2 para esses rótulos")
    order = prompt_order(rows, ctx.baseline)
    cols = []  # (prompt, run_id)
    for p in order:
        for r in sorted(rows[p], key=lambda r: (num(r["sample"]) or 0, r["run_id"])):
            cols.append((p, r["run_id"]))
    col_of = {rid: k for k, (_, rid) in enumerate(cols)}
    cells = defaultdict(dict)
    for it in ctx.items_for(set(col_of)):
        if it["item_kind"] not in ("bug", "trap"):
            continue
        b = it.get("bucket") if it["fate"] == "llm" else "static"
        cells[(it["item_kind"], it["case"], it["item_id"])][col_of[it["run_id"]]] = b or "static"
    if not cells:
        raise Skip("items.csv sem itens rotulados dessas execuções")
    keys = sorted(cells, key=lambda k: (k[0] != "bug", k[1], k[2]))
    flipped = [k for k in keys if len(set(cells[k].values())) > 1]
    shown = keys if show_all else flipped
    import numpy as np
    from matplotlib.colors import ListedColormap
    cats = BUCKETS + ["static"]
    idx = {c: k for k, c in enumerate(cats)}
    fig_h = 1.3 + 0.2 * max(len(shown), 1)
    fig, ax = plt.subplots(figsize=(WIDTH, fig_h))
    if shown:
        mat = np.full((len(shown), len(cols)), np.nan)
        for y, k in enumerate(shown):
            for x, b in cells[k].items():
                mat[y, x] = idx.get(b, idx["static"])
        cmap = ListedColormap([BUCKET_COLOR[c] for c in cats]).with_extremes(bad="white")
        ax.imshow(mat, aspect="auto", cmap=cmap, vmin=-0.5, vmax=len(cats) - 0.5, interpolation="nearest")
        for y, k in enumerate(shown):
            for x, b in cells[k].items():
                loss = k[0] == "bug" and b == "likely_infeasible"
                dark = b in ("likely_real", "likely_infeasible")
                ax.text(x, y, BUCKET_LETTER.get(b, "?"), ha="center", va="center", fontsize=6.5,
                        color="white" if dark else INK, fontweight="bold" if loss else "normal")
                if loss:
                    ax.add_patch(plt.Rectangle((x - 0.5, y - 0.5), 1, 1, fill=False, edgecolor=INK, linewidth=1.4))
        ax.set_yticks(range(len(shown)), [f"{'D' if k[0] == 'bug' else 'A'} {case_short(k[1])} · {k[2]}" for k in shown],
                      fontsize=7)
        nb = sum(1 for k in shown if k[0] == "bug")
        if 0 < nb < len(shown):
            ax.axhline(nb - 0.5, color=INK, linewidth=0.8)
    else:
        ax.text(0.5, 0.5, "nenhum item rotulado mudou de grupo entre execuções ou linhas",
                ha="center", va="center", transform=ax.transAxes, color=MUTED)
        ax.set_yticks([])
    sample_no, seen = [], Counter()
    for p, _ in cols:
        seen[p] += 1
        sample_no.append(str(seen[p]))
    ax.set_xticks(range(len(cols)), sample_no, fontsize=6.5)
    # prompt names over their run columns
    start = 0
    for p in order:
        n = len(rows[p])
        ax.text(start + (n - 1) / 2, -0.75 if shown else 1.02, p, ha="center", va="bottom", fontsize=7,
                rotation=0, transform=ax.transData if shown else ax.transAxes)
        if start:
            ax.axvline(start - 0.5, color="white", linewidth=2.5)
        start += n
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    ax.set_xlabel("execução, por linha de prompt")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=BUCKET_COLOR[c], edgecolor=GRID,
                             label=f"{BUCKET_LETTER[c]}  {BUCKET_NAMES.get(c, 'descartado com prova (estático)')}")
                       for c in cats], loc="upper center", bbox_to_anchor=(0.5, -0.06 - 0.6 / fig_h), ncol=3, fontsize=7)
    hidden = len(keys) - len(shown)
    note(fig, f"D = ponto de defeito, A = armadilha ({label_name(ctx.labels)}). "
              + (f"{hidden} itens com o mesmo grupo em todas as colunas omitidos. " if hidden else "")
              + "Contorno e letra em negrito: defeito julgado inviável (perda de recall).")
    return fig, {"columns": [list(c) for c in cols], "items_shown": len(shown), "items_total": len(keys)}


# --- F8 -------------------------------------------------------------------------

def fig_f8(plt, ctx: Ctx):
    ctx.d.need("runs")
    rows = prompt_rows(ctx)
    if not rows:
        raise Skip("nenhuma execução S2")
    order = prompt_order(rows, ctx.baseline)
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.0), sharey=True)
    for r in (r for rs in rows.values() for r in rs):
        ti, to = num(r["tokens_in"]), num(r["tokens_out"])
        r["_tokens_k"] = str((ti + to) / 1000) if ti is not None and to is not None else ""
    for ax, (key, title, fmt) in zip(axes, [("llm_calls", "chamadas ao modelo", br_formatter()),
                                            ("_tokens_k", "tokens (entrada + saída, milhares)", br_formatter())]):
        plotted = False
        for p in order:
            sx, sy = stat(rows[p], key), stat(rows[p], "score")
            if not sx or not sy:
                continue
            n = len(rows[p])
            ax.errorbar(sx[0], sy[0], xerr=errbar(sx) if n > 1 else None, yerr=errbar(sy) if n > 1 else None,
                        fmt="o", color=COLOR["S2"], ecolor=EDGE["S2"], elinewidth=0.8, capsize=2,
                        markersize=5.5, markeredgecolor="white", markeredgewidth=0.9)
            ax.annotate(p, (sx[0], sy[0]), xytext=(5, 4), textcoords="offset points", fontsize=7, color=INK)
            plotted = True
        if not plotted:
            ax.text(0.5, 0.5, "sem dados", ha="center", transform=ax.transAxes, color=MUTED)
        ax.set_xlabel(title)
        ax.xaxis.set_major_formatter(fmt)
        ax.margins(x=0.25, y=0.2)
    smax = num(next(iter(rows.values()))[0]["score_max"])
    axes[0].set_ylabel(f"pontuação NASAC (máx. {br(smax, 0) if smax else '?'})")
    axes[0].yaxis.set_major_formatter(br_formatter())
    ns = sorted({len(v) for v in rows.values()})
    note(fig, f"Uma marca por linha de prompt; barras: mínimo e máximo de n = {', '.join(map(str, ns))} execuções. "
              f"{label_name(ctx.labels)}, {VIEW_NAMES[ctx.view]}.")
    return fig, {"prompts": order}


# --- F9 -------------------------------------------------------------------------

def _ir(order: list[dict]) -> float | None:
    bugs = [k for k, i in enumerate(order) if i["item_kind"] == "bug"]
    return (max(bugs) + 1) / len(order) if bugs and order else None


def ir_from_items(items: list[dict]) -> dict[str, tuple[float | None, float | None]]:
    """Per-case (static, triage) Inspection Ratio. None when a bug point of the
    case never reaches the list: an IR over an incomplete detection is not
    reported, as in the scorer."""
    rank = {b: k for k, b in enumerate(BUCKETS)}
    by_case = defaultdict(list)
    for i in items:
        by_case[i["case"]].append(i)
    out = {}
    for case, its in by_case.items():
        if any(i["item_kind"] == "bug" and i["fate"] != "llm" for i in its):
            out[case] = (None, None)
            continue
        lst = [i for i in its if i["fate"] == "llm"]
        tri = sorted(lst, key=lambda i: (rank.get(i.get("bucket"), len(BUCKETS)),
                                         -(num(i.get("confidence")) or 0.0), i["item_kind"] == "bug"))
        out[case] = (_ir(lst), _ir(tri))
    return out


def fig_f9(plt, ctx: Ctx):
    ctx.d.need("runs")
    s2 = ctx.runs("S2", prompt=ctx.s2_prompt)
    run_ids = [r["run_id"] for r in s2]
    if not run_ids:
        raise Skip("nenhuma execução S2")
    per_case = defaultdict(lambda: {"S1": [], "S2": []})
    source = "cases.csv"
    if ctx.d.cases:
        for r in ctx.d.cases:
            if r["run_id"] in run_ids:
                for s, k in (("S1", "ir_static"), ("S2", "ir_triage")):
                    if num(r.get(k)) is not None:
                        per_case[r["case"]][s].append(num(r[k]))
    else:
        ctx.d.need("items")
        print("  aviso F9: sem cases.csv; IR estático calculado na ordem das linhas de items.csv")
        source = "items.csv"
        by_run = defaultdict(list)
        for it in ctx.items_for(set(run_ids)):
            by_run[it["run_id"]].append(it)
        for rid, its in by_run.items():
            for case, (a, b) in ir_from_items(its).items():
                if a is not None:
                    per_case[case]["S1"].append(a)
                if b is not None:
                    per_case[case]["S2"].append(b)
    cases = sorted(c for c, v in per_case.items() if v["S1"] and v["S2"])
    if not cases:
        raise Skip("nenhum caso com IR definido para S1 e S2")
    fig, ax = plt.subplots(figsize=(WIDTH, 3.2))
    import random
    rnd = random.Random(7)
    pairs = []
    for c in cases:
        a = statistics.mean(per_case[c]["S1"])
        b = spread(per_case[c]["S2"])
        j = rnd.uniform(-0.07, 0.07)
        pairs.append((a, b, j))
        ax.plot([0 + j, 1 + j], [a, b[0]], color=GRID, linewidth=0.8, zorder=1)
        ax.scatter(0 + j, a, s=20, color=COLOR["S1"], edgecolor="white", linewidth=0.6, zorder=3)
        if len(per_case[c]["S2"]) > 1:
            ax.vlines(1 + j, b[1], b[2], color=EDGE["S2"], linewidth=0.8, zorder=2)
        ax.scatter(1 + j, b[0], s=20, color=COLOR["S2"], edgecolor="white", linewidth=0.6, zorder=3)
    for x, vals, s in ((0, [p[0] for p in pairs], "S1"), (1, [p[1][0] for p in pairs], "S2")):
        bp = ax.boxplot(vals, positions=[x + 0.32], widths=0.12, patch_artist=True, showfliers=False)
        for part in ("boxes",):
            for b in bp[part]:
                b.set(facecolor="white", edgecolor=EDGE[s], linewidth=0.8)
        for part in ("whiskers", "caps", "medians"):
            for l in bp[part]:
                l.set(color=EDGE[s], linewidth=0.8)
    ax.set_xticks([0.12, 1.12], [SYSTEM_NAMES["S1"] + "\n(ordem dos registros)",
                                 SYSTEM_NAMES["S2"] + "\n(ordem da triagem)"])
    ax.set_xlim(-0.35, 1.6)
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(pct_formatter())
    ax.set_ylabel(f"$\\it{{Inspection\\ Ratio}}$ por caso\n({label_name(ctx.labels)})")
    ax.grid(axis="x", visible=False)
    n = len(run_ids)
    note(fig, f"Um ponto por caso ({len(cases)} casos com todos os defeitos detectados), ligado entre S1 e S2; "
              f"S2: média de n = {n} execuções da linha {ctx.s2_prompt}"
              + (", traço: mínimo e máximo" if n > 1 else "") + f". Menor é melhor. Fonte: {source}.")
    return fig, {"run_ids": run_ids, "cases": len(cases), "source": source}


# --- F10 / F11 --------------------------------------------------------------------

def fig_f10(plt, ctx: Ctx):
    ctx.d.need("items", "labels22")
    bugs21 = defaultdict(set)
    for it in ctx.d.items:
        if it["item_kind"] == "bug":
            bugs21[it["case"]].add(it["item_id"])
    comp = defaultdict(Counter)
    groups = defaultdict(set)
    for r in ctx.d.labels22:
        v = r["verdict"].strip().lower()
        if v not in V22:
            print(f"  F10: veredicto desconhecido {v!r} em {r['case']} {r['item_id']}; ignorado")
            continue
        comp[r["case"]][v] += 1
        if v == "bug":
            groups[r["case"]].add(r.get("group") or f"{r['case']}:{r['item_id']}")
    cases = sorted(set(bugs21) | set(comp))
    cats = [("bug21", "defeitos do 2.1", "#104281", None),
            ("bug", "novos defeitos (triplas)", "#86b6ef", "//"),
            ("trap", "novas armadilhas", COLOR["S2"], None),
            ("not_defect", "não é defeito", "#d9d9d9", None),
            ("undecided", "indeciso", "white", "..")]
    fig, ax = plt.subplots(figsize=(WIDTH, 0.9 + 0.2 * len(cases)))
    left = [0] * len(cases)
    for key, name, color, hatch in cats:
        vals = [len(bugs21[c]) if key == "bug21" else comp[c][key] for c in cases]
        nz = [k for k, v in enumerate(vals) if v > 0]  # a zero-width bar still draws its edge
        ax.barh(nz, [vals[k] for k in nz], left=[left[k] for k in nz], height=0.7, color=color, hatch=hatch,
                edgecolor="white" if color != "white" else MUTED, linewidth=0.8 if color != "white" else 0.5,
                label=name)
        left = [a + b for a, b in zip(left, vals)]
    for y, c in enumerate(cases):
        if groups[c]:
            ax.text(left[y] + 0.15, y, f"{len(groups[c])} distinto{'s' if len(groups[c]) > 1 else ''}",
                    va="center", fontsize=6.5, color=MUTED)
    ax.set_yticks(range(len(cases)), [case_short(c) for c in cases], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("itens por caso (triplas)")
    ax.xaxis.set_major_formatter(br_formatter())
    ax.grid(axis="y", visible=False)
    ax.margins(x=0.12)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=c, hatch=h, edgecolor="white" if c != "white" else MUTED, label=n)
                       for _, n, c, h in cats],
              loc="upper center", bbox_to_anchor=(0.5, -0.12 - 0.5 / (0.9 + 0.2 * len(cases))), ncol=3, fontsize=7.5)
    tot = Counter()
    for c in comp.values():
        tot.update(c)
    ndist = sum(len(g) for g in groups.values())
    note(fig, f"Defeitos do 2.1: {label_name(ctx.labels)}. Novos: {tot['bug']} triplas em {ndist} defeitos distintos "
              f"(regra de equivalência); armadilhas: {tot['trap']}; não é defeito: {tot['not_defect']}; "
              f"indecisos: {tot['undecided']} (fora dos denominadores).")
    return fig, {"adjudicated": sum(tot.values())}


def fig_f11(plt, ctx: Ctx):
    ctx.d.need("runs", "items", "labels22")
    new = {(r["case"], r["item_id"]) for r in ctx.d.labels22 if r["verdict"].strip().lower() == "bug"}
    if not new:
        raise Skip("labels22.csv sem defeitos novos")
    s2 = ctx.runs("S2", prompt=ctx.s2_prompt)
    run_ids = [r["run_id"] for r in s2] or sorted({i["run_id"] for i in ctx.d.items})
    cats = BUCKETS + ["static"]
    per_run = {rid: Counter() for rid in run_ids}
    for it in ctx.items_for(set(run_ids)):
        if (it["case"], it["item_id"]) in new:
            per_run[it["run_id"]][it.get("bucket") if it["fate"] == "llm" else "static"] += 1
    fig, ax = plt.subplots(figsize=(WIDTH, 2.6))
    for k, c in enumerate(cats):
        vals = [per_run[r][c] for r in run_ids]
        m, lo, hi = spread(vals)
        ax.bar(k, m, width=0.6, color=COLOR["S2"] if c != "static" else COLOR["S1"], edgecolor="white")
        if hi > lo:
            ax.errorbar(k, m, yerr=[[m - lo], [hi - m]], fmt="none", ecolor=INK, elinewidth=0.8, capsize=3)
        ax.text(k, hi + len(new) * 0.02, br(m, 1 if len(vals) > 1 else 0), ha="center", va="bottom", fontsize=7.5)
    names = [BUCKET_NAMES[c].replace(" ", "\n", 1) for c in BUCKETS] + ["não chega\nà triagem"]
    ax.set_xticks(range(len(cats)), names)
    ax.set_ylabel(f"novos defeitos do 2.2\n(de {len(new)} triplas)")
    ax.yaxis.set_major_formatter(br_formatter())
    ax.set_ylim(0, len(new) * 1.12)
    ax.grid(axis="x", visible=False)
    note(fig, f"Grupo atribuído pela triagem (linha {ctx.s2_prompt}) aos candidatos confirmados como defeito na "
              f"adjudicação; barras: mínimo e máximo de n = {len(run_ids)} execuções.")
    return fig, {"run_ids": run_ids, "new_bugs": len(new)}


FIGURES = {"F1": fig_f1, "F2": fig_f2, "F3": fig_f3, "F4": fig_f4, "F5": fig_f5, "F6": fig_f6,
           "F7": fig_f7, "F8": fig_f8, "F9": fig_f9, "F10": fig_f10, "F11": fig_f11}


# --- main ---------------------------------------------------------------------------

def to_grey(png: Path) -> None:
    import matplotlib.image as mpimg
    import numpy as np
    img = mpimg.imread(png)
    rgb = img[..., :3]
    grey = rgb @ np.array([0.299, 0.587, 0.114])
    out = np.dstack([grey, grey, grey] + ([img[..., 3]] if img.shape[-1] == 4 else []))
    mpimg.imsave(png.with_name(png.stem + "-cinza.png"), np.clip(out, 0, 1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA, help="directory with the CSVs (default: %(default)s)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: %(default)s)")
    ap.add_argument("--only", default="", help="comma-separated subset, e.g. F1,F5")
    ap.add_argument("--labels", default="53/33", help="headline label set (default: %(default)s)")
    ap.add_argument("--subset", default="all", help="case subset for our systems (default: %(default)s)")
    ap.add_argument("--view", default="likely_real", choices=sorted(VIEW_BUCKETS),
                    help="S2's reading of 'reported' (default: %(default)s)")
    ap.add_argument("--s2-prompt", default=None, help="S2's prompt row (default: the one with most runs)")
    ap.add_argument("--baseline-prompt", default="+racebench", help="baseline row for F6-F8 (default: %(default)s)")
    ap.add_argument("--f7-all", action="store_true", help="F7: show every labelled item, not only those that flip")
    ap.add_argument("--png", action="store_true", help="also write PNG previews")
    ap.add_argument("--grey", action="store_true", help="also write greyscale PNG previews (implies --png)")
    args = ap.parse_args(argv)

    try:
        plt, family = setup_style()
    except ImportError:
        print("matplotlib is not installed: pip install -e .[figures]", file=sys.stderr)
        return 2
    if not args.data.is_dir():
        print(f"data directory not found: {args.data}", file=sys.stderr)
        return 2
    data = Data(args.data)
    ctx = Ctx(data, args)
    wanted = [f.strip().upper() for f in args.only.split(",") if f.strip()] or list(FIGURES)
    unknown = [f for f in wanted if f not in FIGURES]
    if unknown:
        print(f"unknown figure(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"dados: {args.data}\nsaída: {args.out}\nfonte: {family or 'padrão do matplotlib'}")
    record = {"data": str(args.data), "font": family, **ctx.describe(),
              "manifest": {k: data.manifest.get(k) for k in ("commit", "model", "date", "created")
                           if isinstance(data.manifest, dict) and k in data.manifest},
              "figures": {}}
    failed = 0
    for key in wanted:
        print(f"{key}: ", end="", flush=True)
        try:
            fn = FIGURES[key]
            fig, info = fn(plt, ctx, args.f7_all) if key == "F7" else fn(plt, ctx)
        except Skip as exc:
            print(f"ignorada ({exc})")
            record["figures"][key] = {"skipped": str(exc)}
            continue
        except Exception as exc:  # one broken figure must not hide the others
            print(f"ERRO: {type(exc).__name__}: {exc}")
            record["figures"][key] = {"error": f"{type(exc).__name__}: {exc}"}
            failed += 1
            continue
        path = args.out / f"{FIGURE_FILES[key]}.pdf"
        place_note(fig)
        fig.savefig(path)
        if args.png or args.grey:
            png = path.with_suffix(".png")
            fig.savefig(png, dpi=150, facecolor="white")
            if args.grey:
                to_grey(png)
        plt.close(fig)
        info = {**info, "file": path.name}
        if "s2_prompt" not in info and ctx._s2:
            info["s2_prompt"] = ctx._s2
        record["figures"][key] = info
        print(path.name)
    (args.out / "thesis-figures.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                                  encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
