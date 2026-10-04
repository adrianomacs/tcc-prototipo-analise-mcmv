"""Base dos ramos de absortância (``core/regras/base/absortancia.py``).

O que estes testes prendem, em ordem de importância:

1. **A população alvo é a do ADR-027, com as DUAS condições** — hospedeiro de
   cobertura por ``classificacao_covering`` E ``PredefinedType = ROOFING``. Covering de
   parede, órfão, ou de cobertura sem ``ROOFING`` fica de fora e é reportado.
2. **Os quatro caminhos do ramo**: conforme, não conforme, exceção (DN-01) e
   indeterminado (DN-08) — ``Regra().checar(ctx)`` direto, sem executor.
3. **Nunca conforme por omissão**: material sem nome ou absortância ausente
   não conclui.
4. **O que o ramo declara ao pai** (``CHAVE_APLICABILIDADE`` /
   ``CHAVE_VEREDITO_RAMO``) é coerente com o estado que emite.

Sem IfcOpenShell: modelos de ``tests/apoio/ifc_falso.py`` e Psets/materiais
por ``monkeypatch`` em ``core.infra.ifc.leitor_modelo``, como os demais testes
de regras BIM.
"""

from __future__ import annotations

import pytest

from core.dominio.conhecimento.zona_bioclimatica import ZonaBioclimatica
from core.dominio.contratos.regra import Estado
from core.dominio.vocabulario import motivos
from core.infra.ifc.leitura_ifc import LeituraIFC
from core.regras.base import absortancia as base
from core.regras.base import agregacao as ag
from tests.apoio import ifc_falso as f
from tests.apoio.contexto_bim import contexto_bim


class _RamoTelhado(base.RamoAbsortancia):
    """Ramo de teste fora do registro: telhado, cláusula não migrada."""
    id = "TST-ABS.1"
    descricao = "ramo de teste"
    limite = 0.6
    zonas = ()
    zonas_texto = "1, 2 e 3"

    def populacao(self, leitura):
        return base.populacao_cobertura(leitura)


class _RamoComZonas(_RamoTelhado):
    """Ramo de teste com cláusula MIGRADA: a zona seleciona."""
    id = "TST-ABS.2"
    zonas = ("1M", "1R", "2M", "2R")
    zonas_texto = "1 e 2 (R e M)"


def _modelo(*coverings_de_cobertura, extras=()):
    """Modelo com um IfcRoof cobrindo os coverings dados, mais entidades extras."""
    telhado = f.telhado()
    rel = f.rel_cobre(telhado, *coverings_de_cobertura, gid="REL-TELHADO")
    return f.modelo_coverings(telhado, *coverings_de_cobertura, rel, *extras)


def _dados(monkeypatch, absortancia=None, materiais=None):
    """``absortancia`` e ``materiais`` por GlobalId (dicts) — o que o leitor
    devolveria para cada covering."""
    absortancia = absortancia or {}
    materiais = materiais or {}
    monkeypatch.setattr(
        "core.infra.ifc.leitor_modelo.propriedades_do_elemento",
        lambda e: ({"AbsortanciaSolar": absortancia[e.GlobalId]}
                   if e.GlobalId in absortancia else {}))
    monkeypatch.setattr(
        "core.infra.ifc.leitor_modelo.materiais_do_elemento",
        lambda e: list(materiais.get(e.GlobalId, [])))


def _ctx(modelo, zona=None):
    return contexto_bim(modelo_ifc=modelo, zona_bioclimatica=zona)


# ---------------------------------------------------------------------------
# 1. População: as duas condições do ADR-027
# ---------------------------------------------------------------------------

