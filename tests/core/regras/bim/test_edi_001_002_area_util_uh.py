"""Testes de EDI-001 / EDI-002 (área útil mínima da UH).

Isola ``_checar_area_util`` de ``core.regras.bim.edi_001_002_area_util_uh``:
não passa pelo executor (sem gate de dependências/aplicabilidade) nem pela
agregação — só ``EDI001().checar(ctx)`` / ``EDI002().checar(ctx)`` direto,
com ``core.infra.ifc.extrator_ambientes.listar`` substituído (monkeypatch)
por uma lista fixa de :class:`Ambiente`, sem IfcOpenShell.

O "não avaliável" testado aqui é o caminho interno da própria regra (soma
abaixo do mínimo com ambiente sem área declarada — ver docstring de
``_checar_area_util``), não o motivo da taxonomia do ADR-006: aquele é
atribuído pelo executor (``core/aplicacao/executor.py``, gates de
aplicabilidade/terreno/dependência/IDS/erro), antes de ``checar`` ser
chamado, e já tem cobertura própria em ``tests/core/aplicacao/
test_executor.py``. Mesmo padrão de ``tests/core/regras/bim/
test_emp_001.py::test_emp001_nao_avaliavel_sem_modelo``.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Estado
from core.dominio.edificacao import Ambiente
from core.dominio.empreendimento import Empreendimento
from core.dominio.modelo_bim import ModeloBIM
from core.dominio.unidade_tipo import UnidadeTipo
from core.regras.bim.edi_001_002_area_util_uh import EDI001, EDI002
from tests.apoio.contexto_bim import contexto_bim


def _ctx(ambientes, *, num_uhs=None, modelo=object()):
    # ADR-021: o denominador é quantas UHs o CONTÊINER representa, não uma
    # declaração do empreendimento — daí o número entrar pelo `ModeloBIM`.
    unidades_tipo = ([UnidadeTipo(modelo=ModeloBIM(unidades_representadas=num_uhs))]
                   if num_uhs else [])
    return contexto_bim(modelo_ifc=modelo,
                        empreendimento=Empreendimento(unidades_tipo=unidades_tipo)), ambientes


def _checar(regra_cls, ctx_ambientes, monkeypatch):
    ctx, ambientes = ctx_ambientes
    monkeypatch.setattr("core.infra.ifc.extrator_ambientes.listar",
                        lambda modelo: ambientes)
    return regra_cls().checar(ctx)


# --- EDI-001 (casa, ≥ 40,00 m²) --------------------------------------------

def test_edi001_conforme_area_suficiente(monkeypatch):
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=45.0)]
    r = _checar(EDI001, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.CONFORME
    assert r.detalhe["area_util_total"] == 45.0


def test_edi001_nao_conforme_area_insuficiente(monkeypatch):
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=20.0)]
    r = _checar(EDI001, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["ambientes_sem_area"] == []


def test_edi001_nao_avaliavel_soma_incompleta_por_ambiente_sem_area(monkeypatch):
    # Soma medida (20 m²) fica abaixo do mínimo (40 m²), mas há um ambiente
    # sem área declarada: a soma pode estar subestimada -> não avaliável, em
    # vez de reprovar indevidamente (robustez documentada na regra).
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=20.0),
                 Ambiente(global_id="A2", nome="Cozinha", area_m2=None)]
    r = _checar(EDI001, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe["ambientes_sem_area"] == ["Cozinha"]


def test_edi001_normaliza_minimo_pelo_numero_de_uhs(monkeypatch):
    # 2 UHs -> mínimo 80 m²; 45 m² não atende mais.
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=45.0)]
    r = _checar(EDI001, _ctx(ambientes, num_uhs=2), monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["area_min"] == 80.0


# --- EDI-002 (apartamento/casa sobreposta, ≥ 41,50 m², incl. varanda) -----

def test_edi002_conforme_area_suficiente(monkeypatch):
    # 40,0 m² principais + 2,0 m² de varanda. Com 30,0 + 12,0 a soma seria 42,0 m²,
    # mas só 30,0 m² principais, e o segundo limite do item 2.I.a.ii reprova.
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=40.0),
                 Ambiente(global_id="A2", nome="Varanda", area_m2=2.0)]
    r = _checar(EDI002, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.CONFORME
    assert r.detalhe["area_util_total"] == 42.0


def test_edi002_nao_conforme_area_insuficiente(monkeypatch):
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=30.0)]
    r = _checar(EDI002, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.NAO_CONFORME


def test_edi001_nao_le_mais_o_numero_das_declaracoes(monkeypatch):
    """Guarda do ADR-021: o denominador é do contêiner. Uma chave ``num_uhs``
    sobrevivente nas declarações de um artefato antigo não volta a multiplicar
    o mínimo — 45 m² continuam atendendo a uma UH."""
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=45.0)]
    ctx = (contexto_bim(modelo_ifc=object(),
                        empreendimento=Empreendimento(declaracoes={"num_uhs": 2})),
           ambientes)
    r = _checar(EDI001, ctx, monkeypatch)
    assert r.estado is Estado.CONFORME and r.detalhe["area_min"] == 40.0


# --- Os não avaliáveis da própria regra levam motivo (ADR-006/022) ---
#
# Dois caminhos internos de ``_checar_area_util`` produzem NÃO AVALIÁVEL sem
# passar pelo executor: nenhum ``IfcSpace`` e soma abaixo do mínimo com
# ambiente sem área. Os dois são conteúdo que o requisito de informação
# (ADR-007) exigiria e o modelo não traz — ``informacao_ausente``. Sem o
# motivo, o ``detalhe`` sairia vazio.

def test_edi002_sem_ifcspace_sai_com_motivo_informacao_ausente(monkeypatch):
    from core.dominio.vocabulario import motivos

    r = _checar(EDI002, _ctx([]), monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert "Nenhum ambiente" in r.mensagem
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE


def test_edi001_soma_incompleta_sai_com_motivo_informacao_ausente(monkeypatch):
    from core.dominio.vocabulario import motivos

    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=20.0),
                 Ambiente(global_id="A2", nome="Cozinha", area_m2=None)]
    r = _checar(EDI001, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE
    # O diagnóstico da soma continua viajando ao lado do motivo.
    assert r.detalhe["ambientes_sem_area"] == ["Cozinha"]


# --- O EDI-002 tem dois limites na mesma regra ------------------------
#
# Anexo III, item 2.I.a.ii: 41,50 m² de área útil COM varanda e 40,00 m² de
# área principal. Área principal = soma dos ambientes que não são varanda.
# Comparar só a soma com 41,50 m² aprovaria uma UH com varanda de 2,00 m² e
# 39,50 m² de área principal.

def test_edi002_declara_os_dois_limites_no_mesmo_parametro():
    assert EDI002.parametro == {"area_util_min_m2": 41.50,
                                "area_principal_min_m2": 40.00}


def test_edi001_segue_com_limite_unico(monkeypatch):
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=45.0)]
    r = _checar(EDI001, _ctx(ambientes), monkeypatch)
    assert "area_principal" not in r.detalhe
    assert "area_principal_min" not in r.detalhe


def test_edi002_total_bate_mas_area_principal_reprova(monkeypatch):
    """O caso dos dois limites: 41,50 m² no total, 2,00 m² de varanda, 39,50 m² principais."""
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=39.5),
                 Ambiente(global_id="A2", nome="Varanda", area_m2=2.0)]
    r = _checar(EDI002, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["area_util_total"] == 41.5
    assert r.detalhe["area_varanda"] == 2.0
    assert r.detalhe["area_principal"] == 39.5
    assert r.detalhe["atende_area_util"] is True
    assert r.detalhe["atende_area_principal"] is False
    assert r.detalhe["atende"] is False


def test_edi002_caso_limite_nos_dois_limites_e_conforme(monkeypatch):
    # 40,00 m² principais + 1,50 m² de varanda: exatamente nos dois mínimos.
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=40.0),
                 Ambiente(global_id="A2", nome="Varanda", area_m2=1.5)]
    r = _checar(EDI002, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.CONFORME
    assert r.detalhe["area_principal"] == 40.0
    assert r.detalhe["atende"] is True


def test_edi002_area_principal_bate_mas_total_reprova(monkeypatch):
    # 40,00 m² principais e 1,40 m² de varanda: 41,40 m² < 41,50 m².
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=40.0),
                 Ambiente(global_id="A2", nome="Varanda", area_m2=1.4)]
    r = _checar(EDI002, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["atende_area_util"] is False
    assert r.detalhe["atende_area_principal"] is True


def test_edi002_sacada_conta_como_varanda(monkeypatch):
    # A categoria vem da classificação nominal, não do nome exato "Varanda".
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=39.5),
                 Ambiente(global_id="A2", nome="Sacada", area_m2=2.0)]
    r = _checar(EDI002, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["area_varanda"] == 2.0


def test_edi002_sem_varanda_a_area_principal_e_o_total(monkeypatch):
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=42.0)]
    r = _checar(EDI002, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.CONFORME
    assert r.detalhe["area_varanda"] == 0.0
    assert r.detalhe["area_principal"] == 42.0


def test_edi002_mostra_os_dois_limites_na_mensagem_e_nos_valores(monkeypatch):
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=39.5),
                 Ambiente(global_id="A2", nome="Varanda", area_m2=2.0)]
    r = _checar(EDI002, _ctx(ambientes), monkeypatch)
    assert "41.50" in r.valor_esperado and "40.00" in r.valor_esperado
    assert "39.50" in r.valor_encontrado and "41.50" in r.valor_encontrado
    assert "41.50" in r.mensagem and "39.50" in r.mensagem and "40.00" in r.mensagem


def test_edi002_area_principal_abaixo_com_ambiente_sem_area_e_nao_avaliavel(monkeypatch):
    from core.dominio.vocabulario import motivos

    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=39.5),
                 Ambiente(global_id="A2", nome="Varanda", area_m2=2.0),
                 Ambiente(global_id="A3", nome="Cozinha", area_m2=None)]
    r = _checar(EDI002, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE
    assert r.detalhe["ambientes_sem_area"] == ["Cozinha"]


def test_edi002_atendendo_aos_dois_limites_ignora_ambiente_sem_area(monkeypatch):
    # Somar menos só erra contra o proponente: se já bate, é conforme.
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=42.0),
                 Ambiente(global_id="A2", nome="Varanda", area_m2=2.0),
                 Ambiente(global_id="A3", nome="Cozinha", area_m2=None)]
    r = _checar(EDI002, _ctx(ambientes), monkeypatch)
    assert r.estado is Estado.CONFORME
    assert "sem área declarada" in r.mensagem


def test_edi002_normaliza_o_limite_principal_pelo_numero_de_uhs(monkeypatch):
    # 2 UHs: 83,00 m² com varanda e 80,00 m² principais. 85,00 m² no total
    # bastam para o primeiro, mas 70,00 m² principais não bastam para o segundo.
    ambientes = [Ambiente(global_id="A1", nome="Sala", area_m2=70.0),
                 Ambiente(global_id="A2", nome="Varanda", area_m2=15.0)]
    r = _checar(EDI002, _ctx(ambientes, num_uhs=2), monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["area_min"] == 83.0
    assert r.detalhe["area_principal_min"] == 80.0
    assert r.detalhe["atende_area_util"] is True
    assert r.detalhe["atende_area_principal"] is False
