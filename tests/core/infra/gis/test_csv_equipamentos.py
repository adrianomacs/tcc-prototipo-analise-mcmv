"""Leitura do CSV de equipamentos de educação — modelo do repositório, exports
reais do Catálogo de Escolas e dos microdados do Censo (R4a/R4b).

Cobre o dialeto (separador, decimal, encoding), a detecção de coluna por
alias com preferência declarada, e as particularidades que os exports reais
ensinaram (R4b): "Categoria Administrativa" não é a esfera, uma coluna
carrega duas perguntas (situação × restrição de atendimento), e o
fundamental sem distinção de ciclo é contado, não convertido.
"""

from __future__ import annotations

import pytest

from core.dominio import equipamentos as eq
from core.infra.gis import csv_equipamentos as leitor

CG_LAT, CG_LON = -20.4712, -54.6215


def _csv(tmp_path, conteudo, nome="escolas.csv", encoding="utf-8"):
    alvo = tmp_path / nome
    alvo.write_text(conteudo, encoding=encoding)
    return str(alvo)


# ===========================================================================
# Leitura de CSV
# ===========================================================================

def test_le_o_modelo_do_repositorio():
    l = leitor.ler("config/modelo_equipamentos.csv")
    assert l.ok and not l.rejeitadas and not l.valores_desconhecidos
    assert len(l.equipamentos) == 4
    assert l.dialeto["separador"] == ";"
    por_nome = {e.nome: e for e in l.equipamentos}
    assert por_nome["EM Prof. Ana Rita"].ciclos == [eq.CICLO_FUND_I,
                                                    eq.CICLO_FUND_II]
    assert por_nome["EMEI Jardim das Acácias"].lat == pytest.approx(-20.4712)


def test_ciclos_multiplos_com_celula_citada_tambem_funcionam(tmp_path):
    """O '|' é o recomendado, mas ';' entre aspas é respeitado pelo csv.reader."""
    caminho = _csv(tmp_path,
                   'nome;latitude;longitude;ciclo;rede;situacao\n'
                   'Escola;-20,47;-54,62;"fundamental_i;fundamental_ii";municipal;ativa\n')
    l = leitor.ler(caminho)
    assert l.equipamentos[0].ciclos == [eq.CICLO_FUND_I, eq.CICLO_FUND_II]


def test_cabecalho_do_catalogo_de_escolas_e_detectado(tmp_path):
    """Inclui 'Código do Município', que não pode virar chave de dedupe."""
    caminho = _csv(tmp_path,
                   "Código da Escola;Nome da Escola;Código do Município;"
                   "Latitude;Longitude;Etapas de Ensino;"
                   "Dependência Administrativa;Situação de Funcionamento\n"
                   "50012345;EMEI Acácias;5002704;-20,4712;-54,6215;"
                   "Educação Infantil;Municipal;Em Atividade\n")
    l = leitor.ler(caminho)
    assert l.colunas_detectadas["codigo_inep"] == "Código da Escola"
    assert l.colunas_detectadas["nome"] == "Nome da Escola"
    e = l.equipamentos[0]
    assert e.codigo_inep == "50012345"
    assert e.ciclos == [eq.CICLO_INFANTIL]
    assert e.rede == eq.REDE_MUNICIPAL and e.situacao == eq.SITUACAO_ATIVA


def test_codigos_numericos_dos_microdados_sao_mapeados(tmp_path):
    """TP_DEPENDENCIA 1..4 e TP_SITUACAO_FUNCIONAMENTO 1..3."""
    caminho = _csv(tmp_path,
                   "NO_ENTIDADE;NU_LATITUDE;NU_LONGITUDE;etapa;"
                   "TP_DEPENDENCIA;TP_SITUACAO_FUNCIONAMENTO\n"
                   "Escola Federal;-20,47;-54,62;anos_iniciais;1;1\n"
                   "Escola Privada;-20,48;-54,63;anos_iniciais;4;1\n"
                   "Escola Paralisada;-20,49;-54,64;anos_iniciais;3;2\n")
    l = leitor.ler(caminho)
    assert len(l.equipamentos) == 3
    redes = {e.nome: (e.rede, e.situacao) for e in l.equipamentos}
    assert redes["Escola Federal"] == (eq.REDE_FEDERAL, eq.SITUACAO_ATIVA)
    assert redes["Escola Privada"] == (eq.REDE_PRIVADA, eq.SITUACAO_ATIVA)
    assert redes["Escola Paralisada"] == (eq.REDE_MUNICIPAL,
                                          eq.SITUACAO_PARALISADA)
    f = eq.filtrar(l.equipamentos, ciclo=eq.CICLO_FUND_I)
    assert [e.nome for e in f.aceitos] == ["Escola Federal"]


