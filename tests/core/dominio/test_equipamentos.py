"""Testes dos equipamentos de educação (Enquadramento — R4a).

Lógica pura: objeto canônico, filtros normativos, mesclagem INEP × CSV e
sanidade do insumo. Nada de rede, nada de IfcOpenShell, nada de leitura de
arquivo — isso é `core/infra/gis/test_csv_equipamentos.py`.
"""

from __future__ import annotations

import pytest

from core.dominio import equipamentos as eq

CG_LAT, CG_LON = -20.4712, -54.6215


def _escola(nome="Escola", *, lat=CG_LAT, lon=CG_LON, ciclos=(eq.CICLO_INFANTIL,),
            rede=eq.REDE_MUNICIPAL, situacao=eq.SITUACAO_ATIVA, codigo=None,
            fonte=eq.FONTE_INEP):
    return eq.Equipamento(nome=nome, lat=lat, lon=lon, ciclos=list(ciclos),
                          rede=rede, situacao=situacao, codigo_inep=codigo,
                          fonte=fonte)


# ===========================================================================
# Filtros normativos: só pública e ativa
# ===========================================================================

def test_privada_e_descartada_com_o_motivo_nomeado():
    f = eq.filtrar([_escola("pública"), _escola("privada", rede=eq.REDE_PRIVADA)])
    assert len(f.aceitos) == 1
    assert f.contagem_por_motivo == {eq.DESCARTE_REDE_PRIVADA: 1}


@pytest.mark.parametrize("situacao", [eq.SITUACAO_PARALISADA, eq.SITUACAO_EXTINTA,
                                      eq.SITUACAO_EM_REFORMA,
                                      eq.SITUACAO_EM_CONSTRUCAO])
def test_situacao_nao_ativa_e_descartada(situacao):
    f = eq.filtrar([_escola(situacao=situacao)])
    assert not f.aceitos
    assert f.contagem_por_motivo == {eq.DESCARTE_SITUACAO_INATIVA: 1}


def test_rede_indefinida_nao_e_assumida_como_publica():
    """Assumir 'pública e ativa' por omissão criaria conformidade falsa."""
    f = eq.filtrar([_escola(rede="")])
    assert not f.aceitos
    assert f.contagem_por_motivo == {eq.DESCARTE_REDE_INDEFINIDA: 1}


def test_situacao_indefinida_nao_e_assumida_como_ativa():
    f = eq.filtrar([_escola(situacao="")])
    assert not f.aceitos
    assert f.contagem_por_motivo == {eq.DESCARTE_SITUACAO_INDEFINIDA: 1}


def test_filtro_de_ciclo_e_opcional_e_reporta_seu_proprio_motivo():
    escolas = [_escola("infantil", ciclos=[eq.CICLO_INFANTIL]),
               _escola("fund I", ciclos=[eq.CICLO_FUND_I]),
               _escola("ambos", ciclos=[eq.CICLO_FUND_I, eq.CICLO_FUND_II])]
    assert len(eq.filtrar(escolas).aceitos) == 3
    f = eq.filtrar(escolas, ciclo=eq.CICLO_FUND_I)
    assert {e.nome for e in f.aceitos} == {"fund I", "ambos"}
    assert f.contagem_por_motivo == {eq.DESCARTE_CICLO_DIVERSO: 1}


def test_motivo_reportado_e_o_mais_basico():
    """Dizer 'não atende ao ciclo' de uma linha sem coordenada confundiria."""
    f = eq.filtrar([_escola(lat=None, rede=eq.REDE_PRIVADA, ciclos=[])],
                   ciclo=eq.CICLO_INFANTIL)
    assert f.contagem_por_motivo == {eq.DESCARTE_SEM_COORDENADA: 1}


def test_resumo_torna_o_descarte_auditavel():
    """É o texto que permite ver que a escola existe e por que não contou."""
    escolas = [_escola("ok"), _escola("p1", rede=eq.REDE_PRIVADA),
               _escola("p2", rede=eq.REDE_PRIVADA),
               _escola("obra", situacao=eq.SITUACAO_EM_CONSTRUCAO)]
    resumo = eq.filtrar(escolas).resumo()
    assert "4 equipamento(s) no conjunto" in resumo
    assert "1 considerado(s)" in resumo
    assert "2 rede privada" in resumo
    assert "1 situação não ativa" in resumo


def test_resumo_sem_descarte_nao_inventa_texto():
    assert "nenhum descartado" in eq.filtrar([_escola()]).resumo()


# ===========================================================================
# Mesclagem INEP × CSV
# ===========================================================================

