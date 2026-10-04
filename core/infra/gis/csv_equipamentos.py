"""Equipamentos a partir de CSV — export do Catálogo de Escolas ou planilha própria.

**Um leitor só, com detecção de colunas**. O
Catálogo de Escolas do INEP não tem API: é um portal de BI que o analista
filtra por município, etapa, dependência e situação, e **exporta**. Ou seja, o
caminho "oficial" e o caminho "planilha feita à mão" desembocam no mesmo lugar
— um CSV. Ter dois leitores duplicaria validação para ganhar nada.

A detecção cobre três vocabulários de cabeçalho ao mesmo tempo: o nosso
(``nome;latitude;longitude;ciclo;rede;situacao``), o do export do Catálogo
(rótulos em português) e o dos microdados do Censo Escolar (``NO_ENTIDADE``,
``TP_DEPENDENCIA``…). O que não for reconhecido **não é descartado em
silêncio**: volta em ``valores_desconhecidos`` para o formulário de mapeamento
semântico pedir a correspondência.

Duas recusas são deliberadas e não têm exceção:

* **linha sem coordenada** é rejeitada COM o número da linha — nunca sumir com
  o registro sem dizer qual;
* **linha sem rede ou sem situação** é rejeitada, porque esses campos são chave
  da avaliação: assumir "pública e ativa" por omissão criaria conformidade
  falsa.

Uso na linha de comando::

    python -m core.infra.gis.csv_equipamentos "entradas/gis/escolas.csv"
"""

from __future__ import annotations

import csv
import io
import os
import re
import unicodedata
from dataclasses import dataclass, field

from core.dominio import equipamentos as eq

CAMPOS_OBRIGATORIOS = ("nome", "latitude", "longitude", "ciclo", "rede", "situacao")
CAMPOS_OPCIONAIS = ("codigo_inep", "endereco", "conveniada", "atendimento")

# Aliases de cabeçalho, já normalizados (minúsculo, sem acento, com "_").
#
# **A ordem é preferência declarada, não decoração.** Antes eram conjuntos, e a
# detecção terminava decidida pela ordem das colunas NO ARQUIVO: no export do
# Catálogo, "Categoria Administrativa" (coluna 7, valores Pública/Privada)
# vencia "Dependência Administrativa" (coluna 10, valores Municipal/Estadual/
# Federal/Privada) só por vir antes — e "Pública" não diz a esfera, então a rede
# saía vazia e TODA escola pública era rejeitada. O mesmo arquivo com as colunas
# em outra ordem se comportaria de outro jeito: é o pior tipo de defeito.
ALIASES: dict[str, tuple[str, ...]] = {
    "nome": ("nome", "escola", "nome_escola", "nome_da_escola", "no_entidade",
             "nome_entidade", "estabelecimento", "instituicao"),
    "latitude": ("latitude", "nu_latitude", "lat", "y", "coord_y"),
    "longitude": ("longitude", "nu_longitude", "lon", "lng", "long", "x", "coord_x"),
    "ciclo": ("ciclo", "ciclos", "etapas_e_modalidade_de_ensino_oferecidas",
              "etapas_de_ensino", "etapa_de_ensino", "etapas", "etapa",
              "nivel", "modalidade", "oferta"),
    "rede": ("dependencia_administrativa", "tp_dependencia", "dependencia",
             "rede", "rede_de_ensino", "esfera"),
    "situacao": ("situacao", "situacao_de_funcionamento", "situacao_funcionamento",
                 "tp_situacao_funcionamento", "restricao_de_atendimento",
                 "funcionamento", "status"),
    "codigo_inep": ("codigo_inep", "co_entidade", "codigo_da_escola", "cod_inep",
                    "codigo_entidade", "id_escola", "codigo"),
    "endereco": ("endereco", "logradouro", "ds_endereco", "endereco_completo"),
    "conveniada": ("conveniada_poder_publico", "tp_conveniada_pp",
                   "in_conveniada_pp", "conveniada"),
    # Coluna própria para a segunda dimensão da restrição de atendimento.
    # Nasceu do recorte municipal gerado pelo `de_inep`: lá as duas dimensões
    # JÁ vêm separadas (o microdado não as dobra numa célula só), e escrevê-las
    # juntas de volta para depois desdobrá-las seria perder informação de
    # propósito. Em CSV do usuário a coluna é opcional, e sem ela o
    # comportamento é exatamente o de antes.
    "atendimento": ("atendimento", "tipo_atendimento"),
}

