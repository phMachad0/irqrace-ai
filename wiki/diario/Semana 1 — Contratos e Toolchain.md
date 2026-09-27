---
type: project
tags: [wiki, project, diario, pt-br]
sources: ["[[Roadmap]]", "[[Pipeline Design]]", "[[LLM Stage Design]]", "[[Dashboard Design]]"]
updated: 2026-09-18
status: draft
---

# Semana 1 — Contratos e Toolchain

> [!info] Sobre esta pasta
> `wiki/diario/` é a **única** parte do vault escrita em português. Ela registra, semana a
> semana, o que foi efetivamente implementado em `project-src/`, com trechos de código e com
> todo conceito técnico explicado. O restante do vault continua em inglês, porque o vocabulário
> vem dos artigos.

**Período:** 31 ago – 4 set 2026 · **Trilha A** (análise estática) · Corresponde a
[[Roadmap]] W1.

## 1. O que a semana tinha que entregar

| Item do Roadmap | Situação |
| --- | --- |
| Congelar os contratos C1, C2, C3 e C4 como arquivos de *schema* com exemplos | feito |
| Toolchain no ar: `clang -g -emit-llvm`, `llvm-link`, SVF compilando e rodando | feito |
| Parser do arquivo de configuração (C1) | feito |
| **Critério de pronto:** os 31 casos simples do [[Racebench]] compilam para *bitcode* | 31/31 |
| **Critério de pronto:** a configuração carrega para pelo menos um caso | carrega para os 31 |
| **Critério de pronto:** o SVF lista os globais de um caso | feito |

## 2. Conceitos que aparecem nesta semana

Antes do código, o vocabulário. Cada termo abaixo é usado no restante da página.

**Fluxo (*flow*).** Uma linha de execução independente do programa. Em software embarcado
dirigido a interrupção existem dois tipos: a **tarefa principal** (o `main`, que roda
continuamente) e as **ISRs** (*Interrupt Service Routines*, as rotinas de tratamento de
interrupção). O que torna esse modelo diferente de *threads* é a **preempção assimétrica**: uma
ISR pode interromper a tarefa principal em qualquer ponto, mas a tarefa principal nunca
interrompe uma ISR ([[Asymmetric Preemption]]).

