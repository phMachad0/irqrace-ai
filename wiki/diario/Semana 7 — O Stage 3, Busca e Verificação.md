---
type: project
tags: [wiki, project, diario, pt-br]
sources: ["[[Roadmap]]", "[[Pipeline Design]]", "[[Path Feasibility Analysis]]", "[[Soundness Assumptions]]", "[[IntRace (paper)]]", "[[Racebench]]"]
updated: 2026-10-25
status: draft
---

# Semana 7 — O Stage 3, Busca e Verificação

**Período planejado:** 12–16 out 2026 (segunda metade do bloco W6–W7) · **implementado em:**
22 out 2026 · **Trilha A** · [[Roadmap]] W6–W7. Página anterior:
[[Semana 6 — O Stage 3, a Codificação]].

> [!note] Revisado em 24 out 2026
> Desde esta data o projeto trabalha com uma única classe de candidato, a trinca de violação de
> atomicidade ([[Triples Only]]). Esta página descreve o código como ele é hoje; a saída da seção 1,
> as contagens e os tempos foram refeitos com ele.

> [!note] Revisado em 25 out 2026
> Uma revisão da branch achou dois pontos em que o stage 3 podia dar `unsat` sem prova. Os dois
> estão corrigidos e descritos no fim da §5, em (d) e (e). Nenhum veredito do Racebench mudou.

> [!note] Sobre a divisão
> W6–W7 é um bloco único no [[Roadmap]], implementado de uma vez. A
> [[Semana 6 — O Stage 3, a Codificação|página anterior]] descreve a codificação; esta descreve a
> busca, o desempenho, os três bugs que a verificação pegou e os números. A divisão é temática, não
> duas fases.

## 1. Resultado

```
31/31 subjects analysed
stage 1: 316 candidates, 10.2 per subject  [1727 ms total]
stage 2: 202 kept, 114 dropped with proof (masking 7, no-path 62, priority 45)  [1325 ms total]
attrition: 36.1% overall; 0-62% per subject
  of which concurrency (priority + masking): 16.5%; no-path is stage 1's cross-function may-precede refined, not a concurrency result
  for scale: IntRace reports 54.2% (33-63% per project) for its stage 2, on another candidate class, in real-world subjects
solver: 202 in -> 166 sat, 0 inconclusive, 36 unsat (dropped with proof)  [17636 ms total]
reaching the LLM: 166, 5.4 per subject; solver attrition 17.8%
  for scale: IntRace reports 86.2% (41-93%) for its feasibility stage, on another candidate class, in real-world subjects
funnel: 316 -> 202 -> 166  [stage 1 1727 ms, stage 2 1325 ms, solver 17636 ms]
slowest subjects in the solver: svp_simple_019_001 7582 ms, svp_simple_024_001 2358 ms, svp_simple_003_001 1127 ms
RECALL GATE (stage3): 48/48 annotated bug points present -- PASS
traps reported: 35/38 after stage 1, 30/38 after stage 2, 16/38 reaching the LLM (14 refuted by the solver)
inspection ratio: 0.84 mean over 31 subject(s) whose bug points were all found
runstore check: 31/31 runs conform to C3 (rule 6: nothing vanished without a proof)
```

**O funil inteiro está medido** — 316 → 202 → 166 candidatos chegando ao LLM, com tempo por estágio
—, e **o portão de recall continua em 48/48**, agora tomado sobre os registros de contexto, isto é,
sobre o que a Trilha B de fato recebe. É o critério de pronto do bloco.

Dos 36 `unsat`, 27 saíram da projeção de endereços (§4) e 9 da busca completa. Nenhum candidato
ficou `inconclusive`.

## 2. Conceitos desta semana

**Busca em profundidade com estados.** O executor mantém uma pilha de *estados simbólicos* — cada um
com a sua pilha de chamadas, memória, condição de caminho e fase. Executa um estado até ele
*bifurcar* (um desvio com os dois lados possíveis, uma escolha de A₁, uma preempção), empilha as
alternativas e continua. Um estado morre quando o caminho fica impossível ou termina sem achar o
alvo.

**Poda.** Perguntar ao solver, num desvio, se o lado é possível; se não for, não segui-lo. Cada
pergunta custa; não perguntar custa caminhos inúteis.

