"""ADR-023 — a ``Edificacao`` FÍSICA, o que ela responde sozinha, e o ``Ambiente``.

A antiga entidade ``Edificacao`` passou a chamar-se ``UnidadeTipo`` e seus
testes foram, por rename, para ``test_unidade_tipo.py``. O que se prende aqui é
a entidade nova:

1. **Só nome, contêiner e composição** — nada de nº de UH nem de tipologia
   próprios: os dois são derivados da composição, pela raiz
   (``test_empreendimento.py``).
2. **A composição é normalizada, não validada**: quantidade por
   ``contagem_de_uh``, entrada com zero removida. Os invariantes (só tipos do
   agregado, uma tipologia só) são do ``Empreendimento``.
3. **Identidade**, como as outras duas entidades do agregado (ADR-004).
4. **O anel de domínio não faz I/O** (ADR-002) — agora com ``unidade_tipo.py``
   na varredura.
"""

from __future__ import annotations

import ast
import os

import pytest

from core.dominio.edificacao import Ambiente, Edificacao
from core.dominio.modelo_bim import ModeloBIM
from core.dominio.vocabulario import declaracoes as dec
from tests.conftest import RAIZ

# ---------------------------------------------------------------------------
# Identidade
# ---------------------------------------------------------------------------

def test_id_gerado_curto_e_identidade_por_id():
    a, b = Edificacao(nome="Torre A"), Edificacao(nome="Torre A")
    assert len(a.id) == 12 and a.id != b.id
    assert a != b, "mesmos dados não fazem a mesma edificação"
    assert a == Edificacao(id=a.id, nome="outro nome")
    assert len({a, b, Edificacao(id=a.id)}) == 2


def test_nome_normaliza_espacos():
    assert Edificacao(nome="  Torre A  ").nome == "Torre A"
    assert Edificacao(nome=None).nome == ""


# ---------------------------------------------------------------------------
# A composição: forma normalizada, sem semântica
# ---------------------------------------------------------------------------

def test_edificacao_nasce_sem_composicao_e_sem_uh():
    e = Edificacao(nome="Torre A")
    assert e.composicao == {} and e.unidades_compostas == 0
    assert e.ids_unidades_tipo == ()


def test_composicao_guarda_quantidades_por_id_na_ordem_declarada():
    e = Edificacao(nome="Torre A", composicao={"padrao": 50, "pcd": "10"})
    assert e.composicao == {"padrao": 50, "pcd": 10}
    assert e.unidades_compostas == 60
    assert e.ids_unidades_tipo == ("padrao", "pcd")


def test_entrada_com_zero_e_removida_nao_guardada():
    """"Zero desta" e "nenhuma desta" são a mesma coisa (ADR-023)."""
    e = Edificacao(composicao={"padrao": 50, "pcd": 0, "": 3, None: 1})
    assert e.composicao == {"padrao": 50}


@pytest.mark.parametrize("quantidade", [-1, "dez", [10]])
def test_quantidade_invalida_na_composicao_e_recusada(quantidade):
    with pytest.raises(ValueError):
        Edificacao(composicao={"padrao": quantidade})


def test_edificacao_nao_tem_unidades_nem_tipologia_proprias():
    """Os dois são derivados da composição, na raiz — pendurá-los aqui seria
    voltar ao papel duplo que o ADR-023 desfez."""
    e = Edificacao(nome="Torre A", composicao={"padrao": 50})
    assert not hasattr(e, "unidades") and not hasattr(e, "tipologia")


# ---------------------------------------------------------------------------
# Contêiner: o mesmo VO das outras entidades (ADR-021/023)
# ---------------------------------------------------------------------------

def test_edificacao_sem_conteiner_nao_e_checavel_por_bim():
    e = Edificacao(nome="Torre B", composicao={"padrao": 60})
    assert e.modelo is None and e.checavel_por_bim is False
    assert e.unidades_representadas == 0, (
        "sem contêiner não há entrega a cujo respeito perguntar — e zero, não "
        "as UH compostas, é o que a regra encontraria")


