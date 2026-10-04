"""O Relatório de Checagem descritivo (ADR-035) — um teste por bloco.

Os relatórios de entrada são os que as regras reais gravaram para dois degraus
da escada do Estrela I, sem rede (`scripts/rodar_cenario.py E0` e `E3`, em
`tests/fixtures/parecer/`): o caso base, pobre em informação (0 C / 3 NC /
11 NA), e o teto (6 C / 4 NC / 4 NA). Os casos de borda — nenhuma checagem,
consolidado parcial, tudo conforme, só não avaliáveis — são recortes desses
mesmos relatórios, para que nenhum teste dependa de um relatório inventado.
"""

from __future__ import annotations

import copy
import json
import os
import re

import pytest

from app.servicos import motivos, parecer
from app.servicos import relatorios as rel
from tests.conftest import RAIZ

PASTA = os.path.join(RAIZ, "tests", "fixtures", "parecer")
FRASE = ("O empreendimento analisado, o Residencial Estrela I, está situado em "
         "Estrela/RS e é um condomínio de apartamentos que totaliza 300 UHs, "
         "com a unidade tipo Apartamento T+1.")


def _ler(cenario: str, *chaves: str) -> dict[str, dict]:
    chaves = chaves or rel.CHECAGENS
    saida = {}
    for chave in chaves:
        with open(os.path.join(PASTA, cenario, f"{chave}.json"), encoding="utf-8") as f:
            saida[chave] = json.load(f)
    return saida


@pytest.fixture(scope="module")
def e0() -> parecer.Parecer:
    return parecer.montar(_ler("E0"), FRASE)


@pytest.fixture(scope="module")
def e3() -> parecer.Parecer:
    return parecer.montar(_ler("E3"), FRASE)


def _itens(p: parecer.Parecer, destinatario: str) -> dict[str, list[str]]:
    """``{chave do grupo: [ids]}`` das pendências de um destinatário."""
    return {g.chave: [i.requisito for i in g.itens]
            for g in p.pendencias.get(destinatario, ())}


def _todos_os_ids_pendentes(p: parecer.Parecer) -> set[str]:
    return {i.requisito for grupos in p.pendencias.values()
            for g in grupos for i in g.itens}


# --- a tabela motivo → destinatário -------------------------------------------

def test_a_tabela_de_destinatarios_cobre_exatamente_os_17_motivos():
    """Motivo novo na taxonomia sem destinatário quebraria em silêncio o
    bloco de pendências: aqui ele quebra o teste (ADR-035)."""
    assert set(parecer.DESTINATARIO) == set(motivos.ROTULO)
    assert len(parecer.DESTINATARIO) == 17


def test_so_nao_aplicavel_prerequisito_e_agregacao_ficam_sem_destinatario():
    sem = {m for m, d in parecer.DESTINATARIO.items() if d is None}
    assert sem == {motivos.NAO_APLICAVEL, motivos.PREREQUISITO_FALHO,
                   motivos.AGREGACAO_INDECISA}


def test_todo_motivo_com_destinatario_tem_acao_redigida():
    for motivo, dest in parecer.DESTINATARIO.items():
        if dest is not None:
            assert parecer.acao_de(motivo), motivo


# --- 1 · abertura -------------------------------------------------------------

def test_abertura_traz_a_frase_as_checagens_e_as_contagens(e0):
    assert e0.abertura.startswith(FRASE)
    assert "Foram executadas as cinco checagens do protótipo" in e0.abertura
    assert ("14 requisitos da Portaria MCID nº 725/2023: nenhum conforme, "
            "3 não conformes e 11 não avaliáveis") in e0.abertura


def test_abertura_amarra_a_versao_das_declaracoes(e3):
    assert "As declarações consideradas são as da versão 174 das Informações Gerais." in e3.abertura


# --- insumos: a 1.ª frase de cada parágrafo ---------------------------------------