**Solver incremental, literais indicadores, *assumptions*.** Em vez de recriar o solver a cada
pergunta, cada termo é afirmado uma só vez na forma `p → termo`, com `p` um booleano novo, e cada
pergunta passa como *hipóteses* os `p` do caminho atual. O Z3 reaproveita o trabalho entre
perguntas.

**Relaxação.** Uma versão mais fraca de uma pergunta, que tem solução sempre que a original tem.
Se a relaxação não tem solução, a original também não. É o princípio da projeção de endereços.

**Teste de mutação.** Reintroduzir de propósito o bug que um teste deveria pegar e verificar que
ele falha. Um teste de regressão que passa com o bug de volta não protege nada.

## 3. A busca

As fases de um estado, em `analysis/src/irqrace-stage3.cpp`:

```cpp
enum class Phase {
  SeekA1,     // the preempted flow, before A1
  SeekSplice, // the preempted flow, after A1, before the preemption
  SeekB,      // the preempting flow, from its entry, looking for B
  SeekA2,     // the preempted flow resumed, looking for A2
  Collect,    // projection: every path from a flow's entry to one access
};
```

Em cada fronteira entre instruções, o laço principal aplica a interferência daquela fronteira e,
na fase `SeekSplice`, bifurca: um estado preempta ali, outro segue procurando um ponto mais adiante.

```cpp
      int rid = runSetAt(act.flow, fr);
      if (!fr.boundaryDone) {
        interfere(st, act.flow, rid);
        if (rid != st.segmentRun) { st.segmentRun = rid; st.segmentSpliced = false; }
        if (st.phase == Phase::SeekSplice && act.flow == baseFlow && !st.segmentSpliced &&
            runs(baseFlow, rid, remoteFlow)) {
          st.segmentSpliced = true;
          State alt = st;
          alt.acts.back().frames.back().boundaryDone = true;
          work.push_back(std::move(alt)); // keep looking further on
          splice(st, rid, fr);
          continue;
        }
```

Ao achar B, antes de devolver o controle ao fluxo preemptado, a busca já exige que A₁ e B se
sobreponham, e esquece o que pode ter mudado:

```cpp
      // A1 and B must touch the same memory; refute early when they cannot.
      {
        z3::expr ab = overlap(*st.first, *st.remote);
        if (solve(st.pc, &ab) == z3::unsat) { handled = true; st.acts.clear(); return false; }
        st.pc.push_back(ab);
      }
      // Back to the preempted flow. Everything that may have run at the
      // preemption point -- B's flow included, which goes on after B -- may
      // have changed what it writes.
      st.acts.pop_back();
      havoc(st, flowWritesOf(st.spliceRun), "interference");
      st.phase = Phase::SeekA2;
      // One crossing per back edge per phase: the preemption and A2 may each
      // lie in a later iteration than the one before them.
      st.crossed.clear();
```

O veredito é `unsat` só se a busca terminou **sem** estourar tempo nem orçamento, sem construção
não suportada e sem nenhuma resposta `unknown` do Z3.

## 4. Desempenho

A primeira versão correta estourava o timeout de 10 s em candidatos simples. Quatro mudanças,
todas sem custo de corretude:

**Um desvio, uma pergunta.** A condição de caminho já é satisfazível quando se chega ao desvio; se
um lado é impossível, o outro é possível sem perguntar. Quando os dois podem ser, o lado falso segue
sem pergunta, e um caminho impossível morre na próxima pergunta, que sempre inclui a condição
inteira:

```cpp
    // The path condition is satisfiable (or unknown) on entry, so if one side
    // is refuted the other is feasible without asking. If both may be, the
    // false side is taken without a check: an infeasible path dies at its next
    // check, which always includes the whole path condition.
    canT = solve(st.pc, &c) != z3::unsat;
    canF = true;
```

**Uma preempção por segmento.** Entre duas fronteiras no mesmo bloco, sem escrita nem chamada do
fluxo preemptado e com o mesmo conjunto de execução, preemptar numa ou noutra dá no mesmo: tudo o
que aqueles fluxos escrevem já está sujo nas duas (o campo `segmentSpliced` do trecho da §3).

**Solver incremental.** Recriar o solver a cada pergunta fazia o Z3 refazer o *bit-blasting* de
`rand() % 10` (resto com sinal de 32 bits) centenas de vezes no `svp_simple_019_001`:

```cpp
  z3::expr lit(const z3::expr &e) {
    unsigned id = Z3_get_ast_id(C, e);
    if (auto it = lits.find(id); it != lits.end()) return it->second;
    z3::expr b = C.bool_const(("p" + std::to_string(id)).c_str());
    inc->add(z3::implies(b, e));
    return lits.emplace(id, b).first->second;
  }
```

**A projeção de endereços.** Antes da busca completa, cada acesso é explorado sozinho, a partir da
entrada do seu fluxo, sem preempção, juntando todos os caminhos com o endereço que tocam. Depois,
uma única pergunta: os três endereços podem coincidir?

```cpp
  bool projectionRefutes(const Candidate &c, unsigned &states) {
    Target a1 = c.a1, b = c.b, a2 = c.a2;
    if (!resolve(a1) || !resolve(b) || (c.triple && !resolve(a2))) return false;
    z3::expr e1 = C.bool_val(true), eb = C.bool_val(true), e2 = C.bool_val(true);
    unsigned s1 = 0, sb = 0, s2 = 0;
    if (!project(a1, e1, s1, states)) return false;
    Addr p1{*projVar, s1};
    if (!project(b, eb, sb, states)) return false;
    Addr pb{*projVar, sb};
    z3::expr goal = e1 && eb && overlap(p1, pb);
    if (c.triple) {
      if (!project(a2, e2, s2, states)) return false;
      Addr p2{*projVar, s2};
      goal = goal && e2 && overlap(pb, p2) && overlap(p1, p2);
    }
    std::vector<z3::expr> none;
    return solve(none, &goal) == z3::unsat;
  }
```

É uma **relaxação**: larga a ordem entre os acessos e o fato de os fluxos compartilharem valores.
Tudo o que a pergunta completa permite, a projeção também permite, então o `unsat` dela é prova
(**J9**). Ela refuta de cara as armadilhas de índice e de guarda impossível — exatamente as que a
busca completa levava mais tempo para esgotar.

Durante o desenvolvimento as versões foram comparadas caso a caso, e nenhuma era a melhor em
tudo. O solver incremental acumula termos de array que pesam em cada pergunta do `001`: com ele, e
sem a projeção, um candidato do `001` estourava o timeout. A projeção não ajuda no `019`, cujas
armadilhas dependem de valores que `main` e a ISR compartilham, e o custo dela se soma ao da busca.
A combinação final é a única em que nenhum candidato fica `inconclusive`. Com ela, hoje, o `001`
leva 0,4 s, o `019` — o mais lento — 7,6 s, e o solver soma 17,6 s nos 31 casos.

## 5. Os três bugs que a verificação pegou

Nenhum número desta página foi reportado antes de os três estarem corrigidos e fixados por um
teste. Os três testes foram **testados por mutação**: com o bug reintroduzido, cada um falha.

```
mutation 1 (volatile):
1 failed, 52 deselected in 0.49s
mutation 2 (one flag):
1 failed, 52 deselected in 0.36s
mutation 3 (one crossing):
1 failed, 52 deselected in 0.48s
mutation 4 (no interference):
2 failed, 51 deselected in 0.52s
```

A quarta mutação não corresponde a um bug encontrado: desligar a interferência inteira faz falhar
os dois testes em que um fluxo concorrente muda o valor de uma guarda.

### (a) Uma decisão escondia a outra — um `unsat` errado

Na primeira execução, a primeira armadilha do `svp_simple_001_001` — `isr_1` escreve `v` duas vezes
seguidas e `isr_2` lê no meio — deu **`unsat`**. Mas a semana 5 tinha mostrado que ela é alcançável.
Entre as duas escritas só há uma fronteira, a imediatamente antes de A₂. A preempção decidida ali
marcava a instrução como "já decidida", e a seleção de A₂ — que é decidida *na mesma instrução* —
era pulada. Um único flag para duas decisões diferentes:

```cpp
  // Two different decisions live at one position, and they must not mask each
  // other: the boundary BEFORE the instruction (interference, the preemption)
  // and the instruction ITSELF (choosing it as A1, B or A2). A preemption just
  // before A2 is exactly the case where both happen at once.
  bool boundaryDone = false;
  bool targetDone = false;
```

