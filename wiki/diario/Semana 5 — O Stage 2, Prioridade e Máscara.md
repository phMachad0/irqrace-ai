---
type: project
tags: [wiki, project, diario, pt-br]
sources: ["[[Roadmap]]", "[[Pipeline Design]]", "[[Soundness Assumptions]]", "[[IntRace (paper)]]", "[[Pair-Triple Unification]]"]
updated: 2026-10-22
status: draft
---

# Semana 5 — O Stage 2, Prioridade e Máscara

**Período planejado:** 28 set–2 out 2026 · **implementado em:** 22 out 2026 · **Trilha A** ·
[[Roadmap]] W5. Página anterior: [[Semana 4 — Derivação de Candidatos e o Recall Gate]].
Próxima: [[Semana 6 — O Stage 3, a Codificação]].

> [!note] Sobre as datas
> O [[Roadmap]] põe esta semana em 28 set–2 out. O último commit da semana 4 é de 27 set e o
> stage 2 foi escrito em 22 out, de uma vez. A página descreve o que existe no código nessa data;
> o atraso de calendário está registrado no próprio [[Roadmap]].

## 1. O que a semana devia entregar

| Item do Roadmap (W5) | Estado |
| --- | --- |
| Modelo de blocos `(T, I, S, p)`; prioridade com **maior = mais alta** | feito — `config.can_preempt` + `masking.may_preempt` (aninhamento) |
| Timing sem restrição | feito — todo registro diz `timing: unconstrained` |
| Máscara por dataflow: mascarada só se mascarada em **todo** caminho | feito — `src/irqrace/masking.py` |
| Propriedade de ponto para pares, **de intervalo para trincas** | feito — o intervalo é todo ponto de todo caminho de A₁ a A₂, incluindo funções chamadas |
| Decisões de prioridade igual e de modelo de chegada explícitas, no manifesto | feito — e mais `triple_interval: single-activation` (G2c) |
| **Pronto quando:** attrition medida contra os 54,2% do IntRace | 23,0% no total, **12,0% por concorrência** (§10) |
| **Pronto quando:** recall gate continua 100% | **48/48** depois do stage 2 |

## 2. Resultado

```
31/31 subjects analysed
stage 1: 566 candidates, 18.3 per subject (316 triples, 250 pairs)  [2376 ms total]
stage 2: 436 kept (202 triples, 234 pairs), 130 dropped with proof (masking 23, no-path 62, priority 45)  [2126 ms total]
attrition: 23.0% overall -- triples 36.1%, pairs 6.4%; 0-45% per subject
  of which concurrency (priority + masking): 12.0%; no-path is stage 1's cross-function may-precede refined, not a concurrency result
  for scale: IntRace reports 54.2% (33-63% per project) for its stage 2, on data-race pairs in real-world subjects
RECALL GATE (stage2): 48/48 annotated bug points present -- PASS
traps reported: 35/38 after stage 1, 30/38 after stage 2 (5 rejected by stage 2)
inspection ratio: 0.29 mean over 31 subject(s) whose bug points were all found
runstore check: 31/31 runs conform to C3 (rule 6: nothing vanished without a proof)
```

**O portão de recall continua em 48 de 48** depois do primeiro estágio que tem permissão para
descartar alguma coisa. Cada um dos 130 descartes deixa uma prova escrita (§9). Nos 31 sujeitos
os dois estágios somam cerca de 4,5 s de análise (2,4 s o stage 1, 2,1 s o stage 2, com variação entre execuções), e 275
testes passam.

## 3. Conceitos desta semana

