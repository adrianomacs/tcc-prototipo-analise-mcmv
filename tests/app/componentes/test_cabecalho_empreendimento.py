"""Frase e card do empreendimento (ADR-034 (d)) — funções puras, testadas por
chamada direta, sem `AppTest`. Um caso por variação da decisão."""

from __future__ import annotations

from app.componentes import cabecalho_empreendimento as cab
from core.dominio.edificacao import Edificacao
from core.dominio.empreendimento import Empreendimento, Localizacao
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec


def _estrela(**kw):
    t1 = UnidadeTipo(nome="Apartamento T+1", unidades=300,
                     tipologia=dec.APARTAMENTO)
    base = {"nome": "Residencial Estrela I",
            "localizacao": Localizacao("4307807", "RS", "Estrela"),
            "unidades_previstas": 300, "unidades_tipo": [t1],
            "declaracoes": {dec.ARRANJO: dec.CONDOMINIO}}
    base.update(kw)
    return Empreendimento(**base), t1


def test_condominio_lista_as_edificacoes_com_as_uhs_de_cada_uma():
    emp, t1 = _estrela()
    emp.edificacoes = [Edificacao(nome="Bloco A", composicao={t1.id: 4}),
                       Edificacao(nome="Bloco B - A12", composicao={t1.id: 296})]
    assert cab.frase_do_empreendimento(emp) == (
        "O empreendimento analisado, o Residencial Estrela I, está situado em "
        "Estrela/RS e é um condomínio de apartamentos que totaliza 300 UHs, "
        "dividido nas edificações Bloco A (4 UHs) e Bloco B - A12 (296 UHs), "
        "com a unidade tipo Apartamento T+1.")


def test_mais_de_tres_edificacoes_vira_contagem_com_intervalo():
    emp, t1 = _estrela()
    nomes = ["Bloco A"] + [f"Bloco A{i}" for i in range(1, 13)]
    emp.edificacoes = [Edificacao(nome=n, composicao={t1.id: 1}) for n in nomes]
    assert ("dividido em 13 edificações (Bloco A a Bloco A12), com a unidade "
            "tipo Apartamento T+1.") in cab.frase_do_empreendimento(emp)


def test_loteamento_muda_a_forma_de_distribuicao_e_nao_lista_edificacoes():
    casa = UnidadeTipo(nome="Casa T+2", unidades=64, tipologia=dec.CASA)
    emp = Empreendimento(nome="Jardim X",
                         localizacao=Localizacao("2704302", "AL", "Maceió"),
                         unidades_previstas=64, unidades_tipo=[casa],
                         edificacoes=[Edificacao(nome="Casa 1",
                                                 composicao={casa.id: 1})],
                         declaracoes={dec.ARRANJO: dec.LOTEAMENTO})
    assert cab.frase_do_empreendimento(emp) == (
        "O empreendimento analisado, o Jardim X, está situado em Maceió/AL e é "
        "um loteamento de 64 UHs em casas, com a unidade tipo Casa T+2.")


def test_duas_unidades_tipo_no_plural():
    a = UnidadeTipo(nome="Apartamento T+1", unidades=10,
                    tipologia=dec.APARTAMENTO)
    b = UnidadeTipo(nome="Apartamento T+3", unidades=10,
                    tipologia=dec.APARTAMENTO)
    emp = Empreendimento(nome="R", unidades_previstas=20, unidades_tipo=[a, b],
                         declaracoes={dec.ARRANJO: dec.CONDOMINIO})
    assert cab.frase_do_empreendimento(emp) == (
        "O empreendimento analisado, o R, é um condomínio de apartamentos que "
        "totaliza 20 UHs, com as unidades tipo Apartamento T+1 e Apartamento "
        "T+3.")