# "Categoria Administrativa" (Pública / Privada) **não** serve como fonte de
# rede, porque não diz a esfera. Fica como cruzamento: se discordar da
# dependência administrativa, o arquivo tem problema e isso tem de aparecer.
COLUNAS_CATEGORIA = ("categoria_administrativa", "categoria")

# Vocabulário de valores. As chaves são normalizadas; os códigos numéricos são
# os dos microdados do Censo Escolar (TP_DEPENDENCIA e TP_SITUACAO...).
VOCAB_REDE = {
    "municipal": eq.REDE_MUNICIPAL, "3": eq.REDE_MUNICIPAL,
    "estadual": eq.REDE_ESTADUAL, "2": eq.REDE_ESTADUAL,
    "federal": eq.REDE_FEDERAL, "1": eq.REDE_FEDERAL,
    "privada": eq.REDE_PRIVADA, "particular": eq.REDE_PRIVADA, "4": eq.REDE_PRIVADA,
    "publica": "",   # ambíguo de propósito: "pública" não diz a esfera
}
VOCAB_SITUACAO = {
    "ativa": eq.SITUACAO_ATIVA, "em_atividade": eq.SITUACAO_ATIVA,
    "atividade": eq.SITUACAO_ATIVA, "1": eq.SITUACAO_ATIVA,
    "paralisada": eq.SITUACAO_PARALISADA, "2": eq.SITUACAO_PARALISADA,
    "extinta": eq.SITUACAO_EXTINTA, "3": eq.SITUACAO_EXTINTA,
    "em_reforma": eq.SITUACAO_EM_REFORMA, "reforma": eq.SITUACAO_EM_REFORMA,
    "em_construcao": eq.SITUACAO_EM_CONSTRUCAO,
    "construcao": eq.SITUACAO_EM_CONSTRUCAO,
}

# A coluna "Restrição de Atendimento" do Catálogo responde DUAS perguntas de uma
# vez, então cada valor traduz para um par (situação, restrição de atendimento).
# Valor fora desta lista cai em ``valores_desconhecidos`` e a linha é rejeitada
# com o número dela, que é o comportamento seguro: nada entra na conta por
# omissão.
#
# Os quatro primeiros vieram dos primeiros exports municipais lidos.
# O **quinto** só apareceu no export NACIONAL: 895
# estabelecimentos, 856 deles em atividade. É a demonstração exata do risco de
# fechar vocabulário sobre amostra pequena — dois municípios não continham o
# valor, e sem ele 856 escolas seriam rejeitadas por "situação não reconhecida"
# em qualquer outro município. AEE é atendimento complementar ao turno regular,
# não escolarização, então recai no mesmo destino da atividade complementar.
VOCAB_RESTRICAO: dict[str, tuple[str, str]] = {
    "escola_em_funcionamento_e_sem_restricao_de_atendimento":
        (eq.SITUACAO_ATIVA, eq.ATENDIMENTO_GERAL),
    "escola_paralisada":
        (eq.SITUACAO_PARALISADA, eq.ATENDIMENTO_GERAL),
    "escola_exclusiva_de_atividade_complementar":
        (eq.SITUACAO_ATIVA, eq.ATENDIMENTO_SEM_ESCOLARIZACAO),
    "escola_exclusiva_de_atendimento_educacional_especializado":
        (eq.SITUACAO_ATIVA, eq.ATENDIMENTO_SEM_ESCOLARIZACAO),
    "escola_atende_exclusivamente_alunos_com_deficiencia":
        (eq.SITUACAO_ATIVA, eq.ATENDIMENTO_EXCLUSIVO_DEFICIENCIA),
}