**Fluxo, ISR, prioridade.** Ver [[Semana 1 — Contratos e Toolchain]]. Um *fluxo* é a tarefa
principal ou uma ISR (*interrupt service routine*, a função que o hardware chama quando uma
interrupção dispara). No Racebench, **número maior = prioridade mais alta** ([[Contradictions]]
#3), e a tarefa principal tem prioridade 0.

**Preempção.** Um fluxo de prioridade mais alta interrompe (*preempta*) um de prioridade mais
baixa, executa até o fim e devolve o controle. O inverso nunca acontece: a tarefa nunca preempta
uma ISR, e uma ISR de prioridade 1 nunca interrompe uma de prioridade 2. Essa assimetria é o que
separa concorrência por interrupção de concorrência por threads ([[Asymmetric Preemption]]).

**Aninhamento (*nesting*).** Uma ISR pode ser preemptada por outra ISR de prioridade mais alta:
`main` → `isr_1` → `isr_2`. A *profundidade de aninhamento* é quantas preempções empilhadas
são necessárias até o fluxo de interesse rodar ([[Interrupt Nesting]]).

**Máscara de interrupção.** O mecanismo de exclusão mútua deste domínio. `disable_isr(n)`
impede a interrupção `n` de disparar; `enable_isr(n)` permite de novo; `n = -1` significa todas.
Ao contrário de um *lock*, a máscara é **um único registrador de hardware compartilhado por
todos os fluxos**: o que uma ISR faz com ela continua valendo depois que ela retorna. Esse fato
é a origem de todos os achados desta semana.

**Propriedade de ponto e propriedade de intervalo.** Para um **par** `(A, B)` a pergunta é: o
fluxo de B pode rodar *no instante* de A? Para uma **trinca** `(A₁, B, A₂)`: o fluxo de B pode
rodar *em algum ponto* entre A₁ e A₂? São perguntas diferentes, e uma não se deduz da outra
([[Pair-Triple Unification]]).

**Análise de fluxo de dados (*dataflow analysis*).** Uma técnica que calcula, para cada ponto
do programa, um fato que vale em toda execução que passa por ali — aqui, "quais interrupções
podem estar habilitadas". Percorre o CFG (*control-flow graph*, o grafo de blocos básicos e
desvios de uma função; ver [[Semana 3 — O Front End do Stage 1]]) propagando estados até nada
mais mudar.

**Estado abstrato, reticulado, *join*.** O *estado* em um ponto guarda, para cada interrupção, o
**conjunto** de valores que ela pode ter ali: `D` (desabilitada), `E` (habilitada), `U`
(desconhecida — tratada como habilitada). Quando dois caminhos se encontram, os conjuntos são
unidos: esse é o *join*. O conjunto de todos os estados possíveis, ordenado por inclusão, é um
*reticulado* (*lattice*) finito, e é isso que garante que a análise termina.

**"Mascarada em todo caminho".** Uma interrupção conta como mascarada num ponto **só se o seu
conjunto for exatamente `{D}`**. Mascarada em *algum* caminho não basta ([[Soundness Assumptions]]
F1). Errar essa direção é transformar um defeito real num descarte.

**Ponto fixo e iteração de Kleene.** Muitas incógnitas aqui dependem umas das outras (o estado
de entrada de uma ISR depende dos estados da tarefa, que dependem do que a ISR deixa para
trás). Resolve-se começando de "nada é alcançável" (o *bottom*) e reaplicando as equações até
nada mudar. Esse resultado final é o *menor ponto fixo* (*least fixpoint*). **As iterações
intermediárias não são corretas** — ainda faltam possibilidades —, por isso só o resultado
convergido é usado (§8).

**Resumo de função (*summary*) e o valor simbólico `K`.** Em vez de analisar uma função de novo
a cada chamada, analisa-se uma vez em termos do estado de entrada dela: `K` significa "o que
estava valendo quando a função começou". Na chamada, `K` é substituído pelo estado real
daquele ponto de chamada.

**Sensibilidade a contexto.** Uma análise é *sensível a contexto* quando distingue as
diferentes situações (contextos) em que um mesmo código roda. Aqui isso importou para ISRs
aninhadas (§7).

**Interferência.** Em cada ponto onde outro fluxo pode disparar, o estado pode passar a conter
também qualquer valor que esse fluxo deixa para trás ao retornar.

**Supergrafo (*supergraph*).** Os CFGs de todas as funções de um fluxo ligados por arestas de
chamada (do ponto de chamada à entrada da função) e de retorno (das saídas da função de volta ao
ponto de chamada). Serve para perguntar "existe caminho de A₁ a A₂?" atravessando funções.

**Attrition.** A fração de candidatos que um estágio remove. O [[IntRace (paper)]] reporta
54,2% para o seu stage 2.

**Recall gate e Inspection Ratio.** Ver [[Semana 4 — Derivação de Candidatos e o Recall Gate]] e
[[Precision Metrics]]. O portão exige que **todo** *bug point* anotado sobreviva; a Inspection
Ratio mede quanto da lista um revisor precisa ler para achar todos.

## 4. A arquitetura: C++ extrai, Python analisa

O `irqrace-stage1` (C++, sobre LLVM e SVF) já tinha o grafo de chamadas e a posição de cada
acesso. Esta semana ele passou a emitir também um **CFG de eventos**: por função, os blocos
básicos, seus sucessores e, em ordem, só os eventos que interessam à máscara — acessos,
chamadas, primitivas de máscara, assembly inline. Entre dois eventos nada muda a máscara, então
isso é tudo de que a análise precisa.

`analysis/src/irqrace-stage1.cpp`:

```cpp
  // It covers every function with a body reachable from any flow, INCLUDING
  // the externals stage 1 treats as transparent. `init` touches no shared
  // memory, but it calls `enable_isr(-1)`: a model that is transparent for
  // accesses is not thereby transparent for the interrupt mask.
```

Saída real para `svp_simple_001_001` — a função `init` e o bloco de entrada de `main`:

```
FN init
  b0 succ=[] exit=True [('call', 25, ['enable_isr'], [-1])]
FN svp_simple_001_001_main
  b0 succ=[1] exit=False [('call', 26, ['init'], []), ('call', 28, ['disable_isr'], [2]), ('call', 30, ['idlerun'], [])]
```

Os argumentos constantes vêm junto (`[-1]`, `[2]`), para que o Python leia `disable_isr(2)` sem
saber de antemão qual argumento nomeia a interrupção — isso está no C1 (`irq_arg`). Cada
registro C2 do stage 1 ganhou um ponteiro de volta para a posição do acesso nesse CFG
(`accesses[].ir`), fora do *fingerprint*: o id do candidato não muda.

A análise roda em Python, sobre `stage1/accesses.json` já gravado no *run store*. O stage 2 não
recompila nem reexecuta o SVF.

## 5. O domínio: três valores, `K` e a origem de cada valor

Cada valor carrega a sua **origem** — o `disable_isr(2)` da linha 28, o `enable_isr(2)` da linha
46 de `isr_1`, o estado inicial. Assim uma prova pode ser enunciada, e uma dúvida também:
"irq 2 não está provadamente mascarada aqui porque `isr_1` pode rodar antes e o seu
`enable_isr(2)` persiste" é a frase de que a etapa de LLM e a monografia precisam.

`src/irqrace/masking.py`:

```python
def masked(cell) -> bool:
    """Masked on every path: the only reading of "masked" this project uses."""
    return bool(cell) and all(v == D for v, _ in cell)
```

A substituição de `K` é uma única operação, usada tanto para aplicar o resumo de uma função
chamada quanto para concretizar um estado simbólico contra a entrada da função:

```python
def apply(summary, state):
    """Substitute ``state`` for the symbolic ``K`` values of ``summary``.

    Used both to apply a callee's summary at a call site and to concretise a
    symbolic state against a function's entry state -- the same operation.
    """
    if summary is None or state is None:
        return None
    out = []
    for cell_sum, cell_in in zip(summary, state):
        acc: set = set()
        for v, o in cell_sum:
            if v == K:
                acc |= cell_in
            else:
                acc.add((v, o))
        out.append(frozenset(acc))
    return tuple(out)
```

Por que resumos e não um supergrafo simples para a máscara: `idlerun()` é chamada em
`svp_simple_001_001` antes e depois de `disable_isr(2)`. Num supergrafo que junta todas as
chamadas, `idlerun` retornaria "talvez habilitada" para os dois pontos, e a seção crítica da
linha 28 se perderia por uma chamada a uma função vazia. Com resumos, o efeito de `idlerun` é
"mantém `K`", aplicado a cada ponto de chamada com o estado daquele ponto
(`test_a_helper_called_inside_and_outside_a_section_does_not_blur_it`).

## 6. As funções de transferência, e o argumento que não é constante

`src/irqrace/masking.py`:

```python
        arg = ev.args[prim.irq_arg] if prim.irq_arg < len(ev.args) else None
        if arg is None:
            o = Origin("mask", fn, ev.line, f"{prim.function}(<non-constant>)")
            mode = prim.non_constant_arg
            if mode == "none":
                return s
            if mode == "all":
                return self._set(s, self.irqs, v, o)
            # 'unknown': the argument may name any interrupt, or none. A disable
            # may leave each one as it was or masked -- which can never make it
            # masked on every path. An enable may unmask any of them.
            return self._smear(s, D if v == D else U, o)
```

O comentário é a regra de corretude inteira: um `disable_isr(x)` com `x` desconhecido **acrescenta**
`D` ao conjunto de cada interrupção, sem substituir nada — e um conjunto que contém outra coisa
além de `D` nunca é "mascarado". Um `enable_isr(x)` desconhecido acrescenta `U` a todas.

Três outras regras do mesmo tipo, todas novas em [[Soundness Assumptions]] (**F6**): uma função
externa sem corpo e fora da lista `externals.models` do C1 **pode habilitar qualquer
interrupção** (pense numa HAL de fabricante que executa `cpsie i`); assembly inline também pode;
uma chamada indireta sem alvo resolvido também pode. Uma externa modelada (`rand`, no
Racebench) deixa a máscara como está.

## 7. Interferência, e por que a máscara é um problema de programa inteiro