def test_linha_sem_coordenada_e_rejeitada_com_o_numero(tmp_path):
    caminho = _csv(tmp_path,
                   "nome;latitude;longitude;ciclo;rede;situacao\n"
                   "Boa;-20,47;-54,62;infantil;municipal;ativa\n"
                   "Sem coordenada;;;infantil;municipal;ativa\n")
    l = leitor.ler(caminho)
    assert len(l.equipamentos) == 1
    assert l.rejeitadas[0][0] == 3
    assert "coordenada" in l.rejeitadas[0][1]
    assert "Sem coordenada" in l.rejeitadas[0][1]


def test_linha_sem_rede_ou_situacao_e_rejeitada_por_ser_filtro_obrigatorio(tmp_path):
    caminho = _csv(tmp_path,
                   "nome;latitude;longitude;ciclo;rede;situacao\n"
                   "Sem rede;-20,47;-54,62;infantil;;ativa\n"
                   "Sem situação;-20,48;-54,63;infantil;municipal;\n")
    l = leitor.ler(caminho)
    assert not l.equipamentos
    assert [n for n, _ in l.rejeitadas] == [2, 3]
    assert "filtro obrigatório" in l.rejeitadas[0][1]
    assert "filtro obrigatório" in l.rejeitadas[1][1]


def test_publica_sem_esfera_e_ambiguo_e_nao_passa(tmp_path):
    """'Pública' não diz se é municipal, estadual ou federal."""
    caminho = _csv(tmp_path,
                   "nome;latitude;longitude;ciclo;rede;situacao\n"
                   "Escola;-20,47;-54,62;infantil;Pública;ativa\n")
    l = leitor.ler(caminho)
    assert not l.equipamentos and l.rejeitadas


def test_vocabulario_desconhecido_vai_para_mapeamento(tmp_path):
    caminho = _csv(tmp_path,
                   "nome;latitude;longitude;ciclo;rede;situacao\n"
                   "Escola;-20,47;-54,62;pos_graduacao;consorciada;em atividade\n")
    l = leitor.ler(caminho)
    assert l.precisa_mapeamento
    assert "consorciada" in l.valores_desconhecidos["rede"]
    assert "pos_graduacao" in l.valores_desconhecidos["ciclo"]
    assert not l.equipamentos          # sem rede reconhecida, não entra


def test_etapa_fora_do_recorte_e_ignorada_sem_poluir_o_mapeamento(tmp_path):
    """Médio e EJA existem no cadastro e não geram requisito — ignorar de propósito.

    Se caíssem em `valores_desconhecidos`, a lacuna que importa — o fundamental
    sem distinção de ciclo — ficaria escondida no meio do ruído.
    """
    caminho = _csv(tmp_path,
                   "nome;latitude;longitude;ciclo;rede;situacao\n"
                   "Escola;-20,47;-54,62;Ensino Médio|Educação de Jovens Adultos;"
                   "estadual;ativa\n")
    l = leitor.ler(caminho)
    assert "ciclo" not in l.valores_desconhecidos
    assert l.equipamentos and l.equipamentos[0].ciclos == []


def test_coluna_obrigatoria_ausente_e_reportada_sem_ler_nada(tmp_path):
    caminho = _csv(tmp_path, "nome;latitude;longitude;ciclo\n"
                             "Escola;-20,47;-54,62;infantil\n")
    l = leitor.ler(caminho)
    assert not l.ok
    assert set(l.faltando) == {"rede", "situacao"}
    assert not l.equipamentos


def test_arquivo_em_latin1_com_acento_e_lido(tmp_path):
    conteudo = ("nome;latitude;longitude;ciclo;rede;situacao\n"
                "Educação Básica;-20,47;-54,62;infantil;municipal;ativa\n")
    caminho = _csv(tmp_path, conteudo, nome="latin.csv", encoding="latin-1")
    l = leitor.ler(caminho)
    assert l.equipamentos[0].nome == "Educação Básica"
    assert l.dialeto["encoding"] in ("cp1252", "latin-1")