# Vocabulário da coluna própria de atendimento (ver ALIASES["atendimento"]).
VOCAB_ATENDIMENTO = {
    "geral": eq.ATENDIMENTO_GERAL,
    "sem_escolarizacao": eq.ATENDIMENTO_SEM_ESCOLARIZACAO,
    "exclusivo_deficiencia": eq.ATENDIMENTO_EXCLUSIVO_DEFICIENCIA,
}

VOCAB_BOOLEANO = {"sim": True, "s": True, "1": True, "true": True,
                  "verdadeiro": True,
                  "nao": False, "n": False, "0": False, "false": False,
                  "falso": False, "nao_informado": False}
VOCAB_CICLO = {
    "infantil": eq.CICLO_INFANTIL, "educacao_infantil": eq.CICLO_INFANTIL,
    "creche": eq.CICLO_INFANTIL, "pre_escola": eq.CICLO_INFANTIL,
    "pre-escola": eq.CICLO_INFANTIL, "ei": eq.CICLO_INFANTIL,
    "fundamental_i": eq.CICLO_FUND_I, "fundamental_1": eq.CICLO_FUND_I,
    "anos_iniciais": eq.CICLO_FUND_I, "ef1": eq.CICLO_FUND_I,
    "ensino_fundamental_anos_iniciais": eq.CICLO_FUND_I,
    "fundamental_ii": eq.CICLO_FUND_II, "fundamental_2": eq.CICLO_FUND_II,
    "anos_finais": eq.CICLO_FUND_II, "ef2": eq.CICLO_FUND_II,
    "ensino_fundamental_anos_finais": eq.CICLO_FUND_II,
}

# Etapas que existem no cadastro e estão **fora do recorte**: a Portaria exige
# distância a equipamento de infantil (ENQ-009) e de fundamental ciclos I e II
# (ENQ-010.1/011.1); médio, profissional e EJA não geram requisito desses.
# Ficam reconhecidas de propósito, para não poluírem `valores_desconhecidos` —
# o que precisa aparecer lá é lacuna de verdade, não etapa que ignoramos.
ETAPAS_FORA_DO_ESCOPO = frozenset({
    "ensino_medio", "medio", "educacao_profissional", "profissional",
    "educacao_de_jovens_adultos", "educacao_de_jovens_e_adultos", "eja",
})

# **O problema central do R4b, nomeado em vez de resolvido por chute.** O
# Catálogo de Escolas informa "Ensino Fundamental" sem separar anos iniciais de
# anos finais, mas ENQ-010.1 (6 a 10 anos) e ENQ-011.1 (11 a 15) são requisitos
# distintos. Traduzir isto para os dois ciclos contaria como cobertura de anos
# finais uma escola que só tem anos iniciais. Então aqui a etapa é **contada e
# reportada**, não convertida: quem resolve é o microdado do Censo Escolar, que
# traz IN_FUND_AI e IN_FUND_AF por escola.
ETAPA_FUNDAMENTAL_INDISTINTA = frozenset({"ensino_fundamental", "fundamental"})

# Múltiplos ciclos numa célula. Aceita ';' ',' '/' e '|', mas o **modelo usa
# '|'** por um motivo prático descoberto ao escrever o próprio modelo: em CSV
# brasileiro o separador de campo é ';', então "fundamental_i;fundamental_ii"
# numa célula não citada quebra a linha em duas colunas. O '|' não colide com
# nenhum separador de campo usual. Célula citada ("a;b") também funciona, porque
# o csv.reader respeita as aspas.
SEPARADORES_CICLO = re.compile(r"[;,/|]+")