def test_populacao_exige_lado_de_cobertura_e_roofing():
    """As duas condições do ADR-027: lado de cobertura E ``ROOFING``. O lado
    vem do hospedeiro quando há relação; sem relação (emenda da C4), do
    ``PredefinedType`` do próprio covering — e aí ``ROOFING`` órfão ENTRA na
    população, ``ROOFING`` só no tipo também (herança do IFC4), enquanto o
    órfão sem tipo continua não classificado."""
    com_roofing = f.covering(predefinido="ROOFING", gid="COV-OK")
    sem_roofing = f.covering(predefinido=None, gid="COV-SEM-TIPO")
    cov_parede = f.covering(predefinido="CLADDING", gid="COV-PAREDE")
    orfao_roofing = f.covering(predefinido="ROOFING", gid="COV-ORFAO-ROOFING")
    orfao_pelo_tipo = f.covering(gid="COV-ORFAO-TIPO", predefinido_do_tipo="ROOFING")
    orfao_sem_tipo = f.covering(gid="COV-ORFAO")
    parede = f.parede()
    modelo = _modelo(com_roofing, sem_roofing,
                     extras=(parede, cov_parede, orfao_roofing, orfao_pelo_tipo,
                             orfao_sem_tipo,
                             f.rel_cobre(parede, cov_parede, gid="REL-PAREDE")))

    alvo, diag = base.populacao_cobertura(LeituraIFC(modelo))

    assert alvo == [com_roofing, orfao_roofing, orfao_pelo_tipo]
    assert diag["cobertura_pelo_hospedeiro"] == 2
    assert diag["cobertura_pelo_predefinido"] == 2
    assert diag["cobertura_sem_roofing"] == ["COV-SEM-TIPO"]
    assert diag["nao_classificados"] == ["COV-ORFAO"]
    assert diag["parede"] == 1
    assert diag["total_coverings"] == 6


def test_sem_populacao_e_informacao_ausente_nunca_conforme(monkeypatch):
    """Órfão sem ``PredefinedType`` de lado, ou hospedeiro sem ROOFING: o
    requisito de informação não foi entregue (ADR-027) — não avaliável, com a
    causa. A absortância declarada não salva: sem lado, não há população."""
    orfao = f.covering(predefinido="CEILING", gid="COV-ORFAO")
    sem_tipo = f.covering(predefinido=None, gid="COV-SEM-TIPO")
    modelo = _modelo(sem_tipo, extras=(orfao,))
    _dados(monkeypatch, absortancia={"COV-ORFAO": 0.2, "COV-SEM-TIPO": 0.2})

    r = _RamoTelhado().checar(_ctx(modelo))

    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE
    assert "ROOFING" in r.mensagem
    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == ""


# ---------------------------------------------------------------------------
# 2. Os quatro caminhos do ramo — cláusula não migrada (telhado)
# ---------------------------------------------------------------------------

def test_indeterminado_conforme_sob_o_proprio_limite(monkeypatch):
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={"COV1": 0.5}, materiais={"COV1": ["Telha de concreto"]})

    r = _RamoTelhado().checar(_ctx(_modelo(cov)))

    # Emite NÃO AVALIÁVEL — a aplicabilidade está em aberto (DN-08) —, mas
    # declara ao pai que, sob <= 0,6, seria conforme.
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL
    assert r.detalhe[ag.CHAVE_APLICABILIDADE] == ag.RAMO_INDETERMINADA
    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == Estado.CONFORME.value
    assert r.elementos == ["COV1"]
    assert r.valor_encontrado == 0.5


def test_indeterminado_nao_conforme_sob_o_proprio_limite(monkeypatch):
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={"COV1": 0.7}, materiais={"COV1": ["Telha de concreto"]})

    r = _RamoTelhado().checar(_ctx(_modelo(cov)))

    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == Estado.NAO_CONFORME.value
    assert r.detalhe["coverings"][0]["situacao"] == base.SIT_NAO_ATENDE


def test_excecao_identificada_e_nao_aplicavel_com_motivo(monkeypatch):
    """Telha de barro não vitrificada: o limite não se aplica — NÃO é conforme."""
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={"COV1": 0.9},
           materiais={"COV1": ["Telha cerâmica natural"]})

    r = _RamoTelhado().checar(_ctx(_modelo(cov)))

    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.NAO_APLICAVEL
    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == ""
    c = r.detalhe["coverings"][0]
    assert c["situacao"] == base.SIT_EXCECAO
    assert c["excecao"] == "telha_barro_nao_vitrificada"
    assert c["termo_casado"] == "ceramic"
    assert "não vitrificada" in r.mensagem


def test_cobertura_verde_tambem_e_excecao(monkeypatch):
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={"COV1": 0.9}, materiais={"COV1": ["Telhado verde"]})
    r = _RamoTelhado().checar(_ctx(_modelo(cov)))
    assert r.detalhe[motivos.CHAVE] == motivos.NAO_APLICAVEL
    assert r.detalhe["coverings"][0]["excecao"] == "cobertura_verde"


