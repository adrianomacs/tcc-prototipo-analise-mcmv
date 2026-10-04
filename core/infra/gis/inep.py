"""Fontes nacionais do INEP → ``Equipamento`` canônico, por município.

Terceiro construtor do ``Equipamento`` e o único que lê fonte
oficial. A diferença para o ``de_csv_equipamentos`` é que aqui **não há um
arquivo**: há três, cada um respondendo a uma parte da pergunta, e nenhum
respondendo sozinho.

Por que três
------------

A divulgação pública do Censo Escolar 2025 (``Tabela_Escola_2025_V2.csv``)
**não traz coordenada**: ``LATITUDE`` e ``LONGITUDE`` constam do dicionário, mas
o arquivo publicado retirou todo o bloco de endereço. E **não traz oferta de
etapa**: ``IN_INF``/``IN_FUND_AI``/``IN_FUND_AF`` não existem nesta safra. O
candidato de nome parecido, ``IN_COMUM_FUND_AI``, significa outra coisa —
"escola oferece matrículas *de alunos com deficiência, TEA ou altas
habilidades* em classes comuns, anos iniciais". Usá-lo como oferta de etapa
daria um número plausível e errado, que é a pior espécie de defeito nesta
ferramenta.

Então a precedência do ``mesclar()`` deixa de poder ser **por registro** e passa
a ser **por campo** — não por escolha de projeto, mas por imposição da fonte:

===================================  ====================================
campo                                fonte canônica
===================================  ====================================
identidade, rede, situação           ``Tabela_Escola`` (microdado)
ciclo ofertado                       ``Tabela_Turma`` (microdado)
coordenada, endereço, convênio       Catálogo de Escolas
===================================  ====================================

Cada equipamento carrega em ``procedencia`` de qual arquivo veio cada campo.
Um "não conforme" precisa ser auditável até a origem do dado que o produziu.

O que NÃO é feito aqui
----------------------

Nada é inventado para preencher lacuna. Escola sem coordenada no Catálogo entra
no conjunto **sem coordenada** e é descartada pelo ``filtrar`` com motivo
``sem_coordenada`` — visível, contado, e caminho aberto para o CSV
complementar. Converter etapa indistinta, interpolar coordenada pelo centróide
do município ou assumir "pública" quando a rede não vem seriam todas formas de
produzir conformidade falsa.

Divergência entre as duas fontes oficiais também não é resolvida no silêncio:
ela é **medida** e devolvida em ``Divergencias``. Duas bases oficiais sobre o
mesmo município discordando é qualidade de dado, e é resultado publicável.

Derivações verificadas contra rótulo, não supostas
--------------------------------------------------

Duas propriedades do ``Equipamento`` não existem como coluna no microdado e
foram **derivadas**. Cada derivação foi conferida contra o rótulo que o Catálogo
publica, em escala nacional (~209 mil estabelecimentos), antes de virar código:

* ``atendimento == exclusivo_deficiencia`` ⟸ todas as turmas da escola são
  classes exclusivas (``QT_TUR_ESP_CE == QT_TUR_BAS > 0``).
  Confere com o rótulo em 1.551 de 1.643 casos; 189 divergências no total.
* ``atendimento == sem_escolarizacao`` ⟸ ``IN_ESCOLARIZACAO == 0`` **entre
  escolas em atividade**. A restrição importa: escola paralisada ou extinta tem
  ``IN_ESCOLARIZACAO == 0`` trivialmente, e sem o recorte a derivação disparava
  para 34 mil estabelecimentos contra 683 rotulados. Com ele, confere em 1.419
  de 1.484; 274 divergências.

As divergências residuais não são erro a esconder: são vintages diferentes (o
microdado é o retrato do Censo de um ano; o Catálogo é o cadastro corrente).
"""

from __future__ import annotations

import csv
import hashlib
import os
from dataclasses import dataclass, field

from core.dominio import equipamentos as eq
from core.infra.gis.csv_equipamentos import _numero as ler_numero

# ---------------------------------------------------------------------------
# Papéis e colunas exigidas de cada arquivo
# ---------------------------------------------------------------------------

PAPEL_ESCOLA = "escola"
PAPEL_TURMA = "turma"
PAPEL_CATALOGO = "catalogo"
PAPEIS = (PAPEL_ESCOLA, PAPEL_TURMA, PAPEL_CATALOGO)

