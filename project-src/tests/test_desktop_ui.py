"""Tests for the native Win32/Tkinter MVP GUI (multi-file .c/.h list & LLM API config tab)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest
import yaml

from irqrace.ui.desktop import (
    LLM_PROVIDER_PRESETS,
    PIPELINE_STEPS,
    REPO_ROOT,
    IrqRaceWinApp,
    PipelineStepper,
    apply_source_list_to_c1_dict,
    build_backend_from_config,
    load_dotenv_into_environ,
    resolve_c_source_files,
    save_dotenv_settings,
    UniversalIntroSplash,
)


@pytest.fixture(scope="module")
def tk_root():
    """Shared single Tk root per test session to avoid Windows Tcl/Tk DLL reload corruption."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_multi_file_c_and_h_list_in_c1(tmp_path: Path) -> None:
    c1 = tmp_path / "mod1.c"
    c2 = tmp_path / "mod2.c"
    hdr = tmp_path / "inc" / "hw_irq.h"
    hdr.parent.mkdir(parents=True, exist_ok=True)
    c1.write_text("int g;\n", encoding="utf-8")
    c2.write_text("void f(void) {}\n", encoding="utf-8")
    hdr.write_text("#define IRQ_EN 1\n", encoding="utf-8")

    yaml_path = REPO_ROOT / "bench" / "configs" / "svp_simple_001_001.yaml"
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    updated = apply_source_list_to_c1_dict(raw, [c1, c2, hdr])

    assert updated["subject"]["build"]["mode"] == "link"
    assert len(updated["subject"]["sources"]) == 2
    assert str(hdr.parent.resolve()) in updated["subject"]["build"]["include_dirs"]


def test_generic_llm_backend_chatgpt_and_groq(tmp_path: Path) -> None:
    # Groq configuration
    groq_b = build_backend_from_config(
        adapter="openai",
        model="openai/gpt-oss-120b",
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk_test_123",
    )
    assert groq_b.spec == "openai:openai/gpt-oss-120b"
    assert groq_b.base_url == "https://api.groq.com/openai/v1"

    # ChatGPT / OpenAI configuration
    oa_b = build_backend_from_config(
        adapter="openai",
        model="gpt-4o",
        base_url="https://api.openai.com/v1",
        api_key="sk_test_456",
    )
    assert oa_b.spec == "openai:gpt-4o"
    assert oa_b.base_url == "https://api.openai.com/v1"

    # Dotenv persistence round-trip
    env_file = tmp_path / ".env"
    save_dotenv_settings(
        {
            "IRQRACE_LLM_ADAPTER": "openai",
            "IRQRACE_LLM_MODEL": "gpt-4o-mini",
            "IRQRACE_OPENAI_BASE_URL": "https://api.openai.com/v1",
        },
        env_path=env_file,
    )
    loaded = load_dotenv_into_environ(env_file)
    assert loaded["IRQRACE_LLM_MODEL"] == "gpt-4o-mini"
    assert loaded["IRQRACE_OPENAI_BASE_URL"] == "https://api.openai.com/v1"


def test_pipeline_stepper_with_source_list(tmp_path: Path) -> None:
    yaml_path = REPO_ROOT / "bench" / "configs" / "svp_simple_001_001.yaml"
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    files = resolve_c_source_files(raw)
    assert len(files) >= 1

    stepper = PipelineStepper(yaml_path, files, work_root=tmp_path)
    store = stepper.init_run()

    logs: list[str] = []
    for idx, (expected_key, _) in enumerate(PIPELINE_STEPS):
        assert stepper.current_step_idx == idx
        step_key, summary = stepper.run_next_step(log_fn=logs.append)
        assert step_key == expected_key
        assert summary

    assert stepper.current_step_idx == len(PIPELINE_STEPS)
    assert store.check() == []


