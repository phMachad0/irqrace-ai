# Monografia do TCC

Fonte LaTeX da monografia parcial e da completa. A estrutura e a formatação
seguem o modelo do departamento, `TCC_PCS_EPUSP_2023` (abntex2 ajustado para o
PCS-EPUSP), com os seis capítulos que ele propõe. Os capítulos são
compartilhados pelas duas versões: `parcial.tex` e `final.tex` diferem apenas
na chave `\ifparcial`, que libera os trechos de resultados na versão completa.

## Compilar

Compila com **pdfLaTeX**, como o modelo. Num terminal, dentro desta pasta:

```bash
make parcial
```

```bash
make final
```

`make watch` recompila a parcial a cada alteração salva e `make limpar` apaga os
intermediários. Os PDFs saem em `build/`.

No Ubuntu ou WSL, o que precisa estar instalado:

```bash
sudo apt install texlive-latex-extra texlive-publishers texlive-lang-portuguese texlive-fonts-recommended texlive-pictures latexmk make
```

`abntex2` vem no pacote `texlive-publishers`. No MiKTeX, os pacotes que faltarem
são baixados na primeira compilação.

## Estrutura

| Caminho | Conteúdo |
| --- | --- |
| `config/preambulo.tex` | pacotes e macros, espelhando o preâmbulo do modelo |
| `config/dados.tex` | título, autores, orientador e instituição |
| `pre-textuais/` | resumo, abstract, listas, siglas e sumário |
| `capitulos/` | um arquivo por capítulo, na ordem do modelo |
| `figuras/` | imagens |
| `referencias.bib` | bibliografia |

## Ficha catalográfica

A folha de rosto sai sem ficha nesta versão. Para a entrega final, gere a ficha
em <https://www.poli.usp.br/bibliotecas/servicos/catalogacao-na-publicacao>,
salve como `ficha.pdf` nesta pasta e troque o `\imprimirfolhaderosto` pelo bloco
comentado logo abaixo dele.

## Marcadores de pendência

`\pendente{...}` marca o que ainda falta escrever. Fica invisível por padrão;
para enxergar os marcadores em vermelho, troque `\mostrarpendentesfalse` por
`\mostrarpendentestrue` em `config/preambulo.tex`.
