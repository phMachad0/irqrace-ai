---
type: project
tags: [wiki, project, diario, pt-br]
sources: ["[[Roadmap]]", "[[Pipeline Design]]", "[[IntRace (paper)]]", "[[Soundness Assumptions]]"]
updated: 2026-09-18
status: draft
---

# Semana 3 — O Front End do Stage 1

**Período:** 14–18 set 2026 · **Trilha A** · Corresponde à primeira metade de [[Roadmap]] W3–W4.
Página anterior: [[Semana 2 — Ground Truth e Protocolo de Avaliação]].

> [!note] Sobre a divisão W3 / W4
> O [[Roadmap]] trata W3–W4 como **um único bloco** — "Stage 1" — e a implementação foi feita de
> uma vez, não em duas etapas separadas. A divisão entre esta página e
> [[Semana 4 — Derivação de Candidatos e o Recall Gate]] é **temática**, seguindo a ordem dos
> próprios itens do Roadmap: aqui o *front end* (alcançabilidade, posições compartilhadas,
> enumeração de acessos); lá a derivação de candidatos, a emissão dos registros e o portão de
> recall.

## 1. O que o bloco tinha que entregar

| Item do Roadmap | Onde está |
| --- | --- |
| Pontos de entrada a partir da configuração; alcançabilidade interprocedural por fluxo | esta página |
| Identificação de posições compartilhadas via **may**-alias do SVF | esta página |
| Enumeração de acessos: fluxo, R/W, função, caminho de chamada, `DILocation`, contexto de laço | esta página |
| Derivação de candidatos — pares **e** trincas de um só conjunto de acessos | [[Semana 4 — Derivação de Candidatos e o Recall Gate]] |
| Emitir registros C2 e diretórios C3 | [[Semana 4 — Derivação de Candidatos e o Recall Gate]] |
| **Critério de pronto:** `candidates.jsonl` para os 31 casos, recall 48/48 | [[Semana 4 — Derivação de Candidatos e o Recall Gate]] |

## 2. Conceitos desta semana

**Estágio 1 (*stage 1*).** O gerador de candidatos. Ele **ignora de propósito** condições de
guarda e estado das interrupções, para que nada seja perdido ([[Pipeline Design]]). Máscara é
problema do estágio 2; viabilidade de caminho é do estágio 3. **O estágio 1 não descarta nada.**

**Grafo de chamadas (*call graph*).** Grafo em que os nós são funções e as arestas são chamadas.
É o que permite responder "partindo desta ISR, que funções podem ser executadas?".

**Alcançabilidade (*reachability*).** O fecho transitivo do grafo de chamadas a partir de um
ponto de entrada. Cada fluxo é a raiz da sua própria alcançabilidade.

**Chamada indireta.** Chamada através de um ponteiro de função (`ops->read(...)`), em que o alvo
não está escrito no código. Firmware de verdade faz isso o tempo todo, via tabelas de vetores.

**Função com endereço tomado (*address-taken*).** Função cujo endereço é usado como valor em
algum lugar — logo, alvo possível de uma chamada indireta.

**CFG (*Control Flow Graph*).** Grafo de fluxo de controle **dentro** de uma função: nós são
blocos básicos (sequências retas de instruções) e arestas são desvios possíveis.

**Bloco básico.** Sequência de instruções sem desvio no meio: entra pelo começo, sai pelo fim.

**Aresta de retorno (*back edge*) e ciclo.** Um laço no código vira um ciclo no CFG. Se existe
caminho de um bloco de volta para ele mesmo, aquele bloco está num ciclo — e isso é exatamente o
teste de "essa instrução pode executar mais de uma vez".

**Objeto de memória / nó PAG.** O SVF representa cada alocação (um global, um `alloca` de pilha,
um `malloc`) como um objeto abstrato, com um identificador numérico no PAG (*Program Assignment
Graph*).

**Objeto base vs sensibilidade a campo.** Uma análise sensível a campo distingue `a[0]` de
`a[999]` e `s.x` de `s.y`. **Normalizar para o objeto base** significa tratar o vetor inteiro
como uma posição só.

## 3. Arquitetura: onde mora cada metade