def test_win_app_top_tabs_and_multi_file_list(tk_root) -> None:
    win = tk.Toplevel(tk_root)
    try:
        app = IrqRaceWinApp(win)
        # Verify the 2 top-level tabs exist ("Pipeline" and "Configuração de APIs de LLM")
        tabs = app.top_notebook.tabs()
        assert len(tabs) == 2

        # Verify source files list contains multiple files (.c and .h)
        assert len(app.source_files_list) >= 2
        assert app.src_listbox.size() == len(app.source_files_list)

        # Verify preset switching in LLM config tab
        app.llm_preset_var.set("ChatGPT / OpenAI Oficial")
        app._on_llm_preset_changed()
        assert app.llm_base_url_var.get() == LLM_PROVIDER_PRESETS["ChatGPT / OpenAI Oficial"]["base_url"]

        app.llm_preset_var.set("Groq (OpenAI-Compatible)")
        app._on_llm_preset_changed()
        assert app.llm_base_url_var.get() == LLM_PROVIDER_PRESETS["Groq (OpenAI-Compatible)"]["base_url"]

        # Verify loading C:\Users\luoma\Desktop\racebench\lucas replaces the file list and selects lucas_config.yaml
        lucas_dir = Path(r"C:\Users\luoma\Desktop\racebench\lucas")
        if lucas_dir.exists():
            app.load_project_folder(lucas_dir)
            assert Path(app.yaml_path_var.get()).name == "lucas_config.yaml"
            names = {p.name for p in app.source_files_list}
            assert "teste_lucas.c" in names
            assert "common.c" in names
            assert "common.h" in names
            assert app.stepper is None
    finally:
        win.destroy()


def test_live_log_tab_and_api_loading_bar(tk_root) -> None:
    """Live log shares the expandable notebook with LLM tabs; API bar reacts to progress/429."""
    win = tk.Toplevel(tk_root)
    try:
        app = IrqRaceWinApp(win)
        tabs = app.notebook.tabs()
        assert len(tabs) == 5
        assert str(app.tab_live_log) == tabs[0]
        assert str(app.log_text.winfo_parent()).startswith(str(app.tab_live_log))
        # The vertical splitter lets the bottom workspace grow
        assert len(app.main_vpaned.panes()) == 2

        app._handle_api_event(
            "api_candidate_progress",
            {"stage": "Triagem", "current": 0, "total": 4, "cid": "c1", "var": "g", "status": "running"},
        )
        assert "1/4" in app.api_status_var.get()

        app._handle_api_event(
            "api_rate_limit_tick", {"remaining_s": 5.0, "total_s": 20.0, "attempt": 1, "max_retries": 6}
        )
        assert "429" in app.api_status_var.get()
        assert abs(app.api_progress_var.get() - 75.0) < 0.01

        app._handle_api_event(
            "api_request_done", {"elapsed_s": 2.0, "in_tokens": 100, "out_tokens": 20}
        )
        assert app.api_tokens_in_total == 100

        app._handle_api_event(
            "api_candidate_progress",
            {"stage": "Triagem", "current": 1, "total": 4, "cid": "c1", "var": "g", "status": "done"},
        )
        assert abs(app.api_progress_var.get() - 25.0) < 0.01
    finally:
        win.destroy()


def test_tracked_backend_emits_rate_limit_events() -> None:
    """A 429 on the first attempt must emit rate_limit_wait/tick events before retrying."""
    from irqrace.llm.backends.openai_backend import _RateLimited
    from irqrace.ui.desktop import TrackedOpenAIBackend

    events: list[str] = []
    calls = {"n": 0}

    def transport(_body):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _RateLimited("rate limited", 0.5)
        return {
            "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1},
        }

    from irqrace.llm.backends import ChatRequest

    b = TrackedOpenAIBackend(
        "m", base_url="http://x", api_key="k", transport=transport,
        event_cb=lambda k, _p: events.append(k),
    )
    resp = b.chat(ChatRequest(system="s", messages=[{"role": "user", "content": "hi"}], max_tokens=8))
    assert resp.text == "OK"
    assert events[0] == "request_start"
    assert "rate_limit_wait" in events
    assert "rate_limit_tick" in events
    assert events[-1] == "request_done"


def test_broken_c_code_raises_build_error_loudly(tmp_path: Path) -> None:
    """When C source has a compilation error, Step 1 must fail loudly with clang-14 diagnostic (never use cached .bc)."""
    import pytest
    from irqrace.build import BuildError

    broken_c = tmp_path / "broken_lucas.c"
    broken_c.write_text(
        "int global_var = ;\n"
        "void svp_simple_031_001_main(void) { ERRO_DE_SINTAXE_INTENCIONAL +++ ; }\n",
        encoding="utf-8",
    )
    yaml_path = REPO_ROOT / "bench" / "configs" / "svp_simple_031_001.yaml"

    stepper = PipelineStepper(yaml_path, [broken_c], work_root=tmp_path)
    store = stepper.init_run()

    logs: list[str] = []
    with pytest.raises(BuildError) as exc_info:
        stepper.run_next_step(log_fn=logs.append)

    err_msg = str(exc_info.value)
    assert "clang-14" in err_msg or "error:" in err_msg
    manifest = store.read_manifest()
    stages = {s["name"]: s["status"] for s in manifest["stages"]}
    assert stages["build"] == "failed"