@dataclass
class Leitura:
    """Saída da leitura: o que virou equipamento, o que caiu e o que falta mapear."""

    equipamentos: list[eq.Equipamento] = field(default_factory=list)
    rejeitadas: list[tuple[int, str]] = field(default_factory=list)
    colunas_detectadas: dict[str, str] = field(default_factory=dict)
    faltando: list[str] = field(default_factory=list)
    valores_desconhecidos: dict[str, list[str]] = field(default_factory=dict)
    dialeto: dict = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    fundamental_indistinto: int = 0

    @property
    def ok(self) -> bool:
        return not self.faltando and bool(self.equipamentos)

    @property
    def precisa_mapeamento(self) -> bool:
        return bool(self.valores_desconhecidos)

    def to_dict(self) -> dict:
        return {"equipamentos": len(self.equipamentos),
                "rejeitadas": len(self.rejeitadas),
                "colunas_detectadas": self.colunas_detectadas,
                "faltando": self.faltando,
                "valores_desconhecidos": self.valores_desconhecidos,
                "dialeto": self.dialeto,
                "avisos": self.avisos,
                "fundamental_indistinto": self.fundamental_indistinto}


# ---------------------------------------------------------------------------
# Normalização e detecção
# ---------------------------------------------------------------------------

def normalizar(texto: str) -> str:
    """Minúsculo, sem acento, espaços e pontuação viram '_'."""
    if texto is None:
        return ""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", str(texto))
                         if not unicodedata.combining(c))
    limpo = re.sub(r"[^a-z0-9]+", "_", sem_acento.strip().lower())
    return limpo.strip("_")


# Tokens que DESQUALIFICAM uma coluna na busca aproximada de cada campo.
# Existe por um risco concreto do export do Catálogo, que traz "Código do
# Município" ao lado do código da escola: casar o código do município como
# chave de deduplicação juntaria escolas diferentes numa só.
NEGATIVOS: dict[str, set[str]] = {
    "codigo_inep": {"municipio", "uf", "estado", "regiao", "distrito", "ibge",
                    "mesorregiao", "microrregiao", "cep"},
    "nome": {"municipio", "uf", "estado", "regiao", "distrito", "gestor",
             "diretor", "orgao"},
    # "Restrição de Atendimento" é a coluna de SITUAÇÃO do Catálogo, que dobra
    # as duas dimensões numa célula. Se a busca aproximada a capturasse como
    # coluna de atendimento, o vocabulário não casaria e a segunda dimensão se
    # perderia em silêncio — justo o que esta coluna existe para evitar.
    "atendimento": {"restricao"},
}


def detectar_colunas(cabecalho: list[str]) -> tuple[dict[str, str], list[str]]:
    """``(campo -> coluna_original, campos_faltando)``.

    Duas passadas, e a ordem importa: **primeiro todos os aliases exatos**,
    depois a busca aproximada só para o que sobrou. Fazer campo a campo
    permitiria que a aproximação de um campo tomasse a coluna que o alias exato
    de outro reclamaria depois.

    Na passada exata percorre-se **os aliases na ordem declarada**, não as
    colunas do arquivo — é o que faz "Dependência Administrativa" ganhar de
    "Categoria Administrativa" mesmo vindo depois no cabeçalho.
    """
    normalizados = {col: normalizar(col) for col in cabecalho}
    detectadas: dict[str, str] = {}

    for campo, aliases in ALIASES.items():
        achou = False
        for alias in aliases:
            for col, norm in normalizados.items():
                if norm == alias and col not in detectadas.values():
                    detectadas[campo] = col
                    achou = True
                    break
            if achou:
                break

    for campo, aliases in ALIASES.items():
        if campo in detectadas:
            continue
        proibidos = NEGATIVOS.get(campo, set())
        for col, norm in normalizados.items():
            if col in detectadas.values():
                continue
            if any(t in norm for t in proibidos):
                continue
            if any(a in norm or norm in a for a in aliases if len(a) > 3):
                detectadas[campo] = col
                break

    faltando = [c for c in CAMPOS_OBRIGATORIOS if c not in detectadas]
    return detectadas, faltando


def _dialeto(amostra: str) -> dict:
    """Separador de campo do arquivo — CSV brasileiro costuma usar ';'."""
    try:
        sniff = csv.Sniffer().sniff(amostra, delimiters=";,\t|")
        separador = sniff.delimiter
    except csv.Error:
        separador = ";" if amostra.count(";") >= amostra.count(",") else ","
    return {"separador": separador}