A decisão de pilha do vault ([[Reimplementation Assessment]]) é **C++ para tudo que toca LLVM e
SVF, Python para orquestração e bookkeeping** — as bibliotecas são C++ e *bindings* dariam briga.

```
irqrace-stage1 (C++/SVF)           stage1.py (Python)
  grafo de chamadas                  derivação de pares
  alcançabilidade por fluxo   ──►    derivação de trincas
  posições compartilhadas            registros C2
  enumeração de acessos              run store C3
  relação may_precede
        │
        └── accesses.json
```

A fronteira é um único JSON. O C++ entrega **fatos** sobre o programa; o Python decide o que
fazer com eles.

## 4. Grafo de chamadas próprio, e não o do SVF

O SVF constrói um grafo de chamadas. Mesmo assim construí o meu. O motivo é a suposição **B2** da
lista de completude:

> Uma chamada indireta cujos alvos não podem ser resolvidos é tratada como podendo chamar **toda
> função com endereço tomado e assinatura compatível**. Um conjunto de alvos vazio **nunca** é
> lido como "não chama nada".

Isso não é o que uma análise de apontadores faz sozinha, e a direção do erro importa: resolver
para o conjunto vazio **apaga subárvores inteiras de acessos alcançáveis**, e a perda é invisível
na saída.

```cpp
// project-src/analysis/src/irqrace-stage1.cpp
const llvm::Value *callee = ci->getCalledOperand()->stripPointerCasts();
if (const auto *cf = llvm::dyn_cast<llvm::Function>(callee)) {
  if (!cf->isIntrinsic())
    out.push_back({cf, &*I, "direct"});
  continue;
}

++indirectSites;
std::set<const llvm::Function *> targets = pointsToTargets(ci);
const char *how = "indirect-resolved";
if (targets.empty() && cfg.signatureFallback) {
  ++overApproximatedSites;
  how = "indirect-overapproximated";
  for (const llvm::Function *cand : addressTaken)
    if (signatureMatches(cand, ci))
      targets.insert(cand);
}
```

O `stripPointerCasts()` na primeira linha é a correção do achado (c) da semana 1: sem ele, os
protótipos estilo K&R do `common.h` fazem todos os 31 sujeitos parecerem usar ponteiro de função.

Repare que cada aresta carrega **como** foi resolvida (`direct`, `indirect-resolved`,
`indirect-overapproximated`). Essa informação atravessa até o registro C2 e vira uma entrada de
`provenance`, para que o modelo de linguagem saiba que aquele caminho de chamada é um palpite
conservador e não um fato.

E a comparação de assinatura é **generosa de propósito**, porque excluir um alvo é a direção
insegura:

```cpp
static bool signatureMatches(const llvm::Function *f, const llvm::CallBase *ci) {
  llvm::FunctionType *ft = f->getFunctionType();
  if (ft == ci->getFunctionType())
    return true;
  // Uma diferença exata de tipos não deve excluir um alvo; exigimos só
  // compatibilidade de aridade.
  if (ft->isVarArg())
    return true;
  return ft->getNumParams() == ci->arg_size();
}
```

## 5. Alcançabilidade por fluxo

Busca em largura a partir do ponto de entrada. Guarda-se **um caminho de chamada representativo**
por função alcançada — o mais curto — e registra-se que existem outros.

```cpp
struct Reach {
  std::map<const llvm::Function *, std::vector<Frame>> path;
  std::set<const llvm::Function *> multiplePaths;
  // Todo call site alcançável de cada callee, como (caller, site).
  std::map<const llvm::Function *,
           std::vector<std::pair<const llvm::Function *, const llvm::Instruction *>>>
      callSites;
};
```

O `multiplePaths` vira o campo `is_one_of_many` do C2: o consumidor precisa saber que o caminho
mostrado não é o único. O `callSites` vai ser usado na [[Semana 4 — Derivação de Candidatos e o Recall Gate]].

Duas classes de função **não** são percorridas:

```cpp
// Primitivas de máscara e externos modelados são descritos pelo arquivo de
// configuração, não percorridos (Soundness Assumptions D2, D3).
if (cfg.maskingPrimitives.count(e.callee->getName().str()) ||
    cfg.transparentExternals.count(e.callee->getName().str()))
  continue;
```

