"""Vocabulário das exceções de absortância da cobertura (DN-01).

A Portaria MCID 725, Anexo III, Tab. 1, item 4.III.i, excetua do limite de
absortância do telhado as "coberturas em telhas de barro não vitrificada e
cobertura verde". Este módulo faz a **correspondência nominal** entre o nome do
material do ``IfcCovering`` e essas duas exceções — mesmo espírito do
``catalogo_ambientes``: regex sobre o nome normalizado, com o termo que casou
devolvido para o relatório dizer por que reconheceu a exceção.

O que conta como cada exceção, e o que torna um material "não identificável",
é **leitura normativa**, não decisão de sistema: está na entrada **DN-01** de
``docs/arquitetura/DECISOES_NORMATIVAS.md``. Aqui só o vocabulário que a
materializa. Anel de domínio: sem I/O, sem IFC — recebe nomes, devolve chaves.

Regra de conclusão que este vocabulário serve (e que a regra aplica):
exceção identificada → o limite NÃO se aplica ao covering; material sem nome →
NÃO IDENTIFICÁVEL, e a regra sai não avaliável; nome que não casa com exceção
nenhuma → material comum, comparado ao limite. **Nunca** conforme por omissão.
"""

from __future__ import annotations

import re
import unicodedata

TELHA_BARRO_NAO_VITRIFICADA = "telha_barro_nao_vitrificada"
COBERTURA_VERDE = "cobertura_verde"

ROTULO = {
    TELHA_BARRO_NAO_VITRIFICADA: "telha de barro não vitrificada",
    COBERTURA_VERDE: "cobertura verde",
}

# Padrões sobre o nome NORMALIZADO (minúsculas, sem acento, pontuação → espaço).
# Telha de barro: o MATERIAL cerâmico, em qualquer grafia usual. Perfil de
# telha (colonial, portuguesa, romana) não entra: existe "romana" de concreto,
# e o perfil não diz de que a telha é feita.
_BARRO = [r"\bbarro\b", r"ceramic", r"\bargila\b", r"terracota", r"terra cota"]
# O que a torna VITRIFICADA — e portanto fora da exceção (a Portaria só excetua
# a não vitrificada; a esmaltada é, inclusive, tratada à parte no item 4.III.h).
_VITRIFICADA = [r"vitrific", r"esmalt", r"vidrad", r"\bglazed\b"]
# Cobertura verde: o sistema vegetado, não a COR verde de uma pintura — por isso
# "verde" sozinho não casa (uma "tinta verde" seria falsa exceção).
_VERDE = [r"cobertura verde", r"telhado verde", r"teto verde", r"laje verde",
          r"\bgreen roof\b", r"vegetad", r"\bvegetal\b", r"\bsubstrato\b",
          r"\bgrama\b"]

_C_BARRO = [re.compile(p) for p in _BARRO]
_C_VITRIFICADA = [re.compile(p) for p in _VITRIFICADA]
_C_VERDE = [re.compile(p) for p in _VERDE]


def normalizar(nome: str | None) -> str:
    """Minúsculas, sem acentos, pontuação/hífens vira espaço, espaços colapsados."""
    if not nome:
        return ""
    s = unicodedata.normalize("NFKD", str(nome))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def classificar(nome: str | None) -> tuple[str | None, str | None]:
    """``(excecao, termo_casado)`` para UM nome de material; ``(None, None)``
    quando o nome não descreve nenhuma das duas exceções.

    Telha de barro só é exceção se NÃO for vitrificada: um termo de
    vitrificação no nome retira a exceção, ainda que "cerâmica" também conste.
    """
    alvo = normalizar(nome)
    if not alvo:
        return None, None
    for padrao in _C_VERDE:
        m = padrao.search(alvo)
        if m:
            return COBERTURA_VERDE, m.group(0).strip()
    if any(p.search(alvo) for p in _C_VITRIFICADA):
        return None, None
    for padrao in _C_BARRO:
        m = padrao.search(alvo)
        if m:
            return TELHA_BARRO_NAO_VITRIFICADA, m.group(0).strip()
    return None, None


def classificar_materiais(nomes: list[str]) -> tuple[str | None, str | None, str | None]:
    """``(excecao, nome_do_material, termo_casado)`` para a lista de materiais
    de um covering: a primeira exceção reconhecida vence. Lista vazia ou só de
    nomes vazios é o caso NÃO IDENTIFICÁVEL — devolve ``(None, None, None)`` e
    quem chama distingue pelo próprio ``nomes``."""
    for nome in nomes:
        excecao, termo = classificar(nome)
        if excecao:
            return excecao, nome, termo
    return None, None, None


def identificavel(nomes: list[str]) -> bool:
    """Há ao menos um material COM NOME associado ao covering."""
    return any(normalizar(n) for n in nomes)
