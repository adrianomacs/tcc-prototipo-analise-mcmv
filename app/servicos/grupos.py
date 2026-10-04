"""Grupos de requisitos e o recorte ativo — único módulo que lê
`config/grupos_requisitos.yaml` e `config/regras_ativas.yaml`, e ponto único
de acesso ao registro de regras (`core.regras.registro.regras_registradas`)
para o restante de `app/`.

Extraído de `_checagem_comum.py`.
"""

from __future__ import annotations

import os

import yaml

from core.aplicacao import grupos as grupos_mod
from core.aplicacao.grupos import Grupo  # noqa: F401 (reexportado)
from core.infra.caminhos import CONFIG
from core.regras.registro import regras_registradas


def ids_ativos() -> list[str]:
    caminho = os.path.join(CONFIG, "regras_ativas.yaml")
    if not os.path.exists(caminho):
        return []
    with open(caminho, "r", encoding="utf-8") as f:
        dados = yaml.safe_load(f) or {}
    return [str(x).strip() for x in (dados.get("ativas") or [])]


def carregar_grupo(gid: str) -> grupos_mod.Grupo | None:
    grupos = grupos_mod.carregar(os.path.join(CONFIG, "grupos_requisitos.yaml"))
    return grupos.get(gid)


def ids_executaveis(grupo: grupos_mod.Grupo, declaracoes: dict) -> list[str]:
    """Regras do grupo que de fato serão executadas: ativas no recorte, com
    motor registrado e aplicáveis às declarações correntes."""
    registradas = regras_registradas()
    ativas = set(ids_ativos())
    out: list[str] = []
    for rid in grupo.ids:
        cls = registradas.get(rid)
        if cls is None or rid not in ativas:
            continue
        if cls.motivo_inaplicavel(declaracoes) is not None:
            continue
        out.append(rid)
    return out


def membros_de_agregacao() -> set[str]:
    """Ids que são alternativa ou ramo de um requisito-pai (ex.: ENQ-010.1 e
    .2 de ENQ-010), lidos do ``agrega`` que cada regra de agregação declara.

    É a unidade da contagem de requisitos (``relatorio_json._normativo``): o
    membro de uma agregação não é requisito à parte, é evidência que o pai
    consome. EDI-004.1 tem pai na planilha mas não é agregado por ninguém — é
    requisito e conta. Lido do registro, antes de qualquer análise, para a tela
    contar requisitos na mesma unidade que o relatório conta depois."""
    return {mid for cls in regras_registradas().values()
            for mid in (getattr(cls, "agrega", None) or [])}


def regra_do_grupo(rid: str) -> tuple[grupos_mod.Grupo, grupos_mod.RegraDoGrupo] | None:
    """O grupo e a linha de um requisito, procurados em todos os grupos — o que
    o expander "O que esta regra verifica" do relatório mostra (ADR-034)."""
    grupos = grupos_mod.carregar(os.path.join(CONFIG, "grupos_requisitos.yaml"))
    for grupo in grupos.values():
        for regra in grupo.regras:
            if regra.id == rid:
                return grupo, regra
    return None



# Situação de cada requisito do grupo diante do empreendimento declarado, para
# a página "Requisitos a serem validados" (ADR-034). Os textos são de tela.
SERA_VERIFICADO = "Será verificado"
_FORA_POR_APLICABILIDADE = {
    "unifamiliar": "Não se aplica, só a casas",
    "multifamiliar": "Não se aplica, só a apartamentos",
}
_REMETIDO = "Remetido ao parecer do analista"
_REMETIDO_A_VISTORIA = "Remetido à vistoria"
_FORA_DO_RECORTE = "Fora do recorte do protótipo"


def situacao_no_empreendimento(grupo: grupos_mod.Grupo,
                               declaracoes: dict) -> list[tuple]:
    """Uma linha por **requisito** do grupo (o membro de agregação não conta à
    parte, ADR-015): ``(regra_do_grupo, situação)``.

    A aplicabilidade sai de ``ids_executaveis``, o mesmo cálculo que a
    checagem faz ao abrir, para esta lista nunca dizer outra coisa que a
    checagem vai fazer. Requisito executável cuja regra se declara remetida
    (``remete_a``) aparece como remetido, porque sai sempre NÃO AVALIÁVEL."""
    from core.dominio.vocabulario import motivos

    registradas = regras_registradas()
    membros = membros_de_agregacao()
    executaveis = set(ids_executaveis(grupo, declaracoes))
    linhas = []
    for r in grupo.regras:
        if r.id in membros:
            continue
        if r.id in executaveis:
            remete = getattr(registradas.get(r.id), "remete_a", "")
            if not remete:
                situacao = SERA_VERIFICADO
            elif remete == motivos.VERIFICACAO_EM_CAMPO:
                situacao = _REMETIDO_A_VISTORIA
            else:
                situacao = _REMETIDO
        else:
            situacao = _FORA_POR_APLICABILIDADE.get(r.aplicabilidade,
                                                    _FORA_DO_RECORTE)
        linhas.append((r, situacao))
    return linhas
