---
type: project
tags: [wiki, project, diario, pt-br]
sources: ["[[Roadmap]]", "[[Real-World Program Benchmark]]", "[[Contradictions]]", "[[Soundness Assumptions]]", "[[Rastro-Robot Firmware]]", "[[Racebench]]"]
updated: 2026-10-30
status: draft
---

# Semana 9 — O Benchmark de Programas Reais

**Período planejado:** 26–30 out 2026 · **feito em:** 29–30 out 2026 (em andamento) · branch
`semana-9` (aberto como `bench/real-world` a partir da `main`, `55d25eb`, e renomeado em 30/10:
todo o trabalho da W9 fica nele) · [[Roadmap]] W9 (*Real-world suite and
repair support*). Página anterior: [[Semana 8 — Integração das Trilhas A e B]].

> [!note] O que esta página cobre
> A primeira vez que a ferramenta saiu do [[Racebench]]. Foram dois sujeitos no mesmo dia. Primeiro,
> o firmware do robô do Pedro, com um bug plantado (§3.1), que expôs três problemas que o Racebench
> não podia mostrar. Depois, os 18 programas "reais" que o NIChecker e o BMC4AV usam (§3.2 em
> diante). Antes de rodar qualquer análise, esse benchmark revelou que existe em **duas versões
> diferentes**, e que o próprio gabarito tem linhas erradas.

## 1. O que a semana devia entregar

| Item do Roadmap (W9) | Estado | Onde |
| --- | --- | --- |
| Os 18 programas do [[Real-World Program Benchmark]], com o `priority.info` importado diretamente | **pronto** — vendorizado, 18/18 compilam, C1 gerado do `priority.info`, *recall gate* **45/45** | `bench/realworld/`, `src/irqrace/realworld.py`, `irqrace realworld` |
| Suporte a re-verificação: re-rodar a análise como certificado e como teste de regressão; CBMC/`bmc4av` para os inconclusivos | **não iniciado** | — |
| Trilha B: triagem e reparo nos 18 programas | **não iniciado** — depende do funil da §3.8 | — |

## 2. Conceitos usados nesta página

**Benchmark de programas reais.** Dezoito programas C dirigidos por interrupção, em seis famílias
(`logger`, `blink`, `brake`, `i2c_pca_isa`, `i8xx_tco`, `wdt_pci`), três versões de cada, com 149 a
1356 linhas. Vários são *drivers* do Linux extraídos para um único `main.c` (o `wdt_pci` é o
`drivers/watchdog/wdt_pci.c`). Cada programa traz dois arquivos de metadados:

- **`priority.info`**: uma linha `nome:prioridade` por rotina de interrupção (ISR). Número maior
  significa prioridade maior ([[Contradictions]] #3).
- **`violation.info`**: o gabarito (*ground truth*). É a lista das violações de atomicidade que o
  programa contém (`true violation`) e dos falsos alarmes plantados (`false violation`, o que no
  Racebench chamamos de *trap*).

**Vendorizar.** Copiar uma dependência externa para dentro do repositório, fixada numa versão
conhecida. A ferramenta e todos os números passam a ler essa cópia. Qualquer clone do repositório
reproduz o resultado sem depender de um diretório que só existe numa máquina. Foi o que se fez
com o Racebench em 29/10 (`bench/racebench/VENDORED.md`).

**Errata.** Um arquivo YAML que lista cada correção que o projeto precisou fazer em material de
terceiros, com a evidência e um grau de confiança: `certain` quando o código admite uma única
leitura, `likely` quando a correção é fortemente sugerida mas reconstrói algo. O material de
terceiros fica intocado, e a correção fica auditável.

**Definição de pré-processador (`-D`).** `clang -DNULL='((void*)0)'` faz o compilador agir como se o
arquivo começasse com `#define NULL ((void*)0)`. Permite compilar um arquivo ao qual falta uma
definição sem editar o arquivo.

**Granularidade do gabarito.** No Racebench, cada violação anotada é uma *instância*: três linhas
exatas (A₁, B, A₂). Aqui, 31 das 45 violações são anotadas **por variável e padrão**
(`true violation int numberOfRecords rww`), sem linhas. Um candidato "casa" com essa anotação se
estiver na mesma variável e tiver o mesmo padrão, em qualquer linha. Esse casamento é mais fraco
que o do Racebench, e qualquer número de *recall* aqui precisa dizer isso.

**Recall gate.** A verificação que define o projeto: toda violação do gabarito precisa estar entre
os candidatos que chegam ao fim do pipeline. Um filtro que derruba uma delas é um defeito da
ferramenta, não um "falso negativo aceitável" ([[Thesis Goal]]).

**`inconclusive` e *timeout*.** O stage 3 dá 10 s ao Z3 por candidato. Se o solver não decide
nesse tempo, o veredito é `inconclusive`, e o candidato **segue adiante**: só `unsat` (prova de
impossibilidade) descarta ([[Soundness Assumptions]] H2).

## 3. O que foi feito, na ordem em que aconteceu

### 3.1. Antes do benchmark: o firmware do robô

Um teste pedido pelo Pedro: plantar uma condição de corrida no firmware do seu robô seguidor de
linha (ESP32, C++, FreeRTOS) e ver se a ferramenta a encontra. O bug é uma atualização perdida
entre a ISR do timer e a tarefa que ela acorda. A ferramenta encontrou o bug e o manteve até a
LLM, que o colocou em primeiro lugar na triagem. O registro completo está em
[[Rastro-Robot Firmware]].

O mais útil foram os três problemas que esse primeiro sujeito em C++ e com dois núcleos expôs,
hoje registrados nas issues #4 a #6 e em [[Soundness Assumptions]] (B2, C2b e a nova **E6**):

1. Em C++, o *fallback* de chamada indireta, que casa os alvos só pela aridade, faz toda chamada
   virtual "chamar" toda tarefa. O stage 1 explodiu para ~15,9 milhões de trincas.
2. O *points-to* insensível a contexto faz dois objetos locais distintos parecerem
   compartilhados. Isso gerou 98% dos candidatos, todos falsos.
3. O filtro de prioridade do stage 2 supõe um único núcleo. No ESP32 isso produziu 25 descartes
   que **não são provas**.

A issue #7 registra uma direção do Pedro: declarar o hardware no C1 e passá-lo à LLM.

### 3.2. As duas cópias do benchmark

O mesmo conjunto de 18 programas existe em dois artefatos: no repositório do NIChecker
(`NIChecker_Experiments/benchmark2_atomicity_violations`) e no artefato do BMC4AV
(`Real-world-Programs/`). O wiki até aqui os tratava como um só, porque afirmava que os
`violation.info` eram idênticos byte a byte. Comparando arquivo por arquivo:

| | cópia NIChecker | cópia BMC4AV |
| --- | --- | --- |
| `main.c` | **difere nos 18** | |
| `main` | mascara as interrupções em volta da inicialização | substituído por um *harness* de threads do CBMC (`__CPROVER_ASYNC_1: Timer_A_isr();`) |
| `priority.info` | nomes sem `_isr`, sem `main` | nomes certos, `main:0` |
| prioridades | | **discordam em 5 programas**; no `wdt_pci_1` estão invertidas (escritores 2 e fechadores 4, contra 4 e 2) |
| `violation.info` | | igual, **exceto `i8xx_tco_1`** (um `no` a mais no fim de uma linha) |
| compila com clang-14 | 12/18 | 17/18 |

A conclusão está em [[Contradictions]] #9. Qualquer comparação entre NIChecker e BMC4AV neste
benchmark pode estar comparando execuções sobre programas diferentes, com modelos de interrupção
diferentes. Nenhum dos dois artigos diz qual cópia usou. A disputa dos "57 falsos negativos"
(#1) fica com mais uma ressalva.

**Decisão (Pedro, 29/10):** analisar a cópia do NIChecker. É a distribuição original, a do
gabarito, e preserva a máscara de verdade em `main`. As prioridades do BMC4AV para os cinco
programas em disputa rodam como **segunda configuração**: não se escolhe um lado sem fonte.

### 3.3. Vendorização sem tocar em nenhum arquivo

`project-src/bench/realworld/` recebeu só as entradas de cada programa (`main.c`, `priority.info`,
`violation.info`) e a licença Apache-2.0, extraídas por `git show` do commit `40267c0` do
NIChecker. O resto dos diretórios de lá são saídas da ferramenta deles. Foi um commit só com isso
(`8afcf8b`), com a procedência em `VENDORED.md`.

Seis programas não compilam como vêm. No Racebench a correção do caso 006 foi um *patch* no
fonte. Aqui deu para evitar isso: todas as correções entram como flags no C1, e os arquivos ficam
idênticos aos do upstream.

`project-src/bench/realworld-errata.yaml`
```yaml
build_defines:
  # Linux errno and stddef values the extraction dropped with its #includes
  # (all commented out at the top of each file). Values are Linux's.
  i8xx_tco_1: &errno [EINVAL=22]
  i8xx_tco_2: &errno_null [EINVAL=22, "NULL=((void*)0)"]
  i8xx_tco_3: *errno_null
  wdt_pci_1: &wdt [ "NULL=((void*)0)", wdt_ctr_port=0, wdtpci_lock0=wdtpci_lock ]
  wdt_pci_2: [wdt_ctr_port=0, wdtpci_lock0=wdtpci_lock]
  wdt_pci_3: *wdt

build_flags:
  wdt_pci_3: [-Wno-error=return-type]
```

`wdtpci_lock0=wdtpci_lock` corrige um erro de digitação: o bloco faz `spin_lock(wdtpci_lock)` e
depois `spin_unlock(wdtpci_lock0)`. A cópia do BMC4AV fez a mesma correção no fonte.
`-Wno-error=return-type` existe porque as oito ISRs do `wdt_pci_3` são `void` e terminam em
`return NULL;`, o que o clang 14 recusa. Esse problema só apareceu no primeiro build, porque no
levantamento os 20 erros de `NULL` do mesmo arquivo esgotavam o limite de erros do clang antes de
chegar nele. Por um momento contei "sete programas quebrados"; são seis, e o `wdt_pci_3` tem dois
problemas.

### 3.4. O gerador de C1, e o nome que não bate

O `priority.info` diz `task_measure:2`, mas a função se chama `task_measure_isr`, e `main` não
aparece. Esse é o mesmo tipo de armadilha que o README do Racebench tinha nos casos 028 e 030. Um
nome de entrada errado faz o fluxo inteiro contribuir **zero acessos, sem erro nenhum**, e todo
defeito que passa por ele desaparece ([[Soundness Assumptions]] B1). O gerador acrescenta `_isr`
e põe `main` como tarefa de prioridade 0:

`project-src/src/irqrace/realworld.py`
```python
    flows: list[dict[str, Any]] = [
        {"id": "main", "kind": "task", "entry": "main", "irq": None, "priority": 0,
         "identified_by": "config"},
    ]
    for irq, (flow, prio) in enumerate(prios, start=1):
        flows.append({"id": flow, "kind": "isr", "entry": f"{flow}_isr", "irq": irq,
                      "priority": prio, "identified_by": "config"})
```

Dois detalhes do modelo. Os números de IRQ são atribuídos em ordem (1..n) e **não decidem
nada**, porque todas as 15 chamadas de máscara do benchmark usam `-1` ("todas as interrupções").
E o estado inicial da máscara é `unknown`, não o `all-enabled` do Racebench: aqui nenhuma
`init()` habilita as interrupções antes de tudo, e sem evidência o seguro é `unknown`
([[Soundness Assumptions]] F5). Um teste confere que toda entrada gerada existe no fonte
(`test_entry_names_exist_in_the_source`), e o *probe* (verificação R7) confirmou o mesmo nos
23 builds.

### 3.5. Os dialetos do gabarito

O `violation.info` tem quatro formas, e mais uma que não deve ser lida:

```
true violation int numberOfRecords rww          por variável
true violation: int test_global_var1 rwr        com dois-pontos
true violation int test_global_array[9000] wwr  com índice (o objeto é o array inteiro)
true violation timerCount(95W,121W,96R)         por instância, com linhas e tipo de acesso
true violation timerCount(93R,123/136W,93W)     instância com linhas alternativas para B
int test_global_var1 rwr                        sem rótulo (logger2) — não é entrada
```

As linhas do `logger2` não têm rótulo e citam variáveis (`test_global_var1..3`) que **não existem
no programa**. O parser as lê como zero entradas e anota o motivo. O leitor tolerante reproduz a
contagem que o wiki tinha feito à mão em agosto: **45 violações e 14 falsos alarmes**. Um teste fixa
essa contagem.

O casamento respeita a granularidade de cada entrada:

`project-src/src/irqrace/realworld.py`
```python
def _matches(entry: Entry, c: dict[str, Any]) -> bool:
    if c.get("variable", {}).get("name") != entry.variable or c.get("pattern") != entry.pattern:
        return False
    if not entry.is_instance:
        return True
    for want, got in zip(entry.accesses, c["accesses"]):
        if got["source"]["line"] not in want.lines or got["kind"] != want.kind:
            return False
    return True
```

### 3.6. O *recall gate* pegou o gabarito, não a ferramenta

A primeira execução do stage 1 deu **40/45**. As cinco faltas estavam todas nas entradas por
instância do `blink2` (4) e do `blink3` (1). O stage 1 tinha gerado candidatos em todas as formas
sobre `timerCount`, então a falha estava no gabarito.

O `blink2` é o `blink1` com uma ISR a mais (`Timer_C`, linhas 117–125) inserida no meio, e as
linhas do gabarito foram copiadas do `blink1` **sem o deslocamento**. A evidência mais clara: a
anotação diz que B é `121W`, uma escrita na linha 121. No `blink2`, a linha 121 é
`if (timerCount == 0)`, uma leitura. A escrita que corresponde à do `blink1` (`Timer_Force`) está
na 132, e o falso alarme do mesmo arquivo já usa 132. No `blink3`, a linha `93` citada não tem
acesso algum a `timerCount`.

As correções seguem a política da errata do Racebench: mudam **só linhas**, nunca rótulo nem
contagem. Cada uma traz a citação exata do arquivo (o parser recusa uma errata que cite mal), a
evidência e confiança `likely`. Quando o original não diz qual escrita era, B recebe as duas
alternativas (`119/132W`). Uma das correções é mais fraca e ficou marcada como tal: a primeira
entrada do `blink2` diz A₁ = A₂ = `93R`, o que não pode ser dois acessos numa ISR sem laço. A
reconstrução como `95R` é a parte mais frágil do arquivo. Com a errata, os `blink` passam 11/11.
Sem ela, `irqrace realworld run --raw` mostra o gabarito como veio.

### 3.7. O solver e o tempo

Rodando em sequência, o `brake2` (623 linhas) levou **444 s** só no stage 3: 44 dos 56 candidatos
estouraram os 10 s do Z3 e ficaram `inconclusive`, o que é correto, porque seguem adiante. No
Racebench o stage 3 inteiro, nos 31 casos, levou 17,6 s. Os *drivers* maiores chegam a 350
candidatos no stage 1, e em sequência a bateria levaria horas.

A saída foi rodar programas em paralelo. Cada configuração é independente e o Z3 usa uma thread
só. `irqrace realworld run -j 3` usa um *pool* de processos e imprime os resultados na ordem dos
arquivos, como antes.

### 3.8. Resultados

**Primeira execução** (29/10, stages 1→3, `-j 3`, 14 min de relógio), com as prioridades
**como vieram** no `priority.info` do NIChecker e a errata de linhas aplicada:

```
[ok ] blink1                       19 ->   12 ->   12 (sat 12, inc 0, unsat 0)     bugs 3/3
[ok ] brake2                       59 ->   56 ->   56 (sat 12, inc 44, unsat 0)    bugs 2/2
[ok ] brake3                      128 ->  128 ->  125 (sat 76, inc 49, unsat 3)    bugs 2/2
[ok ] i8xx_tco_3                  338 ->  177 ->  153 (sat 153, inc 0, unsat 24)  bugs 3/3
[MISS] logger3                      22 ->   10 ->   10 (sat 10, inc 0, unsat 0)    bugs 1/2
        MISSED true violation int tickCounter wwr
[MISS] wdt_pci_1                    79 ->   38 ->   38 (sat 36, inc 2, unsat 0)    bugs 0/2
[MISS] wdt_pci_2                   193 ->  107 ->  107 (sat 107, inc 0, unsat 0)  bugs 0/2
[ok ] wdt_pci_3                   349 ->  184 ->  175 (sat 175, inc 0, unsat 9)   bugs 4/4
...
funnel: stage1 1980 -> stage2 1005 -> context 941
stage 2 drops: no-path 438, priority 537
traps reported: stage1 12/14 -> stage2 9/14 -> context 7/14
RECALL GATE (context): 40/45 ground-truth violations present -- FAIL
```

| | |
| --- | --- |
| Funil (18 programas) | 1980 → 1005 → **941** chegando à LLM, 52,3 por programa |
| Stage 2 | 975 descartes com prova: 537 por prioridade, 438 *no-path* |
| Solver | 1005 → 842 `sat`, 99 `inconclusive` (94 em `brake2`/`brake3`), 64 `unsat` (6,4%) |
| *Recall gate*, prioridades do NIChecker | **40/45**: as 5 faltas estão em `logger3`, `wdt_pci_1` e `wdt_pci_2` |
| *Recall gate*, prioridades do BMC4AV nos 5 programas em disputa | **45/45** |
| Falsos alarmes que chegam à LLM | 7/14 |

**As cinco faltas não são da ferramenta.** Todas caíram no stage 2, por prioridade, e a prova
de cada descarte é correta *em relação ao modelo que recebeu*. No `wdt_pci_1`, a violação
`test_global_var1 rwr` exige que o `writer1` interrompa o `closer1` entre as linhas 989 e 990. O
`priority.info` do NIChecker dá ao `writer1` prioridade 2 e ao `closer1` prioridade 4, e o próprio
artigo do NIChecker diz que número maior é prioridade maior (`p0 < p1 ≤ … ≤ pn`, e "ISR₂ can
preempt ISR₁ because p(ISR₁) < p(ISR₂)"). **Pelo próprio modelo do NIChecker, a violação que o
gabarito do NIChecker anota é impossível.** O mesmo vale para `logger3` (a `task_measure2`, com
prioridade 6, não pode ser interrompida por ninguém) e para `wdt_pci_2`.

Duas verificações separam as hipóteses:

1. **A convenção está invertida no arquivo inteiro?** Os 18 programas foram rodados com as
   prioridades do NIChecker espelhadas (p′ = max + min − p). O *gate* cai para **18/45**. Não é uma
   inversão global.
2. **As prioridades do BMC4AV são consistentes com o gabarito?** Nos cinco programas em que as
   cópias discordam, sim: **9/9**. Nos três que falham com as do NIChecker, a cópia do BMC4AV tem
   exatamente as prioridades que tornam as violações anotadas alcançáveis.

A leitura mais simples: o BMC4AV corrigiu prioridades erradas em cinco arquivos e não disse. Se
foi isso, a [[Contradictions|disputa]] dos "57 falsos negativos" compara o NIChecker rodando sobre
arquivos com erro e o BMC4AV rodando sobre arquivos corrigidos. É uma hipótese; nenhum dos artigos
diz qual cópia usou.

**Decisão (Pedro, 30/10): adotar as prioridades do BMC4AV para que o resultado seja 45/45.** Elas
entram como `priority_corrections` na errata, só nos três programas em que há evidência
(`logger3`, `wdt_pci_1`, `wdt_pci_2`), com a mesma forma das outras correções: a citação, a
evidência e a confiança `likely`. Em `logger2` e `i8xx_tco_1` as prioridades do NIChecker não
contradizem nada, e as do BMC4AV continuam como configuração lateral. O arquivo vendorizado não
muda; `irqrace realworld gen-configs --raw` gera os C1 com as prioridades como vieram.

**Execução oficial** (30/10, 14:43–15:00 UTC, 16 min de relógio, `-j 3`), com as duas erratas:

| | |
| --- | --- |
| Funil (18 programas) | 1980 → 1037 → **972** chegando à LLM, 54 por programa |
| Stage 2 | 943 descartes com prova: 505 por prioridade, 438 *no-path* |
| Solver | 1037 → 846 `sat`, 126 `inconclusive`, 65 `unsat` (6,3%) |
| ***Recall gate*** | **45/45 — PASS** |
| Falsos alarmes que chegam à LLM | 9/14 |

**Os números do solver não são reprodutíveis entre execuções.** O `brake3`, com o mesmo C1, deu
3 `unsat` e 49 `inconclusive` em 29/10 e 0 e 73 em 30/10. O *timeout* de 10 s é de relógio, e na
segunda execução a máquina rodava outro teste ao mesmo tempo. O *recall* não muda com isso,
porque `inconclusive` segue adiante. Mudam o número de candidatos que chegam à LLM e, portanto, o
custo. Um *timeout* contado em passos do solver, e não em segundos, tornaria o número
determinístico.

O ponto para a tese: **o *recall gate* funcionou como deve.** Ele não aceitou "40/45, as faltas são
do benchmark" sem uma prova. A prova é que o descarte é correto em relação ao modelo de interrupção
e que o modelo contradiz o gabarito. É o mesmo argumento do *relabel* do Racebench de 28/10, com o
sinal invertido: lá o gabarito errava ao chamar de falso alarme algo alcançável; aqui o modelo erra
ao tornar inalcançável algo que o gabarito chama de violação.

### 3.9. A parte estática filtra pouco?

A pergunta do Pedro em 30/10: chegam 972 candidatos onde o gabarito tem 45. Num repositório
inteiro, a LLM não ficaria cara demais?

**Primeiro, 972 contra 45 compara unidades diferentes.** O gabarito conta pares (variável,
padrão). Os candidatos são instâncias: cada combinação de linhas A₁, B, A₂. Na mesma execução
oficial:

| Agrupamento dos 972 | Grupos |
| --- | --- |
| nenhum (uma trinca por chamada) | 972 |
| (variável, fluxo de A, fluxo de B, padrão) | 440 |
| **(variável, linha de A₁, linha de A₂, padrão)**: um intervalo, vários B | **280** |
| (variável, padrão), a granularidade do gabarito | 119 |
| variáveis distintas | 75 |

Na granularidade do gabarito, a ferramenta reporta 119 pares, dos quais 45 são violações
anotadas e 9 são falsos alarmes anotados. Os outros 65 estão em variáveis que o gabarito **não
anota**: `expect_close` no `wdt_pci_3` (132 trincas), `tco_expect_close`, os estados do
controlador do `brake`. O gabarito do NIChecker anota sobretudo violações **plantadas**
(`test_global_var*`), e o BMC4AV encontra 94 instâncias contra as 45 anotadas
([[Contradictions]] #1). Parte desses 65 é provavelmente real. Sem um gabarito exaustivo, a
precisão não pode ser calculada aqui.

**Segundo, o volume vem de multiplicação, não de variáveis.** Uma variável muito acessada gera
o produto dos seus acessos. Só `expect_close` no `wdt_pci_3` responde por 132 das 175 trincas do
programa.

**Terceiro, o filtro que parecia legítimo perde bugs.** O artigo do NIChecker diz que ISRs de
mesma prioridade não se interrompem. Desligar `equal_priority_preemption` derruba o stage 2 de
1005 para 561 (−44%), mas o *gate* cai para **43/45**: as duas violações do `i8xx_tco_1` exigem
que `closer1` e `closer2`, ambos com prioridade 4, se interrompam. O próprio gabarito contradiz a
semântica que o artigo declara. O padrão conservador fica.

**Quarto, o filtro que sobra é o solver, e ele é fraco aqui.** Ele refuta 6,3%, contra os 86,2%
que o IntRace relata para a sua etapa de viabilidade. A codificação *thread-modular* torna
arbitrário (*havoc*) tudo o que outro fluxo escreve. É seguro, mas raramente prova
impossibilidade; é o mesmo limite medido no Racebench (17,8%).

**O que isso significa para o custo.** O estágio LLM **não é um componente de recall**: ele ordena
e classifica, mas nunca descarta ([[Soundness Assumptions]] H3). Então o custo dele pode ser
limitado sem tocar no *recall*, de duas formas:

1. **Triar por grupo, não por trinca.** Uma chamada por intervalo (variável, A₁, A₂, padrão), com
   todos os B listados, cobre a mesma pergunta ("esse intervalo pode ser interrompido por uma
   escrita nessa variável?"): são 280 chamadas em vez de 972 (−71%). O veredito vale para o grupo
   para fins de ordenação, e o relatório continua listando todas as trincas.
2. **Orçamento.** O que não couber no orçamento fica `not_triaged`, no grupo "incerto", e aparece
   no relatório. Nada some.

Ordem de grandeza, a partir do que já foi medido: a triagem do rastro-robot levou 325 s para 10
candidatos (`claude-cli:sonnet`, linha `+self-validation`, 4 turnos cada, ~15 mil *tokens* por
candidato pelo tamanho do texto). Isso dá 32,5 s por candidato: as 972 trincas levariam ~9 h em
sequência, e os 280 grupos ~2,5 h. Em custo de API, a medição de 26/09 (linha base, Opus 5) foi
~US$ 0,035 por candidato, ou ~US$ 34 para 972 trincas e ~US$ 10 para 280 grupos. A linha
`+self-validation` custa várias vezes isso. São estimativas a partir de medições anteriores; esta
bateria ainda não foi triada.

### 3.10. Uma variável global em dois arquivos

A outra pergunta do Pedro: se uma global é compartilhada entre dois arquivos, com a tarefa em um
e a ISR no outro, o irqrace detecta? E as trincas, que aparecem só como números de linha?

Um programa mínimo de dois arquivos: `pending` é definida em `task.c`, onde `consume()` lê
(linha 8) e zera (linha 11); `isr.c` declara `extern volatile int pending` e faz `pending++` na
linha 5. C1 com `build.mode: link` e os dois arquivos em `sources`.

**Detecta.** Os dois arquivos viram *bitcode* separadamente e o `llvm-link` os une num só módulo,
onde a `pending` declarada `extern` em `isr.c` passa a ser o mesmo objeto global. O SVF vê um
objeto só, alcançado pelos dois fluxos. Saem 4 candidatos, todos `sat`, entre eles o bug:

```
xfile: 5 -> stage 2 4 -> solver: 4 sat, 0 inconclusive, 0 unsat -> 4 reach the LLM
  - cad9a9700e096f1bc RWW [8, 5, 11] sat
```

**O arquivo não se perde no dado; ele se perde em algumas saídas.** O registro de contexto tem
o arquivo de cada acesso:

```
A1 main  read  {'file': 'task.c', 'line': 8,  'snippet': 'int n = pending; ...'}
B  timer write {'file': 'isr.c',  'line': 5,  'snippet': 'pending++; ...'}
A2 main  write {'file': 'task.c', 'line': 11, 'snippet': 'pending = 0; ...'}
variable decl: task.c:3
enclosing_source: task.c consume, isr.c timer_isr, task.c main
```

O *fingerprint* (e, portanto, o id do candidato) inclui o arquivo de cada acesso, e a LLM recebe
o registro inteiro, com cada corpo de função marcado `location="isr.c:3-6"`. Uma varredura no
código procurou quem usa só a linha:

| Onde | Usa | Consequência num programa de vários arquivos |
| --- | --- | --- |
| `irqrace stage3 -v` (`cli.py`) | só linhas, `[8, 5, 11]` | ambíguo na tela; o dado está certo |
| registro de descarte do stage 2 (`stage2/dropped.jsonl`, contrato C3) | `"lines": [8, 5, 11]`, sem arquivo — **o próprio schema só tem linhas** | quem audita "nada sumiu sem prova" não sabe em que arquivo está cada linha |
| casamento com o gabarito (`evaluation.py`, `realworld.py`) | só linhas | correto nos benchmarks de um arquivo; ambíguo quando houver gabarito de vários |
| UI Streamlit, passo 1 (`ui/app.py`) | mostra só `sources[0]` e destaca nele as linhas de todos os acessos | **destaca a linha errada**: o B de `isr.c:5` aparece na linha 5 de `task.c` |
| verificação de compilação do reparo (`llm/repair.py`) | aplica o *patch* e compila só o arquivo do A₁, sozinho | uma correção na ISR, ou que dependa do outro arquivo, não é verificada direito |

Nenhum desses problemas afeta a detecção nem o *recall*. Os dois primeiros são de exibição e de
auditoria; o da UI mostra algo errado; o do reparo verifica a coisa errada. Os benchmarks (um
`main.c` só) nunca os exercitaram, e o firmware do robô os exercitaria: ele tem 13 arquivos.

## 4. Achados e decisões

- **O benchmark existe em duas versões que não são o mesmo programa** ([[Contradictions]] #9).
  O wiki dizia o contrário e foi corrigido.
- **O gabarito tem erros de linha** em `blink2` e `blink3`, corrigidos por errata com evidência,
  e um arquivo inutilizável (`logger2`).
- **Decisão:** cópia do NIChecker, vendorizada, sem edição de fonte. As prioridades do BMC4AV
  rodam como segunda configuração.
- **O *recall* aqui é mais fraco por construção:** 31 das 45 entradas casam por variável e
  padrão, sem linha.
- **O `priority.info` do NIChecker contradiz o próprio gabarito em três programas** (§3.8). O
  descarte do stage 2 é correto; o modelo de entrada é que está errado. **Decisão (30/10):**
  prioridades do BMC4AV como errata nesses três; *gate* oficial **45/45**.
- **972 candidatos contra 45 entradas é instância contra variável** (§3.9): 119 pares (variável,
  padrão), 280 intervalos. O custo da LLM se controla por agrupamento e orçamento, sem tocar no
  *recall*. Desligar a preempção entre prioridades iguais perderia 2 bugs.
- **Globais entre arquivos são detectadas** (§3.10); o arquivo está no registro, mas cinco
  consumidores usam só a linha, e dois deles (a UI e a verificação do reparo) fazem a coisa
  errada.
- **O resultado do solver depende da carga da máquina** (§3.8): *timeout* em segundos.
- **O custo do stage 3 cresce mais que o tamanho do programa.** Isso empurra a escolha do
  *timeout* para uma questão de recurso; não é questão de recall, porque `inconclusive` nunca
  descarta.

## 5. Como reproduzir

A partir de `project-src/`, com `source scripts/env.sh`:

```bash
.venv/bin/irqrace realworld gen-configs
```

```bash
.venv/bin/irqrace bench build-all --configs bench/configs-realworld --probe
```

```bash
.venv/bin/irqrace realworld run --through stage1
```

```bash
.venv/bin/irqrace realworld run --through stage3 -j 3
```

```bash
.venv/bin/irqrace realworld run --through stage1 --raw
```

```bash
.venv/bin/irqrace realworld gen-configs --raw --out /tmp/configs-as-shipped
```

```bash
.venv/bin/python -m pytest tests/test_realworld.py -q
```

## 6. Estado ao fim da semana

*Parcial; atualizado conforme a semana avança.* Pronto: vendorização, errata, gerador, gabarito,
*recall gate* por entrada, execução paralela, 12 testes e a primeira execução completa: 941
candidatos chegam à LLM, *gate* 40/45 com as prioridades do NIChecker e 45/45 com as do BMC4AV nos
programas em disputa; com as prioridades corrigidas, a execução oficial dá **45/45**. Falta:

- a triagem por grupo (§3.9, issue #9) e os consumidores que usam só a linha (§3.10, #8);
- um *timeout* determinístico no solver (#10);
- a triagem LLM nos 18 programas (Trilha B, W9; #11), que depende de #9, #10 ou #16;
- a interface: nomes `obj_N` (#12), agrupar por variável (#13), ordenação (#14), layout estilo
  VS Code com status nas abas (#15), triagem paralela e mesclada com o reparo (#16), quebra de
  linha no reparo (#17);
- o suporte a re-verificação (CBMC/`bmc4av` nos inconclusivos);
- decidir se o *timeout* do Z3 muda para este benchmark;
- o Pedro conferir à mão as correções do `blink2`, em especial a reconstrução da primeira entrada.

Página anterior: [[Semana 8 — Integração das Trilhas A e B]].
