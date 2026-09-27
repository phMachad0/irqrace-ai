---
type: project
tags: [wiki, project, diario, pt-br]
sources: ["[[Roadmap]]", "[[Pair-Triple Unification]]", "[[Pipeline Design]]", "[[Soundness Assumptions]]"]
updated: 2026-09-18
status: draft
---

# Semana 4 — Derivação de Candidatos e o Recall Gate

**Período:** 21–25 set 2026 · **Trilha A** · Segunda metade de [[Roadmap]] W3–W4 ·
**Marco M2**. Página anterior: [[Semana 3 — O Front End do Stage 1]].

> [!note] Lembrete sobre a divisão
> W3–W4 é um bloco único no [[Roadmap]] e foi implementado de uma vez. A separação entre esta
> página e a anterior é temática.

## 1. Resultado

```
31/31 subjects analysed
candidates: 566 total, 18.3 per subject (316 triples, 250 pairs)
RECALL GATE: 48/48 annotated bug points present -- PASS
traps reported: 35/38     inspection ratio: 0.30 mean
```

**O portão de recall passou: 48 de 48.** É o critério de pronto do bloco e o Marco M2.

Sobre o número de candidatos: 18,3 por sujeito contra os ~208 por programa que o
[[IntRace (paper)]] reporta **não é uma vitória de precisão**. Estes são casos de 37 a 97 linhas
e o número do IntRace é sobre programas reais. O número que importa aqui é o portão.

## 2. Conceitos desta semana

**Serializabilidade.** Uma execução concorrente é *serializável* quando produz o mesmo resultado
de alguma execução sequencial das mesmas operações. Uma violação de atomicidade é exatamente uma
intercalação **não** serializável.

**As quatro intercalações não serializáveis.** Com `A₁` e `A₂` num fluxo e `B` em outro, só
quatro das oito combinações de leitura/escrita mudam o resultado:

| Forma | Por que quebra |
| --- | --- |
| `(R, W, R)` | as duas leituras veem valores diferentes |
| `(R, W, W)` | `A₂` escreve com base numa leitura já obsoleta |
| `(W, R, W)` | `B` enxerga um valor intermediário que não deveria existir |
| `(W, W, R)` | `A₂` lê o valor de `B`, não o de `A₁` |

As outras quatro são serializáveis: `(R,R,*)` não muda estado; `(W,R,R)` — `A₂` lê o valor de
`A₁` de qualquer jeito; `(W,W,W)` — `A₂` sobrescreve, e o estado final é o mesmo sem `B`.

**Registro C2 / *fingerprint*.** Ver [[Semana 1 — Contratos e Toolchain]].

**Portão de recall (*recall gate*).** A verificação de que **todos** os *bug points* anotados
aparecem em algum lugar do conjunto reportado. É a afirmação central do TCC transformada em algo
checável a cada execução.

## 3. Pares e trincas saem do **mesmo** conjunto de acessos

Esta é a regra de [[Pair-Triple Unification]] e é fácil de violar sem perceber, porque as duas
coisas parecem relacionadas:

> Uma trinca **nunca** é construída juntando pares confirmados, e um par **nunca** é inferido de
> uma trinca. São duas perguntas diferentes sobre um único conjunto de acessos.

### Pares

```python
def race_pairs(self) -> list[dict[str, Any]]:
    for obj_id, obj in self.objects.items():
        accs = [a for a in self.analysis["accesses"] if a["object"] == obj_id]
        for i, a in enumerate(accs):
            for b in accs[i + 1:]:
                if a["flow"] == b["flow"]:
                    continue
                if a["kind"] == "read" and b["kind"] == "read":
                    continue
                ...
```

Duas condições: fluxos **diferentes**, e pelo menos uma escrita — leitura contra leitura não é
condição de corrida.

A ordem dentro do par é **canônica, não semântica**. No estágio 1 nada se sabe sobre quem
preempta quem; `A₁` é o acesso do fluxo de menor prioridade puramente para que o mesmo par não
seja emitido duas vezes.

### Trincas

```python
for a1 in locals_:
    for a2 in locals_:
        if (a1["id"], a2["id"]) not in self.precede:
            continue
        if a1["id"] == a2["id"] and not allow_same:
            continue
        for b in remotes:
            shape = (a1["kind"], b["kind"], a2["kind"])
            if shape not in UNSERIALIZABLE:
                continue
            out.append(self._record("atomicity-triple", ..., obj))
```