def _ler_texto(caminho: str) -> tuple[str, str]:
    """Conteúdo e encoding — UTF-8 primeiro, latin-1 como rede de segurança."""
    with open(caminho, "rb") as f:
        bruto = f.read()
    if bruto[:3] == b"\xef\xbb\xbf":
        return bruto[3:].decode("utf-8", errors="replace"), "utf-8-sig"
    for codec in ("utf-8", "cp1252", "latin-1"):
        try:
            return bruto.decode(codec), codec
        except UnicodeDecodeError:
            continue
    return bruto.decode("latin-1", errors="replace"), "latin-1"


def _numero(texto: str) -> float | None:
    """Número decidindo o separador decimal **por valor**, não pelo dialeto.

    Deduzir o decimal do separador de campo é armadilha: um CSV com ';' entre
    campos e '.' decimal (perfeitamente comum, e possível no export do
    Catálogo) faria "-20.4712" virar "-204712". Regras, na ordem:

    * há ponto **e** vírgula → o decimal é o **último** que aparece;
    * só vírgula → é o decimal (uma só) ou agrupamento (várias);
    * só ponto, mais de um → agrupamento de milhar;
    * só ponto, um → decimal (é o caso das coordenadas).
    """
    if texto is None:
        return None
    limpo = str(texto).strip().replace(" ", "").replace("\u00a0", "")
    if not limpo:
        return None

    tem_ponto, tem_virgula = "." in limpo, "," in limpo
    if tem_ponto and tem_virgula:
        if limpo.rfind(",") > limpo.rfind("."):
            limpo = limpo.replace(".", "").replace(",", ".")
        else:
            limpo = limpo.replace(",", "")
    elif tem_virgula:
        limpo = (limpo.replace(",", ".") if limpo.count(",") == 1
                 else limpo.replace(",", ""))
    elif limpo.count(".") > 1:
        limpo = limpo.replace(".", "")

    try:
        return float(limpo)
    except ValueError:
        return None


def _situacao_e_atendimento(valor: str, desconhecidos: dict) -> tuple[str, str]:
    """``(situacao, atendimento)`` a partir de uma célula só.

    Duas tentativas, nesta ordem: vocabulário simples de situação (nosso CSV e
    o ``TP_SITUACAO_FUNCIONAMENTO`` do microdado) e, se não casar, o vocabulário
    composto da "Restrição de Atendimento" do Catálogo, que responde as duas
    perguntas de uma vez.
    """
    chave = normalizar(valor)
    if not chave:
        return "", eq.ATENDIMENTO_GERAL
    if chave in VOCAB_SITUACAO:
        return VOCAB_SITUACAO[chave], eq.ATENDIMENTO_GERAL
    if chave in VOCAB_RESTRICAO:
        return VOCAB_RESTRICAO[chave]
    lista = desconhecidos.setdefault("situacao", [])
    if valor not in lista:
        lista.append(valor)
    return "", eq.ATENDIMENTO_GERAL


def _booleano(valor: str) -> bool | None:
    """Sim/Não do Catálogo, 0/1 do microdado, ou ``None`` quando não informado."""
    chave = normalizar(valor)
    if not chave:
        return None
    return VOCAB_BOOLEANO.get(chave)


def _mapear(valor: str, vocabulario: dict, desconhecidos: dict, campo: str) -> str:
    """Traduz um valor para o vocabulário canônico; coleta o que não reconhece."""
    chave = normalizar(valor)
    if not chave:
        return ""
    if chave in vocabulario:
        return vocabulario[chave]
    lista = desconhecidos.setdefault(campo, [])
    if valor not in lista:
        lista.append(valor)
    return ""