**Prioridade.** Cada ISR tem um número de prioridade. Uma ISR só pode interromper outro fluxo se
tiver prioridade **estritamente maior**. Neste projeto vale a convenção **número maior = maior
prioridade**, que vem do próprio README do Racebench e contraria a prosa de dois dos artigos
([[Contradictions]] #3).

**Máscara de interrupção (*masking*).** O mecanismo de sincronização do mundo embarcado. Em vez
de travar um *mutex*, o código **desabilita** a interrupção durante a região crítica. No
Racebench isso são as funções `disable_isr(n)` e `enable_isr(n)`; `n = -1` significa "todas as
interrupções".

**Condição de corrida (*data race*).** Dois acessos à mesma posição de memória, vindos de fluxos
diferentes, em que pelo menos um é uma escrita e não há sincronização entre eles.

**Violação de atomicidade (*atomicity violation*).** Mais sutil: três acessos. Dois deles
(`A₁` e `A₂`) estão no mesmo fluxo e deveriam formar uma operação indivisível; um terceiro (`B`),
de outro fluxo, se intercala entre eles e quebra a suposição. O Racebench anota seus defeitos
exatamente nesse formato de trinca.

**Bitcode LLVM.** Representação intermediária do compilador LLVM. O `clang` traduz C para
bitcode, e a análise trabalha sobre o bitcode em vez do texto C — porque no bitcode cada leitura
e escrita de memória é uma instrução explícita (`load` e `store`), sem a ambiguidade sintática
do C.

**`DILocation` / *debug info*.** Metadados que o compilador anexa a cada instrução do bitcode
dizendo de qual arquivo, linha e coluna ela veio. É o que permite pegar um resultado no nível do
bitcode e mostrá-lo de volta como código C. Sem `-g` na compilação esses metadados não existem, e
sem eles o registro de contexto que o estágio de LLM consome não pode ser montado.

**SVF (*Static Value-Flow*).** Uma biblioteca de análise estática sobre LLVM. Usamos dela a
**análise de apontadores** (*points-to analysis*): dado um ponteiro, qual é o conjunto de objetos
de memória para os quais ele **pode** apontar.

**May-alias vs must-alias.** `may-alias` responde "estes dois ponteiros *podem* apontar para o
mesmo lugar?"; `must-alias` responde "eles *necessariamente* apontam?". Para não perder defeitos
temos que usar `may`: se a análise disser "não são o mesmo lugar" quando na verdade podem ser, o
candidato desaparece silenciosamente.

**JSON Schema.** Um formato para descrever, de maneira verificável por máquina, qual é a forma
de um documento JSON: quais campos existem, quais são obrigatórios, quais valores são aceitos.
É o que transforma um contrato de "combinado em uma reunião" em algo que um teste consegue
checar.

**NDJSON.** *Newline-delimited JSON*: um objeto JSON por linha. Permite que um arquivo seja lido
enquanto ainda está sendo escrito, e que se use `grep` nele — importante porque o dashboard vai
acompanhar uma análise em andamento.

## 3. Por que quatro contratos, e por que na primeira semana

O projeto tem duas pessoas trabalhando em paralelo: eu na análise estática (Trilha A) e o Lucas
no *pipeline* de LLM (Trilha B). O Lucas não pode esperar o meu estágio 1 existir para começar —
isso serializaria o projeto inteiro e não há folga para isso em dez semanas.

A única forma de paralelizar é **combinar antes, de maneira precisa, o formato dos dados que
atravessam a fronteira entre as duas trilhas**. Feito isso, o Lucas constrói fixtures
(exemplares fabricados à mão) naquele formato e desenvolve contra eles por sete semanas; na
semana 8 troca-se o falso pelo verdadeiro e nada mais muda.

| | Contrato | O que é | Dono | Consumidores |
| --- | --- | --- | --- | --- |
| **C1** | arquivo de configuração — o modelo de interrupções | A | A, C |
| **C2** | **registro de contexto** — um objeto JSON por candidato | A | B, C |
| **C3** | layout do *run store* — diretórios, NDJSON, manifesto | A | B, C |
| **C4** | protocolo de requisição de contexto | **B** | A |

O C4 pertence à Trilha B porque **quem consome é quem deve dizer o que precisa perguntar**; a
Trilha A só implementa o resolvedor por trás.

## 4. C1 — o arquivo de configuração

O C1 descreve o modelo de interrupções: quais funções são pontos de entrada, quais são ISRs, com que número e prioridade, e quais funções mexem na máscara. A decisão de escrevê-lo à mão em vez de inferir com LLM está registrada em [[Specification Inference]].

Uma propriedade importante: **o C1 delimita o custo da análise**. O trabalho é proporcional ao
código alcançável a partir dos pontos de entrada declarados, não ao tamanho do repositório.

Os 31 arquivos de configuração do Racebench **não foram escritos à mão**: são gerados a partir
da tabela que o próprio README da suíte publica, o que os torna rastreáveis até a fonte
primária.

```python
# project-src/src/irqrace/racebench.py
CASE_RE = re.compile(r"^svp_simple_(\d{3})_001\.c$")
HANDLER_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*/\s*(-?\d+)\s*/\s*(-?\d+)")
```

`HANDLER_RE` casa entradas do tipo `svp_simple_001_001_isr_1/1/1`, isto é
`nome_da_função/número_da_interrupção/prioridade`.

O resultado, para o caso 13 (três ISRs):

```yaml
flows:
- {id: main,  kind: task, entry: svp_simple_013_001_main,  irq: null, priority: 0}
- {id: isr_1, kind: isr,  entry: svp_simple_013_001_isr_1, irq: 1,    priority: 1}
- {id: isr_2, kind: isr,  entry: svp_simple_013_001_isr_2, irq: 2,    priority: 2}
- {id: isr_3, kind: isr,  entry: svp_simple_013_001_isr_3, irq: 3,    priority: 3}
masking:
  primitives:
  - {function: disable_isr, effect: disable, irq_arg: 0, all_value: -1}
  - {function: enable_isr,  effect: enable,  irq_arg: 0, all_value: -1}
  initial_state: all-enabled
semantics:
  equal_priority_preemption: true
  isr_arrival: unbounded
  isr_reentrant: false
  nesting: true
  timing_model: unconstrained
```

O bloco `semantics` merece atenção. Cada um daqueles campos **muda o conjunto de candidatos**, e dois deles eram questões em aberto no vault. Em vez de decidir escondido no código, viraram configurações nomeadas, com padrões seguros do ponto de vista de *recall*, e são copiadas para o manifesto de toda execução — de modo que nenhum número que o projeto reportar fica solto da  suposição que o produziu.

A regra de prioridade mora em **uma única função**, porque errar o sentido dela descartaria
exatamente as preempções reais:

```python
# project-src/src/irqrace/config.py
def can_preempt(self, high: Flow, low: Flow) -> bool:
    """LARGER NUMBER = HIGHER PRIORITY."""
    if high.id == low.id:
        return bool(self.semantics["isr_reentrant"])
    if not high.is_isr:
        return False  # uma tarefa nunca preempta nada
    if high.priority > low.priority:
        return True
    if high.priority == low.priority:
        return bool(self.semantics["equal_priority_preemption"])
    return False
```

## 5. C2 — o registro de contexto

É **o** contrato: a costura entre mim e o Lucas. Um objeto JSON por candidato, com tudo que um
modelo de linguagem precisaria para julgar aquele candidato — a variável, os acessos com
localização no fonte, os fluxos e suas prioridades, os caminhos de chamada, o estado da máscara, o corpo das funções envolvidas, o veredito do *solver* e a procedência de cada fato.

Cinco decisões sobre *recall* foram tornadas **estruturais** no schema, em vez de deixadas a
cargo do código. A diferença é que uma decisão estrutural não pode ser revertida por descuido:
não existe campo para expressar a alternativa errada.

**(1) A máscara tem três valores, não dois.**

```json
"MaskingState": {
  "required": ["disabled", "enabled", "unknown"],
  "properties": {
    "disabled": { "description": "Provably disabled on every path." },
    "enabled":  { "description": "Provably enabled on at least one path." },
    "unknown":  { "description": "Not decided — consumers MUST treat these as enabled." }
  }
}
```

Não existe um booleano `is_masked` para alguém usar por engano. Uma interrupção só conta como desabilitada se estiver desabilitada **em todos os caminhos** que chegam àquele ponto;
"desabilitada em algum caminho" vira defeito perdido.

**(2) A propriedade de intervalo é um campo separado da propriedade de ponto.** Para um par a
pergunta é "`B` pode rodar *no instante* de `A`?"; para uma trinca é "`B` pode rodar em
*qualquer ponto* de `[A₁, A₂]`?". Responder uma e inferir a outra é o erro que
[[Pair-Triple Unification]] existe para evitar.

**(3) O veredito do solver tem quatro valores, não dois**: `unsat`, `sat`, `inconclusive` e
`not_run` — e `inconclusive` exige um motivo. Colapsar `inconclusive` em `unsat` seria perda
silenciosa de *recall*; em `sat`, perda do sinal que o estágio de LLM existe para explorar.

**(4) `provenance` é obrigatório.** Marca cada fato como provado, suposto pela configuração,
super-aproximado ou desconhecido. Não é burocracia: um modelo que recebe evidência incompleta declara candidatos infactíveis com confiança, e esse erro fica invisível depois.

**(5) Não existe campo `slice`, e não deve existir.** O contexto é recuperado sob demanda pelo
C4, não pré-computado ([[Program Slicing]]).

Além disso, cada registro carrega um `fingerprint` — um *hash* de conteúdo:

```
"id":          "cf8fd11d0783ef732"
"fingerprint": "f8fd11d0783ef732b0a3363978f24cae..."
```

O `fingerprint` cobre **só** o sujeito, a classe, o nome da variável e as localizações ordenadas
dos acessos. Não cobre identificador de execução, tempos nem veredito do solver. Dois motivos: o cache de triagem do Lucas é indexado por `(fingerprint, configuração de prompt, modelo)`, e se o valor mudasse entre execuções o cache erraria em silêncio; e é a chave que liga o mesmo candidato em `stage1/`, `stage2/`, `solver/`, `context/`, `llm/` e `repair/`.

## 6. C3 — o *run store*

"Uma execução é um diretório, não uma sessão." Cada análise produz `runs/<id>/` com o manifesto,a configuração usada, o bitcode, os candidatos de cada estágio, os resultados do solver, os registros de contexto, as conversas com o LLM, os patches e um log.

Das oito regras do C3, a que sustenta a tese é a regra 6:

> Só `solver/results.jsonl` pode registrar um descarte. Um candidato ausente de `context/`
> precisa ter uma linha `unsat` nomeando-o.

E ela é **verificada mecanicamente**:

```python
# project-src/src/irqrace/runstore.py
for cid in sorted(survivors - contexts):
    if verdicts.get(cid) != "unsat":
        problems.append(
            f"candidate {cid} has no context record and no 'unsat' "
            "solver verdict: it was dropped without a proof, which "
            "is a silent recall loss (C3 rule 6)")
```

Existe um teste que apaga deliberadamente a prova e verifica que o checador acusa.

## 7. C4 — requisição progressiva de contexto

Em vez de mandar um *slice* pré-computado, o registro leva as camadas baratas e o modelo
**pergunta** o que faltar. O conjunto de perguntas é fechado: definição de função, corpo de uma
ISR, estado da máscara numa linha, expansão de macro, todos os outros acessos a uma variável,
todos os caminhos de chamada, definição de tipo, declaração de global.

O campo que faz trabalho de verdade é o `status` da resposta. Quando o modelo pede uma função que
não tem corpo no módulo, a tentação é devolver vazio — mas vazio **se lê como** "essa função não
toca a variável", que é exatamente o falso negativo induzido que o projeto proíbe:

```json
{
  "status": "not_found",
  "recall_rule": "When you cannot obtain a function's definition, assume it may access the shared variable."
}
```

A regra de auto-validação viaja junto com a resposta.

## 8. Toolchain

| Componente | Versão | Observação |
| --- | --- | --- |
| clang / LLVM | 14 | do sistema |
| SVF | 2.7 | é a *release* que tem como alvo o LLVM 14 |
| Z3 | 4.8.12 | do sistema |

O `setup-svf.sh` compila o SVF **contra o LLVM do sistema**, e não baixa o LLVM pré-compilado que o próprio SVF oferece. Dois motivos: o pacote pré-compilado ocupa vários gigabytes descompactado e a máquina tinha menos de 4 GB livres; e usar o mesmo LLVM para compilar os sujeitos e para analisá-los mantém a versão do bitcode e a análise em sintonia. Custou 64 MB e uns dez minutos.

**A armadilha do `optnone`.** `-g` é obrigatório. `-O0` sozinho marca todas as funções com o
atributo `optnone`, e o gerenciador de passes do LLVM simplesmente pula funções assim. Daí a
combinação:

```
-g -O0 -Xclang -disable-O0-optnone
```

E o `build.py` se recusa a compilar sem `-g`, porque isso não é preferência:

```python
if "-g" not in flags:
    raise BuildError(
        "build.flags does not contain -g. Debug metadata is what makes the "
        "source mapping possible; without it every candidate loses its "
        "source range and the context record cannot be built.")
```

## 9. `irqrace-probe` — o sonda do módulo

Ferramenta em C++ que carrega o bitcode pelo SVF, roda a análise de apontadores e relata o que o módulo realmente contém. Não é um teste descartável: a saída dela alimenta o bloco `build` do manifesto C3 e responde dois requisitos do [[Dashboard Design]] — **R4** (mostrar o que o build produziu, inclusive a lista de funções sem corpo) e **R7** (validar o modelo de interrupções
contra o bitcode **nos dois sentidos**).

```
svp_simple_003_001: 4 global(s), 5 function(s) with bodies, 2 declared only (disable_isr, enable_isr)
  debug info: 56/56 loads, stores and calls mapped
  volatile int       svp_simple_003_001_global_flag    svp_simple_003_001.c:25  pag=4
  ...
```

Detalhe que custou tempo: em C, `volatile int a[10]` grava o qualificador no tipo **do
elemento**, não no do vetor. Como o estado compartilhado do Racebench é em boa parte vetores, sem tratar isso todos apareceriam como não-`volatile`:

```cpp
// project-src/analysis/src/irqrace-probe.cpp
if (const auto *c = llvm::dyn_cast<llvm::DICompositeType>(t)) {
  if (c->getTag() == llvm::dwarf::DW_TAG_array_type) {
    t = c->getBaseType();   // desce para o tipo do elemento
    continue;
  }
}
```

## 10. Três achados da semana

**(a) O README do Racebench nomeia dois pontos de entrada errado.** A tabela diz
`svp_simple_028_001_main` e `svp_simple_030_001_main`; os arquivos definem `..._001__main`, com **dois** sublinhados. Não é cosmético: uma ferramenta que confia na tabela analisa a tarefa principal desses dois casos como inalcançável, ela não contribui acesso nenhum, e todo defeito
que a envolve some — sem erro em lugar nenhum. A checagem R7 da sonda pegou isso no primeiro build da suíte, que é precisamente para isso que ela existe.

**(b) Análise de máscara por fluxo, isolada, descarta um *bug point* anotado.** Em
`svp_simple_001_001` a tarefa principal desabilita a interrupção 2 na linha 28 e nunca a
reabilita. Olhando só o grafo de fluxo de controle da tarefa principal, a interrupção 2 está
mascarada em todo o intervalo `[32, 35]` do *bug point* — logo o candidato seria descartado.

Só que a `isr_1` continua habilitada, pode preemptar a tarefa dentro desse intervalo, e faz
`enable_isr(2)`. A máscara que parecia uma prova não é uma. A regra correta tem duas cláusulas:

> A interrupção *n* está mascarada em todo `[A₁, A₂]` somente se **(a)** *n* está mascarada em
> todo ponto de todo caminho de `A₁` a `A₂` no fluxo local, **e** **(b)** nenhum fluxo que possa
> executar dentro desse intervalo a reabilita.

O contrato ganhou o campo `reenabled_within_interval_by` por causa disso, e a análise completa
está em `project-src/docs/masking-semantics.md`.

**(c) `getCalledFunction()` devolve nulo para chamadas diretas.** O `common.h` do Racebench
declara seus auxiliares no estilo K&R:

```c
void idlerun();
void init();
extern int rand();
```

Em C, lista de parâmetros vazia significa *argumentos não especificados*. Então a declaração tem
tipo LLVM `void (...)` enquanto a definição em `common.c` tem tipo `void ()`, e depois do
`llvm-link` toda chamada passa por um *bitcast*. O `CallBase::getCalledFunction()` é um
`dyn_cast` direto do operando, sem remover conversões, então devolve nulo.

Lido ingenuamente, isso faz **todos os 31 sujeitos parecerem conter chamadas indiretas**. Para um
analisador que se quer completo isso não é cosmético: a regra para uma chamada indireta não
resolvida é supor que ela alcança *toda função com endereço tomado e assinatura compatível*, o
que super-aproximaria os 31 grafos de chamada à toa. A correção é uma linha:

```cpp
const llvm::Value *callee = ci->getCalledOperand()->stripPointerCasts();
```

Com ela, **exatamente um** dos 31 casos usa despacho por ponteiro de função de verdade:
`svp_simple_029_001`.

## 11. Como reproduzir

```bash
./scripts/setup-svf.sh && ./scripts/build-analysis.sh && source scripts/env.sh
```

```bash
irqrace doctor
```

```bash
irqrace contracts validate
```

```bash
irqrace bench gen-configs && irqrace bench build-all --probe
```

## 12. Estado ao fim da semana

142 testes passando, incluindo um que compila e sonda os 31 sujeitos de ponta a ponta. Ainda não
existiam: estágio 1, estágio 2, estágio Z3, estágio de LLM, dashboard.

Continua em [[Semana 2 — Ground Truth e Protocolo de Avaliação]].