Quais funções foram modeladas e quais ficaram opacas **faz parte da abstração** sobre a qual a
afirmação de completude se apoia — por isso a lista viaja na configuração e no manifesto, e não
fica embutida no código.

## 6. Posições compartilhadas via may-alias

Para cada `load` e `store`, pega-se o operando ponteiro, pergunta-se ao SVF o conjunto
*points-to*, e normaliza-se cada objeto para o seu **objeto base**:

```cpp
auto objectsTouched = [&](const llvm::Value *ptr) {
  std::set<NodeID> out;
  SVFValue *sv = LLVMModuleSet::getLLVMModuleSet()->getSVFValue(ptr);
  if (!sv || !pag->hasValueNode(sv))
    return out;
  for (NodeID o : pta->getPts(pag->getValueNode(sv))) {
    if (pag->isBlkObjOrConstantObj(o))
      continue;
    // Normaliza para o objeto BASE. Sensibilidade a campo separaria
    // `a[TRIGGER]` de `a[1000]`, e separar é a direção insegura aqui: dois
    // acessos que PODEM ser ao mesmo elemento têm que continuar comparáveis.
    // Distingui-los é trabalho do estágio 3, que consegue provar.
    out.insert(pag->getBaseObjVar(o));
  }
  return out;
};
```

O custo dessa escolha é visível e correto: a segunda armadilha plantada do `svp_simple_001_001` é
exatamente um acesso a `global_array[1000]` onde as escritas são em `global_array[9999]`. Ela
sobrevive ao estágio 1 — e **deve** sobreviver, porque o estágio 1 não tem prova nenhuma de que
os índices diferem.

### O critério de compartilhamento

Aqui está o erro que o portão de recall pegou depois, e vale explicar já: a primeira versão
filtrava para `isGlobalObj()`. Isso é um **atalho**, não um critério. O critério real é:

```cpp
if (!mo || mo->isFunction())
  continue; // o alvo de um ponteiro de função não é dado
// Deliberadamente NÃO restrito a globais. O svp_simple_009_001 compartilha
// uma variável de PILHA entre tarefa e ISR guardando o endereço dela em dois
// ponteiros globais, e o bug point anotado é uma trinca nesse objeto.
```

O que torna uma posição compartilhada é **dois fluxos a alcançarem**, não onde ela foi alocada.

Objetos que só um fluxo toca são descartados depois — isso é seguro, porque nenhum candidato de
nenhuma das duas classes pode se formar a partir deles, e sem esse descarte cada contador de laço
e cada variável local aparece no conjunto de acessos.

## 7. Enumeração de acessos

Para cada instrução `load`/`store` em função alcançável, registra-se: fluxo, leitura ou escrita,
função, intervalo no fonte a partir do `DILocation`, aninhamento de laços e o caminho de chamada.

O aninhamento de laços vem do `LoopInfo` do LLVM, que precisa de uma árvore de dominadores:

```cpp
auto *mut = const_cast<llvm::Function *>(f);
cfgs[f] = std::make_unique<FunctionCFG>(*f);
dts[f] = std::make_unique<llvm::DominatorTree>(*mut);
loops[f] = std::make_unique<llvm::LoopInfo>(*dts[f]);
```

```cpp
for (const llvm::Loop *l = li.getLoopFor(I->getParent()); l; l = l->getParentLoop()) {
  a.inLoop = true;
  SourceRange h;
  if (const llvm::BasicBlock *hb = l->getHeader())
    if (const llvm::Instruction *hi = hb->getFirstNonPHI())
      h = rangeOf(hi);
  a.loopHeaders.push_back(h);
}
```

### Dois detalhes que custaram tempo

**Spills de prólogo não são acessos.** Em `-O0`, o clang guarda cada parâmetro num `alloca` do
bloco de entrada, e esse `store` não tem `DebugLoc` nenhum. Tratá-lo como acesso produz candidato
sem intervalo no fonte:

```cpp
if (llvm::isa<llvm::Argument>(st->getValueOperand()) &&
    st->getParent() == &fn->getEntryBlock())
  continue;
```

É seguro pular porque o `alloca` escrito é o slot do próprio parâmetro — qualquer
compartilhamento real daquele valor reaparece nos `load`s e `store`s seguintes.

**Quando o `DebugLoc` falta de verdade, recupera-se — não se descarta.**