def _paragrafo(p: parecer.Parecer, titulo: str) -> str:
    return dict(p.checagens)[titulo]


def test_enquadramento_amarra_o_terreno_as_escolas_e_a_medida(e0):
    texto = _paragrafo(e0, "Enquadramento")
    assert texto.startswith(
        "Para a análise, foi avaliado o terreno indicado por importação de "
        "arquivo CSV com os vértices da poligonal (E0_memorial.csv, vértices M1 "
        "a M6, EPSG:31982 informado pelo usuário), com área de 95.906,03 m²")
    assert "as escolas vieram do Censo Escolar 2025 (INEP), no recorte de Estrela/RS" in texto
    assert "sem o serviço de cálculo da distância caminhável, as distâncias foram medidas em linha reta" in texto


def test_enquadramento_com_rede_nomeia_o_servico_e_a_malha():
    enq = copy.deepcopy(_ler("E3", "enquadramento")["enquadramento"])
    for linha in enq["por_requisito"]:
        d = linha.get("detalhe") or {}
        if "roteamento_de_rede" in d:
            d["roteamento_de_rede"] = {"provedor": "ors", "procedencia_malha": {
                "osm_date": "2026-09-07T00:00:04Z"}}
    texto = _paragrafo(parecer.montar({"enquadramento": enq}), "Enquadramento")
    assert ("as distâncias foram medidas pelo serviço de cálculo da distância caminhável (ORS, "
            "malha OpenStreetMap de 07/09/2026)") in texto


def test_qualificacao_amarra_a_declaracao_e_a_populacao(e3):
    texto = _paragrafo(e3, "Qualificação Urbanística")
    assert ("Para a análise, foram usados o número de UHs previstas declarado "
            "em Informações Gerais (300) e a população do município (IBGE — "
            "Censo Demográfico 2022, SIDRA tabela 4714).") in texto


def test_checagens_bim_nomeiam_o_modelo_submetido_sem_o_caminho(e3):
    georref = _paragrafo(e3, "Georreferenciamento do modelo")
    assert georref.startswith("Para a análise, foi utilizado o modelo de "
                              "informações submetido, E3_teto.ifc (IFC4, "
                              "declarado como edificação isolada)")
    assert "limites de Estrela/RS pela malha municipal do IBGE" in georref
    programa = _paragrafo(e3, "Programa de necessidades")
    assert "com 8 UHs representadas), do qual se leram 72 ambientes (IfcSpace)" in programa
    bim_gis = _paragrafo(e3, "Requisitos de projeto (BIM + GIS)")
    assert "do qual se leram 117 revestimentos (IfcCovering)" in bim_gis
    assert "a zona bioclimática do município (2R) veio da ABNT TR 15220-3-1:2024" in bim_gis
    for _, texto in e3.checagens:
        assert "entradas/" not in texto and "estrela_i/" not in texto


def test_cada_paragrafo_diz_quando_a_analise_foi_gravada():
    relatorios = _ler("E3", "georref")
    relatorios["georref"]["gerado_em"] = "2026-09-25T21:00:00+00:00"
    texto = _paragrafo(parecer.montar(relatorios), "Georreferenciamento do modelo")
    assert "Análise gravada em 25/09/2026." in texto


# --- 2 · um parágrafo por checagem ---------------------------------------------

def test_os_titulos_cobrem_exatamente_as_checagens_somadas():
    """Chave somada sem título sumiria do texto; título sem chave falaria de
    uma checagem fora da soma (a garantia que a 2.4.2 tinha com `_ROTULOS`)."""
    assert list(parecer.TITULOS) == list(rel.CHECAGENS)


def test_um_paragrafo_por_checagem_na_ordem_da_arvore(e3):
    assert [t for t, _ in e3.checagens] == [parecer.TITULOS[c] for c in rel.CHECAGENS]


