# docs/figuras/ — figuras geradas por código

Cada figura aqui é saída de um script em `scripts/`, e o mesmo script gera a
versão da página do protótipo (SVG) e a versão para impressão (PNG). Não se
edita o SVG nem o PNG à mão; muda-se o script e regenera-se. O PNG é gerado
e não é versionado.

| Arquivo | Gerado por | Onde é usado |
|---|---|---|
| `figura1_fluxo_idealizado.svg` | `scripts/gerar_figura1.py` | página "Fluxo Idealizado" do protótipo (`app/paginas/pesquisa/fluxo_idealizado.py`) |
| `figura1_fluxo_idealizado.png` | `scripts/gerar_figura1.py` | versão para impressão (300 dpi, 16 cm de largura) |
| `figura2_arquitetura.svg` | `scripts/gerar_figura2.py` | página "Desenvolvimento do protótipo" (`app/paginas/pesquisa/desenvolvimento_prototipo.py`) |
| `figura2_arquitetura.png` | `scripts/gerar_figura2.py` | versão para impressão (300 dpi, 16 cm de largura) |

Para regenerar, na raiz do repositório, com o extra de desenvolvimento
instalado (é ele que traz o matplotlib, fora das dependências do núcleo):

```
pip install -e ".[dev]"
python scripts/gerar_figura1.py
python scripts/gerar_figura2.py
```

O script é determinístico na mesma máquina e recusa gerar a figura se algum
texto transbordar da sua caixa. Na figura do fluxo idealizado, o IDS fica fora
da moldura do protótipo pelo ADR-007. A figura da arquitetura é a visão
estrutural em anéis, adaptada de Martin (2012), com o painel do caminho de uma
checagem; a ordem dos anéis é a que `tests/arquitetura/test_aneis.py` impõe
(ADR-002, ADR-037).
