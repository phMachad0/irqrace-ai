---
type: project
tags: [wiki, project, diario, pt-br]
sources: ["[[Roadmap]]", "[[Pipeline Design]]", "[[LLM Stage Design]]", "[[Triples Only]]", "[[Soundness Assumptions]]", "[[Racebench]]", "[[LLM Triage]]", "[[Precision Metrics]]"]
updated: 2026-10-29
status: draft
---

# Semana 8 — Integração das Trilhas A e B

**Período planejado:** 19–23 out 2026 · **feito em:** 23–26 out 2026 · **Trilha B**, sobre o
`track-b/llm-integration` · [[Roadmap]] W8 (*Integration*, marco M4). Páginas anteriores:
[[Semana 5 a 8 — Trilha B (Triagem, Ablação, Reparo e Integração C3-C4)]] (a Trilha B até a W8)
e [[Semana 7 — O Stage 3, Busca e Verificação]] (a Trilha A).

> [!note] O que esta página cobre
> A semana em que a Trilha B deixou de rodar sobre *fixtures* e sobre estágios simulados e passou a
> rodar sobre o que a Trilha A produz de verdade. Ela começou com um relatório PDF cujas
> classificações não faziam sentido e terminou com o *merge* da `main` (a Trilha A das semanas 5–7),
> a [[Triples Only|decisão de usar só trincas]] aplicada à Trilha B e o aplicativo desktop rodando os
> stages 2 e 3 reais. No caminho, quase tudo que estava errado era o mesmo defeito em lugares
> diferentes: **um resultado que ninguém calculou, apresentado como se tivesse sido calculado.**

## 1. O que a semana devia entregar

O [[Roadmap]] dá a W8 duas vezes, uma por trilha. Os itens e o estado ao fim da semana:

| Item do Roadmap (W8) | Estado | Onde |
| --- | --- | --- |
| Registros de contexto reais substituem os *fixtures* | **pronto** — desktop e CLI triam os registros que o stage 3 escreve | `ui/desktop.py`, `llm/pipeline.py` |
| O *resolver* C4 atrás do protocolo da Trilha B, sobre candidatos reais | **pronto, com uma correção** — `masking_state_at` quebrava em registros do stage 1 (§3.8) | `llm/resolver.py` |
| Execução ponta a ponta no Racebench com o pipeline da Trilha B | **parcial** — ponta a ponta em `svp_simple_001_001` (build → stage 3 → triagem); a triagem dos 31 casos ainda não rodou | `ui/desktop.py`, `irqrace llm triage` |
| Refazer os números sobre o resíduo pós-Z3, sem reaproveitar os dos *fixtures* | **não feito** — a avaliação por estágio existe (§3.7), falta a bateria de triagem | `run_evaluation.py` |
| Marco M4 | **parcial** | — |

Fora do Roadmap, mas feito nesta semana porque a integração dependia disso: a correção do caminho
do código-fonte (§3.1), a chave do *cache* (§3.2), a triagem que não descarta (§3.3), um quarto
*backend* de LLM (§3.4) e a remoção de tudo que fingia a análise estática (§3.6).

## 2. Conceitos usados nesta página

**Registro de contexto (C2).** O documento JSON que descreve um candidato para a LLM: a variável
compartilhada, os três acessos com arquivo e linha, os fluxos (a tarefa `main` e as ISRs, as
rotinas de interrupção), o estado da máscara de interrupções, o veredito do *solver* e
`enclosing_source`, o corpo das funções que contêm os acessos. É o contrato entre as trilhas
(`contracts/c2-context-record.schema.json`).

**Trinca (A₁, B, A₂).** O único tipo de candidato desde 24 out: dois acessos `A₁` e `A₂` do mesmo
fluxo e um acesso remoto `B`, de outro fluxo, que cai entre eles. Se essa intercalação produz um
estado que nenhuma execução sequencial produziria, é uma [[Atomicity Violation|violação de
atomicidade]]. Antes existiam também os pares (*race pairs*), dois acessos em fluxos diferentes; eles
saíram do projeto ([[Triples Only]]).

**Stage 2 e stage 3.** Os dois filtros da Trilha A. O stage 2 decide, por prioridade e máscara de
interrupções, se o fluxo de `B` pode mesmo rodar entre `A₁` e `A₂`; o stage 3 codifica o programa
para o *solver* Z3 e pergunta se a intercalação é alcançável. Os dois podem **descartar** um
candidato, mas só com prova: o stage 2 grava a prova em texto em `stage2/dropped.jsonl`, e o stage 3
só descarta com `unsat` (o Z3 provou que a intercalação é impossível). `sat` quer dizer "não
refutado", não "bug confirmado".

**Ground truth, recall gate e armadilhas.** O [[Racebench]] anota, em cada caso, os *bug points*
(trincas reais, 48 nos 31 casos simples) e as armadilhas (*traps*, trincas que parecem bug e não são,
38). O *recall gate* é a regra do projeto: todo *bug point* anotado tem de chegar ao relatório
(48/48). "Armadilhas vivas" é quantas armadilhas ainda estão na lista depois de um estágio.

**Inspection Ratio (IR).** A fração da lista ordenada que alguém precisa ler para encontrar todos os
*bug points*: `(posição do último bug + 1) / tamanho da lista`. Só é definido quando todo bug foi
detectado ([[Precision Metrics]]).

**Bucket.** O grupo em que a triagem coloca o candidato: `likely_real`, `uncertain`,
`likely_benign`, `likely_infeasible`. Os *buckets* só ordenam a leitura; **nenhum candidato sai do
relatório por causa da LLM** — só uma prova tira um candidato.

**Cache de respostas da LLM.** Um diretório (`.llm-cache/`) com uma resposta por arquivo, para não
pagar de novo a mesma pergunta. A chave do arquivo diz o que conta como "a mesma pergunta".

**DWARF e `comp_dir`.** O DWARF é o formato das informações de depuração que o `clang -g` grava no
*bitcode*: para cada instrução, de que arquivo e linha ela veio. O nome do arquivo pode vir partido
em duas partes, o diretório de compilação (`comp_dir`) e um caminho relativo a ele.

**Merge e conflito.** Integrar no `track-b` os *commits* da `main`. Quando os dois lados mudaram o
mesmo trecho, o git não escolhe sozinho e marca um conflito, que é resolvido à mão.

## 3. O que foi feito, na ordem em que aconteceu

### 3.1. O relatório que não fazia sentido — a LLM nunca tinha visto código

O ponto de partida foi um PDF do desktop para `svp_simple_001_001` (23 out). A trinca do bug,
`(32, 55, 35)`, estava na lista mas saiu `uncertain`; o par `(32, 60)` saiu `likely_real` e ganhou
*patch*; e os *patches* citavam `compute(i)`, `some_value` e `N`, que não existem no arquivo.

A causa principal: **`enclosing_source` estava vazio em todos os 23 registros.** O `clang` gravou o
arquivo como `directory: /home/pedro/Documentos/tcc` mais `filename: racebench/2.1_remarks/...`, o
stage 1 só emite o *filename*, e o Python abria esse caminho relativo a partir de `project-src`, não
achava, e engolia o erro. O modelo triou e "corrigiu" código que nunca leu. A correção:

`project-src/src/irqrace/stage1.py`
```python
def _source_lines(file: str, root: str = ".") -> list[str]:
    """The lines of *file*, or ``[]`` when it cannot be found.

    Debug info may name a file relative to the compilation directory, which the
    analysis does not emit: clang splits ``/a/b/racebench/x.c`` into directory
    ``/a/b`` and filename ``racebench/x.c``. Such a name resolves against no
    fixed directory, so try the working directory, then ``root`` and each of its
    ancestors. Without this the record silently ships no source at all.
    """
    path = Path(file)
    if path.is_absolute():
        candidates = [path]
    else:
        base = Path(root).resolve()
        candidates = [path, base / path, *(d / path for d in base.parents)]
    for c in candidates:
        try:
            return c.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
    return []
```

Os ids dos candidatos não mudaram, porque o *fingerprint* cobre a localização dos acessos, não o
código. Isso importa para o próximo problema.

### 3.2. O cache servia as respostas antigas

> **Decisão revertida:** o cache de respostas foi removido do projeto em 30 out (§3.19).

Com o código-fonte nos registros, o app continuou mostrando as mesmas classificações. A chave do
*cache* era `(fingerprint, configuração de prompt, modelo, schema)`, e o *fingerprint* não tinha
mudado: o *cache* devolvia as respostas que o modelo deu **sem** ver o código. A chave passou a
incluir um *hash* do que o modelo vê:

`project-src/src/irqrace/llm/client.py`
```python
def evidence_hash(record: dict[str, Any]) -> str:
    """Identity of what the model is shown about *record*, for the cache key.

    The rendered record, minus ``solver_result.wall_ms``: timing differs on every
    run and changes no answer, so keeping it would defeat the cache's purpose of
    surviving a re-run of the analyzer.
    """
    shown = json.loads(json.dumps(record))
    if isinstance(shown.get("solver_result"), dict):
        shown["solver_result"].pop("wall_ms", None)
    return hashlib.sha256(render_record(shown).encode("utf-8")).hexdigest()
```

O tempo do *solver* fica de fora de propósito: muda a cada execução e não muda a resposta.

### 3.3. A triagem descartava candidatos em silêncio

Rodada de novo com o código-fonte (CLI, 23 out), a triagem levou 67 minutos e terminou com status
`ok` e **7 de 23** candidatos; os outros 16 tinham ido para uma lista `excluded` por erro de API
(provável limite de taxa, com o app rodando ao mesmo tempo na mesma chave), sem motivo gravado. No
app, mais tarde, foram 3 de 13. Isso fere a regra central do projeto — a LLM não descarta — e agora
um candidato sem resposta continua no relatório, como `uncertain`, com o motivo:

`project-src/src/irqrace/llm/verdict.py`
```python
    def untriaged(cls, record: dict[str, Any], reason: str) -> "Triage":
        """The verdict for a candidate the stage could not get an answer for.

        A backend error, a refusal or an interrupted run is not evidence about
        the candidate, so it must not remove it from the report: it lands in
        ``uncertain`` -- inspected, never hidden -- with the reason attached.
        Confidence 0 places it last within that bucket, below every candidate a
        model actually looked at.
        """
        return cls(
            candidate_id=record["id"],
            fingerprint=record["fingerprint"],
            feasibility=FeasibilityAnswer(
                reasoning=f"Not triaged: {reason}",
                verdict=Feasibility.uncertain,
                confidence=0.0,
            ),
            not_triaged=reason,
```

`project-src/src/irqrace/llm/pipeline.py`
```python
    # A candidate no sample could triage stays in the report as uncertain, with
    # the reason: a backend error is not evidence about the candidate.
    answered = {t.candidate_id for t in final}
    reasons = dict(excluded)
    for rec in records:
        if rec["id"] not in answered:
            reason = reasons.get(rec["id"], "no verdict was produced")
            final.append(Triage.untriaged(rec, reason))
            store.log("warn", "triage", "candidate-not-triaged",
                      f"{rec['id']}: {reason}", candidate_id=rec["id"])
```