def test_omite_o_que_falta_e_nunca_inventa():
    emp = Empreendimento(nome="Estrela I",
                         localizacao=Localizacao("4307807", "RS", "Estrela"))
    assert cab.frase_do_empreendimento(emp) == (
        "O empreendimento analisado, o Estrela I, está situado em Estrela/RS.")
    emp, _ = _estrela(unidades_previstas=0, declaracoes={})
    assert cab.frase_do_empreendimento(emp) == (
        "O empreendimento analisado, o Residencial Estrela I, está situado em "
        "Estrela/RS e é composto de apartamentos, com a unidade tipo "
        "Apartamento T+1.")
    assert cab.frase_do_empreendimento(Empreendimento(nome="Só nome")) == (
        "O empreendimento analisado, o Só nome.")


def test_vazia_quando_nada_foi_declarado():
    assert cab.frase_do_empreendimento(Empreendimento()) == ""


def test_nao_carrega_a_inconsistencia_declaratoria():
    """Declaradas × previstas continua aviso à parte (ADR-034 (d))."""
    emp, _ = _estrela(unidades_previstas=10)
    assert not emp.declaracao_consistente
    frase = cab.frase_do_empreendimento(emp)
    assert "10 UHs" in frase and "300" not in frase


def test_nunca_fala_em_tipologia():
    """O que se repete é "unidade tipo"; tipologia é casa × apartamento."""
    emp, _ = _estrela()
    assert "tipologia" not in cab.frase_do_empreendimento(emp)


def test_card_escapa_o_texto_declarado():
    html = cab.montar_card("O empreendimento analisado, o <b>X</b>.")
    assert "<b>X</b>" not in html and "&lt;b&gt;X&lt;/b&gt;" in html


def test_declaracao_consistente_quando_sem_excedente():
    emp = Empreendimento(unidades_previstas=10,
                         unidades_tipo=[UnidadeTipo(nome="A", unidades=10)])
    assert emp.declaracao_consistente
    assert emp.excedente_declarado == 0


def test_declaracao_inconsistente_quando_excede():
    """A aritmética existe em `Empreendimento` (ADR-021/033); o card só lê."""
    emp = Empreendimento(unidades_previstas=10,
                         unidades_tipo=[UnidadeTipo(nome="A", unidades=12)])
    assert not emp.declaracao_consistente
    assert emp.excedente_declarado == 2


# --- ADR-022 sob o card: os números declarados que não fecham ---------------

def test_numeros_que_fecham_nao_geram_aviso():
    emp, t1 = _estrela()
    emp.edificacoes = [Edificacao(nome="Bloco A", composicao={t1.id: 300})]
    assert cab.aviso_de_inconsistencia(emp) is None


def test_composicao_acima_da_unidade_tipo_vira_alerta_com_os_numeros():
    emp, t1 = _estrela()
    emp.edificacoes = [Edificacao(nome="Bloco A", composicao={t1.id: 8}),
                       Edificacao(nome="Bloco B - A12", composicao={t1.id: 296})]
    aviso = cab.aviso_de_inconsistencia(emp)
    assert aviso.nivel == "warning"
    assert "304 UHs da unidade tipo Apartamento T+1, que declara 300" in (
        aviso.consequencia)
    assert "Informações Gerais" in aviso.acao


def test_unidades_tipo_acima_do_previsto_vira_alerta_e_sem_link_aponta_abaixo():
    emp, _ = _estrela(unidades_previstas=250)
    aviso = cab.aviso_de_inconsistencia(emp, com_link=False)
    assert "300 UHs, 50 a mais que as 250 previstas" in aviso.consequencia
    assert aviso.acao == "Corrija as quantidades abaixo."


def test_unidades_tipo_abaixo_do_previsto_vira_orientacao():
    emp, _ = _estrela(unidades_previstas=320)
    assert cab.aviso_de_inconsistencia(emp) is None
    aviso = cab.aviso_de_cobertura_declarada(emp)
    assert aviso.nivel == "info"
    assert aviso.chave == "As unidades tipo cobrem 300 das 320 UHs previstas."


def test_sem_previsao_ou_sem_unidade_tipo_nao_orienta():
    emp, _ = _estrela(unidades_previstas=0)
    assert cab.aviso_de_cobertura_declarada(emp) is None
    emp, _ = _estrela(unidades_tipo=[])
    assert cab.aviso_de_cobertura_declarada(emp) is None
    emp, _ = _estrela()
    assert cab.aviso_de_cobertura_declarada(emp) is None