def _ciclos(valor: str, desconhecidos: dict) -> tuple[list[str], bool]:
    """``(ciclos, fundamental_sem_distincao)`` — múltiplos por ';' ',' '/' '|'.

    Escola servindo fundamental I **e** II é o caso comum, não a exceção. Três
    destinos possíveis para cada pedaço: ciclo canônico, etapa fora do recorte
    (ignorada em silêncio, de propósito), e "Ensino Fundamental" sem distinção
    de ciclo — que não é traduzido nem ignorado: é **sinalizado**.
    """
    saida: list[str] = []
    indistinto = False
    for parte in SEPARADORES_CICLO.split(str(valor or "")):
        if not parte.strip():
            continue
        chave = normalizar(parte)
        if chave in ETAPAS_FORA_DO_ESCOPO:
            continue
        if chave in ETAPA_FUNDAMENTAL_INDISTINTA:
            indistinto = True
            continue
        canonico = _mapear(parte, VOCAB_CICLO, desconhecidos, "ciclo")
        if canonico and canonico not in saida:
            saida.append(canonico)
    return saida, indistinto


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def ler(caminho: str, *, fonte: str = eq.FONTE_CSV,
        precisao: str = eq.PRECISAO_DECLARADA) -> Leitura:
    """Lê o CSV e devolve equipamentos, rejeições e o que falta mapear."""
    texto, encoding = _ler_texto(caminho)
    amostra = texto[:8192]
    dialeto = _dialeto(amostra)
    dialeto["encoding"] = encoding

    leitor = csv.reader(io.StringIO(texto), delimiter=dialeto["separador"])
    linhas = [l for l in leitor if any((c or "").strip() for c in l)]
    if not linhas:
        return Leitura(faltando=list(CAMPOS_OBRIGATORIOS), dialeto=dialeto)

    cabecalho = [c.strip() for c in linhas[0]]
    detectadas, faltando = detectar_colunas(cabecalho)
    resultado = Leitura(colunas_detectadas=detectadas, faltando=faltando,
                        dialeto=dialeto)

    col_categoria = next((c for c in cabecalho
                          if normalizar(c) in COLUNAS_CATEGORIA), None)
    if "rede" in faltando and col_categoria:
        resultado.avisos.append(
            f"O arquivo tem '{col_categoria}' (Pública/Privada) mas não uma coluna "
            "de dependência administrativa. Pública não diz a esfera, e a esfera é "
            "filtro obrigatório — exporte também a coluna 'Dependência "
            "Administrativa'.")
    if faltando:
        return resultado

    indice = {campo: cabecalho.index(col) for campo, col in detectadas.items()}

    def celula(linha: list[str], campo: str) -> str:
        i = indice.get(campo)
        if i is None or i >= len(linha):
            return ""
        return (linha[i] or "").strip()

    def celula_indice(linha: list[str], i: int) -> str:
        return (linha[i] or "").strip() if i < len(linha) else ""

    i_categoria = cabecalho.index(col_categoria) if col_categoria else None
    divergencias: list[int] = []

    for numero_linha, linha in enumerate(linhas[1:], start=2):
        lat = _numero(celula(linha, "latitude"))
        lon = _numero(celula(linha, "longitude"))
        nome = celula(linha, "nome")

        if lat is None or lon is None:
            resultado.rejeitadas.append(
                (numero_linha, f"coordenada ausente ou ilegível ({nome or 'sem nome'})"))
            continue
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            resultado.rejeitadas.append(
                (numero_linha, f"coordenada fora do intervalo válido: {lat}, {lon}"))
            continue

        rede = _mapear(celula(linha, "rede"), VOCAB_REDE,
                       resultado.valores_desconhecidos, "rede")
        situacao, atendimento = _situacao_e_atendimento(
            celula(linha, "situacao"), resultado.valores_desconhecidos)
        ciclos, indistinto = _ciclos(celula(linha, "ciclo"),
                                     resultado.valores_desconhecidos)
        if indistinto:
            resultado.fundamental_indistinto += 1
        conveniada = _booleano(celula(linha, "conveniada"))

        # Coluna própria vence a dimensão derivada da célula de situação: quem
        # a escreveu tinha as duas dimensões separadas na origem. Valor não
        # reconhecido não silencia — vai para `valores_desconhecidos` e mantém
        # o derivado, porque descartar a linha inteira por causa dela seria
        # desproporcional (ela é opcional).
        if "atendimento" in indice:
            bruto = celula(linha, "atendimento")
            if bruto:
                explicito = _mapear(bruto, VOCAB_ATENDIMENTO,
                                    resultado.valores_desconhecidos, "atendimento")
                if explicito:
                    atendimento = explicito

        if i_categoria is not None and rede:
            categoria = normalizar(celula_indice(linha, i_categoria))
            if categoria == "publica" and rede == eq.REDE_PRIVADA or categoria == "privada" and rede in eq.REDES_PUBLICAS:
                divergencias.append(numero_linha)

        if not rede:
            resultado.rejeitadas.append(
                (numero_linha, (f"rede não informada ou não reconhecida "
                               f"({nome or 'sem nome'}) — é filtro obrigatório")))
            continue
        if not situacao:
            resultado.rejeitadas.append(
                (numero_linha, (f"situação não informada ou não reconhecida "
                               f"({nome or 'sem nome'}) — é filtro obrigatório")))
            continue

        codigo = celula(linha, "codigo_inep") or None
        resultado.equipamentos.append(eq.Equipamento(
            nome=nome or f"(sem nome, linha {numero_linha})",
            lat=lat, lon=lon, ciclos=ciclos, rede=rede, situacao=situacao,
            atendimento=atendimento, conveniada=conveniada,
            fonte=fonte, precisao=precisao,
            codigo_inep=codigo, endereco=celula(linha, "endereco") or None,
            procedencia={"arquivo": caminho, "linha": numero_linha,
                         "encoding": encoding}))

    if divergencias:
        resultado.avisos.append(
            f"{len(divergencias)} linha(s) em que '{col_categoria}' discorda da "
            f"dependência administrativa (primeira: linha {divergencias[0]}). "
            "A dependência foi usada; verifique o export.")
    if resultado.fundamental_indistinto:
        resultado.avisos.append(
            f"{resultado.fundamental_indistinto} escola(s) com etapa 'Ensino "
            "Fundamental' sem distinção entre anos iniciais e finais. ENQ-010.1 e "
            "ENQ-011.1 são requisitos distintos, então essas escolas NÃO contam "
            "para nenhum dos dois — a distinção vem do microdado do Censo Escolar "
            "(IN_FUND_AI / IN_FUND_AF).")

    return resultado


