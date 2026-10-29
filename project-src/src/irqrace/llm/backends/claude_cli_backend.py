"""Claude through ``claude -p``, the Claude Code CLI in non-interactive mode.

The point is *who pays*. The CLI signs in with the user's Claude subscription
(Pro or Max), so a triage sweep is drawn from the plan's usage limits instead of
billed per token like the ``anthropic:`` adapter. For a thesis that runs the same
31 subjects under five prompt rows, that is the difference between a budget line
and none.

Each request is one process::

    claude -p --model <model> --output-format json --json-schema <schema> ...

with the prompt on stdin. The CLI enforces the schema itself and returns the
validated object as ``structured_output``, so answers are ``native_schema`` --
the same tier as the Anthropic and OpenAI adapters, and comparable with them in
the ablation.

## Keeping the call a plain model call

Claude Code is an agent, not an endpoint, and by default it would bring an
agent's context into every request. Each piece is switched off:

* ``--system-prompt`` **replaces** Claude Code's own system prompt with the
  triage prompt, rather than appending to it;
* ``--tools ""``, ``--strict-mcp-config`` and ``--disable-slash-commands``: no
  tools, no MCP servers, no skills;
* ``--setting-sources ""``: the user's hooks and plugins do not run;
* the process starts in an **empty temporary directory**, so no ``CLAUDE.md``
  and no project memory is discovered -- run from this repository, the vault's
  own ``CLAUDE.md`` would otherwise ride along with every candidate;
* ``--no-session-persistence``: a sweep does not leave hundreds of sessions in
  the user's history.

``--bare`` would do most of this in one flag, but it also restricts auth to
``ANTHROPIC_API_KEY`` and never reads the subscription login, which defeats the
purpose.

## Billing, deliberately

``ANTHROPIC_API_KEY`` and ``ANTHROPIC_AUTH_TOKEN`` are **removed** from the
child's environment. With either set, the CLI would authenticate with it and
bill the API account -- silently, since the answer looks the same. Without them
it uses the subscription login or fails with "not logged in", which is the
honest outcome.

Usage is therefore **unpriced**: :meth:`Usage.cost_usd` returns ``None``. The
CLI does report a ``total_cost_usd``, but on a subscription that is a list-price
estimate of what the tokens would have cost on the API, not a charge, and
putting it in a cost column would be a claim this run did not incur.

## Known differences from the API adapters, reported as caveats

* temperature and ``max_tokens`` cannot be set from the CLI;
* a multi-turn request (only the deferred ``+progressive`` row sends one) is
  rendered as a transcript inside a single prompt, because ``claude -p`` takes
  one user turn;
* a model alias (``sonnet``, ``opus``) resolves to whatever the CLI maps it to
  that day. :attr:`ClaudeCLIBackend.resolved_model` records what actually
  answered; prefer a full model id for any number that goes into the thesis.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable

from irqrace.llm.backends.base import (
    Backend,
    BackendError,
    Capabilities,
    ChatRequest,
    ChatResponse,
    RefusalError,
    StructuredMode,
    StructuredOutputError,
    Usage,
    extract_json,
)

DEFAULT_EXECUTABLE = "claude"
DEFAULT_TIMEOUT_S = 600.0

#: Credentials that would make the CLI bill an API account instead of the plan.
_API_AUTH_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

#: ``(argv, stdin, env, cwd, timeout_s, stop_checker) -> (returncode, stdout, stderr)``.
Runner = Callable[..., tuple[int, str, str]]


class ClaudeCLIBackend(Backend):
    provider = "claude-cli"

    def __init__(
        self,
        model: str,
        *,
        executable: str | None = None,
        timeout_s: float | None = None,
        stop_checker: Callable[[], bool] | None = None,
        runner: Runner | None = None,
    ):
        super().__init__(model)
        self.executable = (
            executable or os.environ.get("IRQRACE_CLAUDE_CLI") or DEFAULT_EXECUTABLE
        )
        self.timeout_s = timeout_s or DEFAULT_TIMEOUT_S
        self.stop_checker = stop_checker
        self._runner = runner or _run
        #: The model the CLI reported answering with on the last call.
        self.resolved_model: str | None = None

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            structured=StructuredMode.native_schema,
            # The CLI caches the system prompt on its own (1h ephemeral cache);
            # there is nothing to mark, but cost is not comparable to an
            # uncached backend either way -- and here there is no cost at all.
            prompt_caching=True,
            temperature=False,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        argv = self._argv(request)
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="irqrace-claude-") as cwd:
            code, stdout, stderr = self._runner(
                argv,
                stdin=_render_messages(request.messages),
                env=_subscription_env(),
                cwd=cwd,
                timeout_s=self.timeout_s,
                stop_checker=self.stop_checker,
            )
        elapsed = time.perf_counter() - started

        data = self._parse(code, stdout, stderr)
        self.resolved_model = next(iter(data.get("modelUsage") or {}), None)

        text = data.get("result") or ""
        parsed: dict[str, Any] | None = None
        if request.schema is not None:
            parsed = data.get("structured_output")
            if not isinstance(parsed, dict):
                # Older CLIs return the object only as text in `result`.
                parsed = extract_json(text)
        return ChatResponse(
            text=text,
            parsed=parsed,
            structured_mode=None if request.schema is None else StructuredMode.native_schema,
            usage=_usage(data, elapsed),
        )

    def _argv(self, request: ChatRequest) -> list[str]:
        exe = shutil.which(self.executable) or self.executable
        argv = [
            exe, "-p",
            "--model", self.model,
            "--output-format", "json",
            "--system-prompt", request.system,
            "--tools", "",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--setting-sources", "",
            "--no-session-persistence",
        ]
        if request.schema is not None:
            argv += ["--json-schema", json.dumps(request.schema)]
        return argv

    def _parse(self, code: int, stdout: str, stderr: str) -> dict[str, Any]:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            detail = (stderr or stdout).strip()[:500]
            raise BackendError(
                f"`{self.executable} -p` exited {code} without a JSON result: {detail}"
                + (
                    "\nIs Claude Code installed and logged in with a subscription? "
                    "Run `claude` once interactively and use /login."
                    if code != 0 else ""
                )
            ) from None
        if not isinstance(data, dict):
            raise BackendError(f"`{self.executable} -p` returned {type(data).__name__}, not an object")

        if data.get("is_error") or code != 0:
            status = data.get("api_error_status")
            message = str(data.get("result") or stderr.strip() or "unknown error")[:500]
            raise BackendError(
                f"claude-cli:{self.model} failed"
                + (f" (HTTP {status})" if status else "")
                + f": {message}"
            )
        if data.get("stop_reason") == "refusal":
            raise RefusalError(
                f"claude-cli:{self.model} declined: {str(data.get('result') or '')[:300]}"
            )
        if data.get("subtype") not in (None, "success"):
            raise StructuredOutputError(
                f"claude-cli:{self.model} ended with {data.get('subtype')!r}"
            )
        return data


def _render_messages(messages: list[dict[str, str]]) -> str:
    """One prompt from a message list.

    ``claude -p`` takes a single user turn. One message -- every active ablation
    row -- goes through verbatim. A longer history is rendered as a transcript,
    which is a different input from a native multi-turn request and is listed
    as such in the module docstring.
    """
    if len(messages) == 1:
        return messages[0]["content"]
    *history, last = messages
    turns = "\n\n".join(
        f'<turn role="{m["role"]}">\n{m["content"]}\n</turn>' for m in history
    )
    return (
        "The conversation so far:\n\n"
        f"<conversation>\n{turns}\n</conversation>\n\n"
        "Now answer the latest user turn:\n\n"
        f"{last['content']}"
    )


def _subscription_env() -> dict[str, str]:
    env = dict(os.environ)
    for var in _API_AUTH_VARS:
        env.pop(var, None)
    return env


def _usage(data: dict[str, Any], elapsed: float) -> Usage:
    u = data.get("usage") or {}
    return Usage(
        input_tokens=u.get("input_tokens") or 0,
        output_tokens=u.get("output_tokens") or 0,
        cache_write_tokens=u.get("cache_creation_input_tokens") or 0,
        cache_read_tokens=u.get("cache_read_input_tokens") or 0,
        latency_s=elapsed,
        # Unpriced on purpose: drawn from the plan's limits, not billed. See
        # the module docstring on why `total_cost_usd` is not used.
        price_in=None,
        price_out=None,
    )


def _run(
    argv: list[str],
    *,
    stdin: str,
    env: dict[str, str],
    cwd: str,
    timeout_s: float,
    stop_checker: Callable[[], bool] | None,
) -> tuple[int, str, str]:
    """Run one ``claude -p`` process, honouring a timeout and a stop request."""
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=cwd,
        )
    except FileNotFoundError:
        raise BackendError(
            f"{argv[0]!r} not found. Install Claude Code, or point IRQRACE_CLAUDE_CLI "
            "at the executable."
        ) from None

    deadline = time.monotonic() + timeout_s
    pending_input: str | None = stdin
    while True:
        try:
            stdout, stderr = proc.communicate(input=pending_input, timeout=0.5)
            return proc.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            pending_input = None  # already written; communicate() must not resend it
            if stop_checker is not None and stop_checker():
                proc.kill()
                proc.communicate()
                raise InterruptedError("stopped by the user during a claude -p call")
            if time.monotonic() > deadline:
                proc.kill()
                proc.communicate()
                raise BackendError(f"claude -p timed out after {timeout_s:.0f}s")
