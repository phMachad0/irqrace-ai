"""The C1 configuration wizard of the desktop app (generic mode).

In generic mode the user never edits the C1 YAML by hand: either an existing
file is imported, or this wizard walks through the interrupt model -- sources,
flows, masking primitives, semantics -- and writes the file. Two halves:

* :class:`WizardState` and the code scanners are plain Python. They build the
  C1 dict, and :func:`validate_state` runs it through the same
  :meth:`Config.from_dict` the pipeline uses, so a file the wizard accepts is a
  file the pipeline accepts.
* :class:`ConfigWizard` is the Tk window, one page per section of the contract.

The defaults are the recall-safe ones the schema documents
(``contracts/c1-config.schema.json``); every page that offers an unsound choice
says so next to it. ``flows`` is the recall-critical field: a handler left out
contributes no accesses, and its defects become invisible with no error.
"""

from __future__ import annotations

import copy
import os
import re
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, Callable

import yaml

from irqrace.config import DEFAULTS, SCHEMA_VERSION, Config, ConfigError, _deep_merge, resolve_source_root

_C_KEYWORDS = {
    "if", "for", "while", "switch", "return", "sizeof", "do", "else", "case",
    "defined", "__attribute__", "asm", "__asm__", "typeof",
}
_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"' + r"|'(?:\\.|[^'\\])*'")
_FUNC_DEF_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(([^()]*)\)\s*\{")
_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")

#: Name shapes that suggest an interrupt handler or a masking primitive. They
#: only pre-fill the form; the user confirms every row.
_ISR_NAME_RE = re.compile(r"isr|irq_?handler|irqhandler|_handler$|interrupt", re.I)
_MASK_NAME_RE = re.compile(
    r"^(cli|sti)$|(disable|enable)_?(isr|irq|int|interrupt)s?|(isr|irq|int|interrupt)s?_?(disable|enable)",
    re.I,
)
_TASK_NAME_RE = re.compile(r"(^|_)main$|^main_|task", re.I)

FLOW_KINDS = ("task", "isr")
PRIMITIVE_EFFECTS = ("disable", "enable")
NON_CONSTANT_ARG = ("unknown", "all", "none")
INITIAL_STATES = ("all-enabled", "all-disabled", "unknown")
ISR_ARRIVAL = ("unbounded", "once-per-interval")
EXTERNALS_DEFAULT = ("may-read-write-reachable", "none")
EXTERNAL_EFFECTS = ("none", "reads-args", "writes-args", "reads-writes-args")


class WizardError(ValueError):
    """The wizard's answers do not make a usable configuration."""


# ---------------------------------------------------------------------------
# Scanning the sources
# ---------------------------------------------------------------------------


def _strip(text: str) -> str:
    return _STRING_RE.sub('""', _COMMENT_RE.sub(" ", text))


def scan_functions(paths: list[Path]) -> tuple[list[str], list[str]]:
    """(defined, called-but-not-defined) function names across *paths*.

    A regex scan, not a parse: it only feeds the comboboxes and the
    suggestions, and the user can type any name the scan missed.
    """
    defined: set[str] = set()
    called: set[str] = set()
    for p in paths:
        try:
            text = _strip(Path(p).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for m in _FUNC_DEF_RE.finditer(text):
            if m.group(1) not in _C_KEYWORDS:
                defined.add(m.group(1))
        for m in _CALL_RE.finditer(text):
            if m.group(1) not in _C_KEYWORDS:
                called.add(m.group(1))
    return sorted(defined), sorted(called - defined)


def suggest_flows(defined: list[str]) -> list[dict[str, Any]]:
    """One task for the main-like entry and one ISR per handler-like name."""
    flows: list[dict[str, Any]] = []
    tasks = [f for f in defined if _TASK_NAME_RE.search(f) and not _ISR_NAME_RE.search(f)]
    main = next((f for f in tasks if f == "main"), tasks[0] if tasks else None)
    if main:
        flows.append({"id": "main", "kind": "task", "entry": main, "irq": None, "priority": 0})
    isrs = [f for f in defined if _ISR_NAME_RE.search(f) and not _MASK_NAME_RE.search(f)]
    for n, fn in enumerate(isrs, start=1):
        flows.append({"id": f"isr_{n}", "kind": "isr", "entry": fn, "irq": n, "priority": n})
    return flows


def suggest_primitives(names: list[str]) -> list[dict[str, Any]]:
    out = []
    for fn in names:
        if not _MASK_NAME_RE.search(fn):
            continue
        low = fn.lower()
        effect = "disable" if ("disable" in low or low == "cli") else "enable"
        bare = low in ("cli", "sti")
        out.append({
            "function": fn, "effect": effect,
            "irq_arg": None if bare else 0, "all_value": None if bare else -1,
            "non_constant_arg": "unknown",
        })
    return out


# ---------------------------------------------------------------------------
# The state and its C1 form
# ---------------------------------------------------------------------------


def _rel(path: Path, base: Path) -> str:
    """*path* relative to *base* in POSIX form, or absolute across drives."""
    try:
        return Path(os.path.relpath(path, base)).as_posix()
    except ValueError:
        return path.as_posix()


@dataclass
class WizardState:
    name: str = ""
    sources: list[Path] = field(default_factory=list)
    defines: list[str] = field(default_factory=list)
    flows: list[dict[str, Any]] = field(default_factory=list)
    primitives: list[dict[str, Any]] = field(default_factory=list)
    initial_state: str = "all-enabled"
    isr_entry_masks_self: bool = False
    equal_priority_preemption: bool = True
    isr_arrival: str = "unbounded"
    isr_reentrant: bool = False
    nesting: bool = True
    externals_default: str = "may-read-write-reachable"
    external_models: list[dict[str, Any]] = field(default_factory=list)
    solver_timeout_ms: int = 120000
    #: The imported document, when editing: fields the wizard does not manage
    #: (analysis switches, output, ground truth) are carried over unchanged.
    base: dict[str, Any] = field(default_factory=dict)

    @property
    def c_files(self) -> list[Path]:
        return [p for p in self.sources if p.suffix.lower() == ".c"]

    @property
    def h_files(self) -> list[Path]:
        return [p for p in self.sources if p.suffix.lower() in (".h", ".hpp")]

    def to_c1(self, target: Path | None = None) -> dict[str, Any]:
        """The C1 document. Paths are written relative to *target*'s directory
        where possible, as ``bench/configs`` does, so the pair can be moved."""
        if not self.name.strip():
            raise WizardError("o projeto precisa de um nome")
        c_files = [p.resolve() for p in self.c_files]
        if not c_files:
            raise WizardError("nenhum arquivo .c foi selecionado")
        root = Path(os.path.commonpath([p.parent for p in c_files]))
        anchor = target.resolve().parent if target else None
        include_dirs: list[str] = []
        for p in [q.resolve() for q in self.h_files] + c_files:
            if str(p.parent) not in include_dirs:
                include_dirs.append(str(p.parent))

        carried = copy.deepcopy(self.base)
        doc: dict[str, Any] = {"schema_version": SCHEMA_VERSION}
        build: dict[str, Any] = {}
        build.update({
            "mode": "link" if len(c_files) > 1 else "single-tu",
            # build.py hands include_dirs to clang verbatim, so they stay absolute.
            "include_dirs": include_dirs,
            "defines": list(self.defines),
            "extra_bitcode": [],
        })
        doc["subject"] = {
            "name": self.name.strip(),
            "source_root": _rel(root, anchor) if anchor else str(root),
            "sources": [_rel(p, root) for p in c_files],
            "build": build,
        }
        doc["priority_convention"] = "larger-is-higher"
        doc["flows"] = [
            {"id": f["id"], "kind": f["kind"], "entry": f["entry"],
             "irq": f["irq"] if f["kind"] == "isr" else None,
             "priority": int(f["priority"]), "identified_by": "config"}
            for f in self.flows
        ]
        doc["masking"] = {
            "primitives": [dict(p) for p in self.primitives],
            "initial_state": self.initial_state,
            "isr_entry_masks_self": bool(self.isr_entry_masks_self),
        }
        doc["semantics"] = {
            "equal_priority_preemption": bool(self.equal_priority_preemption),
            "isr_arrival": self.isr_arrival,
            "isr_reentrant": bool(self.isr_reentrant),
            "nesting": bool(self.nesting),
            "timing_model": "unconstrained",
        }
        doc["externals"] = {
            "default": self.externals_default,
            "models": [{k: v for k, v in m.items() if v not in (None, "")} for m in self.external_models],
        }
        analysis = carried.pop("analysis", {})
        analysis.setdefault("solver", {})["timeout_ms"] = int(self.solver_timeout_ms)
        doc["analysis"] = analysis
        doc.update(carried)  # output, ground_truth
        doc.setdefault("ground_truth", {"kind": "none"})
        return doc

    @classmethod
    def from_c1(cls, raw: dict[str, Any], yaml_path: Path | None = None) -> "WizardState":
        """Pre-fill the wizard from an existing C1 file (for "Editar no assistente")."""
        raw = resolve_source_root(copy.deepcopy(raw), yaml_path)
        data = _deep_merge(DEFAULTS, raw)
        subject = data.get("subject", {})
        root = Path(subject.get("source_root") or (yaml_path.parent if yaml_path else "."))
        sources: list[Path] = []

        def _add(p: Path) -> None:
            p = p.resolve()
            if p not in sources:
                sources.append(p)

        for s in list(subject.get("sources", [])) + list(subject.get("build", {}).get("extra_bitcode", [])):
            p = Path(s) if Path(s).is_absolute() else root / s
            if p.is_dir():
                for q in sorted(p.rglob("*.c")):
                    _add(q)
            elif p.suffix.lower() == ".c" and p.exists():
                _add(p)
        for d in subject.get("build", {}).get("include_dirs", []) or []:
            if Path(d).is_dir():
                for h in sorted(Path(d).glob("*.h")):
                    _add(h)
        for c in [p for p in sources if p.suffix == ".c"]:
            for h in sorted(c.parent.glob("*.h")):
                _add(h)

        sem = data.get("semantics", {})
        mask = data.get("masking", {})
        ext = data.get("externals", {})
        return cls(
            name=str(subject.get("name", "")),
            sources=sources,
            defines=list(subject.get("build", {}).get("defines", []) or []),
            flows=[
                {"id": f["id"], "kind": f["kind"], "entry": f["entry"],
                 "irq": f.get("irq"), "priority": f.get("priority", 0)}
                for f in data.get("flows", [])
            ],
            primitives=[
                {"function": p["function"], "effect": p["effect"],
                 "irq_arg": p.get("irq_arg", 0), "all_value": p.get("all_value", -1),
                 "non_constant_arg": p.get("non_constant_arg", "unknown")}
                for p in mask.get("primitives", [])
            ],
            initial_state=mask.get("initial_state", "all-enabled"),
            isr_entry_masks_self=bool(mask.get("isr_entry_masks_self", False)),
            equal_priority_preemption=bool(sem.get("equal_priority_preemption", True)),
            isr_arrival=sem.get("isr_arrival", "unbounded"),
            isr_reentrant=bool(sem.get("isr_reentrant", False)),
            nesting=bool(sem.get("nesting", True)),
            externals_default=ext.get("default", "may-read-write-reachable"),
            external_models=[dict(m) for m in ext.get("models", [])],
            solver_timeout_ms=int(data.get("analysis", {}).get("solver", {}).get("timeout_ms", 120000)),
            base={k: v for k, v in raw.items() if k in ("analysis", "output", "ground_truth")},
        )


def validate_state(state: WizardState, target: Path | None = None) -> Config:
    """Build the document and load it exactly as the pipeline will."""
    doc = state.to_c1(target)
    try:
        return Config.from_dict(doc, path=target)
    except ConfigError:
        raise
    except Exception as e:  # contract violations arrive as their own error type
        raise ConfigError(str(e)) from e


def dump_c1(doc: dict[str, Any]) -> str:
    header = (
        "# Configuração C1 gerada pelo assistente do irqrace.\n"
        "# Para alterá-la, use \"Editar no assistente\" no modo genérico do app.\n"
    )
    return header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def save_c1(state: WizardState, target: Path) -> Config:
    cfg = validate_state(state, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dump_c1(state.to_c1(target)))
    return cfg


# ---------------------------------------------------------------------------
# The Tk window
# ---------------------------------------------------------------------------


def _int_or_none(text: str) -> int | None:
    text = text.strip()
    if text in ("", "-", "nenhum", "None", "null"):
        return None
    return int(text)


class ConfigWizard:
    """Modal, page-by-page wizard that ends by writing the C1 file."""

    PAGES = (
        ("Projeto", "Nome do projeto e arquivos-fonte"),
        ("Fluxos", "Tarefas e rotinas de interrupção (ISRs)"),
        ("Mascaramento", "Primitivas que habilitam/desabilitam interrupções"),
        ("Semântica", "Modelo do processador e funções externas"),
        ("Revisão", "Validar e salvar a configuração"),
    )

    def __init__(
        self,
        master: tk.Misc,
        state: WizardState,
        *,
        on_finish: Callable[[Path, list[Path]], None],
        target: Path | None = None,
    ) -> None:
        self.state = state
        self.on_finish = on_finish
        self.target_var = tk.StringVar(value=str(target) if target else "")
        self.defined: list[str] = []
        self.external: list[str] = []

        self.win = tk.Toplevel(master)
        self.win.title("Assistente de Configuração (C1)")
        self.win.geometry("940x640")
        self.win.minsize(820, 560)
        self.win.transient(master.winfo_toplevel())

        body = ttk.Frame(self.win, padding=8)
        body.pack(fill=tk.BOTH, expand=True)

        side = ttk.Frame(body, padding=(4, 4, 12, 4))
        side.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(side, text="Etapas", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))
        self.step_labels: list[ttk.Label] = []
        for i, (title, _) in enumerate(self.PAGES, start=1):
            lbl = ttk.Label(side, text=f"{i}. {title}", padding=(4, 3))
            lbl.pack(anchor=tk.W, fill=tk.X)
            self.step_labels.append(lbl)

        main = ttk.Frame(body)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.title_var = tk.StringVar()
        ttk.Label(main, textvariable=self.title_var, font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        ttk.Separator(main).pack(fill=tk.X, pady=6)
        self.page_host = ttk.Frame(main)
        self.page_host.pack(fill=tk.BOTH, expand=True)

        nav = ttk.Frame(main, padding=(0, 8, 0, 0))
        nav.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(nav, text="Cancelar", command=self.win.destroy).pack(side=tk.LEFT)
        self.btn_next = ttk.Button(nav, text="Avançar >", command=self._next)
        self.btn_next.pack(side=tk.RIGHT)
        self.btn_back = ttk.Button(nav, text="< Voltar", command=self._back)
        self.btn_back.pack(side=tk.RIGHT, padx=6)

        self.pages = [
            self._page_project(), self._page_flows(), self._page_masking(),
            self._page_semantics(), self._page_review(),
        ]
        self.index = 0
        self._rescan()
        self._show(0)
        self.win.grab_set()

    # -- navigation ------------------------------------------------------

    def _show(self, i: int) -> None:
        for p in self.pages:
            p.pack_forget()
        self.index = i
        self.pages[i].pack(fill=tk.BOTH, expand=True)
        title, sub = self.PAGES[i]
        self.title_var.set(f"{i + 1}/{len(self.PAGES)} — {title}: {sub}")
        for j, lbl in enumerate(self.step_labels):
            lbl.configure(font=("Segoe UI", 9, "bold" if j == i else "normal"),
                          foreground="" if j <= i else "gray")
        self.btn_back.configure(state=tk.NORMAL if i > 0 else tk.DISABLED)
        self.btn_next.configure(text="Salvar e usar ✔" if i == len(self.pages) - 1 else "Avançar >")
        if i == len(self.pages) - 1:
            self._refresh_review()

    def _back(self) -> None:
        if self.index > 0:
            self._show(self.index - 1)

    def _next(self) -> None:
        problem = self._check_page(self.index)
        if problem:
            messagebox.showerror("Corrija antes de avançar", problem, parent=self.win)
            return
        if self.index < len(self.pages) - 1:
            self._show(self.index + 1)
        else:
            self._finish()

    def _check_page(self, i: int) -> str | None:
        st = self.state
        if i == 0:
            st.name = self.name_var.get().strip()
            st.defines = [d.strip() for d in self.defines_var.get().split(",") if d.strip()]
            if not st.name:
                return "Informe um nome para o projeto."
            if not st.c_files:
                return "Adicione pelo menos um arquivo .c."
        elif i == 1:
            if not st.flows:
                return "Declare pelo menos um fluxo (a tarefa principal)."
            if not any(f["kind"] == "isr" for f in st.flows):
                if not messagebox.askyesno(
                    "Nenhuma ISR declarada",
                    "Nenhum fluxo é uma ISR. Sem interrupções não há concorrência para analisar, "
                    "e o pipeline não reportará nada.\n\nContinuar mesmo assim?",
                    parent=self.win,
                ):
                    return "Declare as ISRs do programa."
        elif i == 3:
            try:
                st.solver_timeout_ms = int(self.timeout_var.get())
            except ValueError:
                return "O timeout do solver deve ser um número inteiro (ms)."
        return None

    def _finish(self) -> None:
        target_s = self.target_var.get().strip()
        if not target_s:
            self._choose_target()
            target_s = self.target_var.get().strip()
            if not target_s:
                return
        target = Path(target_s)
        if target.exists() and not messagebox.askyesno(
            "Substituir arquivo?", f"{target}\njá existe. Substituir?", parent=self.win
        ):
            return
        try:
            save_c1(self.state, target)
        except (WizardError, ConfigError) as e:
            messagebox.showerror("Configuração inválida", str(e), parent=self.win)
            return
        self.win.grab_release()
        self.win.destroy()
        self.on_finish(target.resolve(), list(self.state.sources))

    # -- page 1: project -------------------------------------------------

    def _page_project(self) -> ttk.Frame:
        f = ttk.Frame(self.page_host)
        r = ttk.Frame(f)
        r.pack(fill=tk.X, pady=4)
        ttk.Label(r, text="Nome do projeto:", width=20).pack(side=tk.LEFT)
        self.name_var = tk.StringVar(value=self.state.name)
        ttk.Entry(r, textvariable=self.name_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(f, text="Arquivos-fonte (.c e .h) do programa sob análise:").pack(anchor=tk.W, pady=(8, 2))
        lf = ttk.Frame(f)
        lf.pack(fill=tk.BOTH, expand=True)
        self.src_list = tk.Listbox(lf, font=("Consolas", 9), selectmode=tk.EXTENDED)
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.src_list.yview)
        self.src_list.configure(yscrollcommand=sb.set)
        self.src_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        col = ttk.Frame(lf, padding=(6, 0, 0, 0))
        col.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Button(col, text="+ Arquivos...", width=16, command=self._add_files).pack(pady=1)
        ttk.Button(col, text="+ Pasta...", width=16, command=self._add_folder).pack(pady=1)
        ttk.Button(col, text="- Remover", width=16, command=self._remove_files).pack(pady=1)

        r2 = ttk.Frame(f)
        r2.pack(fill=tk.X, pady=(8, 2))
        ttk.Label(r2, text="Macros (-D), separadas por vírgula:", width=34).pack(side=tk.LEFT)
        self.defines_var = tk.StringVar(value=", ".join(self.state.defines))
        ttk.Entry(r2, textvariable=self.defines_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.scan_var = tk.StringVar()
        ttk.Label(f, textvariable=self.scan_var, foreground="gray").pack(anchor=tk.W, pady=(6, 0))
        ttk.Label(
            f, wraplength=640, justify=tk.LEFT,
            text="Os arquivos .c são compilados um a um para bitcode e ligados (llvm-link); as pastas "
                 "dos .h viram diretórios de include (-I). O assistente lê os fontes para sugerir "
                 "funções nas próximas etapas.",
        ).pack(anchor=tk.W, pady=(4, 0))
        self._refresh_sources()
        return f

    def _refresh_sources(self) -> None:
        self.src_list.delete(0, tk.END)
        for p in self.state.sources:
            self.src_list.insert(tk.END, str(p))

    def _add_paths(self, paths: list[Path]) -> None:
        for p in paths:
            p = p.resolve()
            if p.suffix.lower() in (".c", ".h", ".hpp") and p not in self.state.sources:
                self.state.sources.append(p)
        if not self.name_var.get().strip() and self.state.c_files:
            self.name_var.set(self.state.c_files[0].parent.name)
        self._refresh_sources()
        self._rescan()

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self.win, title="Arquivos C / Header",
            filetypes=[("Arquivos C e Headers", "*.c *.h *.hpp"), ("Todos os arquivos", "*.*")],
        )
        self._add_paths([Path(p) for p in paths])

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.win, title="Pasta do projeto (.c / .h)")
        if folder:
            root = Path(folder)
            self._add_paths(sorted(list(root.rglob("*.c")) + list(root.rglob("*.h"))))
            if not self.name_var.get().strip():
                self.name_var.set(root.name)

    def _remove_files(self) -> None:
        for idx in reversed(self.src_list.curselection()):
            self.state.sources.pop(idx)
        self._refresh_sources()
        self._rescan()

    def _rescan(self) -> None:
        self.defined, self.external = scan_functions(self.state.sources)
        self.scan_var.set(
            f"{len(self.state.c_files)} arquivo(s) .c, {len(self.state.h_files)} .h — "
            f"{len(self.defined)} função(ões) definida(s), {len(self.external)} chamada(s) sem corpo."
        )
        if hasattr(self, "entry_cb"):
            self.entry_cb.configure(values=self.defined)
            self.prim_fn_cb.configure(values=sorted(set(self.external + self.defined)))
            self.ext_fn_cb.configure(values=self.external)

    # -- page 2: flows ---------------------------------------------------

    def _page_flows(self) -> ttk.Frame:
        f = ttk.Frame(self.page_host)
        ttk.Label(
            f, wraplength=640, justify=tk.LEFT, foreground="#a33",
            text="Declare TODAS as rotinas de interrupção. Uma ISR que fica de fora não contribui "
                 "nenhum acesso, e os defeitos que só ela alcança desaparecem sem nenhum erro. "
                 "Prioridade: número maior = prioridade maior.",
        ).pack(anchor=tk.W, pady=(0, 6))

        cols = ("id", "kind", "entry", "irq", "priority")
        self.flow_tree = ttk.Treeview(f, columns=cols, show="headings", height=8, selectmode="browse")
        for c, t, w in zip(cols, ("ID", "Tipo", "Função de entrada", "IRQ", "Prioridade"), (90, 60, 260, 60, 80)):
            self.flow_tree.heading(c, text=t)
            self.flow_tree.column(c, width=w, anchor=tk.W)
        self.flow_tree.pack(fill=tk.BOTH, expand=True)
        self.flow_tree.bind("<<TreeviewSelect>>", self._flow_selected)

        form = ttk.LabelFrame(f, text=" Fluxo ", padding=6)
        form.pack(fill=tk.X, pady=6)
        self.flow_id = tk.StringVar()
        self.flow_kind = tk.StringVar(value="isr")
        self.flow_entry = tk.StringVar()
        self.flow_irq = tk.StringVar()
        self.flow_prio = tk.StringVar(value="1")
        ttk.Label(form, text="ID").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(form, textvariable=self.flow_id, width=12).grid(row=1, column=0, padx=(0, 6))
        ttk.Label(form, text="Tipo").grid(row=0, column=1, sticky=tk.W)
        ttk.Combobox(form, textvariable=self.flow_kind, values=FLOW_KINDS, state="readonly",
                     width=7).grid(row=1, column=1, padx=(0, 6))
        ttk.Label(form, text="Função de entrada").grid(row=0, column=2, sticky=tk.W)
        self.entry_cb = ttk.Combobox(form, textvariable=self.flow_entry, values=self.defined, width=34)
        self.entry_cb.grid(row=1, column=2, padx=(0, 6))
        ttk.Label(form, text="IRQ (só ISR)").grid(row=0, column=3, sticky=tk.W)
        ttk.Entry(form, textvariable=self.flow_irq, width=8).grid(row=1, column=3, padx=(0, 6))
        ttk.Label(form, text="Prioridade").grid(row=0, column=4, sticky=tk.W)
        ttk.Entry(form, textvariable=self.flow_prio, width=8).grid(row=1, column=4, padx=(0, 6))

        btns = ttk.Frame(f)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Adicionar / Atualizar", command=self._flow_upsert).pack(side=tk.LEFT)
        ttk.Button(btns, text="Remover", command=self._flow_remove).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Sugerir a partir do código", command=self._flow_suggest).pack(side=tk.RIGHT)
        self._refresh_flows()
        return f

    def _refresh_flows(self) -> None:
        self.flow_tree.delete(*self.flow_tree.get_children())
        for i, fl in enumerate(self.state.flows):
            irq = "" if fl.get("irq") is None else fl["irq"]
            self.flow_tree.insert("", tk.END, iid=str(i),
                                  values=(fl["id"], fl["kind"], fl["entry"], irq, fl["priority"]))

    def _flow_selected(self, _e=None) -> None:
        sel = self.flow_tree.selection()
        if not sel:
            return
        fl = self.state.flows[int(sel[0])]
        self.flow_id.set(fl["id"])
        self.flow_kind.set(fl["kind"])
        self.flow_entry.set(fl["entry"])
        self.flow_irq.set("" if fl.get("irq") is None else str(fl["irq"]))
        self.flow_prio.set(str(fl["priority"]))

    def _flow_upsert(self) -> None:
        fid, kind, entry = self.flow_id.get().strip(), self.flow_kind.get(), self.flow_entry.get().strip()
        try:
            prio = int(self.flow_prio.get())
            irq = _int_or_none(self.flow_irq.get())
        except ValueError:
            messagebox.showerror("Valor inválido", "IRQ e prioridade devem ser inteiros.", parent=self.win)
            return
        if not fid or not entry:
            messagebox.showerror("Campos obrigatórios", "Informe o ID e a função de entrada.", parent=self.win)
            return
        if kind == "isr" and irq is None:
            messagebox.showerror("IRQ obrigatória", "Uma ISR precisa do número da interrupção.", parent=self.win)
            return
        row = {"id": fid, "kind": kind, "entry": entry, "irq": irq if kind == "isr" else None, "priority": prio}
        idx = next((i for i, fl in enumerate(self.state.flows) if fl["id"] == fid), None)
        clash = next((fl for fl in self.state.flows if fl["entry"] == entry and fl["id"] != fid), None)
        if clash:
            messagebox.showerror("Entrada repetida", f"O fluxo {clash['id']!r} já usa {entry!r}.", parent=self.win)
            return
        if idx is None:
            self.state.flows.append(row)
        else:
            self.state.flows[idx] = row
        self._refresh_flows()

    def _flow_remove(self) -> None:
        sel = self.flow_tree.selection()
        if sel:
            self.state.flows.pop(int(sel[0]))
            self._refresh_flows()

    def _flow_suggest(self) -> None:
        sugg = suggest_flows(self.defined)
        have = {fl["entry"] for fl in self.state.flows}
        new = [s for s in sugg if s["entry"] not in have]
        if not new:
            messagebox.showinfo("Sugestões", "Nenhuma função nova com cara de main/ISR foi encontrada.",
                                parent=self.win)
            return
        ids = {fl["id"] for fl in self.state.flows}
        for s in new:
            base, n = s["id"], 1
            while s["id"] in ids:
                n += 1
                s["id"] = f"{base}_{n}"
            ids.add(s["id"])
            self.state.flows.append(s)
        self._refresh_flows()
        messagebox.showinfo(
            "Sugestões adicionadas",
            f"{len(new)} fluxo(s) sugerido(s) pelo nome das funções. Confira o número de IRQ e a "
            "prioridade de cada um: o assistente não tem como deduzi-los do código.",
            parent=self.win,
        )

    # -- page 3: masking -------------------------------------------------

    def _page_masking(self) -> ttk.Frame:
        f = ttk.Frame(self.page_host)
        ttk.Label(
            f, wraplength=640, justify=tk.LEFT,
            text="Funções que desabilitam ou habilitam interrupções (ex.: disable_isr(n), cli()). "
                 "'Argumento IRQ' é o índice (base 0) do parâmetro que diz qual interrupção; deixe "
                 "vazio se a função afeta todas (cli/sti). 'Valor = todas' é o valor do argumento "
                 "que significa todas as interrupções.",
        ).pack(anchor=tk.W, pady=(0, 6))
        cols = ("function", "effect", "irq_arg", "all_value", "non_constant_arg")
        self.prim_tree = ttk.Treeview(f, columns=cols, show="headings", height=6, selectmode="browse")
        for c, t, w in zip(cols, ("Função", "Efeito", "Argumento IRQ", "Valor = todas", "Arg. não constante"),
                           (200, 80, 100, 100, 130)):
            self.prim_tree.heading(c, text=t)
            self.prim_tree.column(c, width=w, anchor=tk.W)
        self.prim_tree.pack(fill=tk.BOTH, expand=True)
        self.prim_tree.bind("<<TreeviewSelect>>", self._prim_selected)

        form = ttk.LabelFrame(f, text=" Primitiva ", padding=6)
        form.pack(fill=tk.X, pady=6)
        self.prim_fn = tk.StringVar()
        self.prim_eff = tk.StringVar(value="disable")
        self.prim_arg = tk.StringVar(value="0")
        self.prim_all = tk.StringVar(value="-1")
        self.prim_nc = tk.StringVar(value="unknown")
        for col, label in enumerate(("Função", "Efeito", "Argumento IRQ", "Valor = todas",
                                     "Arg. não constante")):
            ttk.Label(form, text=label).grid(row=0, column=col, sticky=tk.W)
        self.prim_fn_cb = ttk.Combobox(form, textvariable=self.prim_fn, width=26)
        self.prim_fn_cb.grid(row=1, column=0, padx=(0, 6))
        ttk.Combobox(form, textvariable=self.prim_eff, values=PRIMITIVE_EFFECTS, state="readonly",
                     width=9).grid(row=1, column=1, padx=(0, 6))
        ttk.Entry(form, textvariable=self.prim_arg, width=10).grid(row=1, column=2, padx=(0, 6))
        ttk.Entry(form, textvariable=self.prim_all, width=10).grid(row=1, column=3, padx=(0, 6))
        ttk.Combobox(form, textvariable=self.prim_nc, values=NON_CONSTANT_ARG, state="readonly",
                     width=10).grid(row=1, column=4, padx=(0, 6))

        btns = ttk.Frame(f)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Adicionar / Atualizar", command=self._prim_upsert).pack(side=tk.LEFT)
        ttk.Button(btns, text="Remover", command=self._prim_remove).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Sugerir a partir do código", command=self._prim_suggest).pack(side=tk.RIGHT)

        g = ttk.LabelFrame(f, text=" Estado inicial ", padding=6)
        g.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(g, text="Máscara na entrada de cada fluxo:").pack(side=tk.LEFT)
        self.initial_var = tk.StringVar(value=self.state.initial_state)
        ttk.Combobox(g, textvariable=self.initial_var, values=INITIAL_STATES, state="readonly",
                     width=14).pack(side=tk.LEFT, padx=6)
        self.masks_self_var = tk.BooleanVar(value=self.state.isr_entry_masks_self)
        ttk.Checkbutton(g, text="O hardware mascara a própria IRQ enquanto sua ISR executa",
                        variable=self.masks_self_var).pack(side=tk.LEFT, padx=10)
        ttk.Label(f, foreground="gray", wraplength=640, justify=tk.LEFT,
                  text="'unknown' é a escolha segura para uma plataforma desconhecida.").pack(anchor=tk.W)

        for var, attr in ((self.initial_var, "initial_state"), (self.masks_self_var, "isr_entry_masks_self")):
            var.trace_add("write", lambda *_a, v=var, a=attr: setattr(self.state, a, v.get()))
        self._refresh_prims()
        return f

    def _refresh_prims(self) -> None:
        self.prim_tree.delete(*self.prim_tree.get_children())
        for i, p in enumerate(self.state.primitives):
            show = lambda v: "todas" if v is None else v  # noqa: E731
            self.prim_tree.insert("", tk.END, iid=str(i), values=(
                p["function"], p["effect"], show(p.get("irq_arg")), "" if p.get("all_value") is None
                else p["all_value"], p.get("non_constant_arg", "unknown")))

    def _prim_selected(self, _e=None) -> None:
        sel = self.prim_tree.selection()
        if not sel:
            return
        p = self.state.primitives[int(sel[0])]
        self.prim_fn.set(p["function"])
        self.prim_eff.set(p["effect"])
        self.prim_arg.set("" if p.get("irq_arg") is None else str(p["irq_arg"]))
        self.prim_all.set("" if p.get("all_value") is None else str(p["all_value"]))
        self.prim_nc.set(p.get("non_constant_arg", "unknown"))

    def _prim_upsert(self) -> None:
        fn = self.prim_fn.get().strip()
        if not fn:
            messagebox.showerror("Campo obrigatório", "Informe o nome da função.", parent=self.win)
            return
        try:
            row = {"function": fn, "effect": self.prim_eff.get(),
                   "irq_arg": _int_or_none(self.prim_arg.get()),
                   "all_value": _int_or_none(self.prim_all.get()),
                   "non_constant_arg": self.prim_nc.get()}
        except ValueError:
            messagebox.showerror("Valor inválido", "Argumento IRQ e 'valor = todas' devem ser inteiros "
                                 "ou vazios.", parent=self.win)
            return
        idx = next((i for i, p in enumerate(self.state.primitives) if p["function"] == fn), None)
        if idx is None:
            self.state.primitives.append(row)
        else:
            self.state.primitives[idx] = row
        self._refresh_prims()

    def _prim_remove(self) -> None:
        sel = self.prim_tree.selection()
        if sel:
            self.state.primitives.pop(int(sel[0]))
            self._refresh_prims()

    def _prim_suggest(self) -> None:
        have = {p["function"] for p in self.state.primitives}
        new = [p for p in suggest_primitives(sorted(set(self.external + self.defined)))
               if p["function"] not in have]
        self.state.primitives.extend(new)
        self._refresh_prims()
        messagebox.showinfo(
            "Sugestões", f"{len(new)} primitiva(s) sugerida(s) pelo nome." if new
            else "Nenhuma função com nome de primitiva de mascaramento foi encontrada.", parent=self.win)

    # -- page 4: semantics and externals ---------------------------------

    def _page_semantics(self) -> ttk.Frame:
        f = ttk.Frame(self.page_host)
        sem = ttk.LabelFrame(f, text=" Semântica das interrupções ", padding=6)
        sem.pack(fill=tk.X)
        st = self.state
        self.epp_var = tk.BooleanVar(value=st.equal_priority_preemption)
        self.reent_var = tk.BooleanVar(value=st.isr_reentrant)
        self.nest_var = tk.BooleanVar(value=st.nesting)
        self.arrival_var = tk.StringVar(value=st.isr_arrival)
        rows = (
            (self.epp_var, "Fluxos de mesma prioridade podem se preemptar (seguro: marcado)"),
            (self.nest_var, "Aninhamento: uma ISR pode ser interrompida por outra de prioridade maior "
                            "(seguro: marcado)"),
            (self.reent_var, "Uma ISR pode interromper a si mesma (reentrante)"),
        )
        for var, text in rows:
            ttk.Checkbutton(sem, text=text, variable=var).pack(anchor=tk.W)
        r = ttk.Frame(sem)
        r.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(r, text="Chegada das interrupções:").pack(side=tk.LEFT)
        ttk.Combobox(r, textvariable=self.arrival_var, values=ISR_ARRIVAL, state="readonly",
                     width=18).pack(side=tk.LEFT, padx=6)
        ttk.Label(r, foreground="#a33", text="qualquer coisa além de 'unbounded' é um filtro não-sound").pack(
            side=tk.LEFT)

        ext = ttk.LabelFrame(f, text=" Funções externas (sem corpo no programa) ", padding=6)
        ext.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        r2 = ttk.Frame(ext)
        r2.pack(fill=tk.X)
        ttk.Label(r2, text="Padrão para externas não modeladas:").pack(side=tk.LEFT)
        self.ext_default_var = tk.StringVar(value=st.externals_default)
        ttk.Combobox(r2, textvariable=self.ext_default_var, values=EXTERNALS_DEFAULT, state="readonly",
                     width=26).pack(side=tk.LEFT, padx=6)
        ttk.Label(r2, foreground="#a33", text="'none' é não-sound: só para experimentos").pack(side=tk.LEFT)

        cols = ("function", "effect", "note")
        self.ext_tree = ttk.Treeview(ext, columns=cols, show="headings", height=5, selectmode="browse")
        for c, t, w in zip(cols, ("Função", "Efeito", "Nota"), (180, 130, 300)):
            self.ext_tree.heading(c, text=t)
            self.ext_tree.column(c, width=w, anchor=tk.W)
        self.ext_tree.pack(fill=tk.BOTH, expand=True, pady=(6, 4))
        self.ext_tree.bind("<<TreeviewSelect>>", self._ext_selected)
        form = ttk.Frame(ext)
        form.pack(fill=tk.X)
        self.ext_fn = tk.StringVar()
        self.ext_eff = tk.StringVar(value="none")
        self.ext_note = tk.StringVar()
        self.ext_fn_cb = ttk.Combobox(form, textvariable=self.ext_fn, values=self.external, width=22)
        self.ext_fn_cb.pack(side=tk.LEFT)
        ttk.Combobox(form, textvariable=self.ext_eff, values=EXTERNAL_EFFECTS, state="readonly",
                     width=16).pack(side=tk.LEFT, padx=4)
        ttk.Entry(form, textvariable=self.ext_note).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(form, text="Adicionar / Atualizar", command=self._ext_upsert).pack(side=tk.LEFT)
        ttk.Button(form, text="Remover", command=self._ext_remove).pack(side=tk.LEFT, padx=4)

        r3 = ttk.Frame(f)
        r3.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(r3, text="Timeout do solver Z3 por candidato (ms):").pack(side=tk.LEFT)
        self.timeout_var = tk.StringVar(value=str(st.solver_timeout_ms))
        ttk.Entry(r3, textvariable=self.timeout_var, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Label(r3, foreground="gray", text="um timeout nunca descarta: o candidato segue como inconclusivo").pack(
            side=tk.LEFT)

        for var, attr in ((self.epp_var, "equal_priority_preemption"), (self.reent_var, "isr_reentrant"),
                          (self.nest_var, "nesting"), (self.arrival_var, "isr_arrival"),
                          (self.ext_default_var, "externals_default")):
            var.trace_add("write", lambda *_a, v=var, a=attr: setattr(self.state, a, v.get()))
        self._refresh_ext()
        return f

    def _refresh_ext(self) -> None:
        self.ext_tree.delete(*self.ext_tree.get_children())
        for i, m in enumerate(self.state.external_models):
            self.ext_tree.insert("", tk.END, iid=str(i), values=(m["function"], m["effect"], m.get("note", "")))

    def _ext_selected(self, _e=None) -> None:
        sel = self.ext_tree.selection()
        if sel:
            m = self.state.external_models[int(sel[0])]
            self.ext_fn.set(m["function"])
            self.ext_eff.set(m["effect"])
            self.ext_note.set(m.get("note", ""))

    def _ext_upsert(self) -> None:
        fn = self.ext_fn.get().strip()
        if not fn:
            return
        row = {"function": fn, "effect": self.ext_eff.get(), "note": self.ext_note.get().strip()}
        idx = next((i for i, m in enumerate(self.state.external_models) if m["function"] == fn), None)
        if idx is None:
            self.state.external_models.append(row)
        else:
            self.state.external_models[idx] = row
        self._refresh_ext()

    def _ext_remove(self) -> None:
        sel = self.ext_tree.selection()
        if sel:
            self.state.external_models.pop(int(sel[0]))
            self._refresh_ext()

    # -- page 5: review --------------------------------------------------

    def _page_review(self) -> ttk.Frame:
        f = ttk.Frame(self.page_host)
        r = ttk.Frame(f)
        r.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(r, text="Salvar em:", width=12).pack(side=tk.LEFT)
        ttk.Entry(r, textvariable=self.target_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(r, text="Escolher...", command=self._choose_target).pack(side=tk.LEFT, padx=6)
        self.valid_var = tk.StringVar()
        self.valid_lbl = ttk.Label(f, textvariable=self.valid_var, font=("Segoe UI", 9, "bold"))
        self.valid_lbl.pack(anchor=tk.W, pady=(0, 4))
        self.preview = scrolledtext.ScrolledText(f, font=("Consolas", 9), wrap=tk.NONE, height=20)
        self.preview.pack(fill=tk.BOTH, expand=True)
        return f

    def _choose_target(self) -> None:
        initial = self.state.c_files[0].parent if self.state.c_files else Path.cwd()
        name = (self.state.name or "projeto").replace(" ", "_")
        path = filedialog.asksaveasfilename(
            parent=self.win, title="Salvar configuração C1",
            initialdir=str(initial), initialfile=f"{name}.c1.yaml", defaultextension=".yaml",
            filetypes=[("Configuração C1", "*.yaml *.yml")],
        )
        if path:
            self.target_var.set(path)
            self._refresh_review()

    def _refresh_review(self) -> None:
        target = Path(self.target_var.get()) if self.target_var.get().strip() else None
        self.preview.configure(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)
        try:
            cfg = validate_state(self.state, target)
            self.preview.insert(tk.END, dump_c1(self.state.to_c1(target)))
            n_isr = sum(1 for fl in cfg.flows if fl.is_isr)
            self.valid_var.set(f"✔ Configuração válida: {len(cfg.flows)} fluxo(s), {n_isr} ISR(s), "
                               f"{len(cfg.masking_primitives)} primitiva(s) de mascaramento.")
            self.valid_lbl.configure(foreground="#1a7f37")
            self.btn_next.configure(state=tk.NORMAL)
        except (WizardError, ConfigError) as e:
            self.valid_var.set("✖ Configuração inválida — volte e corrija:")
            self.valid_lbl.configure(foreground="#a33")
            self.preview.insert(tk.END, str(e))
            self.btn_next.configure(state=tk.DISABLED)
        self.preview.configure(state=tk.DISABLED)