O mesmo vale para o *loop* próprio do desktop, para o botão *Stop* no meio da triagem e para o modo
*offline*. Se **todos** falham, a etapa termina `failed`: isso é explícito, não silencioso.

Duas observações sobre a qualidade das respostas daquela rodada, que continuam valendo e estão em
aberto: com o código à vista, o modelo marcou a trinca do bug como `likely_benign` porque
"`reader1` nunca é usado" — verdade no código do Racebench, cujos leitores são variáveis mortas, mas
o gabarito conta a leitura do valor intermediário como o bug (o `log.md` registra a decisão de 27 set
de não pontuar nocividade no Racebench); e acertou a armadilha 2 pelo motivo errado, porque o
`enable_isr(2)` estava na `isr_1`, fora do `enclosing_source`. Com o stage 2 real, esse fato chega
pronto ao modelo em `masking.interval.reenabled_within_interval_by`.

### 3.4. Um quarto *backend*: `claude -p` na assinatura

`claude-cli:<modelo>` chama o Claude Code em modo não interativo, com o *login* da assinatura Pro/Max
em vez de créditos de API: o consumo entra no limite do plano, sem cobrança por *token*. A CLI
valida a resposta contra o JSON Schema (`structured_output`), então o nível de saída estruturada é o
mesmo dos outros *backends*. A chamada é isolada para que só o prompt da triagem chegue ao modelo:

`project-src/src/irqrace/llm/backends/claude_cli_backend.py`
```python
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
```

O processo roda numa pasta temporária vazia (sem `CLAUDE.md`), e as credenciais de API saem do
ambiente, para que uma chave esquecida não transforme uma rodada do plano em cobrança:

```python
def _subscription_env() -> dict[str, str]:
    env = dict(os.environ)
    for var in _API_AUTH_VARS:
        env.pop(var, None)
    return env
```

A flag `--bare` faria quase tudo isso de uma vez, mas ela recusa o *login* da assinatura. Testado ao
vivo: 2 chamadas com `claude-cli:haiku` na *fixture* do bug de `svp_simple_001`, 40 s.

### 3.5. Os stages 2 e 3 eram simulados — e a primeira correção foi só dizer isso

O desktop tinha uma etapa "Stage 2 & 3" que copiava os candidatos do stage 1 para `stage2/` e
escrevia, para **todo** candidato, um resultado do Z3 inventado (`"verdict": "inconclusive"`,
`"reason": "timeout"`, `"wall_ms": 12`), com tempos fixos de 45 e 380 ms no *manifest*. O PDF
mostrava "Solver Z3 · OK · 380 ms". A reverificação dos *patches* também era marcada `ok`, com
`dropped_with_proof` igual ao número de *patches*.

Como a Trilha A ainda não estava integrada, a primeira correção (24 out) não ligou nada: marcou as
etapas como `skipped`, com o motivo, e deixou os registros do stage 1 chegarem ao modelo como eram
(`solver_result: not_run`, máscara `unknown`). Um teste de integração local com a Trilha A (23 out,
desfeito no mesmo dia, documentado fora do repositório) já tinha mostrado o funil real
`23 → 19 → 13` nesse caso, ainda com pares.

### 3.6. O *merge* da `main` e a remoção do que fingia a análise estática

