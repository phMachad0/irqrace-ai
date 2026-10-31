---
type: project
tags: [wiki, project, diario, pt-br]
sources: ["[[Roadmap]]", "[[LLM Stage Design]]", "[[Prompt Architecture]]", "[[LLM Triage]]", "[[LLM-Assisted Repair]]", "[[LLift (paper)]]", "[[IRIS (paper)]]", "[[SkipAnalyzer (paper)]]", "[[SDRacer (paper)]]", "[[SAST-Genius (paper)]]"]
updated: 2026-10-26
status: solid
---

# Semana 5 a 8 — Trilha B (Triagem, Ablação, Reparo e Integração C3–C4)

**Período:** 26 set – 20 out 2026 · **Trilha B (Integração LLM)** · Cobertura completa de [[Roadmap]] W1–W8 da Trilha B · **Marcos M1 (GO), M3 (Ablação) e Integração W8**. Página anterior: [[Semana 4 — Derivação de Candidatos e o Recall Gate]].

> [!note] Nota sobre o agrupamento
> A Trilha B iniciou em `track-b/llm-integration` após o congelamento dos contratos C1–C4 e avançou até fechar todos os entregáveis de código de W1 a W8 (conjunto de *fixtures*, *seam* agnóstico a provedor, arquitetura de *prompts* em cinco linhas de ablação, *resolver* C4 sobre árvore de código-fonte C, estágio de reparo com testemunha obrigatória e integração ponta a ponta sobre o *run store* C3). Esta página documenta toda a engenharia da Trilha B.

> [!note] Revisado em 26 out 2026
> Esta página descreve a Trilha B como ela estava em 20 out. Desde então: o projeto usa só trincas
> ([[Triples Only]]), e a estratégia de reparo `mask_access`, que só servia a pares, saiu do
> vocabulário — a §3.3 cita o código como ele é hoje; a triagem não descarta mais candidatos por erro
> de API; os registros passaram a levar o código-fonte, que antes saía vazio; e a §3.4 hoje roda
> sobre os stages 2 e 3 reais da Trilha A, depois do *merge* da `main`. Tudo isso está em
> [[Semana 8 — Integração das Trilhas A e B]]. As contagens de testes da §6 são as de 20 out.

## 1. Entregáveis do Roadmap (Trilha B, W1–W8)