`A₁` e `A₂` vêm do mesmo fluxo e têm que estar na relação `may_precede`; `B` vem de qualquer
outro fluxo. O `a1 == a2` é permitido — é o caso da mesma instrução dentro de um laço.

```python
UNSERIALIZABLE = {
    ("read", "write", "read"),
    ("read", "write", "write"),
    ("write", "write", "read"),
    ("write", "read", "write"),
}
```

**Isto é um filtro de verdade** — o único fora do estágio 3 — então está declarado na lista de
suposições (**H1b**) em vez de aplicado em silêncio. É correto em relação à definição padrão de
violação de atomicidade, e todos os 48 *bug points* anotados caem dentro do conjunto.

## 4. Os três defeitos que o portão de recall pegou

É exatamente por isso que ele está agendado antes de qualquer outra coisa.

### (a) Restringir posições compartilhadas a globais perdeu um *bug point*

Primeira execução: **47/48**, sem erro nenhum. O ausente:

```
MISSED bug1 *svp_simple_009_001_p WRW(32, 44, 33)
```

O código:

```c
void svp_simple_009_001_main() {
  int svp_simple_009_001_local_var1 = 0x01;     // variável de PILHA

  svp_simple_009_001_p = &svp_simple_009_001_local_var1;   // endereço escapa
  svp_simple_009_001_q = &svp_simple_009_001_local_var1;   // por dois globais

  *svp_simple_009_001_p = 0x02;   // linha 32  -> A1
  *svp_simple_009_001_q = 0x03;   // linha 33  -> A2 (mesmo objeto, outro ponteiro!)
}

void svp_simple_009_001_isr_1() {
  reader1 = *svp_simple_009_001_p;   // linha 44 -> B
}
```

A posição compartilhada é `local_var1`, uma variável **de pilha**, cujo endereço escapa para dois
ponteiros globais. Meu filtro `isGlobalObj()` a excluía. O que faz uma posição ser compartilhada
é **dois fluxos a alcançarem**, não onde ela foi alocada — e note que a anotação chama a variável
de `*p` enquanto `A₂` a acessa via `*q`, o que só a análise `may-alias` resolve.

O teste que trava a regressão diz a mesma coisa:

```python
def test_a_stack_object_shared_through_a_global_pointer_is_found(tmp_path):
    """Restringir o estágio 1 a globais de módulo perde esse bug point
    silenciosamente; o portão de recall foi o que pegou."""
    ...
    assert rep.bugs_detected == 1, "the stack-shared bug point is missing again"
```

### (b) Uma função chamada duas vezes torna uma instrução dois acessos

No `svp_simple_029_001`:

```c
ctrl_sts  = svp_simple_029_001_ptr_GetTmData(tm_para);      // linha 73
ctrl_sts -= svp_simple_029_001_ptr_GetTmData(tm_para + 1);  // linha 74
...
unsigned8 svp_simple_029_001_GetTmData(unsigned32 tm_name) {
  return svp_simple_029_001_tm_blocks[tm_name];             // linha 80
}
```

A suíte anota a trinca `<R,#80>, <W,#83>, <R,#80>` — a linha 80 como `A₁` **e** `A₂`. Mas a linha
80 não está em laço nenhum: ela executa duas vezes porque **a função é chamada duas vezes**.
Alcançabilidade no CFG intraprocedural diz que a instrução não pode preceder a si mesma.

É o mesmo argumento do laço, alcançado por chamadas repetidas em vez de aresta de retorno:

```cpp
auto multiInvocation = [&](const std::string &flow, const llvm::Function *fn) {
  ...
  if (sit->second.size() >= 2)              // dois ou mais call sites no fluxo
    return true;
  for (const auto &[caller, site] : sit->second) {
    analyse(caller);
    if (cfgs[caller]->inCycle(site))        // ou um call site dentro de um laço
      return true;
  }
  return false;
};
```

```cpp
if (a.fn == b.fn) {
  ok = cfgs[a.fn]->mayPrecede(a.inst, b.inst) || multiInvocation(a.flow, a.fn);
}
```

**A função de entrada do fluxo fica de fora de propósito.** Se uma ISR que dispara duas vezes
pode fornecer `A₁` e `A₂` em ativações separadas é uma pergunta sobre o **modelo de chegada de
interrupções**, não sobre o grafo de chamadas; respondê-la aqui seria decidi-la por acidente.
Isso virou a suposição **G2c**, marcada para revisão junto com **E3**.