Com a Trilha A na `main` (PR #2), o `track-b` recebeu o *merge* (`be88e35`). O código mergeou
sozinho; os conflitos foram só de documentação (`index.md`, `log.md`, o README e três páginas da
wiki, estas só no `updated:`), resolvidos como união, com a `main` como referência onde as versões se
sobrepunham, como a [[Triples Only|Issue #1]] pedia. O binário `irqrace-probe`, que a `main` deixou de
versionar, saiu do índice e ficou no disco.

Depois do *merge*, a etapa "Stage 2 & 3" do desktop chama as mesmas funções que `irqrace stage3`:

`project-src/src/irqrace/ui/desktop.py`
```python
        log_fn("  Stage 2: análise de máscara de interrupções e prioridade (ponto fixo)...")
        s2 = stage2(self.cfg, self.store)
        reasons = ", ".join(f"{k}: {v}" for k, v in sorted(s2["reasons"].items())) or "nenhum"
        log_fn(
            f"  Stage 2: {s2['in']} entrada -> {s2['kept']} mantidos, "
            f"{s2['dropped']} descartados com prova ({reasons}) [{s2['wall_ms']} ms]"
        )
        for d in self.store.read_drops():
            log_fn(f"    - {d['candidate_id']} {d['pattern']} {d['lines']} [{d['reason']}]")

        log_fn("  Stage 3: execução simbólica sobre o IR com Z3...")
        s3 = stage3(self.cfg, self.store, bitcode)
```

A etapa de contexto deixou de apagar `context/` e reconstruir os registros, porque isso jogaria fora
o veredito e a nota de proveniência que o stage 3 escreve. E foi removido tudo que apresentava
resultados de análise estática que ninguém calculou:

- **`scripts/seed-showcase-run.py`**, que escrevia `stage2/`, `solver/`, triagem, *diffs* sintéticos
  e reverificação `ok` para os 31 casos — inclusive marcando candidatos `unsat` por heurística, ou
  seja, inventando provas.
- **No dashboard**, a tabela do funil por estágio — exportável em Markdown/LaTeX "para o TCC" —
  acrescentava "(100%)" a todo *recall*, supunha 1 bug e 2 armadilhas quando não havia relatório,
  contava todo `unsat` como armadilha e mostrava a reverificação como "PASS / 100% eliminado /
  Verificado". A página inicial afirmava "48/48 bugs", "Zero falsos negativos" e "80%–95%" de
  rejeição de armadilhas, para qualquer conjunto de *runs*. O painel de reparo dizia que todo
  *patch* tinha sido reverificado.
- **No PDF**, um Inspection Ratio fixo em "1.00 (Ótimo)" (calculado e nunca exibido) e
  `likely_infeasible` chamado de "armadilhas rejeitadas".

### 3.7. A avaliação por estágio, calculada

No lugar dos números fixos, um módulo pequeno avalia um *run* estágio a estágio contra a *ground
truth*, com a mesma regra de casamento do `irqrace stage3-all`
(`project-src/src/irqrace/run_evaluation.py`). Ele avalia os candidatos do stage 1, os do stage 2, os
registros que chegam à LLM e, quando a triagem rodou, os mesmos registros **na ordem da triagem** — a
triagem não descarta nada, então o que ela muda é a ordem, que é o que o Inspection Ratio mede. Um
caso sem *ground truth* nesta máquina não recebe número nenhum; um estágio que não rodou mostra "-".

Conferido contra os `eval/report.json` que a Trilha A gravou nos 31 casos: **0 divergências**, e os
totais reproduzem o funil dela — *recall* 48/48, armadilhas vivas 35 → 30 → 16 de 38.

No desktop, ponta a ponta em `svp_simple_001_001`:

| Estágio | Candidatos | Recall | Armadilhas vivas | IR |
| --- | --- | --- | --- | --- |
| Stage 1 | 14 | 1/1 | 2/2 | 0,29 |
| Stage 2 (4 descartes por prioridade) | 10 | 1/1 | 2/2 | 0,40 |
| Chegam à LLM (4 `unsat` no Z3) | 6 | 1/1 | 1/2 | 1,00 |

O IR sobe porque a lista encolhe e o bug fica por último nela: com 6 candidatos, é preciso ler todos.

### 3.8. Um bug real que o *run* falso escondia

Depois de apagar o *showcase*, o teste que percorre o dashboard passou a abrir o primeiro *run* real
da lista, que só tinha o stage 1, e quebrou: o *resolver* C4 de `masking_state_at` lia
`access["masking"]`, e um registro do stage 1 ainda não tem máscara. Enquanto o dashboard abria o
*run* fabricado, que tinha máscara inventada, isso nunca apareceu. Agora a máscara não calculada é
respondida como `unsupported` — "trate como desconhecido, prefira `uncertain`" — e nunca como
habilitada ou desabilitada:

`project-src/src/irqrace/llm/resolver.py`
```python
    def _masking_at(self, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
        line, file = args.get("line"), args.get("file")
        per_role = {
            m["role"]: m["state"]
            for m in (self.record.get("masking") or {}).get("per_access", [])
        }
        for access in self.record["accesses"]:
            src = access["source"]
            if src["line"] == line and (file is None or src["file"] == file):
                state = access.get("masking") or per_role.get(access["role"])
                if state is None:
                    # A stage-1 record: stage 2 has not computed masking yet.
                    # The state is unknown, not enabled and not disabled.
                    return {}, "unsupported"
                return {
                    "file": src["file"],
                    "line_start": line,
                    "line_end": line,
                    "masking": state,
                }, "ok"
```

### 3.9. Só trincas na Trilha B (Issue #1)

A parte da [[Triples Only|decisão de 24 out]] que cabia à Trilha B (`bda61f2`):

- **Fixtures**: o gerador emite `c2/2.0.0` e as 20 foram regeneradas. Todas já eram trincas, então
  só a versão mudou — exceto `svp_simple_006-trap-2`, cujo código passou a ter o `j < 5` que a Trilha
  A corrigiu no Racebench local (errata de 22 out). Era a *fixture* que o teste de "fixtures
  atualizadas" acusava havia dias.
- **Prompts**: `base.md` só define a trinca; `repair.md` perdeu a estratégia `mask_access` e a regra
  de escopo dos pares.
- **Reparo**: `mask_access` saiu do vocabulário fechado — numa trinca ela protege uma ponta e deixa o
  intervalo onde o acesso remoto cai, então nunca foi um reparo válido aqui:

`project-src/src/irqrace/llm/repair.py`
```python
class Strategy(str, enum.Enum):
    """The closed repair vocabulary. No mutex, by construction."""

    #: disable_isr(n) before A1, enable_isr(n) after A2.
    mask_interval = "mask_interval"
    #: Widen a critical section that already exists nearby.
    extend_section = "extend_section"
    #: Merge two adjacent sections whose gap is the defect.
    merge_sections = "merge_sections"
```

- **Interface**: o desktop, o PDF e o dashboard falam em "trincas (A1, B, A2)", não em pares e
  triplas.

### 3.10. O estudo da triagem e o registro que decide o caso

Um bug do 001 classificado como `uncertain` levou a um estudo em 15 dos 31 casos do Racebench
([[Triage Study 2026-10-26]]): 101 candidatos triados pelo terminal com `claude-cli:sonnet` e quatro
agentes analisando cada bug e cada armadilha contra o código-fonte. Para isso a CLI ganhou dois
comandos: `irqrace pipeline`, que roda as mesmas etapas do desktop pelo mesmo objeto
(`PipelineStepper`), e `irqrace llm report`, que cruza cada candidato com a *ground truth*, o
estágio em que saiu da pipeline e a triagem.

O achado principal: **o registro não trazia o código que decide o caso.** O stage 1 montava `flows`
e `enclosing_source` só com as funções que contêm os três acessos. Quando o fluxo citado em
`masking.interval.reenabled_within_interval_by` faltava, 12 de 16 respostas saíam `uncertain`;
quando estava, 78 de 85 saíam `feasible`. Acrescentar à mão só o que faltava resolveu os casos
analisados. O estudo achou também um **vazamento de *ground truth***: o `line_end + 1` mostrava ao
modelo a linha seguinte à função, que no Racebench é o cabeçalho `//bug点:` das anotações — em 50 dos
101 registros.

Três mudanças, todas gerais (nenhuma regra fala do Racebench):

**(1) A função vai até a chave que a fecha.** A extensão agora é achada contando chaves a partir da
primeira linha, ignorando comentários e literais:

`project-src/src/irqrace/source_context.py`
```python
def function_extent(lines: list[str], start: int, hint_end: int | None = None) -> int | None:
    """Last line of the function whose definition starts on ``start`` (1-based).

    Counts braces from ``start``, ignoring comments and literals, and returns
    the line where the body's opening brace is closed. ``None`` when the braces
    do not balance within the file (macro-generated bodies, say); the caller
    then falls back to ``hint_end``, never to a line past it.
    """
    depth, opened, in_block = 0, False, False
    for n in range(start, len(lines) + 1):
        code, in_block = _code_only(lines[n - 1], in_block)
        for ch in code:
            if ch == "{":
                depth, opened = depth + 1, True
            elif ch == "}":
                depth -= 1
                if opened and depth == 0:
                    return n
        if not opened and code.rstrip().endswith(";"):
            return None  # a prototype, not a definition
    return hint_end
```

**(2) O registro leva o que o caso depende.** `flows` passa a ter todos os fluxos configurados, e
`enclosing_source` acrescenta as funções dos caminhos de chamada, o código de todo fluxo que toca a
variável ou muda a máscara de interrupções (*masking*), e funções chamadas curtas — com um limite de
tamanho. O critério dos fluxos:

`project-src/src/irqrace/stage1.py`
```python
        touching = {a["function"] for a in self.accesses.values() if a["object"] == obj["id"]}
        for flow in self.flows.values():
            reach = self._reachable(flow.entry)
            relevant = [f for f in reach if f in touching or self._calls_primitive(f)]
            if relevant:
                add(flow.entry)
                for f in relevant:
                    add(f)
```

Na proveniência (`provenance`, a lista de fatos com o status de cada um) entram: `writers.<variável>`
— cada ponto do programa que escreve na variável do candidato e em toda variável compartilhada que o
código mostrado lê, com a declaração e se a lista é **completa** (`proven`) ou pode não ser
(`unknown`); o que o C1 diz das primitivas de máscara e das funções externas (`assumed_from_config`);
e as macros usadas. Uma condição (*guard*) só pode ser "nunca verdadeira" sobre uma lista completa de
escritas — por isso o status. Nenhum id mudou, porque o *fingerprint* não depende desses campos, e o
contrato C2 continua `c2/2.0.0`: só a descrição de `flows` e `enclosing_source` foi atualizada.

**(3) O prompt explica os campos.** O `base.md` agora diz o que significam `masking.per_access` (o
estado **em todo caminho e com todo fluxo que pode rodar antes**, então um `disable_isr` visível não o
contradiz), `masking.interval`, o `sat` do solver (evidência, não prova), as listas de escritas, os
modelos do C1 e os `null` de `static_features` ("não calculado", nunca "falso"). O código vai
numerado com as linhas do arquivo.

**O resultado**, nos mesmos 15 casos (uma amostra cada):

| | antes | depois |
| --- | --- | --- |
| bugs chamados `feasible` | 18 de 23 | **23 de 23** |
| bugs chamados `infeasible` | 0 | 0 |
| armadilhas genuínas rejeitadas | 1 de 11 | **8 de 11** |
| armadilhas em disputa chamadas `infeasible` | 0 de 5 | 0 de 5 |
| Inspection Ratio médio (só viabilidade) | 0,67 | **0,55** |

As oito rejeições citam o elemento bloqueador certo — em cinco, "a ISR limpa a *flag* antes de
desmascarar a leitora". As três armadilhas que ainda passam são as duas classes que não foram
mexidas: a definição de "mesma posição de memória" (007) e as trincas subsumidas (022). O bug do
caso 001 (`cf213e…`), que abriu o estudo, agora sai `feasible`. A nocividade não mudou e ainda põe 11
dos 23 bugs em `likely_benign` (leitores mortos); é o próximo item.

### 3.11. Itens 4 a 6 e uma linha de prompt com a semântica do Racebench

**Mesma posição de memória (item 4).** O `base.md` agora define a trinca sobre **uma** posição: a
mesma variável e, num array ou ponteiro, o mesmo elemento. A tabela de domínio ganhou a linha "B
toca outra posição em todo caminho", que só vale com o argumento (os valores do índice ou do
ponteiro); um índice que não dá para determinar pode coincidir.

**Duas perguntas, dois prompts (item 5).** A checagem de autovalidação (*self-validation*) puxa
para `uncertain` por motivos de alcançabilidade, e estava sendo aplicada também à pergunta de
nocividade. Agora cada pergunta recebe o seu prompt de sistema: a de viabilidade fica com a tabela
de domínio e a checagem; a de nocividade recebe um critério **por padrão** (`harmfulness.md`: em WRW
importa o que B lê, em RWR a releitura de A2, em RWW a escrita perdida, em WWR o que A2 lê) e uma
checagem curta, própria.

**Para onde vai o valor lido (item 6, em parte).** O Stage 1 em C++ passou a seguir, dentro da
função, o valor de cada leitura (*def-use*: de onde um valor é definido até onde é usado), inclusive
através de variáveis locais:

`project-src/analysis/src/irqrace-stage1.cpp`
```cpp
      } else if (const auto *st = llvm::dyn_cast<llvm::StoreInst>(ui)) {
        if (st->getPointerOperand() == v) {
          u.deref = true;
        } else if (const auto *al = llvm::dyn_cast<llvm::AllocaInst>(
                       st->getPointerOperand()->stripPointerCasts())) {
          // Stored into a local: follow its loads.
          for (const llvm::User *au : al->users())
            if (const auto *al2 = llvm::dyn_cast<llvm::LoadInst>(au))
              work.push_back(al2);
            else if (!llvm::isa<llvm::StoreInst>(au) &&
                     !llvm::isa<llvm::DbgInfoIntrinsic>(au))
              u.escapes = true; // the local's address is taken
        } else {
          u.escapes = true; // stored to global or heap memory
```

Com isso, `feeds_branch` e `used_as_index` deixaram de ser sempre `null`: são calculados sobre as
leituras que importam em cada padrão, e só ficam `null` quando o valor escapa da função.

`project-src/src/irqrace/stage1.py`
```python
    MATTERING_READS = {"RWR": ("A1", "A2"), "WWR": ("A2",), "WRW": ("B",), "RWW": ("A1",)}
```

Ficou de fora do item 6: *points-to* sensível à ordem das instruções e limitar os valores que o
Stage 3 supõe para escritas de outros fluxos — mudanças no uso do SVF e na codificação do Z3.

**Uma linha experimental, `+racebench`.** Um agente leu a documentação DeepWiki do Racebench e
redigiu um asset (`racebench_semantics.md`), conferido contra o README e o `common.c` do benchmark,
sem exemplos nem nomes de casos (a proveniência de cada regra está em
`project-src/docs/racebench-prompt-rationale.md`). As regras principais: a intercalação já é o
defeito, sem precisar de efeito visível; mesma posição = mesmo armazenamento; **A1 e A2 precisam ser
adjacentes** (se o mesmo fluxo toca a posição de novo no meio, o benchmark conta a trinca mais fina);
e o modelo de chegada de interrupções do README. Ele entra como uma linha à parte, nunca na tabela
de ablação.

Nos mesmos 15 casos, uma amostra cada:

| | itens 1–3 | + itens 4–6 | `+racebench` |
| --- | --- | --- | --- |
| bugs em `likely_real` | 10 de 23 | 8 de 23 | **23 de 23** |
| armadilhas genuínas rejeitadas | 8 de 11 | 9 de 11 | **10 de 11** |
| armadilhas em disputa chamadas `infeasible` | 0 de 5 | 0 de 5 | 0 de 5 |
| Inspection Ratio médio (buckets) | 0,59 | 0,63 | **0,44** |

**Decisão registrada.** A regra de adjacência julga *redundância*, não alcançabilidade: a
intercalação é possível, o benchmark só conta outra trinca no lugar. Por isso ela fica na linha
experimental e não vai para o prompt de produção, onde marcaria como "impossível" algo que pode
acontecer. A leitura para a monografia: no Racebench, a diferença entre as linhas é sobretudo de
**definição** (o que o benchmark chama de defeito), não de raciocínio — a viabilidade dos bugs já
estava em 23 de 23.

### 3.12. A pipeline inteira nos 31 casos

Com o cache das respostas da LLM apagado, a ferramenta inteira rodou nos 31 casos simples do
Racebench com `claude-cli:sonnet` e a linha `+racebench`, quatro casos em paralelo
([[Racebench Full Run 2026-10-28]]). A pontuação usa a regra da competição NASAC 2019 (+2 por bug
detectado, −3 por armadilha reportada) sobre a *ground truth* medida (48 bugs, 38 armadilhas);
detecções que o benchmark não anota nem como bug nem como armadilha não contam como falso positivo.
O script que pontua é `project-src/scripts/bench-triage-report.py`.

| "reportado" = | bugs | armadilhas reportadas | pontos (máx. 96) |
| --- | --- | --- | --- |
| bucket `likely_real` da LLM | 46 de 48 | 5 de 38 | **77** |
| tudo que a LLM não chamou de inviável | 46 de 48 | 6 de 38 | 74 |
| só os estágios estáticos | 48 de 48 | 16 de 38 | 48 |

As 5 armadilhas reportadas são exatamente as 5 "em disputa", que a semântica do próprio README torna
alcançáveis. Os 2 bugs perdidos (017) foram rejeitados pela **regra de adjacência** do prompt do
Racebench — que o próprio gabarito do 017 contradiz, porque anota essas trincas não-adjacentes como
bugs. Decisão: a regra deve sair do prompt. Tempo total: 956 s (≈16 min) com quatro casos em
paralelo, 256 chamadas à LLM; os estágios estáticos somam 29 s nos 31 casos — 99% do tempo é a LLM.

**Segunda rodada, sem a regra de adjacência:** 48 de 48 bugs em `likely_real`, 8 armadilhas
reportadas, **72 pontos**. A pontuação tinha um artefato: a regra de casamento compara as linhas e
não o tipo de acesso, e quando dois candidatos dividem as mesmas linhas (a linha 29 do 017 escreve e
lê a variável) pegava o primeiro. Agora prefere o "irmão" cujos tipos batem com a anotação. Na
análise caso a caso, 5 das 8 armadilhas reportadas são **erros do gabarito** sob a semântica do
próprio README (001 #1, 019 #2–#4, 020 #1 — a do 019 #2 ficou desatualizada quando o código do
`2.1_remarks` mudou), 2 são "possíveis falsos positivos" que o próprio anotador marcou como dúvida
(022), e 1 é erro do modelo (007, que acertou na primeira rodada). Com o gabarito corrigido: 87 de 96.

### 3.13. O gabarito corrigido e a variância

Por decisão do Pedro, as cinco armadilhas que a revisão mostrou serem alcançáveis pela semântica do
próprio README viraram **bugs no fonte do Racebench** (na época em `../racebench/2.1_remarks`, sem
commit, visível pelo `git diff` de lá; desde 29/10 a suíte está dentro do repositório e a mudança é
um commit próprio — ver §3.14): 001 armadilha 1, 019 armadilhas 2–4 e 020 armadilha 1. O total dos casos
simples passou de **48 bugs e 38 armadilhas para 53 e 33**. Todo número anterior a 28/10 usa 48/38;
a mudança está registrada na errata (`relabel_2026_10_28`), no protocolo de avaliação, na página
[[Racebench]], em [[Contradictions]] #7–#8, no `CLAUDE.md` e nas constantes de
`evaluation.py`. As correções de linha do 019 foram escritas no próprio fonte, então saíram da
errata (12 → 6 correções). A fixture da Trilha B que usava a antiga armadilha do 001 virou a
armadilha que continua no gabarito (`array[1000]` contra `array[9999]`).

Com os rótulos novos o *recall gate* estático dá 53/53. Uma terceira rodada, igual à segunda, mediu
a variância: as duas rodadas concordam em 163 de 166 candidatos (98,2%, κ = 0,93), e só uma
armadilha mudou de lado (007). Pontuação sobre 106: **97 e 100**, com 53 de 53 bugs nas duas.

### 3.14. O Racebench dentro do repositório, e os ids que dependiam da máquina

**O que mudou.** A suíte do Racebench era um repositório separado, um diretório acima do vault
(`../racebench`), e o código a encontrava por caminhos absolutos como
`/home/pedro/Documentos/tcc/racebench/2.1_remarks` (e, na interface, `C:/Users/luoma/...`). As duas
alterações que o projeto fez na suíte (o patch do 006 e a correção de gabarito da §3.13) existiam
só como mudanças **sem commit** naquele checkout. Consequência: nenhum clone do irqrace conseguia
reproduzir o gabarito 53/33.

Por decisão do Pedro, a suíte foi **vendorizada** — copiada para dentro do repositório, em
`project-src/bench/racebench`, em vez de ser uma dependência externa. A cópia veio do commit
`ec1d828` do upstream (`chenruibuaa/racebench`) por `git archive`, sem nada além dos arquivos
versionados, e as duas alterações entraram por cima num commit separado. Assim, o histórico do
irqrace mostra exatamente o que foi mudado na suíte. O arquivo `bench/racebench/VENDORED.md` registra
a origem, as alterações e um aviso: **o upstream não tem licença**. A cópia é redistribuída sem
mudanças além dessas duas, para fins de reprodutibilidade, e os direitos continuam com os autores.

Todo o código passa a encontrar a suíte por uma função só:

`project-src/src/irqrace/racebench.py`
```python
VENDORED_SUITE = Path(__file__).resolve().parents[2] / "bench" / "racebench" / "2.1_remarks"


def locate_suite() -> Path | None:
    """The ``2.1_remarks`` directory: ``IRQRACE_RACEBENCH`` if set, else the vendored copy.

    The variable exists to run against another copy of the suite on purpose
    (an upstream checkout, say); it never falls back silently, so a wrong
    value gives ``None`` rather than the vendored copy.
    """
    import os

    if env := os.environ.get("IRQRACE_RACEBENCH"):
        path = Path(env)
        path = path if path.name == "2.1_remarks" else path / "2.1_remarks"
        return path if path.is_dir() else None
    return VENDORED_SUITE if VENDORED_SUITE.is_dir() else None
```

A variável de ambiente `IRQRACE_RACEBENCH` continua existindo, para rodar contra outra cópia de
propósito, mas nunca cai silenciosamente na cópia vendorizada: um valor errado dá `None`. As 31
configurações em `bench/configs/` agora dizem `source_root: ../racebench/2.1_remarks`, um caminho
**relativo ao próprio arquivo**, que `config.resolve_source_root` torna absoluto ao carregar —
então elas valem em qualquer clone, rodando de qualquer diretório.

**O defeito que a mudança expôs.** Cada candidato tem um id (`c` + 16 dígitos hexadecimais) que é
um *hash* SHA-256 do seu *fingerprint*: o sujeito, a classe, a variável e, para cada um dos três
acessos, o papel, o tipo, o fluxo, o **arquivo** e a linha. O campo do arquivo vem das *debug info*
(informações de depuração que o clang grava no *bitcode* para ligar cada instrução a um arquivo e
uma linha do fonte). O clang grava esse caminho **relativo ao diretório mais profundo que o arquivo
compartilha com o diretório de trabalho** de quem rodou o comando. Com o layout antigo isso dava
`racebench/2.1_remarks/svp_simple_001/svp_simple_001_001.c` (o ancestral comum era
`/home/pedro/Documentos/tcc`); com a suíte dentro do repositório, daria só
`svp_simple_001_001.c`. Ou seja, **o id de cada candidato dependia de onde as pastas estavam no
disco e de onde o comando era rodado**. Na máquina do Lucas, por exemplo, os ids seriam outros. Os
testes passaram a falhar porque procuravam o candidato `cf213e34277d338cc` e ele não existia mais.

A correção ancora o caminho na raiz da suíte. Primeiro localiza o arquivo, do mesmo jeito que já se
fazia para ler o fonte (diretório de trabalho, depois a raiz e cada ancestral dela), e só então o
torna relativo à raiz:

`project-src/src/irqrace/stage1.py`
```python
def _rel(path: str, root: str) -> str:
    """*path* relative to *root*, which is what the fingerprint hashes.

    A debug-info name relative to an unknown compilation directory (see
    ``_source_lines``) is first located the same way, so the result depends on
    neither the working directory nor where the suite sits on disk. Until
    2026-10-29 it was resolved against the working directory only, and the
    names -- hence every candidate id -- depended on the machine's layout:
    ``racebench/2.1_remarks/svp_simple_001/svp_simple_001_001.c`` on one
    checkout, ``svp_simple_001_001.c`` on another.
    """
    base = Path(root).resolve()
    p = Path(path)
    candidates = [p] if p.is_absolute() else [p, base / p, *(d / p for d in base.parents)]
    for c in candidates:
        try:
            if c.is_file():
                return c.resolve().relative_to(base).as_posix()
        except (ValueError, OSError):
            continue
    return path
```

Além disso, o app desktop — que é quem executa `irqrace pipeline` — escolhia como raiz a pasta do
*primeiro* `.c` da lista (a pasta do caso). Agora escolhe a pasta mais profunda que contém **todos**
(`os.path.commonpath`), que para um caso do Racebench (o arquivo do caso mais o `common.c`) é a
`2.1_remarks`. O caminho resultante é `svp_simple_001/svp_simple_001_001.c`, o mesmo formato que
as *fixtures* da Trilha B já usavam.

**Verificação.** Rodando o caso 019 a partir da cópia vendorizada e a partir do `../racebench`
antigo, saem os mesmos ids. O caso 001 também dá os mesmos ids rodando de `project-src/` e de `/`.
O *recall gate* estático dá exatamente o funil anterior: 316 → 202 → 166 candidatos, 53/53 bugs e
30 → 25 → 11 de 33 armadilhas. Os testes que fixavam o id passaram a achar o candidato pelas linhas
(32, 55, 35), e há um teste novo que carrega uma config a partir de `/` e confere que ela chega na
suíte. Resultado: 594 testes passando.

**O custo.** Todos os ids de candidato mudaram uma vez. Ids citados em páginas com data anterior a
29/10 (como o `cf213e34277d338cc` do WRW 32/55/35 do caso 001) são os antigos. O cache do LLM, que
tem o *fingerprint* na chave, começa vazio para os candidatos reais. As contagens não mudam.

### 3.15. Uma nova sequência de telas: modo Racebench e modo genérico com assistente (29 out)

Até aqui o desktop abria direto numa tela de configuração que misturava duas coisas diferentes: um
seletor de "Caso Racebench" e um campo de texto com o caminho do arquivo `.yaml` de configuração. Ele
ainda carregava, sem perguntar, o caso `svp_simple_001_001` e o *run* mais recente dele. A pedido do
Lucas, o app passou a ter uma **tela inicial** com dois caminhos:

| Tela | Para quê | Módulo |
| --- | --- | --- |
| **Início** | escolher o modo | `ui/desktop.py` |
| **Benchmarks Racebench** | rodar os casos da suíte sem intervenção e comparar com o gabarito | `ui/benchmark_screen.py` |
| **Analisar um projeto** (modo genérico) | descrever o programa sob análise e rodar o pipeline | `ui/desktop.py` + `ui/c1_wizard.py` |
| **Configuração da LLM** | provedor, modelo e chave, compartilhada pelos dois modos | `ui/desktop.py` |

**O arquivo de configuração não é mais editado à mão.** O arquivo C1 é o contrato que descreve o
modelo de interrupções do programa (fontes, fluxos, prioridades, primitivas de mascaramento,
semântica do processador). Um *fluxo* é um ponto de entrada que roda "por conta própria": a tarefa
principal ou uma ISR (*interrupt service routine*, a função que o hardware chama quando a interrupção
dispara). No modo genérico o usuário tem duas saídas: **importar** um C1 existente ou **criá-lo pelo
assistente** (*wizard*, uma janela de várias páginas que conduz o preenchimento passo a passo). O
campo do caminho ficou somente leitura. O assistente tem cinco páginas: Projeto (nome e arquivos
`.c`/`.h`), Fluxos, Mascaramento, Semântica e Revisão. Ele lê os fontes com uma expressão regular
para sugerir funções. Não é um *parser*, e por isso é só sugestão: o usuário confirma cada linha, e
o número da IRQ e a prioridade o assistente não tem como deduzir.

O ponto que importa para a tese: **o assistente valida com a mesma função que o pipeline usa**, então
não existe arquivo que o assistente aceite e o pipeline recuse:

```python
# project-src/src/irqrace/ui/c1_wizard.py
def validate_state(state: WizardState, target: Path | None = None) -> Config:
    """Build the document and load it exactly as the pipeline will."""
    doc = state.to_c1(target)
    try:
        return Config.from_dict(doc, path=target)
```

Os padrões oferecidos são os *recall-safe* do esquema. *Recall* é a fração dos defeitos reais que a
ferramenta encontra. Um padrão *recall-safe* é o que nunca faz um defeito real sumir: chegada de
interrupções `unbounded`, externas `may-read-write-reachable`, aninhamento e preempção entre
prioridades iguais ligados. Toda opção que não é *sound* (que pode esconder um defeito real) vem com
um aviso em vermelho ao lado. Na página de fluxos o aviso é o mais importante do contrato: uma ISR
esquecida não contribui nenhum acesso, e os defeitos que só ela alcança desaparecem sem erro nenhum.
Importar um arquivo também valida. O `lucas_config.yaml` antigo, no esquema anterior ao `c1/2.0.0`,
agora é recusado com a mensagem do contrato, em vez de falhar só na etapa 1.

**O modo Racebench** lista os 31 arquivos de `bench/configs`, deixa escolher a profundidade e roda os
casos selecionados fora da *thread* da janela (uma *thread* é um fluxo de execução paralelo; assim a
janela não trava). Nesta primeira versão, os casos rodavam um de cada vez, do início ao fim; a §3.18
mudou isso na profundidade completa. A profundidade **estática** (etapas 1–4) é o padrão: é sobre ela que o *recall gate* é definido, e ela
não gasta chamadas de API. O *recall gate* é a exigência de que nenhum *bug point* do gabarito se
perca. A profundidade **completa** acrescenta triagem e reparo pela LLM. Cada caso é pontuado por
`evaluate_run`, a mesma avaliação por estágio da §3.7. A tabela mostra os candidatos por estágio, os
bugs detectados sobre o total, as armadilhas reportadas (*traps*, linhas anotadas como "não é bug")
e o tempo. Um caso que falha vira uma linha da tabela, não o fim da bateria:

```python
# project-src/src/irqrace/ui/benchmark_screen.py
    except InterruptedError:
        out["status"] = "stopped"
    except Exception as e:  # a failing case is a row in the table, not the end of the batch
        out["error"] = f"{type(e).__name__}: {e}"
```

O resumo de cada bateria é gravado em `runs/benchmarks/racebench-<profundidade>-<data>.json`. Um
duplo clique num caso abre o *run* na aba Pipeline, onde candidatos, triagem e *diff* podem ser
inspecionados como no modo genérico.

**Um defeito achado no caminho.** O log de 29 out mostrava o build compilando a partir de
`C:\Users\luoma\Desktop\racebench`, o *checkout* antigo, e não da cópia vendorizada (§3.14). A causa
era `resolve_c_source_files`: ela usava o `source_root` relativo dos `bench/configs`
(`../racebench/2.1_remarks`) contra o **diretório de trabalho**, e não contra o arquivo. Rodando da
raiz do *vault*, `../racebench` é justamente o *checkout* antigo. Agora a função recebe o arquivo de
origem e resolve a partir dele:

```python
# project-src/src/irqrace/ui/desktop.py
    if yaml_path is not None:
        raw_cfg = resolve_source_root(copy.deepcopy(raw_cfg), Path(yaml_path))
```

Um teste confere que todos os fontes importados de `svp_simple_001_001.yaml` estão dentro de
`bench/racebench`.

**Testes.** `tests/test_desktop_modes.py` é novo, com 8 testes:
- varredura e sugestões a partir do código;
- arquivo do assistente aceito por `Config.load` e pelo `PipelineStepper`;
- recusa do que o contrato recusa;
- ida e volta de um C1 do Racebench pelo assistente, preservando fluxos, primitivas, semântica e
  gabarito;
- um caso real de benchmark rodando até o contexto com *recall gate* 2/2;
- caso que falha virando linha;
- navegação entre as telas.

A *fixture* `tk_root` foi para o `conftest.py` com escopo de sessão, porque no Windows um segundo
`tk.Tk()` depois de destruir o primeiro corrompe o estado do Tcl/Tk. No Windows a suíte fica em
389 passando e 37 falhando. As 37 falhas já existiam antes desta mudança: problemas de codificação
`cp1252` em `test_groundtruth`/`test_racebench`, o `lucas_config.yaml` no esquema antigo e um teste
desatualizado da tela de abertura.

### 3.16. O histórico da LLM mostra o que ela leu (29 out)

Para avaliar um veredito é preciso saber em que código ele se apoiou. A aba "Histórico LLM" só
despejava os turnos da conversa, e ainda lia um campo `phase` que os turnos não têm. Ela foi
refeita (`ui/llm_history.py`) para separar as **duas vias** pelas quais o código chega ao modelo:

- **entregue** (azul): os blocos `<source>` do registro C2 que `render_record` põe no primeiro
  prompt, sem a LLM pedir. É a função de cada acesso da trinca, já numerada por linha.
- **solicitado** (amarelo para o pedido; verde para o código fornecido; vermelho para o recusado):
  os pedidos do protocolo **C4**. Com o *progressive prompting* ligado, a LLM escreve, num bloco
  `request`, um pedido de um tipo fechado (`function_definition`, `isr_body`,
  `all_accesses_to`…). O programa o interpreta, o *resolver* responde, e a resposta volta no turno
  seguinte. Quando não há corpo (`not_found`), a resposta leva a regra de recall que o modelo deve
  aplicar, e o histórico mostra essa regra.

C4 **não é MCP** (*Model Context Protocol*, o padrão de *tool calling* entre aplicações e modelos).
É um protocolo textual próprio do projeto, definido em `contracts/c4-*.schema.json`, que funciona
com qualquer *backend*. O *backend* `claude -p` desliga as ferramentas e os servidores MCP de
propósito (§3.4).

No topo da aba fica um resumo, "O QUE A LLM LEU", com cada trecho, local e número de linhas. Para
isso o `TriageClient` passou a gravar no `turns.jsonl` os pedidos interpretados e as respostas do
*resolver* como dados, e não só como texto:

```python
# project-src/src/irqrace/llm/client.py
            convo.add("assistant", text, stage=stage, turn=turn, requests=requests)
            ...
            convo.add("user", reply_text, stage=stage, turn=turn, kind="c4_replies", replies=replies)
```

O contrato C3 já dizia que o `turns.jsonl` contém "os pedidos e respostas C4". Para *runs* antigos,
sem esses campos, a aba reconstrói pedidos e respostas a partir do texto, com o mesmo *parser* do
cliente.

**O achado.** Ao montar a aba, ficou visível que **nenhum dos 164 `turns.jsonl` existentes tem um
único pedido C4**. Das linhas de prompt da ablação (`simple`, `+domain`, `+decomposition`,
`+self-validation`), nenhuma liga `progressive`. Ele só existe na linha adiada `+progressive`.
Então, em todos os *runs* até aqui, a LLM leu **somente** o código entregue no registro C2. Quando
o prompt do *run* não permite pedidos, a aba diz isso explicitamente, em vez de mostrar uma lista
vazia. Isso é um dado para a [[LLM Stage Design|decisão D#2]]: a distribuição de pedidos que o
desenho chama de "o experimento mais barato do projeto" ainda não foi medida nenhuma vez.

Um defeito antigo saiu no caminho: a aba Triagem quebrava (`AttributeError`) em triagens com
`produced_by: null`, como as escritas pelo *backend* CLI. Testes: `tests/test_llm_history.py`
(5 testes), com uma conversa simulada que pede um `isr_body` (respondido) e uma função
inexistente (`not_found`, com a regra).

### 3.17. O "Completo" que não chamava a LLM: o cache sem transcrição (29 out)

> **Decisão revertida:** esta seção descreve código que não existe mais. O cache, o checkbox
> "Reutilizar respostas em cache" e o evento `llm-cache-hit` foram removidos em 30 out (§3.19).

**O sintoma.** No modo Racebench, a profundidade "Completo" parecia rodar só a parte estática: não
havia nenhum registro de conversa com a LLM. Os *runs* mostram que as etapas 5 e 6 rodaram, sim. O
resumo `runs/benchmarks/racebench-full-20261029T225848Z.json` lista
`build,stage1,solver,context,triage,repair` nos 31 casos. Mas no `svp_simple_029_001` a triagem
terminou em 54 ms, e no `svp_simple_030_001` só 2 dos 11 candidatos têm `turns.jsonl`.

**A causa** é o **cache de resultados** (`.llm-cache/`): um diretório com uma resposta por chave.
A chave é formada pela *fingerprint* do candidato, pelo prompt, pelo modelo, pelo esquema e pela
evidência mostrada, e o cache existe para não pagar duas vezes pela mesma pergunta. Num acerto de
cache (*cache hit*), o `TriageClient` devolvia o veredito guardado antes de montar a conversa:
nada era chamado, nada era gravado e nada era avisado. O `RepairClient` fazia o mesmo. Para quem
avalia, um veredito sem conversa é indistinguível de uma transcrição perdida.

**A correção** tem três partes:

1. O cache passa a guardar a transcrição ao lado da resposta (`<chave>.turns.jsonl`).
2. Num acerto, o cliente escreve no *run* um `turns.jsonl` (ou `repair-turns.jsonl`) que começa
   com um turno marcador `cache_hit`, seguido da conversa original:

```python
# project-src/src/irqrace/llm/client.py
        cached = self.cache.get(*key)
        self.last_from_cache = cached is not None
        if cached is not None:
            if run_dir is not None:
                cache_hit_conversation(
                    record["id"], self.cache.get_turns(*key), stage="triage",
                    backend_spec=self.backend.spec, prompt_config=self.config.name,
                ).write(run_dir)
            return Triage.model_validate(cached)
```

3. A interface mostra a origem de cada resposta:
   - o log da etapa marca cada candidato servido do cache com ♻ e fecha com "X via API, Y do cache";
   - o `log.ndjson` do *run* ganha um evento `llm-cache-hit`. O bloco `llm` do *manifest* não
     admite campos extras (C3), então o evento vai para o log;
   - a aba "Histórico LLM" mostra a faixa roxa "♻ RESPOSTA DO CACHE";
   - a tela de configuração da LLM ganhou o checkbox **"Reutilizar respostas em cache"**. Desmarcado,
     ele força chamadas novas à API, nos dois modos.

As 306 entradas que já estavam no cache foram escritas antes desta mudança e não têm transcrição.
Para elas, a aba diz que a conversa original não foi guardada e manda desligar o cache para
revê-la.

Um veredito de cache continua sendo um veredito válido, com o mesmo modelo, o mesmo prompt e a
mesma evidência. O que mudou é que ele não fica mais invisível para a avaliação.

Testes:

- três novos em `tests/test_llm_history.py`: acerto com transcrição, acerto sem transcrição e cache
  desligado;
- um trecho a mais no teste de cache de `tests/test_llm_repair.py`;
- uma execução de ponta a ponta do caso 029 com `claude-cli:haiku`/`simple`, que registrou
  "0 via API, 2 do cache" na triagem e "1 do cache" no reparo.

### 3.18. Racebench em duas filas: a LLM não espera o estático (30 out)

**O problema.** Em "Executar todos" na profundidade completa, cada caso passava pelas 6 etapas antes
de o próximo começar. Quem espera é a LLM: a resposta do modelo leva segundos, e nesse tempo o
estático do caso seguinte ficava parado. As chamadas à API também saíam uma de cada vez.

**A decisão: duas filas.** `run_batch`, em `ui/benchmark_screen.py`, separa a bateria assim:

- **Fila estática:** uma *thread*, um caso por vez, etapas 1–4.
- **Fila LLM:** um *pool* de *threads* (um grupo fixo de N fluxos de execução que pegam tarefas de
  uma fila), etapas 5–6. N é escolhido na tela, em "Casos na LLM em paralelo", de 1 a 16, e o padrão
  é 4.

Quando o estático de um caso termina, o caso vai para o *pool*, e a fila estática passa ao próximo
sem esperar:

```python
# project-src/src/irqrace/ui/benchmark_screen.py
            reached = run_steps(res, stepper, STATIC_LAST_STEP, log_fn, should_stop)
            evaluate_case(res, stepper)
            if reached and last_step != STATIC_LAST_STEP:
                emit("row_static", dict(res))  # a copy: the pool writes to *res* from here on
                pool.submit(llm_lane, res, stepper, log_fn)
            else:
                finish(res)
```

Três escolhas nesse desenho:

1. **O estático continua sequencial.** Ele não é o gargalo, e rodá-lo em paralelo contaminaria os
   tempos por estágio (`wall_ms`).
2. **O paralelismo é por caso, não por candidato.** Dentro de um caso os candidatos seguem em ordem.
   O laço de `_step_triage` regrava `triage.jsonl` a cada candidato e consulta
   `client.last_from_cache`, e os dois assumem uma única *thread*. Com 31 casos, o paralelismo por
   caso já resolve a espera.
3. **Um caso nunca está nas duas filas ao mesmo tempo.** É isso que dispensa travas (*locks*) no
   `PipelineStepper` e no `RunStore`: cada caso tem os seus, e só uma *thread* os toca de cada vez.

**O que mudou na tela.** A coluna de status passa por `na fila` → `⏳ estático` → `🤖 fila LLM` →
`🤖 LLM` → resultado. Candidatos, bugs e recall aparecem assim que o estático acaba, antes da LLM.
Cada linha de log leva o nome do caso, porque os logs agora se intercalam. O botão (STOP) avisa
todos os casos em curso, e os que estão na fila LLM terminam `parado` sem chamar a API.

**Uma falha da LLM não apaga mais o recall.** Antes, uma exceção na triagem pulava `evaluate_run` e a
linha ficava sem números. Agora `evaluate_case` roda mesmo depois de uma falha: o caso fica `failed`,
com os números do estático, porque o *recall gate* é definido sobre eles.

**Um risco que as duas filas criaram.** Todo `PipelineStepper` novo varre os `manifest.json` de todos
os *runs* em `find_matching_template_run`, e agora isso acontece enquanto outras *threads* gravam
esses arquivos. A gravação usa `os.replace`, que troca o arquivo de uma vez só. No Windows, essa
troca levanta `PermissionError` se alguém estiver com o destino aberto, e o caso cairia no meio da
LLM por causa de uma simples leitura. A correção tenta de novo por alguns milissegundos:

```python
# project-src/src/irqrace/runstore.py
    for attempt in range(1, attempts + 1):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts:
                raise
            time.sleep(wait_s * attempt)
```

Esse risco veio da leitura do código. A falha não foi observada numa execução; o teste a simula.
A varredura saiu do projeto em 30 out (§3.19). A nova tentativa ficou, porque a interface também lê
esse arquivo durante um *run*.

**O custo: *rate limit*.** O *rate limit* é o limite de uso imposto pelo provedor, em geral em tokens
por minuto, e estourá-lo devolve o erro HTTP 429. Os N casos dividem o mesmo limite. O *backend*
desiste depois de 6 novas tentativas ou de 300 s, e o candidato vira `uncertain` com o motivo em
`not_triaged`. Isso não perde recall, porque nada sai do relatório, mas piora a triagem sem alarde.
Por isso o total de candidatos sem veredicto aparece no resumo da tela e no JSON da bateria, junto
com `llm_workers`: duas baterias com N diferentes não são diretamente comparáveis. Não há limitador
global de taxa. Se o número subir, basta reduzir N.

**Verificação.** Oito testes novos em `tests/test_desktop_modes.py`, com um *stepper* falso:

- a LLM de um caso só é liberada quando o estático do caso seguinte começa, o que prova que ela não
  espera;
- as fases LLM de dois casos se sobrepõem;
- os resultados saem ordenados mesmo terminando fora de ordem;
- a falha na LLM mantém os números do estático;
- o STOP não deixa o caso entrar na LLM;
- um único *worker* (uma *thread* do *pool*) ainda roda todos os casos;
- a profundidade estática não chega à LLM;
- candidatos sem veredicto chegam ao resumo.

Um nono teste cobre `write_manifest` com um `PermissionError` simulado.

Houve também uma execução de ponta a ponta da tela real, com os 31 casos e a análise estática de
verdade, contra um servidor local falso que responde em 0,4 s e devolve 429 nas três primeiras
chamadas. Resultado: 31/31 `ok`, 53/53 bugs, 501 chamadas em 79 s, no máximo 4 simultâneas, linhas
em `🤖 LLM` e `⏳ estático` ao mesmo tempo. O STOP encerrou a bateria com 1 chamada feita. **Isso
não mede o ganho de tempo nem o comportamento de *rate limit* com um provedor real.**

No Windows a suíte, sem `tests/test_ui_app.py` (este Python não tem `pandas`), fica em 400 passando e
36 falhando. A falha a menos é `test_live_triage_keeps_every_candidate_when_the_api_fails_on_some`:
um `lambda` do teste não aceitava o `cache=` da §3.17, e a correção foi de uma linha no teste. As 36
restantes são 33 de `test_racebench`, 2 de `test_groundtruth` e a do `lucas_config.yaml`.

**A primeira bateria real, e o "travamento" que não era travamento.** Em 30 out a tela pareceu presa
em `🤖 LLM`. Os *runs* mostram que não estava: com `claude-cli` as chamadas funcionaram em paralelo
(às 19:28, os casos 001 a 004 estavam em triagem ao mesmo tempo). Na bateria que pareceu presa, o
*pool* estava em 1 e cada candidato levava cerca de 26 s, então o caso 001 ficou mais de 2 minutos na
mesma linha, sem nenhum sinal de avanço, e os outros 30 esperaram na fila. A falta era de informação:

- a linha agora mostra `🤖 Triagem 3/6`, a partir do evento `api_candidate_progress`, que os
  *steppers* da bateria não recebiam;
- o resumo mostra quantos casos terminaram, quantos estão na LLM e quantos esperam na fila;
- na profundidade estática, o resumo diz que a LLM não é chamada. O rótulo "API LLM: Inativa" é da
  aba Pipeline e o modo Racebench não o atualiza; ao abrir um *run* da tabela, ele agora diz que o
  *run* já foi executado.

**Um defeito real achado no teste.** Uma conexão derrubada no meio da resposta levanta
`RemoteDisconnected`, que não é `URLError` nem nenhuma das exceções que as etapas capturam. O erro
encerrava o caso inteiro, em vez de uma tentativa de um candidato. Agora é uma falha transitória,
repetida como um *rate limit*:

```python
# project-src/src/irqrace/llm/backends/openai_backend.py
        except ConnectionError as e:
            # A connection dropped mid-response is not wrapped in URLError, and
            # it is none of the exceptions the stages catch: it ended the whole
            # case instead of one attempt at one candidate.
            raise _Transient(f"connection to {self.base_url} lost: {e}", 5.0) from None
```

**`+progressive` com `claude-cli`: dois achados.**

1. Nos *runs* reais desse dia, com Sonnet 5.5 e Haiku, **nenhuma das transcrições gravadas tem um
   pedido C4**. Esta seção dizia que "o caminho funciona" porque 166 rodadas chegaram ao *resolver* no
   servidor falso. **Isso estava errado:** o desktop nem usava o *resolver* com os fontes, e o pedido
   falso também não testava o que importava (§3.21).
2. Com `claude-sonnet-5-5`, vários candidatos falharam com a mensagem "safeguards flagged this
   message" (`reasoning_extraction`). Isso não aconteceu na bateria com `+self-validation`, nem nos
   5 candidatos respondidos pelo Haiku, e aconteceu também num *run* sem paralelismo, então a causa
   não é o paralelismo. A **hipótese**, ainda não verificada, é a segunda chamada: como `claude -p`
   só aceita um turno, `_render_messages` transforma a resposta anterior do modelo numa transcrição
   e pede que ela seja convertida no formato final, o que pode parecer uma tentativa de extrair o
   raciocínio. O erro chega como falha de API, não como recusa. Nesses *runs* a transcrição do
   candidato que falha não foi gravada, então eles não mostram em que chamada o erro ocorreu. Desde a
   §3.20 ela é gravada turno a turno, e o próximo erro deste tipo vai dizer.

A suíte no Windows, nas mesmas condições, fica em 402 passando e as mesmas 36 falhando.

### 3.19. O cache de LLM saiu do projeto (30 out)

**A decisão**, do autor do projeto: nenhuma resposta da LLM pode ser reutilizada. Toda triagem e todo
reparo são uma chamada nova ao modelo. Isso reverte a decisão da W2 e as §3.2 e §3.17.

**O que saiu:**

- `llm/cache.py` e o parâmetro `cache=` de `TriageClient`, `RepairClient`, `triage_store` e
  `repair_store`;
- as opções `--no-cache` e `--cache-only` da CLI e dos *scripts*;
- `evidence_hash` e os *hashes* de esquema, que só existiam para compor a chave do cache;
- o parâmetro `sample`, que só distinguia entradas de cache. `--samples` da ablação continua: agora
  cada repetição é simplesmente outra chamada. Só `--sample` de `run-repair.py` saiu, por não ter mais
  efeito;
- o checkbox, o log "X via API, Y do cache", o evento `llm-cache-hit` e a faixa roxa do histórico;
- **o modo "Cache / Simulado (Offline)"**. Ele copiava vereditos e *patches* de um *run* anterior do
  mesmo caso (`find_matching_template_run`), sem chamar a LLM. O nome era outro, mas era um cache.
  Com "Usar API de LLM Real" desmarcado, as etapas 5 e 6 agora ficam `skipped` e os candidatos seguem
  em `context/` sem veredicto. Isso resolve a pendência da §6, em que esse modo "fingia a LLM".

**O que ficou, de propósito:**

- o *prompt caching* do provedor (`cache_control`, `cache_read_tokens`). É outra coisa: o modelo é
  chamado e responde de novo, e só parte dos *tokens* de entrada sai mais barata. Nenhuma resposta é
  reaproveitada;
- `PromptConfig.hash`, que continua identificando a linha da ablação nos relatórios;
- o *fingerprint*, cuja regra continua valendo: é por ele que dois *runs* do mesmo sujeito são
  comparados;
- caches internos sem relação com a LLM, como o de linhas de fonte no stage 1;
- o diretório `.llm-cache/` em disco (458 arquivos, fora do git). Nada mais o lê. Ele não foi apagado
  porque, estando fora do git, não poderia ser recuperado.

**O que o projeto perde:**

- reexecutar custa de novo: rodar a mesma linha duas vezes paga duas vezes;
- `--cache-only` era a forma de repontuar linhas já medidas sem nenhuma chamada. Agora, repontuar
  exige chamar o modelo, ou reler os resultados salvos em JSON;
- nos *runs* antigos, o marcador `cache_hit` continua nos arquivos e aparece no histórico como um turno
  comum de SISTEMA, com o texto dizendo que a resposta veio do cache. O número continua auditável.

**Testes.** `tests/test_llm_cache.py` saiu. Quatro testes novos fixam o comportamento: a mesma
triagem pedida duas vezes faz duas chamadas, o mesmo reparo também, sem API não há veredicto, e um
*run* antigo com marcador continua legível. No Windows a suíte, sem `tests/test_ui_app.py`, fica em
393 passando e as mesmas 36 falhas antigas. A contagem caiu porque os testes do cache foram removidos.
A tela real, com a análise estática real e o servidor falso, rodou os 31 casos em `+progressive`:
31/31 `ok` e 53/53 bugs. Com o STOP, foram 17 `ok` e 14 parados.

### 3.20. Inspeção ao vivo de um caso do Racebench (30 out)

**O problema.** A tabela só conhecia o *run* de um caso depois que ele terminava, então o duplo clique
não fazia nada antes disso. Em baterias reais um caso leva minutos.

**O que mudou.** O duplo clique funciona assim que o caso começa, inclusive ainda no estático. A aba
Pipeline abre em **inspeção ao vivo**: etapas, candidatos, vereditos e a aba Histórico LLM se atualizam
sozinhos, e as linhas do log daquele caso aparecem no log da aba. Um candidato que está sendo
respondido aparece como `⏳ na LLM`. Quando o caso termina, a aba volta ao modo normal.

Abrir mais cedo seria uma linha. Quatro problemas tornaram isso mais que uma linha:

1. **Dois escritores no mesmo *run*.** Abrir um *run* cria um `PipelineStepper` ligado a ele. Com o
   caso ainda rodando, clicar em "Executar Tudo" faria uma segunda *thread* escrever no mesmo diretório.
   Por isso a inspeção é somente leitura: nenhum *stepper* fica ligado e os botões ficam desativados,
   inclusive o de aplicar *patch*, porque o benchmark está lendo aqueles fontes.
2. **Atualizar sem atrapalhar a leitura.** `_refresh_from_store` voltava para o primeiro candidato e
   levava o texto ao topo. Agora a tela compara `run_signature` (caminho, data e tamanho de cada
   arquivo) e só redesenha o que mudou. O candidato selecionado e a rolagem são mantidos, e quem está no
   fim do texto continua acompanhando o fim.
3. **Arquivos lidos pela metade.** `triage.jsonl` é reescrito a cada candidato. Uma leitura no meio da
   escrita dá erro de JSON, e a atualização simplesmente tenta de novo no segundo seguinte. **O teste
   achou um defeito aqui:** a tabela era limpa antes da leitura, então essa exceção a deixava vazia.
   Agora ela só é limpa depois que tudo foi lido.
4. **A conversa só existia no fim.** `turns.jsonl` era gravado quando o candidato terminava. Agora
   `Conversation` grava a cada turno:

```python
# project-src/src/irqrace/llm/client.py
    def add(self, role: str, content: Any, **meta: Any) -> None:
        self.turns.append({"role": role, "content": content, **meta})
        if self.live_path is not None:
            self._dump(self.live_path)
```

O mesmo vale para o reparo. Há um ganho além da inspeção: uma conversa que falha agora deixa no *run*
o que foi dito até ali, o que faltava para diagnosticar o erro do Sonnet da §3.18.

**Limite:** a tela mostra cada turno quando a resposta chega. Ela não mostra o texto sendo gerado
palavra por palavra, porque os *backends* não usam *streaming*.

**Verificação.** Três testes novos em `tests/test_desktop_modes.py`: o *run* é anunciado antes da
primeira etapa, uma conversa que falha deixa o que foi dito, e a inspeção é somente leitura e mantém a
seleção, inclusive com um `triage.jsonl` cortado no meio. Na tela real, com o servidor falso, um caso
foi aberto ainda em `⏳ estático` e acompanhado até o fim: 0/6 a 6/6 etapas, 14 candidatos, histórico
crescendo e seleção mantida. A suíte fica em 396 passando e as mesmas 36 falhas antigas.

### 3.21. Opções de prompt: por que os bugs reais viravam `likely_benign`, e o C4 de verdade (30 out)

**A queixa** foi que a LLM "quase sempre descarta bugs reais". Antes de mexer no prompt, os bugs do
gabarito foram contados por grupo nos *runs* do dia:

| Modelo / prompt | `likely_real` | `likely_benign` | `likely_infeasible` |
| --- | --- | --- | --- |
| Sonnet 5.5, `+self-validation` | 4 | **19** | 0 |
| Haiku, `+progressive` | 0 | **10** | 0 |
| Opus, `+progressive` | 0 | **4** | 0 |

Os 33 bugs em `likely_benign` foram todos julgados `feasible`. A LLM acertava que a intercalação
ocorre e dizia que ela não faz mal: "o valor vai para um local nunca lido" (um **leitor morto**, como
o `reader1` do Racebench). `harmfulness.md` manda exatamente isso, e em código real está certo. O
gabarito do Racebench, porém, conta a intercalação em si. A linha `+racebench` já resolvia isso, mas
não estava em uso. Mais código, sozinho, não mudaria essa resposta.

**Três defeitos deixavam o C4 inútil, e nenhum teste os tinha pegado:**

1. Em 31/31 casos o desktop usava o `RecordBackedResolver`, que só repete o registro. A raiz passada
   tinha um nível a mais (`.../svp_simple_001`), e os caminhos do registro já começam com essa pasta.
2. `_load_subject_sources` só carregava `*.h` da raiz, então `common.c` nunca era lido. É justamente
   o código fora do registro para o qual o C4 existe.
3. `all_call_paths` devolvia o formato do C2 num lugar onde o contrato C4 exige outro, e isso lançava
   `ContractError`. Como esse erro é um `ValueError`, que o desktop não capturava, um pedido derrubaria
   o caso. O mesmo valia para um pedido malformado do modelo. Agora um pedido que não pode ser atendido
   volta como `unsupported`, com a regra de recall (`_answer`, em `llm/client.py`).

**O que mudou:**

- **Duas opções novas:** `+c4`, o prompt completo com pedidos, e `+racebench+c4`. `ABLATION` não mudou.
- **`context_requests.md` reescrito.** O texto antigo dizia "Do not ask for context you will not use
  -- what you request [...] is measured". O novo diz que pedir é opcional, e manda pedir antes de
  responder `infeasible` ou `benign` se a resposta depender de código não lido. A regra de `not_found`
  agora está no próprio texto: antes ela citava um *checklist* ausente em `+progressive`. Saiu
  `masking_state_at`, que só responde para linhas de acesso, e o registro já traz isso.
- **A tela Racebench ganhou um seletor de prompt próprio**, com padrão `+racebench+c4`, independente do
  `.env`, e um aviso quando a opção escolhida não tem a semântica do benchmark.
- **Nova coluna "LLM: reais"**, porque "Bugs detectados" só mostra o estático e nunca revelaria o
  problema acima. Os totais vão para o resumo e o JSON (`triage_outcome`, em `run_evaluation.py`).
- **O erro do Sonnet saiu.** `_render_messages`, do `claude -p`, deixou de reenviar a prosa do modelo:
  o histórico vira uma mensagem só, com tarefa, registro, respostas C4 e instrução final.

**Resultado com chamadas reais**, só triagem, `+racebench+c4`:

| Modelo | Casos | Bugs `likely_real` | `uncertain` | `benign` | Armadilhas `likely_real` | Pedidos C4 |
| --- | --- | --- | --- | --- | --- | --- |
| Haiku | 001–005 | 4/6 | 2 | 0 | 0/1 | 0 |
| Sonnet 5.5 | 002, 004, 005 | 3/3 | 0 | 0 | 0/1 | **4** |

Os quatro pedidos do Sonnet são **os primeiros pedidos C4 reais do projeto**: três
`global_declaration` e um `all_accesses_to`, todos respondidos `ok` pelo *resolver* com os fontes.
Os casos 002, 004 e 005, que falhavam com o erro de `safeguards`, passaram sem erro. É uma amostra
de 8 casos, e não a bateria dos 31.

**O que ficou aberto:** 4 dos 14 candidatos do Haiku falharam com `unknown error` na segunda chamada;
por isso os 2 bugs do caso 001 ficaram `uncertain`. O *backend* descartava o motivo. Agora ele inclui
`errors`/`subtype` na mensagem, mas a repetição que leria esse motivo não foi feita. A causa é
desconhecida.

`harmfulness.md` não mudou: `+c4`, em código real, continua chamando leitor morto de `benign`.

### 3.22. Multi-arquivo: a linha agora anda com o arquivo (31 out, *issue* #8)

**O problema.** Uma global usada em `task.c` e `isr.c` é detectada, e o registro C2 guarda o arquivo de
cada acesso. Mas vários consumidores usavam só a linha: `(8,5,11)` não diz que o 5 está em `isr.c`.

**O que a *issue* não dizia.** Ela afirmava que nada afetava a detecção nem o recall, e isso é verdade.
Mas o reparo podia **corromper um fonte sem aviso**: `apply_unified_diff` ignorava o nome do arquivo e
não conferia as linhas de contexto. Um diff feito para `isr.c`, aplicado a `task.c`, trocava
`pending = 0;` por `guarded_inc();`, e o botão "Aplicar patch" grava no arquivo real. A verificação de
compilação tinha o mesmo erro: testava o patch no arquivo do A₁.

**A correção central:** as linhas decidem, não os números.

```python
# project-src/src/irqrace/llm/repair.py
    code = ["".join(line.split()) for line in src]
    wanted_code = ["".join(line.split()) for line in old]
    fits = (
        i for i in sorted(range(floor, len(src) - len(old) + 1), key=lambda i: abs(i - wanted))
        if code[i:i + len(old)] == wanted_code
    )
```

Um *hunk* (um bloco do diff) vai para onde suas linhas estão, o mais perto possível do número citado,
como faz o programa `patch`. Se elas não estão no arquivo, o diff é recusado.

**A medição que mudou a primeira versão.** A checagem foi testada nos 244 patches reais em `runs/`. Na
versão estrita, 52 dos 194 do Haiku de 29/10 eram recusados, e **37 só por indentação**: o modelo
reescreve tabulação como espaços. Por isso espaço em branco deixou de contar, como em `patch -l`:

| Modelo, data | Aplicam | Recusados |
| --- | --- | --- |
| Sonnet 5.5, 30/10 | 6 | 0 |
| Haiku, 30/10 | 8 | 0 |
| Haiku, 29/10 | 179 | 15 |
| Llama, 20 e 22/10 | 5 | 28 |

Os 15 recusados do Haiku têm as linhas no arquivo, mas fora de sequência: o diff está errado, e o
código antigo os aplicaria deslocando o conteúdo. Três patches antigos (`gpt-oss-120b`) não dizem o
arquivo. **Uma consequência:** a *Syntax Rate* medida antes desta mudança deixa de ser comparável,
porque patches que antes "aplicavam" agora falham.

**O que mudou no resto:**

- **`Patch.file`:** o modelo declara o arquivo, e `repair.md` explica como. Isso muda a resposta da LLM.
  Um patch altera um único arquivo; uma correção que exija dois não é representável.
- **Compilação:** o sujeito é recriado numa pasta temporária com o patch aplicado. Compila-se o `.c`
  alterado ou, se o patch for num `.h`, todos os `.c`. Um `.c` só pode quebrar a si mesmo com
  `-fsyntax-only`. **Não há link**, então uma função inexistente não é detectada.
- **Exibição:** `access_locations` mostra `(8,5,11)` em um arquivo e `task.c:8, isr.c:5, task.c:11` em
  vários, na lista do desktop, no PDF, no `stage3 -v` e na Streamlit. A opção do asterisco foi descartada.
- **Marcas no código:** a aba Código Fonte e o passo 1 da Streamlit marcam um acesso só no arquivo dele.
  A Streamlit mostra um painel por arquivo.
- **Contrato C3 passa a `c3/1.1.0`:** o registro de descarte ganha `accesses: [{file, line}]`. `lines`
  fica por compatibilidade, e runs `c3/1.0.0` continuam válidos.
- **Gabarito:** `Access.file` é opcional e, quando existe, entra no casamento. O Racebench não o usa.
  `realworld.py`, que só existe na branch `semana-9`, ainda precisa da mesma mudança na integração.
- **Alvo do patch no desktop:** compara o caminho inteiro e devolve `None` em vez de adivinhar.

**Testes.** `tests/test_multifile.py` traz o programa de dois arquivos da *issue*, rodando o pipeline
real.

**Dois erros meus que só o WSL mostrou.** O Windows não tem pandas, então `test_ui_app.py` não roda lá, e
a Streamlit ficou com `access_locations` sem importar: a primeira tabela de candidatos quebrava com
`NameError`. E o campo novo `accesses` do registro de descarte confundiu um auxiliar de `test_stage2.py`,
que tratava qualquer `accesses` como acessos C2. Vale a lição: uma suíte que pula testes em uma máquina
não atesta nada sobre eles.

**Um alarme falso que custou tempo.** A suíte do WSL acusou o recall gate do `svp_simple_019_001`. Parecia
grave, mas o caso falhava igual no `HEAD` limpo. A causa era o ambiente: `/etc/profile.d/irqrace.sh` define
`IRQRACE_RACEBENCH` apontando para a cópia antiga em `Desktop/racebench`, anterior ao relabel. O gabarito
lido não era o vendorizado. Sem essa variável, o caso passa. Rode a suíte com
`env -u IRQRACE_RACEBENCH`.

### 3.23. A lista de candidatos e o layout (31 out, *issues* #13, #14, #15, #17)

Quatro pedidos sobre a mesma tela. O que decide ordem, agrupamento e estado das abas foi para um módulo
sem Tk, `ui/candidate_list.py`, que roda em máquina sem tela. `desktop.py` só desenha.

- **#14, ordem:** por padrão, o que chega à LLM vem primeiro, na ordem da triagem, e depois o que foi
  descartado com prova. Clicar no título ordena e mostra ▲ ou ▼. Linhas ordenam como números, viabilidade
  pela confiança e *bucket* pelo significado:

```python
# project-src/src/irqrace/ui/candidate_list.py
BUCKET_ORDER = tuple(b.value for b in INSPECTION_ORDER) + (PENDING, DISCARDED)
```

  A ordem de inspeção é a mesma da métrica *Inspection Ratio*: a fila de leitura de quem revisa.
- **#13, agrupamento:** a caixa "Agrupar por variável" transforma a lista em árvore, com contagem por
  padrão, quantos vão à LLM, quantos foram descartados e o melhor *bucket*. A chave inclui a declaração,
  porque dois locais chamados `rate` em funções diferentes são duas variáveis.
- **#15, layout:** lista e detalhe do candidato lado a lado, e as abas num painel inferior que redimensiona
  e recolhe, como o terminal do VS Code. O detalhe mostra cada acesso com arquivo, fluxo, prioridade e
  trecho de código com a linha marcada. O estado da aba usa símbolo **e** cor (`✓ ○ ✗ …`). Como uma aba do
  `ttk` não tem cor própria de texto, a cor vai numa pequena imagem.
- **#17, quebra de linha:** um `tk.Text` não aplica `wrap` por trecho, então a aba de reparo tem dois
  painéis: a explicação quebra linha, e o diff não quebra e tem barra horizontal.

### 3.24. Triagem em paralelo, por intervalo e sob orçamento (31 out, *issues* #9 e #16)

**O problema.** Os 18 programas reais levam 972 triplas à LLM, e `wdt_pci_3` tem 132 só em `expect_close`.
A maioria é a mesma pergunta repetida: este intervalo, de A₁ a A₂, pode ser interrompido por uma escrita?

**Um motor só.** `triage_store` e o desktop tinham laços próprios. Agora ambos usam `triage_records`, em
`llm/pipeline.py`, com três opções:

- **Paralelo:** `workers` conversas ao mesmo tempo, com `ThreadPoolExecutor`, porque o trabalho é espera de
  rede. Cada conversa grava só o próprio diretório, e os totais de custo têm trava. O resultado não depende
  de `workers`, salvo sob orçamento, em que as chamadas em andamento decidem onde ele para. Antes disso, o
  paralelismo era só por caso, na tela Racebench, e não ajudava num programa com 175 triplas. Essa tela
  segue com `workers=1`, senão as duas camadas se multiplicariam.
- **Por intervalo:** triplas que só diferem em B viram uma conversa, com todos os B listados. O prompt pede
  a resposta do intervalo inteiro:

```python
# project-src/src/irqrace/llm/intervals.py
        "Answer for the interval as a whole: the interleaving is feasible if ANY of these B can "
        "occur inside it, and harmful if ANY of them that can occur does harm. Do not answer "
        "infeasible unless the blocking element rules out every B listed.",
```

  Assim "inviável" exige descartar todos os B, e um B perigoso não se esconde atrás dos demais. O fluxo faz
  parte da chave: uma linha alcançada por dois fluxos são dois intervalos, com mascaramento e prioridade
  diferentes. A tripla copia o veredito e guarda em `interval_of` qual conversa respondeu por ela.
- **Orçamento:** limite de chamadas, *tokens* ou dólares, checado antes de cada conversa. Grupos com sinal
  estático mais forte vão primeiro. O que sobra fica `uncertain`, com o motivo. Um limite em dólares para
  no primeiro pedido sem preço, porque sem preço não é de graça.

**Por que isso não custa recall.** A LLM não descarta nada. Um teste parametrizado confirma que o relatório
lista os mesmos candidatos com e sem cada opção, inclusive com orçamento zero. O que muda é quanto da
ordenação um modelo de fato leu, então o manifesto registra `workers`, `by_interval` e `budget`.

**O que ainda não está medido.** Nenhuma destas opções rodou com LLM real. Falta saber se o veredito por
grupo concorda com o por tripla, e por isso a #9 continua aberta. A parte 2 da #16, triagem e reparo no
mesmo prompt, não foi feita: muda a arquitetura de prompt e precisa entrar como nova linha da ablação.

### 3.25. Nomes de variável pela informação de debug (31 out, *issue* #12)

**O problema.** Objetos locais apareciam como `obj_1176`, inclusive no prompt. O clang descarta o nome de
valores locais, então `hasName()` falha e sobra o número interno do SVF (*Static Value-Flow*, a análise de
ponteiros usada no Stage 1).

**A correção.** O `-g` já é obrigatório, e a informação de debug guarda o que o fonte disse:

```cpp
// project-src/analysis/src/irqrace-stage1.cpp
    auto declares = llvm::FindDbgDeclareUses(const_cast<llvm::AllocaInst *>(ai));
    if (declares.empty())
      return;
    const llvm::DILocalVariable *dv = declares[0]->getVariable();
```

`llvm.dbg.declare` é a marca que liga uma alocação de pilha (`alloca`) à sua variável de origem. Dela saem
nome, tipo, arquivo e linha. Uma alocação dinâmica vira `malloc in foo()`, com o local da chamada.
`obj_N` só sobra se não houver debug info, e `svf_node` segue como identificador interno. `variable.storage`
deixou de dizer `global` para tudo, e o novo `variable.function` entra em `c2/2.1.0`, compatível com
registros `2.0.0`. A tela mostra `rate (local de taskControl, tasks.cpp:226)`.

**Uma consequência.** O nome faz parte da impressão digital do candidato, então os IDs de candidatos em
variáveis locais mudam. No Racebench isso atinge só o `svp_simple_009_001`: 9 dos 316 candidatos do Stage 1
estão em locais, antes `obj_14`, `obj_17` e `obj_55`, agora `svp_simple_009_001_local_var1` a `3`. Conferido
rodando o código antigo e o novo sobre esse caso. Comparar esses IDs com execuções anteriores a esta mudança
não vai casar. O recall gate do caso continua passando.

## 4. Achados e decisões

1. **O mesmo defeito, em seis lugares.** Stage 2 e Z3 simulados, reverificação `ok` sem execução,
   o script do *showcase*, o funil do dashboard, os KPIs da página inicial, o IR do PDF. Em todos, um
   número com aparência de medição. O critério para remover foi um só: se ninguém calculou, não pode
   aparecer como calculado — aparece "-" ou "não executado".
2. **Dados falsos escondem bugs reais.** O *showcase* fabricado escondia o `KeyError` do *resolver*
   (§3.8); os estágios simulados escondiam que o modelo nunca tinha visto código (§3.1).
3. **Corrigir uma etapa pode invalidar o *cache* sem que ele perceba.** O *fingerprint* identifica o
   candidato, não a evidência sobre ele (§3.2).
4. **Decisão revertida, registrada:** a reverificação foi primeiro marcada `skipped` com o motivo
   "os stages 2 e 3 não existem nesta branch". Agora eles existem; o motivo passou a ser o que de
   fato falta (aplicar o *patch*, recompilar, rodar os stages 1–3 de novo e mapear o candidato pelas
   linhas deslocadas). Ela continua `skipped`.
5. **Paralelismo tem custo em qualidade, não só em taxa.** Um candidato que esgota as tentativas de
   *rate limit* continua no relatório como `uncertain`, então o recall não acusa nada. Por isso o
   total sem veredicto e `llm_workers` passaram a sair junto com os números (§3.18).

## 5. Como reproduzir

Dentro de `project-src/`, com a *venv* do projeto:

```bash
.venv/bin/python -m pytest -q tests
```

```bash
.venv/bin/irqrace contracts validate
```

```bash
.venv/bin/irqrace stage3-all
```

```bash
.venv/bin/irqrace llm triage runs/<run_id> --backend claude-cli:sonnet
```

```bash
.venv/bin/python desktop_app.py
```

```bash
.venv/bin/irqrace ui
```

```bash
.venv/bin/python scripts/bench-triage-report.py runs/bench-racebench-2026-10-28c
```

Para os testes das duas filas do modo Racebench (§3.18):

```bash
.venv/bin/python -m pytest -q tests/test_desktop_modes.py
```

Para ver as alterações feitas na suíte vendorizada (o patch do 006 e a correção de gabarito):

```bash
git log -p -- bench/racebench
```

## 6. Estado ao fim da semana

**592 testes passando, nenhum falhando** — a primeira suíte inteiramente verde no `track-b` (a falha
da *fixture* desatualizada sumiu com a §3.9). O desktop roda build → stage 1 → stage 2 → stage 3 →
contexto sobre um caso real (conferido em `svp_simple_001_001`, §3.7), e a triagem e o reparo
operam sobre o que esses estágios produzem — nos testes, com um *backend* simulado; ao vivo, depois
do *merge*, ainda não. O relatório e o dashboard só mostram números medidos.

Falta:

- **a triagem dos 31 casos sobre o resíduo pós-Z3** (166 trincas), que é o número que o M4 pede — e
  não os números dos *fixtures*;
- **a reverificação dos *patches*** (W9), hoje `skipped`;
- `feeds_branch` e `used_as_index` saem sempre `null`, e o modelo ora lê isso como "não", ora inventa
  evidência;
- decidir o critério de nocividade diante dos leitores mortos do Racebench (§3.3).

Página anterior: [[Semana 7 — O Stage 3, Busca e Verificação]] · Trilha B até a W8:
[[Semana 5 a 8 — Trilha B (Triagem, Ablação, Reparo e Integração C3-C4)]].
