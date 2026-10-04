"""ADR-004 — repositório ``empreendimento.json``, que absorve o ``terreno.json``."""

from __future__ import annotations

import json

from core.dominio import ancora
from core.dominio.edificacao import Edificacao
from core.dominio.empreendimento import Empreendimento, Localizacao, ModeloBIM
from core.dominio.terreno import Terreno
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec
from core.infra.persistencia import artefato
from core.infra.persistencia import empreendimento_json as repo
from tests.conftest import FIXTURES


def _terreno(procedencia=None):
    return Terreno(origem="desenhada", nivel="ponto", precisao="aproximada",
                   crs_metrico="EPSG:31982", centro_wgs84=(-29.48, -51.94),
                   procedencia=procedencia or {})


def test_ida_e_volta(tmp_path):
    emp = Empreendimento(nome="Estrela I", localizacao=Localizacao("4307807", "RS", "Estrela"),
                         declaracoes={dec.ARRANJO: dec.CONDOMINIO}, terreno=_terreno(),
                         unidades_tipo=[UnidadeTipo(
                             nome="Torre A", unidades=4, tipologia=dec.APARTAMENTO,
                             modelo=ModeloBIM(caminho="m.ifc",
                                              natureza=dec.EDIFICACAO_ISOLADA,
                                              unidades_representadas=4))])
    emp.renomear("Estrela I — lote 2")
    destino = repo.gravar(emp, str(tmp_path))
    assert destino.endswith(repo.NOME_ARQUIVO)
    gravado = json.loads((tmp_path / repo.NOME_ARQUIVO).read_text(encoding="utf-8"))
    assert "gravado_em" in gravado
    lido = repo.ler(str(tmp_path))
    assert lido == emp and lido.versao == 2 and lido.to_dict() == emp.to_dict()
    assert not list(tmp_path.glob("*.tmp")), "escrita atômica não deixa lixo"


def test_nada_gravado_devolve_none(tmp_path):
    assert repo.ler(str(tmp_path)) is None


def test_ilegivel_devolve_none_e_nao_ressuscita_o_terreno_antigo(tmp_path):
    artefato.gravar(_terreno(), str(tmp_path))
    (tmp_path / repo.NOME_ARQUIVO).write_text("{nao e json", encoding="utf-8")
    assert repo.ler(str(tmp_path)) is None


def test_migra_o_terreno_json_legado_com_a_localizacao_declarada(tmp_path):
    proc = {"municipio_declarado": {"uf": "RS", "nome": "Estrela", "ibge": "4307807"}}
    artefato.gravar(_terreno(proc), str(tmp_path))
    emp = repo.ler(str(tmp_path))
    assert emp is not None and emp.terreno.centro_wgs84 == (-29.48, -51.94)
    assert emp.localizacao == Localizacao("4307807", "RS", "Estrela")
    assert not (tmp_path / repo.NOME_ARQUIVO).exists(), "ler não grava"


def test_migracao_com_codigo_invalido_mantem_o_terreno_sem_localizacao(tmp_path):
    artefato.gravar(_terreno({"municipio_declarado": {"ibge": "123"}}), str(tmp_path))
    emp = repo.ler(str(tmp_path))
    assert emp.terreno is not None and emp.localizacao is None


def test_o_gravado_prevalece_sobre_o_legado(tmp_path):
    artefato.gravar(_terreno(), str(tmp_path))
    emp = Empreendimento(nome="novo")
    repo.gravar(emp, str(tmp_path))
    assert repo.ler(str(tmp_path)).nome == "novo"


def test_descartar_remove_os_dois(tmp_path):
    artefato.gravar(_terreno(), str(tmp_path))
    repo.gravar(Empreendimento(), str(tmp_path))
    repo.descartar(str(tmp_path))
    assert repo.ler(str(tmp_path)) is None
    repo.descartar(str(tmp_path))       # idempotente


# ---------------------------------------------------------------------------
# Migração do esquema E0 (ADR-021, ADR-023)
# ---------------------------------------------------------------------------
#
# O esquema antigo é o que o código gravava até o commit 813219f: sem
# ``edificacoes``/``unidades_tipo``, sem ``unidades_previstas`` e sem
# ``unidades_representadas`` dentro do ``modelo``. Em vez de escrever esse JSON
# à mão, os testes abaixo o produzem com o ``to_dict`` de hoje e **retiram** as
# chaves acrescentadas desde então — assim o formato de partida continua sendo
# o do código, e não a lembrança que alguém tinha dele.

CHAVES_POSTERIORES_AO_E0 = ("unidades_previstas", "unidades_tipo", "edificacoes")