def test_telha_ceramica_esmaltada_nao_e_excecao(monkeypatch):
    """A Portaria só excetua a NÃO vitrificada: a esmaltada é comparada."""
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={"COV1": 0.7},
           materiais={"COV1": ["Telha cerâmica esmaltada"]})
    r = _RamoTelhado().checar(_ctx(_modelo(cov)))
    assert r.detalhe["coverings"][0]["situacao"] == base.SIT_NAO_ATENDE
    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == Estado.NAO_CONFORME.value


def test_excecao_fica_fora_da_comparacao_e_o_resto_decide(monkeypatch):
    """Um covering de barro (0,9) e um pintado (0,3): o barro não conta, o
    pintado atende — conforme sob o próprio limite, com a ressalva dita."""
    barro = f.covering(predefinido="ROOFING", gid="BARRO")
    pintado = f.covering(predefinido="ROOFING", gid="PINTADO")
    _dados(monkeypatch, absortancia={"BARRO": 0.9, "PINTADO": 0.3},
           materiais={"BARRO": ["Telha de barro"], "PINTADO": ["Tinta acrílica branca"]})

    r = _RamoTelhado().checar(_ctx(_modelo(barro, pintado)))

    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == Estado.CONFORME.value
    assert r.valor_encontrado == 0.3      # o barro não entra no valor comparado
    assert "excetuado" in r.mensagem


# ---------------------------------------------------------------------------
# 3. Nunca conforme por omissão
# ---------------------------------------------------------------------------

def test_material_sem_nome_nao_e_identificavel(monkeypatch):
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={"COV1": 0.2}, materiais={"COV1": [""]})

    r = _RamoTelhado().checar(_ctx(_modelo(cov)))

    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE
    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == ""
    assert r.detalhe["coverings"][0]["situacao"] == base.SIT_MATERIAL_NAO_IDENTIFICAVEL
    assert "por omissão" in r.mensagem


def test_covering_sem_material_associado_tambem_nao_conclui(monkeypatch):
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={"COV1": 0.2}, materiais={})
    r = _RamoTelhado().checar(_ctx(_modelo(cov)))
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE


def test_absortancia_ausente_nao_conclui(monkeypatch):
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={}, materiais={"COV1": ["Telha de concreto"]})
    r = _RamoTelhado().checar(_ctx(_modelo(cov)))
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE
    assert r.detalhe["coverings"][0]["situacao"] == base.SIT_SEM_ABSORTANCIA
    assert "AbsortanciaSolar" in r.mensagem


def test_um_acima_do_limite_reprova_mesmo_com_outro_pendente(monkeypatch):
    """Medido é medido: 0,8 reprova sob o próprio limite ainda que outro
    covering esteja sem informação."""
    a = f.covering(predefinido="ROOFING", gid="A")
    b = f.covering(predefinido="ROOFING", gid="B")
    _dados(monkeypatch, absortancia={"A": 0.8}, materiais={"A": ["Concreto"], "B": ["Concreto"]})
    r = _RamoTelhado().checar(_ctx(_modelo(a, b)))
    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == Estado.NAO_CONFORME.value


def test_sem_modelo_e_nao_avaliavel():
    r = _RamoTelhado().checar(contexto_bim(modelo_ifc=None))
    assert r.estado is Estado.NAO_AVALIAVEL


def _ramos_registrados():
    from core.regras.gis_bim.edi_019_1_parede_zb_1_2 import EDI0191
    from core.regras.gis_bim.edi_019_2_parede_zb_3_6 import EDI0192
    from core.regras.gis_bim.edi_024_1_telhado_zb_1_3 import EDI0241
    from core.regras.gis_bim.edi_024_2_telhado_zb_4_8 import EDI0242
    return [EDI0191, EDI0192, EDI0241, EDI0242]


@pytest.mark.parametrize("classe", _ramos_registrados(), ids=lambda c: c.id)
def test_ramo_sem_modelo_e_insumo_do_proponente_ausente(classe):
    """ADR-033: a causa vem antes da zona — sem modelo não há o que medir."""
    r = classe().checar(contexto_bim(modelo_ifc=None))
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_DO_PROPONENTE_AUSENTE


