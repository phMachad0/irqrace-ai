---
type: project
tags: [wiki, project, diario, pt-br]
sources: ["[[Roadmap]]", "[[Racebench]]", "[[Precision Metrics]]", "[[Soundness and False Negatives]]"]
updated: 2026-09-18
status: draft
---

# Semana 2 — Ground Truth e Protocolo de Avaliação

**Período:** 7–11 set 2026 · **Trilha A** · Corresponde a [[Roadmap]] W2.
Página anterior: [[Semana 1 — Contratos e Toolchain]].

Esta semana vem **antes de qualquer análise**, de propósito. Tudo que vier depois vai ser medido
contra o que se decidir aqui; se o denominador estiver errado, todo número do TCC está errado
junto.

## 1. O que a semana tinha que entregar

| Item do Roadmap | Situação |
| --- | --- |
| Parser tolerante das anotações do `2.1_remarks` | feito |
| Contar cinco casos à mão para certificar o parser | feito — 12 bugs / 9 traps, confere |
| Fixar e documentar a **unidade de contagem** | **por instância de trinca**, 48 / 38 |
| Fixar e documentar a **regra de casamento** | mesmo sujeito, mesma localização, mesmas linhas ordenadas |
| Escrever a **lista de suposições de completude** | [[Soundness Assumptions]], 27 entradas |

Produto extra, que a certificação obrigou a criar: uma **errata curada** de 12 correções às
anotações do Racebench.

## 2. Conceitos desta semana

***Ground truth*** (verdade fundamental). O gabarito: a lista do que a suíte afirma serem os
defeitos reais e as armadilhas plantadas. Toda métrica é calculada contra ele.

***Bug point*** e ***trap***. O Racebench anota duas coisas dentro dos arquivos: `bug点` são os
defeitos reais (48 nos 31 casos simples) e `误报点` são **falsos positivos plantados de
propósito** (38) — trechos construídos para parecerem defeito e não serem. Uma ferramenta que
reporta uma *trap* não errou de leve: na competição original um falso positivo valia **−3** contra
**+2** de uma detecção.

**Recall (revocação).** Fração dos defeitos reais que a ferramenta encontra. É a métrica
principal deste projeto e tem que ser 100%.

**Precisão.** Fração do que a ferramenta reporta que é defeito real. Este projeto **troca
precisão por recall** de propósito.

***Inspection Ratio*** (razão de inspeção). Que fração da lista de candidatos uma pessoa precisa
ler, na ordem em que foram apresentados, até ter encontrado todos os defeitos reais. É a métrica
do lado da precisão que substitui a precisão em si, porque não dá para burlar descartando
candidatos ([[Precision Metrics]]).

**Unidade de contagem.** A resposta para "um defeito é o quê?". O corpus mistura contagens por
variável e por instância de trinca sem dizer qual usa — e todo `recall` divide por essa escolha.

**Regra de casamento (*match rule*).** Quando é que um candidato reportado **é** um dado *bug
point* anotado? Sem isso, "recall 100%" não é sequer uma afirmação computável.

**Errata.** Uma lista curada de correções ao gabarito, com a evidência de cada uma, aplicada
antes de medir.

## 3. O problema: as anotações não são legíveis por máquina

As anotações ficam em comentários no fim de cada arquivo:

```c
//bug点:
//1.svp_simple_019_001_global_var1<R#45>,<W#65>,<R#54>
```

Lê-se: a variável, seguida de três acessos, cada um com tipo (`R` leitura / `W` escrita) e
número de linha. O do meio é o acesso do fluxo que preempta.

O problema é que os 31 casos usam **quatro gramáticas incompatíveis**, vários formatos de
cabeçalho, um caso sem cabeçalho nenhum, e erros de digitação:

| Gramática | Exemplo | Onde |
| --- | --- | --- |
| tipo-depois-linha, sem espaços | `<R#45>,<W#65>,<R#54>` | maioria de 001–020 |
| acessos justapostos, sem vírgula | `<W#43><R#63><W#44>` | `svp_simple_001` |
| vírgula dentro dos colchetes | `<R,#44>, <W,#79>` | 021, 025, 029 |
| **linha-depois-tipo, campos invertidos** | `<#46,R> <#90,W>` | `svp_simple_031` |

