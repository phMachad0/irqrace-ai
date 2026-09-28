.PHONY: parcial final relato watch limpar

parcial:
	latexmk parcial.tex

final:
	latexmk final.tex

relato:
	latexmk relato.tex

# recompila a cada alteração salva
watch:
	latexmk -pvc -view=none parcial.tex

limpar:
	latexmk -C parcial.tex final.tex relato.tex
	rm -rf build