def test_o_paragrafo_nomeia_todo_requisito_da_portaria_verificado(e3):
    for (titulo, paragrafo), chave in zip(e3.checagens, rel.CHECAGENS):
        ids = _ler("E3", chave)[chave]["resumo"]["normativo"]["ids"]
        for rid in ids:
            assert f"{rid}," in paragrafo, (titulo, rid)


def test_nao_conforme_traz_o_exigido_e_o_medido_dos_campos_da_regra(e0):
    georref = dict(e0.checagens)["Georreferenciamento do modelo"]
    assert "EMP-001: não conforme — nível 40 da escala LoGeoRef, para o nível 50" in georref
    assert "(IfcProjectedCRS)" in georref and "(IfcMapConversion)" in georref
    qualif = dict(e0.checagens)["Qualificação Urbanística"]
    assert "pelo limite EMP-025.1: 300 UHs previstas" in qualif
    assert "limite de 100 UHs por empreendimento (excede em 200)" in qualif


def test_conforme_por_ramo_diz_a_zona_e_o_medido(e3):
    bim_gis = dict(e3.checagens)["Requisitos de projeto (BIM + GIS)"]
    assert ("EDI-019: conforme — na zona bioclimática 2R, pelo ramo EDI-019.1: "
            "115 revestimentos de parede externa, maior absortância 0,35, para "
            "o limite de 0,60") in bim_gis


def test_numeros_saem_no_formato_brasileiro(e3):
    programa = dict(e3.checagens)["Programa de necessidades"]
    assert "menor largura 1,49 m, para o mínimo de 1,50 m" in programa
    assert "1.49" not in programa


def test_nao_avaliaveis_sem_alternativas_se_agrupam_pelo_rotulo_do_motivo(e0):
    programa = dict(e0.checagens)["Programa de necessidades"]
    assert ("Não puderam ser avaliados (informação ausente no modelo): EDI-004, "
            "EDI-004.1, EDI-007, EDI-008, EDI-009 e EDI-011.") in programa
    assert ("Não pôde ser avaliado (depende de outra verificação não aprovada): "
            "EDI-002.") in programa


def test_requisito_de_vias_em_aberto_explica_cada_via(e0):
    enq = dict(e0.checagens)["Enquadramento"]
    assert "ENQ-010: não avaliável — basta uma das vias; ENQ-010.1 em aberto" in enq
    assert "ENQ-010.2 em aberto (depende de parecer do analista)" in enq


# --- 3 · limites da análise ------------------------------------------------------

def test_limites_trazem_o_diagnostico_marcado_e_o_recorte(e0):
    assert "O resultado vale para 300 UHs, a partir de um modelo que foi declarado com 8 UHs." in e0.limites
    assert e0.limites[-1] == ("Esta síntese cobre os 14 requisitos da Portaria "
                              "verificados pelo protótipo, não a Portaria inteira.")


def test_limites_trazem_os_ambientes_deixados_de_fora(e3):
    assert any(linha.startswith("10 ambientes do modelo foram deixados de fora")
               for linha in e3.limites)


@pytest.mark.parametrize("nota, ids", [
    (parecer.NOTA_LINHA_RETA, "ENQ-009, ENQ-010 e ENQ-011"),
    (parecer.NOTA_REMETIDA, "ENQ-010 e ENQ-011"),
    (parecer.NOTA_ZONA_SUPERADA, "EDI-024"),
])
def test_nota_padrao_dos_inconclusivos_aparece_uma_vez_com_os_requisitos(e3, nota, ids):
    linhas = [linha for linha in e3.limites if parecer.NOTAS[nota] in linha]
    assert linhas == [f"{ids}: {parecer.NOTAS[nota]}"]


def test_zona_superada_nao_se_anota_em_requisito_decidido(e3):
    """EDI-019 conclui (ramo único aplicável): a nota explica resultado em
    aberto, não a regra em geral."""
    linha = next(x for x in e3.limites if parecer.NOTAS[parecer.NOTA_ZONA_SUPERADA] in x)
    assert "EDI-019" not in linha