Esta é a parte que a implementação óbvia erra, e que `project-src/docs/masking-semantics.md`
já documentava desde a semana 1: no `svp_simple_001_001`, `main` mascara irq 2 na linha 28 e
nunca desmascara — mas `isr_1` pode rodar no meio e chamar `enable_isr(2)`.

`src/irqrace/masking.py`:

```python
    def _close(self, flow: str, fn: str, s):
        """Apply, to a closure, everything a flow firing here may leave behind."""
        if s is None:
            return None
        entry = self.fn_entry.get((flow, fn))
        while True:
            c = concretise(s, entry)
            grown = s
            for G in self.direct(flow, c):
                grown = join(grown, self.effect.get(G.id))
            if grown == s:
                return s
            s = grown
```

Em cada ponto: quais fluxos podem disparar aqui (`direct`)? Acrescente o que cada um deixa
para trás (`effect`). Repita até estabilizar, porque o que um deixa pode permitir que outro
dispare. O resultado no ponto da linha 32 de `main`, com e sem essa interferência:

```
main 32 {1: ['E'], 2: ['D', 'E']} local {1: ['E'], 2: ['D']}
```

A visão "local" diz irq 2 mascarada; a visão correta diz que não. **Calculado só a partir do CFG
de `main`, o *bug point* do caso 1 de 31 seria descartado.**

**A máscara persiste depois do retorno?** Depende do hardware: em alguns, o retorno de
interrupção restaura o estado anterior; em outros, não. A análise toma a **união** das duas
possibilidades (**F7**): o que uma ISR habilita pode quebrar uma prova no fluxo que ela
interrompeu; o que ela desabilita nunca ajuda a construir uma
(`test_an_isrs_disable_never_protects_the_flow_it_preempted`).

## 8. Onde uma ISR começa — e o ponto fixo

Uma ISR começa no estado de qualquer ponto onde ela pode disparar, em qualquer fluxo. Esse é o
estado de entrada dela: a união de todos esses pontos (**F8**).

`src/irqrace/masking.py`:

```python
                        # F8: an ISR starts in the state of any point it may fire at.
                        for G in self.direct(F.id, c):
                            isr_entry[G.id] = join(isr_entry[G.id], c)
```

Essa equação depende dos estados de todos os fluxos, que dependem do que cada ISR deixa para
trás, que depende do estado de entrada dela. O sistema inteiro é resolvido como um ponto fixo:

```python
        for rnd in range(1, self.MAX_ROUNDS + 1):
            before = (dict(self.summary), dict(self.fn_entry),
                      dict(self.isr_entry), dict(self.effect))
            for F in self.flows:
                for fn in self.reach[F.id]:
                    pts, ex = self._analyse(F.id, fn)
                    self.points[(F.id, fn)] = pts
                    self.summary[(F.id, fn)] = ex
            self.fn_entry, self.isr_entry = self._entries()
            self.effect = {G.id: strip_entry(self.summary.get((G.id, G.entry)))
                           for G in self.isrs}
            if (self.summary, self.fn_entry, self.isr_entry, self.effect) == before:
                self.rounds = rnd
                break
        else:
            raise MaskAnalysisError(
                f"masking analysis did not converge in {self.MAX_ROUNDS} rounds; "
                "refusing to use an intermediate iterate, which is not sound")
```

O limite de rodadas não é um corte: se for atingido, a análise **levanta erro** em vez de
devolver uma resposta parcial. Nos 31 sujeitos ela converge em 3 a 6 rodadas.

> [!warning] Uma regra registrada na semana 1 foi revista
> `docs/masking-semantics.md` dizia para calcular partindo de "tudo pode rodar" e apertando,
> "nunca o contrário". As duas direções são corretas **na convergência**; a diferença é o que
> significa uma iteração intermediária. Descendo do topo, toda iteração já é correta, mas o
> processo pode parar num ponto fixo maior que o menor quando fluxos podem se preemptar em ciclo
> (prioridades iguais, reentrância) — e o menor ponto fixo é a resposta precisa. A escolha foi
> **subir do *bottom* e nunca devolver uma iteração não convergida**
> (`test_an_intermediate_iterate_is_never_returned`). A preocupação original — anunciar uma
> prova antes de tê-la — é atendida por essa regra, e não pela direção. O raciocínio está
> registrado no próprio documento, numa seção "Correction", em vez de apagado.

## 9. As decisões: o que fica e o que sai, e a prova de cada descarte

**Pares — propriedade de ponto.** `(A, B)` sobrevive se o fluxo de B pode rodar enquanto o
fluxo de A está em A, ou o contrário.

