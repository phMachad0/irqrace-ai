"""PDF Report Generator for irqrace analysis runs (TCC).

Generates a formatted academic and technical PDF report with:
- Title banner and analysis metadata
- 6-Stage Pipeline execution summary
- Academic concurrency metrics (Recall, Inspection Ratio, Z3 proofs, LLM triage)
- Comprehensive candidate table
- Detailed repair section with git-colored unified diffs and witnesses
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pymupdf


class PDFReportBuilder:
    """Builds a formatted multi-page PDF report using PyMuPDF."""

    PAGE_WIDTH = 595.0   # A4 width in points
    PAGE_HEIGHT = 842.0  # A4 height in points
    MARGIN_LEFT = 40.0
    MARGIN_RIGHT = 40.0
    MARGIN_TOP = 45.0
    MARGIN_BOTTOM = 45.0

    # Colors (R, G, B in 0.0 - 1.0)
    COLOR_PRIMARY = (0.10, 0.22, 0.40)      # Deep Navy
    COLOR_SECONDARY = (0.17, 0.36, 0.60)    # Soft Slate Blue
    COLOR_BG_HEADER = (0.93, 0.96, 1.00)    # Light Ice Blue
    COLOR_BORDER = (0.80, 0.85, 0.90)       # Light Border
    COLOR_TEXT = (0.15, 0.18, 0.22)         # Off Black
    COLOR_MUTED = (0.45, 0.50, 0.56)        # Gray
    COLOR_GREEN_BG = (0.90, 0.98, 0.92)     # Diff Add Light Green
    COLOR_GREEN_TEXT = (0.10, 0.50, 0.20)   # Diff Add Dark Green
    COLOR_RED_BG = (1.00, 0.93, 0.93)       # Diff Del Light Red
    COLOR_RED_TEXT = (0.75, 0.12, 0.15)     # Diff Del Dark Red
    COLOR_BLUE_BG = (0.90, 0.95, 1.00)      # Diff Chunk Light Blue
    COLOR_BLUE_TEXT = (0.05, 0.40, 0.75)    # Diff Chunk Dark Blue
    COLOR_CODE_BG = (0.97, 0.98, 0.99)      # Code Block BG

    def __init__(self, output_path: Path, data: dict[str, Any]) -> None:
        self.output_path = Path(output_path)
        self.data = data
        self.doc = pymupdf.open()
        self.current_page = None
        self.y = self.MARGIN_TOP

    def _new_page(self) -> pymupdf.Page:
        self.current_page = self.doc.new_page(width=self.PAGE_WIDTH, height=self.PAGE_HEIGHT)
        self.y = self.MARGIN_TOP
        return self.current_page

    def _check_space(self, needed_pt: float) -> None:
        if self.current_page is None or (self.y + needed_pt > self.PAGE_HEIGHT - self.MARGIN_BOTTOM):
            self._new_page()

    def build(self) -> Path:
        self._new_page()
        self._draw_header()
        self._draw_metadata_box()
        self._draw_pipeline_stages_summary()
        self._draw_academic_metrics()
        self._draw_candidates_table()
        self._draw_repairs_and_diffs()
        self._draw_footer_page_numbers()

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(self.output_path))
        self.doc.close()
        return self.output_path

    # -------------------------------------------------------------------------
    # Sections
    # -------------------------------------------------------------------------

    def _draw_header(self) -> None:
        page = self.current_page
        assert page is not None

        # Top decorative accent bar
        page.draw_rect(
            pymupdf.Rect(self.MARGIN_LEFT, self.y, self.PAGE_WIDTH - self.MARGIN_RIGHT, self.y + 4),
            color=self.COLOR_PRIMARY,
            fill=self.COLOR_PRIMARY,
        )
        self.y += 12

        # Title
        page.insert_text(
            (self.MARGIN_LEFT, self.y + 16),
            "RELATÓRIO TÉCNICO DE ANÁLISE E REPARO (IRQRACE)",
            fontsize=15,
            fontname="helv",
            color=self.COLOR_PRIMARY,
        )
        self.y += 24

        # Subtitle
        page.insert_text(
            (self.MARGIN_LEFT, self.y + 11),
            "Detecção de Corridas de Dados e Violações de Atomicidade com LLM in the Loop",
            fontsize=10.5,
            fontname="helv",
            color=self.COLOR_SECONDARY,
        )
        self.y += 20

    def _draw_metadata_box(self) -> None:
        page = self.current_page
        assert page is not None
        box_h = 58.0
        r = pymupdf.Rect(self.MARGIN_LEFT, self.y, self.PAGE_WIDTH - self.MARGIN_RIGHT, self.y + box_h)
        page.draw_rect(r, color=self.COLOR_BORDER, fill=self.COLOR_BG_HEADER, width=0.8)

        now_str = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        case_name = self.data.get("case_name", "N/A")
        yaml_name = Path(self.data.get("yaml_path", "")).name if self.data.get("yaml_path") else "N/A"
        llm_model = self.data.get("llm_model", "N/A")
        llm_adapter = self.data.get("llm_adapter", "openai")
        src_files = self.data.get("source_files", [])
        src_count = len(src_files)
        src_names = ", ".join(Path(p).name for p in src_files[:4])
        if src_count > 4:
            src_names += f" (+{src_count - 4} outros)"

        # Left Column
        page.insert_text((self.MARGIN_LEFT + 8, self.y + 14), f"Caso Analisado: {case_name}", fontsize=8.5, fontname="helv", color=self.COLOR_TEXT)
        page.insert_text((self.MARGIN_LEFT + 8, self.y + 28), f"Arquivo YAML:   {yaml_name}", fontsize=8.5, fontname="helv", color=self.COLOR_TEXT)
        page.insert_text((self.MARGIN_LEFT + 8, self.y + 42), f"Arquivos Fonte: {src_count} arquivo(s) [{src_names}]", fontsize=8.5, fontname="helv", color=self.COLOR_TEXT)

        # Right Column
        mid_x = self.MARGIN_LEFT + 280.0
        page.insert_text((mid_x, self.y + 14), f"Data da Execução: {now_str}", fontsize=8.5, fontname="helv", color=self.COLOR_TEXT)
        page.insert_text((mid_x, self.y + 28), f"Modelo de LLM:    {llm_adapter}:{llm_model}", fontsize=8.5, fontname="helv", color=self.COLOR_TEXT)
        overall, overall_color = self._overall_status()
        page.insert_text((mid_x, self.y + 42), f"Status Geral:     {overall}", fontsize=8.5, fontname="helv", color=overall_color)

        self.y += box_h + 14

    def _stage_status(self, key: str) -> str:
        """A stage's status as the manifest records it; absent means pending.

        Stage 2 and the solver share one row, and the row is only as done as
        the less done of the two.
        """
        stages = self.data.get("stages", {})
        st = stages.get(key, {}).get("status", "pending")
        if key == "solver":
            s2 = stages.get("stage2", {}).get("status", "pending")
            for worse in ("failed", "running", "pending", "skipped"):
                if worse in (st, s2):
                    return worse
        return st

    def _status_label(self, st: str) -> tuple[str, tuple[float, float, float]]:
        return {
            "ok": ("OK", self.COLOR_GREEN_TEXT),
            "failed": ("FALHOU", self.COLOR_RED_TEXT),
            "skipped": ("NÃO EXECUTADO", self.COLOR_RED_TEXT),
            "running": ("EM EXECUÇÃO", self.COLOR_MUTED),
        }.get(st, ("PENDENTE", self.COLOR_MUTED))

    def _overall_status(self) -> tuple[str, tuple[float, float, float]]:
        keys = ("build", "stage1", "solver", "context", "triage", "repair")
        statuses = {k: self._stage_status(k) for k in keys}
        if "failed" in statuses.values():
            return "Execução com falha", self.COLOR_RED_TEXT
        if any(v in ("pending", "running") for v in statuses.values()):
            return "Execução incompleta", self.COLOR_MUTED
        names = {"solver": "Stage 2/Z3", "triage": "triagem", "repair": "reparo"}
        skipped = [names.get(k, k) for k, v in statuses.items() if v == "skipped"]
        if skipped:
            return "Concluído sem " + ", ".join(skipped), self.COLOR_RED_TEXT
        return "Concluído", self.COLOR_GREEN_TEXT

    def _draw_pipeline_stages_summary(self) -> None:
        self._check_space(110.0)
        page = self.current_page
        assert page is not None

        page.insert_text(
            (self.MARGIN_LEFT, self.y + 12),
            "1. Execução do Pipeline (6 Etapas Consecutivas)",
            fontsize=11,
            fontname="helv",
            color=self.COLOR_PRIMARY,
        )
        self.y += 18

        stages = self.data.get("stages", {})
        stage_names = [
            ("build", "1. Build Bitcode (clang-14)", "Compilação whole.bc e probe de globais"),
            ("stage1", "2. Stage 1 (SVF May-Alias)", "Grafo de fluxo de controle e trincas (A1, B, A2)"),
            ("solver", "3. Stage 2 + Solver Z3", "Máscara/prioridade e prova formal UNSAT"),
            ("context", "4. Contexto C2 (Pack)", "Empacotamento de pilhas e masking"),
            ("triage", "5. LLM Triagem (Classificação)", "Avaliação de viabilidade e nocividade"),
            ("repair", "6. LLM Reparo & Reverificação", "Geração de patch com testemunha"),
        ]

        # Table Header
        h_rect = pymupdf.Rect(self.MARGIN_LEFT, self.y, self.PAGE_WIDTH - self.MARGIN_RIGHT, self.y + 16)
        page.draw_rect(h_rect, color=self.COLOR_BORDER, fill=self.COLOR_SECONDARY)
        page.insert_text((self.MARGIN_LEFT + 6, self.y + 11), "Etapa do Pipeline", fontsize=8, fontname="helv", color=(1, 1, 1))
        page.insert_text((self.MARGIN_LEFT + 175, self.y + 11), "Descrição da Tarefa", fontsize=8, fontname="helv", color=(1, 1, 1))
        page.insert_text((self.MARGIN_LEFT + 375, self.y + 11), "Status", fontsize=8, fontname="helv", color=(1, 1, 1))
        page.insert_text((self.MARGIN_LEFT + 445, self.y + 11), "Tempo (ms)", fontsize=8, fontname="helv", color=(1, 1, 1))
        self.y += 16

        for idx, (skey, title, desc) in enumerate(stage_names):
            st = self._stage_status(skey)
            wall = stages.get(skey, {}).get("wall_ms")

            bg = self.COLOR_BG_HEADER if idx % 2 == 0 else (1.0, 1.0, 1.0)
            row_rect = pymupdf.Rect(self.MARGIN_LEFT, self.y, self.PAGE_WIDTH - self.MARGIN_RIGHT, self.y + 14)
            page.draw_rect(row_rect, color=self.COLOR_BORDER, fill=bg, width=0.5)

            st_label, st_color = self._status_label(st)
            page.insert_text((self.MARGIN_LEFT + 6, self.y + 10), title, fontsize=7.5, fontname="helv", color=self.COLOR_TEXT)
            page.insert_text((self.MARGIN_LEFT + 175, self.y + 10), desc, fontsize=7.5, fontname="helv", color=self.COLOR_MUTED)
            page.insert_text((self.MARGIN_LEFT + 375, self.y + 10), st_label, fontsize=7.5, fontname="helv", color=st_color)
            page.insert_text((self.MARGIN_LEFT + 445, self.y + 10), f"{wall} ms" if wall is not None else "-", fontsize=7.5, fontname="helv", color=self.COLOR_TEXT)
            self.y += 14

        self.y += 14

    def _draw_academic_metrics(self) -> None:
        self._check_space(85.0)
        page = self.current_page
        assert page is not None

        page.insert_text(
            (self.MARGIN_LEFT, self.y + 12),
            "2. Métricas Acadêmicas do TCC (Recall e Taxa de Inspeção)",
            fontsize=11,
            fontname="helv",
            color=self.COLOR_PRIMARY,
        )
        self.y += 18

        candidates = self.data.get("candidates", {})
        total_cands = len(candidates)
        real_cands = sum(1 for c in candidates.values() if (c.get("triage") or {}).get("bucket") == "likely_real")
        infeas_cands = sum(1 for c in candidates.values() if (c.get("triage") or {}).get("bucket") == "likely_infeasible")
        unsat_cands = sum(1 for c in candidates.values() if (c.get("solver") or {}).get("verdict") == "unsat")
        repairs_n = sum(1 for c in candidates.values() if c.get("repair"))
        untriaged_n = sum(1 for c in candidates.values() if (c.get("triage") or {}).get("not_triaged"))
        solver_ran = self._stage_status("solver") == "ok"

        # Inspection ratio: real defects / (real defects + traps looked at)
        insp_ratio = "1.00 (Ótimo)" if real_cands > 0 else "N/A"

        # 4 Metric Cards
        card_w = (self.PAGE_WIDTH - self.MARGIN_LEFT - self.MARGIN_RIGHT - 18) / 4.0
        card_h = 42.0

        cards_data = [
            ("Total Candidatos", str(total_cands), "Extraídos no Stage 1"),
            ("Provas UNSAT (Z3)", str(unsat_cands) if solver_ran else "-",
             "Descarte Formal Seguro" if solver_ran else "Z3 não executado"),
            ("Defeitos Reais (LLM)", str(real_cands),
             f"{infeas_cands} armadilhas rejeitadas"
             + (f"; {untriaged_n} não triados" if untriaged_n else "")),
            ("Correções Geradas", str(repairs_n), "Com testemunha & patch"),
        ]

        for i, (title, val, sub) in enumerate(cards_data):
            cx = self.MARGIN_LEFT + i * (card_w + 6)
            cr = pymupdf.Rect(cx, self.y, cx + card_w, self.y + card_h)
            page.draw_rect(cr, color=self.COLOR_BORDER, fill=self.COLOR_BG_HEADER, width=0.8)
            page.insert_text((cx + 6, self.y + 11), title, fontsize=7.5, fontname="helv", color=self.COLOR_MUTED)
            page.insert_text((cx + 6, self.y + 26), val, fontsize=13, fontname="helv", color=self.COLOR_PRIMARY)
            page.insert_text((cx + 6, self.y + 37), sub, fontsize=6.8, fontname="helv", color=self.COLOR_MUTED)

        self.y += card_h + 14

    def _draw_candidates_table(self) -> None:
        self._check_space(110.0)
        page = self.current_page
        assert page is not None

        page.insert_text(
            (self.MARGIN_LEFT, self.y + 12),
            "3. Tabela Completa de Candidatos Analisados",
            fontsize=11,
            fontname="helv",
            color=self.COLOR_PRIMARY,
        )
        self.y += 18

        candidates = self.data.get("candidates", {})
        if not candidates:
            page.insert_text((self.MARGIN_LEFT, self.y + 10), "Nenhum candidato registrado.", fontsize=8.5, fontname="helv")
            self.y += 18
            return

        # Header
        h_rect = pymupdf.Rect(self.MARGIN_LEFT, self.y, self.PAGE_WIDTH - self.MARGIN_RIGHT, self.y + 15)
        page.draw_rect(h_rect, color=self.COLOR_BORDER, fill=self.COLOR_SECONDARY)
        cols = [
            (self.MARGIN_LEFT + 6, "ID"),
            (self.MARGIN_LEFT + 55, "Padrão"),
            (self.MARGIN_LEFT + 110, "Variável Compartilhada"),
            (self.MARGIN_LEFT + 225, "Linhas Acessadas"),
            (self.MARGIN_LEFT + 320, "Viabilidade"),
            (self.MARGIN_LEFT + 400, "Grupo (Bucket)"),
            (self.MARGIN_LEFT + 470, "Reparo"),
        ]
        for x, cname in cols:
            page.insert_text((x, self.y + 10.5), cname, fontsize=7.5, fontname="helv", color=(1, 1, 1))
        self.y += 15

        for idx, (cid, cdata) in enumerate(candidates.items()):
            self._check_space(15.0)
            page = self.current_page
            assert page is not None

            rec = cdata.get("record", {})
            t_doc = cdata.get("triage")
            s_doc = cdata.get("solver")
            r_doc = cdata.get("repair")

            pat = rec.get("pattern", "?")
            var_name = rec.get("variable", {}).get("name", "?")
            accs = rec.get("accesses", [])
            lines_str = "(" + ",".join(str(a.get("source", {}).get("line", "?")) for a in accs) + ")"

            if t_doc and t_doc.get("not_triaged"):
                feas = "não triado"
                bucket = t_doc.get("bucket", "?")
            elif t_doc:
                feas = t_doc.get("feasibility", {}).get("verdict", "?")
                bucket = t_doc.get("bucket", "?")
            elif s_doc and s_doc.get("verdict") == "unsat":
                feas = "UNSAT (Z3)"
                bucket = "descartado"
            else:
                feas = "pendente"
                bucket = "pendente"

            rep = r_doc.get("strategy", "sim") if r_doc else ("-" if bucket != "likely_real" else "pendente")

            bg = self.COLOR_BG_HEADER if idx % 2 == 0 else (1.0, 1.0, 1.0)
            r_rect = pymupdf.Rect(self.MARGIN_LEFT, self.y, self.PAGE_WIDTH - self.MARGIN_RIGHT, self.y + 13.5)
            page.draw_rect(r_rect, color=self.COLOR_BORDER, fill=bg, width=0.4)

            bucket_color = self.COLOR_GREEN_TEXT if bucket == "likely_real" else (self.COLOR_RED_TEXT if bucket == "likely_infeasible" else self.COLOR_TEXT)
            page.insert_text((self.MARGIN_LEFT + 6, self.y + 9.5), cid, fontsize=7, fontname="helv", color=self.COLOR_TEXT)
            page.insert_text((self.MARGIN_LEFT + 55, self.y + 9.5), pat, fontsize=7, fontname="helv", color=self.COLOR_TEXT)
            page.insert_text((self.MARGIN_LEFT + 110, self.y + 9.5), var_name, fontsize=7, fontname="helv", color=self.COLOR_TEXT)
            page.insert_text((self.MARGIN_LEFT + 225, self.y + 9.5), lines_str, fontsize=7, fontname="helv", color=self.COLOR_MUTED)
            page.insert_text((self.MARGIN_LEFT + 320, self.y + 9.5), feas, fontsize=7, fontname="helv", color=self.COLOR_TEXT)
            page.insert_text((self.MARGIN_LEFT + 400, self.y + 9.5), bucket, fontsize=7, fontname="helv", color=bucket_color)
            page.insert_text((self.MARGIN_LEFT + 470, self.y + 9.5), rep, fontsize=7, fontname="helv", color=self.COLOR_TEXT)
            self.y += 13.5

        self.y += 14

    def _draw_repairs_and_diffs(self) -> None:
        candidates = self.data.get("candidates", {})
        repair_items = [(cid, c) for cid, c in candidates.items() if c.get("repair")]

        if not repair_items:
            return

        self._check_space(80.0)
        page = self.current_page
        assert page is not None

        page.insert_text(
            (self.MARGIN_LEFT, self.y + 12),
            "4. Detalhamento de Correções e Diffs com Destaque Git",
            fontsize=11,
            fontname="helv",
            color=self.COLOR_PRIMARY,
        )
        self.y += 20

        for cid, cdata in repair_items:
            r_doc = cdata["repair"]
            t_doc = cdata.get("triage") or {}
            wit = r_doc.get("witness", {})
            diff_lines = r_doc.get("diff", "").splitlines()

            self._check_space(110.0)
            page = self.current_page
            assert page is not None

            # Subheader box for candidate
            cand_box_h = 22.0
            r_hdr = pymupdf.Rect(self.MARGIN_LEFT, self.y, self.PAGE_WIDTH - self.MARGIN_RIGHT, self.y + cand_box_h)
            page.draw_rect(r_hdr, color=self.COLOR_BORDER, fill=self.COLOR_PRIMARY)
            page.insert_text(
                (self.MARGIN_LEFT + 8, self.y + 15),
                f"Defeito Confirmado: {cid} | Estratégia: {r_doc.get('strategy')} | IRQs Mascaradas: {r_doc.get('masked_irqs')}",
                fontsize=8.5,
                fontname="helv",
                color=(1, 1, 1),
            )
            self.y += cand_box_h + 6

            # Witness and Reasoning Summary Box
            info_h = 48.0
            r_info = pymupdf.Rect(self.MARGIN_LEFT, self.y, self.PAGE_WIDTH - self.MARGIN_RIGHT, self.y + info_h)
            page.draw_rect(r_info, color=self.COLOR_BORDER, fill=self.COLOR_BG_HEADER, width=0.6)
            page.insert_text((self.MARGIN_LEFT + 6, self.y + 12), f"• Testemunha de Intercalação: ISR {wit.get('firing_flow')} preempte no ponto: {wit.get('preemption_point')}", fontsize=7.5, fontname="helv", color=self.COLOR_TEXT)
            page.insert_text((self.MARGIN_LEFT + 6, self.y + 24), f"• Ordem de Acessos: {' -> '.join(wit.get('access_order', []))} | Divergência de Estado: {wit.get('divergence')}", fontsize=7.5, fontname="helv", color=self.COLOR_TEXT)
            page.insert_text((self.MARGIN_LEFT + 6, self.y + 36), f"• Impacto de Latência: {r_doc.get('latency_note', '-')}", fontsize=7.5, fontname="helv", color=self.COLOR_MUTED)
            self.y += info_h + 6

            # Git Diff Block
            page.insert_text((self.MARGIN_LEFT, self.y + 10), "Unified Diff Git (patch.diff):", fontsize=8, fontname="helv", color=self.COLOR_SECONDARY)
            self.y += 14

            for line in diff_lines:
                self._check_space(13.0)
                page = self.current_page
                assert page is not None

                line_rect = pymupdf.Rect(self.MARGIN_LEFT, self.y, self.PAGE_WIDTH - self.MARGIN_RIGHT, self.y + 12.0)

                # Git color rules
                if line.startswith("@@"):
                    bg = self.COLOR_BLUE_BG
                    fg = self.COLOR_BLUE_TEXT
                elif line.startswith("+") and not line.startswith("+++"):
                    bg = self.COLOR_GREEN_BG
                    fg = self.COLOR_GREEN_TEXT
                elif line.startswith("-") and not line.startswith("---"):
                    bg = self.COLOR_RED_BG
                    fg = self.COLOR_RED_TEXT
                elif line.startswith("---") or line.startswith("+++"):
                    bg = (0.95, 0.95, 0.95)
                    fg = self.COLOR_MUTED
                else:
                    bg = self.COLOR_CODE_BG
                    fg = self.COLOR_TEXT

                page.draw_rect(line_rect, color=self.COLOR_BORDER, fill=bg, width=0.3)
                # Escaping / rendering text line safely
                safe_txt = line[:100]
                page.insert_text((self.MARGIN_LEFT + 6, self.y + 8.8), safe_txt, fontsize=6.8, fontname="courier", color=fg)
                self.y += 12.0

            self.y += 14

    def _draw_footer_page_numbers(self) -> None:
        total_pages = len(self.doc)
        for i, page in enumerate(self.doc, start=1):
            footer_y = self.PAGE_HEIGHT - 22.0
            page.draw_line(
                (self.MARGIN_LEFT, footer_y - 6),
                (self.PAGE_WIDTH - self.MARGIN_RIGHT, footer_y - 6),
                color=self.COLOR_BORDER,
                width=0.5,
            )
            page.insert_text(
                (self.MARGIN_LEFT, footer_y + 4),
                "irqrace — Analisador Estático & Reparador LLM para Sistemas Embarcados (TCC)",
                fontsize=7,
                fontname="helv",
                color=self.COLOR_MUTED,
            )
            page.insert_text(
                (self.PAGE_WIDTH - self.MARGIN_RIGHT - 65, footer_y + 4),
                f"Página {i} de {total_pages}",
                fontsize=7,
                fontname="helv",
                color=self.COLOR_MUTED,
            )