# ---------------------------------------------------------------------------
# 4. Aplicabilidade pela zona — cláusula migrada (o caminho da B4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("classe, esperado", [
    ("1M", ag.RAMO_APLICAVEL), ("2R", ag.RAMO_APLICAVEL),
    ("3B", ag.RAMO_INAPLICAVEL), ("6A", ag.RAMO_INAPLICAVEL),
])
def test_zona_seleciona_o_ramo_quando_a_clausula_e_migrada(classe, esperado):
    aplic, _ = _RamoComZonas().aplicabilidade_na_zona(
        ZonaBioclimatica(classe=classe, codigo_ibge="0000000"))
    assert aplic == esperado


def test_zona_nao_resolvida_e_indeterminada_mesmo_com_clausula_migrada():
    aplic, explicacao = _RamoComZonas().aplicabilidade_na_zona(None)
    assert aplic == ag.RAMO_INDETERMINADA
    assert "não resolvida" in explicacao


def test_clausula_nao_migrada_e_indeterminada_para_qualquer_zona():
    for zona in (None, ZonaBioclimatica(classe="3B", codigo_ibge="0000000")):
        aplic, explicacao = _RamoTelhado().aplicabilidade_na_zona(zona)
        assert aplic == ag.RAMO_INDETERMINADA
        assert "não se traduz" in explicacao


def test_ramo_aplicavel_emite_o_proprio_veredito(monkeypatch):
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={"COV1": 0.7}, materiais={"COV1": ["Concreto"]})
    zona = ZonaBioclimatica(classe="1M", codigo_ibge="0000000")

    r = _RamoComZonas().checar(_ctx(_modelo(cov), zona))

    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe[ag.CHAVE_APLICABILIDADE] == ag.RAMO_APLICAVEL
    assert r.detalhe["zona_resolvida"]["classe"] == "1M"


def test_ramo_inaplicavel_sai_nao_aplicavel_e_nao_afirma_veredito(monkeypatch):
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={"COV1": 0.7}, materiais={"COV1": ["Concreto"]})
    zona = ZonaBioclimatica(classe="5A", codigo_ibge="0000000")

    r = _RamoComZonas().checar(_ctx(_modelo(cov), zona))

    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.NAO_APLICAVEL
    assert r.detalhe[ag.CHAVE_APLICABILIDADE] == ag.RAMO_INAPLICAVEL
    # O veredito sob o próprio limite viaja informativo; o pai o ignora.
    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == Estado.NAO_CONFORME.value


def test_causa_propria_vem_antes_da_aplicabilidade(monkeypatch):
    """Ramo aplicável mas sem material: o que destrava é a informação, não a
    zona — a causa declarada é a do ramo."""
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _dados(monkeypatch, absortancia={"COV1": 0.2}, materiais={})
    zona = ZonaBioclimatica(classe="1M", codigo_ibge="0000000")
    r = _RamoComZonas().checar(_ctx(_modelo(cov), zona))
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE
    assert r.detalhe[ag.CHAVE_APLICABILIDADE] == ag.RAMO_APLICAVEL


# ---------------------------------------------------------------------------
# 5. População da PAREDE EXTERNA — a decisão que o ADR-027 deixou para a B4
# ---------------------------------------------------------------------------
#
# A externalidade é declarada no PRÓPRIO covering (``Pset_CoveringCommon.
# IsExternal``, padrão do IFC4), e o ``Pset_WallCommon`` do hospedeiro entra
# como conferência quando a relação existe. Nenhuma heurística geométrica
# decide o lado (ADR-027), e divergência entre as duas declarações não é
# desempatada pelo protótipo.


class _RamoParede(base.RamoAbsortancia):
    """Ramo de teste fora do registro: parede externa, cláusula migrada."""
    id = "TST-ABS.3"
    descricao = "ramo de teste (parede)"
    limite = 0.4
    zonas = ("3A", "3B")
    zonas_texto = "3 (A e B)"
    familia = "parede externa"
    excecoes_por_material = False

    def populacao(self, leitura):
        return base.populacao_parede(leitura)


def _modelo_paredes(*pares):
    """``(parede, covering)`` por par; cada parede hospeda o seu covering."""
    entidades = []
    for i, (parede, cov) in enumerate(pares):
        entidades += [parede, cov, f.rel_cobre(parede, cov, gid=f"REL-P{i}")]
    return f.modelo_coverings(*entidades)


def _externalidade(monkeypatch, *, coverings=None, paredes=None):
    """``IsExternal`` por GlobalId, no covering e no IfcWall hospedeiro."""
    coverings = coverings or {}
    paredes = paredes or {}
    def falso(elemento, pset, *chaves):
        origem = coverings if pset == base.PSET_COVERING else (
            paredes if pset == base.PSET_PAREDE else {})
        valor = origem.get(getattr(elemento, "GlobalId", None))
        return (valor, f"{pset}.{base.PROP_EXTERNO}") if valor is not None else (None, "")
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.propriedade_de_pset", falso)