**Trincas — propriedade de intervalo.** `(A₁, B, A₂)` sobrevive se o fluxo de B pode rodar em
*algum* ponto de *algum* caminho de A₁ a A₂, diretamente ou aninhado dentro de outro fluxo que
roda ali. O intervalo é calculado no supergrafo do fluxo:

`src/irqrace/stage2.py`:

```python
    def interval(self, after_a1: tuple, before_a2: tuple) -> frozenset:
        """Every point on some path from just after A1 to just before A2."""
        if after_a1 not in self._fwd:
            self._fwd[after_a1] = self._closure(after_a1, self.succ)
        if before_a2 not in self._bwd:
            self._bwd[before_a2] = self._closure(before_a2, self.pred)
        return self._fwd[after_a1] & self._bwd[before_a2]
```

Tudo que é alcançável depois de A₁ **e** que alcança A₂. O supergrafo devolve cada função a
*todos* os seus pontos de chamada no fluxo — isso cria caminhos que não existem, o que só pode
*acrescentar* pontos ao intervalo: a direção segura.

**Toda remoção é uma prova** ([[Soundness Assumptions]] **H1d**). Cada descarte grava uma linha
em `stage2/dropped.jsonl` com o motivo, o argumento em prosa com as linhas do fonte, e os
identificadores das suposições em que ele se apoia. A primeira armadilha de
`svp_simple_003_001`, rejeitada (`contracts/examples/c3-drop-example.json`, trecho):

```json
  "lines": [38, 62, 43],
  "local_flow": "main",
  "pattern": "RWR",
  "proof": "isr_1 may preempt main on priority, but irq 1 (isr_1) is masked at every point of every path from line 38 to line 43 in main (13 program points, callees included), even after every mask change a flow able to run there could make. Masked by: disable_isr(1) at line 33 in svp_simple_003_001_main. No other flow may run inside the interval at all.",
  "reason": "masking",
  "relies_on": ["B1", "E1", "E4", "F1", "F2", "F3", "F5", "F6", "F7", "F8", "F9", "G2c", "H1d"],
```

O campo `relies_on` existe para o dia em que uma suposição for revista: basta procurar o
identificador nos arquivos de descarte, em vez de redescobrir quais resultados dependiam dela.

E a regra é verificada, não apenas descrita. `src/irqrace/runstore.py`:

```python
            for cid in sorted(s1 - s2 - dropped):
                problems.append(
                    f"candidate {cid} is in stage1 but neither in stage2 nor in "
                    "stage2/dropped.jsonl: it vanished without a proof, which is a "
                    "silent recall loss (C3 rule 6)")
```

Os três motivos de descarte:

| Motivo | Quantos | O que prova |
| --- | --- | --- |
| `priority` | 45 | o fluxo de B nunca roda enquanto o de A₁ está ativo — quase sempre `main` como B entre dois acessos de uma ISR |
| `masking` | 23 | podia por prioridade, mas a interrupção dele está mascarada em todo o intervalo, e nada que roda ali a desmascara |
| `no-path` | 62 | não existe caminho de A₁ a A₂ numa ativação do fluxo (§10d) |

## 10. Os achados

### (a) Uma armadilha do Racebench é alcançável segundo o próprio README

A primeira armadilha do `svp_simple_001_001`, `global_var <W#43><R#63><W#44>`, é rotulada falso
positivo porque irq 2 fica mascarada por `main` até `isr_1` desmascarar na linha 46, *depois* das
duas escritas. O argumento supõe que `isr_1` sempre **começa** com irq 2 mascarada. O README da
suíte diz que uma interrupção pode disparar sempre que estiver habilitada, "em momento, posição e
número de vezes indeterminados". Há então duas rotas pelas quais `isr_1` começa com irq 2
habilitada:

1. **Antes do `disable_isr(2)` de `main`.** `init()`, chamada na linha 26, executa
   `enable_isr(-1)`, e `main` só mascara irq 2 na linha 28. `isr_1` pode disparar entre as duas.
2. **Depois de uma ativação anterior de si mesma.** O `enable_isr(2)` da linha 46 é um *unlock*
   global e persiste. Uma segunda ativação de `isr_1` começa com irq 2 habilitada.

Nas duas, `isr_2` (prioridade 2) preempta `isr_1` entre as linhas 43 e 44 e lê o valor
intermediário. A interleaving é alcançável; o stage 2 mantém o candidato e explica por quê:

```
isr_2 may run within [line 43, line 44] of isr_1, at nesting depth 1; irq 2 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init; enable_isr(2) at line 46 in svp_simple_001_001_isr_1; isr_1 may itself start with irq 2 unmasked: an ISR begins in the state of whatever point it preempted, and isr_1 may fire wherever irq 2 is unmasked -- including before any masking call in the flows it preempts (F8).
```

