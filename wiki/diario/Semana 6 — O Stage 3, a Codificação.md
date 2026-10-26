---
type: project
tags: [wiki, project, diario, pt-br]
sources: ["[[Roadmap]]", "[[Pipeline Design]]", "[[Path Feasibility Analysis]]", "[[Soundness Assumptions]]", "[[IntRace (paper)]]"]
updated: 2026-10-24
status: draft
---

# Semana 6 — O Stage 3, a Codificação

**Período planejado:** 5–9 out 2026 (primeira metade do bloco W6–W7) · **implementado em:**
22 out 2026 · **Trilha A** · [[Roadmap]] W6–W7. Página anterior:
[[Semana 5 — O Stage 2, Prioridade e Máscara]]. Próxima: [[Semana 7 — O Stage 3, Busca e Verificação]].

> [!note] Revisado em 24 out 2026
> Desde esta data o projeto trabalha com uma única classe de candidato, a trinca de violação de
> atomicidade ([[Triples Only]]). Esta página descreve o código como ele é hoje.

> [!note] Sobre a divisão entre esta página e a próxima
> W6–W7 é um bloco único no [[Roadmap]] e foi implementado de uma vez, no mesmo dia que a semana
> 5. A separação é **temática**: esta página descreve *o que* o solver codifica e por que essa
> codificação é segura para descartar; a [[Semana 7 — O Stage 3, Busca e Verificação|próxima]]
> descreve como a busca é feita, o que ela custa, os bugs que o recall gate pegou e os números.

## 1. O que o bloco devia entregar

| Item do Roadmap (W6–W7) | Estado |
| --- | --- |
| Resumos simbólicos das ISRs; *splice* no ponto de preempção; descarregar as restrições de caminho | feito — `analysis/src/irqrace-stage3.cpp`, execução simbólica sobre o IR LLVM com Z3 |
| **Só alcançabilidade**, nunca "não serializável"; o solver só serve para provar impossível | feito — a pergunta é a da §3 |
| Timeout e construção não suportada → **`inconclusive`**, mantido e repassado, nunca `SAT`, nunca descartado | feito — §7, com testes |
| **Pronto quando:** o funil inteiro medido — stage 1 → stage 2 → Z3 → LLM — com tempos por estágio | feito — 316 → 202 → **166** ([[Semana 7 — O Stage 3, Busca e Verificação|semana 7]], §1) |
| **Pronto quando:** recall gate continua 100% | **48/48**, medido sobre os registros que chegam ao LLM |

## 2. Conceitos desta semana

**Execução simbólica.** Executar o programa com *símbolos* no lugar de valores: em vez de `x = 3`,
`x = x₀`; em vez de seguir um `if`, seguir os dois lados, cada um com a condição anotada. Cada
caminho acumula uma **condição de caminho** (*path condition*), a conjunção das condições dos
desvios tomados. Ver [[Symbolic Execution]].

**SMT e Z3.** Um *solver* SMT (*satisfiability modulo theories*) responde se uma fórmula tem
solução. O Z3 é o usado aqui, com duas teorias: **bit-vectors** (inteiros de largura fixa, que
transbordam como os do C) e **arrays** (funções de índice para valor, com `select` para ler e
`store` para escrever). `sat` = existe solução; `unsat` = não existe; `unknown` = não decidiu (por
exemplo, timeout).

**Sobre-aproximação.** Uma codificação **sobre-aproxima** o programa quando toda execução real
também é execução da codificação, mas não necessariamente o contrário. Daí a assimetria que
organiza tudo nesta semana: se a codificação não tem nenhuma execução que faça X (`unsat`), o
programa também não tem — é uma **prova**. Se a codificação tem (`sat`), isso **não** prova que o
programa tem.

**Havoc.** "Esquecer" um valor: trocá-lo por um símbolo novo, sem restrição nenhuma. É a forma
mais simples de sobre-aproximar o que não se sabe calcular — o valor depois de muitas iterações de
um laço, o que outra ISR pode ter escrito.

**IR LLVM, SSA, bloco básico.** O código intermediário do compilador (ver
[[Semana 1 — Contratos e Toolchain]]). Em SSA (*static single assignment*) cada valor é definido
uma vez; uma instrução `phi` escolhe entre valores conforme o bloco de onde se veio.

**Aresta de volta (*back edge*) e cabeça de laço.** Num CFG, o laço natural tem uma *cabeça*
(*header*) que domina o corpo, e a aresta de volta é a que retorna do corpo à cabeça (ver
[[Semana 3 — O Front End do Stage 1]]).