# Exigidas para o adaptador funcionar. Ausência aqui interrompe a extração e é
# reportada pelo nome — nunca contornada por aproximação, porque nome parecido
# no microdado já provou não significar coisa parecida.
COLUNAS_ESCOLA = ("CO_ENTIDADE", "NO_ENTIDADE", "CO_MUNICIPIO", "TP_DEPENDENCIA",
                  "TP_SITUACAO_FUNCIONAMENTO", "IN_ESCOLARIZACAO")
COLUNAS_TURMA = ("CO_ENTIDADE", "CO_MUNICIPIO", "QT_TUR_BAS", "QT_TUR_ESP_CE",
                 "QT_TUR_INF_CRE", "QT_TUR_INF_PRE", "QT_TUR_FUND_AI",
                 "QT_TUR_FUND_AF")
COLUNAS_CATALOGO = ("Código INEP", "Latitude", "Longitude")

# Opcionais: ausentes, o campo correspondente fica vazio e um aviso é emitido.
OPCIONAIS_ESCOLA = ("NU_ANO_CENSO", "NO_MUNICIPIO", "SG_UF",
                    "IN_PODER_PUBLICO_PARCERIA")
OPCIONAIS_TURMA = ("QT_TUR_FUND_AI_MULTIETAPA",)
OPCIONAIS_CATALOGO = ("Escola", "Endereço", "Conveniada Poder Público",
                      "Restrição de Atendimento", "Município", "UF")

# --- Vocabulários do microdado (dicionário oficial, safra 2025) -------------
DEPENDENCIA = {"1": eq.REDE_FEDERAL, "2": eq.REDE_ESTADUAL,
               "3": eq.REDE_MUNICIPAL, "4": eq.REDE_PRIVADA}
SITUACAO = {"1": eq.SITUACAO_ATIVA, "2": eq.SITUACAO_PARALISADA,
            "3": eq.SITUACAO_EXTINTA, "4": eq.SITUACAO_EXTINTA}

# --- Turmas que decidem o ciclo --------------------------------------------
# A Portaria trata a educação infantil como faixa única de 0 a 5 anos,
# então creche OU pré-escola atendem o ENQ-009 —
# ao contrário do fundamental, cujos dois ciclos são requisitos distintos e
# jamais somados.
TURMAS_POR_CICLO = {
    eq.CICLO_INFANTIL: ("QT_TUR_INF_CRE", "QT_TUR_INF_PRE"),
    eq.CICLO_FUND_I: ("QT_TUR_FUND_AI",),
    eq.CICLO_FUND_II: ("QT_TUR_FUND_AF",),
}


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class Fonte:
    """Um arquivo de entrada e o que o torna citável."""

    papel: str
    caminho: str
    sha256: str = ""
    bytes: int = 0
    linhas_lidas: int = 0
    linhas_no_municipio: int = 0

    def to_dict(self) -> dict:
        return {"papel": self.papel, "arquivo": os.path.basename(self.caminho),
                "sha256": self.sha256, "bytes": self.bytes,
                "linhas_lidas": self.linhas_lidas,
                "linhas_no_municipio": self.linhas_no_municipio}


@dataclass
class Divergencias:
    """O que as duas fontes oficiais dizem de diferente — medido, não resolvido."""

    so_no_microdado: list[str] = field(default_factory=list)
    so_no_catalogo: list[str] = field(default_factory=list)
    situacao_divergente: list[str] = field(default_factory=list)
    atendimento_divergente: list[str] = field(default_factory=list)
    conveniada_divergente: list[str] = field(default_factory=list)
    sem_linha_de_turma: list[str] = field(default_factory=list)

    CAMPOS = ("so_no_microdado", "so_no_catalogo", "situacao_divergente",
              "atendimento_divergente", "conveniada_divergente",
              "sem_linha_de_turma")

    @property
    def total(self) -> int:
        return sum(len(getattr(self, c)) for c in self.CAMPOS)

    def to_dict(self) -> dict:
        d = {c: len(getattr(self, c)) for c in self.CAMPOS}
        d["codigos"] = {c: getattr(self, c)[:50] for c in self.CAMPOS}
        return d