def test_populacao_de_parede_exige_hospedeiro_e_is_external_proprio(monkeypatch):
    externo = f.covering(gid="COV-EXT")
    interno = f.covering(gid="COV-INT")
    sem_declaracao = f.covering(gid="COV-SEM")
    orfao = f.covering(gid="COV-ORFAO")             # sem hospedeiro nenhum
    modelo = _modelo_paredes((f.parede("W1"), externo), (f.parede("W2"), interno),
                             (f.parede("W3"), sem_declaracao))
    modelo._entidades.append(orfao)
    _externalidade(monkeypatch,
                   coverings={"COV-EXT": True, "COV-INT": False})

    alvo, diag = base.populacao_parede(LeituraIFC(modelo))

    assert alvo == [externo]
    assert diag["parede_pelo_hospedeiro"] == 3
    assert diag["parede_pelo_predefinido"] == 0
    assert diag[base.EXT_INTERNA] == ["COV-INT"]
    assert diag[base.EXT_SEM_DECLARACAO] == ["COV-SEM"]
    assert diag["nao_classificados"] == ["COV-ORFAO"]
    assert base.CHAVE_BLOQUEIO not in diag


def test_parede_orfa_entra_pelo_cladding_e_pelo_is_external_proprio(monkeypatch):
    """O caso do Revit (E3 do Estrela I): nenhum ``IfcRelCoversBldgElements``.
    O lado vem do ``CLADDING`` do próprio covering (emenda da C4) e a
    externalidade do ``Pset_CoveringCommon.IsExternal`` — sem hospedeiro não
    há conferência, e portanto não há divergência possível."""
    externa = f.covering(predefinido="CLADDING", gid="COV-EXT")
    interna = f.covering(predefinido="CLADDING", gid="COV-INT")
    sem_lado = f.covering(gid="COV-SEM-LADO")          # USERDEFINED/None: não classifica
    modelo = f.modelo_coverings(externa, interna, sem_lado)
    _externalidade(monkeypatch, coverings={"COV-EXT": True, "COV-INT": False,
                                           "COV-SEM-LADO": True})

    alvo, diag = base.populacao_parede(LeituraIFC(modelo))

    assert alvo == [externa]
    assert diag["parede_pelo_hospedeiro"] == 0
    assert diag["parede_pelo_predefinido"] == 2
    assert diag[base.EXT_INTERNA] == ["COV-INT"]
    assert diag["nao_classificados"] == ["COV-SEM-LADO"]
    assert base.CHAVE_BLOQUEIO not in diag


def test_sem_is_external_declarado_e_informacao_ausente(monkeypatch):
    """Covering de parede sem ``IsExternal``: o requisito de informação não foi
    entregue (ADR-027) — nunca se adivinha a externalidade pela geometria."""
    cov = f.covering(gid="COV1")
    modelo = _modelo_paredes((f.parede(), cov))
    _externalidade(monkeypatch)
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.propriedades_do_elemento",
                        lambda e: {"AbsortanciaSolar": 0.2})

    r = _RamoParede().checar(_ctx(modelo, ZonaBioclimatica(classe="3A",
                                                           codigo_ibge="0000000")))

    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE
    assert "IsExternal" in r.mensagem
    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == ""


def test_hospedeiro_confirma_o_covering(monkeypatch):
    """As duas declarações concordando, o ramo segue normalmente."""
    cov = f.covering(gid="COV1")
    modelo = _modelo_paredes((f.parede("W1"), cov))
    _externalidade(monkeypatch, coverings={"COV1": True}, paredes={"W1": True})
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.propriedades_do_elemento",
                        lambda e: {"AbsortanciaSolar": 0.3})

    r = _RamoParede().checar(_ctx(modelo, ZonaBioclimatica(classe="3A",
                                                           codigo_ibge="0000000")))
    assert r.estado is Estado.CONFORME