**Splice (emenda).** A técnica do [[IntRace (paper)]]: transformar a pergunta concorrente numa
pergunta sequencial, "colando" a execução da ISR que preempta no meio da execução do fluxo
preemptado, no ponto de preempção.

## 3. A pergunta, exatamente

Para uma trinca `(A₁, B, A₂)`, com A₁ e A₂ no fluxo F e B no fluxo H:

> Existe uma execução em que F chega a A₁, depois H roda desde a sua entrada até B enquanto F está
> em algum ponto entre A₁ e A₂, e depois F chega a A₂ — com os três acessos tocando a mesma
> célula de memória?

É **só alcançabilidade**. Se a interleaving é danosa, ou mesmo não serializável, não é pergunta do
solver: isso já foi filtrado estruturalmente no stage 1 (as quatro formas não serializáveis,
**H1b**) e o resto é da etapa de LLM. Manter o solver na pergunta "é impossível?" é o que mantém o
seu `unsat` uma prova.

## 4. A arquitetura: Python monta a consulta, C++ resolve

O Z3 nesta máquina só existe como biblioteca C++ (`libz3-dev` 4.8.12; não há bindings Python), e
a decisão de stack da wiki já era "C++ para o que toca LLVM e SVF" ([[Reimplementation Assessment]]).
Então o stage 3 é um binário novo, `irqrace-stage3`, que carrega o mesmo `whole.bc` e roda o
mesmo SVF.

O que o Python sabe e o C++ não: **quem pode rodar em cada ponto**, que vem da análise de máscara do
stage 2 ([[Semana 5 — O Stage 2, Prioridade e Máscara]]). Para não recalcular nada, o Python
escreve uma consulta em texto, `solver/query.txt`, com o conjunto de fluxos que podem rodar em
cada fronteira entre instruções. O stage 2 calcula esses conjuntos por *ponto* (antes do evento
`k`); a tradução para fronteiras de instrução está em `src/irqrace/stage3.py`:

```python
    # Stage 2's run sets, moved from its points (before event k) onto the
    # instruction boundaries they cover: (event k-1, event k].
    for F in cfg.flows:
        for fn in m.reach[F.id]:
            for b, blk in enumerate(prog[fn]["blocks"]):
                evs, n = blk["events"], blk.get("n")
                if n is None:
                    raise Stage3Error("stage1/accesses.json has no instruction counts; "
                                      "re-run stage 1 with a W6+ irqrace-stage1")
                for k in range(len(evs) + 1):
                    lo = 0 if k == 0 else evs[k - 1]["i"] + 1
                    hi = evs[k]["i"] if k < len(evs) else n - 1
                    if lo > hi:
                        continue
                    run = c.run(F.id, m.state(F.id, (fn, b, k)))
                    out.append(f"run {F.id} {fn} {b} {lo} {hi} {','.join(sorted(run)) or '-'}")
```

Para isso o `irqrace-stage1` passou a emitir, em cada evento, o índice da instrução (`"i"`) e, em
cada bloco, o número de instruções (`"n"`). Os dois processos se falam por *(função, bloco, índice
de instrução)* — nada de ids do SVF atravessando a fronteira, porque nada garante que dois
processos numerem os nós do mesmo jeito.

## 5. A memória: um array de bytes por objeto

Cada objeto do SVF (global, `alloca`, função) é um array Z3 de 64 bits de índice para 8 bits de
valor. Um ponteiro é um bit-vector de 64 bits com o objeto nos bits altos e o deslocamento nos
baixos:

`analysis/src/irqrace-stage3.cpp`:

```cpp
  z3::expr ptrOf(NodeID obj, uint64_t off = 0) {
    return C.bv_val((static_cast<uint64_t>(obj) << 40) | off, 64);
  }
  z3::expr objField(const z3::expr &p) { return p.extract(63, 40); }
  z3::expr offField(const z3::expr &p) { return z3::zext(p.extract(39, 0), 24); }
```

Uma leitura por um ponteiro é uma escolha entre os objetos para os quais ele *pode* apontar,
segundo o SVF; o valor padrão, se não for nenhum deles, é **um símbolo novo**:

```cpp
  z3::expr load(State &st, const llvm::Value *ptrV, const z3::expr &ptr, unsigned n) {
    bool unknown = false;
    std::set<NodeID> objs = facts.pointsTo(ptrV, unknown);
    z3::expr off = offField(ptr);
    z3::expr obj = objField(ptr);
    // Default: a fresh value. Sound whatever the pointer turns out to be.
    z3::expr out = fresh(8 * n);
    if (unknown) notes.insert("unresolved-pointer");
    for (NodeID o : objs) {
      z3::expr v = readBytes(memOf(st, o), off, n);
      out = objs.size() == 1 && !unknown ? v : z3::ite(obj == C.bv_val(o, 24), v, out);
    }
    return out;
  }
```

Memória por **byte**, e não por elemento, porque o Racebench tem `union` (`svp_simple_010_001`) e
arrays de ponteiros lidos como `int` (`svp_simple_024_001`): o que importa é se as faixas de bytes
se cruzam. É exatamente o teste final de uma trinca:

```cpp
  z3::expr overlap(const Addr &a, const Addr &b) {
    z3::expr oa = offField(a.ptr), ob = offField(b.ptr);
    return objField(a.ptr) == objField(b.ptr) && z3::ult(oa, ob + C.bv_val(b.size, 64)) &&
           z3::ult(ob, oa + C.bv_val(a.size, 64));
  }
```

Essa exigência — os três acessos se sobrepõem dois a dois — é o que o stage 1 não podia fazer: ele
normaliza tudo para o objeto-base (**C1b**), então `a[1000]` e `a[9999]` são "o mesmo lugar" para
ele. O solver separa. Virou a suposição **J7**.

**Valores iniciais.** A tarefa principal começa dos inicializadores das globais (`int flag = 0;`).
Uma ISR começa com a memória **sem restrição**, porque pode disparar em qualquer ponto (**J5**, a
versão para valores da regra F8 da semana 5).

## 6. Laços: uma passada, com havoc na cabeça

Sem desenrolar (o laço de 10 000 iterações do `svp_simple_001_001` tornaria isso inviável), cada
laço é atravessado uma vez, com tudo que ele pode escrever — inclusive nas funções que chama —
esquecido na entrada da cabeça. Uma passada sobre esse estado cobre qualquer iteração.

```cpp
  bool go(State &st, Frame &fr, const llvm::BasicBlock *to) {
    const llvm::BasicBlock *from = fr.bb;
    FnInfo &fi = facts.info(fr.fn);
    bool back = facts.isBackEdge(from, to);
    if (back) {
      // Every later iteration is covered by the havoc at the header, so
      // looking for A1 or B a back edge adds nothing; between A1 and A2 one
      // crossing is what reaches a later iteration (Soundness Assumptions G2).
      if (!backEdgesAllowed(st.phase) || st.acts.size() > 1) return false;
      if (!st.crossed.insert({from, to}).second) return false;
    }
    const llvm::Loop *l = fi.li->getLoopFor(to);
    bool header = l && l->getHeader() == to;
    bool havocked = false;
    if (header && (back || !l->contains(from))) {
      havoc(st, facts.loopWrites(l), "loop");
      havocked = true;
    }
```

Duas regras moram aqui:

- **Procurando A₁ ou B, a aresta de volta é cortada.** O havoc da cabeça já representa o começo de
  qualquer iteração, então ir e voltar não acrescenta estado nenhum.
- **Entre A₁ e A₂, ela pode ser cruzada.** É assim que a mesma instrução serve de A₁ numa iteração e
  de A₂ numa posterior (**G2**) — cruzando a aresta, a cabeça é esquecida de novo e a instrução pode
  ser alcançada outra vez. Quantas vezes cruzar é uma das coisas que a semana 7 teve de corrigir.

O havoc não perde as guardas *dentro* do corpo. No segundo laço do `svp_simple_001_001`, `i` é
esquecido na cabeça, mas o `if (i == 9999)` vem depois e restringe `i` para a escrita que ele
guarda — por isso a leitura de `a[1000]` não pode ser o B daquela trinca (a segunda armadilha do
arquivo, refutada; ver [[Semana 7 — O Stage 3, Busca e Verificação|semana 7]], §6).

Laços irredutíveis (um ciclo que não tem cabeça natural) não são cobertos pela regra, e viram
`inconclusive` (**J2**).

## 7. Interferência: o que outro fluxo pode escrever é esquecido

Este é o elo com o stage 2. Em cada fronteira entre instruções em que algum fluxo Y pode rodar —
segundo o conjunto que o stage 2 calculou, já levando em conta máscara e prioridade —, tudo o que
Y pode escrever é marcado como sujo, e cada objeto sujo vira um array novo no próximo acesso
(havoc preguiçoso):