| Semana / Item no [[Roadmap]] | Estado | Onde vive em `project-src/` |
| --- | --- | --- |
| **W1** — Protocolo C4 especificado pelo consumidor LLM | pronto | `contracts/c4-*.schema.json`, `src/irqrace/llm/resolver.py` |
| **W1** — 20 *fixtures* C2 rotulados (10 *bug points*, 10 *traps*, 6 pares adversariais) | pronto (20/20) | `fixtures/`, `scripts/build-fixtures.py`, `src/irqrace/llm/fixtures.py` |
| **W1 (Marco M1)** — *Feasibility probe* (go/no-go) | **GO** (recall 9/9, *trap rejection* 80%) | `ablation-groq.json`, `ablation-groq.md` |
| **W2** — *Harness* agnóstico a provedor (`anthropic`, `openai`, `ollama`), *cache* por *fingerprint* + *schema hash*, modelo de custo | pronto; o *cache* foi removido em 30 out ([[Semana 8 — Integração das Trilhas A e B]] §3.19) | `src/irqrace/llm/backends/`, `client.py`, `cost.py` |
| **W3** — Linha 2 (`+domain`): regras de domínio de interrupção (D#1) | pronto e medido | `src/irqrace/llm/prompts/domain_rules.md` |
| **W4** — Linha 3 (`+progressive`): protocolo C4 com *rules* de *recall* e `SourceBackedResolver` sobre a árvore `.c`/`.h` (D#2) | pronto | `src/irqrace/llm/resolver.py`, `prompts/context_requests.md` |
| **W5** — Linha 4 (`+decomposition`): separação entre viabilidade (*feasibility*) e nocividade (*harmfulness*) + propagação estilo IRIS (D#3) | pronto | `src/irqrace/llm/client.py`, `verdict.py`, `scoring.py` |
| **W6 (Marco M3)** — Linha 5 (`+self-validation`), votação majoritária ($n=3$), medição de consistência e gerador de tabela M3 | pronto | `src/irqrace/llm/prompts/self_validation.md`, `scripts/run-ablation.py`, `scripts/ablation-table.py` |
| **W7** — Estágio de reparo com testemunha (*witness*) obrigatória, vocabulário fechado e gabarito de 10 correções de referência (*Syntax Rate* e *Logic Rate*) | pronto | `src/irqrace/llm/repair.py`, `repair_references.py`, `scripts/run-repair.py` |
| **W8** — Integração ponta a ponta sobre diretórios C3 (`runs/<run_id>/`) e subcomandos CLI `irqrace llm triage` e `irqrace llm repair` | pronto | `src/irqrace/llm/pipeline.py`, `src/irqrace/cli.py` |

## 2. Conceitos técnicos desta trilha

**Política de decisão conservadora (*decision policy*).** Regra central de [[LLM Triage]]: o modelo de linguagem **nunca** descarta um candidato. Em vez de pedir ao modelo que escolha uma gaveta (*bucket*) de prioridade, o *harness* faz duas perguntas estruturadas — se a intercalação é viável (`feasible`, `infeasible`, `uncertain`) e, quando não inviável, se é nociva (`harmful`, `benign`, `uncertain`) — e uma função determinística em Python (`bucket_of`) deriva uma de quatro gavetas: `likely_real`, `uncertain`, `likely_benign`, `likely_infeasible`. Qualquer resposta `uncertain` em qualquer eixo força o candidato para a gaveta `uncertain`.

**Taxa de Inspeção (*Inspection Ratio*).** Métrica adotada de [[Reducing False Alarms (paper)]] e documentada em [[Precision Metrics]]: a fração do conjunto total de candidatos que um engenheiro humano precisa inspecionar, seguindo a ordem ranqueada pelo estágio LLM, até encontrar o **último** defeito real (*bug point*). Quando dois candidatos empatam em gaveta e confiança, o desempate coloca os defeitos reais por **último** (pior caso para o avaliador), evitando que a ordem de *hash* infle artificialmente a métrica.

**Prompting progressivo (*progressive prompting*, D#2) e o contrato C4.** Em vez de pré-computar uma fatia estática do programa (*slice*), o modelo recebe o registro C2 inicial e pode emitir blocos ```` ```request ```` pedindo definições de funções (`function_definition`), corpos de ISR (`isr_body`), expansões de macro (`macro_expansion`), declarações globais (`global_declaration`), definições de tipo (`type_definition`), todos os acessos a uma variável (`all_accesses_to`) ou caminhos de chamada (`all_call_paths`). Quando uma definição não existe (por exemplo, função externa de biblioteca ou ROM), o *resolver* responde `status: "not_found"` acompanhado da regra de autovalidação que obriga o modelo a assumir que a função ausente pode acessar a variável compartilhada.

**Testemunha de intercalação (*interleaving witness*).** Conceito adaptado de [[SAST-Genius (paper)]] para o reparo de concorrência ([[LLM-Assisted Repair]]): antes de propor um *diff*, o modelo deve explicitar qual fluxo preempta (`firing_flow`), em qual ponto (`preemption_point`), a ordem exata dos acessos (`access_order`, p.ex. `["A1", "B", "A2"]`) e qual estado diverge de toda execução serial (`divergence`).

**Taxas de Sintaxe (*Syntax Rate*) e de Lógica (*Logic Rate*).** Métricas de reparo de [[SkipAnalyzer (paper)]]. *Syntax Rate* mede a fração de *patches* que aplicam de forma limpa e passam por `clang/gcc -fsyntax-only` (reportando `None` — "não medido" — quando o compilador ou a suíte não estão presentes na máquina, jamais um 100% espúrio). *Logic Rate* compara o **efeito semântico** do reparo proposto (estratégia dentro do vocabulário fechado de [[SDRacer (paper)]], conjunto de IRQs mascaradas e intervalo de linhas coberto) contra 10 correções de referência escritas à mão (`repair_references.py`).

## 3. Decisões de arquitetura e trechos de código

### 3.1. A política de decisão é um tipo, não uma instrução de prompt

Arquivo: `project-src/src/irqrace/llm/verdict.py`

```python
def bucket_of(
    feasibility: FeasibilityAnswer,
    harmfulness: HarmfulnessAnswer | None,
) -> Bucket:
    """The decision policy of ``wiki/LLM Stage Design.md``, as a total function."""
    if feasibility.verdict is Feasibility.infeasible:
        return Bucket.likely_infeasible
    if feasibility.verdict is Feasibility.uncertain or harmfulness is None:
        return Bucket.uncertain
    if harmfulness.verdict is Harmfulness.uncertain:
        return Bucket.uncertain
    if harmfulness.verdict is Harmfulness.benign:
        return Bucket.likely_benign
    return Bucket.likely_real
```

E a função `score()` em `project-src/src/irqrace/llm/scoring.py` recusa avaliar qualquer conjunto onde falte ou sobre um único candidato:

```python
if set(by_id) != expected or len(triages) != len(fixtures):
    missing = expected - set(by_id)
    extra = set(by_id) - expected
    raise ScoringError(
        f"triage set does not match fixture set (missing={sorted(missing)}, "
        f"extra={sorted(extra)}); stage 2 must rank every candidate, never drop"
    )
```

### 3.2. `SourceBackedResolver`: respondendo C4 direto da árvore C

Arquivo: `project-src/src/irqrace/llm/resolver.py`

Na decisão de 27/09/2026 (`log.md`), a linha `+progressive` havia sido adiada porque o `RecordBackedResolver` só conhecia o próprio registro C2 e devolvia `not_found` para qualquer função chamadora fora dele (como `SetSelfCtrlFlag` em `svp_simple_029_001`). O `SourceBackedResolver` resolve isso lendo diretamente os arquivos `.c` e `.h` do sujeito quando disponíveis, mantendo o *fallback* para as regras de *recall* quando o símbolo é realmente externo:

```python
class SourceBackedResolver(RecordBackedResolver):
    served_by = "resolver"

    def _dispatch(
        self, kind: str, args: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        key = _key_for(kind, args)
        if (kind, key) in self.extra:
            return self.extra[(kind, key)], "ok"

        if kind in ("function_definition", "isr_body"):
            payload, status = super()._function_body(kind, args)
            if status == "ok" or not self._sources:
                return payload, status
            return self._source_function_body(kind, args)
```

### 3.3. Estágio de Reparo (W7): vocabulário fechado e *Logic Rate* por efeito

Arquivo: `project-src/src/irqrace/llm/repair.py`

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

Até 26 out o vocabulário tinha também `mask_access`, "mascarar um único acesso", válida só para
pares. Numa trinca ela protege uma ponta e deixa o intervalo onde o acesso remoto cai; com o projeto
usando só trincas, ela saiu ([[Semana 8 — Integração das Trilhas A e B]], §3.9).

No cálculo de `logic_rate`, mascarar todas as interrupções (`-1`) ou um superconjunto das IRQs exigidas pela referência sobre um intervalo `[covers_from_line, covers_to_line]` que contenha o intervalo de referência conta como logicamente correto, enquanto a justificativa de latência (`latency_note`) é exigida pelo schema:

```python
irqs = set(patch.masked_irqs)
masks_all = -1 in irqs or irqs >= ref.masked_irqs
ok = (
    (patch.strategy == ref.strategy
     or {patch.strategy, ref.strategy} <= equivalent)
    and masks_all
    and patch.covers_from_line <= ref.covers_from_line
    and patch.covers_to_line >= ref.covers_to_line
)
```

### 3.4. Integração W8 sobre o `RunStore` (C3)

Arquivo: `project-src/src/irqrace/llm/pipeline.py`

A função `prepare_context(store)` promove candidatos sobreviventes de `stage2` (ou `stage1` quando o estágio 2/Z3 ainda não rodou) que não tenham veredito `unsat` para `context/<cand_id>.json`, garantindo que `RunStore.check()` valide a Regra 6 do contrato C3. Em seguida, `triage_store()` e `repair_store()` gravam `llm/triage.jsonl`, `llm/<cand_id>/verdict.json`, `llm/<cand_id>/turns.jsonl`, `repair/<cand_id>/patch.diff` e atualizam `manifest.json`.

## 4. Achados experimentais e de engenharia na Trilha B

1. **Marco M1 (GO) e o teto de *recall* já na linha `simple`.** No primeiro experimento real com os 20 *fixtures* (`openai/gpt-oss-120b` via Groq), a linha de base `simple` atingiu **100% no portão de recall** (9/9 na primeira rodada; 10/10 após *retry*) e **80% de rejeição de armadilhas**, separando corretamente pares adversariais como `svp_simple_001_001` (intervalo perfurado por `isr_1` que reabilita a IRQ 2) e `svp_simple_017_001` vs `svp_simple_006_001` (mesma instrução em laço vs guarda satisfeita uma única vez).
2. **Conflito entre o critério de nocividade de Bai et al. e os leitores mortos do Racebench (Opção C).** Vários *bug points* do Racebench leem a variável compartilhada para uma variável local que nunca é lida (`reader = x;`). Quando a regra de nocividade foi explicitada em `+domain`, o modelo classificou corretamente esses casos como benignos, o que piorava a *Inspection Ratio*. Adotou-se a Opção C (`harm_scored=False` por padrão no Racebench): a pergunta de nocividade continua sendo feita e registrada, mas no Racebench pontua-se apenas a viabilidade.
3. **Três falsos sucessos silenciosos eliminados no *scoring*.** Linhas parciais (onde a API falhou na maioria dos candidatos) antes reportavam 100% de *recall* sobre os poucos candidatos avaliados. Agora `Score` e `RepairScore` carregam `n_expected` e marcam qualquer execução incompleta como `INCOMPLETE`, bloqueando o portão de recall.

## 5. Como reproduzir

```bash
# Validar contratos e rodar toda a suíte de testes offline (243 testes)
.\venv\Scripts\python.exe -m pytest project-src/tests --ignore=project-src/tests/test_racebench.py -q

# Inspecionar fixtures, prompts e backends
.\venv\Scripts\python.exe -m irqrace llm fixtures
.\venv\Scripts\python.exe -m irqrace llm prompts
.\venv\Scripts\python.exe -m irqrace llm backends

# Rodar a ablação (M3) contra um backend real. Toda execução chama o modelo.
.\venv\Scripts\python.exe project-src/scripts/run-ablation.py --backend anthropic:claude-opus-5 --samples 3 --resolver auto --include-deferred --json ablation-opus.json

# Rodar a avaliação do estágio de reparo (W7)
.\venv\Scripts\python.exe project-src/scripts/run-repair.py --backend anthropic:claude-opus-5 --json repair-opus.json --out repair-opus.md

# Rodar triagem e reparo ponta a ponta sobre um diretório de execução C3 (W8)
.\venv\Scripts\python.exe -m irqrace llm triage runs/<run_id> --backend anthropic:claude-opus-5
.\venv\Scripts\python.exe -m irqrace llm repair runs/<run_id> --backend anthropic:claude-opus-5
.\venv\Scripts\python.exe -m irqrace runstore check runs/<run_id>
```

## 6. Estado ao fim da implementação da Trilha B

**243 testes passando** (sendo **202 testes** dedicados à Trilha B em `tests/test_llm_*.py`), cobrindo contratos, *fixtures*, *backends*, *cache*, *prompts*, *scoring*, `RecordBackedResolver`, `SourceBackedResolver`, `RepairClient`, `score_repairs` e o pipeline C3 ponta a ponta (`prepare_context`, `triage_store`, `repair_store` e subcomandos CLI). Todo o código da Trilha B previsto no [[Roadmap]] (W1–W8) está implementado e pronto para as baterias de execução com chaves de API ou modelos locais.

Próxima página: [[Semana 8 — Integração das Trilhas A e B]].