def _gravar_no_esquema_antigo(emp: Empreendimento, pasta, natureza: str = "") -> None:
    """Grava ``emp`` como o código do esquema E0 gravaria.

    A chave ``modelo`` na raiz entra AQUI, e não vem mais de ``to_dict``: o
    ``Empreendimento`` não tem esse campo (ADR-023), e quem reconhece a
    chave é só a migração. É exatamente o que estes testes exercitam — ler um
    arquivo que o código de hoje não seria capaz de escrever."""
    dados = emp.to_dict()
    for chave in CHAVES_POSTERIORES_AO_E0:
        dados.pop(chave, None)
    dados["modelo"] = ({"caminho": "m.ifc", "schema": "", "natureza": natureza,
                        "digest": ""} if natureza else None)
    if dados.get("terreno"):
        dados["terreno"].pop("modelo", None)
    (pasta / repo.NOME_ARQUIVO).write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _antigo(*, declaracoes=None, terreno=None) -> Empreendimento:
    return Empreendimento(
        nome="Estrela I", localizacao=Localizacao("4307807", "RS", "Estrela"),
        declaracoes=declaracoes if declaracoes is not None else
        {repo.CHAVE_NUM_UHS_LEGADA: 3, dec.TIPOLOGIA: dec.APARTAMENTO},
        terreno=terreno)


def test_artefato_antigo_sintetiza_a_unidade_tipo_1(tmp_path):
    """Uma unidade tipo, com o que as declarações antigas diziam (ADR-021)."""
    _gravar_no_esquema_antigo(_antigo(), tmp_path, dec.EDIFICACAO_ISOLADA)
    emp = repo.ler(str(tmp_path))
    assert len(emp.unidades_tipo) == 1
    unidade_tipo = emp.unidades_tipo[0]
    assert unidade_tipo.nome == repo.NOME_UNIDADE_TIPO_SINTETIZADA
    assert unidade_tipo.unidades == 3 and unidade_tipo.tipologia == dec.APARTAMENTO
    assert unidade_tipo.modelo.caminho == "m.ifc"
    assert unidade_tipo.unidades_representadas == 3


def test_a_migracao_nao_mexe_na_versao_e_o_conteiner_so_tem_um_dono(tmp_path):
    """A leitura não marca como desatualizado o relatório já gravado — e o
    contêiner do esquema antigo passa a ter UM lugar só."""
    antigo = _antigo()
    antigo.renomear("Estrela I — lote 2")         # versão 2
    _gravar_no_esquema_antigo(antigo, tmp_path, dec.EDIFICACAO_ISOLADA)
    emp = repo.ler(str(tmp_path))
    assert not hasattr(emp, "modelo"), "o campo legado saiu do domínio"
    assert emp.unidades_tipo[0].modelo == ModeloBIM(
        caminho="m.ifc", natureza=dec.EDIFICACAO_ISOLADA, unidades_representadas=3)
    assert emp.versao == 2
    assert emp.unidades_previstas == 0, "previstas não é num_uhs (ADR-021)"


def test_conteiner_de_terreno_vai_para_o_terreno_e_nao_representa_uh(tmp_path):
    _gravar_no_esquema_antigo(_antigo(declaracoes={}, terreno=_terreno()),
                              tmp_path, dec.TERRENO)
    emp = repo.ler(str(tmp_path))
    assert emp.terreno.modelo.caminho == "m.ifc"
    assert emp.terreno.modelo.unidades_representadas == 0
    assert emp.unidades_tipo == [], "só terreno declarado; nada a sintetizar"


def test_terreno_com_edificacoes_anexa_o_mesmo_conteiner_aos_dois(tmp_path):
    _gravar_no_esquema_antigo(_antigo(terreno=_terreno()), tmp_path,
                              dec.TERRENO_COM_EDIFICACOES)
    emp = repo.ler(str(tmp_path))
    assert emp.terreno.modelo == emp.unidades_tipo[0].modelo
    assert emp.unidades_tipo[0].unidades_representadas == 3


def test_artefato_antigo_sem_declaracao_nenhuma_nao_inventa_unidade_tipo(tmp_path):
    _gravar_no_esquema_antigo(_antigo(declaracoes={}), tmp_path)
    emp = repo.ler(str(tmp_path))
    assert emp.unidades_tipo == [] and emp.nome == "Estrela I"


