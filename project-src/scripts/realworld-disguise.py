#!/usr/bin/env python3
"""A disguised copy of the 18 real-world programs, for the LLM-only reading.

    python scripts/realworld-disguise.py --out DIR [--seed 2026]

The programs are public (NIChecker's artifact) and name their planted
variables ``test_global_var1`` and the like, which can tell a model where a
violation is without any analysis. This copy keeps each program's behaviour and
changes what a memory or a name could key on:

* every comment is removed, ``blink1``-``3``'s trailing answers with them, and
  blank lines are dropped, so every line moves;
* every file-scope variable and every function defined in the file becomes a
  neutral name (``v_<word>``, ``fn_<word>``; ISR entries ``irq_<word>``), except
  ``main``, the masking API and well-known kernel/libc API functions, whose names
  say what they do and not which program this is; so do the macros the file
  defines (``K_<WORD>``), its type names (``t_<word>``), struct and union fields
  (``f_<word>``) and enum constants (``E_<WORD>``), and string literals lose
  their text (``"msg"``); locals and parameters keep their names;
* the programs become ``program_NN`` in a shuffled order.

Declarations are found with clang's AST (``-ast-dump=json``) with each program's
own defines, so the renaming covers exactly the identifiers the program
declares. Renaming every occurrence of an identifier token preserves C
semantics; the new names are checked not to collide with any word already in
the file. ``DIR/<program>.json`` holds the original program, the flows under the
new names, ``equal_priority_preemption`` from the program's C1, the name map and
``line_map`` (new line -> original line), so findings are scored against the
original ``violation.info``. Deterministic for a given seed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "bench" / "realworld"
CONFIGS = ROOT / "bench" / "configs-realworld"

_spec = importlib.util.spec_from_file_location("rd", Path(__file__).with_name("racebench-disguise.py"))
_rd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rd)
strip_comments = _rd.strip_comments

WORDS = _rd.WORDS + ("aspen birch coral drift ermine flint grove heron inlet jade knoll larch "
                     "maple north oasis prism quarry reef sable thorn umbra vale wharf yew zinc "
                     "acorn bluff crest delta ember fern gale husk ivory jet kiln loom mesa "
                     "nook opal pine quill rust shoal tide urchin vine wisp").split()

#: Functions whose name is API, not program identity: kept as they are.
KEEP = {
    "main", "disable_isr", "enable_isr", "assert",
    "spin_lock", "spin_unlock", "spin_lock_irqsave", "spin_unlock_irqrestore", "spin_lock_init",
    "outb", "inb", "outw", "inw", "outl", "inl", "outb_p", "inb_p", "readb", "writeb", "readl", "writel",
    "udelay", "mdelay", "msleep", "ndelay",
    "clear_bit", "set_bit", "test_bit", "test_and_set_bit", "test_and_clear_bit",
    "up", "down", "down_interruptible", "sema_init",
    "printk", "printf", "kmalloc", "kfree", "malloc", "free", "memset", "memcpy", "strcpy", "strlen",
    "mod_timer", "del_timer", "init_timer", "add_timer", "request_irq", "free_irq",
    "wake_up", "wake_up_interruptible", "wait_event", "wait_event_interruptible",
    "copy_to_user", "copy_from_user", "get_user", "put_user",
}

IDENTIFYING = re.compile(r"wdt|tco|pca|brake|logger|blink|i2c|watchdog|test_global", re.I)

ANSWERS = re.compile(r"^//\s*(true\s+)?violations|^//\s*false positive")


def drop_inactive(lines: list[str], predefined: set[str]) -> list[str]:
    """Blank the lines the preprocessor would skip, and the conditional directives.

    Handles ``#if 0``, ``#if NAME``, ``#ifdef``, ``#ifndef``, ``#else`` and
    ``#endif``, with ``NAME`` defined when it is in *predefined* or ``#define``d
    on an active line above; ``#if`` conditions with ``defined()``, ``&&``,
    ``||``, ``!`` and comparisons are evaluated, an undefined name counting 0.
    An ``#elif`` or anything else is refused, so nothing is guessed. The line count is kept, so line numbers still map.
    """
    defined = {name: "1" for name in predefined}
    stack: list[tuple[bool, bool]] = []  # (parent active, this branch active)

    def evaluate(cond: str) -> bool:
        expr = re.sub(r"defined\s*\(?\s*([A-Za-z_]\w*)\s*\)?", lambda m: "1" if m.group(1) in defined else "0", cond)
        expr = re.sub(r"[A-Za-z_]\w*", lambda m: defined.get(m.group(0), "0") or "1", expr)
        expr = expr.replace("&&", " and ").replace("||", " or ")
        expr = re.sub(r"!(?!=)", " not ", expr)
        if not re.fullmatch(r"[\s\d()<>=!a-z]*", expr):
            raise SystemExit(f"condition not handled: {cond}")
        return bool(eval(expr, {"__builtins__": {}}))
    out = []
    for line in lines:
        t = line.strip()
        active = all(a for _, a in stack) if stack else True
        m = re.match(r"#\s*(if|ifdef|ifndef|elif|else|endif)\b\s*(.*)", t)
        if m:
            kind, cond = m.group(1), m.group(2).strip()
            if kind == "elif":
                raise SystemExit(f"#elif not handled: {t}")
            if kind in ("if", "ifdef", "ifndef"):
                if kind == "if":
                    truth = evaluate(cond)
                else:
                    truth = cond.split()[0] in defined
                    if kind == "ifndef":
                        truth = not truth
                stack.append((active, truth))
            elif kind == "else":
                parent, truth = stack.pop()
                stack.append((parent, not truth))
            else:
                stack.pop()
            out.append("")
            continue
        if not active:
            out.append("")
            continue
        d = re.match(r"#\s*define\s+([A-Za-z_]\w*)(?:\s+(\S+))?", t)
        if d:
            value = d.group(2) or ""
            defined[d.group(1)] = value if re.fullmatch(r"\d+", value) else ("1" if not value else "1")
        out.append(line)
    return out


def programs() -> list[str]:
    return sorted(p.stem for p in CONFIGS.glob("*.yaml") if "__" not in p.stem)


KEEP_MACROS = {"NULL", "true", "false", "TRUE", "FALSE", "bool", "__init", "__exit", "__user",
               "__iomem", "inline", "FULLCODE"}


def declared(program: str, cfg: dict) -> tuple[list[str], list[str], dict[str, list[str]]]:
    """File-scope variables and defined functions of the program, from clang's AST."""
    build = cfg["subject"]["build"]
    args = ["clang-14", "-fsyntax-only", "-w", "-Wno-return-type", "-Xclang", "-ast-dump=json",
            *[f"-D{d}" for d in build.get("defines") or []],
            *[f for f in build.get("flags") or [] if f.startswith(("-D", "-std", "-I"))],
            str(SUITE / program / "main.c")]
    res = subprocess.run(args, capture_output=True, text=True)
    if not res.stdout.strip():
        raise SystemExit(f"{program}: clang produced no AST\n{res.stderr[:500]}")
    ast = json.loads(res.stdout)
    variables, functions = [], []
    other: dict[str, list[str]] = {"type": [], "field": [], "enum": []}

    def walk(node: dict) -> None:
        kind, name = node.get("kind"), node.get("name")
        if name and not node.get("isImplicit"):
            bucket = {"RecordDecl": "type", "TypedefDecl": "type", "EnumDecl": "type",
                      "FieldDecl": "field", "EnumConstantDecl": "enum"}.get(kind)
            if bucket and name not in other[bucket]:
                other[bucket].append(name)
        for child in node.get("inner", []) or []:
            if isinstance(child, dict):
                walk(child)

    for d in ast.get("inner", []):
        if not d.get("isImplicit"):
            walk(d)
    for d in ast.get("inner", []):
        if d.get("isImplicit") or "name" not in d:
            continue
        if d["kind"] == "VarDecl" and d["name"] not in variables:
            variables.append(d["name"])
        elif d["kind"] == "FunctionDecl":
            has_body = any(i.get("kind") == "CompoundStmt" for i in d.get("inner", []))
            if has_body and d["name"] not in KEEP and d["name"] not in functions:
                functions.append(d["name"])
    return variables, functions, other


