"""Todo caminho de arquivo do repositório citado na documentação **vigente**
existe, e nenhum documento vigente cita os pacotes removidos na migração v2.

Este teste é o par de `test_docs_citados.py`: aquele guarda o sentido
código → documentação (docstring não cita documento descartado); este guarda
o sentido documentação → código (ADR, visão geral, débito e checklist não
apontam para arquivo que não existe mais).

Por que existe: os 19 ADRs foram escritos antes de `tests/` ser reorganizado, e
em poucos dias toda a seção **Evidência** — justamente a âncora que dá
rastreabilidade decisão → código → teste — passou a apontar para arquivos
renomeados. Documento normativo que aponta para o vazio é o mesmo defeito do
`README.md` da v1, que motivou a reorganização inteira. A verificação é
estática: lê Markdown, não importa nem executa nada.

Escopo (fora de `arquivo/`, tudo é vigente):
- varre `docs/**.md` exceto `docs/arquivo/` e `docs/planos/`, mais `CLAUDE.md`,
  `README.md` e `tests/README.md`;
- `docs/arquivo/` é consulta histórica e `docs/planos/` tem vida curta, por
  definição descrevendo um estado que ainda não existe — nenhum dos dois é
  fonte de instrução, logo não se cobra deles caminho vivo.

Duas válvulas, ambas declaradas:
- `ISENTOS` — arquivo inteiro cuja natureza é narrar o passado ou transcrever
  fonte alheia. Está vazio; documento novo não entra aqui.
- Os marcadores `<!-- caminhos-historicos -->` … `<!-- /caminhos-historicos -->`
  isentam um TRECHO de um documento vigente: a tabela de equivalência v1 → v2
  da `VISAO_GERAL.md`, o registro datado de execuções do checklist, os três
  documentos de módulo escritos antes da v2 (que trazem nota de leitura
  apontando para a tabela de equivalência) e a citação literal do
  texto defasado que a tela ainda mostra.
"""

from __future__ import annotations

import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASTAS_DO_REPO = ("core", "app", "tests", "scripts", "config", "web", "artefatos",
                  "entradas", "docs")
EXTENSOES = ("py", "md", "csv", "json", "yaml", "yml", "xlsx", "ids", "html", "js",
             "toml", "png", "txt")

PADRAO_CAMINHO = re.compile(
    r"(?:" + "|".join(PASTAS_DO_REPO) + r")/[A-Za-z0-9_./-]+\.(?:" + "|".join(EXTENSOES) + r")\b"
)

# Pacotes de `core/` removidos na v2. Um documento vigente que
# os cite fora de trecho marcado está descrevendo um repositório que não existe.
PACOTES_REMOVIDOS = ("core/ingestao/", "core/georref/", "core/motor/", "core/saida/",
                     "core/territorio/", "core/roteamento/", "core/conhecimento/",
                     "core/pipeline.py", "core/caminhos.py")

PASTAS_NAO_VIGENTES = (os.path.join("docs", "arquivo"), os.path.join("docs", "planos"))

# Arquivos vigentes cuja NATUREZA é citar o passado; ver docstring.
ISENTOS = {}

ABRE = "<!-- caminhos-historicos -->"
FECHA = "<!-- /caminhos-historicos -->"


def _sem_trechos_historicos(texto: str) -> str:
    """Remove os trechos marcados como históricos, preservando as quebras de
    linha para que o número da linha continue fazendo sentido no relatório."""
    saida, resto = [], texto
    while ABRE in resto:
        antes, _, depois = resto.partition(ABRE)
        saida.append(antes)
        dentro, marcador, resto = depois.partition(FECHA)
        assert marcador, f"{ABRE} sem {FECHA} correspondente"
        saida.append("\n" * dentro.count("\n"))
    saida.append(resto)
    return "".join(saida)


def _documentos_vigentes():
    for pasta_base in ("docs",):
        for raiz_atual, _dirs, arquivos in os.walk(os.path.join(RAIZ, pasta_base)):
            relativo = os.path.relpath(raiz_atual, RAIZ)
            if relativo.startswith(PASTAS_NAO_VIGENTES):
                continue
            for nome in sorted(arquivos):
                if nome.endswith(".md"):
                    yield os.path.relpath(os.path.join(raiz_atual, nome), RAIZ).replace(os.sep, "/")
    for avulso in ("CLAUDE.md", "README.md", "tests/README.md"):
        if os.path.isfile(os.path.join(RAIZ, avulso)):
            yield avulso


def _citacoes():
    """(documento, linha, caminho citado), já fora dos trechos históricos."""
    for doc in _documentos_vigentes():
        if doc in ISENTOS:
            continue
        with open(os.path.join(RAIZ, doc), encoding="utf-8") as arq:
            texto = _sem_trechos_historicos(arq.read())
        for numero, linha in enumerate(texto.splitlines(), start=1):
            for achado in PADRAO_CAMINHO.findall(linha):
                yield doc, numero, achado


def test_todo_caminho_citado_em_documento_vigente_existe():
    faltando = [
        f"{doc}:{linha}: caminho citado não existe: {achado}"
        for doc, linha, achado in _citacoes()
        if not os.path.isfile(os.path.join(RAIZ, achado))
    ]
    assert not faltando, (
        "\nDocumento vigente apontando para arquivo inexistente. Corrija o caminho, "
        "ou envolva o trecho em " + ABRE + " … " + FECHA + " se a citação for "
        "deliberadamente histórica.\n" + "\n".join(faltando)
    )


def test_nenhum_documento_vigente_cita_pacote_removido_na_v2():
    proibidos = [
        f"{doc}:{linha}: cita pacote removido na v2: {achado}"
        for doc, linha, achado in _citacoes()
        if achado.startswith(PACOTES_REMOVIDOS)
    ]
    assert not proibidos, (
        "\nA árvore da v1 não existe mais; a tradução está na tabela "
        "'Equivalência com a árvore da v1' de docs/arquitetura/VISAO_GERAL.md §2.\n"
        + "\n".join(proibidos)
    )


def test_isencoes_declaradas_continuam_existindo():
    """Isenção de arquivo que já não existe é isenção esquecida: ou o documento
    voltou com outro nome (e deixou de ser verificado sem ninguém notar), ou a
    lista virou entulho."""
    sumidos = [doc for doc in ISENTOS if not os.path.isfile(os.path.join(RAIZ, doc))]
    assert not sumidos, f"ISENTOS aponta para documento inexistente: {sumidos}"