Mais: colchete duplicado em 004 (`<<R#52>`), colchete de fechamento faltando em 016 (`<W#33,`),
`#` ausente em 027 (`<W, 41>`), e um `w` minúsculo em 013 (`<w#66>`) que o vault ainda não tinha
catalogado.

**Um parser estrito lê 28 *bug points* em vez de 48 — e não dá erro.** Ele só devolve um número
menor. Por isso o parser é deliberadamente tolerante **e registra toda tolerância que aplicou**,
para que a leitura seja auditável e não só permissiva.

## 4. O parser tolerante

Uma única expressão regular cobre as quatro gramáticas e as quatro anomalias:

```python
# project-src/src/irqrace/groundtruth.py
ACCESS = re.compile(
    r"""<+\s*
        (?:
            (?P<type_first>[RrWw])\s*,?\s*\#?\s*(?P<line_after>\d+)
          |
            \#?\s*(?P<line_first>\d+)\s*,\s*(?P<type_after>[RrWw])
        )
        \s*>*""",
    re.VERBOSE,
)
```

Lendo peça por peça:

- `<+` — um ou mais `<`, o que absorve o colchete duplicado de `svp_simple_004_001`;
- a primeira alternativa é **tipo primeiro**: letra, vírgula opcional, `#` opcional, dígitos —
  isso cobre `<R#45>`, `<R,#44>`, `<R, #25>` e `<W, 41>` de uma vez;
- a segunda alternativa é **linha primeiro**, para o `svp_simple_031_001`;
- `[RrWw]` aceita o `w` minúsculo de `svp_simple_013_001`;
- `>*` torna o colchete de fechamento **opcional**, para `<W#33,` do `svp_simple_016_001`.

Cada desvio vira um registro, não um silêncio:

```python
if letter.islower():
    notes.append(f"access {raw!r} uses a lowercase access type")
if raw.startswith("<<"):
    notes.append(f"access {raw!r} has a doubled opening bracket")
if not raw.rstrip().endswith(">"):
    notes.append(f"access {raw!r} is missing its closing bracket")
```

Resultado sobre a suíte: **48 bug points e 38 traps**, e 25 desvios tolerados, cada um listado.

### O caso sem cabeçalho

O `svp_simple_022_001` abre com quatro entradas numeradas e **nenhum cabeçalho**, e só depois vem
uma seção `可能误报` ("possível falso positivo"). A decisão foi lê-las como *bug points*:

```python
if section is None:
    # Ler uma lista sem cabeçalho como traps perderia quatro bug points;
    # lê-las como bug points é a escolha segura para recall e bate com a
    # ordenação do próprio arquivo, em que a seção de traps vem depois.
    section = "bug"
    gt.anomalies.append(Anomaly(case, lineno, "missing-section-header", ...))
```

Quatro dos 48 *bug points* da suíte dependem desse julgamento — por isso ele é um dos dois casos
marcados para conferência independente.

## 5. Conferência à mão

Cinco casos foram contados à mão, escolhidos por serem **adversariais, não representativos**:
entre eles exercitam todas as gramáticas e todos os defeitos conhecidos.

| Caso | Por que está aqui | À mão | Parser |
| --- | --- | --- | --- |
| `001` | acessos justapostos; dois-pontos de largura total | 1 bug, 2 traps | 1, 2 |
| `016` | colchete faltando; tipo contradiz a fonte; **sem seção de traps** | 3, 0 | 3, 0 |
| `019` | todos os números de linha errados | 1, 4 | 1, 4 |
| `022` | **lista de bugs sem cabeçalho** | 4, 3 | 4, 3 |
| `031` | campos invertidos em todas as entradas | 3, 0 | 3, 0 |
| | **total** | **12, 9** | **12, 9** |

A ressalva está escrita na própria página de conferência: a mesma pessoa escreveu o parser e a
contagem, então isso estabelece **concordância, não correção**. Por isso dois casos ficaram
marcados para o Pedro conferir de forma independente.

