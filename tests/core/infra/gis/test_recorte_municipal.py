"""Recorte municipal versionado — geração, ida e volta, e cache honesto.

O recorte é a **fronteira** entre as bases nacionais (centenas de MB, fora do
controle de versão) e o aplicativo. Duas propriedades a sustentam, e as duas
estão testadas aqui:

1. **Ida e volta sem perda.** O CSV gravado, relido pelo mesmo leitor que lê o
   CSV do usuário, tem de reproduzir exatamente os mesmos números. Se o recorte
   perdesse uma dimensão pelo caminho — e ele quase perdeu o ``atendimento`` —,
   escolas corretamente excluídas voltariam a contar.
2. **Cache que não mente.** "Já gerado" é "existe **e** o SHA-256 das fontes
   confere". Reusar recorte gerado a partir de outro arquivo seria a versão
   silenciosa do erro que este módulo inteiro existe para não cometer.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

from core.dominio import equipamentos as eq
from core.infra.gis import csv_equipamentos as leitor
from core.infra.gis import inep as de_inep
from tests.apoio.inep import (
    CAB_CATALOGO,
    CAB_ESCOLA,
    CAB_TURMA,
    CATALOGO,
    ESCOLAS,
    TURMAS,
)
from tests.conftest import RAIZ


def _gerador():
    caminho = os.path.join(RAIZ, "scripts", "gerar_equipamentos.py")
    spec = importlib.util.spec_from_file_location("gerar_equipamentos", caminho)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gerar_equipamentos"] = mod
    spec.loader.exec_module(mod)
    return mod


gerar = _gerador()


@pytest.fixture
def ambiente(tmp_path):
    """Pasta de fontes e pasta de saída, como no repositório real."""
    fontes_dir = tmp_path / "entradas" / "inep"
    fontes_dir.mkdir(parents=True)
    saida = tmp_path / "config"
    (fontes_dir / "Tabela_Escola_2025_V2.csv").write_text(
        CAB_ESCOLA + "\n" + "\n".join(ESCOLAS) + "\n", encoding="latin-1")
    (fontes_dir / "Tabela_Turma_2025_V2.csv").write_text(
        CAB_TURMA + "\n" + "\n".join(TURMAS) + "\n", encoding="latin-1")
    (fontes_dir / "Análise - Tabela da lista das escolas - Detalhado.csv").write_text(
        CAB_CATALOGO + "\n" + "\n".join(CATALOGO) + "\n", encoding="utf-8-sig")
    return {"fontes_dir": str(fontes_dir), "saida": str(saida)}


def _gera(ambiente, codigo="4307807", extra=()):
    return gerar.main(["--municipio", codigo, "--fontes", ambiente["fontes_dir"],
                       "--saida", ambiente["saida"], *extra])


# ---------------------------------------------------------------------------
# Localização das fontes
# ---------------------------------------------------------------------------

def test_fontes_sao_reconhecidas_por_prefixo(ambiente):
    """O INEP já renomeou o arquivo entre safras — casar nome exato quebraria."""
    achados, faltando = gerar.localizar_fontes(ambiente["fontes_dir"])
    assert faltando == []
    assert set(achados) == set(de_inep.PAPEIS)


def test_pasta_sem_fontes_falha_dizendo_o_que_falta(tmp_path, capsys):
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    codigo = gerar.main(["--municipio", "4307807", "--fontes", str(vazia),
                         "--saida", str(tmp_path / "config")])
    assert codigo == 1
    assert "FONTES NÃO ENCONTRADAS" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Ida e volta
# ---------------------------------------------------------------------------

def test_recorte_relido_reproduz_os_mesmos_numeros(ambiente, capsys):
    """A propriedade que torna o recorte utilizável em vez de só menor."""
    assert _gera(ambiente) == 0
    capsys.readouterr()

    direto = de_inep.extrair(
        "4307807", calcular_sha=False,
        escola=os.path.join(ambiente["fontes_dir"], "Tabela_Escola_2025_V2.csv"),
        turma=os.path.join(ambiente["fontes_dir"], "Tabela_Turma_2025_V2.csv"),
        catalogo=os.path.join(ambiente["fontes_dir"],
                              "Análise - Tabela da lista das escolas - Detalhado.csv"))
    relido = leitor.ler(os.path.join(ambiente["saida"], "equipamentos_4307807.csv"),
                        fonte=eq.FONTE_INEP, precisao=eq.PRECISAO_OFICIAL)

    assert relido.faltando == []
    assert relido.rejeitadas == []
    assert relido.valores_desconhecidos == {}
    for ciclo in eq.CICLOS:
        assert len(eq.filtrar(relido.equipamentos, ciclo=ciclo).aceitos) == \
               len(eq.filtrar(direto.equipamentos, ciclo=ciclo).aceitos), ciclo


def test_atendimento_sobrevive_a_ida_e_volta(ambiente, capsys):
    """Sem a coluna própria, as escolas excluídas voltariam a contar.

    A dimensão *quem a escola atende* não existe como coluna no microdado — é
    derivada. Se o recorte a perdesse, a escola de classes exclusivas e a que
    não escolariza ninguém reapareceriam como atendimento geral.
    """
    _gera(ambiente)
    capsys.readouterr()
    relido = leitor.ler(os.path.join(ambiente["saida"], "equipamentos_4307807.csv"))
    por = {e.codigo_inep: e for e in relido.equipamentos}
    assert por["104"].atendimento == eq.ATENDIMENTO_EXCLUSIVO_DEFICIENCIA
    assert por["105"].atendimento == eq.ATENDIMENTO_SEM_ESCOLARIZACAO
    assert por["101"].atendimento == eq.ATENDIMENTO_GERAL


def test_ciclos_usam_barra_vertical_e_nao_ponto_e_virgula(ambiente, capsys):
    """O separador de campo é ';': uma célula com ';' se parte na primeira
    planilha que reabrir e salvar o arquivo."""
    _gera(ambiente)
    capsys.readouterr()
    with open(os.path.join(ambiente["saida"], "equipamentos_4307807.csv"),
              encoding="utf-8") as arquivo:
        texto = arquivo.read()
    assert "fundamental_i|fundamental_ii" in texto


def test_sem_coordenada_fica_fora_do_csv_e_dentro_da_procedencia(ambiente, capsys):
    """Some do insumo, não do relato."""
    _gera(ambiente)
    capsys.readouterr()
    with open(os.path.join(ambiente["saida"], "equipamentos_4307807.csv"),
              encoding="utf-8") as arquivo:
        texto = arquivo.read()
    assert "EMEF SEM COORDENADA" not in texto
    with open(os.path.join(ambiente["saida"], "equipamentos_4307807.json"),
              encoding="utf-8") as arquivo:
        proc = json.load(arquivo)
    assert proc["contagens"]["sem_coordenada"] == 1


# ---------------------------------------------------------------------------
# Procedência
# ---------------------------------------------------------------------------

def test_procedencia_permite_conferir_o_numero_sem_ter_o_arquivo(ambiente, capsys):
    _gera(ambiente)
    capsys.readouterr()
    with open(os.path.join(ambiente["saida"], "equipamentos_4307807.json"),
              encoding="utf-8") as arquivo:
        proc = json.load(arquivo)
    assert proc["ano_censo"] == "2025"
    assert proc["nome_municipio"] == "Estrela" and proc["uf"] == "RS"
    assert {f["papel"] for f in proc["fontes"]} == set(de_inep.PAPEIS)
    assert all(len(f["sha256"]) == 64 for f in proc["fontes"])
    assert proc["contagens"]["aptos_por_ciclo"][eq.CICLO_INFANTIL] >= 1
    assert "por_motivo_de_descarte" in proc["contagens"]
    # a precedência por campo fica declarada no artefato, não só no código
    assert proc["precedencia_por_campo"]["coordenada"] == "Catálogo de Escolas"
    assert proc["precedencia_por_campo"]["ciclos"] == "microdado/Tabela_Turma"


def test_sensibilidade_das_conveniadas_e_registrada(ambiente, capsys):
    """A regra é a pública estrita — e o número que ela deixa de fora é medido."""
    _gera(ambiente)
    capsys.readouterr()
    with open(os.path.join(ambiente["saida"], "equipamentos_4307807.json"),
              encoding="utf-8") as arquivo:
        proc = json.load(arquivo)
    s = proc["sensibilidade_conveniadas"][eq.CICLO_INFANTIL]
    assert s["conveniadas_excluidas"] == 1
    assert s["considerados_se_incluisse"] == s["considerados"] + 1


# ---------------------------------------------------------------------------
# Cache honesto
# ---------------------------------------------------------------------------

def test_segunda_rodada_pula_o_municipio_ja_gerado(ambiente, capsys):
    _gera(ambiente)
    capsys.readouterr()
    assert _gera(ambiente) == 0
    assert "pulando" in capsys.readouterr().out


def test_fonte_trocada_torna_o_recorte_defasado(ambiente, capsys):
    """Cache velho reusado em silêncio seria o mesmo erro, na forma calada."""
    _gera(ambiente)
    capsys.readouterr()
    fonte = os.path.join(ambiente["fontes_dir"], "Tabela_Turma_2025_V2.csv")
    with open(fonte, "a", encoding="latin-1") as f:
        f.write("2025;109;4307807;1;0;1;0;0;0;0\n")
    assert gerar.estado(ambiente["saida"], "4307807",
                        gerar.localizar_fontes(ambiente["fontes_dir"])[0])[0] == "defasado"
    assert _gera(ambiente) == 0
    assert "DEFASADO" in capsys.readouterr().out


def test_forcar_regera_mesmo_atual(ambiente, capsys):
    _gera(ambiente)
    capsys.readouterr()
    _gera(ambiente, extra=("--forcar",))
    saida = capsys.readouterr().out
    assert "pulando" not in saida and "gravado" in saida


# ---------------------------------------------------------------------------
# Duas correções no leitor de CSV, motivadas pelo export nacional
# ---------------------------------------------------------------------------

def test_aee_e_reconhecido_como_ativa_sem_escolarizacao(tmp_path):
    """Quinto valor da "Restrição de Atendimento", só visto no export NACIONAL.

    Dois municípios não continham o valor; no país são 895 estabelecimentos,
    856 em atividade. Sem ele, todos seriam rejeitados por "situação não
    reconhecida" — demonstração do risco de fechar vocabulário sobre amostra
    pequena.
    """
    arquivo = tmp_path / "escolas.csv"
    arquivo.write_text(
        "Escola;Latitude;Longitude;Dependência Administrativa;"
        "Restrição de Atendimento;Etapas e Modalidade de Ensino Oferecidas\n"
        "CENTRO AEE;-29.50;-51.96;Municipal;"
        "ESCOLA EXCLUSIVA DE ATENDIMENTO EDUCACIONAL ESPECIALIZADO;Educação Infantil\n",
        encoding="utf-8")
    L = leitor.ler(str(arquivo))
    assert L.valores_desconhecidos == {}
    assert L.rejeitadas == []
    e = L.equipamentos[0]
    assert e.situacao == eq.SITUACAO_ATIVA
    assert e.atendimento == eq.ATENDIMENTO_SEM_ESCOLARIZACAO
    assert eq.filtrar(L.equipamentos).contagem_por_motivo == {
        eq.DESCARTE_SEM_ESCOLARIZACAO: 1}


def test_coluna_restricao_do_catalogo_nao_e_capturada_como_atendimento(tmp_path):
    """A coluna nova não pode roubar a coluna de situação do Catálogo.

    "Restrição de Atendimento" responde duas perguntas numa célula; se a busca
    aproximada a casasse com o campo ``atendimento``, o vocabulário não bateria
    e a segunda dimensão se perderia — justo o que a coluna existe para evitar.
    """
    arquivo = tmp_path / "catalogo.csv"
    arquivo.write_text(
        "Escola;Latitude;Longitude;Dependência Administrativa;"
        "Restrição de Atendimento;Etapas e Modalidade de Ensino Oferecidas\n"
        "EMEI X;-29.50;-51.96;Municipal;"
        "ESCOLA EXCLUSIVA DE ATIVIDADE COMPLEMENTAR;Educação Infantil\n",
        encoding="utf-8")
    L = leitor.ler(str(arquivo))
    assert L.colunas_detectadas["situacao"] == "Restrição de Atendimento"
    assert "atendimento" not in L.colunas_detectadas
    assert L.equipamentos[0].atendimento == eq.ATENDIMENTO_SEM_ESCOLARIZACAO


# ---------------------------------------------------------------------------
# Busca de município pelo nome
# ---------------------------------------------------------------------------

def test_procurar_devolve_o_codigo_a_partir_do_nome(ambiente):
    """A chave é o código; a busca existe para que ninguém precise decorá-lo."""
    escola = os.path.join(ambiente["fontes_dir"], "Tabela_Escola_2025_V2.csv")
    achados = de_inep.procurar_municipios(escola, "estrela")
    assert [(c, n, u) for c, n, u, _ in achados] == [("4307807", "Estrela", "RS")]


def test_procurar_ignora_acento_e_caixa(ambiente):
    """"São José" digitado sem acento tem de achar — é o caso comum."""
    escola = os.path.join(ambiente["fontes_dir"], "Tabela_Escola_2025_V2.csv")
    assert de_inep.procurar_municipios(escola, "SAO JOSE")[0][0] == "3549904"
    assert de_inep.procurar_municipios(escola, "são josé")[0][0] == "3549904"


def test_procurar_conta_estabelecimentos_para_desempatar_homonimos(ambiente):
    escola = os.path.join(ambiente["fontes_dir"], "Tabela_Escola_2025_V2.csv")
    achados = de_inep.procurar_municipios(escola, "")
    por_codigo = {c: n for c, _, _, n in achados}
    assert por_codigo["4307807"] == 8      # as oito linhas de Estrela na fixture
    assert por_codigo["3549904"] == 1


def test_procurar_restrito_por_uf(ambiente):
    escola = os.path.join(ambiente["fontes_dir"], "Tabela_Escola_2025_V2.csv")
    assert de_inep.procurar_municipios(escola, "", uf="RS")[0][2] == "RS"
    assert len(de_inep.procurar_municipios(escola, "", uf="RS")) == 1


def test_procurar_sem_resultado_devolve_lista_vazia(ambiente):
    escola = os.path.join(ambiente["fontes_dir"], "Tabela_Escola_2025_V2.csv")
    assert de_inep.procurar_municipios(escola, "municipio que nao existe") == []
    assert de_inep.procurar_municipios("/nao/existe.csv", "estrela") == []