```cpp
  z3::expr &memOf(State &st, NodeID obj) {
    if (st.dirty.count(obj)) {
      st.dirty.erase(obj);
      st.mem.insert_or_assign(obj, freshMem());
      return st.mem.at(obj);
    }
    auto it = st.mem.find(obj);
    if (it == st.mem.end()) it = st.mem.emplace(obj, initial(obj, st.initMode)).first;
    return it->second;
  }
```

Por ser preguiçoso, uma escrita do próprio fluxo depois da marca vale: o objeto é renovado *antes*
da escrita, que então é aplicada. E porque a interferência vem dos conjuntos do stage 2, ela
**respeita a máscara**: dentro de uma seção crítica que ninguém reabre, o valor que a tarefa acabou
de escrever continua lá (`test_masking_shields_a_value_from_interference`).

Essa é uma abordagem **thread-modular**: cada fluxo vê os outros só pelo que eles podem escrever,
não pela ordem em que rodam. É sólida e barata, e é o que mais custa precisão (semana 7, §9).

## 8. O splice, e o que um veredito quer dizer

O fluxo H roda desde a sua entrada sobre a memória do ponto de preempção. Ao achar B, H é
interrompido ali — o que ele faria depois só tiraria restrições — e, quando F retoma, tudo o que o
conjunto daquele ponto pode escrever é esquecido de novo (**J4**).

Os três veredictos, em `src/irqrace/stage3.py`:

```python
* ``unsat`` -- no execution of the over-approximate encoding reaches A1, then B
  inside [A1, A2], then A2, touching one memory cell. Since every real execution
  is an execution of the encoding, none of those does either. A proof, and the
  only licence to drop.
* ``sat`` -- the encoding has such an execution. **Not** a confirmation: the
  encoding havocs everything a concurrently running flow may write, and
  everything a loop may write, so a SAT witness may be spurious. The record's
  ``unconstrained`` list says what was havocked.
* ``inconclusive`` -- timeout, exploration budget, or a construct the encoding
  cannot express soundly. Kept and passed on, with the reason (H2).
```

`sat` = **não refutado**. Essa frase foi para a descrição do `SolverResult` no contrato
(`contracts/common.defs.schema.json`), porque é a Trilha B que vai ler esses registros (**J8**).

O que não se consegue expressar com segurança vira `inconclusive`, nunca `sat` e nunca descarte:
recursão (`test_recursion_is_inconclusive_never_a_drop`), CFG irredutível, terminador desconhecido,
timeout (`test_a_timeout_is_inconclusive_and_the_candidate_reaches_the_llm` — com timeout zero, todos
os candidatos chegam ao LLM).

## 9. A única suposição que não é sobre-aproximação

Tudo acima esquece informação. Uma coisa a codificação **supõe**: que o programa não tem
comportamento indefinido que a análise precise seguir (**J6**). Desreferenciar um ponteiro que não
aponta para nenhum dos seus alvos possíveis — nulo inclusive — não toca objeto nenhum; chamar por
um ponteiro assim não acontece; acessos ficam dentro do seu objeto; aritmética inteira dá a volta.

Nenhum `unsat` do Racebench depende disso: todos foram auditados contra o fonte, e cada um tem
como motivo um índice, uma guarda, um inicializador ou um ponteiro reapontado (semana 7, §6). Um
programa com UB pode fazer qualquer coisa, e a codificação não faz.

## 10. Como reproduzir

```bash
cd project-src && ./scripts/build-analysis.sh && source scripts/env.sh
```

```bash
irqrace stage3 bench/configs/svp_simple_001_001.yaml -v
```

O `-v` imprime o veredito de cada candidato. A consulta que foi ao binário fica em
`solver/query.txt` dentro do diretório da execução.

## 11. Estado ao fim desta metade

A codificação existe e é sobre-aproximada em tudo, exceto em **J6**. [[Soundness Assumptions]]
ganhou o grupo **J** (J1–J9) e a entrada **A4**: o stage 1 enumera só `load` e `store`, então um
`memcpy` ou `memset` sobre um buffer compartilhado é um acesso que ele não vê — nenhum caso do
Racebench usa, firmware real usa, e precisa ser fechado antes da suíte de programas reais.

Página anterior: [[Semana 5 — O Stage 2, Prioridade e Máscara]]. Próxima:
[[Semana 7 — O Stage 3, Busca e Verificação]].