```cpp
if (!a.src.valid()) {
  // Descartar o acesso seria perda silenciosa de recall (Soundness Assumptions
  // A2). Usa-se a linha da função e marca-se o registro: uma localização
  // imprecisa é recuperável por um leitor; um candidato ausente não é.
  if (const llvm::DISubprogram *sp = fn->getSubprogram()) {
    a.src.file = sp->getFilename().str();
    a.src.line = sp->getLine();
  }
  a.sourceRecovered = true;
  ++recoveredRanges;
}
```

Do lado Python, essa marca vira procedência explícita:

```python
if any(self.accesses[i].get("source_recovered") for i in acc_ids):
    entries.append({
        "fact": "accesses.source", "status": "overapproximated",
        "note": "an access carried no debug location; the enclosing "
                "function's line was used. ..."})
```

## 8. A relação `may_precede`

É o fato que a derivação de trincas precisa: **dentro de um fluxo, o acesso `a` pode ser seguido,
mais tarde, pelo acesso `b`?**

Dentro de uma função, é alcançabilidade no CFG em granularidade de instrução:

```cpp
bool mayPrecede(const llvm::Instruction *a, const llvm::Instruction *b) const {
  const llvm::BasicBlock *ba = a->getParent(), *bb = b->getParent();
  if (ba != bb)
    return reach.at(index.at(ba)).at(index.at(bb));
  if (order.at(a) < order.at(b))
    return true;
  // Mesmo bloco, b em ou antes de a: só se alcança dando a volta num ciclo.
  return reach.at(index.at(ba)).at(index.at(ba));
}
```

Três comportamentos caem fora disso de graça, e todos os três importam:

1. **`a` precede `a`** quando o bloco está num ciclo — isto é, **a mesma instrução dentro de um
   laço serve como `A₁` e `A₂`**. É o caso que o `svp_simple_029_001` anota, e 7 das 86 trincas
   da suíte têm essa forma.
2. **Ramos mutuamente exclusivos não se precedem.** No `isr_2` do caso 001, as leituras nas linhas
   55 e 58 estão nos dois braços de um `if/else`. Nenhuma execução faz as duas, e o CFG estabelece
   isso **estruturalmente**, sem apelar para condição de guarda nenhuma. Não é filtragem: é que
   não há candidato a gerar.
3. **Ordem de retorno de laço.** Um acesso numa linha posterior pode preceder um numa linha
   anterior, se a aresta de retorno os conecta.

Entre funções diferentes, dentro do mesmo fluxo, **super-aproxima-se para verdadeiro**:

```cpp
} else {
  // Provar que um callee não pode rodar antes de outro exigiria ordenação
  // interprocedural que o front end não tem, e chutar seria a direção insegura.
  ok = true;
}
```

## 9. A saída

```json
{
  "tool": "irqrace-stage1",
  "flows": [ {"id": "main", "entry": "...", "reachable_functions": 1, "resolved": true}, ... ],
  "objects": [ {"id": 14, "name": "svp_simple_001_001_global_array",
                "declared_type": "volatile int[]", "volatile": true,
                "flows": ["isr_2", "main"]} ],
  "functions": [ {"name": "...", "line_start": 25, "line_end": 37} ],
  "accesses": [ {"id": 0, "flow": "main", "object": 14, "kind": "write",
                 "source": {"line": 32, "column": 70},
                 "in_loop": true, "loop_headers": [...],
                 "call_path": {"frames": [...], "is_one_of_many": false}} ],
  "may_precede": [ [0, 0], [0, 1], [1, 1], [3, 4], [6, 8], [7, 8] ],
  "indirect_call_sites": 0,
  "warnings": []
}
```

Olhando o `may_precede` do caso 001 dá para conferir tudo o que foi dito acima: `[0,0]` está lá
(a escrita da linha 32 está num laço); `[1,0]` não está (os dois laços são sequenciais); e o par
entre os dois braços do `if/else` da `isr_2` também não está.

## 10. Estado ao fim desta metade

O *front end* produz o conjunto de acessos e a relação de ordem para os 31 sujeitos. Ainda falta
transformar isso em candidatos e medir.

Continua em [[Semana 4 — Derivação de Candidatos e o Recall Gate]].