## 6. Dois achados sobre o gabarito

Cruzando cada acesso anotado com a linha que ele nomeia, apareceram duas classes de erro.

### (a) Oito tipos de acesso contradizem o código

O vault registrava um. São oito, em cinco casos. Exemplo em `svp_simple_002_001`, armadilha 3:

```
//3.svp_simple_002_001_global_array<R#33>,<W#44>,<R#35>
```

As linhas 33 e 35 são `global_array[TRIGGER] = 1;` — **escritas**. E o próprio arquivo, no seu
*bug point* 1, anota essas mesmas linhas como `<W#33>` e `<W#35>`. As entradas do anotador
contradizem umas às outras.

O verificador distingue três situações, porque a heurística ingênua tem falso positivo:

```python
# a linha faz as duas coisas: `for (x = 0; x < N; x++)` ou `x = x + 1`
if len(kinds) == 2:
    ... "access-type-ambiguous"      # registrado, não tratado como erro
elif a.kind not in kinds:
    ... "access-type-disagrees-with-source"
```

Vinte acessos caem no caso ambíguo. Isso vai importar na regra de casamento.

### (b) Todas as linhas do `svp_simple_019_001` estão deslocadas

A anotação diz que a `isr_1` escreve `global_var1` na linha 65. A linha 65 é `idlerun();`. A
escrita está na **71**.

```
                anotado   real
global_var1 (escrita)   65  ->  71    (+6)
global_var2 (escrita)   61  ->  67    (+6)
global_condition3       63  ->  69    (+6)
leituras em main        45  ->  45    (0)
                        49  ->  51    (+2)
                        53  ->  56    (+3)
                        54  ->  59    (+5)
```

O deslocamento é **reconstruível**, não arbitrário. Seis linhas explicam tudo: os dois blocos
guardados de `main` ganharam `{`, `enable_isr(1);` e `}`. Cada linha posterior desloca exatamente
pelo número de inserções acima dela — 2 para `reader4`, 3 para a linha em branco seguinte, 5 para
`reader5`, e 6 para tudo dentro da `isr_1`.

**A consequência é decisiva:** casamento por linha exata contra o texto publicado dá **zero** no
*bug point* desse caso, por mais bom que o analisador seja. Estaria medindo a tipografia da
suíte.

Há um resíduo honesto que **não** foi corrigido: `enable_isr(1)` dentro daqueles blocos é
semanticamente relevante — é o que torna as leituras nas linhas 51 e 59 preemptáveis apesar do
`disable_isr(1)` acima. Se as anotações são anteriores a essa edição, os **rótulos** bug/trap
podem estar tão desatualizados quanto as linhas. Corrigir um rótulo é *redecidir* o gabarito, e
não ler o que ele diz. Ficou registrado como questão aberta.

## 7. Decisão 1 — unidade de contagem: por instância de trinca

| Unidade | Bug points | Traps |
| --- | --- | --- |
| **por instância de trinca** | **48** | **38** |
| por (caso, variável) | 33 | 29 |
| por caso | 31 | 31 |

Escolhida a mais fina: é a mais difícil de inflar, é a que o [[BMC4AV (paper)]] usa nas tabelas
dele (então comparação entre artigos continua possível), e as mais grossas escondem estrutura —
`svp_simple_017_001` tem quatro *bug points* distintos numa única variável.

## 8. Decisão 2 — regra de casamento

> Um candidato **casa** com uma trinca anotada quando está no mesmo sujeito, trata da mesma
> posição de memória, e suas linhas de acesso ordenadas `(A₁, B, A₂)` são iguais às linhas
> corrigidas da anotação.

Três coisas que a regra **não** faz, cada uma justificada por medição e não por gosto.

**Não exige que os tipos de acesso batam.** Duas medições sustentam isso. A chave `(caso,
linhas)` já distingue **todas as 86 anotações, sem nenhuma colisão**, e nenhuma armadilha
compartilha trinca de linhas com um *bug point* — então exigir o tipo não acrescenta poder de
discriminação. E 20 acessos anotados nomeiam uma linha que lê *e* escreve; exigir igualdade de
tipo transformaria cada um num cara-ou-coroa sobre qual dos dois o detector escolheu reportar.