def disguise(program: str, cfg: dict, rng: random.Random) -> tuple[list[str], dict[int, int], dict[str, str], list[dict]]:
    raw = (SUITE / program / "main.c").read_text(encoding="utf-8", errors="replace").splitlines()
    cut = next((i for i, l in enumerate(raw) if ANSWERS.match(l)), len(raw))
    clean = strip_comments(raw[:cut])
    predefined = {d.split("=", 1)[0] for d in cfg["subject"]["build"].get("defines") or []}
    clean = drop_inactive(clean, predefined)
    # String literals keep their quotes and lose their text.
    clean = [re.sub(r'"(?:[^"\\\n]|\\.)*"', '"msg"', l) for l in clean]
    variables, functions, other = declared(program, cfg)
    macros = []
    for l in clean:
        m = re.match(r"\s*#\s*define\s+([A-Za-z_]\w*)", l)
        if m and m.group(1) not in KEEP_MACROS and m.group(1) not in macros:
            macros.append(m.group(1))
    isr_entries = {f["entry"] for f in cfg["flows"] if f["kind"] == "isr"}
    existing = set(re.findall(r"[A-Za-z_]\w*", "\n".join(clean)))
    pool = [w for w in WORDS]
    rng.shuffle(pool)
    names: dict[str, str] = {}
    counter = 0

    def fresh(prefix: str) -> str:
        nonlocal counter
        while True:
            word = pool[counter % len(pool)]
            name = f"{prefix}{word}" if counter < len(pool) else f"{prefix}{word}{counter // len(pool)}"
            counter += 1
            if name not in existing and name not in names.values():
                return name

    for v in sorted(variables, key=lambda n: (-len(n), n)):
        names[v] = fresh("v_")
    for f in sorted(functions, key=lambda n: (-len(n), n)):
        names[f] = fresh("irq_" if f in isr_entries else "fn_")
    taken = set(names) | KEEP | KEEP_MACROS
    for m in sorted(set(macros) - taken, key=lambda n: (-len(n), n)):
        names[m] = fresh("K_").upper().replace("K_", "K_", 1)
    taken = set(names) | KEEP | KEEP_MACROS
    for kind, prefix in (("type", "t_"), ("field", "f_"), ("enum", "E_")):
        for n in sorted(set(other[kind]) - taken, key=lambda n: (-len(n), n)):
            new = fresh(prefix)
            names[n] = new.upper() if prefix == "E_" else new
            taken.add(n)
    # Anything left that still names the program family (a local, a macro's
    # value, a name the C1 defines on the command line) is renamed the same way.
    leftover = sorted({t for l in clean for t in re.findall(r"[A-Za-z_]\w*", l)
                       if IDENTIFYING.search(t) and t not in names}, key=lambda n: (-len(n), n))
    for t in leftover:
        names[t] = fresh("x_")
    if names:
        pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")\b")
        renamed = [pattern.sub(lambda m: names[m.group(1)], l) for l in clean]
    else:
        renamed = clean
    out, line_map = [], {}
    for orig, text in enumerate(renamed, 1):
        if text.strip():
            out.append(text)
            line_map[len(out)] = orig
    flows = [{"entry": names.get(f["entry"], f["entry"]), "kind": f["kind"], "priority": f["priority"],
              "irq": f.get("irq")} for f in cfg["flows"]]
    return out, line_map, names, flows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    progs = programs()
    numbers = list(range(1, len(progs) + 1))
    rng.shuffle(numbers)
    index = {}
    for prog, num in zip(progs, numbers):
        cfg = yaml.safe_load((CONFIGS / f"{prog}.yaml").read_text())
        src, line_map, names, flows = disguise(prog, cfg, rng)
        name = f"program_{num:02d}"
        text = "\n".join(src) + "\n"
        leaks = [w for w in ("test_global", prog, "violation", "NIChecker", "BMC4AV") if w.lower() in text.lower()]
        if leaks:
            print(f"warning: {name} ({prog}) still contains {leaks}", file=sys.stderr)
        (out / f"{name}.c").write_text(text)
        (out / f"{name}.json").write_text(json.dumps(
            {"program": name, "case": prog, "flows": flows,
             "equal_priority_preemption": cfg["semantics"]["equal_priority_preemption"],
             "names": names, "line_map": {str(k): v for k, v in line_map.items()}}, indent=2))
        index[name] = prog
    (out / "index.json").write_text(json.dumps({"seed": args.seed, "programs": index}, indent=2))
    print(f"{len(progs)} programs disguised into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