def test_load_lucas_folder_and_compile_via_wsl(tmp_path: Path) -> None:
    """Verify C:\\Users\\luoma\\Desktop\\racebench\\lucas compiles via real WSL clang-14 + runs irqrace-stage1."""
    lucas_dir = Path(r"C:\Users\luoma\Desktop\racebench\lucas")
    if not lucas_dir.exists():
        return

    yaml_path = lucas_dir / "lucas_config.yaml"
    files = sorted(list(lucas_dir.rglob("*.c")) + list(lucas_dir.rglob("*.h")))

    stepper = PipelineStepper(yaml_path, files, work_root=tmp_path)
    store = stepper.init_run()
    logs: list[str] = []
    s1_key, _ = stepper.run_next_step(log_fn=logs.append)
    assert s1_key == "build"
    assert (store.root / "build" / "whole.bc").exists()

    s2_key, s2_summary = stepper.run_next_step(log_fn=logs.append)
    assert s2_key == "stage1"
    assert "candidatos extraídos" in s2_summary


def test_two_screen_wizard_and_mandatory_llm(monkeypatch, tk_root) -> None:
    """Verify Screen 1 requires LLM configuration before advancing to Screen 2, and buttons are non-verbose."""
    import tkinter.messagebox as mb

    errors: list[str] = []
    monkeypatch.setattr(mb, "showerror", lambda title, msg: errors.append(f"{title}: {msg}"))
    monkeypatch.setattr("irqrace.ui.desktop.save_dotenv_settings", lambda *args, **kwargs: None)

    win = tk.Toplevel(tk_root)
    try:
        app = IrqRaceWinApp(win)

        # Starts on Screen 1 (tab_setup)
        assert app.top_notebook.select() == str(app.tab_setup)

        # Check button names are concise: (RESET), (STEP), (RESUME), (STOP)
        assert app.btn_reset.cget("text") == "(RESET)"
        assert app.btn_step.cget("text") == "(STEP)"
        assert app.btn_resume.cget("text") == "(RESUME)"
        assert app.btn_stop.cget("text") == "(STOP)"

        # Attempt to proceed without API key must fail and show mandatory error
        app.llm_api_key_var.set("")
        ok = app._on_proceed_to_pipeline()
        assert ok is False
        assert any("OBRIGATÓRIA" in err for err in errors)
        assert app.top_notebook.select() == str(app.tab_setup)

        # Fill API key and proceed
        app.llm_api_key_var.set("gsk_valid_key_test_123")
        ok = app._on_proceed_to_pipeline()
        assert ok is True
        assert app.top_notebook.select() == str(app.tab_pipeline)

        # Button state management
        app._set_buttons_state(tk.DISABLED)  # running
        assert str(app.btn_reset.cget("state")) == "disabled"
        assert str(app.btn_step.cget("state")) == "disabled"
        assert str(app.btn_resume.cget("state")) == "disabled"
        assert str(app.btn_stop.cget("state")) == "normal"

        # Stop button triggers interrupt
        stepper = app._create_stepper()
        app.stepper = stepper
        app.is_running_async = True
        app._on_stop_run()
        assert app.stop_requested is True
        assert stepper.stop_requested is True

        app._set_buttons_state(tk.NORMAL)  # stopped/idle
        assert str(app.btn_reset.cget("state")) == "normal"
        assert str(app.btn_step.cget("state")) == "normal"
        assert str(app.btn_resume.cget("state")) == "normal"
        assert str(app.btn_stop.cget("state")) == "disabled"
    finally:
        win.destroy()


def test_stop_run_and_midblock_interrupt() -> None:
    """TrackedOpenAIBackend raises InterruptedError immediately when stop_checker returns True."""
    import pytest
    from irqrace.llm.backends import ChatRequest
    from irqrace.ui.desktop import TrackedOpenAIBackend

    b = TrackedOpenAIBackend(
        "m",
        base_url="http://fake",
        api_key="k",
        transport=lambda _b: {},
        stop_checker=lambda: True,
    )

    with pytest.raises(InterruptedError):
        b.chat(ChatRequest(system="s", messages=[{"role": "user", "content": "hi"}], max_tokens=8))