@dataclass
class Extracao:
    """Saída da extração — espelha a ``Leitura`` do leitor de CSV."""

    equipamentos: list[eq.Equipamento] = field(default_factory=list)
    municipio: str = ""
    nome_municipio: str = ""
    uf: str = ""
    ano_censo: str = ""
    faltando: dict[str, list[str]] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    fontes: list[Fonte] = field(default_factory=list)
    divergencias: Divergencias = field(default_factory=Divergencias)
    multietapa: int = 0

    @property
    def ok(self) -> bool:
        return not self.faltando and bool(self.equipamentos)

    @property
    def com_coordenada(self) -> int:
        return sum(1 for e in self.equipamentos if e.lat is not None)

    def to_dict(self) -> dict:
        return {"municipio": self.municipio,
                "nome_municipio": self.nome_municipio, "uf": self.uf,
                "ano_censo": self.ano_censo,
                "equipamentos": len(self.equipamentos),
                "com_coordenada": self.com_coordenada,
                "faltando": self.faltando, "avisos": self.avisos,
                "fontes": [f.to_dict() for f in self.fontes],
                "divergencias": self.divergencias.to_dict(),
                "multietapa": self.multietapa}


# ---------------------------------------------------------------------------
# Leitura em streaming
# ---------------------------------------------------------------------------

def _inteiro(texto: str) -> int:
    """Contagem de turmas; vazio e lixo valem zero, nunca levantam."""
    texto = (texto or "").strip()
    return int(texto) if texto.lstrip("-").isdigit() else 0