# ---------------------------------------------------------------------------
# CLI de diagnóstico
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Recorte municipal versionado — ``config/equipamentos_<ibge>.csv``
#
# Estas funções ficam no adaptador que sabe ler o CSV, e não dentro da regra de
# distância; quem decide QUANDO resolver é
# ``core/aplicacao/resolver_territorio.py``. Mesma pasta relativa ao CWD, mesmo
# cache por (caminho, mtime).
# ---------------------------------------------------------------------------

PASTA_RECORTES = os.path.join("config")

# Cache do recorte por (caminho, mtime). O mtime não é zelo excessivo: sem ele,
# regerar o recorte com o app aberto serviria dado velho em silêncio — a mesma
# família do "cache que mente" que o gerador já evita pelo SHA-256.
_CACHE: dict[tuple[str, float], Leitura] = {}


def caminho_do_recorte(codigo_ibge: str, pasta: str = PASTA_RECORTES) -> str:
    return os.path.join(pasta, f"equipamentos_{codigo_ibge}.csv")


def carregar_recorte(codigo_ibge: str, pasta: str = PASTA_RECORTES):
    """``Leitura`` do recorte municipal, ou ``None`` se o arquivo não existe."""
    caminho = caminho_do_recorte(codigo_ibge, pasta)
    if not os.path.exists(caminho):
        return None
    chave = (caminho, os.path.getmtime(caminho))
    if chave not in _CACHE:
        _CACHE.clear()          # um município por vez na tela; cache minúsculo
        _CACHE[chave] = ler(caminho, fonte=eq.FONTE_INEP,
                            precisao=eq.PRECISAO_OFICIAL)
    return _CACHE[chave]