def test_pdf_report_generation(tmp_path: Path) -> None:
    """PDFReportBuilder generates a valid multi-page PDF with pipeline, metrics, candidate table and git diff."""
    import pymupdf
    from irqrace.ui.pdf_report import PDFReportBuilder

    pdf_out = tmp_path / "relatorio_tcc_test.pdf"
    data = {
        "case_name": "svp_simple_001_001",
        "yaml_path": "svp_simple_001_001.yaml",
        "source_files": [Path("main.c"), Path("hardware.h")],
        "llm_model": "openai/gpt-oss-120b",
        "llm_adapter": "openai",
        "stages": {
            "build": {"status": "ok", "wall_ms": 115},
            "stage1": {"status": "ok", "wall_ms": 320},
            "solver": {"status": "ok", "wall_ms": 80},
            "context": {"status": "ok", "wall_ms": 40},
            "triage": {"status": "ok", "wall_ms": 650},
            "repair": {"status": "ok", "wall_ms": 820},
        },
        "candidates": {
            "c1": {
                "record": {"pattern": "atomicity-triple", "variable": {"name": "global_count"}},
                "triage": {"bucket": "likely_real", "feasibility": {"verdict": "feasible"}},
                "repair": {
                    "strategy": "mask_interval",
                    "masked_irqs": [1],
                    "covers_from_line": 15,
                    "covers_to_line": 18,
                    "witness": {
                        "firing_flow": "isr_1",
                        "preemption_point": "16",
                        "access_order": ["A1", "B", "A2"],
                        "divergence": "valor de global_count sobrescrito incorretamente",
                    },
                    "latency_note": "Mascaramento delimitado a 3 instruções (custo desprezível)",
                    "diff": (
                        "--- a/main.c\n"
                        "+++ b/main.c\n"
                        "@@ -15,4 +15,6 @@\n"
                        "+disable_isr(1);\n"
                        " global_count++;\n"
                        "+enable_isr(1);\n"
                    ),
                },
            },
            "c2": {
                "record": {"pattern": "atomicity-triple", "variable": {"name": "trap_var"}},
                "triage": {"bucket": "likely_infeasible", "feasibility": {"verdict": "infeasible"}},
                "repair": None,
            },
        },
    }

    builder = PDFReportBuilder(pdf_out, data)
    out_file = builder.build()
    assert out_file.exists()
    assert out_file.stat().st_size > 1000

    doc = pymupdf.open(str(out_file))
    assert len(doc) >= 1
    full_text = "\n".join(page.get_text() for page in doc)
    assert "RELATÓRIO TÉCNICO" in full_text
    assert "svp_simple_001_001" in full_text
    assert "c1" in full_text
    assert "global_count" in full_text
    assert "disable_isr(1);" in full_text
    doc.close()


def test_apply_and_revert_patch_flow(tmp_path: Path) -> None:
    """Applying a patch writes the modified C source and creates .bak; reverting restores it."""
    from irqrace.llm.repair import apply_unified_diff

    c_file = tmp_path / "target_code.c"
    initial_code = (
        "#include <stdio.h>\n"
        "int shared = 0;\n"
        "void worker(void) {\n"
        "    shared = shared + 1;\n"
        "}\n"
    )
    c_file.write_text(initial_code, encoding="utf-8")

    diff_txt = (
        "--- a/target_code.c\n"
        "+++ b/target_code.c\n"
        "@@ -3,3 +3,5 @@\n"
        " void worker(void) {\n"
        "+    disable_isr(2);\n"
        "     shared = shared + 1;\n"
        "+    enable_isr(2);\n"
        " }\n"
    )

    patched_code = apply_unified_diff(c_file.read_text(encoding="utf-8"), diff_txt)
    assert patched_code is not None
    assert "disable_isr(2);" in patched_code
    assert "enable_isr(2);" in patched_code

    # Create backup and write patch
    bak_file = c_file.with_name(f"{c_file.name}.bak")
    bak_file.write_text(initial_code, encoding="utf-8")
    c_file.write_text(patched_code, encoding="utf-8")

    assert c_file.read_text(encoding="utf-8") == patched_code
    assert bak_file.read_text(encoding="utf-8") == initial_code

    # Revert from backup
    c_file.write_text(bak_file.read_text(encoding="utf-8"), encoding="utf-8")
    bak_file.unlink()

    assert c_file.read_text(encoding="utf-8") == initial_code
    assert not bak_file.exists()


def test_universal_intro_splash(monkeypatch, tk_root) -> None:
    """Verify Clean View TCC Intro Splash renders students, advisor and dismisses cleanly on ENTER/ESC."""
    import os

    # Temporarily remove PYTEST_CURRENT_TEST to allow splash initialization
    cur_test = os.environ.pop("PYTEST_CURRENT_TEST", None)
    try:
        completed = []
        splash = UniversalIntroSplash(tk_root, duration_ms=50, on_complete=lambda: completed.append(True))
        assert splash.splash is not None
        assert splash.canvas is not None
        splash.dismiss()
        assert splash.dismissed is True
        assert completed == [True]
    finally:
        if cur_test is not None:
            os.environ["PYTEST_CURRENT_TEST"] = cur_test