# --- 4 · pendências ----------------------------------------------------------------

def test_nao_conformidades_vao_ao_proponente_primeiro(e0):
    grupos = e0.pendencias[parecer.PROPONENTE]
    assert grupos[0].chave == parecer.NAO_CONFORMIDADE
    assert grupos[0].acao == parecer.ACAO_NAO_CONFORMIDADE
    assert [i.requisito for i in grupos[0].itens] == ["ENQ-009", "EMP-025", "EMP-001"]


def test_informacao_ausente_vai_ao_proponente_com_a_acao_do_motivo(e0):
    grupos = {g.chave: g for g in e0.pendencias[parecer.PROPONENTE]}
    g = grupos[motivos.INFORMACAO_AUSENTE]
    assert g.acao == motivos.ACAO[motivos.INFORMACAO_AUSENTE]
    assert [i.requisito for i in g.itens] == [
        "EDI-004", "EDI-004.1", "EDI-007", "EDI-008", "EDI-009", "EDI-011",
        "EDI-019", "EDI-024"]


def test_via_de_requisito_decidido_nao_gera_pendencia(e0):
    """EMP-025 já reprova pelo limite por empreendimento: o grupo de
    contíguos (EMP-025.2) não decide mais nada (ADR-035)."""
    assert "EMP-025.2" not in _todos_os_ids_pendentes(e0)


def test_via_de_requisito_aprovado_nao_gera_pendencia():
    relatorios = _ler("E3", "enquadramento")
    enq = copy.deepcopy(relatorios["enquadramento"])
    for linha in enq["por_requisito"]:
        if linha["requisito"] == "ENQ-010":
            linha["estado"] = "conforme"
            linha["detalhe"].pop(motivos.CHAVE, None)
    p = parecer.montar({"enquadramento": enq})
    ids = _todos_os_ids_pendentes(p)
    assert "ENQ-010.1" not in ids and "ENQ-010.2" not in ids
    assert {"ENQ-011.1", "ENQ-011.2"} <= ids


def test_requisito_de_vias_em_aberto_desdobra_cada_via_no_seu_destinatario(e0):
    assert _itens(e0, parecer.ANALISE_HUMANA) == {
        motivos.ANALISE_HUMANA_DOCUMENTAL: ["ENQ-010.2", "ENQ-011.2"]}
    assert _itens(e0, parecer.FERRAMENTA) == {
        motivos.METRICA_INSUFICIENTE: ["ENQ-010.1", "ENQ-011.1"]}


def test_via_remetida_nomeia_o_insumo_que_falta(e0):
    item = next(i for g in e0.pendencias[parecer.ANALISE_HUMANA] for i in g.itens
                if i.requisito == "ENQ-010.2")
    assert item.complemento == "itinerário do transporte público escolar municipal"


def test_prerequisito_falho_vira_observacao_no_primeiro_prerequisito(e0):
    assert "EDI-002" not in _todos_os_ids_pendentes(e0)
    itens = {i.requisito: i for g in e0.pendencias[parecer.PROPONENTE] for i in g.itens}
    assert itens["EDI-004"].complemento.endswith("o EDI-002 depende deste requisito")
    assert "EDI-002" not in itens["EDI-004.1"].complemento


def test_ramo_nao_aplicavel_nunca_vira_pendencia(e3):
    assert "EDI-019.2" not in _todos_os_ids_pendentes(e3)


def test_ramos_por_zona_pendem_no_proprio_requisito(e3):
    itens = {i.requisito: i for g in e3.pendencias[parecer.PROPONENTE] for i in g.itens}
    assert "EDI-024.1" not in itens and "EDI-024.2" not in itens
    assert itens["EDI-024"].complemento == "2 revestimentos de cobertura sem material identificável"


def test_dependencias_podem_ser_injetadas():
    p = parecer.montar(_ler("E0", "programa"), dependencias={})
    assert "EDI-002" not in _todos_os_ids_pendentes(p)
    itens = {i.requisito: i for g in p.pendencias[parecer.PROPONENTE] for i in g.itens}
    assert "depende deste requisito" not in itens["EDI-004"].complemento