Esse é o tipo de bug que o projeto inteiro existe para não deixar passar: um `unsat` falso é uma
prova falsa, e um descarte com prova falsa é uma perda de recall que ninguém vê. Foi pego porque o
stage 2 já tinha explicado por que aquela armadilha é alcançável. Teste:
`test_a_preemption_just_before_a2_does_not_hide_a2`.

### (b) Uma leitura volátil contava como escrita — e apagava todas as provas

Corrigido o (a), quase tudo deu `sat`, inclusive a armadilha de índice (`a[1000]` contra `a[9999]`),
que deveria ser `unsat`. O modelo do Z3 mostrou o porquê: o `i` do laço de `main` lia uma versão nova
da memória a cada comparação, como se outro fluxo pudesse escrevê-lo. O conjunto de escrita de
`isr_2` era "tudo". O `isr_2` só *lê* — mas os globais do Racebench são todos `volatile`, e para o
LLVM uma leitura volátil "pode escrever na memória" (`mayWriteToMemory()`), porque o hardware pode
reagir a ela:

```cpp
    WriteSet ws;
    // A load writes no program object -- not even a volatile one, which LLVM's
    // mayWriteToMemory() counts as a write because the hardware may react to
    // it. Racebench declares every shared global volatile, so missing this
    // makes every ISR "write everything" and havocs every proof away.
    if (llvm::isa<llvm::LoadInst>(I)) return ws;
```

Esse bug estava no lado seguro — esquecer demais não perde recall —, mas zerava a precisão. Teste:
`test_a_volatile_read_is_not_a_write` (**J3**).

### (c) A aresta de volta cruzada uma vez no total, e não por fase

Revendo a codificação, o conjunto de arestas de volta já cruzadas era compartilhado entre "procurar
a preempção" e "procurar A₂". Se A₁ está no fim de uma iteração, a única janela desmascarada no meio
da seguinte e A₂ no começo da outra depois, são **duas** travessias — e uma só no total refuta uma
violação real. Nenhum caso do Racebench tinha essa forma, e por isso o portão não pegaria. O teste
foi escrito para exigi-la:

```c
  disable_isr(1);
  for (int k = 0; k < 3; k++) {
    r2 = x;                          /* A2 */
    enable_isr(1);
    disable_isr(1);
    r1 = x;                          /* A1 */
  }
```

A correção é o `st.crossed.clear()` do trecho da §3. Teste:
`test_the_back_edge_is_crossed_once_per_phase` (**J2**).

### Depois: dois furos que a revisão da branch achou (25 out 2026)

Os três bugs acima foram pegos durante a implementação. Os dois abaixo foram achados depois, por uma
revisão da branch inteira contra a regra do projeto — *o solver só descarta com prova*. Nenhum dos
dois aparece no Racebench, e por isso o portão não os pegaria: nenhum dos 202 vereditos mudou com a
correção.

### (d) Uma chamada indireta sem alvo conhecido era lida como "não chama ninguém"

Uma **chamada indireta** é uma chamada através de um ponteiro de função (`fp()`), em vez de pelo
nome. Para saber quem ela pode chamar, a análise consulta o **conjunto points-to** do ponteiro — os
objetos para os quais o SVF calculou que ele pode apontar. Quando o ponteiro passa por um inteiro
(`slot = (unsigned long)&g; fp = (void (*)(void))slot;`), o SVF perde o rastro e o conjunto fica
vazio.

O stage 1 nunca lê um conjunto vazio como "não chama ninguém": nesse caso a chamada pode ir para
**qualquer função cujo endereço é tomado** no programa (`&g` em algum lugar) e cuja assinatura é
compatível — a premissa **B2** de [[Soundness Assumptions]]. O stage 3 não fazia o mesmo: sem alvo,
pulava a chamada. Um acesso que só existe dentro de `g` nunca era alcançado, a projeção não juntava
nenhum caminho, e a trinca — gerada pelo stage 1 e mantida pelo stage 2 — saía **`unsat`**, sem
registro de contexto. Agora o stage 3 usa o mesmo grafo de chamadas:

`project-src/analysis/src/irqrace-stage3.cpp`
```cpp
    if (out.empty() || unknown) {
      if (over) *over = true;
      for (const llvm::Function *f : addressTaken)
        if (signatureMatches(f, ci) && seen.insert(f).second) out.push_back(f);
    }
```