def test_separador_virgula_com_decimal_ponto(tmp_path):
    caminho = _csv(tmp_path,
                   "nome,latitude,longitude,ciclo,rede,situacao\n"
                   "Escola,-20.4712,-54.6215,infantil,municipal,ativa\n")
    l = leitor.ler(caminho)
    assert l.dialeto["separador"] == ","
    assert l.equipamentos[0].lat == pytest.approx(-20.4712)


def test_numero_decide_o_decimal_por_valor_nao_pelo_dialeto():
    """Deduzir o decimal do separador de campo faria '-20.4712' virar -204712."""
    assert leitor._numero("-20,4712") == pytest.approx(-20.4712)
    assert leitor._numero("-20.4712") == pytest.approx(-20.4712)
    assert leitor._numero("1.234,56") == pytest.approx(1234.56)
    assert leitor._numero("1,234.56") == pytest.approx(1234.56)
    assert leitor._numero("1.234.567") == pytest.approx(1234567.0)
    assert leitor._numero(" -54 ") == pytest.approx(-54.0)
    assert leitor._numero("") is None
    assert leitor._numero("n/d") is None
    assert leitor._numero(None) is None


def test_ponto_decimal_com_separador_ponto_e_virgula(tmp_path):
    """Combinação real e antes quebrada: campo por ';' e decimal por '.'."""
    caminho = _csv(tmp_path,
                   "nome;latitude;longitude;ciclo;rede;situacao\n"
                   "Escola;-20.4712;-54.6215;infantil;municipal;ativa\n")
    l = leitor.ler(caminho)
    assert not l.rejeitadas, l.rejeitadas
    assert l.equipamentos[0].lat == pytest.approx(-20.4712)
    assert l.equipamentos[0].lon == pytest.approx(-54.6215)


# ===========================================================================
# R4b — o que os exports reais do Catálogo de Escolas ensinaram
# ===========================================================================

CABECALHO_CATALOGO = (
    "Restrição de Atendimento,Escola,Código INEP,UF,Município,"
    "Categoria Administrativa,Endereço,Dependência Administrativa,"
    "Conveniada Poder Público,Etapas e Modalidade de Ensino Oferecidas,"
    "Latitude,Longitude\n"
)


def _catalogo(tmp_path, *linhas):
    return _csv(tmp_path, CABECALHO_CATALOGO + "".join(l + "\n" for l in linhas),
                nome="catalogo.csv")


def test_dependencia_vence_categoria_mesmo_vindo_depois_no_cabecalho(tmp_path):
    """O defeito era decidir a rede pela ORDEM das colunas no arquivo.

    'Categoria Administrativa' vem antes e só diz Pública/Privada — que não
    informa a esfera. Vencendo a disputa, ela zerava a rede de toda escola
    pública e o leitor rejeitava o município inteiro.
    """
    caminho = _catalogo(
        tmp_path,
        "ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,EMEI Girassol,"
        "43060722,RS,Estrela,Pública,Rua X,Municipal,Não,Educação Infantil,"
        "-29.482985,-51.95250167")
    l = leitor.ler(caminho)
    assert l.colunas_detectadas["rede"] == "Dependência Administrativa"
    assert not l.rejeitadas, l.rejeitadas
    assert l.equipamentos[0].rede == eq.REDE_MUNICIPAL


def test_categoria_sozinha_nao_serve_como_rede_e_o_aviso_diz_o_que_falta(tmp_path):
    caminho = _csv(tmp_path,
                   "Escola,Categoria Administrativa,Latitude,Longitude,"
                   "Etapas e Modalidade de Ensino Oferecidas,"
                   "Restrição de Atendimento\n"
                   "EMEI,Pública,-29.48,-51.95,Educação Infantil,"
                   "ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO\n")
    l = leitor.ler(caminho)
    assert "rede" in l.faltando
    assert any("Dependência" in a for a in l.avisos), l.avisos


