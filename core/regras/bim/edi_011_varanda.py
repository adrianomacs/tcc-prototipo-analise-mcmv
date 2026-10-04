"""EDI-011 — Dimensões mínimas da varanda (apartamentos).

Requisito dimensional multifamiliar (Anexo III, Tab. 1, item 2.I.c.viii):
largura interna ≥ 0,80 m **e** área útil ≥ 1,50 m², para cada varanda da UH.

Mecânica (mesma família de EDI-007/008/009):
  * só a **população** da triagem do extrator, com o fantasma do exportador
    fora e reportado (ADR-031);
  * identificação nominal da categoria 'varanda' (programa_ambientes);
  * largura **geométrica** pelo footprint (retângulo rotacionado mínimo);
  * área preferencialmente **nominal** (quantidade do IfcSpace, como nas
    regras de área EDI-001/002); sem quantidade, usa a área do footprint como
    fallback — a fonte fica registrada por ambiente (transparência).

ATOMICIDADE: não depende do resultado agregado de EDI-004/EDI-004.1
(``depende_de = []``) — extrai e classifica os ambientes 'varanda' de forma
independente, direto do modelo. Assim, mesmo que o programa mínimo esteja
incompleto (ex.: falta a sala), a varanda ainda é avaliada dimensionalmente
se houver varanda(s) no modelo. Todos os ambientes 'varanda' devem atender.

Os dois NÃO AVALIÁVEL — nenhuma varanda identificada e varanda sem medida
completa — saem com ``informacao_ausente`` (ADR-006/022), pela mesma razão
das larguras de EDI-007/008/009: é conteúdo que o requisito de informação
(ADR-007) exigiria e o modelo não traz.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Contexto, Dominio, Regra, Verbo
from core.dominio.vocabulario import declaracoes as dec
from core.dominio.vocabulario import motivos
from core.regras.registro import registrar


@registrar
class EDI011(Regra):
    id = "EDI-011"
    dominio = Dominio.BIM
    descricao = "Dimensões mínimas da varanda (largura ≥ 0,80 m e área ≥ 1,50 m²)"
    depende_de = []  # atômica: classifica seus próprios ambientes 'varanda',
                     # independente do resultado agregado do EDI-004/EDI-004.1
    ids_spec = None
    alvo = "IfcSpace 'varanda' (footprint + quantidade de área)"
    verbo = Verbo.DIMENSIONAL
    parametro = {"largura_min_m": 0.80, "area_min_m2": 1.50}
    insumos = []
    usa_visualizacao = True  # relatorio exibe as varandas medidas no modelo
    aplicabilidade = {dec.TIPO_MODELO: dec.COM_EDIFICACAO,
                      dec.TIPOLOGIA: [dec.APARTAMENTO]}

    def checar(self, ctx: Contexto):
        if ctx.modelo_ifc is None:
            return self.nao_avaliavel(
                motivo=motivos.INSUMO_DO_PROPONENTE_AUSENTE,
                mensagem="Modelo IFC não carregado.")

        from core.dominio.conhecimento import catalogo_ambientes as pa

        larg_min = self.parametro["largura_min_m"]
        area_min = self.parametro["area_min_m2"]

        # Só a população da triagem: a varanda fantasma do exportador não é
        # avaliada, e o relatório a mostra (ADR-031).
        triagem = ctx.leitura_modelo.triar_ambientes()
        nota = triagem.nota()
        alvos = []
        for a in triagem.populacao:
            chave, rot, termo = pa.classificar(a.nome)
            if chave == "varanda":
                item = a.to_dict()
                item.update({"categoria": chave, "categoria_rotulo": rot,
                             "termo_casado": termo})
                alvos.append(item)

        if not alvos:
            return self.nao_avaliavel(
                motivo=motivos.INFORMACAO_AUSENTE,
                mensagem="Nenhum ambiente identificado como 'Varanda' no modelo "
                         "(correspondência nominal); dimensões não avaliáveis." + nota)

        medidas = triagem.medidas
        reprovados, sem_medida = [], []
        for item in alvos:
            m = medidas.get(item["global_id"], {"erro": "sem medida"})
            item.update(m)

            # Área: quantidade nominal do IfcSpace; fallback = footprint.
            if isinstance(item.get("area_m2"), (int, float)):
                area, fonte = float(item["area_m2"]), item.get("fonte_area") or "quantidade"
            elif "area_footprint_m2" in m:
                area, fonte = float(m["area_footprint_m2"]), "footprint (geométrica)"
            else:
                area, fonte = None, None
            item["area_avaliada_m2"] = area
            item["fonte_area_avaliada"] = fonte

            largura = m.get("largura_m")
            if largura is None or area is None:
                sem_medida.append(item["nome"])
                item["atende"] = None
                continue

            ok_largura = largura >= larg_min
            ok_area = area >= area_min
            item["atende"] = ok_largura and ok_area
            if not item["atende"]:
                falhas = []
                if not ok_largura:
                    falhas.append(f"largura {largura:.2f} m < {larg_min:.2f} m")
                if not ok_area:
                    falhas.append(f"área {area:.2f} m² < {area_min:.2f} m²")
                reprovados.append(f"{item['nome']} ({'; '.join(falhas)})")

        detalhe = {
            "tipo": "larguras",
            "categoria": "varanda",
            "categoria_rotulo": "Varanda",
            "largura_min_m": larg_min,
            "area_min_m2": area_min,
            "metodo": ctx.leitura_modelo.metodo_ambientes,
            "ambientes": alvos,
            "fora_da_populacao": triagem.fora,
        }
        base = {
            "valor_esperado": f"largura ≥ {larg_min:.2f} m e área ≥ {area_min:.2f} m²",
            "valor_encontrado": f"{len(alvos)} varanda(s) avaliada(s)",
            "elementos": [x["global_id"] for x in alvos],
            "detalhe": detalhe,
        }

        if reprovados:
            return self.nao_conforme(
                mensagem=(f"Varanda com dimensões abaixo do mínimo: "
                          f"{'; '.join(reprovados)}.{nota}"),
                **base)
        if sem_medida:
            return self.nao_avaliavel(
                motivo=motivos.INFORMACAO_AUSENTE,
                mensagem=(f"{len(sem_medida)} varanda(s) sem medida completa "
                          f"({'; '.join(sem_medida)}); não avaliável.{nota}"),
                **base)
        return self.conforme(
            mensagem=(f"{len(alvos)} varanda(s) com largura ≥ {larg_min:.2f} m "
                      f"e área ≥ {area_min:.2f} m².{nota}"),
            **base)
