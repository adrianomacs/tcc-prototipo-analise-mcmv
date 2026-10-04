"""Classificação de `IfcCovering` — pelo hospedeiro ou, órfão, pelo próprio
`PredefinedType` (`core/infra/ifc/classificacao_covering.py`) — ver a
docstring do módulo para o critério completo. Nenhum destes testes precisa do
IfcOpenShell: usam `tests/apoio/ifc_falso.py`, no mesmo padrão dos demais
testes de `infra/ifc/`.
"""

from __future__ import annotations

from core.infra.ifc import classificacao_covering as cc
from tests.apoio import ifc_falso as f


def test_parede_e_cobertura_sao_separadas_no_mesmo_modelo():
    """O teste-âncora do critério de saída: um modelo com as duas famílias
    não mistura os dois lados."""
    cov_parede = f.covering(gid="COV-PAREDE")
    cov_cobertura = f.covering(gid="COV-COBERTURA")
    parede = f.parede()
    telhado = f.telhado()
    modelo = f.modelo_coverings(
        parede, telhado, cov_parede, cov_cobertura,
        f.rel_cobre(parede, cov_parede, gid="REL-PAREDE"),
        f.rel_cobre(telhado, cov_cobertura, gid="REL-TELHADO"),
    )

    resultado = cc.classificar_por_hospedeiro(modelo)

    assert resultado.parede == [cov_parede]
    assert resultado.cobertura == [cov_cobertura]
    assert resultado.nao_classificado == []


def test_covering_orfao_sem_predefinedtype_e_reportado_nao_classificado():
    """Covering sem NENHUM `IfcRelCoversBldgElements` e sem `PredefinedType`
    que diga o lado: reportado, nunca atribuído por padrão — atribuir por
    omissão fabricaria falso conforme. `CEILING`, `NOTDEFINED` e
    `USERDEFINED` também não são lado nenhum."""
    orfaos = [f.covering(gid="COV-ORFAO"),
              f.covering(predefinido="CEILING", gid="COV-FORRO"),
              f.covering(predefinido="NOTDEFINED", gid="COV-ND"),
              f.covering(predefinido="USERDEFINED", gid="COV-UD")]
    modelo = f.modelo_coverings(*orfaos)

    resultado = cc.classificar_por_hospedeiro(modelo)

    assert resultado.nao_classificado == orfaos
    assert resultado.parede == [] and resultado.cobertura == []
    assert resultado.origem == {}


def test_covering_orfao_resolve_o_lado_pelo_proprio_predefinedtype():
    """Emenda ao ADR-027 (C4): sem relação nenhuma — o caso do Revit —, o
    `PredefinedType` do próprio covering decide: `ROOFING` → cobertura,
    `CLADDING` → parede. A partição diz que o lado veio do covering, não do
    hospedeiro (`origem`), e o mapa de hospedeiros continua vazio."""
    telhado = f.covering(predefinido="ROOFING", gid="COV-ROOFING")
    parede = f.covering(predefinido="CLADDING", gid="COV-CLADDING")
    modelo = f.modelo_coverings(telhado, parede)

    resultado = cc.classificar_por_hospedeiro(modelo)

    assert resultado.cobertura == [telhado]
    assert resultado.parede == [parede]
    assert resultado.nao_classificado == []
    assert resultado.origem == {telhado: cc.ORIGEM_PREDEFINIDO,
                                parede: cc.ORIGEM_PREDEFINIDO}
    assert resultado.hospedeiro == {}


def test_predefinedtype_e_herdado_do_tipo_quando_a_ocorrencia_nao_declara():
    """Regra do IFC4: ocorrência sem `PredefinedType` herda o do
    `IfcCoveringType`. É como o Revit grava (`ROOFING` no tipo, `$` na
    ocorrência); ler só a ocorrência perdia o telhado. A ocorrência, quando
    declara, prevalece sobre o tipo."""
    herdado = f.covering(gid="COV-HERDA", predefinido_do_tipo="ROOFING")
    proprio_vence = f.covering(predefinido="CLADDING", gid="COV-PROPRIO",
                               predefinido_do_tipo="ROOFING")
    nd_herda = f.covering(predefinido="NOTDEFINED", gid="COV-ND",
                          predefinido_do_tipo="CLADDING")
    modelo = f.modelo_coverings(herdado, proprio_vence, nd_herda)

    resultado = cc.classificar_por_hospedeiro(modelo)

    assert cc.predefinido(herdado) == "ROOFING"
    assert resultado.cobertura == [herdado]
    assert resultado.parede == [proprio_vence, nd_herda]