**Isto inverte uma afirmação da semana 1.** As *fixtures* `c2-trap.json` e `c2-bugpoint.json`
foram construídas à mão na semana 1 dizendo que a armadilha era provadamente inviável, e
reportavam em cada acesso a visão *local* (`disabled: [2]` na linha 32 de `main`) — exatamente o
valor contra o qual `masking-semantics.md` alerta, e que um stage 2 correto não consegue
produzir. Agora as duas carregam o que o stage 2 realmente emite. E a *run fixture* fazia o
solver devolver `unsat` nessa armadilha; o exemplo de `unsat` passou a ser a *segunda*
armadilha do arquivo, `<W#32><R#60><W#35>` (`c2-trap-array-index.json`), onde ele é verdadeiro:
B lê o elemento 1000 e A₂ escreve só o 9999.

O rótulo **não** foi corrigido — corrigir rótulo é redecidir a *ground truth*, a mesma linha que a
errata traçou para o `svp_simple_019_001`. Ficou registrado como [[Soundness Assumptions]] **I4**
e [[Contradictions]] #7. A consequência prática: **uma ferramenta correta não consegue rejeitar
as 38 armadilhas** desta suíte.

Por que as ferramentas publicadas concordam com o rótulo — evidência parcial: o código local do
[[BMC4AV (tool)]] usa a instrumentação `--isr` do [[CBMC]], que só insere chamada de ISR antes de
instruções que conflitam com o conjunto de leitura/escrita da ISR
(`goto-instrument/interrupt.cpp`, ll. 89–120). Entre `init()` e `disable_isr(2)` não há nenhuma,
então nesse modelo a primeira rota não existe. Como a segunda é excluída não foi estabelecido;
ficou em [[Open Questions]].

### (b) O teste que falhou ensinou a segunda rota

Escrevi um teste para mostrar que a prova *funciona* quando o programa a garante: interrupções
começam desligadas e `main` mascara irq 2 antes de habilitar irq 1, de modo que `isr_1` não pode
disparar antes da máscara. Esperava irq 2 mascarada na linha 43. O teste falhou:

```
E       AssertionError: assert False
E        +  where False = is_masked(<irqrace.masking.MaskAnalysis object at 0x7baea0289390>, (frozenset({('E', Origin(kind='mask', function='main', line=29, text='enable_isr(1)'))}), frozenset({('D', Origin(kind...main', line=28, text='disable_isr(2)')), ('E', Origin(kind='mask', function='isr_1', line=46, text='enable_isr(2)'))})), 2)
```

A origem do `E` é a linha 46 **da própria `isr_1`**: uma ativação anterior deixou irq 2 habilitada.
A análise estava certa e a expectativa, errada. O teste virou dois: um que documenta a segunda rota
(`test_an_earlier_activation_can_leave_the_next_one_unmasked`) e um em que as duas rotas estão
fechadas — `isr_1` mascara irq 2 de novo antes de retornar — e a prova sai
(`test_when_the_program_guarantees_the_isr_starts_masked_the_proof_holds`). Corretude não é
dúvida generalizada.

### (c) A entrada global de uma ISR escondia três armadilhas

Na primeira execução completa, só 2 armadilhas eram rejeitadas. Auditando as que sobravam em
casos com máscara, três tinham o mesmo formato: `svp_simple_027/028/030`, com B em `isr_3`.

```c
int svp_simple_028_001__main() {
  svp_simple_028_001_init();

  disable_isr(-1);
  enable_isr(1);
  if (svp_simple_028_001_gloable_var > 12) {  
    svp_simple_028_001_gloable_var = 0;     
  }
```

Em `[29, 30]` irq 3 está mascarada, `isr_1` só habilita irq 2, `isr_2` não habilita nada: `isr_3`
não tem como rodar ali. Mas a análise decidia "o que pode rodar dentro de `isr_1`" a partir do
estado de entrada **global** de `isr_1` — que inclui ativações que começaram *antes* da linha 27,
com irq 3 habilitada. Uma ativação aninhada *dentro* do intervalo, porém, começou dentro dele.

A correção é sensível a contexto: o que pode rodar dentro de uma ativação é decidido a partir do
estado do ponto onde ela disparou. Os estados dentro de cada fluxo são mantidos relativos à
entrada dele justamente para poderem ser reconcretizados por ponto de disparo.

`src/irqrace/stage2.py`:

```python
    def inside(self, X: str, entry) -> frozenset[str]:
        """Flows that may run while X is active, X having started in ``entry``."""
        key = (X, entry)
        if key in self._inside:
            return self._inside[key]
        if key in self._stack:
            return frozenset(self.nested[X])  # a preemption cycle: the global answer
        self._stack.add(key)
        acc: set[str] = set()
        for rel in self.rel_points[X]:
            acc |= self.run(X, apply(rel, entry))
        self._stack.discard(key)
        self._inside[key] = frozenset(acc)
        return self._inside[key]
```

Onde a recursão encontra a si mesma (prioridades iguais, reentrância), cai na resposta global, que
é correta. Resultado: **5 armadilhas rejeitadas em vez de 2**, 12 descartes a mais, portão ainda
em 48/48. A versão global era correta, só cega: perda de precisão, não de recall — e por isso foi
achada auditando armadilhas, não pelo portão. A suposição ficou em **F9**.

### (d) 62 descartes que não são concorrência

O motivo `no-path` não fazia parte do plano. O stage 1 supõe que dois acessos em funções
diferentes do mesmo fluxo *podem* se preceder (é a sobre-aproximação da
[[Semana 3 — O Front End do Stage 1]]), e conta uma função como "executada mais de uma vez" quando
o fluxo alcança dois pontos de chamada dela (G2b). O supergrafo do stage 2 refina as duas coisas.
Auditei os casos com mais descartes: em `svp_simple_022_001`, A₁ na linha 39 é a última instrução
de `main` — nada vem depois. Em `svp_simple_029_001`, `isr_1` chama `SetTmData` nos dois braços de
um `if/else`:

```c
void svp_simple_029_001_isr_1() {
  if (svp_simple_029_001_average_adjust_flag == 0xFF) {
    svp_simple_029_001_average_adjust_count++;
    svp_simple_029_001_ptr_SetTmData(
        36, svp_simple_029_001_average_adjust_count); 
  } else {
    svp_simple_029_001_average_adjust_count = 0;
    svp_simple_029_001_ptr_SetTmData(36, svp_simple_029_001_average_adjust_count);
  }
}
```

Dois pontos de chamada, mas exclusivos: uma ativação não executa a linha 83 duas vezes. São
descartes corretos, mas são **um refinamento do stage 1, não um resultado de concorrência**, e o
relatório os separa da attrition comparada com o IntRace.

### (e) Uma frase de prova errada com veredito certo

No `svp_simple_026_001`, uma prova dizia que `isr_2` "mantém irq 1 mascarada em todo o seu
código". Não mantém: `isr_2` pode começar com irq 1 habilitada. O motivo real é outro — `isr_2`
nunca *desmascara* irq 1, e `isr_1` (prioridade 1) não pode preemptar `isr_2` (prioridade 2). O
descarte estava certo; a justificativa, não. Corrigida para "nenhum deles deixa irq 1 desmascarada
ao retornar, e `isr_1` não pode rodar aninhada em nenhum deles". Uma prova é texto que alguém vai
ler na monografia, e um texto errado sobre um veredito certo ensina a coisa errada.

### (f) 12% contra 54,2%: não é comparável, e a diferença era esperada

O IntRace reporta 54,2% (33–63% por projeto) para o seu stage 2, sobre **pares de *data race*
em programas reais**. Aqui:

- **19 dos 31 casos não chamam nenhuma primitiva de máscara**, então seus pares só poderiam cair
  por prioridade — e um par entre a tarefa e uma ISR nunca cai por prioridade, porque a ISR
  sempre pode preemptar a tarefa. Por isso só 6,4% dos pares saem.
- A maior parte dos descartes por concorrência é de **trincas** com B em `main` entre dois
  acessos de uma ISR (`priority`, 45).

A comparação que significaria alguma coisa é a da [[Real-World Program Benchmark]] (W9).

## 11. Decisões tomadas

| Decisão | Por quê |
| --- | --- |
| Estado por acesso no C2 = visão **com interferência**, não a local | é a única que um consumidor pode ler como "mascarada" sem ser enganado; a local continua no `stage2/masking.json` e serve só para explicar (`reenabled_within_interval_by`) |
| Persistência da máscara depois do retorno: **união** (F7) | depende do hardware; a união cobre os dois casos na direção segura |
| Externa não modelada **pode habilitar qualquer interrupção** (F6) | a leitura segura de [[Soundness Assumptions]] F3 e D1 |
| Menor ponto fixo, **nunca uma iteração parcial** | §8; reverte a direção registrada na semana 1, com a razão no próprio documento |
| `no-path` como motivo de descarte no stage 2 | é o estágio que tem o supergrafo; reportado separado da attrition de concorrência |
| `critical_sections` (campo opcional do C2) **não é preenchido** | as *fixtures* tinham versões escritas à mão; calcular `begin`/`end` exige heurística sobre o fim da seção, e preferi fatos exatos (as origens, na proveniência) a intervalos aproximados |
| E3 (ISR não preempta a si mesma) — **evidência nova, decisão pendente** | o README diz que uma interrupção preempta "o programa principal ou interrupções de nível mais baixo"; isso exclui o mesmo nível, então o padrão lê a suíte. Falta Pedro confirmar |

