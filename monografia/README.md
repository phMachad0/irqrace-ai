# Monografia do TCC

Fonte LaTeX (abntex2) da monografia parcial e da completa. Os capítulos são
compartilhados: `parcial.tex` inclui os capítulos 1–6, `final.tex` inclui 1–5
e 7–9.

## Compilar no Windows (MiKTeX)

Compila com **XeLaTeX** (configurado no `latexmkrc`), porque o texto usa a
fonte Arial instalada no sistema. Numa máquina sem Arial, o preâmbulo usa a TeX
Gyre Heros, de métrica equivalente. O MiKTeX desta máquina baixa sozinho os
pacotes que faltarem. Num terminal, dentro desta pasta:

```bash
latexmk parcial.tex    # gera build/parcial.pdf
latexmk final.tex      # gera build/final.pdf
```

## Compilar (WSL)

Uma vez, numa distribuição Ubuntu do WSL:

```bash
sudo apt update
sudo apt install texlive-xetex texlive-latex-extra texlive-publishers \
                 texlive-lang-portuguese texlive-fonts-extra latexmk make
sudo apt install ttf-mscorefonts-installer   # opcional: Arial de verdade
```

`abntex2` vem no pacote `texlive-publishers`.

Depois, dentro desta pasta:

```bash
cd /mnt/c/Users/luoma/Desktop/irqrace-ai/monografia
make parcial      # gera build/parcial.pdf
make final        # gera build/final.pdf
make watch        # recompila a cada alteração salva
```

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `config/` | preâmbulo (pacotes, macros) e dados da capa |
| `pre-textuais/` | resumo, abstract, listas e siglas |
| `capitulos/` | um arquivo por capítulo |
| `pos-textuais/` | apêndices |
| `figuras/` | imagens |
| `referencias.bib` | bibliografia; campos `VERIFICAR` ainda não conferidos |

## Marcadores de pendência

`\pendente{...}` aparece em vermelho no PDF. Para a entrega, troque
`\mostrarpendentestrue` por `\mostrarpendentesfalse` em
`config/preambulo.tex`.
