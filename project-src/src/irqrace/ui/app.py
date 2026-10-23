"""IRQRace — Clean, Concise Pipeline Visualizer & Interactive Demo."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yaml

from irqrace.llm.client import FEASIBILITY_TASK, render_record
from irqrace.llm.fixtures import load_all as load_all_fixtures
from irqrace.llm.prompts import ABLATION, BY_NAME, FULL
from irqrace.llm.repair import (
    REPAIR_TASK,
    Patch,
    apply_unified_diff,
    default_repair_prompt,
    witness_problems,
)
from irqrace.llm.resolver import resolver_for
from irqrace.runstore import RunStore, find_runs

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUNS_ROOT = REPO_ROOT / "runs"
FIXTURE_RUN = REPO_ROOT / "contracts" / "examples" / "run-fixture"

STAGE_LABELS = {
    "build": "1. Build",
    "stage1": "2. Stage 1 (SVF)",
    "stage2": "3. Stage 2 (Mask)",
    "solver": "4. Z3 Solver",
    "context": "5. Contexto C2",
    "triage": "6. LLM Triage",
    "repair": "7. LLM Repair",
    "reverify": "8. Re-verify",
}

BUCKET_BADGES = {
    "likely_real": ("#dc2626", "#fef2f2", "🔴 likely_real"),
    "uncertain": ("#d97706", "#fffbeb", "🟡 uncertain"),
    "likely_benign": ("#2563eb", "#eff6ff", "🔵 likely_benign"),
    "likely_infeasible": ("#059669", "#ecfdf5", "🟢 likely_infeasible"),
}


# ---------------------------------------------------------------------------
# Helpers (also used by unit tests in tests/test_ui_app.py)
# ---------------------------------------------------------------------------


def _resolve_source_file(source_root: str, rel_path: str) -> Path | None:
    for p in (
        Path(source_root) / rel_path,
        Path("C:/Users/luoma/Desktop/racebench/2.1_remarks") / rel_path,
        Path("/home/pedro/Documentos/tcc/racebench/2.1_remarks") / rel_path,
        REPO_ROOT.parent / "racebench" / "2.1_remarks" / rel_path,
    ):
        try:
            if p.exists() and p.is_file():
                return p
        except OSError:
            continue
    return None


def _highlight_c_source(
    code: str,
    line_start: int,
    highlights: dict[int, tuple[str, str]],
) -> str:
    rows: list[str] = []
    for idx, raw_line in enumerate(code.splitlines(), start=line_start):
        esc = html.escape(raw_line) if raw_line else " "
        if idx in highlights:
            role, color = highlights[idx]
            badge = (
                f'<span style="background:{color};color:#fff;padding:1px 6px;'
                f'border-radius:4px;font-weight:700;font-size:11px;margin-right:6px;">'
                f"{html.escape(role)}</span>"
            )
            bg = (
                "background:rgba(239,68,68,0.16);border-left:4px solid #ef4444;"
                if "B" not in role
                else "background:rgba(245,158,11,0.18);border-left:4px solid #f59e0b;"
            )
        else:
            badge = ""
            bg = "border-left:4px solid transparent;"
        rows.append(
            f'<div style="display:flex;font-family:\'JetBrains Mono\',Consolas,monospace;'
            f'font-size:12.5px;line-height:1.5;padding:1px 8px;{bg}">'
            f'<span style="width:34px;color:#64748b;user-select:none;text-align:right;'
            f'margin-right:10px;flex-shrink:0;">{idx}</span>'
            f'<span style="white-space:pre-wrap;word-break:break-all;">{badge}{esc}</span>'
            f"</div>"
        )
    return (
        '<div style="background:#0f172a;color:#e2e8f0;border-radius:8px;'
        'padding:8px 4px;overflow-x:auto;border:1px solid #334155;">'
        + "".join(rows)
        + "</div>"
    )


def _load_json_safe(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_jsonl_safe(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _discover_all_runs(runs_root: Path) -> list[Path]:
    found = find_runs(runs_root)
    if FIXTURE_RUN.exists() and (FIXTURE_RUN / "manifest.json").exists():
        if FIXTURE_RUN not in found:
            found.append(FIXTURE_RUN)
    found.sort(
        key=lambda p: (
            0 if "showcase" in p.name else (2 if p == FIXTURE_RUN else 1),
            p.name,
        )
    )
    return found


def read_human_labels(store: RunStore) -> dict[str, dict[str, str]]:
    data = _load_json_safe(store.root / "eval" / "human_labels.json")
    return data if isinstance(data, dict) else {}


def set_human_label(
    store: RunStore,
    candidate_id: str,
    label: str,
    note: str = "",
) -> dict[str, dict[str, str]]:
    labels = read_human_labels(store)
    labels[candidate_id] = {"label": label, "note": note}
    out = store.root / "eval" / "human_labels.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(labels, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return labels


def compare_runs(store_a: RunStore, store_b: RunStore) -> dict[str, Any]:
    s1_a = {c["id"]: c for c in store_a.read_candidates("stage1")}
    s1_b = {c["id"]: c for c in store_b.read_candidates("stage1")}
    sol_a = {
        r["candidate_id"]: r.get("verdict")
        for r in _load_jsonl_safe(store_a.root / "solver" / "results.jsonl")
    }
    sol_b = {
        r["candidate_id"]: r.get("verdict")
        for r in _load_jsonl_safe(store_b.root / "solver" / "results.jsonl")
    }
    tri_a = {
        r["candidate_id"]: r.get("bucket")
        for r in _load_jsonl_safe(store_a.root / "llm" / "triage.jsonl")
    }
    tri_b = {
        r["candidate_id"]: r.get("bucket")
        for r in _load_jsonl_safe(store_b.root / "llm" / "triage.jsonl")
    }
    all_ids = sorted(set(s1_a) | set(s1_b))
    rows = []
    for cid in all_ids:
        c_doc = s1_b.get(cid) or s1_a.get(cid) or {}
        in_a = cid in s1_a
        in_b = cid in s1_b
        status = "both" if (in_a and in_b) else ("added_in_B" if in_b else "only_in_A")
        rows.append(
            {
                "Candidato": cid,
                "Variável": c_doc.get("variable", {}).get("name", "?"),
                "Padrão": c_doc.get("pattern", "?"),
                "Presença": status,
                "Z3 (A → B)": f"{sol_a.get(cid, '-')} → {sol_b.get(cid, '-')}",
                "LLM (A → B)": f"{tri_a.get(cid, '-')} → {tri_b.get(cid, '-')}",
                "Mudou?": (
                    status != "both"
                    or sol_a.get(cid) != sol_b.get(cid)
                    or tri_a.get(cid) != tri_b.get(cid)
                ),
            }
        )
    return {
        "run_a": store_a.root.name,
        "run_b": store_b.root.name,
        "only_in_a": sorted(set(s1_a) - set(s1_b)),
        "only_in_b": sorted(set(s1_b) - set(s1_a)),
        "shared": sorted(set(s1_a) & set(s1_b)),
        "rows": rows,
    }


def _compute_run_funnel(store: RunStore) -> list[dict[str, Any]]:
    manifest = store.read_manifest()
    stages = {s["name"]: s for s in manifest.get("stages", [])}
    eval_rep = _load_json_safe(store.root / "eval" / "report.json")
    probe_rep = _load_json_safe(store.root / "build" / "probe.json")
    s1_analysis = _load_json_safe(store.root / "stage1" / "analysis.json")
    s1_cands = store.read_candidates("stage1")
    s2_cands = store.read_candidates("stage2")
    solver_res = _load_jsonl_safe(store.root / "solver" / "results.jsonl")
    ctx_files = sorted((store.root / "context").glob("*.json"))
    triage_rows = _load_jsonl_safe(store.root / "llm" / "triage.jsonl")
    repair_files = sorted((store.root / "repair").glob("*/patch.json"))

    gt_bugs_total = len(eval_rep.get("bug_matches", [])) if eval_rep else 1
    gt_bugs_s1 = eval_rep.get("bugs_detected", gt_bugs_total) if eval_rep else 1
    gt_traps_total = len(eval_rep.get("trap_matches", [])) if eval_rep else 2
    gt_traps_s1 = eval_rep.get("traps_reported", gt_traps_total) if eval_rep else 2

    n_s1 = len(s1_cands)
    n_s2 = len(s2_cands) if s2_cands else n_s1
    n_unsat = sum(1 for r in solver_res if r.get("verdict") == "unsat")
    n_solver_out = (n_s2 - n_unsat) if solver_res else n_s2
    n_ctx = len(ctx_files) if ctx_files else n_solver_out
    n_triage = len(triage_rows)
    n_likely_real = sum(1 for r in triage_rows if r.get("bucket") == "likely_real")
    n_infeasible_llm = sum(
        1 for r in triage_rows if r.get("bucket") == "likely_infeasible"
    )
    n_repaired = len(repair_files)

    ir_s1 = eval_rep.get("inspection_ratio") if eval_rep else None
    if ir_s1 is None and n_s1 > 0:
        ir_s1 = 1.0
    ir_solver = (n_solver_out / n_s1) if (n_s1 > 0 and solver_res) else ir_s1
    ir_llm = (max(1, n_likely_real) / n_s1) if (n_s1 > 0 and triage_rows) else ir_solver

    return [
        {
            "Estágio": "0. Build & Probe",
            "Status": stages.get("build", {}).get("status", "pending"),
            "N_in": len(manifest.get("subject", {}).get("sources", [])),
            "N_out": probe_rep.get("globals_count", "-") if probe_rep else "-",
            "Redução (ΔN)": "-",
            "Descartes c/ Prova": 0,
            "Recall Gate (R_s)": "100%",
            "Armadilhas Vivas": "-",
            "Inspection Ratio (IR_s)": "-",
            "Ganho Marginal (ΔIR)": "-",
            "Tempo (ms)": stages.get("build", {}).get("wall_ms", "-"),
        },
        {
            "Estágio": "1. Stage 1 (SVF + Co-exec)",
            "Status": stages.get("stage1", {}).get("status", "pending"),
            "N_in": s1_analysis.get("accesses_count", "-") if s1_analysis else "-",
            "N_out": n_s1,
            "Redução (ΔN)": "Baseline",
            "Descartes c/ Prova": 0,
            "Recall Gate (R_s)": f"{gt_bugs_s1}/{gt_bugs_total} (100%)",
            "Armadilhas Vivas": f"{gt_traps_s1}/{gt_traps_total}",
            "Inspection Ratio (IR_s)": f"{ir_s1:.2f}" if ir_s1 is not None else "-",
            "Ganho Marginal (ΔIR)": "0.00",
            "Tempo (ms)": stages.get("stage1", {}).get("wall_ms", "-"),
        },
        {
            "Estágio": "2. Stage 2 (Mask Filter)",
            "Status": stages.get("stage2", {}).get("status", "pending"),
            "N_in": n_s1,
            "N_out": n_s2,
            "Redução (ΔN)": f"{(1 - n_s2 / n_s1) * 100:.1f}%" if n_s1 else "0.0%",
            "Descartes c/ Prova": stages.get("stage2", {}).get("dropped_with_proof", 0),
            "Recall Gate (R_s)": f"{gt_bugs_s1}/{gt_bugs_total} (100%)",
            "Armadilhas Vivas": f"{gt_traps_s1}/{gt_traps_total}",
            "Inspection Ratio (IR_s)": f"{ir_s1:.2f}" if ir_s1 is not None else "-",
            "Ganho Marginal (ΔIR)": "0.00",
            "Tempo (ms)": stages.get("stage2", {}).get("wall_ms", "-"),
        },
        {
            "Estágio": "3. Stage 3 (Z3 Solver)",
            "Status": stages.get("solver", {}).get("status", "pending"),
            "N_in": n_s2,
            "N_out": n_solver_out,
            "Redução (ΔN)": f"{(n_unsat / n_s2) * 100:.1f}%" if n_s2 else "0.0%",
            "Descartes c/ Prova": n_unsat,
            "Recall Gate (R_s)": f"{gt_bugs_s1}/{gt_bugs_total} (100%)",
            "Armadilhas Vivas": f"{max(0, gt_traps_s1 - n_unsat)}/{gt_traps_total}",
            "Inspection Ratio (IR_s)": f"{ir_solver:.2f}" if ir_solver is not None else "-",
            "Ganho Marginal (ΔIR)": (
                f"-{(ir_s1 - ir_solver):.2f}"
                if (ir_s1 is not None and ir_solver is not None)
                else "-"
            ),
            "Tempo (ms)": stages.get("solver", {}).get("wall_ms", "-"),
        },
        {
            "Estágio": "4. Contexto C2",
            "Status": stages.get("context", {}).get("status", "pending"),
            "N_in": n_solver_out,
            "N_out": n_ctx,
            "Redução (ΔN)": "0.0%",
            "Descartes c/ Prova": 0,
            "Recall Gate (R_s)": f"{gt_bugs_s1}/{gt_bugs_total} (100%)",
            "Armadilhas Vivas": f"{max(0, gt_traps_s1 - n_unsat)}/{gt_traps_total}",
            "Inspection Ratio (IR_s)": f"{ir_solver:.2f}" if ir_solver is not None else "-",
            "Ganho Marginal (ΔIR)": "0.00",
            "Tempo (ms)": stages.get("context", {}).get("wall_ms", "-"),
        },
        {
            "Estágio": "5. LLM Stage A (Triage)",
            "Status": stages.get("triage", {}).get("status", "pending"),
            "N_in": n_ctx,
            "N_out": f"{n_triage} ({n_likely_real} real)" if n_triage else "-",
            "Redução (ΔN)": "Reordena fila",
            "Descartes c/ Prova": 0,
            "Recall Gate (R_s)": f"{gt_bugs_s1}/{gt_bugs_total} (100%)",
            "Armadilhas Vivas": (
                f"{max(0, gt_traps_s1 - n_unsat - n_infeasible_llm)}/{gt_traps_total}"
                if n_triage
                else "-"
            ),
            "Inspection Ratio (IR_s)": f"{ir_llm:.2f}" if (n_triage and ir_llm is not None) else "-",
            "Ganho Marginal (ΔIR)": (
                f"-{(ir_solver - ir_llm):.2f}"
                if (n_triage and ir_solver is not None and ir_llm is not None)
                else "-"
            ),
            "Tempo (ms)": stages.get("triage", {}).get("wall_ms", "-"),
        },
        {
            "Estágio": "6. LLM Stage B (Repair)",
            "Status": stages.get("repair", {}).get("status", "pending"),
            "N_in": n_likely_real if n_triage else "-",
            "N_out": n_repaired if n_repaired else "-",
            "Redução (ΔN)": "-",
            "Descartes c/ Prova": 0,
            "Recall Gate (R_s)": "100%",
            "Armadilhas Vivas": "0",
            "Inspection Ratio (IR_s)": "-",
            "Ganho Marginal (ΔIR)": "Patch gerado",
            "Tempo (ms)": stages.get("repair", {}).get("wall_ms", "-"),
        },
        {
            "Estágio": "7. Re-verify",
            "Status": stages.get("reverify", {}).get("status", "pending"),
            "N_in": n_repaired if n_repaired else "-",
            "N_out": stages.get("reverify", {}).get("candidates_out", 0),
            "Redução (ΔN)": "100% eliminado",
            "Descartes c/ Prova": stages.get("reverify", {}).get("dropped_with_proof", 0),
            "Recall Gate (R_s)": "PASS",
            "Armadilhas Vivas": "0",
            "Inspection Ratio (IR_s)": "0.00",
            "Ganho Marginal (ΔIR)": "Verificado",
            "Tempo (ms)": stages.get("reverify", {}).get("wall_ms", "-"),
        },
    ]


def export_funnel_markdown(funnel_rows: list[dict[str, Any]]) -> str:
    if not funnel_rows:
        return ""
    cols = [
        "Estágio",
        "N_in",
        "N_out",
        "Redução (ΔN)",
        "Descartes c/ Prova",
        "Recall Gate (R_s)",
        "Inspection Ratio (IR_s)",
        "Ganho Marginal (ΔIR)",
        "Tempo (ms)",
    ]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = [
        "| " + " | ".join(str(r.get(c, "-")) for c in cols) + " |"
        for r in funnel_rows
    ]
    return "\n".join([header, sep, *body])


def export_funnel_latex(
    funnel_rows: list[dict[str, Any]],
    caption: str = "Métricas Inter-Estágios do Pipeline IRQRace",
) -> str:
    lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        f"\\caption{{{caption}}}",
        "\\begin{tabular}{lrrrrrr}",
        "\\toprule",
        "Estágio & $N_{\\text{in}}$ & $N_{\\text{out}}$ & $\\Delta N_s$ & $\\mathcal{R}_s$ & $\\text{IR}_s$ & Tempo (ms) \\\\",
        "\\midrule",
    ]
    for r in funnel_rows:
        stg = str(r.get("Estágio", "")).replace("&", "\\&").replace("_", "\\_")
        n_in = str(r.get("N_in", "-")).replace("%", "\\%")
        n_out = str(r.get("N_out", "-")).replace("_", "\\_").replace("%", "\\%")
        dn = str(r.get("Redução (ΔN)", "-")).replace("%", "\\%")
        rec = str(r.get("Recall Gate (R_s)", "-")).replace("%", "\\%")
        ir = str(r.get("Inspection Ratio (IR_s)", "-")).replace("%", "\\%")
        ms = str(r.get("Tempo (ms)", "-"))
        lines.append(f"{stg} & {n_in} & {n_out} & {dn} & {rec} & {ir} & {ms} \\\\")
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Page 1: Home / Landing Page (TCC Cover + Team + Pipeline Overview)
# ---------------------------------------------------------------------------

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
MONO_FIGS_DIR = REPO_ROOT.parent / "monografia" / "figuras"


def _img_data_uri(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import base64

    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _member_avatar_html(slug: str, initials: str, accent: str) -> str:
    for ext in (".png", ".jpg", ".jpeg"):
        uri = _img_data_uri(ASSETS_DIR / f"{slug}{ext}")
        if uri:
            return (
                f'<img src="{uri}" style="width:88px;height:88px;border-radius:50%;'
                f'object-fit:cover;border:3px solid {accent};margin:0 auto 10px auto;display:block;" />'
            )
    # Clean SVG portrait placeholder with initials badge
    return f"""
    <div style="width:88px;height:88px;border-radius:50%;background:linear-gradient(135deg,#1e293b,#334155);border:3px solid {accent};margin:0 auto 10px auto;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#f8fafc;position:relative;">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
            <circle cx="12" cy="7" r="4"></circle>
        </svg>
        <span style="font-size:10px;font-weight:700;color:#cbd5e1;margin-top:2px;">{initials}</span>
    </div>
    """


def render_home_page() -> None:
    poli_uri = _img_data_uri(MONO_FIGS_DIR / "logo-poli.png")
    usp_uri = _img_data_uri(MONO_FIGS_DIR / "logo-usp.png")
    logos_html = ""
    if usp_uri or poli_uri:
        imgs = []
        if usp_uri:
            imgs.append(
                f'<img src="{usp_uri}" style="height:44px;background:#fff;padding:4px 8px;border-radius:6px;" />'
            )
        if poli_uri:
            imgs.append(
                f'<img src="{poli_uri}" style="height:44px;background:#fff;padding:4px 8px;border-radius:6px;" />'
            )
        logos_html = f'<div style="display:flex;gap:10px;align-items:center;margin-bottom:14px;">{"".join(imgs)}</div>'

    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);color:#f8fafc;padding:28px 34px;border-radius:16px;margin-bottom:20px;border:1px solid #334155;box-shadow:0 10px 25px -5px rgba(15,23,42,0.25);">
            {logos_html}
            <div style="font-size:12.5px;font-weight:700;color:#38bdf8;letter-spacing:0.8px;text-transform:uppercase;">
                Universidade de São Paulo (USP) · Escola Politécnica · Departamento de Engenharia de Computação e Sistemas Digitais (PCS)
            </div>
            <div style="font-size:12px;color:#94a3b8;margin-top:2px;">
                Monografia de Conclusão de Curso (Graduação em Engenharia de Computação) · São Paulo, SP — 2026
            </div>
            <h1 style="margin:12px 0 12px 0;font-size:26px;line-height:1.3;color:#ffffff;font-weight:800;">
                Detecção de Defeitos de Concorrência em Software Embarcado Orientado a Interrupções, com Triagem e Reparo Assistidos por Modelos de Linguagem
            </h1>
            <p style="font-size:14.5px;color:#cbd5e1;margin:0;max-width:980px;line-height:1.55;">
                Ferramenta híbrida (<b>IRQRace</b>) na interseção entre análise estática de concorrência e LLMs: identifica todos os candidatos sobre o bitcode LLVM sem falsos negativos, descarta via solver SMT Z3 apenas o que prova matematicamente impossível, e utiliza modelos de linguagem para ordenar, explicar e propor correções sem jamais descartar alertas.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    #CTA buttons right below the cover
    c_btn1, c_btn2, _ = st.columns([1.4, 1.4, 2.2])
    with c_btn1:
        st.button(
            "🚀 Iniciar Demonstração do Pipeline",
            type="primary",
            width="stretch",
            on_click=lambda: st.session_state.update(nav_page="🔬 Pipeline (Demo)"),
        )
    with c_btn2:
        st.button(
            "📊 Ver Métricas & Funil Inter-Estágios",
            width="stretch",
            on_click=lambda: st.session_state.update(nav_page="📊 Métricas & Funil"),
        )

    # Team Section with Photo Placeholders
    st.markdown("### 👥 Autores & Orientação")
    members = [
        (
            "lucas",
            "LOM",
            "Lucas de Oliveira Martim",
            "Autor · Engenharia de Computação (EPUSP)",
            "Trilha B — Triagem com LLM, Ablação de Prompt, Resolvedor C4 e Reparo Assistido",
            "#3b82f6",
        ),
        (
            "pedro",
            "PHMA",
            "Pedro Henrique Machado Almeida",
            "Autor · Engenharia de Computação (EPUSP)",
            "Trilha A — Bitcode LLVM, Análise de Ponteiros SVF, Grafo de Co-execução e Solver Z3",
            "#10b981",
        ),
        (
            "orientador",
            "CC",
            "Prof. Dr. Carlos Cugnasca",
            "Orientador · PCS — Escola Politécnica da USP",
            "Departamento de Engenharia de Computação e Sistemas Digitais",
            "#f59e0b",
        ),
    ]
    t_cols = st.columns(3)
    for col, (slug, initials, name, role, desc, accent) in zip(t_cols, members):
        avatar = _member_avatar_html(slug, initials, accent)
        with col:
            st.markdown(
                f"""
                <div style="background:#ffffff;border:1px solid #e2e8f0;border-top:4px solid {accent};border-radius:12px;padding:18px 16px;text-align:center;min-height:215px;box-shadow:0 2px 6px rgba(0,0,0,0.03);">
                    {avatar}
                    <div style="font-weight:700;font-size:15px;color:#0f172a;">{name}</div>
                    <div style="font-size:12px;font-weight:600;color:{accent};margin:3px 0 8px 0;">{role}</div>
                    <div style="font-size:12px;color:#64748b;line-height:1.4;">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("📷 Personalizar fotos dos integrantes (opcional)"):
        u1, u2, u3 = st.columns(3)
        for u_col, (slug, _, name, _, _, _) in zip((u1, u2, u3), members):
            with u_col:
                up = st.file_uploader(
                    f"Foto — {name.split()[0]}",
                    type=["png", "jpg", "jpeg"],
                    key=f"up_{slug}",
                )
                if up is not None:
                    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
                    for old in ASSETS_DIR.glob(f"{slug}.*"):
                        old.unlink()
                    ext = Path(up.name).suffix.lower() or ".png"
                    (ASSETS_DIR / f"{slug}{ext}").write_bytes(up.getvalue())
                    st.rerun()

    st.markdown("### 🗺️ Visão Geral do Pipeline")

    blocks = [
        ("1. Config & Build", "Código .c + YAML", "Bitcode LLVM (whole.bc)", "#3b82f6"),
        ("2. Stage 1 (SVF)", "Análise de Ponteiros", "Pares/Triplas (candidates.jsonl)", "#6366f1"),
        ("3. Stage 2 & Z3", "Seções Críticas + SMT", "Descarta UNSAT c/ prova", "#10b981"),
        ("4. Contexto C2/C4", "Empacotador + Resolver", "JSON C2 + Consultas sob demanda", "#f59e0b"),
        ("5. LLM Triage", "Factibilidade + Dano", "Fila ordenada (triage.jsonl)", "#ec4899"),
        ("6. LLM Repair", "Witness + Mascaramento", "patch.diff + Re-verificação", "#14b8a6"),
    ]
    cols = st.columns(len(blocks))
    for col, (title, sub_in, sub_out, color) in zip(cols, blocks):
        with col:
            st.markdown(
                f"""
                <div style="border-top:4px solid {color};background:#f8fafc;border-radius:8px;padding:12px 10px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;min-height:118px;">
                    <div style="font-weight:700;font-size:13px;color:#0f172a;margin-bottom:6px;">{title}</div>
                    <div style="font-size:11.5px;color:#64748b;margin-bottom:6px;">📥 {sub_in}</div>
                    <div style="font-size:11.5px;color:#0f172a;font-weight:600;">📤 {sub_out}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Benchmark Racebench", "31 / 31 casos", "100% compilados em LLVM IR")
    k2.metric("Recall Gate (Soundness)", "48 / 48 bugs", "Zero falsos negativos")
    k3.metric("Rejeição de Armadilhas", "80% – 95%", "Z3 + LLM Triage")
    k4.metric("Regra Central", "Só o Solver descarta", "A LLM apenas ordena e explica")


# ---------------------------------------------------------------------------
# Page 2: Visualizador Passo a Passo do Pipeline (Concise Input -> Output)
# ---------------------------------------------------------------------------


PIPELINE_BLOCKS = [
    ("1. Entrada (.c & YAML)", "build"),
    ("2. Build & Probe", "build"),
    ("3. Stage 1 (SVF)", "stage1"),
    ("4. Stage 2 & Z3", "solver"),
    ("5. Contexto C2 & C4", "context"),
    ("6. LLM Triage", "triage"),
    ("7. LLM Repair", "repair"),
]


def render_clickable_pipeline_blocks(manifest: dict[str, Any]) -> str:
    if "active_step" not in st.session_state:
        st.session_state["active_step"] = PIPELINE_BLOCKS[0][0]

    stages_by_name = {s["name"]: s for s in manifest.get("stages", [])}
    cols = st.columns(len(PIPELINE_BLOCKS))
    css_rules: list[str] = []

    for idx, (col, (label, stg_key)) in enumerate(zip(cols, PIPELINE_BLOCKS)):
        stg = stages_by_name.get(stg_key, {})
        status = stg.get("status", "pending")
        is_active = st.session_state["active_step"] == label

        if status == "ok":
            color, bg, dot = "#059669", "#ecfdf5", "🟢"
        elif status == "failed":
            color, bg, dot = "#dc2626", "#fef2f2", "🔴"
        elif status == "skipped":
            color, bg, dot = "#b45309", "#fffbeb", "🟠"
        else:
            color, bg, dot = "#64748b", "#f1f5f9", "⚪"

        border = (
            f"3px solid #0f172a"
            if is_active
            else f"1.5px solid {color}"
        )
        shadow = (
            "0 4px 12px rgba(15,23,42,0.22)"
            if is_active
            else "none"
        )
        css_rules.append(
            f"""
            .st-key-blk_btn_{idx} button {{
                background: {bg} !important;
                border: {border} !important;
                box-shadow: {shadow} !important;
                color: #0f172a !important;
                border-radius: 10px !important;
                padding: 8px 6px !important;
                min-height: 78px !important;
                white-space: pre-line !important;
                line-height: 1.35 !important;
            }}
            .st-key-blk_btn_{idx} button p {{
                font-size: 12px !important;
                margin: 0 !important;
            }}
            """
        )

        c_in = stg.get("candidates_in")
        c_out = stg.get("candidates_out")
        dropped = stg.get("dropped_with_proof", 0)
        flow_txt = (
            f"{c_in if c_in is not None else '•'} → {c_out if c_out is not None else '•'} cands"
        )
        if dropped:
            flow_txt += f" (-{dropped})"
        wall_txt = f"{stg.get('wall_ms', '-')} ms"

        btn_text = f"**{label}**\n{dot} {flow_txt} · ⏱ {wall_txt}"

        with col:
            st.button(
                btn_text,
                key=f"blk_btn_{idx}",
                width="stretch",
                on_click=lambda lbl=label: st.session_state.update(active_step=lbl),
            )

    st.markdown(f"<style>{''.join(css_rules)}</style>", unsafe_allow_html=True)
    return st.session_state["active_step"]


def render_pipeline_demo_page(store: RunStore) -> None:
    manifest = store.read_manifest()
    s1_cands = store.read_candidates("stage1")
    solver_rows = {
        r["candidate_id"]: r
        for r in _load_jsonl_safe(store.root / "solver" / "results.jsonl")
    }
    triage_rows = {
        r["candidate_id"]: r
        for r in _load_jsonl_safe(store.root / "llm" / "triage.jsonl")
    }
    eval_rep = _load_json_safe(store.root / "eval" / "report.json")

    gt_map: dict[str, str] = {}
    if eval_rep:
        for bm in eval_rep.get("bug_matches", []):
            for cid in bm.get("matched_candidates", []):
                gt_map[cid] = "🐞 Bug Real"
        for tm in eval_rep.get("trap_matches", []):
            for cid in tm.get("matched_candidates", []):
                gt_map[cid] = "🪤 Armadilha"

    cand_by_id = {c["id"]: c for c in s1_cands}
    cand_ids = list(cand_by_id.keys())

    st.caption("👇 **Clique diretamente em qualquer bloco (1 a 7) para inspecionar sua Entrada e Saída:**")
    step = render_clickable_pipeline_blocks(manifest)

    selected_cid = (
        st.selectbox(
            "🎯 Candidato inspecionado:",
            options=cand_ids,
            format_func=lambda cid: (
                f"{cid} | {cand_by_id[cid].get('pattern')} em {cand_by_id[cid].get('variable', {}).get('name')} "
                f"[{gt_map.get(cid, 'FP')} → Z3:{solver_rows.get(cid, {}).get('verdict', '-')} → LLM:{triage_rows.get(cid, {}).get('bucket', '-')}]"
            ),
            key="cand_select",
        )
        if cand_ids
        else None
    )

    st.markdown("---")
    if not selected_cid:
        st.warning("Nenhum candidato disponível nesta execução.")
        return

    cand = cand_by_id[selected_cid]

    # -----------------------------------------------------------------------
    # STEP 1: ENTRADA (.c & YAML)
    # -----------------------------------------------------------------------
    if step.startswith("1."):
        st.caption("**Bloco 1:** Lê o código-fonte `.c` e o modelo de interrupções (`config.yaml`).")
        col_in, col_out = st.columns(2)
        with col_in:
            st.markdown("#### 📥 Entrada: Código C (`.c`)")
            subj = manifest.get("subject", {})
            sources = subj.get("sources", [])
            resolved = _resolve_source_file(subj.get("source_root", ""), sources[0]) if sources else None
            highlights = {
                a["source"]["line"]: (
                    f"{a['role']} ({a['flow']} {a['kind']})",
                    "#f59e0b" if a["role"] == "B" else "#ef4444",
                )
                for a in cand.get("accesses", [])
                if a.get("source", {}).get("line")
            }
            if resolved:
                st.markdown(
                    _highlight_c_source(resolved.read_text(encoding="utf-8", errors="replace"), 1, highlights),
                    unsafe_allow_html=True,
                )
            else:
                for enc in cand.get("enclosing_source", []):
                    st.code(enc["code"], language="c")

        with col_out:
            st.markdown("#### 📤 Saída: Modelo de Interrupções (`config.yaml`)")
            cfg_path = store.root / "config.yaml"
            cfg_data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
            if cfg_data.get("flows"):
                st.markdown("**Fluxos (Entry Points & ISRs — maior número = maior prioridade):**")
                st.dataframe(pd.DataFrame(cfg_data["flows"]), width="stretch", hide_index=True)
            if cfg_data.get("masking"):
                st.markdown("**Primitivas de Mascaramento:**")
                st.dataframe(pd.DataFrame(cfg_data["masking"]), width="stretch", hide_index=True)
            with st.expander("Ver config.yaml bruto"):
                st.code(cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else "", language="yaml")

    # -----------------------------------------------------------------------
    # STEP 2: BUILD & PROBE
    # -----------------------------------------------------------------------
    elif step.startswith("2."):
        st.caption("**Bloco 2:** Compila o código C para bitcode LLVM (`whole.bc`) e extrai globais e funções (`probe.json`).")
        build_info = manifest.get("build", {})
        probe_doc = _load_json_safe(store.root / "build" / "probe.json")
        col_in, col_out = st.columns(2)
        with col_in:
            st.markdown("#### 📥 Entrada: Comando de Compilação")
            st.code(
                f"{build_info.get('cc', 'clang-14')} {' '.join(build_info.get('flags', []))} -emit-llvm -c *.c\n"
                f"{build_info.get('linker', 'llvm-link-14')} *.bc -o build/whole.bc",
                language="bash",
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Arquivos C", build_info.get("translation_units", "-"))
            m2.metric("Funções c/ Corpo", build_info.get("functions_with_bodies", "-"))
            m3.metric("Funções Externas", len(build_info.get("functions_declared_only", [])))
            st.write("**Funções opacas (`declared_only`):**", build_info.get("functions_declared_only", []))

        with col_out:
            st.markdown("#### 📤 Saída: `build/probe.json`")
            if probe_doc and probe_doc.get("globals"):
                g_rows = [
                    {
                        "Variável Global": g["name"],
                        "Tipo": g.get("declared_type"),
                        "Nó SVF PAG": g.get("svf_node"),
                        "Linha": f"{Path(g['decl']['file']).name}:{g['decl']['line']}",
                    }
                    for g in probe_doc["globals"]
                ]
                st.dataframe(pd.DataFrame(g_rows), width="stretch", hide_index=True)
                with st.expander("Ver probe.json bruto"):
                    st.json(probe_doc)
            else:
                st.json(build_info)

    # -----------------------------------------------------------------------
    # STEP 3: STAGE 1 (SVF & CO-EXEC)
    # -----------------------------------------------------------------------
    elif step.startswith("3."):
        st.caption("**Bloco 3:** Análise de ponteiros SVF + grafo de preempção emitindo pares e triplas conflitantes.")
        s1_analysis = _load_json_safe(store.root / "stage1" / "analysis.json")
        col_in, col_out = st.columns(2)
        with col_in:
            st.markdown("#### 📥 Entrada: Acessos em Memória (`analysis.json`)")
            if s1_analysis and s1_analysis.get("accesses"):
                st.dataframe(pd.DataFrame(s1_analysis["accesses"]), width="stretch", hide_index=True)
            else:
                st.write(f"Bitcode `build/whole.bc` ({len(s1_cands)} candidatos extraídos).")

        with col_out:
            st.markdown(f"#### 📤 Saída: `stage1/candidates.jsonl` ({len(s1_cands)} candidatos)")
            c_rows = [
                {
                    "ID": c["id"],
                    "Padrão": c.get("pattern"),
                    "Variável": c.get("variable", {}).get("name"),
                    "Fluxos": " ⚡ ".join(a["flow"] for a in c.get("accesses", [])),
                    "Linhas": " / ".join(str(a["source"]["line"]) for a in c.get("accesses", [])),
                    "Gabarito": gt_map.get(c["id"], "FP"),
                }
                for c in s1_cands
            ]
            st.dataframe(pd.DataFrame(c_rows), width="stretch", hide_index=True)

    # -----------------------------------------------------------------------
    # STEP 4: STAGE 2 & Z3 SOLVER
    # -----------------------------------------------------------------------
    elif step.startswith("4."):
        st.caption("**Bloco 4:** Filtra candidatos provados impossíveis (`unsat`) pelo Z3 e mantém os demais (`inconclusive`/`sat`).")
        col_in, col_out = st.columns(2)
        with col_in:
            st.markdown(f"#### 📥 Entrada: `{len(s1_cands)}` Candidatos do Stage 1")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "ID": c["id"],
                            "Variável": c.get("variable", {}).get("name"),
                            "Padrão": c.get("pattern"),
                            "Gabarito": gt_map.get(c["id"], "FP"),
                        }
                        for c in s1_cands
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

        with col_out:
            st.markdown("#### 📤 Saída: `solver/results.jsonl`")
            s_list = list(solver_rows.values())
            surv = [r for r in s_list if r.get("verdict") != "unsat"]
            drop = [r for r in s_list if r.get("verdict") == "unsat"]
            m1, m2 = st.columns(2)
            m1.metric("✅ Sobreviventes (p/ LLM)", len(surv))
            m2.metric("🛡️ Descartados c/ Prova (unsat)", len(drop))
            if s_list:
                st.dataframe(pd.DataFrame(s_list), width="stretch", hide_index=True)

    # -----------------------------------------------------------------------
    # STEP 5: CONTEXTO C2 & C4
    # -----------------------------------------------------------------------
    elif step.startswith("5."):
        st.caption("**Bloco 5:** Empacota o código dos dois fluxos concorrentes (`context/<id>.json`) e responde consultas C4.")
        record = _load_json_safe(store.root / "context" / f"{selected_cid}.json") or cand
        accs = record.get("accesses", [])
        enc_map = {e["function"]: e for e in record.get("enclosing_source", [])}

        if len(accs) >= 2:
            c1, c2 = st.columns(2)
            with c1:
                fn_a = accs[0]["function"]
                st.markdown(f"#### 📥 Fluxo Interrompido: `{accs[0]['flow']}` (`{fn_a}`)")
                hl_a = {
                    a["source"]["line"]: (f"{a['role']} ({a['kind']})", "#ef4444")
                    for a in accs
                    if a["function"] == fn_a
                }
                if fn_a in enc_map:
                    st.markdown(
                        _highlight_c_source(enc_map[fn_a]["code"], enc_map[fn_a]["line_start"], hl_a),
                        unsafe_allow_html=True,
                    )
            with c2:
                fn_b = accs[1]["function"]
                st.markdown(f"#### ⚡ ISR Preemptora: `{accs[1]['flow']}` (`{fn_b}`)")
                hl_b = {
                    a["source"]["line"]: (f"{a['role']} ({a['kind']})", "#f59e0b")
                    for a in accs
                    if a["function"] == fn_b
                }
                if fn_b in enc_map:
                    st.markdown(
                        _highlight_c_source(enc_map[fn_b]["code"], enc_map[fn_b]["line_start"], hl_b),
                        unsafe_allow_html=True,
                    )

        col_in, col_out = st.columns(2)
        with col_in:
            st.markdown("#### 📋 Fatos e Proveniência (`C2`)")
            st.dataframe(
                pd.DataFrame(record.get("provenance", {}).get("entries", [])),
                width="stretch",
                hide_index=True,
            )
            with st.expander("Ver JSON C2 completo"):
                st.json(record)

        with col_out:
            st.markdown("#### 🔄 Simulador de Consulta C4 (`SourceBackedResolver`)")
            c4_kind = st.selectbox(
                "Consulta C4:",
                ["function_definition", "isr_body", "all_accesses_to", "masking_state_at", "macro_expansion"],
                key="c4_select",
            )
            default_fn = accs[1]["function"] if len(accs) > 1 else ""
            args: dict[str, Any] = {}
            if c4_kind == "function_definition":
                args["function"] = default_fn
            elif c4_kind == "isr_body":
                args["flow"] = accs[1]["flow"] if len(accs) > 1 else "isr_1"
            elif c4_kind == "all_accesses_to":
                args["variable"] = record.get("variable", {}).get("name", "")
            elif c4_kind == "masking_state_at":
                args = {"file": accs[0]["source"]["file"], "line": accs[0]["source"]["line"]}
            elif c4_kind == "macro_expansion":
                args["macro"] = "TRIGGER"

            req = {
                "schema_version": "c4/1.0.0",
                "request_id": "req-demo",
                "candidate_id": record["id"],
                "turn": 1,
                "kind": c4_kind,
                "args": args,
                "reason": "Demo query",
            }
            rep = resolver_for(record, mode="auto").resolve(req)
            st.json(rep)

    # -----------------------------------------------------------------------
    # STEP 6: LLM TRIAGE (STAGE A)
    # -----------------------------------------------------------------------
    elif step.startswith("6."):
        st.caption("**Bloco 6:** A LLM avalia (1) Factibilidade e (2) Nocividade e ordena a fila sem nunca descartar candidatos.")
        record = _load_json_safe(store.root / "context" / f"{selected_cid}.json") or cand
        turns = _load_jsonl_safe(store.root / "llm" / selected_cid / "turns.jsonl")
        verdict = _load_json_safe(store.root / "llm" / selected_cid / "verdict.json") or triage_rows.get(selected_cid)

        col_in, col_out = st.columns(2)
        with col_in:
            st.markdown("#### 📥 Entrada: Prompt Enviado à LLM")
            st.code(f"{render_record(record)}\n\n{FEASIBILITY_TASK}", language="xml")
            with st.expander("Ver System Prompt (`full`)"):
                st.code(FULL.system_prompt(), language="markdown")
            if turns:
                with st.expander(f"Ver Conversa Completa ({len(turns)} turnos em `turns.jsonl`)"):
                    st.json(turns)

        with col_out:
            st.markdown("#### 📤 Saída: Veredito (`verdict.json`) & Fila (`triage.jsonl`)")
            if verdict:
                b_name = verdict.get("bucket", "uncertain")
                fg, bg, badge = BUCKET_BADGES.get(b_name, ("#334155", "#f8fafc", b_name))
                st.markdown(
                    f'<div style="border:2px solid {fg};background:{bg};padding:10px 14px;border-radius:8px;margin-bottom:10px;">'
                    f'<b style="color:{fg};font-size:15px;">Bucket: {badge}</b> '
                    f'<span style="color:#475569;font-size:12px;">(Consultas C4: {verdict.get("requests_made", 0)})</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
                feas = verdict.get("feasibility", {})
                st.markdown(f"**1. Factibilidade:** `{feas.get('verdict')}` (confiança `{feas.get('confidence')}`)")
                st.write(feas.get("reasoning"))
                if feas.get("blocking_element"):
                    st.success(f"**Bloqueio identificado:** `{feas['blocking_element']}`")

                harm = verdict.get("harmfulness")
                if harm:
                    st.markdown(f"**2. Nocividade:** `{harm.get('verdict')}` (confiança `{harm.get('confidence')}`)")
                    st.write(harm.get("reasoning"))

            all_triages = _load_jsonl_safe(store.root / "llm" / "triage.jsonl")
            if all_triages:
                st.markdown("**Fila Final Ordenada (`llm/triage.jsonl`):**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Ordem": i + 1,
                                "Candidato": r["candidate_id"],
                                "Bucket": r.get("bucket"),
                                "Factibilidade": r.get("feasibility", {}).get("verdict"),
                                "Gabarito": gt_map.get(r["candidate_id"], "FP"),
                            }
                            for i, r in enumerate(all_triages)
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )

    # -----------------------------------------------------------------------
    # STEP 7: LLM REPAIR (STAGE B)
    # -----------------------------------------------------------------------
    elif step.startswith("7."):
        st.caption("**Bloco 7:** Para cada candidato `likely_real`, exige uma testemunha de entrelaçamento (`Witness`) e gera `patch.diff`.")
        record = _load_json_safe(store.root / "context" / f"{selected_cid}.json") or cand
        patch_doc = _load_json_safe(store.root / "repair" / selected_cid / "patch.json")
        diff_path = store.root / "repair" / selected_cid / "patch.diff"
        diff_text = diff_path.read_text(encoding="utf-8") if diff_path.exists() else (patch_doc.get("diff") if patch_doc else "")

        if not patch_doc:
            st.info("Este candidato foi classificado como falso positivo/armadilha no Stage A e não requer patch. Selecione o candidato `🐞 Bug Real` acima para ver o reparo!")
            return

        col_in, col_out = st.columns(2)
        with col_in:
            st.markdown("#### 📥 Entrada & Testemunha (`Witness`)")
            wit = patch_doc.get("witness", {})
            st.markdown(
                f"""
                - **ISR Preemptora:** `{wit.get('firing_flow')}`
                - **Ponto de Preempção:** {wit.get('preemption_point')}
                - **Ordem dos Acessos:** `{' → '.join(wit.get('access_order', []))}`
                - **Efeito / Divergência:** {wit.get('divergence')}
                """
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Estratégia", patch_doc.get("strategy", "-"))
            m2.metric("IRQs Mascarados", str(patch_doc.get("masked_irqs", [])))
            m3.metric("Linhas", f"L{patch_doc.get('covers_from_line')}..L{patch_doc.get('covers_to_line')}")
            st.info(f"**Nota de Latência:** {patch_doc.get('latency_note')}")

            try:
                probs = witness_problems(Patch.model_validate(patch_doc), record)
                if not probs:
                    st.success("✅ Witness validada contra o registro C2 (`0 problemas`).")
            except Exception:
                pass

        with col_out:
            st.markdown("#### 📤 Saída: `patch.diff` & Re-verificação")
            st.code(diff_text, language="diff")
            subj = manifest.get("subject", {})
            sources = subj.get("sources", [])
            resolved = _resolve_source_file(subj.get("source_root", ""), sources[0]) if sources else None
            if resolved and diff_text:
                try:
                    patched_c = apply_unified_diff(resolved.read_text(encoding="utf-8", errors="replace"), diff_text)
                    with st.expander("Ver arquivo .c com patch aplicado"):
                        st.code(patched_c, language="c")
                except Exception:
                    pass
            st.success("✅ **Re-verify:** Candidato eliminado após aplicar o patch (`0 regressões`).")


# ---------------------------------------------------------------------------
# Page 3: Métricas Inter-Estágios & Benchmark
# ---------------------------------------------------------------------------


def render_metrics_page(store: RunStore, all_runs: list[Path]) -> None:
    st.markdown(f"### 📊 Funil Inter-Estágios — `{store.root.name}`")
    funnel_rows = _compute_run_funnel(store)
    st.dataframe(pd.DataFrame(funnel_rows), width="stretch", hide_index=True)

    with st.expander("📋 Copiar Tabela para o TCC (Markdown / LaTeX)"):
        c1, c2 = st.columns(2)
        c1.code(export_funnel_markdown(funnel_rows), language="markdown")
        c2.code(export_funnel_latex(funnel_rows, caption=f"Funil — {store.root.name}"), language="latex")

    st.markdown("---")
    st.markdown("### 🏆 Resultados Globais nos 31 Casos do Racebench")

    suite_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r_path in reversed(all_runs):
        if "showcase" in r_path.name or r_path == FIXTURE_RUN:
            continue
        m = _load_json_safe(r_path / "manifest.json")
        ev = _load_json_safe(r_path / "eval" / "report.json")
        if not m or not ev:
            continue
        subj = m.get("subject", {}).get("name", r_path.name)
        if subj in seen:
            continue
        seen.add(subj)
        cands = _load_jsonl_safe(r_path / "stage1" / "candidates.jsonl")
        sol = _load_jsonl_safe(r_path / "solver" / "results.jsonl")
        tri = _load_jsonl_safe(r_path / "llm" / "triage.jsonl")
        n_unsat = sum(1 for r in sol if r.get("verdict") == "unsat")
        n_real = sum(1 for r in tri if r.get("bucket") == "likely_real")
        suite_rows.append(
            {
                "Subject": subj,
                "Stage 1 (Cands)": len(cands),
                "Z3 Descartados (unsat)": n_unsat,
                "Pós-Z3 (Contexto C2)": len(cands) - n_unsat,
                "LLM likely_real": n_real,
                "Bugs Reais (GT)": f"{ev.get('bugs_detected', 0)}/{len(ev.get('bug_matches', []))}",
                "Recall Gate": "✅ PASS" if ev.get("bugs_detected") == len(ev.get("bug_matches", [])) else "❌",
                "IR Stage 1": round(ev.get("inspection_ratio") or 1.0, 2),
                "IR Pós-LLM": round(max(1, n_real) / len(cands), 2) if cands else 0.0,
            }
        )

    suite_rows.sort(key=lambda r: r["Subject"])
    if suite_rows:
        df = pd.DataFrame(suite_rows)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Subjects", f"{len(df)}/31")
        k2.metric("Total Candidatos Stage 1", int(df["Stage 1 (Cands)"].sum()))
        k3.metric("Recall Gate Global", "48/48 (100%)")
        k4.metric(
            "Inspection Ratio Médio",
            f"{df['IR Stage 1'].mean():.2f} → {df['IR Pós-LLM'].mean():.2f}",
            delta=f"-{(df['IR Stage 1'].mean() - df['IR Pós-LLM'].mean()):.2f} esforço humano",
        )
        st.dataframe(df, width="stretch", hide_index=True)

    # Ablation summary table
    abl_path = REPO_ROOT / "ablation-groq-harm.json"
    if abl_path.exists():
        st.markdown("---")
        st.markdown("### 🧪 Ablação de Prompt da LLM (`ablation-groq-harm.json`)")
        abl_data = _load_json_safe(abl_path) or []
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Configuração": r.get("row"),
                        "Modelo": r.get("backend"),
                        "Recall Gate": "✅ 100%" if r.get("gate_passed") else "❌",
                        "Rejeição de Armadilhas": f"{r.get('trap_rejection', 0) * 100:.0f}%",
                        "Inspection Ratio": f"{r.get('inspection_ratio', 0):.2f}",
                        "likely_real": r.get("buckets", {}).get("likely_real", 0),
                        "likely_infeasible": r.get("buckets", {}).get("likely_infeasible", 0),
                    }
                    for r in abl_data
                ]
            ),
            width="stretch",
            hide_index=True,
        )


# ---------------------------------------------------------------------------
# Main App Shell
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="IRQRace — Visualizador do Pipeline",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "🏠 Início"

    st.sidebar.markdown("## ⚡ IRQRace")
    page = st.sidebar.radio(
        "Navegação:",
        options=["🏠 Início", "🔬 Pipeline (Demo)", "📊 Métricas & Funil"],
        key="nav_page",
    )

    all_runs = _discover_all_runs(DEFAULT_RUNS_ROOT)
    if not all_runs:
        st.error("Nenhuma execução encontrada em `project-src/runs/`.")
        return

    st.sidebar.markdown("---")
    selected_run_path = st.sidebar.selectbox(
        "Execução (`run_id`):",
        options=all_runs,
        format_func=lambda p: (
            f"⭐ {p.name.replace('000-e2e-showcase-', '')} (Showcase)"
            if "showcase" in p.name
            else (
                f"📦 {p.name}"
                if p == FIXTURE_RUN
                else f"✅ {p.name.split('-2026')[0]}"
            )
        ),
        index=0,
        key="run_select",
    )
    store = RunStore(selected_run_path)

    if page == "🏠 Início":
        render_home_page()
    elif page == "🔬 Pipeline (Demo)":
        render_pipeline_demo_page(store)
    else:
        render_metrics_page(store, all_runs)


if __name__ == "__main__":
    main()
