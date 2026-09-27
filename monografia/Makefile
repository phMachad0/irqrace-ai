.PHONY: parcial final watch limpar

parcial:
	latexmk parcial.tex

final:
	latexmk final.tex

# recompila a cada alteração salva
watch:
	latexmk -pvc -view=none parcial.tex

limpar:
	latexmk -C parcial.tex final.tex
	rm -rf build