### (c) Spills de prólogo produziam candidatos sem posição no fonte

Descrito na [[Semana 3 — O Front End do Stage 1]]. O sintoma foi uma violação de contrato, o que
é o comportamento desejado — o C2 exige `line >= 1`:

```
stage1 candidate c28e41d364f35e4e0 does not conform to contract c2:
  accesses/0/source/line: 0 is less than the minimum of 1
```

O schema pegou o problema em vez de deixá-lo virar um registro inútil rio abaixo.

## 5. A errata da semana 2 se pagou na hora

O *bug point* do `svp_simple_019_001` é detectado nas linhas **(45, 71, 59)** — as **corrigidas**:

```json
{"kind": "bug", "index": 1, "variable": "svp_simple_019_001_global_var1",
 "pattern": "RWR", "lines": [45, 71, 59],
 "detected": true, "candidate_id": "caea1fadc837d54db", "rank": 3,
 "kinds_agree": true, "name_agrees": true}
```

O analisador reporta a linha 71, onde a escrita realmente está. A anotação publicada diz 65, que
é `idlerun();`. **Sem a errata isso teria sido um `MISSED` que não se deve a nada na ferramenta.**

## 6. As três armadilhas que o estágio 1 não reporta

Todas explicadas; nenhuma é sintoma.

| Caso | Forma corrigida | Motivo |
| --- | --- | --- |
| `002` trap 3 | `(W,W,W)` | serializável — fora das quatro formas, por projeto |
| `017` trap 1 | `(W,W,W)` | idem |
| `015` trap 1 | `(R,W,R)` | `A₁` e `A₂` são os dois braços de `p == 1 ? v : v` |

O caso 015 merece nota: os dois braços do operador ternário são **mutuamente exclusivos**, o CFG
estabelece isso estruturalmente, e portanto **não há candidato a gerar**. Isso é geração, não
filtragem — a distinção importa, porque a regra do projeto é que só o estágio 3 pode descartar.

## 7. O que sai gravado

Cada execução vira um diretório C3 completo. Os candidatos são registros C2 em NDJSON, com
`solver_result: not_run` e sem bloco de máscara — porque o estágio 1 não sabe nada disso ainda:

```python
def test_stage1_never_records_a_drop(tmp_path):
    """O estágio 1 é o gerador. Só uma prova pode descartar, e só rio abaixo."""
    assert all(c["solver_result"]["verdict"] == "not_run" for c in cands)
    assert all(c["emitted_by"]["stage"] == "stage1" for c in cands)
```

E cada execução grava também o seu próprio relatório de avaliação, para que um número de recall
nunca fique separado da execução que o produziu nem do manifesto que registra a unidade de
contagem e a regra de casamento usadas:

```json
{
  "subject": "svp_simple_019_001",
  "counting_unit": "per-triple-instance",
  "match_rule": "same-subject-same-location-same-ordered-lines",
  "ground_truth": "racebench-2.1_remarks + curated errata",
  "bug_points": 1, "bugs_detected": 1, "recall_gate": true,
  "traps": 4, "traps_reported": 4,
  "candidates_reported": 15,
  "inspection_ratio": 0.2666666666666667
}
```

Os 31 diretórios passam no `runstore check`, isto é, na regra 6 do C3: nenhum candidato
desapareceu sem prova.

## 8. Como reproduzir

```bash
irqrace stage1 bench/configs/svp_simple_001_001.yaml
```

```bash
irqrace stage1-all
```

## 9. Estado ao fim do bloco

203 testes. [[Soundness Assumptions]] ganhou sete entradas nesta semana — **A2b**, **C1b**,
**C2b**, **G2b**, **G2c**, **H1b**, **H1c** — das quais **G2c** é uma escolha deliberada do lado
da precisão e está marcada para revisão.

Ainda não existem: estágio 2 (máscara e o filtro de concorrência), estágio Z3, estágio de LLM,
dashboard.

**Decisões pendentes para a semana 5**, ambas do modelo de interrupções e ambas capazes de mudar
o conjunto de candidatos:

- **E3** — uma ISR pode preemptar a si mesma? Hoje o padrão é *não*, e é a única suposição da
  lista que não é segura para recall.
- **G2c** — um intervalo `[A₁, A₂]` pode atravessar duas ativações do mesmo fluxo?