def _encoding(caminho: str) -> str:
    """Encoding decidido pelo início do arquivo, tolerando o corte do trecho.

    Mesma armadilha do inspetor: o trecho é um corte arbitrário, e um caractere
    multibyte partido nele não significa "não é UTF-8". O decodificador
    incremental com ``final=False`` guarda a cauda em vez de falhar.
    """
    import codecs
    with open(caminho, "rb") as f:
        inicio = f.read(65536)
    if inicio[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    try:
        codecs.getincrementaldecoder("utf-8")().decode(inicio, False)
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def _separador(caminho: str, encoding: str) -> str:
    with open(caminho, "rb") as f:
        linha = f.read(65536).decode(encoding, errors="replace").splitlines()
    linha = linha[0] if linha else ""
    return max((";", ",", "\t", "|"), key=linha.count)


def sha256(caminho: str, *, bloco: int = 1 << 20) -> str:
    """SHA-256 em blocos — o arquivo é nacional e não cabe em memória.

    Não é burocracia: é o que permite a um terceiro conferir que o recorte
    versionado saiu **daquele** arquivo, e o que deixa o gerador detectar
    recorte defasado em vez de reusá-lo calado.
    """
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for pedaco in iter(lambda: f.read(bloco), b""):
            h.update(pedaco)
    return h.hexdigest()


def _abrir(caminho: str):
    enc = _encoding(caminho)
    sep = _separador(caminho, enc)
    f = open(caminho, encoding=enc, errors="replace", newline="")
    leitor = csv.reader(f, delimiter=sep)
    try:
        cabecalho = [c.strip() for c in next(leitor)]
    except StopIteration:
        f.close()
        return None, [], {}, None
    indice = {}
    for i, nome in enumerate(cabecalho):
        if nome and nome not in indice:      # duplicata fica com a primeira
            indice[nome] = i
    return f, cabecalho, indice, leitor


def _campo(linha: list[str], indice: dict, nome: str) -> str:
    i = indice.get(nome)
    if i is None or i >= len(linha):
        return ""
    return (linha[i] or "").strip()


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------

def extrair(codigo_ibge: str, *, escola: str, turma: str, catalogo: str,
            calcular_sha: bool = True) -> Extracao:
    """Recorte municipal canônico a partir das três fontes nacionais.

    ``codigo_ibge`` é o código de 7 dígitos — e não o nome, de propósito: nome
    depende de acentuação e de grafia, e é a espécie de chave que falha em
    silêncio.
    """
    codigo_ibge = str(codigo_ibge).strip()
    res = Extracao(municipio=codigo_ibge)

    exigidas = {PAPEL_ESCOLA: (escola, COLUNAS_ESCOLA, OPCIONAIS_ESCOLA),
                PAPEL_TURMA: (turma, COLUNAS_TURMA, OPCIONAIS_TURMA),
                PAPEL_CATALOGO: (catalogo, COLUNAS_CATALOGO, OPCIONAIS_CATALOGO)}
    aberturas: dict[str, tuple] = {}
    for papel, (caminho, obrig, opc) in exigidas.items():
        if not caminho or not os.path.exists(caminho):
            res.faltando[papel] = [f"arquivo não encontrado: {caminho}"]
            continue
        f, _cab, indice, leitor = _abrir(caminho)
        if leitor is None:
            res.faltando[papel] = ["arquivo vazio"]
            continue
        ausentes = [c for c in obrig if c not in indice]
        if ausentes:
            res.faltando[papel] = ausentes
            f.close()
            continue
        for c in opc:
            if c not in indice:
                res.avisos.append(
                    f"{papel}: coluna opcional '{c}' ausente — o campo "
                    "correspondente fica vazio.")
        aberturas[papel] = (f, indice, leitor, caminho)

    if res.faltando:
        for f, _, _, _ in aberturas.values():
            f.close()
        return res

    # --- 1. Tabela_Escola: identidade, rede, situação ----------------------
    f, ix, leitor, caminho = aberturas[PAPEL_ESCOLA]
    fonte = Fonte(PAPEL_ESCOLA, caminho)
    escolas: dict[str, dict] = {}
    with f:
        for linha in leitor:
            fonte.linhas_lidas += 1
            if _campo(linha, ix, "CO_MUNICIPIO") != codigo_ibge:
                continue
            fonte.linhas_no_municipio += 1
            codigo = _campo(linha, ix, "CO_ENTIDADE")
            if not codigo:
                continue
            situacao = SITUACAO.get(_campo(linha, ix, "TP_SITUACAO_FUNCIONAMENTO"), "")
            escolas[codigo] = {
                "nome": _campo(linha, ix, "NO_ENTIDADE"),
                "rede": DEPENDENCIA.get(_campo(linha, ix, "TP_DEPENDENCIA"), ""),
                "situacao": situacao,
                "escolariza": _inteiro(_campo(linha, ix, "IN_ESCOLARIZACAO")),
                "parceria": _inteiro(_campo(linha, ix, "IN_PODER_PUBLICO_PARCERIA")),
            }
            if not res.ano_censo:
                res.ano_censo = _campo(linha, ix, "NU_ANO_CENSO")
                res.nome_municipio = _campo(linha, ix, "NO_MUNICIPIO")
                res.uf = _campo(linha, ix, "SG_UF")
    fonte.sha256 = sha256(caminho) if calcular_sha else ""
    fonte.bytes = os.path.getsize(caminho)
    res.fontes.append(fonte)

    if not escolas:
        res.avisos.append(
            f"Nenhuma escola com CO_MUNICIPIO = {codigo_ibge} no microdado. "
            "Confira o código IBGE de 7 dígitos.")
        for resto in (PAPEL_TURMA, PAPEL_CATALOGO):
            aberturas[resto][0].close()
        return res

    # --- 2. Tabela_Turma: ciclo ofertado e atendimento exclusivo ----------
    f, ix, leitor, caminho = aberturas[PAPEL_TURMA]
    fonte = Fonte(PAPEL_TURMA, caminho)
    turmas: dict[str, dict] = {}
    with f:
        for linha in leitor:
            fonte.linhas_lidas += 1
            if _campo(linha, ix, "CO_MUNICIPIO") != codigo_ibge:
                continue
            fonte.linhas_no_municipio += 1
            codigo = _campo(linha, ix, "CO_ENTIDADE")
            if not codigo:
                continue
            contagens = {c: _inteiro(_campo(linha, ix, c))
                         for c in COLUNAS_TURMA if c.startswith("QT_")}
            contagens["QT_TUR_FUND_AI_MULTIETAPA"] = _inteiro(
                _campo(linha, ix, "QT_TUR_FUND_AI_MULTIETAPA"))
            turmas[codigo] = contagens
    fonte.sha256 = sha256(caminho) if calcular_sha else ""
    fonte.bytes = os.path.getsize(caminho)
    res.fontes.append(fonte)

    # --- 3. Catálogo: coordenada, endereço, convênio ----------------------
    f, ix, leitor, caminho = aberturas[PAPEL_CATALOGO]
    fonte = Fonte(PAPEL_CATALOGO, caminho)
    do_catalogo: dict[str, dict] = {}
    # O Catálogo não traz o código IBGE — só nome do município e UF. Para
    # detectar o que existe nele e não no microdado, é preciso casar por
    # nome+UF, e é a única chave disponível. Fica explícito que é chave frágil.
    alvo_nome = (res.nome_municipio or "").strip().lower()
    alvo_uf = (res.uf or "").strip().upper()
    so_no_catalogo: list[str] = []
    with f:
        for linha in leitor:
            fonte.linhas_lidas += 1
            codigo = _campo(linha, ix, "Código INEP")
            if codigo not in escolas:
                if alvo_nome and codigo \
                        and _campo(linha, ix, "Município").strip().lower() == alvo_nome \
                        and _campo(linha, ix, "UF").strip().upper() == alvo_uf:
                    so_no_catalogo.append(codigo)
                continue
            fonte.linhas_no_municipio += 1
            conv = _campo(linha, ix, "Conveniada Poder Público").lower()
            do_catalogo[codigo] = {
                "lat": ler_numero(_campo(linha, ix, "Latitude")),
                "lon": ler_numero(_campo(linha, ix, "Longitude")),
                "endereco": _campo(linha, ix, "Endereço") or None,
                "conveniada": True if conv.startswith("s")
                else (False if conv.startswith("n") else None),
                "restricao": _campo(linha, ix, "Restrição de Atendimento").upper(),
            }
    fonte.sha256 = sha256(caminho) if calcular_sha else ""
    fonte.bytes = os.path.getsize(caminho)
    res.fontes.append(fonte)

    # --- 4. Composição, campo a campo -------------------------------------
    for codigo, base in sorted(escolas.items()):
        t = turmas.get(codigo)
        c = do_catalogo.get(codigo)
        if t is None:
            res.divergencias.sem_linha_de_turma.append(codigo)
        if c is None:
            res.divergencias.so_no_microdado.append(codigo)

        ciclos = []
        if t:
            for ciclo, colunas in TURMAS_POR_CICLO.items():
                if any(t.get(col, 0) > 0 for col in colunas):
                    ciclos.append(ciclo)
            if t.get("QT_TUR_FUND_AI_MULTIETAPA", 0) > 0:
                res.multietapa += 1

        atendimento = _atendimento(base, t)
        if c and c.get("restricao"):
            # Duas perguntas distintas, comparadas separadamente — fundi-las
            # repetiria o erro que a própria coluna do Catálogo comete.
            if ("PARALISADA" in c["restricao"]) is (base["situacao"] == eq.SITUACAO_ATIVA):
                res.divergencias.situacao_divergente.append(codigo)
            if ("DEFICIÊNCIA" in c["restricao"]) is not \
                    (atendimento == eq.ATENDIMENTO_EXCLUSIVO_DEFICIENCIA):
                res.divergencias.atendimento_divergente.append(codigo)

        conveniada = c["conveniada"] if c else None
        # O microdado desta safra não tem `IN_CONVENIADA_PP`: o mais próximo é
        # `IN_PODER_PUBLICO_PARCERIA`, que é conceito MAIS LARGO (parceria ou
        # convênio). Por isso o campo canônico vem do Catálogo, que rotula
        # exatamente "Conveniada Poder Público" — usar o proxy largo seria o
        # erro do `IN_COMUM_*` em miniatura. O confronto vira número.
        if conveniada is not None and bool(base["parceria"]) != conveniada:
            res.divergencias.conveniada_divergente.append(codigo)

        res.equipamentos.append(eq.Equipamento(
            nome=base["nome"],
            lat=c["lat"] if c else None,
            lon=c["lon"] if c else None,
            ciclos=ciclos,
            rede=base["rede"],
            situacao=base["situacao"],
            atendimento=atendimento,
            conveniada=conveniada,
            fonte=eq.FONTE_INEP,
            precisao=eq.PRECISAO_OFICIAL,
            codigo_inep=codigo,
            endereco=c["endereco"] if c else None,
            procedencia={
                "identidade": "microdado/Tabela_Escola",
                "rede": "microdado/Tabela_Escola",
                "situacao": "microdado/Tabela_Escola",
                "ciclos": "microdado/Tabela_Turma" if t else "ausente",
                "coordenada": "catalogo" if c and c["lat"] is not None else "ausente",
                "conveniada": "catalogo" if conveniada is not None else "ausente",
                "ano_censo": res.ano_censo,
            }))

    # códigos presentes só no Catálogo não entram no conjunto — o microdado é
    # canônico para identidade —, mas a contagem é reportada.
    res.divergencias.so_no_catalogo = sorted(so_no_catalogo)

    sem_coord = len(res.equipamentos) - res.com_coordenada
    if sem_coord:
        res.avisos.append(
            f"{sem_coord} de {len(res.equipamentos)} estabelecimento(s) sem "
            "coordenada no Catálogo. Eles entram no conjunto e são descartados "
            "com motivo 'sem_coordenada' — lacuna para o CSV complementar "
            "resolver, nunca motivo para reprovar o requisito.")
    if res.divergencias.sem_linha_de_turma:
        res.avisos.append(
            f"{len(res.divergencias.sem_linha_de_turma)} estabelecimento(s) sem "
            "linha na Tabela_Turma: não ofertam turma alguma, e por isso ficam "
            "sem ciclo. Não é lacuna de leitura.")
    if res.multietapa:
        res.avisos.append(
            f"{res.multietapa} estabelecimento(s) com turma multietapa "
            "(educação infantil e anos iniciais na mesma turma). São contados "
            "no ciclo de cada coluna que os declara e sinalizados aqui, nunca "
            "convertidos de um ciclo para o outro.")
    return res


def _atendimento(base: dict, turmas: dict | None) -> str:
    """Deriva a dimensão *quem a escola atende*, separada da situação.

    As duas derivações foram conferidas contra o rótulo do Catálogo em escala
    nacional (ver o docstring do módulo). A ordem importa: a pergunta "escolariza
    alguém?" só faz sentido para escola em atividade, porque escola paralisada ou
    extinta tem ``IN_ESCOLARIZACAO == 0`` por definição, não por vocação.
    """
    if turmas and turmas.get("QT_TUR_BAS", 0) > 0 and \
            turmas.get("QT_TUR_ESP_CE", 0) == turmas["QT_TUR_BAS"]:
        return eq.ATENDIMENTO_EXCLUSIVO_DEFICIENCIA
    if base["situacao"] == eq.SITUACAO_ATIVA and not base["escolariza"]:
        return eq.ATENDIMENTO_SEM_ESCOLARIZACAO
    return eq.ATENDIMENTO_GERAL


# ---------------------------------------------------------------------------
# Busca de município — porque a chave é o código, e ninguém o sabe de cor
# ---------------------------------------------------------------------------

def procurar_municipios(escola: str, texto: str, *,
                        uf: str | None = None) -> list[tuple[str, str, str, int]]:
    """``[(codigo_ibge, nome, uf, n_estabelecimentos)]`` casando com ``texto``.

    A extração exige o **código IBGE de 7 dígitos**, e não o nome, por um motivo
    já pago: nome depende de acentuação e de grafia, e é a espécie de chave que
    falha em silêncio. Mas exigir o código sem oferecer como descobri-lo
    empurraria o usuário para procurá-lo fora da ferramenta — e digitá-lo
    errado. Então a busca é por nome, sem acento e sem caixa, e o que ela
    devolve é o código.

    A contagem de estabelecimentos vai junto para desempatar homônimos: o Brasil
    tem várias "Bom Jesus", e a maior costuma ser a procurada — mas quem decide é
    quem lê, não este código.
    """
    import unicodedata

    def simplificar(valor: str) -> str:
        sem_acento = "".join(c for c in unicodedata.normalize("NFKD", valor or "")
                             if not unicodedata.combining(c))
        return sem_acento.strip().lower()

    alvo = simplificar(texto)
    uf_alvo = (uf or "").strip().upper()
    if not os.path.exists(escola):
        return []
    f, _, ix, leitor = _abrir(escola)
    if leitor is None:
        return []
    faltantes = [c for c in ("CO_MUNICIPIO", "NO_MUNICIPIO", "SG_UF") if c not in ix]
    if faltantes:
        f.close()
        return []
    achados: dict[str, list] = {}
    with f:
        for linha in leitor:
            nome = _campo(linha, ix, "NO_MUNICIPIO")
            sigla = _campo(linha, ix, "SG_UF")
            if uf_alvo and sigla.upper() != uf_alvo:
                continue
            if alvo and alvo not in simplificar(nome):
                continue
            codigo = _campo(linha, ix, "CO_MUNICIPIO")
            if not codigo:
                continue
            if codigo in achados:
                achados[codigo][3] += 1
            else:
                achados[codigo] = [codigo, nome, sigla, 1]
    return [tuple(v) for v in sorted(achados.values(), key=lambda v: (v[2], v[1]))]