**Não exige que o nome da variável bata.** As anotações nomeiam a posição no nível do fonte, e às
vezes isso é um apelido: `*p`, `*u`, `*ptr_var`, `global_array[1]`, `global_union.header`. Não
são erros — é como aquela posição se chama ali — e resolvê-los é exatamente o trabalho da análise
`may-alias`. Doze anotações dependem disso.

```python
def normalise_variable(name: str) -> str:
    base = name.strip().lstrip("*&")
    for sep in ("[", ".", "->"):
        base = base.split(sep)[0]
    return base.strip()
```

**Não mede pares contra gabarito de trincas.** O gabarito do Racebench tem forma de trinca;
pontuar pares contra ele é a confusão de vocabulário que o vault aponta no [[IntRace (paper)]],
que reporta trincas sob nome de duas posições. Pares recebem um número próprio.

## 9. Decisão 3 — casar contra o gabarito corrigido

A errata vive em `project-src/bench/racebench-errata.yaml`: 12 correções, cada uma citando a
anotação como publicada, dando a trinca corrigida, declarando uma confiança (`certain` em onze,
`likely` em uma) e carregando sua evidência.

```yaml
- case: svp_simple_019_001
  kind: bug
  index: 1
  reason: line-drift
  confidence: certain
  as_written: "svp_simple_019_001_global_var1<R#45>,<W#65>,<R#54>"
  corrected: [[read, 45], [write, 71], [read, 59]]
  evidence: >
    global_var1 is written exactly once in isr_1, at line 71; line 65 is
    `idlerun();`. ...
```

**Nenhuma correção muda uma contagem**: 48 e 38 valem antes e depois. O que muda é a distribuição
de formatos, e as duas leituras são reportadas lado a lado.

Aplicar a errata é *fail-fast*: uma entrada que não casa mais **levanta erro**, em vez de ser
pulada — porque uma errata silenciosamente inaplicável significa que a suíte se moveu por baixo
de todo número medido contra ela.

```python
if target is None:
    raise ErrataError(
        f"errata names {corr.case} {corr.kind} {corr.index}, which the "
        "parser did not find; the suite or the parser has changed")
```

## 10. A lista de suposições de completude

[[Soundness Assumptions]] é a lista à qual a afirmação "sem falsos negativos" é **relativa**.
Zero falso negativo incondicional não é atingível para C com ponteiros e tabelas de vetores de
interrupção. O que é atingível, e defensável num TCC, é completude **relativa a uma abstração
declarada**.

Vinte e sete entradas em nove grupos. Cada uma dá a suposição, **como ela poderia esconder um
defeito**, e onde está implementada ou verificada. A terceira coluna não é ressalva: é a lista
que um leitor deve atacar.

Duas entradas merecem destaque:

- **E3 — re-entrância de ISR** é a única suposição da página que **não** é segura para recall, e
  isso é deliberado e registrado. O README do Racebench diz que uma interrupção pode disparar um
  número não especificado de vezes; o [[SDRacer (tool)]] exclui re-entrância e o
  [[NIChecker (tool)]] limita execuções, então o corpus também não concorda. Marcada para revisão
  antes de qualquer afirmação final de recall.
- **I3** — os rótulos do `svp_simple_019_001` podem estar velhos. É a entrada mais fraca da
  página, e está lá justamente por isso.

## 11. Como reproduzir

```bash
irqrace groundtruth certify
```

```bash
irqrace groundtruth parse --verbose
```

```bash
irqrace groundtruth errata --verbose
```

## 12. Estado ao fim da semana

190 testes. O arnês de avaliação roda de ponta a ponta contra as duas *fixtures* feitas à mão na
semana 1 — e a errata já se mostrou necessária ali: sem a correção de linha 63→64, a *fixture* da
armadilha do caso 001 não casaria com a própria anotação dela.

Continua em [[Semana 3 — O Front End do Stage 1]].