def test_num_uhs_ilegivel_nao_derruba_a_leitura(tmp_path):
    _gravar_no_esquema_antigo(
        _antigo(declaracoes={repo.CHAVE_NUM_UHS_LEGADA: "três",
                             dec.TIPOLOGIA: dec.CASA}),
        tmp_path, dec.EDIFICACAO_ISOLADA)
    emp = repo.ler(str(tmp_path))
    assert emp.unidades_tipo[0].unidades == 0
    assert emp.unidades_tipo[0].tipologia == dec.CASA


def test_artefato_novo_sem_unidades_tipo_permanece_sem_unidades_tipo(tmp_path):
    """A chave presente e vazia é declaração de que não há — não é artefato velho."""
    repo.gravar(_antigo(), str(tmp_path))
    assert repo.ler(str(tmp_path)).unidades_tipo == []


def test_regravar_o_migrado_fixa_o_esquema_novo(tmp_path):
    _gravar_no_esquema_antigo(_antigo(), tmp_path, dec.EDIFICACAO_ISOLADA)
    migrado = repo.ler(str(tmp_path))
    repo.gravar(migrado, str(tmp_path))
    relido = repo.ler(str(tmp_path))
    assert relido.to_dict() == migrado.to_dict()
    assert relido.unidades_tipo[0].id == migrado.unidades_tipo[0].id


