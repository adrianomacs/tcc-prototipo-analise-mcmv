r"""ADR-002: "remover
fachadas com um teste que falha se algum import antigo sobreviver" — o
equivalente a `grep -r "core.territorio\|core.motor.contrato" .` vazio,
mas restrito a código (core/, app/, scripts/, tests/), não à prosa
histórica de docs/ (que registra decisões já tomadas, não código a rodar).

Por que este teste existe. A migração criou fachadas amortecedoras
(Strangler Fig) em `core/territorio`, `core/ingestao`, `core/georref`,
`core/roteamento`, `core/saida`, `core/conhecimento`, `core/motor` (exceto
`core/motor/regras`, que nunca teve fachada) e em dois
módulos avulsos, `core/pipeline.py` e `core/caminhos.py`, para que a
reorganização em anéis não quebrasse import nenhum enquanto durasse. A
remoção apaga essas fachadas; sem este teste, um import esquecido nesses
caminhos voltaria a funcionar hoje (o caminho antigo ainda existe até a
fachada ser removida) e só quebraria silenciosamente depois, na primeira
vez que alguém de fato apagar os arquivos. Por isso a lista inclui também os
dois módulos avulsos, `core/pipeline.py` e `core/caminhos.py`, que uma
varredura só dos pacotes não pegaria.

A segunda checagem (`test_nenhuma_docstring_de_fachada_sobrevive`) não
depende de uma lista de nomes: qualquer arquivo `.py` com a docstring
"Fachada (Strangler Fig" — a assinatura textual usada em toda fachada
criada na migração — reprova o teste. É a rede de segurança contra
esquecer um caminho que a lista abaixo não previu.
"""

from __future__ import annotations

import os
import re

from tests.conftest import RAIZ

PACOTES_REMOVIDOS = (
    "territorio", "ingestao", "georref", "roteamento", "saida",
    "conhecimento", "motor",
)
MODULOS_AVULSOS_REMOVIDOS = ("pipeline", "caminhos")

# `import core.motor…`, `from core.motor import …`, `from core.motor.X import …`
# — qualquer um dos sete pacotes removidos como primeiro componente após
# `core.`, OU `from core import pipeline`/`from core.pipeline import …` /
# `from core import caminhos`/`from core.caminhos import …` (os dois módulos
# avulsos). Não pega `core.dominio`, `core.aplicacao`, `core.regras`,
# `core.infra` (os anéis atuais) nem `core.infra.caminhos`/
# `core.aplicacao.pipeline` (os caminhos reais).
_ALVOS = "|".join(PACOTES_REMOVIDOS + MODULOS_AVULSOS_REMOVIDOS)
PADRAO = re.compile(
    r"^\s*(?:from\s+core\.(" + _ALVOS + r")(?:\.\S+)?\s+import\s+\S+"
    r"|from\s+core\s+import\s+(?:[^#\n]*\b(?:" + "|".join(MODULOS_AVULSOS_REMOVIDOS) + r")\b[^#\n]*)"
    r"|import\s+core\.(" + _ALVOS + r")(?:\.\S+)?)\b",
    re.MULTILINE,
)

PASTAS_VARRIDAS = ("core", "app", "scripts", "tests")
ARQUIVO_DESTE_TESTE = os.path.abspath(__file__)


def _arquivos_py():
    for nome_pasta in PASTAS_VARRIDAS:
        pasta_alvo = os.path.join(RAIZ, nome_pasta)
        if not os.path.isdir(pasta_alvo):
            continue
        for pasta, subpastas, arquivos in os.walk(pasta_alvo):
            subpastas[:] = [s for s in subpastas if s != "__pycache__"]
            for nome in sorted(arquivos):
                if nome.endswith(".py"):
                    yield os.path.join(pasta, nome)


def _imports_antigos() -> list[str]:
    achados: list[str] = []
    for caminho in _arquivos_py():
        if os.path.abspath(caminho) == ARQUIVO_DESTE_TESTE:
            continue  # este arquivo cita os nomes dos alvos no padrão acima
        with open(caminho, "r", encoding="utf-8") as f:
            linhas = f.readlines()
        for i, linha in enumerate(linhas, start=1):
            if PADRAO.match(linha):
                relativo = os.path.relpath(caminho, RAIZ)
                achados.append(f"{relativo}:{i}: {linha.strip()}")
    return achados


def test_nenhum_import_dos_pacotes_fachada_removidos_na_fase_6():
    achados = _imports_antigos()
    alvos = ", ".join("core." + p for p in PACOTES_REMOVIDOS + MODULOS_AVULSOS_REMOVIDOS)
    assert not achados, (
        f"import de um caminho-fachada removido na Fase 6 ({alvos}):\n"
        + "\n".join(achados)
    )


def test_pacotes_e_modulos_fachada_nao_existem_mais_no_filesystem():
    achados = [
        "core/" + p for p in PACOTES_REMOVIDOS
        if os.path.isdir(os.path.join(RAIZ, "core", p))
    ] + [
        f"core/{m}.py" for m in MODULOS_AVULSOS_REMOVIDOS
        if os.path.isfile(os.path.join(RAIZ, "core", f"{m}.py"))
    ]
    assert not achados, (
        "caminhos-fachada ainda presentes (deveriam ter sido apagados na "
        f"Fase 6): {achados}"
    )


def test_nenhuma_docstring_de_fachada_sobrevive():
    """Rede de segurança sem lista fixa: qualquer `.py` com a assinatura
    textual "Fachada (Strangler Fig" é, por definição, uma fachada que já
    deveria ter sido apagada."""
    achados = []
    for caminho in _arquivos_py():
        if os.path.abspath(caminho) == ARQUIVO_DESTE_TESTE:
            continue
        with open(caminho, "r", encoding="utf-8") as f:
            if "Fachada (Strangler Fig" in f.read():
                achados.append(os.path.relpath(caminho, RAIZ))
    assert not achados, f"fachada(s) Strangler Fig ainda presente(s): {achados}"