def test_csv_vence_no_mesmo_codigo_inep():
    oficial = _escola("nome errado no cadastro", codigo="500123")
    declarado = _escola("nome correto", codigo="500123", fonte=eq.FONTE_CSV)
    conjunto, proc = eq.mesclar([oficial], [declarado])

    assert len(conjunto) == 1
    assert conjunto[0].nome == "nome correto"
    assert proc == {"oficiais": 1, "declarados": 1, "substituidos": 1,
                    "acrescentados": 0, "total": 1}


def test_declarado_sem_codigo_e_acrescentado():
    conjunto, proc = eq.mesclar([_escola("A", codigo="1")],
                                [_escola("B", fonte=eq.FONTE_CSV)])
    assert {e.nome for e in conjunto} == {"A", "B"}
    assert proc["acrescentados"] == 1 and proc["substituidos"] == 0


def test_oficiais_sem_codigo_sao_preservados():
    conjunto, _ = eq.mesclar([_escola("sem código"), _escola("com código", codigo="9")],
                             [])
    assert len(conjunto) == 2


# ===========================================================================
# Sanidade do insumo — lacuna de cadastro não pode virar falso não-conforme
# ===========================================================================

def test_nenhum_aceito_com_registros_no_conjunto_distingue_as_duas_causas():
    sinais = eq.sanidade([], ciclo=eq.CICLO_INFANTIL, total_no_conjunto=7)
    assert len(sinais) == 1
    assert sinais[0].codigo == eq.SUSPEITA_SEM_ETAPA
    assert "todos privados" in sinais[0].mensagem
    assert "vistoria" in sinais[0].mensagem


def test_cadastro_vazio_aponta_cadastro_incompleto():
    sinais = eq.sanidade([], ciclo=eq.CICLO_FUND_I, total_no_conjunto=0)
    assert sinais[0].codigo == eq.SUSPEITA_SEM_ETAPA
    assert "incompleto" in sinais[0].mensagem


def test_contagem_implausivel_para_a_populacao():
    poucos = [_escola(f"e{i}", lon=CG_LON + i * 0.01) for i in range(3)]
    sinais = eq.sanidade(poucos, ciclo=eq.CICLO_INFANTIL,
                         populacao_municipal=900_000)
    assert any(s.codigo == eq.SUSPEITA_CONTAGEM_IMPLAUSIVEL for s in sinais)


def test_contagem_plausivel_nao_gera_sinal():
    muitas = [_escola(f"e{i}", lon=CG_LON + i * 0.01) for i in range(60)]
    sinais = eq.sanidade(muitas, ciclo=eq.CICLO_INFANTIL,
                         populacao_municipal=900_000)
    assert not any(s.codigo == eq.SUSPEITA_CONTAGEM_IMPLAUSIVEL for s in sinais)


def test_coordenadas_identicas_acusam_artefato_de_cadastro():
    iguais = [_escola("a"), _escola("b"), _escola("c")]   # todas no mesmo ponto
    sinais = eq.sanidade(iguais, ciclo=eq.CICLO_INFANTIL)
    assert any(s.codigo == eq.SUSPEITA_COORDENADAS_IDENTICAS for s in sinais)


def test_conjunto_saudavel_nao_gera_sinal():
    saudavel = [_escola(f"e{i}", lat=CG_LAT + i * 0.01, lon=CG_LON + i * 0.01)
                for i in range(12)]
    assert eq.sanidade(saudavel, ciclo=eq.CICLO_INFANTIL,
                       populacao_municipal=100_000) == []


def test_distancia_absurda_e_sinal_e_distancia_normal_nao_e():
    assert eq.suspeita_por_distancia(850.0) is None
    assert eq.suspeita_por_distancia(None) is None
    suspeita = eq.suspeita_por_distancia(23_000.0)
    assert suspeita is not None
    assert suspeita.codigo == eq.SUSPEITA_DISTANCIA_ABSURDA
    assert "23.0 km" in suspeita.mensagem


# ===========================================================================
# Ida e volta do objeto canônico
# ===========================================================================

def test_ida_e_volta_do_equipamento():
    original = _escola("Escola", ciclos=[eq.CICLO_INFANTIL, eq.CICLO_FUND_I],
                       codigo="500123")
    copia = eq.Equipamento.from_dict(original.to_dict())
    assert copia == original


def test_atendimento_sobrevive_ao_to_dict():
    e = eq.Equipamento(nome="X", lat=CG_LAT, lon=CG_LON,
                       atendimento=eq.ATENDIMENTO_EXCLUSIVO_DEFICIENCIA,
                       conveniada=True)
    volta = eq.Equipamento.from_dict(e.to_dict())
    assert volta.atendimento == eq.ATENDIMENTO_EXCLUSIVO_DEFICIENCIA
    assert volta.conveniada is True
    assert volta.oferta_publica_ampliada is True
    assert volta.escolariza_demanda_geral is False
