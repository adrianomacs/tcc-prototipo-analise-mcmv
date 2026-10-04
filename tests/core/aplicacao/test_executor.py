"""Testes da infraestrutura do motor (sem IfcOpenShell).

    pytest tests/core/aplicacao/test_executor.py

Usa modelos IFC falsos (``tests/apoio/ifc_falso.py``) e, para as dependências e o gate
do terreno, **regras temporárias** criadas no próprio teste: depois que o
esboço do ENQ-009 foi removido (2026-09-10), nenhuma regra registrada declara
``depende_de``, e amarrar o teste a uma regra concreta foi justamente o que o
fez quebrar. O comportamento testado é do executor, não da regra.
"""

import pytest

from core.aplicacao.executor import _consolidar, executar
from core.dominio import terreno as trn
from core.dominio.contratos.regra import Contexto, Estado, Regra, Resultado
from core.dominio.empreendimento import Empreendimento, ModeloBIM
from core.dominio.vocabulario import motivos
from core.regras.registro import _REGISTRO, regras_registradas
from tests.apoio.contexto_bim import contexto_bim
from tests.apoio.ifc_falso import modelo_nivel_30

CG_LON, CG_LAT = -54.6215, -20.4712


@pytest.fixture
def regra_temporaria():
    """Cria regras só durante o teste e limpa o registro global no fim.

    Mexe em ``_REGISTRO`` de propósito: o decorador ``@registrar`` é definitivo
    por design (o registro é a fonte de rastreabilidade do protótipo), então o
    isolamento tem de ser feito aqui, e não afrouxando a produção.
    """
    criadas: list[str] = []

    def criar(rid: str, **atributos):
        atributos.setdefault("checar", lambda self, ctx: self.conforme())
        _REGISTRO[rid] = type("RegraTemp", (Regra,), {"id": rid, **atributos})
        criadas.append(rid)

    yield criar

    for rid in criadas:
        _REGISTRO.pop(rid, None)


def _quadrado(lado_graus: float = 0.001):
    return [(CG_LON - lado_graus, CG_LAT - lado_graus),
            (CG_LON + lado_graus, CG_LAT - lado_graus),
            (CG_LON + lado_graus, CG_LAT + lado_graus),
            (CG_LON - lado_graus, CG_LAT + lado_graus)]


def test_registro_descobre_regras():
    regras = regras_registradas()
    for rid in ("EMP-001", "EDI-024",
                "EDI-004", "EDI-004.1", "EDI-001", "EDI-002"):
        assert rid in regras, f"regra {rid} nao registrada"


def test_dependencia_prereq_nao_conforme_gera_nao_avaliavel(regra_temporaria):
    # Modelo no nivel 30 (sem CRS projetado): EMP-001 fica NAO_CONFORME e a
    # regra que dele depende deve resultar NAO_AVALIAVEL, com o motivo dito.
    regra_temporaria("TST-DEP", depende_de=["EMP-001"])
    ctx = contexto_bim(modelo_ifc=modelo_nivel_30(), camadas_gis={},
                       conteiner=ModeloBIM(natureza="terreno"))
    resultados = executar(ctx, ids_selecionados=["EMP-001", "TST-DEP"])
    assert resultados["EMP-001"].estado is Estado.NAO_CONFORME
    assert resultados["TST-DEP"].estado is Estado.NAO_AVALIAVEL
    assert resultados["TST-DEP"].detalhe[motivos.CHAVE] == motivos.PREREQUISITO_FALHO


def test_sem_terreno_a_regra_que_o_exige_fica_nao_avaliavel(regra_temporaria):
    regra_temporaria("TST-PONTO", exige_terreno=trn.NIVEL_PONTO)
    resultados = executar(Contexto(), ids_selecionados=["TST-PONTO"])
    assert resultados["TST-PONTO"].estado is Estado.NAO_AVALIAVEL
    assert resultados["TST-PONTO"].detalhe[motivos.CHAVE] == motivos.TERRENO_AUSENTE


def test_terreno_ponto_atende_quem_pede_ponto_e_barra_quem_pede_poligonal(regra_temporaria):
    """O gate é ATÔMICO: a regra que se satisfaz com o ponto roda mesmo
    quando a vizinha, que exige geometria, não pode ser avaliada."""
    regra_temporaria("TST-PONTO", exige_terreno=trn.NIVEL_PONTO)
    regra_temporaria("TST-POLI", exige_terreno=trn.NIVEL_POLIGONAL)
    ctx = Contexto(
        empreendimento=Empreendimento(terreno=trn.de_ponto_wgs84(CG_LAT, CG_LON)))

    resultados = executar(ctx, ids_selecionados=["TST-PONTO", "TST-POLI"])
    assert resultados["TST-PONTO"].estado is Estado.CONFORME
    assert resultados["TST-POLI"].estado is Estado.NAO_AVALIAVEL
    assert resultados["TST-POLI"].detalhe[motivos.CHAVE] == motivos.TERRENO_INSUFICIENTE


def test_terreno_com_poligonal_libera_as_duas_exigencias(regra_temporaria):
    regra_temporaria("TST-PONTO", exige_terreno=trn.NIVEL_PONTO)
    regra_temporaria("TST-POLI", exige_terreno=trn.NIVEL_POLIGONAL)
    ctx = Contexto(empreendimento=Empreendimento(terreno=trn.de_poligonal_wgs84(
        _quadrado(), origem=trn.ORIGEM_DESENHADA, precisao=trn.PRECISAO_APROXIMADA)))

    resultados = executar(ctx, ids_selecionados=["TST-PONTO", "TST-POLI"])
    assert resultados["TST-PONTO"].estado is Estado.CONFORME
    assert resultados["TST-POLI"].estado is Estado.CONFORME


def test_regra_sem_exigencia_de_terreno_roda_sem_terreno(regra_temporaria):
    """Retrocompatibilidade: as regras BIM já validadas não declaram
    ``exige_terreno`` e não podem ser afetadas pelo gate novo."""
    regra_temporaria("TST-LIVRE")
    resultados = executar(Contexto(), ids_selecionados=["TST-LIVRE"])
    assert resultados["TST-LIVRE"].estado is Estado.CONFORME


def test_consolidacao_uma_nao_conforme_reprova():
    res = [
        Resultado("X", Estado.CONFORME, elementos=["g1"]),
        Resultado("X", Estado.NAO_CONFORME, elementos=["g2"]),
    ]
    consolidado = _consolidar("X", res)
    assert consolidado.estado is Estado.NAO_CONFORME
    assert set(consolidado.elementos) == {"g1", "g2"}


def test_consolidacao_todas_conformes():
    res = [Resultado("Y", Estado.CONFORME), Resultado("Y", Estado.CONFORME)]
    assert _consolidar("Y", res).estado is Estado.CONFORME
