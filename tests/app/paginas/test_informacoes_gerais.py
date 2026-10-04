"""Informações Gerais — 2.1.1 (ADR-004).

`AppTest` da página de verdade — ao contrário de `test_fase3_regras.py`
(funções isoladas), aqui o cenário passa pelos widgets reais (seletor de
UF/Município, texto do nome), exatamente como pede a regra de aplicabilidade: "trocar o município com terreno confirmado → aviso
presente".

Isolado de `artefatos/` real via `app.servicos.empreendimento.ARTEFATOS`
apontado para `tmp_path` — sem isso, o teste dependeria do estado real de
desenvolvimento (o `terreno.json`/`empreendimento.json` do Estrela I) e
poderia passar ou falhar por acidente conforme quem rodou o app por último.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que renderizar")
pytestmark = pytest.mark.interface

from streamlit.testing.v1 import AppTest

from app.servicos import empreendimento as emp_mod
from app.servicos import territorio
from core.dominio.edificacao import Edificacao
from core.dominio.empreendimento import Empreendimento, Localizacao
from core.dominio.modelo_bim import ModeloBIM
from core.dominio.terreno import Terreno
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec
from tests.conftest import RAIZ

CAMINHO_PAGINA = os.path.join(
    RAIZ, "app", "paginas", "checagens", "informacoes_gerais.py")


def _terreno(municipio_declarado: dict | None = None) -> Terreno:
    """Terreno confirmado — com `procedencia["municipio_declarado"]`
    preenchido, como `checagem_enquadramento._confirmar` sempre grava
    (ver o cabeçalho de `informacoes_gerais._aviso_terreno_desatualizado`:
    é este campo, não `emp.localizacao`, que a regra 1 compara)."""
    t = Terreno(origem="mapa", nivel="ponto", precisao="declarada",
               crs_metrico="EPSG:31982", centro_wgs84=(-29.5, -51.96))
    t.procedencia["municipio_declarado"] = municipio_declarado or {
        "uf": "RS", "nome": "Estrela", "ibge": "4307807"}
    return t


def test_pagina_renderiza_sem_exececao_e_sem_empreendimento_ainda(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception


def test_preencher_e_gravar_persiste_o_empreendimento(tmp_path, monkeypatch):
    """Preencher nome + implantação + tipologia (sem terreno confirmado
    ainda) grava `artefatos/empreendimento.json` de verdade — a "escrita
    reativa" que o ADR-004 pede (persistência em `artefatos/empreendimento.
    json`)."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception

    at.text_input(key="nome__geral").set_value("Estrela I").run(timeout=60)
    assert not at.exception

    gravado = emp_mod.ler()
    assert gravado is not None and gravado.nome == "Estrela I"


def test_trocar_municipio_com_terreno_confirmado_avisa_e_oferece_redefinir(
        tmp_path, monkeypatch):
    """Regra 1 do §4.3: a política é "avisa, não corrige" — a nova
    localização é aceita, o terreno não é apagado sozinho, e a tela oferece
    **Redefinir terreno**."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))

    base = territorio._municipios_snapshot()
    if not base:
        pytest.skip("sem config/municipios_ibge.csv gerado neste ambiente")
    outro = next((m for m in base if m.codigo_ibge != "4307807"), None)
    if outro is None:
        pytest.skip("snapshot de municípios não tem alternativa a Estrela/RS")

    emp = Empreendimento(nome="Estrela I",
                         localizacao=Localizacao("4307807", "RS", "Estrela"),
                         terreno=_terreno())
    emp_mod.gravar(emp)

    pares_uf = territorio.municipios.ufs(base)
    idx_uf = next(i for i, (sigla, _) in enumerate(pares_uf) if sigla == outro.uf)

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.session_state["uf__geral"] = idx_uf
    at.session_state["mun__geral"] = outro
    at.run(timeout=60)

    assert not at.exception, "\n".join(str(e) for e in at.exception)
    textos_aviso = [w.value for w in at.warning]
    assert any("terreno do Enquadramento" in t for t in textos_aviso), textos_aviso
    assert any(b.label == "Redefinir terreno" for b in at.button)

    # avisa, não corrige: a localização nova FOI aceita e gravada.
    gravado = emp_mod.ler()
    assert gravado.localizacao.codigo_ibge == outro.codigo_ibge
    # ...e o terreno, sem o clique em "Redefinir", continua lá.
    assert gravado.terreno is not None


def test_clicar_redefinir_terreno_apaga_o_terreno(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))

    base = territorio._municipios_snapshot()
    if not base:
        pytest.skip("sem config/municipios_ibge.csv gerado neste ambiente")
    outro = next((m for m in base if m.codigo_ibge != "4307807"), None)
    if outro is None:
        pytest.skip("snapshot de municípios não tem alternativa a Estrela/RS")

    emp = Empreendimento(nome="Estrela I",
                         localizacao=Localizacao("4307807", "RS", "Estrela"),
                         terreno=_terreno())
    emp_mod.gravar(emp)

    pares_uf = territorio.municipios.ufs(base)
    idx_uf = next(i for i, (sigla, _) in enumerate(pares_uf) if sigla == outro.uf)

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.session_state["uf__geral"] = idx_uf
    at.session_state["mun__geral"] = outro
    at.run(timeout=60)

    (botao,) = [b for b in at.button if b.label == "Redefinir terreno"]
    at = botao.click().run(timeout=60)
    assert not at.exception

    gravado = emp_mod.ler()
    assert gravado.terreno is None


def test_aviso_do_recorte_de_equipamentos_aparece_em_2_1_1(tmp_path, monkeypatch):
    """Regra 2 do §4.3: o aviso do recorte de equipamentos migrou para cá
    (antes vivia em `checagem_enquadramento._aviso_do_recorte`)."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    monkeypatch.setattr(territorio, "carregar_recorte", lambda codigo: None)

    emp = Empreendimento(localizacao=Localizacao("4307807", "RS", "Estrela"))
    emp_mod.gravar(emp)

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception
    textos_aviso = [w.value for w in at.warning]
    assert any("recorte de equipamentos" in t for t in textos_aviso), textos_aviso


# --- ADR-023: os dois sub-formulários e `unidades_previstas` ---------------

def test_adicionar_unidade_tipo_cria_e_persiste(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception

    (botao,) = [b for b in at.button if b.label == "Adicionar unidade tipo"]
    at = botao.click().run(timeout=60)
    assert not at.exception

    gravado = emp_mod.ler()
    assert [u.nome for u in gravado.unidades_tipo] == ["Unidade tipo 1"]


def test_editar_nome_unidades_tipologia_da_unidade_tipo_persiste(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa padrão")])
    emp_mod.gravar(emp)
    alvo = emp.unidades_tipo[0]

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception

    at.text_input(key=f"tipo_nome__{alvo.id}").set_value("Bloco Único")
    at.number_input(key=f"tipo_unidades__{alvo.id}").set_value(56)
    at.selectbox(key=f"tipo_tipologia__{alvo.id}").set_value(
        "Apartamento / casa sobreposta")
    at.run(timeout=60)
    assert not at.exception

    gravado = emp_mod.ler()
    (unidade_tipo,) = gravado.unidades_tipo
    assert unidade_tipo.id == alvo.id, "a mesma unidade tipo, não uma nova"
    assert unidade_tipo.nome == "Bloco Único"
    assert unidade_tipo.unidades == 56
    assert unidade_tipo.tipologia == dec.APARTAMENTO


def test_remover_unidade_tipo_apaga_a_unidade_tipo(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Padrão"),
                                        UnidadeTipo(nome="PCD")])
    emp_mod.gravar(emp)
    alvo = emp.unidades_tipo[0]

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception

    (botao,) = [b for b in at.button if b.key == f"tipo_remover__{alvo.id}"]
    at = botao.click().run(timeout=60)
    assert not at.exception

    gravado = emp_mod.ler()
    assert [u.nome for u in gravado.unidades_tipo] == ["PCD"]


def test_unidades_previstas_persiste(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception

    at.number_input(key="previstas__geral").set_value(64).run(timeout=60)
    assert not at.exception

    assert emp_mod.ler().unidades_previstas == 64


def test_adicionar_edificacao_e_compor_persiste(tmp_path, monkeypatch):
    """A edificação física nasce vazia e ganha composição — que é o único
    caminho pelo qual a interface declara a quem as UHs pertencem (ADR-023)."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa padrão",
                                                    unidades=16)])
    emp_mod.gravar(emp)
    tipo = emp.unidades_tipo[0]

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception

    (botao,) = [b for b in at.button if b.label == "Adicionar edificação"]
    at = botao.click().run(timeout=60)
    assert not at.exception

    gravado = emp_mod.ler()
    (edificacao,) = gravado.edificacoes
    assert edificacao.nome == "Edificação 1"
    assert edificacao.composicao == {}, "nasce sem composição declarada"

    at.number_input(key=f"edif_comp__{edificacao.id}__{tipo.id}").set_value(16)
    at.run(timeout=60)
    assert not at.exception

    assert emp_mod.ler().edificacoes[0].composicao == {tipo.id: 16}


def test_remover_unidade_tipo_limpa_a_composicao_que_a_citava(tmp_path, monkeypatch):
    """O cascade da raiz visto pela tela: a composição não sobrevive ao tipo
    que ela cita (ADR-023)."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    tipo = UnidadeTipo(nome="Casa padrão", unidades=16)
    emp = Empreendimento(unidades_tipo=[tipo],
                         edificacoes=[Edificacao(nome="Torre A",
                                                 composicao={tipo.id: 16})])
    emp_mod.gravar(emp)

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception

    (botao,) = [b for b in at.button if b.key == f"tipo_remover__{tipo.id}"]
    at = botao.click().run(timeout=60)
    assert not at.exception

    gravado = emp_mod.ler()
    assert gravado.unidades_tipo == []
    assert gravado.edificacoes[0].composicao == {}


def test_conteiner_anexado_aparece_no_resumo_da_unidade_tipo(tmp_path, monkeypatch):
    """O contêiner só é mostrado — quem o anexa é a tela de checagem, nunca
    2.1.1 (ver o cabeçalho do módulo da página)."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    modelo = ModeloBIM(caminho="entradas/ifc/estrela.ifc",
                       natureza=dec.EDIFICACAO_ISOLADA, unidades_representadas=1)
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa padrão",
                                                    modelo=modelo)])
    emp_mod.gravar(emp)

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception
    textos = [c.value for c in at.caption]
    assert any("estrela.ifc" in t and "1 UH(s) representada" in t
               for t in textos), textos


def test_sem_conteiner_o_resumo_nao_promete_o_que_nao_acontece(tmp_path, monkeypatch):
    """O contêiner de uma análise é efêmero: analisar um IFC numa checagem
    **não** preenche esta linha. Dizer "nenhum enviado ainda" mandava o usuário
    procurar na tela, depois de analisar, uma mudança que nunca vem."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa padrão")])
    emp_mod.gravar(emp)

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception
    textos = [c.value for c in at.caption]
    assert any("informado a cada análise" in t for t in textos), textos
    assert not any("nenhum enviado ainda" in t for t in textos), textos


# --- Regressões observadas em tela -----------------------------
#
# Os três primeiros passaram despercebidos pela suíte da R2 porque ela olhava
# só o que ficou GRAVADO depois do clique — e o que estava errado era a tela
# não ser redesenhada. Estes testes olham os widgets da mesma execução.

def test_adicionar_unidade_tipo_mostra_o_cartao_na_hora(tmp_path, monkeypatch):
    """Sem o `st.rerun`, o cartão novo só aparecia na interação seguinte — e
    clicar de novo criava uma segunda unidade tipo."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp_mod.gravar(Empreendimento())

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    (botao,) = [b for b in at.button if b.label == "Adicionar unidade tipo"]
    at = botao.click().run(timeout=60)
    assert not at.exception

    (gravada,) = emp_mod.ler().unidades_tipo
    chaves_na_tela = [w.key for w in at.text_input]
    assert f"tipo_nome__{gravada.id}" in chaves_na_tela, chaves_na_tela


def test_remover_unidade_tipo_tira_o_cartao_na_hora(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    alvo = UnidadeTipo(nome="Casa padrão")
    emp_mod.gravar(Empreendimento(unidades_tipo=[alvo]))

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    (botao,) = [b for b in at.button if b.key == f"tipo_remover__{alvo.id}"]
    at = botao.click().run(timeout=60)
    assert not at.exception

    assert emp_mod.ler().unidades_tipo == []
    chaves_na_tela = [w.key for w in at.text_input]
    assert f"tipo_nome__{alvo.id}" not in chaves_na_tela, chaves_na_tela


def test_adicionar_edificacao_mostra_o_cartao_na_hora(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp_mod.gravar(Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa")]))

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    (botao,) = [b for b in at.button if b.label == "Adicionar edificação"]
    at = botao.click().run(timeout=60)
    assert not at.exception

    (gravada,) = emp_mod.ler().edificacoes
    chaves_na_tela = [w.key for w in at.text_input]
    assert f"edif_nome__{gravada.id}" in chaves_na_tela, chaves_na_tela


def test_tipologia_mista_vira_erro_de_tela_e_nao_e_aplicada(tmp_path, monkeypatch):
    """Trocar a tipologia de uma unidade tipo já composta torna mista a
    composição de quem a cita — e quem recusa aí é `definir_unidades_tipo`,
    não `definir_edificacoes`. A tela quebrava antes de chegar à mensagem."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    casa = UnidadeTipo(nome="Casa", unidades=5, tipologia=dec.CASA)
    outra = UnidadeTipo(nome="Outra", unidades=5, tipologia=dec.CASA)
    emp_mod.gravar(Empreendimento(
        unidades_tipo=[casa, outra],
        edificacoes=[Edificacao(nome="Torre A",
                                composicao={casa.id: 5, outra.id: 5})]))

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    at.selectbox(key=f"tipo_tipologia__{outra.id}").set_value(
        "Apartamento / casa sobreposta")
    at = at.run(timeout=60)

    assert not at.exception, "a tela não pode morrer pelo invariante da raiz"
    erros = [e.value for e in at.error]
    assert any("tipologias diferentes" in e for e in erros), erros
    assert any("não foi aplicada" in e for e in erros), erros
    gravado = emp_mod.ler()
    assert {u.tipologia for u in gravado.unidades_tipo} == {dec.CASA}
    assert gravado.edificacoes[0].composicao == {casa.id: 5, outra.id: 5}


def _expander_de_edificacoes(at):
    (expander,) = [e for e in at.status if e.proto.label.startswith("Edificações")]
    return expander


def test_o_expander_de_edificacoes_fica_aberto_quando_ha_alguma(tmp_path, monkeypatch):
    """O Streamlit não guarda o estado do expander entre execuções, e cada
    campo editado é uma execução: com `expanded` fixo em `False` o
    sub-formulário se fechava a cada tecla."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp_mod.gravar(Empreendimento(edificacoes=[Edificacao(nome="Torre A")]))

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception
    # `st.expander(icon=...)` é classificado como `Status` pela AppTest — ver
    # a nota em `tests/app/test_main_navegacao.py`. A página tem também o
    # "O que esta página faz" (ADR-034): o de edificações se acha pelo rótulo.
    expander = _expander_de_edificacoes(at)
    assert expander.proto.expanded


def test_o_expander_de_edificacoes_nasce_retraido(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp_mod.gravar(Empreendimento())

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception
    expander = _expander_de_edificacoes(at)
    assert not expander.proto.expanded


def test_rotulo_das_uhs_previstas(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert at.number_input(key="previstas__geral").label == (
        "Quantidade de UHs previstas para o empreendimento")


# ---------------------------------------------------------------------------
# Gravação: só quando algo mudou; chave fora do vocabulário sai com aviso
# ---------------------------------------------------------------------------

def test_reexecutar_sem_mudar_nada_nao_grava(tmp_path, monkeypatch):
    """Render não é efeito colateral: a segunda execução, sem nenhum widget
    mexido, não chama `gravar` — e a `versao` do artefato não anda."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception
    versao = emp_mod.ler().versao

    chamadas = []
    original = emp_mod.gravar
    monkeypatch.setattr(emp_mod, "gravar",
                        lambda emp: chamadas.append(emp.versao) or original(emp))
    at.run(timeout=60)
    at.run(timeout=60)
    assert not at.exception
    assert chamadas == []
    assert emp_mod.ler().versao == versao


def test_declaracao_fora_do_vocabulario_sai_com_aviso(tmp_path, monkeypatch):
    """O `num_uhs` legado (ADR-021) é descartado ao gravar — e a tela diz."""
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp_mod.gravar(Empreendimento(
        nome="Estrela I",
        declaracoes={dec.ARRANJO: dec.CONDOMINIO, "num_uhs": 1}))

    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception
    assert any("num_uhs" in w.value for w in at.warning), [w.value for w in at.warning]
    gravado = emp_mod.ler()
    assert "num_uhs" not in gravado.declaracoes
    assert gravado.declaracoes[dec.ARRANJO] == dec.CONDOMINIO