# --- 5 · nota de natureza e texto -------------------------------------------------

def test_nota_de_natureza_com_a_data_das_analises():
    relatorios = _ler("E3", "georref")
    relatorios["georref"]["gerado_em"] = "2026-09-25T21:00:00+00:00"
    p = parecer.montar(relatorios)
    assert p.nota == ("Síntese gerada automaticamente pelo protótipo a partir das "
                      "análises gravadas em 25/09/2026. Cada frase decorre de um "
                      "requisito verificado. Não substitui o parecer do analista.")


def test_o_texto_nao_cita_adr_dn_nem_caminho(e0, e3):
    for p in (e0, e3):
        texto = p.texto()
        assert not re.search(r"\b(ADR|DN)-\d", texto)
        assert "artefatos/" not in texto and "entradas/" not in texto


def test_mesmo_relatorio_mesmo_texto():
    assert (parecer.montar(_ler("E3"), FRASE).texto()
            == parecer.montar(_ler("E3"), FRASE).texto())


# --- casos de borda -------------------------------------------------------------

def test_nenhuma_checagem():
    p = parecer.montar({}, FRASE)
    assert p.vazio
    assert p.abertura == (f"{FRASE} Nenhuma checagem foi executada para este "
                          "empreendimento; não há o que relatar.")
    assert "Pendências" not in p.texto()


def test_consolidado_parcial_diz_o_que_nao_rodou():
    p = parecer.montar(_ler("E3", "georref", "programa"))
    assert "Foram executadas duas das cinco checagens do protótipo" in p.abertura
    assert ("Não foram executadas: Enquadramento, Qualificação Urbanística e "
            "Requisitos de projeto (BIM + GIS); os requisitos dessas checagens "
            "não entram nesta síntese.") in p.limites


def test_tudo_conforme_nao_tem_pendencia():
    p = parecer.montar(_ler("E3", "georref"))
    assert not any(p.pendencias.values())
    assert "Nenhuma pendência decorre desta análise." in p.texto()
    assert "Foi executada uma das cinco checagens" in p.abertura


def test_so_nao_avaliaveis():
    p = parecer.montar(_ler("E0", "programa"))
    assert "nenhum conforme, nenhum não conforme e 7 não avaliáveis" in p.abertura
    assert _itens(p, parecer.PROPONENTE).keys() == {motivos.INFORMACAO_AUSENTE}


# --- 6 · arquivos analisados --------------------------------------------------------

SHA_E3 = "d8204053d5b6de93848e7302e73cb992ec6ae4a4c7fadeb619893c7a451c2197"
SHA_MEMORIAL = "329a9d4a0d564acd792d9f3432a0420debd1d551bac5f1c5574026c23cea94d8"


def test_arquivos_analisados_com_a_impressao_digital_sem_repetir(e3):
    assert e3.arquivos == (f"E0_memorial.csv — SHA-256 {SHA_MEMORIAL}",
                           f"E3_teto.ifc — SHA-256 {SHA_E3}")
    assert "**Arquivos analisados.**" in e3.texto()


def test_a_impressao_fica_fora_do_corpo_do_texto(e3):
    """O parágrafo cita o nome; o SHA só na seção do fim."""
    for _, paragrafo in e3.checagens:
        assert not re.search(r"[0-9a-f]{64}", paragrafo)
    assert not re.search(r"[0-9a-f]{64}", e3.abertura)


def test_relatorio_sem_registro_de_arquivos_declara_a_falta():
    relatorios = _ler("E3", "georref")
    relatorios["georref"]["meta"].pop("arquivos")
    assert parecer.montar(relatorios).arquivos == (
        "E3_teto.ifc — impressão digital não registrada nesta análise",
        "E0_memorial.csv — impressão digital não registrada nesta análise")
