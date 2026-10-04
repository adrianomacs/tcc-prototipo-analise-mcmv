"""Testes dos inspetores de fonte (``scripts/inspecionar_*.py``).

Um script "somente leitura" parece não merecer teste — mas este é a **porta de
entrada** do R4b: é a saída dele que define os nomes de coluna contra os quais o
``de_inep.py`` será escrito. Um inspetor que quebra, ou que lê o arquivo no
encoding errado, não produz um erro visível: produz um vocabulário errado, que
vira adaptador errado. Por isso os dois defeitos abaixo viraram teste em vez de
correção silenciosa.

Os scripts não formam um pacote, então são carregados por caminho.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

from tests.conftest import RAIZ


def _carregar(nome: str):
    caminho = os.path.join(RAIZ, "scripts", f"{nome}.py")
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec and spec.loader, caminho
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


censo = _carregar("inspecionar_censo_escolar")


# --------------------------------------------------------------------------
# Defeito 1 — encoding decidido por um trecho cortado
# --------------------------------------------------------------------------

def test_utf8_tolera_caractere_partido_no_fim_do_trecho():
    """Corte no meio de multibyte não pode ser lido como "não é UTF-8".

    O inspetor decide o encoding lendo 64 KB. Num arquivo nacional cheio de
    acento, o corte cair no meio de uma sequência multibyte é o caso comum, não
    o excepcional — e concluir latin-1 dali faz todo nome acentuado virar
    mojibake no arquivo inteiro.
    """
    partido = "ESCOLA MUNICIPAL CONCEIÇÃO".encode()[:-1]
    assert censo._utf8_tolerando_corte(partido) is not None


def test_byte_invalido_continua_reprovando_utf8():
    """A tolerância acima não pode virar "aceita qualquer coisa".

    Se ela aceitasse byte inválido, latin-1 nunca seria detectado e o defeito
    trocaria de lado. O que se tolera é *cauda incompleta*, não *byte ilegal*.
    """
    assert censo._utf8_tolerando_corte(b"\xff\xfe ESCOLA") is None


def test_latin1_ainda_e_reconhecido():
    assert censo._utf8_tolerando_corte("CONCEIÇÃO".encode("latin-1")) is None


# --------------------------------------------------------------------------
# Defeito 2 — posição da coluna obtida por busca pelo nome normalizado
# --------------------------------------------------------------------------

def test_coluna_com_espaco_em_volta_do_rotulo_e_resolvida():
    """Espaço em volta do rótulo não pode derrubar o inspetor.

    A versão anterior guardava o nome já normalizado e depois procurava esse
    nome na lista crua (``cabecalho.index``), o que levanta ``ValueError``
    quando o cabeçalho real traz `` NO_ENTIDADE ``. Resolver nome **e** posição
    na mesma passada elimina a classe inteira.
    """
    cabecalho = ["NU_ANO_CENSO", "CO_ENTIDADE", " NO_ENTIDADE ", "CO_MUNICIPIO",
                 "TP_DEPENDENCIA", "TP_SITUACAO_FUNCIONAMENTO", "IN_ESCOLARIZACAO"]
    achadas, indice, ausentes = censo._resolver(cabecalho)
    assert ausentes == []
    assert achadas["nome_escola"] == "NO_ENTIDADE"
    assert indice["nome_escola"] == 2
    assert cabecalho[indice["codigo_escola"]] == "CO_ENTIDADE"


def test_preferencia_declarada_vence_a_ordem_do_arquivo():
    """Mesma lição do R4b, agora no inspetor.

    ``CO_ENTIDADE`` é o primeiro candidato de ``codigo_escola``; ele deve vencer
    ``CO_ESCOLA`` mesmo aparecendo **depois** no arquivo. Detecção cujo
    resultado depende da ordem das colunas é defeito, ainda que acerte.
    """
    cabecalho = ["CO_ESCOLA", "CO_ENTIDADE", "NO_ENTIDADE", "CO_MUNICIPIO",
                 "TP_DEPENDENCIA", "TP_SITUACAO_FUNCIONAMENTO", "IN_ESCOLARIZACAO"]
    achadas, indice, _ = censo._resolver(cabecalho)
    assert achadas["codigo_escola"] == "CO_ENTIDADE"
    assert indice["codigo_escola"] == 1


def test_essenciais_ausentes_sao_nomeadas():
    """Arquivo errado (matrícula, turma, docente) precisa dizer o que falta."""
    _, _, ausentes = censo._resolver(["NU_ANO_CENSO", "CO_ENTIDADE", "NU_IDADE"])
    assert "codigo_municipio" in ausentes and "dependencia" in ausentes
    assert "situacao" in ausentes and "escolarizacao" in ausentes


# --------------------------------------------------------------------------
# Guarda de memória
# --------------------------------------------------------------------------

def test_sem_municipio_o_inspetor_para_apos_o_retrato(tmp_path, capsys):
    """Sem recorte, nada é acumulado — o streaming perderia o sentido.

    O vocabulário, a cobertura e o cruzamento são medidos POR MUNICÍPIO;
    guardar as ~180 mil escolas do país em memória para depois descartá-las
    contraria a razão de o script ler linha a linha.
    """
    cabecalho = ("NU_ANO_CENSO;CO_ENTIDADE;NO_ENTIDADE;CO_MUNICIPIO;NO_MUNICIPIO;"
                 "TP_DEPENDENCIA;TP_SITUACAO_FUNCIONAMENTO;IN_ESCOLARIZACAO")
    linha = "2025;43000001;EMEI CONCEIÇÃO;4307807;ESTRELA;3;1;1"
    arquivo = tmp_path / "microdados_ed_basica_2025.csv"
    arquivo.write_text(f"{cabecalho}\n{linha}\n", encoding="latin-1")

    censo.inspecionar(str(arquivo), municipio=None, catalogo=None, amostra=10)
    saida = capsys.readouterr().out
    assert "--municipio" in saida
    assert "COBERTURA DE COORDENADA" not in saida


def test_inspetor_declara_o_que_o_arquivo_de_escola_nao_responde(tmp_path, capsys):
    """O achado sobre o arquivo de escola, transformado em comportamento verificável.

    O arquivo de escola do microdado 2025 não traz coordenada nem oferta de
    etapa. Um inspetor que imprimisse zero para os três ciclos estaria
    tecnicamente certo e praticamente enganoso — quem lesse concluiria que o
    município não tem escolas. Ele precisa **dizer que a pergunta não é
    respondível aqui** e apontar onde é.
    """
    cabecalho = ("NU_ANO_CENSO;CO_ENTIDADE;NO_ENTIDADE;CO_MUNICIPIO;NO_MUNICIPIO;"
                 "TP_DEPENDENCIA;TP_SITUACAO_FUNCIONAMENTO;IN_ESCOLARIZACAO")
    linhas = [
        "2025;43000001;EMEI CONCEIÇÃO;4307807;ESTRELA;3;1;1",
        "2025;43000002;EMEF SÃO SEBASTIÃO;4307807;ESTRELA;3;1;1",
        "2025;43000003;COLÉGIO TIRADENTES;4307807;ESTRELA;2;1;1",
        # privada: fora da regra estrita
        "2025;43000004;CRECHE PARTICULAR;4307807;ESTRELA;4;1;1",
        # paralisada: fora
        "2025;43000005;EEB JOÃO;4307807;ESTRELA;3;2;1",
        # ativa que não escolariza ninguém
        "2025;43000006;CENTRO DE ATIVIDADE;4307807;ESTRELA;3;1;0",
        "2025;41000001;ESCOLA DE OUTRO MUNICÍPIO;4106902;CURITIBA;3;1;1",
    ]
    arquivo = tmp_path / "Tabela_Escola_2025_V2.csv"
    arquivo.write_text(cabecalho + "\n" + "\n".join(linhas) + "\n", encoding="latin-1")

    censo.inspecionar(str(arquivo), municipio="4307807", catalogo=None, amostra=10)
    saida = capsys.readouterr().out

    # o que ele SABE responder
    assert "públicas e em atividade         : 4" in saida
    assert "dessas, que escolarizam         : 3" in saida
    # o que ele declara NÃO responder, em vez de responder zero
    assert "COORDENADA: nenhuma neste arquivo" in saida
    assert "ETAPA: este arquivo não informa oferta de etapa" in saida
    assert "IN_COMUM_FUND_AI" in saida and "EDUCAÇÃO" in saida
    assert "Tabela_Turma" in saida and "de_inep.py" in saida


def test_recorte_vazio_sugere_o_codigo_ibge(tmp_path, capsys):
    """Nome com acento é armadilha; o código IBGE não depende de acento."""
    cabecalho = ("NU_ANO_CENSO;CO_ENTIDADE;NO_ENTIDADE;CO_MUNICIPIO;NO_MUNICIPIO;"
                 "TP_DEPENDENCIA;TP_SITUACAO_FUNCIONAMENTO;IN_ESCOLARIZACAO")
    linha = "2025;35000001;EMEI CENTRO;3549904;SÃO JOSÉ DOS CAMPOS;3;1;1"
    arquivo = tmp_path / "microdados_ed_basica_2025.csv"
    arquivo.write_text(f"{cabecalho}\n{linha}\n", encoding="latin-1")

    censo.inspecionar(str(arquivo), municipio="sao jose dos campos",
                      catalogo=None, amostra=10)
    saida = capsys.readouterr().out
    assert "RECORTE VAZIO" in saida
    assert "código IBGE" in saida


@pytest.mark.parametrize("valor, esperado", [
    ("1", True), ("1.0", True), (" 1 ", True),
    ("0", False), ("", False), ("   ", False),
])
def test_bandeira_do_microdado(valor, esperado):
    assert censo._bandeira(valor) is esperado