def test_restricao_de_atendimento_responde_duas_perguntas(tmp_path):
    """Uma coluna do Catálogo carrega situação E restrição — separar as duas."""
    caminho = _catalogo(
        tmp_path,
        "ESCOLA PARALISADA,EM Parada,1,SP,SJC,Pública,R,Municipal,Não,"
        "Ensino Médio,-23.2,-45.9",
        "ESCOLA EXCLUSIVA DE ATIVIDADE COMPLEMENTAR,EM Complementar,2,SP,SJC,"
        "Pública,R,Municipal,Não,Educação Infantil,-23.2,-45.9",
        "ESCOLA ATENDE EXCLUSIVAMENTE ALUNOS COM DEFICIÊNCIA,EM Especial,3,SP,"
        "SJC,Pública,R,Estadual,Não,Educação Infantil,-23.2,-45.9",
        "ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,EMEI Comum,4,SP,"
        "SJC,Pública,R,Municipal,Não,Educação Infantil,-23.2,-45.9")
    l = leitor.ler(caminho)
    assert len(l.equipamentos) == 4, l.rejeitadas
    por_nome = {e.nome: e for e in l.equipamentos}
    assert por_nome["EM Parada"].situacao == eq.SITUACAO_PARALISADA
    assert por_nome["EM Complementar"].situacao == eq.SITUACAO_ATIVA
    assert (por_nome["EM Complementar"].atendimento
            == eq.ATENDIMENTO_SEM_ESCOLARIZACAO)
    assert (por_nome["EM Especial"].atendimento
            == eq.ATENDIMENTO_EXCLUSIVO_DEFICIENCIA)
    assert por_nome["EMEI Comum"].atendimento == eq.ATENDIMENTO_GERAL

    f = eq.filtrar(l.equipamentos, ciclo=eq.CICLO_INFANTIL)
    assert [e.nome for e in f.aceitos] == ["EMEI Comum"]
    assert f.contagem_por_motivo == {
        eq.DESCARTE_SITUACAO_INATIVA: 1,
        eq.DESCARTE_SEM_ESCOLARIZACAO: 1,
        eq.DESCARTE_ATENDIMENTO_EXCLUSIVO: 1,
    }


def test_fundamental_sem_distincao_e_contado_nao_convertido(tmp_path):
    """Converter 'Ensino Fundamental' nos dois ciclos criaria conformidade falsa.

    Uma escola só de anos iniciais contaria como cobertura de anos finais. Então
    a etapa é sinalizada e não entra em ciclo nenhum.
    """
    caminho = _catalogo(
        tmp_path,
        "ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,EMEF Pinheiros,"
        "43207278,RS,Estrela,Pública,R,Municipal,Não,Ensino Fundamental,"
        "-29.4959248,-51.94709033")
    l = leitor.ler(caminho)
    assert l.fundamental_indistinto == 1
    assert l.equipamentos[0].ciclos == []
    assert any("IN_FUND_AI" in a for a in l.avisos), l.avisos
    assert not eq.filtrar(l.equipamentos, ciclo=eq.CICLO_FUND_I).aceitos


def test_conveniada_e_lida_e_a_sensibilidade_mede_o_efeito_da_regra(tmp_path):
    caminho = _catalogo(
        tmp_path,
        "ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,EMEI Municipal,"
        "1,RS,Estrela,Pública,R,Municipal,Não,Educação Infantil,-29.48,-51.95",
        "ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,EEI Colmeia,"
        "2,RS,Estrela,Privada,R,Privada,Sim,Educação Infantil,-29.4874,-51.9531",
        "ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,Colégio Particular,"
        "3,RS,Estrela,Privada,R,Privada,Não,Educação Infantil,-29.50,-51.96")
    l = leitor.ler(caminho)
    por_nome = {e.nome: e for e in l.equipamentos}
    assert por_nome["EEI Colmeia"].conveniada is True
    assert por_nome["Colégio Particular"].conveniada is False
    assert por_nome["EMEI Municipal"].conveniada is False

    s = eq.sensibilidade_conveniadas(l.equipamentos, ciclo=eq.CICLO_INFANTIL)
    assert s["considerados"] == 1
    assert s["conveniadas_excluidas"] == 1
    assert s["considerados_se_incluisse"] == 2
    assert s["nomes"] == ["EEI Colmeia"]
    # A regra avaliada não muda: a conveniada continua fora do conjunto aceito.
    assert [e.nome for e in eq.filtrar(l.equipamentos,
                                       ciclo=eq.CICLO_INFANTIL).aceitos] \
        == ["EMEI Municipal"]


def test_coordenada_ausente_do_catalogo_vem_como_espacos(tmp_path):
    """No export real a célula não é vazia: são 30 espaços."""
    caminho = _catalogo(
        tmp_path,
        "ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,EMEI Criança Feliz,"
        "43172318,RS,Estrela,Pública,R,Municipal,Não,Educação Infantil,"
        + " " * 30 + "," + " " * 30)
    l = leitor.ler(caminho)
    assert not l.equipamentos
    assert l.rejeitadas and "coordenada" in l.rejeitadas[0][1]