## 12. O que mudou nos contratos — item para a reunião de segunda

O [[Roadmap]] diz que mudança de contrato depois da semana 2 é o principal risco de cronograma.
Nada foi renegociado, mas três coisas mudaram e a Trilha B precisa saber:

- **O significado de `accesses[].masking` e `masking.per_access`**: agora é o estado *com*
  interferência. As 20 *fixtures* da Trilha B seguem a convenção das duas *fixtures* da semana 1
  — conferido no branch `track-b/llm-integration` (commit `8b67d60`): `svp_simple_001-bug_point-1`
  diz `disabled: [2]` em A₁ e A₂, e `svp_simple_001-trap-1` diz `disabled_throughout: [2]`, um
  valor que o stage 2 não produz para essa armadilha (§10a). Elas devem ser revistas antes da
  integração da semana 8 — em especial qualquer uma que diga `disabled` para uma interrupção que
  outra ISR desmascara, ou que dê a armadilha do 001 como inviável. O branch da Trilha B não foi
  alterado.
- **`stage2/dropped.jsonl`**, com schema próprio (`contracts/c3-drop-record.schema.json`). A
  regra 6 do C3 já exigia essa linha; agora ela tem arquivo e formato. A descrição de
  `dropped_with_proof` no schema do manifesto dizia que só o solver podia descartar e foi
  corrigida.
- **Uma *fixture* nova** (`c2-trap-array-index.json`) e uma *run fixture* em que o solver
  devolve `sat` para a armadilha do 001 e `unsat` para a de índice.

## 13. Como reproduzir

```bash
cd project-src && ./scripts/build-analysis.sh && source scripts/env.sh
```

```bash
irqrace stage2-all
```

```bash
irqrace stage2 bench/configs/svp_simple_001_001.yaml -v
```

```bash
/usr/bin/python3 -m pytest tests -q
```

`-v` imprime cada descarte com a sua prova. O `python3` do `PATH` nesta máquina é o virtualenv
do PlatformIO, que não tem `jsonschema`; por isso o `/usr/bin/python3` explícito.

## 14. Estado ao fim da semana

275 testes: 203 que já existiam e 72 novos — 26 em `tests/test_masking.py`, uma regra de corretude
por teste sobre programas montados à mão; 42 em `tests/test_stage2.py`, sobre os casos reais; e 4
em `tests/test_contracts.py`, para os dois exemplos de contrato novos.
[[Soundness Assumptions]] ganhou seis entradas — **F6**, **F7**, **F8**, **F9**, **H1d**, **I4** —
e teve **E3**, **G2b** e **H1** atualizadas.

Ainda não existem: o estágio Z3, a etapa de LLM, o dashboard, e o campo `critical_sections`.

**Decisões pendentes, todas do Pedro:**

- **E3** — confirmar o padrão (ISR não preempta a si mesma) agora que o README o sustenta para o
  Racebench.
- **G2c** — um intervalo `[A₁, A₂]` pode atravessar duas ativações do mesmo fluxo? Continua aberta;
  é mais uma pergunta de definição de violação de atomicidade do que de modelo de chegada.
- **O cronograma.** Pelo calendário do [[Roadmap]] esta é a semana 8, e o gatilho do degrau 3 da
  escada de corte (*nada resolvendo até 16 out*) já passou.

> [!note] Revisado em 22 out 2026, nas semanas 6–7
> O código desta semana mudou em dois pontos, nenhum deles nos trechos citados acima: o
> `irqrace-stage1` passou a emitir, em cada evento do CFG, o índice da instrução (`"i"`) e, em cada
> bloco, o número de instruções (`"n"`), que o stage 3 usa para traduzir os conjuntos de execução
> do stage 2 em fronteiras entre instruções; e `irqrace stage2-all` passou a compartilhar o laço de
> avaliação com o novo `stage3-all`, com a saída mostrada na seção 2 inalterada. O estágio Z3 que
> esta página dava como inexistente está em [[Semana 6 — O Stage 3, a Codificação]] e
> [[Semana 7 — O Stage 3, Busca e Verificação]].

Página anterior: [[Semana 4 — Derivação de Candidatos e o Recall Gate]]. Próxima:
[[Semana 6 — O Stage 3, a Codificação]].