`unknown` cobre também o conjunto que tem funções *e* algo que o SVF não nomeia: aí a lista de alvos
conhecidos não é completa, e a busca segue os dois. O conjunto de escrita de uma chamada assim
continua "tudo", como antes — ele nunca encolhe. Teste:
`test_an_unresolved_indirect_call_reaches_every_compatible_target`; com o *fallback* desligado
(mutação), ele falha.

### (e) Um timeout podia virar `unknown` sem registro

Cada candidato tem um prazo (`timeout_ms`). Passado o prazo, `solve()` devolvia `unknown` sem marcar
que tinha havido um `unknown` — e a checagem de A₂ em `decide()` lê qualquer coisa diferente de
`sat` como ramo refutado. Se a busca terminasse aí, o veredito seria `unsat` por falta de tempo, e
não por prova.

Ao investigar, vi que **hoje isso não chega a acontecer**: antes da checagem de A₂, `decide()` sempre
põe um estado na fila (o que segue sem escolher aquela instrução), e o laço da busca olha o relógio
antes de tirar o próximo estado — a busca para como `inconclusive`, motivo `timeout`. Uma mutação que
desfaz a correção não faz nenhum teste falhar, e é por isso. O furo era latente, e a correção torna a
regra local, em vez de depender de onde o laço olha o relógio:

`project-src/analysis/src/irqrace-stage3.cpp`
```cpp
    // Past the deadline the answer is unknown, and it must be recorded as such.
    // decide()'s A2 check reads anything but SAT as a refuted branch; today
    // the search loop's own deadline check stops the search before that can
    // end in UNSAT, but a timeout must not become a proof because of where
    // the loop happens to look at the clock.
    if (left <= 0) { sawUnknown = true; return z3::unknown; }
```

O teste antigo usava `timeout_ms=0`, que para a busca antes do primeiro passo. O novo,
`test_a_deadline_passing_inside_the_search_is_never_unsat`, usa uma variável de ambiente só de teste,
`IRQRACE_STAGE3_EXPIRE_AFTER_CALLS=n`, que faz o prazo vencer na *n*-ésima chamada ao solver — a
única forma determinística de pôr o prazo no meio de um passo. O caso é uma trinca que só a busca
refuta (`a[k]` contra `a[1 - k]`, que nunca coincidem num mesmo caminho); para cada *n* entre 1 e o
número de chamadas, o veredito tem de ser `inconclusive`.

## 6. A auditoria de cada `unsat`

O portão só cobre os 48 *bug points*. Um `unsat` errado num candidato não anotado é uma perda de
recall que o portão não vê. Por isso auditei contra o fonte todos os vereditos `unsat` — os 36 de
hoje estão entre eles. Todos têm um motivo verificável no código:

| Motivo | Exemplos |
| --- | --- |
| elementos diferentes do mesmo array | `001` (1000 contra 9999), `002` (9999 contra 0), `008` (3 contra 4), `029` (36 contra 37), `024` (as duas chamadas de `RTData`) |
| guarda impossível | `002` (`i == N + 1` dentro de `i < N`), `007` (`i ≠ 2` contra o índice 2) |
| global que ninguém escreve | `003` (`global_flag1 = 0`), `004` (`condition3 = 1`), `005` (`global_condition = 0`) |
| campos diferentes de uma `struct` | `010` (`header` no deslocamento 0, `data` no 4) |
| ponteiro reapontado | `011` (`*u` passa de `var2` para `var3`), `009` (`m` reapontado pela própria ISR antes de ler) |
| relação que só `main` pode mudar | `019`, a armadilha 1 (os `para` só são escritos por `main`, antes das duas guardas) |

Um deles era o *bug point* do `svp_simple_006_001`, que no fonte publicado está em código morto por
causa de um erro de digitação na condição de um laço; o caso é analisado com o fonte corrigido, como
registra a nota em `project-src/bench/racebench-errata.yaml`.

## 7. Um achado: mais uma armadilha alcançável

A armadilha `global_var <R#37><W#44><R#40>` do `svp_simple_020_001` é dada como falso positivo porque
as guardas das linhas 36 e 39 — `sum > para` e `sum < para` — parecem exclusivas. Mas `para` pode
mudar entre elas:

```c
void svp_simple_020_001_isr_1() {
  svp_simple_020_001_global_var = 0x01;
  svp_simple_020_001_global_flag = 1;
  enable_isr(2);
}
void svp_simple_020_001_isr_2() {
  if (svp_simple_020_001_global_flag == 1) {
    svp_simple_020_001_global_para = 11;
    svp_simple_020_001_global_var = 0x05;
  }
}
```

Com `para = 0` e `sum = 2`: `main` lê na linha 37; `isr_1` preempta e escreve na 44 (o B), liga o
flag e desmascara a irq 2; `isr_2` faz `para = 11`; `main` testa `2 < 11` e lê na 40. A
testemunha do solver preempta exatamente na linha 37. **Conferi à mão** com essa interleaving
concreta — um `sat` sozinho não seria evidência (§8). É a segunda armadilha nessa situação, depois
da do `001` ([[Contradictions]] #7).

## 8. 12% contra 86%, e o que a codificação não vê

O [[IntRace (paper)]] reporta 86,2% de remoção no seu estágio de viabilidade; aqui são 17,8%. Três
razões, só a última sobre o método:

- sujeitos diferentes (programas reais contra casos de 37 a 97 linhas) e classes de candidato
  diferentes;
- o IntRace não diz que a sua codificação sobre-aproxima — e a daqui precisa, porque descarta;
- **a codificação é thread-modular.** Cada fluxo vê os outros só pelo que eles podem escrever. Uma
  armadilha que é inviável por causa da *ordem* em que as ISRs rodam parece viável. O exemplo é o
  `svp_simple_028_001`: `isr_2` só escreve se `isr_1_flag` for diferente de zero, e quem habilita
  `isr_2` é `isr_1`, que zera o flag logo antes. Mas o flag é escrito por `isr_1`, que pode rodar ali,
  então ele é esquecido, e a guarda fica satisfazível.

Essas chegam ao LLM marcadas `sat`, com a lista `unconstrained` dizendo o que foi esquecido. Recuperá-
las exigiria modelar no solver a máscara e a ordem de ativação — em suma, um BMC dos fluxos que podem
rodar — e ficou como pergunta em [[Open Questions]]: quantas das 16 armadilhas que chegam ao LLM são
desse tipo, e a etapa de LLM já as separa?

## 9. O que mudou nos contratos — item para a reunião de segunda

- **`solver_result: sat` quer dizer "não refutado"**, e agora a descrição do `SolverResult` diz isso.
  A Trilha B não deve tratar `sat` como defeito confirmado; o campo `unconstrained` diz o que a
  testemunha pode ter inventado, e `assignment.preempted_at` diz onde a preempção foi colocada.
- **Os registros em `context/` agora são emitidos pelo stage 3** (`emitted_by.stage = "stage3"`) e só
  existem para os candidatos `sat` ou `inconclusive`. A entrada de proveniência `solver_result`
  explica o veredito.
- **Dois arquivos novos no *run store***: `solver/query.txt` (a consulta) e `solver/stats.json`
  (estados, perguntas ao solver, tempo e método de cada `unsat`).

## 10. Como reproduzir

```bash
cd project-src && ./scripts/build-analysis.sh && source scripts/env.sh
```

```bash
irqrace stage3-all
```

```bash
/usr/bin/python3 -m pytest tests -q
```

## 11. Estado ao fim do bloco

329 testes hoje. Os 55 deste bloco estão em `tests/test_stage3.py`: 14 sobre programas C
compilados com o mesmo clang, uma regra de corretude por teste; 31 com o portão em cada caso do
Racebench; e 10 com vereditos específicos que esta página argumenta. A suíte inteira leva cerca de 80
s.

[[Soundness Assumptions]] tem hoje 56 entradas: o grupo **J** (J1–J9) e a **A4** deste bloco, e a **H1e**, que declara a classe de defeito coberta. A
**J6** — o programa não tem comportamento indefinido que a análise precise seguir — é a única que
não é sobre-aproximação, e as duas provas do Racebench que dependem dela estão nomeadas lá.

Ainda faltam: a integração com a Trilha B (W8), a suíte de programas reais e a revalidação com CBMC
(W9), e a lacuna **A4** do stage 1.

**Decisões pendentes, todas do Pedro:** **E3** e **G2c** (da semana 5, sem mudança), e o cronograma
— pelo calendário do [[Roadmap]] esta é a semana 8, e o M4 é amanhã.

Página anterior: [[Semana 6 — O Stage 3, a Codificação]].