def test_empreendimento_real_do_estrela_i(tmp_path):
    """Artefato **real** do Estrela I, gravado pelo código do esquema
    E0 (terreno marcado no mapa, sem contêiner), com o ``num_uhs`` que a
    tela do Programa de necessidades grava nas declarações."""
    (tmp_path / repo.NOME_ARQUIVO).write_text(
        (FIXTURES / "empreendimento_esquema_antigo.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    emp = repo.ler(str(tmp_path))
    assert emp.nome == "Residencial Estrela I" and emp.versao == 26
    assert emp.terreno is not None and emp.terreno.modelo is None
    assert [ (e.unidades, e.tipologia, e.modelo) for e in emp.unidades_tipo ] == [
        (1, dec.APARTAMENTO, None)]
    assert emp.excedente_declarado == 0


def test_o_terreno_json_legado_continua_sem_unidades_tipo(tmp_path):
    """A migração mais antiga (ADR-004) não tem declarações de onde tirar UH."""
    artefato.gravar(_terreno(), str(tmp_path))
    assert repo.ler(str(tmp_path)).unidades_tipo == []


def test_unidade_tipo_gravada_e_lida_de_volta(tmp_path):
    emp = Empreendimento(nome="misto", unidades_previstas=10, unidades_tipo=[
        UnidadeTipo(nome="Torre A", unidades=6, tipologia=dec.APARTAMENTO,
                   modelo=ModeloBIM(caminho="a.ifc", unidades_representadas=2)),
        UnidadeTipo(nome="Casa 1", unidades=1, tipologia=dec.CASA)])
    repo.gravar(emp, str(tmp_path))
    lido = repo.ler(str(tmp_path))
    assert lido.to_dict() == emp.to_dict()
    assert lido.unidades_declaradas == 7 and lido.declaracao_consistente


# ---------------------------------------------------------------------------
# Migração do esquema E1 — as ``edificacoes`` de então eram unidades tipo
# (ADR-023, D-J)
# ---------------------------------------------------------------------------

def _gravar_no_esquema_e1(dados: dict, pasta) -> None:
    """Grava um dicionário como o código do esquema E1 gravaria: ``edificacoes``
    presente com os campos de unidade tipo, ``unidades_tipo`` ausente."""
    assert "edificacoes" in dados and "unidades_tipo" not in dados
    (pasta / repo.NOME_ARQUIVO).write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _e1(*, edificacoes, terreno=None) -> dict:
    dados = Empreendimento(nome="Estrela I", localizacao=Localizacao("4307807", "RS", "Estrela"),
                           unidades_previstas=120, terreno=terreno).to_dict()
    dados.pop("unidades_tipo")
    dados["edificacoes"] = edificacoes
    return dados


def test_esquema_e1_real_do_estrela_i(tmp_path):
    """Artefato **real** gravado pelo código do esquema E1 (versão 57, dois
    blocos, capturado na Fase R0): cada item vira unidade tipo com o MESMO
    id, e nenhuma edificação física é sintetizada."""
    (tmp_path / repo.NOME_ARQUIVO).write_text(
        (FIXTURES / "empreendimento_esquema_adr020.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    emp = repo.ler(str(tmp_path))
    assert emp.nome == "Residencial Estrela I" and emp.versao == 57
    assert emp.unidades_previstas == 120
    assert [(u.id, u.nome, u.unidades, u.tipologia, u.modelo) for u in emp.unidades_tipo] == [
        ("d6ff0051603f", "Bloco A", 60, dec.APARTAMENTO, None),
        ("97eed0629ba4", "Bloco B", 60, dec.APARTAMENTO, None)]
    assert emp.edificacoes == [], "nenhuma física sintetizada de artefato antigo"
    assert emp.unidades_declaradas == 120 and emp.declaracao_consistente
    assert emp.terreno is not None and emp.terreno.modelo is None


def test_esquema_e1_com_conteiner_duplicado_no_terreno_e_na_unidade_tipo(tmp_path):
    """E0 lido e regravado — "Edificação 1" com contêiner E
    ``terreno.modelo`` igual. O contêiner sobrevive nos dois donos, a
    migração não decide entre eles: quem decide é a precedência da âncora."""
    vo = {"caminho": "m.ifc", "schema": "IFC4", "natureza": dec.TERRENO_COM_EDIFICACOES,
          "digest": "", "unidades_representadas": 1}
    _gravar_no_esquema_e1(_e1(terreno=_terreno(), edificacoes=[
        {"id": "aaaaaaaaaaaa", "nome": "Edificação 1", "unidades": 1,
         "tipologia": dec.APARTAMENTO, "modelo": vo}]), tmp_path)
    dados = json.loads((tmp_path / repo.NOME_ARQUIVO).read_text(encoding="utf-8"))
    dados["terreno"]["modelo"] = vo
    (tmp_path / repo.NOME_ARQUIVO).write_text(json.dumps(dados), encoding="utf-8")

    emp = repo.ler(str(tmp_path))
    assert emp.unidades_tipo[0].id == "aaaaaaaaaaaa"
    assert emp.unidades_tipo[0].modelo == emp.terreno.modelo == ModeloBIM.from_dict(vo)
    assert emp.edificacoes == []
    assert ancora.tipologia_em_analise(emp, emp.terreno.modelo) == dec.APARTAMENTO
    assert ancora.conteiner_em_analise(emp) is emp.unidades_tipo[0].modelo


def test_a_migracao_e1_nao_mexe_na_versao_e_regravar_fixa_o_e2(tmp_path):
    _gravar_no_esquema_e1(_e1(edificacoes=[
        {"id": "aaaaaaaaaaaa", "nome": "Bloco A", "unidades": 60,
         "tipologia": dec.APARTAMENTO, "modelo": None}]), tmp_path)
    migrado = repo.ler(str(tmp_path))
    assert migrado.versao == 1
    repo.gravar(migrado, str(tmp_path))
    gravado = json.loads((tmp_path / repo.NOME_ARQUIVO).read_text(encoding="utf-8"))
    assert gravado["unidades_tipo"][0]["id"] == "aaaaaaaaaaaa"
    assert gravado["edificacoes"] == []
    relido = repo.ler(str(tmp_path))
    assert relido.to_dict() == migrado.to_dict() and relido.versao == 1


def test_esquema_e1_com_edificacoes_vazia_vira_e2_vazio(tmp_path):
    _gravar_no_esquema_e1(_e1(edificacoes=[]), tmp_path)
    emp = repo.ler(str(tmp_path))
    assert emp.unidades_tipo == [] and emp.edificacoes == []


def test_esquema_e2_com_unidades_tipo_presente_nunca_e_migrado(tmp_path):
    """A chave ``unidades_tipo`` é a assinatura do E2: as ``edificacoes`` que
    a acompanham são físicas de verdade e ficam onde estão."""
    padrao = UnidadeTipo(nome="Apto padrão", unidades=100, tipologia=dec.APARTAMENTO)
    emp = Empreendimento(nome="torres", unidades_previstas=100, unidades_tipo=[padrao],
                         edificacoes=[Edificacao(nome="Torre A", composicao={padrao.id: 50},
                                                 modelo=ModeloBIM(caminho="a.ifc",
                                                                  unidades_representadas=6))])
    repo.gravar(emp, str(tmp_path))
    lido = repo.ler(str(tmp_path))
    assert lido.to_dict() == emp.to_dict()
    assert lido.edificacoes[0].composicao == {padrao.id: 50}
    assert lido.tipologia_de(lido.edificacoes[0]) == dec.APARTAMENTO
    assert lido.unidades_compostas(padrao) == 50


def test_esquema_e2_vazio_grava_as_duas_chaves(tmp_path):
    repo.gravar(Empreendimento(), str(tmp_path))
    gravado = json.loads((tmp_path / repo.NOME_ARQUIVO).read_text(encoding="utf-8"))
    assert gravado["unidades_tipo"] == [] and gravado["edificacoes"] == []