def procedencia_do_recorte(codigo_ibge: str, pasta: str = PASTA_RECORTES) -> dict:
    """Safra do Censo e data de geração, do ``.json`` que acompanha o recorte."""
    import json

    caminho = os.path.join(pasta, f"equipamentos_{codigo_ibge}.json")
    if not os.path.exists(caminho):
        return {}
    try:
        with open(caminho, encoding="utf-8") as f:
            proc = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return {"ano_censo": proc.get("ano_censo"),
            "gerado_em": proc.get("gerado_em"),
            "nome_municipio": proc.get("nome_municipio"),
            "uf": proc.get("uf"),
            "fontes": [f.get("arquivo") for f in proc.get("fontes", [])]}


def recorte_municipal(codigo_ibge: str,
                      pasta: str = PASTA_RECORTES) -> eq.RecorteMunicipal:
    """O recorte do município como objeto de domínio — presente ou ausente.

    Único montador de ``RecorteMunicipal``: o resolvedor da aplicação e o caminho
    legado da regra passam os dois por aqui, para que não possam divergir.
    """
    codigo = str(codigo_ibge or "").strip()
    return eq.RecorteMunicipal(
        codigo_ibge=codigo,
        origem=caminho_do_recorte(codigo, pasta),
        leitura=carregar_recorte(codigo, pasta),
        procedencia=procedencia_do_recorte(codigo, pasta))


def _cli() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="Diagnostica a leitura de um CSV de equipamentos de educação.")
    p.add_argument("csv", help="Caminho do arquivo CSV.")
    p.add_argument("--ciclo", choices=list(eq.CICLOS), default=None,
                   help="Aplica também o filtro de ciclo.")
    p.add_argument("--populacao", type=int, default=None,
                   help="População municipal, para o teste de plausibilidade.")
    args = p.parse_args()

    leitura = ler(args.csv)
    print("=" * 72)
    print(f"ARQUIVO  : {args.csv}")
    print(f"DIALETO  : separador {leitura.dialeto.get('separador')!r} · "
          f"encoding {leitura.dialeto.get('encoding')} · "
          f"decimal decidido por valor")
    print("\nCOLUNAS DETECTADAS")
    for campo in CAMPOS_OBRIGATORIOS + CAMPOS_OPCIONAIS:
        col = leitura.colunas_detectadas.get(campo)
        print(f"  {campo:<12} -> {col!r}" if col else f"  {campo:<12} -> (não encontrada)")
    if leitura.faltando:
        print(f"\nFALTAM COLUNAS OBRIGATÓRIAS: {', '.join(leitura.faltando)}")
        return

    print(f"\nLIDOS    : {len(leitura.equipamentos)} equipamento(s)")
    if leitura.rejeitadas:
        print(f"REJEITADAS: {len(leitura.rejeitadas)} linha(s)")
        for numero, motivo in leitura.rejeitadas[:15]:
            print(f"  linha {numero}: {motivo}")
        if len(leitura.rejeitadas) > 15:
            print(f"  ... e outras {len(leitura.rejeitadas) - 15}")
    if leitura.valores_desconhecidos:
        print("\nVALORES A MAPEAR (formulário de mapeamento semântico)")
        for campo, valores in leitura.valores_desconhecidos.items():
            print(f"  {campo}: {valores}")

    filtragem = eq.filtrar(leitura.equipamentos, ciclo=args.ciclo)
    print(f"\nFILTROS NORMATIVOS (pública + ativa"
          f"{' + ciclo ' + args.ciclo if args.ciclo else ''})")
    print(f"  {filtragem.resumo()}")

    if args.ciclo:
        sinais = eq.sanidade(filtragem.aceitos, ciclo=args.ciclo,
                             populacao_municipal=args.populacao,
                             total_no_conjunto=filtragem.total)
        print(f"\nSANIDADE DO INSUMO: {len(sinais)} sinal(is)")
        for s in sinais:
            print(f"  [{s.codigo}] {s.mensagem}")


if __name__ == "__main__":
    _cli()
