"""EDI-007 / EDI-008 / EDI-009 — Larguras mínimas de ambientes.

Trio de requisitos dimensionais do programa de necessidades (Anexo III,
Tab. 1, itens 2.I.c.iii a 2.I.c.v):

    EDI-007    Largura mínima da cozinha ................. ≥ 1,80 m
    EDI-008    Largura mínima da sala de estar/refeições .. ≥ 2,40 m
    EDI-009    Largura mínima do banheiro ................. ≥ 1,50 m

Mecânica comum (nominal × dimensional, com transparência):
  0. entra só a **população** da triagem do extrator. O ambiente fantasma do
     exportador fica fora e é reportado em ``fora_da_populacao`` (ADR-031);
  1. os ambientes são identificados **nominalmente** pela categorização de
     ``core.dominio.conhecimento.catalogo_ambientes`` (mesma base do EDI-004);
  2. a largura é medida **geometricamente** pelo footprint do IfcSpace
     (``core.infra.ifc.extrator_ambientes`` — menor lado do retângulo
     rotacionado mínimo; método e limitação registrados no diagnóstico);
  3. TODOS os ambientes da categoria devem atender (num modelo com múltiplas
     UHs há várias cozinhas — cada uma precisa cumprir o mínimo, o que torna
     a checagem independente da normalização por UH).

Três estados: algum ambiente medido abaixo do mínimo -> NÃO CONFORME; todos
medidos e conformes -> CONFORME (se houver ambiente sem medida, vira NÃO
AVALIÁVEL, pois o conjunto está incompleto); nenhum ambiente da categoria ->
NÃO AVALIÁVEL (categoria ausente no modelo). Os dois NÃO AVALIÁVEL saem com
o motivo ``informacao_ausente`` (ADR-006/022): categoria sem correspondência
nominal e ambiente sem geometria medível são, os dois, conteúdo que o requisito
de informação (ADR-007) exigiria do modelo e que ele não traz — a taxonomia
não distingue "nome fora do catálogo" de "IfcSpace ausente", e distingui-los é
trabalho da mensagem, não do motivo.

ATOMICIDADE: estas regras NÃO dependem do resultado agregado do EDI-004
(``depende_de = []``). Cada uma extrai e classifica, de forma independente,
apenas os ambientes da sua própria categoria (cozinha/sala/banheiro) — não
precisa que o programa mínimo completo esteja satisfeito para ser avaliada.
Assim, um modelo com o programa incompleto (ex.: falta a sala) ainda tem a
largura do banheiro verificada, desde que haja banheiro(s) no modelo. Isso
evita que a checagem "herde" NÃO AVALIÁVEL do EDI-004 por ambientes de outras
categorias que nada têm a ver com a dimensão sendo avaliada aqui.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Contexto, Dominio, Regra, Verbo
from core.dominio.vocabulario import declaracoes as dec
from core.dominio.vocabulario import motivos
from core.regras.registro import registrar


def _checar_largura(regra: Regra, ctx: Contexto, categoria: str):
    """Mede a largura de todos os ambientes da categoria e compara ao mínimo."""
    if ctx.modelo_ifc is None:
        return regra.nao_avaliavel(motivo=motivos.INSUMO_DO_PROPONENTE_AUSENTE,
                                   mensagem="Modelo IFC não carregado.")

    from core.dominio.conhecimento import catalogo_ambientes as pa

    minimo = regra.parametro["largura_min_m"]
    # Só a população da triagem. A sala fantasma de 1,83 m reprovava o EDI-008
    # no lugar da real, de 4,735 m (ADR-031).
    triagem = ctx.leitura_modelo.triar_ambientes()
    nota = triagem.nota()
    alvos = []
    for a in triagem.populacao:
        chave, rot, termo = pa.classificar(a.nome)
        if chave == categoria:
            item = a.to_dict()
            item.update({"categoria": chave, "categoria_rotulo": rot,
                         "termo_casado": termo})
            alvos.append(item)

    rotulo_cat = pa.rotulo(categoria)
    if not alvos:
        return regra.nao_avaliavel(
            motivo=motivos.INFORMACAO_AUSENTE,
            mensagem=f"Nenhum ambiente identificado como '{rotulo_cat}' no "
                     "modelo (correspondência nominal); largura não avaliável." + nota)

    medidas = triagem.medidas
    reprovados, sem_medida, larguras = [], [], []
    for item in alvos:
        m = medidas.get(item["global_id"], {"erro": "sem medida"})
        item.update(m)
        if "erro" in m:
            sem_medida.append(item["nome"])
            item["atende"] = None
            continue
        larguras.append(m["largura_m"])
        item["atende"] = m["largura_m"] >= minimo
        if not item["atende"]:
            reprovados.append(f"{item['nome']} ({m['largura_m']:.2f} m)")

    detalhe = {
        "tipo": "larguras",
        "categoria": categoria,
        "categoria_rotulo": rotulo_cat,
        "largura_min_m": minimo,
        "metodo": ctx.leitura_modelo.metodo_ambientes,
        "ambientes": alvos,
        "fora_da_populacao": triagem.fora,
    }
    base = {
        "valor_esperado": f"largura ≥ {minimo:.2f} m",
        "valor_encontrado": (f"menor largura medida: {min(larguras):.2f} m"
                          if larguras else "sem medida"),
        "unidade": "m",
        "elementos": [x["global_id"] for x in alvos],
        "detalhe": detalhe,
    }

    if reprovados:
        return regra.nao_conforme(
            mensagem=(f"{rotulo_cat}: largura mínima {minimo:.2f} m não "
                      f"atendida em: {'; '.join(reprovados)}.{nota}"),
            **base)
    if sem_medida:
        return regra.nao_avaliavel(
            motivo=motivos.INFORMACAO_AUSENTE,
            mensagem=(f"{rotulo_cat}: {len(sem_medida)} ambiente(s) sem medida "
                      f"geométrica ({'; '.join(sem_medida)}); os medidos "
                      f"atendem, mas o conjunto está incompleto — não avaliável.{nota}"),
            **base)
    return regra.conforme(
        mensagem=(f"{rotulo_cat}: {len(alvos)} ambiente(s) com largura ≥ "
                  f"{minimo:.2f} m (menor medida: {min(larguras):.2f} m).{nota}"),
        **base)


class _RegraLargura(Regra):
    """Base do trio: metadado comum às larguras mínimas de ambientes."""
    dominio = Dominio.BIM
    depende_de = []              # atômica: classifica sua própria categoria de
                                  # ambientes, independente do EDI-004 agregado
    ids_spec = None
    verbo = Verbo.DIMENSIONAL
    insumos = []
    usa_visualizacao = True  # relatorio exibe os ambientes medidos no modelo
    aplicabilidade = {dec.TIPO_MODELO: dec.COM_EDIFICACAO}
    categoria = ""            # definida em cada regra

    def checar(self, ctx: Contexto):
        return _checar_largura(self, ctx, self.categoria)


@registrar
class EDI007(_RegraLargura):
    id = "EDI-007"
    descricao = "Largura mínima da cozinha (≥ 1,80 m)"
    alvo = "IfcSpace 'cozinha' (footprint)"
    parametro = {"largura_min_m": 1.80}
    categoria = "cozinha"


@registrar
class EDI008(_RegraLargura):
    id = "EDI-008"
    descricao = "Largura mínima da sala de estar/refeições (≥ 2,40 m)"
    alvo = "IfcSpace 'sala' (footprint)"
    parametro = {"largura_min_m": 2.40}
    categoria = "sala"


@registrar
class EDI009(_RegraLargura):
    id = "EDI-009"
    descricao = "Largura mínima do banheiro (≥ 1,50 m)"
    alvo = "IfcSpace 'banheiro' (footprint)"
    parametro = {"largura_min_m": 1.50}
    categoria = "banheiro"
