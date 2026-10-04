"""Relatório de Checagem (2.4.2) — o texto descritivo montado das análises gravadas.

ADR-035: o texto sai **só** dos relatórios das checagens gravados em
`artefatos/relatorios/` (ADR-001), de forma determinística — mesmo relatório,
mesmo texto —, sem modelo de linguagem e sem frase que não decorra de um
requisito verificado. É isso que o torna auditável: cada frase aponta o id do
requisito de onde veio, e o que ela afirma está num campo que a regra gravou.

O construtor é puro (:func:`montar` recebe os relatórios e a frase do
empreendimento e devolve um :class:`Parecer`); a página só o desenha. Onde há
modelo de frase por tipo de regra (``detalhe["tipo"]``), a frase é montada dos
campos gravados, no formato de número brasileiro; onde não há, usa-se a 1.ª
frase da mensagem da regra. Mensagem de regra não é reescrita aqui (ela mora
em ``core/``, e mudá-la mexe na linha de base).

As pendências seguem a tabela motivo → destinatário do ADR-035
(:data:`DESTINATARIO`), com a ação de `motivos.ACAO` — a mesma da tela.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.servicos import motivos
from app.servicos import relatorios as rel

# --- Destinatários (ADR-035) -------------------------------------------------
PROPONENTE = "proponente"
ANALISE_HUMANA = "analise_humana"
FERRAMENTA = "ferramenta"

TITULO_DESTINATARIO = {
    PROPONENTE: "Ao proponente",
    ANALISE_HUMANA: "À análise humana",
    FERRAMENTA: "À configuração da ferramenta e às bases",
}

# ``None``: o motivo não gera pendência própria (ADR-035). `nao_aplicavel` só
# aparece no texto; `prerequisito_falho` é anexado à pendência do
# pré-requisito; `agregacao_indecisa` se desdobra nas alternativas em aberto.
DESTINATARIO = {
    motivos.INFORMACAO_AUSENTE: PROPONENTE,
    motivos.INSUMO_DO_PROPONENTE_AUSENTE: PROPONENTE,
    motivos.INCONSISTENCIA_DECLARATORIA: PROPONENTE,
    motivos.TERRENO_INSUFICIENTE: PROPONENTE,
    motivos.TERRENO_AUSENTE: PROPONENTE,
    motivos.VERIFICACAO_EM_CAMPO: ANALISE_HUMANA,
    motivos.ANALISE_HUMANA_DOCUMENTAL: ANALISE_HUMANA,
    motivos.PORTE_INDETERMINADO: ANALISE_HUMANA,
    motivos.METRICA_INSUFICIENTE: FERRAMENTA,
    motivos.INSUMO_AUSENTE: FERRAMENTA,
    motivos.INSUMO_SUSPEITO: FERRAMENTA,
    motivos.MAPEAMENTO_PENDENTE: FERRAMENTA,
    motivos.MEMBRO_NAO_EXECUTADO: FERRAMENTA,
    motivos.ERRO_DE_EXECUCAO: FERRAMENTA,
    motivos.NAO_APLICAVEL: None,
    motivos.PREREQUISITO_FALHO: None,
    motivos.AGREGACAO_INDECISA: None,
}

# Chave de pendência para a não conformidade (não é motivo da taxonomia).
NAO_CONFORMIDADE = "nao_conforme"
ACAO_NAO_CONFORMIDADE = ("Recomenda-se ao proponente revisar a proposta, ou "
                         "demonstrar o atendimento, quanto a:")

# Títulos das checagens no texto, na ordem de `relatorios.CHECAGENS`.
TITULOS = {
    "enquadramento": "Enquadramento",
    "qualificacao": "Qualificação Urbanística",
    "georref": "Georreferenciamento do modelo",
    "programa": "Programa de necessidades",
    "bim_gis": "Requisitos de projeto (BIM + GIS)",
}

# --- Notas padrão dos casos inconclusivos (ADR-035) --------------------------
# Texto fixo, disparado por campo gravado, citado uma vez com os requisitos a
# que se aplica. Cada uma resume uma decisão já tomada: ADR-013 (linha reta),
# DN-04 (alternativa remetida), DN-08 (vocabulário de zona superado) e
# ADR-030 (zona derivada do município).
NOTA_LINHA_RETA = "linha_reta"
NOTA_REMETIDA = "remetida"
NOTA_ZONA_SUPERADA = "zona_superada"
NOTA_ZONA_NAO_RESOLVIDA = "zona_nao_resolvida"

NOTAS = {
    NOTA_LINHA_RETA: (
        "A distância em linha reta é sempre menor ou igual à distância "
        "caminhável: quando é ela a medida (sem o serviço de cálculo da distância "
        "caminhável, ou para equipamento fora do raio medido por ele), basta para reprovar, mas "
        "nunca para aprovar."),
    NOTA_REMETIDA: (
        "Quando a Portaria aceita mais de uma via e uma delas depende de "
        "documento que não é dado público (como o itinerário do transporte "
        "escolar), o protótipo não a descarta: o requisito fica em aberto, e "
        "a decisão cabe ao analista."),
    NOTA_ZONA_SUPERADA: (
        "A Portaria descreve parte das faixas pelo zoneamento bioclimático da "
        "NBR 15220-3:2005, que a norma vigente (ABNT TR 15220-3-1:2024) "
        "substituiu sem correspondência entre as numerações. O protótipo não "
        "traduz uma edição na outra: conclui quando o resultado é o mesmo sob "
        "qualquer leitura — absortância até 0,4 atende e acima de 0,6 não "
        "atende — e deixa ao analista a faixa entre 0,4 e 0,6."),
    NOTA_ZONA_NAO_RESOLVIDA: (
        "A zona bioclimática do município não pôde ser determinada pela base "
        "do protótipo; sem ela, não se sabe qual limite de absortância se "
        "aplica."),
}

NOTA_DE_NATUREZA = ("Síntese gerada automaticamente pelo protótipo a partir "
                    "das análises gravadas{datas}. Cada frase decorre de um "
                    "requisito verificado. Não substitui o parecer do analista.")

# Entidades IFC que o EMP-001 lista como lacuna, em linguagem de uso, com o
# termo técnico entre parênteses (ADR-034 (e)).
_LACUNA_LOGEOREF = {
    "IfcPostalAddress": "o endereço (IfcPostalAddress)",
    "IfcSite": "as coordenadas geográficas do terreno (IfcSite)",
    "IfcProjectedCRS": "o sistema de coordenadas projetado (IfcProjectedCRS)",
    "IfcMapConversion": ("a conversão das coordenadas do modelo para o mapa "
                         "(IfcMapConversion)"),
}

_ESTADO = {"conforme": "conforme", "nao_conforme": "não conforme",
           "nao_avaliavel": "não avaliável"}


# --- Estrutura devolvida -----------------------------------------------------

@dataclass(frozen=True)
class ItemPendencia:
    requisito: str
    descricao: str
    complemento: str = ""


@dataclass(frozen=True)
class GrupoPendencia:
    """Um motivo (ou a não conformidade) com a ação e os requisitos dele."""
    chave: str
    acao: str
    itens: tuple[ItemPendencia, ...]


@dataclass(frozen=True)
class LinhaRequisito:
    """Um requisito da Portaria verificado, para a tela mostrar em tabela o que
    o parágrafo conta em prosa (ADR-035). ``detalhe`` é o exigido × medido de
    quem concluiu, ou o que deixou em aberto, ou o motivo, de quem não pôde
    ser avaliado — os mesmos campos que o parágrafo usa."""
    requisito: str
    descricao: str
    estado: str
    detalhe: str = ""


@dataclass(frozen=True)
class BlocoChecagem:
    """O parágrafo de uma checagem repartido para a tela: ``introducao`` são os
    insumos e a frase que anuncia os requisitos verificados, e ``linhas`` são
    esses requisitos com o resultado. Sem requisito verificado, ``introducao``
    é o parágrafo inteiro e ``linhas`` fica vazio."""
    titulo: str
    introducao: str
    linhas: tuple[LinhaRequisito, ...] = ()


@dataclass(frozen=True)
class Parecer:
    abertura: str
    checagens: tuple[tuple[str, str], ...]          # (título, parágrafo)
    limites: tuple[str, ...]
    pendencias: dict[str, tuple[GrupoPendencia, ...]] = field(default_factory=dict)
    arquivos: tuple[str, ...] = ()
    nota: str = ""
    # O mesmo conteúdo de ``checagens``, repartido para a tela. ``texto()`` não
    # o usa: o texto do parecer continua o dos parágrafos.
    blocos: tuple[BlocoChecagem, ...] = ()

    @property
    def vazio(self) -> bool:
        return not self.checagens

    def texto(self) -> str:
        """O parecer inteiro em Markdown — o que a página desenha e o que se
        compara nos testes e com o autor."""
        partes = [self.abertura]
        for titulo, paragrafo in self.checagens:
            partes.append(f"**{titulo}.** {paragrafo}")
        if self.limites:
            partes.append("**Limites da análise.**")
            partes.extend(f"- {linha}" for linha in self.limites)
        if self.checagens:
            partes.append("**Pendências.**")
            if not any(self.pendencias.values()):
                partes.append("Nenhuma pendência decorre desta análise.")
            for dest, grupos in self.pendencias.items():
                if not grupos:
                    continue
                partes.append(f"*{TITULO_DESTINATARIO[dest]}.*")
                for g in grupos:
                    partes.append(g.acao)
                    partes.extend(f"- {linha_item(i)}" for i in g.itens)
        if self.arquivos:
            partes.append("**Arquivos analisados.**")
            partes.extend(f"- {linha}" for linha in self.arquivos)
        if self.nota:
            partes.append(f"*{self.nota}*")
        return "\n\n".join(partes)


def linha_item(item: ItemPendencia) -> str:
    texto = f"{item.requisito} — {item.descricao}"
    return f"{texto}: {item.complemento}" if item.complemento else texto


# --- Construtor --------------------------------------------------------------

def montar(relatorios: dict[str, dict], frase_empreendimento: str = "", *,
           dependencias: dict[str, list[str]] | None = None) -> Parecer:
    """O parecer dos relatórios recebidos (``{chave: relatório}``, as chaves de
    `relatorios.CHECAGENS`), na ordem das checagens.

    ``frase_empreendimento`` é a frase do card (ADR-034 (d)), montada pela
    página. ``dependencias`` (``{id: [pré-requisitos]}``) vem do registro das
    regras quando omitido — é o ``depende_de`` que a própria regra declara.
    """
    executadas = [c for c in rel.CHECAGENS if c in relatorios]
    if not executadas:
        abertura = _juntar(frase_empreendimento,
                           "Nenhuma checagem foi executada para este "
                           "empreendimento; não há o que relatar.")
        return Parecer(abertura=abertura, checagens=(), limites=())

    if dependencias is None:
        dependencias = _dependencias_registradas()

    ordem = {c: relatorios[c] for c in executadas}
    checagens = tuple((TITULOS.get(c, c), _paragrafo(c, r)) for c, r in ordem.items())
    pendencias = _pendencias(ordem, dependencias)
    limites = tuple(_limites(ordem, executadas))
    blocos = tuple(_bloco(c, r) for c, r in ordem.items())
    return Parecer(abertura=_abertura(ordem, frase_empreendimento),
                   checagens=checagens, limites=limites,
                   pendencias=pendencias, arquivos=tuple(_arquivos(ordem)),
                   nota=_nota(ordem), blocos=blocos)


# --- 1 · Abertura ------------------------------------------------------------

def _abertura(relatorios: dict[str, dict], frase: str) -> str:
    c = rel.consolidar(relatorios)
    k = len(relatorios)
    n = len(rel.CHECAGENS)
    execucao = (f"Foram executadas as {_extenso(n, 'f')} checagens do protótipo"
                if k == n else
                f"{'Foi executada' if k == 1 else 'Foram executadas'} "
                f"{_extenso(k, 'f')} das {_extenso(n, 'f')} checagens do protótipo")
    contagens = [_contagem(c["conforme"], "conforme", "conformes"),
                 _contagem(c["nao_conforme"], "não conforme", "não conformes"),
                 _contagem(c["nao_avaliavel"], "não avaliável", "não avaliáveis")]
    frase_contagem = (
        f"{execucao}, que somam {_plural(c['total'], 'requisito', 'requisitos')} "
        f"da Portaria MCID nº 725/2023: {_enumerar(contagens)}.")
    versoes = sorted({(r.get("meta") or {}).get("empreendimento", {}).get("versao")
                      for r in relatorios.values()} - {None})
    texto_versao = ""
    if len(versoes) == 1:
        texto_versao = (f"As declarações consideradas são as da versão "
                        f"{versoes[0]} das Informações Gerais.")
    return _juntar(frase, frase_contagem, texto_versao)


# --- Insumos de cada checagem (ADR-035) ---------------------------------------
# A 1.ª frase de cada parágrafo amarra o resultado ao que a análise consumiu:
# o arquivo, o terreno, as bases e a data — tudo lido do ``meta`` e do
# ``detalhe`` que o pipeline gravou, nunca do estado corrente da sessão.

_ROTULO_ORIGEM_TERRENO = {
    "csv": "importação de arquivo CSV com os vértices da poligonal",
    "ifc": "leitura do terreno de um modelo IFC (IfcSite)",
    "desenhada": "poligonal desenhada no mapa",
    "ponto": "indicação do centro do terreno, sem poligonal",
}
_NATUREZA = {
    "edificacao_isolada": "edificação isolada",
    "terreno": "modelo só do terreno",
    "terreno_com_edificacoes": "terreno com edificações",
}


def _insumos(chave: str, relatorio: dict) -> str:
    meta = relatorio.get("meta") or {}
    linhas = relatorio.get("por_requisito") or []
    quando = _data(relatorio.get("gerado_em"))
    partes: list[str] = []
    if chave == "enquadramento":
        partes.append(_insumo_terreno(meta.get("terreno")))
        partes.append(_insumo_equipamentos(linhas))
        partes.append(_insumo_rede(meta, linhas))
    elif chave == "qualificacao":
        partes.append(_insumo_porte(linhas))
    else:
        partes.append(_insumo_modelo(chave, meta, linhas))
        if chave == "georref":
            partes.append(_insumo_municipio(linhas))
        if chave == "bim_gis":
            partes.append(_insumo_zona(linhas))
    partes = [p for p in partes if p]
    if not partes:
        return ""
    texto = "Para a análise, " + "; ".join(partes) + "."
    return texto + (f" Análise gravada em {quando}." if quando else "")


def _insumo_terreno(terreno: dict | None) -> str:
    if not terreno:
        return "não havia terreno definido"
    proc = terreno.get("procedencia") or {}
    origem = _ROTULO_ORIGEM_TERRENO.get(terreno.get("origem"), terreno.get("origem", ""))
    texto = f"foi avaliado o terreno indicado por {origem}"
    detalhes = []
    arquivo = _nome_arquivo(proc.get("arquivo"))
    if arquivo:
        detalhes.append(arquivo)
    vertices = proc.get("vertices") or []
    if vertices:
        detalhes.append(f"vértices {vertices[0]} a {vertices[-1]}"
                        if len(vertices) > 1 else f"vértice {vertices[0]}")
    if proc.get("epsg_origem"):
        fonte = (" informado pelo usuário"
                 if proc.get("epsg_origem_fonte") == "informado_pelo_usuario" else "")
        detalhes.append(f"{proc['epsg_origem']}{fonte}")
    if detalhes:
        texto += f" ({', '.join(detalhes)})"
    if terreno.get("nivel") == "poligonal" and terreno.get("area_m2"):
        texto += (f", com área de {_num(terreno['area_m2'], 2)} m², precisão "
                  f"{terreno.get('precisao', '')}, e as distâncias medidas a "
                  "partir do centro da poligonal")
    elif terreno.get("nivel") == "ponto":
        texto += ", e as distâncias medidas a partir desse ponto"
    return texto


def _insumo_equipamentos(linhas: list[dict]) -> str:
    for linha in linhas:
        proc = (linha.get("detalhe") or {}).get("procedencia_recorte") or {}
        if proc.get("ano_censo"):
            lugar = "/".join(x for x in (proc.get("nome_municipio"), proc.get("uf")) if x)
            gerado = _data(proc.get("gerado_em"))
            return (f"as escolas vieram do Censo Escolar {proc['ano_censo']} "
                    f"(INEP), no recorte de {lugar}"
                    + (f" gerado em {gerado}" if gerado else ""))
    return ""


def _insumo_rede(meta: dict, linhas: list[dict]) -> str:
    for linha in linhas:
        rede = (linha.get("detalhe") or {}).get("roteamento_de_rede") or {}
        malha = rede.get("procedencia_malha") or {}
        if rede.get("provedor"):
            texto = (f"as distâncias foram medidas pelo serviço de cálculo da "
                     f"distância caminhável "
                     f"({rede['provedor'].upper()}")
            osm = _data(malha.get("osm_date"))
            return texto + (f", malha OpenStreetMap de {osm})" if osm else ")")
    if any((l.get("detalhe") or {}).get("tipo") == "distancia_equipamento" for l in linhas):
        return ("sem o serviço de cálculo da distância caminhável, as distâncias "
                "foram medidas em linha reta")
    return ""


def _insumo_municipio(linhas: list[dict]) -> str:
    for linha in linhas:
        loc = (linha.get("detalhe") or {}).get("localizacao_declarada") or {}
        if loc.get("avaliado") and loc.get("municipio"):
            return (f"a posição gravada no modelo foi confrontada com os limites "
                    f"de {loc['municipio']}/{loc.get('uf', '')} pela malha "
                    "municipal do IBGE")
    return ""


def _insumo_porte(linhas: list[dict]) -> str:
    for linha in linhas:
        d = linha.get("detalhe") or {}
        if d.get("tipo") == "porte_empreendimento":
            texto = (f"foram usados o número de UHs previstas declarado em "
                     f"Informações Gerais ({_mil(d.get('unidades_previstas') or 0)})")
            if d.get("fonte_populacao"):
                texto += f" e a população do município ({d['fonte_populacao']})"
            return texto
    return ""


def _insumo_modelo(chave: str, meta: dict, linhas: list[dict]) -> str:
    nome = _nome_arquivo(meta.get("ifc"))
    if not nome:
        return "nenhum modelo IFC foi submetido"
    extras = []
    for linha in linhas:
        d = linha.get("detalhe") or {}
        if d.get("schema"):
            extras.append(d["schema"])
            break
    natureza = _NATUREZA.get(meta.get("tipo_modelo") or "")
    if natureza:
        extras.append(f"declarado como {natureza}")
    uhs = _unidades_representadas(meta, linhas)
    if uhs:
        extras.append(f"com {_plural(uhs, 'UH representada', 'UHs representadas')}")
    texto = f"foi utilizado o modelo de informações submetido, {nome}"
    if extras:
        texto += f" ({', '.join(extras)})"
    if chave == "programa":
        total = next(((l.get("detalhe") or {}).get("total_ambientes") for l in linhas
                      if (l.get("detalhe") or {}).get("total_ambientes") is not None), None)
        if total is not None:
            texto += (f", do qual se leram {_plural(total, 'ambiente', 'ambientes')} "
                      "(IfcSpace), identificados pelo nome")
    if chave == "bim_gis":
        total = next((((l.get("detalhe") or {}).get("populacao") or {}).get("total_coverings")
                      for l in linhas
                      if ((l.get("detalhe") or {}).get("populacao") or {}).get("total_coverings")
                      is not None), None)
        if total is not None:
            texto += (f", do qual se leram {_plural(total, 'revestimento', 'revestimentos')} "
                      "(IfcCovering)")
    return texto


def _unidades_representadas(meta: dict, linhas: list[dict]) -> int | None:
    for diag in meta.get("diagnosticos") or []:
        valor = (diag.get("valores") or {}).get("unidades_representadas")
        if valor:
            return int(valor)
    for linha in linhas:
        valor = (linha.get("detalhe") or {}).get("num_uhs")
        if valor:
            return int(valor)
    return None


def _insumo_zona(linhas: list[dict]) -> str:
    for linha in linhas:
        zona = (linha.get("detalhe") or {}).get("zona_resolvida") or {}
        if zona.get("classe"):
            fonte = zona.get("fonte", "").replace("_", " ")
            fonte = re.sub(r"(\d{4}) (\d)", r"\1-\2", fonte)  # TR 15220-3-1
            fonte = re.sub(r" (\d{4})$", r":\1", fonte)
            return (f"a zona bioclimática do município ({zona['classe']}) veio "
                    f"da {fonte}" if fonte else
                    f"a zona bioclimática do município é {zona['classe']}")
    return ""


def _nome_arquivo(caminho) -> str:
    """Só o nome do arquivo (ADR-034: a tela não mostra caminho)."""
    return re.split(r"[\\/]", (caminho or "").strip())[-1]


# --- 2 · Um parágrafo por checagem --------------------------------------------

def _paragrafo(chave: str, relatorio: dict) -> str:
    grupos = rel.agrupar(relatorio)
    insumos = _insumos(chave, relatorio)
    if not grupos:
        return _juntar(insumos, "Nenhum requisito foi verificado.")
    verificados = [f"{g['requisito'].get('requisito', '')}, "
                   f"{_minuscula(g['requisito'].get('descricao', ''))}"
                   for g in grupos]
    verbo = ("Verificou-se um requisito" if len(grupos) == 1 else
             f"Verificaram-se {_extenso(len(grupos), 'm')} requisitos")
    frases = [insumos] if insumos else []
    frases.append(f"{verbo}: {'; '.join(verificados)}.")

    nao_avaliaveis: dict[str, list[str]] = {}
    for g in grupos:
        r, membros = g["requisito"], g["membros"]
        estado = r.get("estado")
        rid = r.get("requisito", "")
        if estado in ("conforme", "nao_conforme"):
            medido = _medido(r, membros, relatorio)
            frase = f"{rid}: {_ESTADO[estado]}"
            frases.append(f"{frase} — {medido}." if medido else f"{frase}.")
        else:
            aberto = _em_aberto(r, membros)
            if aberto:
                frases.append(f"{rid}: não avaliável — {aberto}.")
            else:
                motivo = _motivo(r)
                nao_avaliaveis.setdefault(motivo, []).append(rid)

    for motivo, ids in nao_avaliaveis.items():
        rotulo = _minuscula(motivos.rotulo(motivo)) if motivo else "motivo não declarado"
        verbo = "Não pôde ser avaliado" if len(ids) == 1 else "Não puderam ser avaliados"
        frases.append(f"{verbo} ({rotulo}): {_enumerar(ids)}.")
    return " ".join(frases)


def _bloco(chave: str, relatorio: dict) -> BlocoChecagem:
    """O parágrafo de `_paragrafo` repartido em introdução e linhas por
    requisito, com os mesmos auxiliares, para a tela montar a tabela."""
    titulo = TITULOS.get(chave, chave)
    grupos = rel.agrupar(relatorio)
    if not grupos:
        return BlocoChecagem(titulo, _paragrafo(chave, relatorio))
    verbo = ("Verificou-se um requisito" if len(grupos) == 1 else
             f"Verificaram-se {_extenso(len(grupos), 'm')} requisitos")
    introducao = " ".join(f for f in (_insumos(chave, relatorio), f"{verbo}:") if f)
    linhas = []
    for g in grupos:
        r, membros = g["requisito"], g["membros"]
        estado = r.get("estado")
        if estado in ("conforme", "nao_conforme"):
            detalhe = _medido(r, membros, relatorio)
        else:
            motivo = _motivo(r)
            detalhe = (_em_aberto(r, membros)
                       or (_minuscula(motivos.rotulo(motivo)) if motivo
                           else "motivo não declarado"))
        linhas.append(LinhaRequisito(r.get("requisito", ""), r.get("descricao", ""),
                                     estado, detalhe[:1].upper() + detalhe[1:]))
    return BlocoChecagem(titulo, introducao, tuple(linhas))


def _em_aberto(r: dict, membros: list[dict]) -> str:
    """Por que um requisito de alternativas/ramos ficou em aberto, em prosa.
    ``""`` quando não é agregação (o motivo agrupado já diz)."""
    d = r.get("detalhe") or {}
    if d.get("tipo") != "agregacao" or not membros:
        return ""
    if d.get("modo") == "selecao_exclusiva":
        return _minuscula(motivos.rotulo(_motivo(r)))
    partes = []
    for m in membros:
        mid = m.get("requisito", "")
        if m.get("estado") in ("conforme", "nao_conforme"):
            medido = _medido(m, [], {})
            partes.append(f"{mid} {_ESTADO[m['estado']]}"
                          + (f" ({medido})" if medido else ""))
        else:
            partes.append(f"{mid} em aberto "
                          f"({_minuscula(motivos.rotulo(_motivo(m)))})")
    via = ("basta uma das vias" if d.get("modo") == "qualquer"
           else "são exigidas todas as vias")
    return f"{via}; {'; '.join(partes)}"


def _medido(r: dict, membros: list[dict], relatorio: dict) -> str:
    """O exigido × medido de um requisito concluído, dos campos que a regra
    gravou — modelo de frase por ``detalhe["tipo"]``; sem modelo, a 1.ª frase
    da mensagem."""
    d = r.get("detalhe") or {}
    tipo = d.get("tipo")
    if tipo == "distancia_equipamento":
        return _medido_distancia(d) or _primeira_frase(r)
    if tipo == "logeoref":
        return _medido_logeoref(d)
    if tipo == "porte_empreendimento":
        return _medido_porte(d, relatorio)
    if tipo == "absortancia":
        return _medido_absortancia(d)
    if tipo == "ambientes":
        return _medido_ambientes(d)
    if tipo == "larguras":
        return _medido_larguras(d)
    if tipo == "agregacao":
        return _medido_agregacao(r, membros, relatorio)
    return _primeira_frase(r)


def _medido_distancia(d: dict) -> str:
    det = d.get("determinante") or {}
    metros, limiar = det.get("metros"), d.get("limiar_m")
    if metros is None or not limiar:
        return ""
    metrica = {"linha_reta": "em linha reta",
               "rede_pedestre": "pela rede de pedestres"}.get(det.get("metrica"), "")
    destino = f" até {det['rotulo']}" if det.get("rotulo") else ""
    return (f"menor distância obtida de {_mil(metros)} m{destino}"
            f"{' ' + metrica if metrica else ''}, para o máximo de {_mil(limiar)} m")


def _medido_logeoref(d: dict) -> str:
    texto = (f"nível {d.get('nivel')} da escala LoGeoRef, para o nível "
             f"{d.get('alvo')} exigido")
    lacunas = [_LACUNA_LOGEOREF.get(x, x) for x in d.get("lacunas") or []]
    if lacunas:
        texto += f"; faltam no modelo {_enumerar(lacunas)}"
    loc = d.get("localizacao_declarada") or {}
    if loc.get("avaliado") and loc.get("municipio"):
        lugar = f"{loc['municipio']}/{loc.get('uf', '')}".rstrip("/")
        texto += ("; as coordenadas gravadas situam o modelo em " + lugar
                  if loc.get("dentro") else
                  "; as coordenadas gravadas situam o modelo fora de " + lugar)
    return texto


def _medido_porte(d: dict, relatorio: dict) -> str:
    previstas, limite = d.get("unidades_previstas"), d.get("limite")
    if previstas is None or limite is None:
        return ""
    dec = (relatorio.get("meta") or {}).get("declaracoes") or {}
    municipio = dec.get("municipio") or "o município"
    pop = d.get("populacao")
    texto = f"{_mil(previstas)} UHs previstas"
    if pop:
        texto += (f"; {municipio} tem {_mil(pop)} habitantes (Censo 2022), "
                  f"na faixa {d.get('faixa', '')}")
    texto += f", com limite de {_mil(limite)} UHs por empreendimento"
    if previstas > limite:
        texto += f" (excede em {_mil(previstas - limite)})"
    return texto


def _medido_absortancia(d: dict) -> str:
    cov = d.get("coverings") or []
    familia = _familia_absortancia(d)
    limite = d.get("limite")
    medidos = [c["absortancia"] for c in cov
               if c.get("situacao") in ("atende", "nao_atende")
               and c.get("absortancia") is not None]
    if medidos:
        acima = sum(1 for c in cov if c.get("situacao") == "nao_atende")
        texto = (f"{_plural(len(medidos), 'revestimento', 'revestimentos')} de "
                 f"{familia}, maior absortância {_dec(max(medidos))}, para o "
                 f"limite de {_dec(limite)}")
        if acima:
            texto += f" ({acima} acima do limite)"
        return texto
    return _falta_absortancia(d)


def _falta_absortancia(d: dict) -> str:
    """O que falta no modelo para a absortância, contado por situação."""
    cov = d.get("coverings") or []
    familia = _familia_absortancia(d)
    sem_material = sum(1 for c in cov if c.get("situacao") == "material_nao_identificavel")
    sem_alfa = sum(1 for c in cov if c.get("situacao") == "sem_absortancia")
    partes = []
    if sem_material:
        partes.append(f"{_plural(sem_material, 'revestimento', 'revestimentos')} "
                      f"de {familia} sem material identificável")
    if sem_alfa:
        partes.append(f"{_plural(sem_alfa, 'revestimento', 'revestimentos')} "
                      f"de {familia} sem a absortância informada")
    if partes:
        return _enumerar(partes)
    return (f"nenhum revestimento de {familia} classificado no modelo "
            "(IfcCovering)")


def _familia_absortancia(d: dict) -> str:
    criterio = ((d.get("populacao") or {}).get("criterio") or "").lower()
    return "cobertura" if "cobertura" in criterio else "parede externa"


def _medido_ambientes(d: dict) -> str:
    """Contagem por categoria do programa contra o mínimo normalizado pelas
    UHs do modelo; na não conformidade, só as categorias que faltam."""
    categorias = d.get("categorias") or []
    faltando = [c for c in categorias if c.get("atende") is False]
    alvo = faltando or categorias
    partes = [f"{_minuscula(c.get('rotulo', ''))} ({_mil(c.get('qtd', 0))}, "
              f"para o mínimo de {_mil(c.get('min', 0))})" for c in alvo]
    if not partes:
        return ""
    return ("abaixo do mínimo: " if faltando else "") + _enumerar(partes)


def _medido_larguras(d: dict) -> str:
    amb = [a for a in d.get("ambientes") or [] if a.get("largura_m") is not None]
    minimo = d.get("largura_min_m")
    if not amb or minimo is None:
        return ""
    rotulo = _minuscula(d.get("categoria_rotulo") or "ambiente")
    menor = min(a["largura_m"] for a in amb)
    abaixo = sum(1 for a in amb if a.get("atende") is False)
    texto = (f"{_plural(len(amb), rotulo, rotulo + 's')}, menor largura "
             f"{_dec(menor, 2)} m, para o mínimo de {_dec(minimo, 2)} m")
    if d.get("area_min_m2") is not None:
        texto += f" e área mínima de {_dec(d['area_min_m2'], 2)} m²"
    if abaixo:
        texto += f" ({abaixo} abaixo do mínimo)"
    return texto


def _medido_agregacao(r: dict, membros: list[dict], relatorio: dict) -> str:
    """Requisito de alternativas ou ramos concluído: quem decidiu e o medido
    dele. Na seleção exclusiva é o ramo aplicável (ou os candidatos
    unânimes); nas vias, o membro que decidiu."""
    d = r.get("detalhe") or {}
    estado = r.get("estado")
    if d.get("modo") == "selecao_exclusiva":
        candidatos = set(d.get("candidatos") or [])
        decisivos = [m for m in membros if m.get("requisito") in candidatos]
    else:
        decisivos = [m for m in membros if m.get("estado") == estado]
    if not decisivos:
        return _primeira_frase(r)
    m = decisivos[0]
    medido = _medido(m, [], relatorio)
    zona = ((m.get("detalhe") or {}).get("zona_resolvida") or {}).get("classe")
    membro = (d.get("rotulo_membro") or "item").replace("(s)", "")
    artigo = "pela" if membro.endswith("a") else "pelo"
    prefixo = f"{artigo} {membro} {m.get('requisito')}"
    if d.get("modo") == "selecao_exclusiva" and zona:
        prefixo = f"na zona bioclimática {zona}, {prefixo}"
    return f"{prefixo}: {medido}" if medido else prefixo


def _primeira_frase(r: dict) -> str:
    msg = (r.get("mensagem") or "").strip()
    if not msg:
        return ""
    primeira = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ(])", msg, maxsplit=1)[0]
    return _minuscula(primeira.rstrip("."))


# --- 3 · Limites da análise ---------------------------------------------------

def _limites(relatorios: dict[str, dict], executadas: list[str]) -> list[str]:
    linhas: list[str] = []
    vistos: set[str] = set()
    for r in relatorios.values():
        for diag in (r.get("meta") or {}).get("diagnosticos") or []:
            msg = (diag.get("mensagem") or "").strip()
            if diag.get("marcado") and msg and msg not in vistos:
                vistos.add(msg)
                linhas.append(msg)

    fora = _ambientes_fora(relatorios)
    if fora:
        linhas.append(f"{_plural(fora, 'ambiente do modelo foi deixado', 'ambientes do modelo foram deixados')} "
                      "de fora da análise do programa por parecer(em) erro de "
                      "exportação; a lista está no relatório do programa.")

    for chave, ids in _notas(relatorios).items():
        linhas.append(f"{_enumerar(ids)}: {NOTAS[chave]}")

    faltantes = [TITULOS[c] for c in rel.CHECAGENS if c not in executadas]
    if faltantes:
        linhas.append(f"Não {'foi executada' if len(faltantes) == 1 else 'foram executadas'}: "
                      f"{_enumerar(faltantes)}; os requisitos dessas checagens "
                      "não entram nesta síntese.")
    total = rel.consolidar(relatorios)["total"]
    linhas.append(f"Esta síntese cobre os {_plural(total, 'requisito', 'requisitos')} "
                  "da Portaria verificados pelo protótipo, não a Portaria inteira.")
    return linhas


def _ambientes_fora(relatorios: dict[str, dict]) -> int:
    """Ambientes fantasma (ADR-031) — gravados em cada regra do programa;
    conta-se uma vez, do primeiro requisito que os traz."""
    for r in relatorios.values():
        for linha in r.get("por_requisito") or []:
            fora = (linha.get("detalhe") or {}).get("fora_da_populacao")
            if fora:
                return len(fora)
    return 0


def _notas(relatorios: dict[str, dict]) -> dict[str, list[str]]:
    """Quais notas padrão se aplicam e a que requisitos, pelos campos gravados.

    Só entram requisitos que o texto relata como inconclusivos ou decididos
    por métrica limitada: a nota explica um resultado, não a regra em geral.
    """
    notas: dict[str, list[str]] = {}

    def anotar(chave: str, rid: str) -> None:
        ids = notas.setdefault(chave, [])
        if rid not in ids:
            ids.append(rid)

    for r in relatorios.values():
        for g in rel.agrupar(r):
            pai, membros = g["requisito"], g["membros"]
            pid = pai.get("requisito", "")
            for linha in [pai, *membros]:
                d = linha.get("detalhe") or {}
                det = d.get("determinante") or {}
                if (d.get("tipo") == "distancia_equipamento"
                        and det.get("metrica") == "linha_reta"
                        and linha.get("estado") != "conforme"):
                    anotar(NOTA_LINHA_RETA, pid)
            if pai.get("estado") != "nao_avaliavel":
                continue
            for m in membros:
                d = m.get("detalhe") or {}
                if d.get("tipo") == "remetida":
                    anotar(NOTA_REMETIDA, pid)
                if d.get("aplicabilidade_do_ramo") == "indeterminada":
                    zona = (d.get("zona_resolvida") or {}).get("classe")
                    anotar(NOTA_ZONA_SUPERADA if zona else NOTA_ZONA_NAO_RESOLVIDA, pid)
    return notas


# --- 4 · Pendências por destinatário ------------------------------------------

def _pendencias(relatorios: dict[str, dict],
                dependencias: dict[str, list[str]]) -> dict[str, tuple[GrupoPendencia, ...]]:
    """Só o que decide um requisito da Portaria gera pendência (ADR-035):
    requisito decidido não gera, nem as vias dele."""
    por_chave: dict[str, list[ItemPendencia]] = {}
    ordem: list[str] = []
    esperando: list[tuple[dict, list[str]]] = []

    def incluir(chave: str, item: ItemPendencia) -> None:
        if chave not in por_chave:
            por_chave[chave] = []
            ordem.append(chave)
        if item not in por_chave[chave]:
            por_chave[chave].append(item)

    for r in relatorios.values():
        for g in rel.agrupar(r):
            pai, membros = g["requisito"], g["membros"]
            estado = pai.get("estado")
            if estado == "conforme":
                continue
            if estado == "nao_conforme":
                incluir(NAO_CONFORMIDADE, _item(pai, _medido(pai, membros, r)))
                continue
            d = pai.get("detalhe") or {}
            vias = (d.get("tipo") == "agregacao" and membros
                    and d.get("modo") != "selecao_exclusiva")
            abertos = ([m for m in membros if m.get("estado") == "nao_avaliavel"]
                       if vias else [pai])
            for linha in abertos:
                motivo = _motivo(linha)
                if motivo == motivos.PREREQUISITO_FALHO:
                    esperando.append((linha, dependencias.get(linha.get("requisito"), [])))
                    continue
                if DESTINATARIO.get(motivo) is None:
                    continue
                incluir(motivo, _item(linha, _complemento(linha, membros, r)))

    _anexar_dependentes(por_chave, esperando)

    grupos: dict[str, list[GrupoPendencia]] = {d: [] for d in TITULO_DESTINATARIO}
    for chave in ordem:
        if chave == NAO_CONFORMIDADE:
            dest, acao = PROPONENTE, ACAO_NAO_CONFORMIDADE
        else:
            dest, acao = DESTINATARIO[chave], acao_de(chave)
        grupos[dest].append(GrupoPendencia(chave, acao, tuple(por_chave[chave])))
    # Não conformidade primeiro no bloco do proponente: é o que decide.
    grupos[PROPONENTE].sort(key=lambda g: g.chave != NAO_CONFORMIDADE)
    return {d: tuple(g) for d, g in grupos.items()}


def acao_de(motivo: str) -> str:
    """A ação de um motivo — a mesma da tela (`motivos.ACAO`, fonte única)."""
    return motivos.ACAO.get(motivo, "")


def _item(linha: dict, complemento: str) -> ItemPendencia:
    return ItemPendencia(linha.get("requisito", ""),
                         _minuscula(linha.get("descricao", "")), complemento)


def _complemento(linha: dict, membros: list[dict], relatorio: dict) -> str:
    """O que falta, por tipo: o insumo da via remetida, o que falta de
    absortância, ou a 1.ª frase da mensagem."""
    d = linha.get("detalhe") or {}
    if d.get("tipo") == "remetida":
        return d.get("insumo", "")
    if d.get("tipo") == "agregacao" and d.get("modo") == "selecao_exclusiva":
        candidatos = set(d.get("candidatos") or [])
        for m in membros:
            if m.get("requisito") in candidatos and m.get("estado") == "nao_avaliavel":
                return _complemento(m, [], relatorio)
        return ""
    if d.get("tipo") == "absortancia":
        return _falta_absortancia(d)
    if d.get("tipo") == "distancia_equipamento":
        return _medido_distancia(d)
    return _primeira_frase(linha)


def _anexar_dependentes(por_chave: dict[str, list[ItemPendencia]],
                        esperando: list[tuple[dict, list[str]]]) -> None:
    """``prerequisito_falho`` não é pendência própria: o requisito que espera
    entra como observação no item do **primeiro** pré-requisito pendente, na
    ordem declarada pela regra (``depende_de``) — uma vez só."""
    posicao = {item.requisito: (chave, i) for chave, itens in por_chave.items()
               for i, item in enumerate(itens)}
    for linha, pres in esperando:
        alvo = next((posicao[p] for p in pres if p in posicao), None)
        if alvo is None:
            continue
        chave, i = alvo
        item = por_chave[chave][i]
        obs = f"o {linha.get('requisito')} depende deste requisito"
        complemento = f"{item.complemento}; {obs}" if item.complemento else obs
        por_chave[chave][i] = ItemPendencia(item.requisito, item.descricao, complemento)


def _dependencias_registradas() -> dict[str, list[str]]:
    from app.servicos.grupos import regras_registradas
    return {rid: list(getattr(cls, "depende_de", []) or [])
            for rid, cls in regras_registradas().items()}


# --- 6 · Arquivos analisados ---------------------------------------------------

def _arquivos(relatorios: dict[str, dict]) -> list[str]:
    """``arquivo — SHA-256 …`` de cada arquivo submetido que as análises
    consumiram, sem repetir. O texto cita só o nome; a impressão digital fica
    aqui, no fim, para não quebrar a leitura (ADR-035). Relatório anterior ao
    registro (sem ``meta.arquivos``) cai no nome gravado, sem impressão."""
    vistos: dict[tuple[str, str], None] = {}
    for r in relatorios.values():
        meta = r.get("meta") or {}
        arquivos = meta.get("arquivos")
        if arquivos is None:
            arquivos = [{"arquivo": _nome_arquivo(meta.get("ifc")), "sha256": ""},
                        {"arquivo": _nome_arquivo(((meta.get("terreno") or {})
                                                   .get("procedencia") or {}).get("arquivo")),
                         "sha256": ""}]
        for a in arquivos:
            nome = a.get("arquivo") or ""
            if nome:
                vistos.setdefault((nome, a.get("sha256") or ""), None)
    linhas = []
    for nome, sha in vistos:
        linhas.append(f"{nome} — SHA-256 {sha}" if sha else
                      f"{nome} — impressão digital não registrada nesta análise")
    return linhas


# --- 5 · Nota de natureza -----------------------------------------------------

def _nota(relatorios: dict[str, dict]) -> str:
    datas = sorted({_data(r.get("gerado_em")) for r in relatorios.values()} - {""})
    texto_datas = ""
    if len(datas) == 1:
        texto_datas = f" em {datas[0]}"
    elif datas:
        texto_datas = f" entre {datas[0]} e {datas[-1]}"
    return NOTA_DE_NATUREZA.format(datas=texto_datas)


def _data(iso: str | None) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else ""


# --- Utilidades de texto ------------------------------------------------------

def _motivo(linha: dict) -> str:
    return (linha.get("detalhe") or {}).get(motivos.CHAVE, "") or ""


_EXTENSO = {1: ("um", "uma"), 2: ("dois", "duas"), 3: ("três", "três"),
            4: ("quatro", "quatro"), 5: ("cinco", "cinco")}


def _extenso(n: int, genero: str) -> str:
    """Número pequeno por extenso (até cinco); acima disso, algarismos."""
    par = _EXTENSO.get(n)
    return (par[1] if genero == "f" else par[0]) if par else _mil(n)


def _contagem(n: int, singular: str, plural: str) -> str:
    return f"nenhum {singular}" if n == 0 else _plural(n, singular, plural)


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{_mil(n)} {singular if n == 1 else plural}"


def _enumerar(itens: list[str]) -> str:
    itens = [i for i in itens if i]
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def _juntar(*frases: str) -> str:
    return " ".join(f for f in frases if f)


def _minuscula(texto: str) -> str:
    """Primeira letra em minúscula, a não ser que a palavra seja sigla."""
    if len(texto) > 1 and texto[0].isupper() and not texto[1].isupper():
        return texto[0].lower() + texto[1:]
    return texto


def _mil(valor) -> str:
    return f"{float(valor):,.0f}".replace(",", ".")


def _num(valor, casas: int) -> str:
    """Número com milhar e decimal no padrão brasileiro (95.906,03)."""
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def _dec(valor, casas: int = 2) -> str:
    if valor is None:
        return ""
    return f"{float(valor):.{casas}f}".replace(".", ",")


__all__ = ["DESTINATARIO", "NOTAS", "Parecer", "montar"]