def test_divergencia_entre_covering_e_hospedeiro_bloqueia_o_ramo(monkeypatch):
    """Declaração × declaração: o protótipo não escolhe um lado (ADR-027), e a
    causa é a do ADR-022 — a correção é do proponente, não do analista."""
    cov = f.covering(gid="COV1")
    modelo = _modelo_paredes((f.parede("W1"), cov))
    _externalidade(monkeypatch, coverings={"COV1": True}, paredes={"W1": False})
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.propriedades_do_elemento",
                        lambda e: {"AbsortanciaSolar": 0.2})

    r = _RamoParede().checar(_ctx(modelo, ZonaBioclimatica(classe="3A",
                                                           codigo_ibge="0000000")))

    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INCONSISTENCIA_DECLARATORIA
    assert "contradição" in r.mensagem
    assert r.detalhe["populacao"][base.EXT_DIVERGENTE] == ["COV1"]
    # Bloqueio da POPULAÇÃO: não se chega a avaliar covering nenhum.
    assert r.detalhe["coverings"] == []


def test_parede_nao_pede_material_nenhum(monkeypatch):
    """DN-02: 4.II.a.x não excetua material, então exigi-lo produziria
    pendência por informação que o requisito não pede. Sem material, o ramo
    conclui pelo que a Portaria de fato manda comparar."""
    cov = f.covering(gid="COV1")
    modelo = _modelo_paredes((f.parede("W1"), cov))
    _externalidade(monkeypatch, coverings={"COV1": True})
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.propriedades_do_elemento",
                        lambda e: {"AbsortanciaSolar": 0.7})
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.materiais_do_elemento",
                        lambda e: pytest.fail("ramo de parede não lê material (DN-02)"))

    r = _RamoParede().checar(_ctx(modelo, ZonaBioclimatica(classe="3B",
                                                           codigo_ibge="0000000")))

    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["coverings"][0]["situacao"] == base.SIT_NAO_ATENDE


# ---------------------------------------------------------------------------
# 6. A propriedade é achada pelo NOME, em qualquer property set (ADR-027)
# ---------------------------------------------------------------------------
#
# O IFC não tem absortância solar de superfície opaca em pset padrão, e
# ``ThermalTransmittance`` — que os ``Pset_*Common`` oferecem — é outra
# grandeza. ``AbsortanciaSolar`` é, portanto, requisito de informação do
# contratante, e o protótipo NÃO exige um pset nomeado enquanto a
# especificação não existir. Este teste prende essa decisão: se alguém trocar
# o achatamento por ``propriedade_de_pset`` com um nome fixo, ele reprova.


def _psets(monkeypatch, por_gid):
    """Imita ``propriedades_do_elemento``: achata TODOS os psets num dict só,
    como faz ``ifcopenshell.util.element.get_psets``."""
    def falso(elemento):
        achatado = {}
        for props in por_gid.get(getattr(elemento, "GlobalId", None), {}).values():
            achatado.update(props)
        return achatado
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.propriedades_do_elemento", falso)


@pytest.mark.parametrize("pset", [
    "Pset_CoveringCommon",          # o pset padrão do elemento
    "Pset_MCMV_Absortancia",        # um pset que a contratante venha a definir
    "Dados de identidade",          # o que um exportador em português produz
])
def test_absortancia_e_achada_em_qualquer_pset(monkeypatch, pset):
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _psets(monkeypatch, {"COV1": {pset: {"AbsortanciaSolar": 0.3}}})
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.materiais_do_elemento",
                        lambda e: ["Telha de concreto"])

    r = _RamoTelhado().checar(_ctx(_modelo(cov)))

    assert r.detalhe[ag.CHAVE_VEREDITO_RAMO] == Estado.CONFORME.value
    assert r.valor_encontrado == 0.3


def test_thermal_transmittance_nao_substitui_a_absortancia(monkeypatch):
    """Grandezas diferentes: U (W/m²K, condução) não é α (fração da radiação
    absorvida), e o requisito de U é outro (Tab. 2). Um covering que só traz
    ``ThermalTransmittance`` não entregou a informação que EDI-019/024 pedem."""
    cov = f.covering(predefinido="ROOFING", gid="COV1")
    _psets(monkeypatch, {"COV1": {"Pset_CoveringCommon": {"ThermalTransmittance": 0.3,
                                                          "IsExternal": True}}})
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.materiais_do_elemento",
                        lambda e: ["Telha de concreto"])

    r = _RamoTelhado().checar(_ctx(_modelo(cov)))

    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE
    assert r.detalhe["coverings"][0]["situacao"] == base.SIT_SEM_ABSORTANCIA