def test_hospedeiro_existente_prevalece_sobre_o_predefinedtype_do_covering():
    """Havendo relação, é o hospedeiro que decide — o `PredefinedType` não o
    sobrepõe: parede hospedando um `ROOFING` continua parede (a contradição
    é do proponente), e hospedeiro de classe estranha continua não
    classificado mesmo com `CLADDING` declarado."""
    parede = f.parede()
    coluna = f.FakeEntity("IfcColumn", _gid="C1")
    cov_roofing_na_parede = f.covering(predefinido="ROOFING", gid="COV-RP")
    cov_cladding_na_coluna = f.covering(predefinido="CLADDING", gid="COV-CC")
    modelo = f.modelo_coverings(
        parede, coluna, cov_roofing_na_parede, cov_cladding_na_coluna,
        f.rel_cobre(parede, cov_roofing_na_parede, gid="REL-P"),
        f.rel_cobre(coluna, cov_cladding_na_coluna, gid="REL-C"),
    )

    resultado = cc.classificar_por_hospedeiro(modelo)

    assert resultado.parede == [cov_roofing_na_parede]
    assert resultado.origem[cov_roofing_na_parede] == cc.ORIGEM_HOSPEDEIRO
    assert resultado.nao_classificado == [cov_cladding_na_coluna]


def test_relacao_sem_hospedeiro_declarado_tambem_e_reportado():
    """A relação existe, mas `RelatingBuildingElement` está vazio — não é
    crash nem atribuição por adivinhação, e também não cai na via do
    `PredefinedType`: a relação foi autorada e está quebrada."""
    cov = f.covering(predefinido="ROOFING", gid="COV-SEM-HOSPEDEIRO")
    modelo = f.modelo_coverings(cov, f.rel_cobre(None, cov))

    resultado = cc.classificar_por_hospedeiro(modelo)

    assert resultado.nao_classificado == [cov]


def test_hospedeiro_de_classe_desconhecida_e_reportado():
    """Hospedeiro que não é parede, telhado nem laje (ex.: IfcColumn) também
    não pode ser atribuído a um lado por adivinhação."""
    coluna = f.FakeEntity("IfcColumn", _gid="C1")
    cov = f.covering(gid="COV-COLUNA")
    modelo = f.modelo_coverings(coluna, cov, f.rel_cobre(coluna, cov))

    resultado = cc.classificar_por_hospedeiro(modelo)

    assert resultado.nao_classificado == [cov]


def test_hospedeiro_slab_e_ambiguo_e_desempata_pelo_predefinedtype_do_covering():
    """`IfcSlab` não decide piso x laje de cobertura sozinho (mesma classe
    nos dois casos): o desempate é o `PredefinedType` do COVERING, não do
    hospedeiro — `ROOFING` para cobertura, `CLADDING` para parede."""
    slab = f.laje()
    cov_roofing = f.covering(predefinido="ROOFING", gid="COV-ROOFING")
    cov_cladding = f.covering(predefinido="CLADDING", gid="COV-CLADDING")
    cov_indefinido = f.covering(predefinido="NOTDEFINED", gid="COV-INDEFINIDO")
    modelo = f.modelo_coverings(
        slab, cov_roofing, cov_cladding, cov_indefinido,
        f.rel_cobre(slab, cov_roofing, cov_cladding, cov_indefinido),
    )

    resultado = cc.classificar_por_hospedeiro(modelo)

    assert resultado.cobertura == [cov_roofing]
    assert resultado.parede == [cov_cladding]
    assert resultado.nao_classificado == [cov_indefinido]


def test_modelo_sem_covering_nenhum_devolve_particao_vazia():
    modelo = f.modelo_coverings()

    resultado = cc.classificar_por_hospedeiro(modelo)

    assert resultado == cc.CoveringsPorHospedeiro()