def test_pavimento_tipo_misto_anexado_a_edificacao():
    """O caso 3 do ADR-023: o arquivo que mistura tipos tem dono, e o
    denominador continua sendo o do contêiner, não a composição."""
    torre = Edificacao(nome="Torre A", composicao={"padrao": 50, "pcd": 10},
                       modelo=ModeloBIM(caminho="tipo_misto.ifc",
                                        natureza=dec.EDIFICACAO_ISOLADA,
                                        unidades_representadas=6))
    assert torre.checavel_por_bim is True
    assert (torre.unidades_representadas, torre.unidades_compostas) == (6, 60)


# ---------------------------------------------------------------------------
# Serialização (sem I/O)
# ---------------------------------------------------------------------------

def test_ida_e_volta_preserva_identidade_conteiner_e_composicao():
    e = Edificacao(nome="Torre A", composicao={"padrao": 50, "pcd": 10},
                   modelo=ModeloBIM(caminho="tipo.ifc", schema="IFC4",
                                    natureza=dec.EDIFICACAO_ISOLADA,
                                    unidades_representadas=6))
    volta = Edificacao.from_dict(e.to_dict())
    assert volta == e and volta.to_dict() == e.to_dict()
    assert volta.modelo == e.modelo and volta.composicao == e.composicao


def test_edificacao_sem_conteiner_viaja_com_modelo_none_e_composicao_vazia():
    d = Edificacao(nome="Torre B").to_dict()
    assert d["modelo"] is None and d["composicao"] == {}
    volta = Edificacao.from_dict(d)
    assert volta.modelo is None and volta.composicao == {}


def test_ausencia_de_edificacao_viaja_como_none():
    assert Edificacao.from_dict(None) is None and Edificacao.from_dict({}) is None


def test_from_dict_ignora_os_campos_da_unidade_tipo_e_gera_id_se_faltar():
    """Um item do esquema E1 (``edificacoes`` da antiga entidade) lido pelo domínio
    vira uma física SEM ``unidades``/``tipologia``: reconhecer que eram
    unidades tipo é migração, da persistência (ADR-023)."""
    e = Edificacao.from_dict({"nome": "Bloco A", "unidades": 60,
                              "tipologia": dec.APARTAMENTO, "modelo": None})
    assert len(e.id) == 12 and e.nome == "Bloco A"
    assert e.composicao == {} and not hasattr(e, "unidades")

# ---------------------------------------------------------------------------
# O Ambiente que já morava aqui continua intacto
# ---------------------------------------------------------------------------

def test_ambiente_continua_no_modulo_e_serializa():
    a = Ambiente(global_id="1X2", nome="Sala", area_m2=12.5)
    assert a.to_dict()["nome"] == "Sala" and a.to_dict()["area_m2"] == 12.5


# ---------------------------------------------------------------------------
# Anel de domínio: nada de I/O (ADR-002)
# ---------------------------------------------------------------------------

PROIBIDOS_NO_DOMINIO = {"os", "json", "csv", "yaml", "urllib", "ifcopenshell",
                        "ifctester", "geopandas", "tempfile", "pathlib"}


def _imports_e_chamadas(caminho: str) -> tuple[set[str], set[str]]:
    with open(caminho, encoding="utf-8") as f:
        arvore = ast.parse(f.read())
    modulos, chamadas = set(), set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            modulos |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module and not no.level:
            modulos.add(no.module.split(".")[0])
        elif isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
            chamadas.add(no.func.id)
    return modulos, chamadas


@pytest.mark.parametrize("modulo", ["edificacao.py", "unidade_tipo.py",
                                    "modelo_bim.py", "identidade.py"])
def test_modulos_novos_do_dominio_nao_fazem_io(modulo):
    modulos, chamadas = _imports_e_chamadas(
        os.path.join(RAIZ, "core", "dominio", modulo))
    assert not (modulos & PROIBIDOS_NO_DOMINIO), modulos & PROIBIDOS_NO_DOMINIO
    assert "open" not in chamadas
