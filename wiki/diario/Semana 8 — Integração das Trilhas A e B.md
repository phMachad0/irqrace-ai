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
- decidir o critério de nocividade diante dos leitores mortos do Racebench (§3.3);
- o modo *offline* do desktop ainda copia a triagem e o reparo de um *run* anterior do mesmo caso;
  não finge a análise estática, mas finge a LLM.

Página anterior: [[Semana 7 — O Stage 3, Busca e Verificação]] · Trilha B até a W8:
[[Semana 5 a 8 — Trilha B (Triagem, Ablação, Reparo e Integração C3-C4)]].
