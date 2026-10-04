"""EDI-004 / EDI-004.1 — Programa mínimo de necessidades da UH.

Par de requisitos que verifica a **existência** do programa mínimo de ambientes
na unidade habitacional (UH), agregando as 6 categorias em um único veredito.

    EDI-004    Presença do programa mínimo de ambientes na UH
               (sala, dorm. casal, dorm. 2 pessoas, cozinha, área de serviço,
               banheiro).
    EDI-004.1  Varanda integrante do programa mínimo (apenas UH multifamiliar).

ATOMICIDADE (dependências): apenas as regras de área útil (EDI-001/EDI-002)
dependem do veredito agregado do EDI-004(/.1) — área útil é a soma de todos
os ambientes da UH, logo só é significativa quando o programa está completo.
As demais regras dimensionais por categoria (EDI-004.1, EDI-007/008/009,
EDI-011) NÃO dependem mais do EDI-004: cada uma já classifica e avalia,
isoladamente, apenas os ambientes da sua própria categoria — não precisam do
programa completo para serem avaliáveis. Isso evita o falso "NÃO AVALIÁVEL"
que ocorria quando faltava, por exemplo, a sala, mas o banheiro (e sua
largura) estavam plenamente presentes e verificáveis no modelo.

``checar`` está implementado nas duas classes abaixo — existência nominal do
programa, via ``core.dominio.conhecimento.catalogo_ambientes.avaliar_
programa`` — com teste unitário isolado em ``tests/core/regras/bim/
test_edi_004_programa_necessidades.py``. Base normativa do programa
mínimo: config/Base_Requisitos_Portaria_MCID_725.xlsx.
"""

from __future__ import annotations

from core.dominio import ancora
from core.dominio.contratos.regra import Contexto, Dominio, Regra, Verbo
from core.dominio.vocabulario import declaracoes as dec
from core.dominio.vocabulario import motivos
from core.regras.registro import registrar

# Ambientes do programa mínimo (itens exigidos; dois dormitórios distintos).
_AMBIENTES_MINIMOS = ("sala", "dormitorio_casal", "dormitorio_2p", "cozinha",
                      "area_servico", "banheiro")


def _diagnostico(ctx: Contexto, exigidos: list[str]) -> dict | None:
    """Extrai os ambientes e avalia a presença nominal do programa informado.

    Normaliza a exigência pelas UHs que o contêiner em análise **representa**
    (ADR-021), com piso de 1 pela mesma razão do EDI-001/002 — ver a nota de
    limitação em ``programa_ambientes.avaliar_programa``.

    Conta só a **população** da triagem. Ambiente fantasma do exportador não
    entra na contagem e vai para ``fora_da_populacao``, com os sinais
    (ADR-031).

    Devolve o diagnóstico (``tipo='ambientes'``) ou ``None`` se não há IfcSpace
    na população."""
    from core.dominio.conhecimento import catalogo_ambientes as pa

    triagem = ctx.leitura_modelo.triar_ambientes()
    if not triagem.populacao:
        return None
    diag = pa.avaliar_programa(
        triagem.populacao, exigidos,
        unidades_representadas=max(1, ancora.unidades_representadas(ctx)))
    diag["fora_da_populacao"] = triagem.fora
    diag["nota_fora_da_populacao"] = triagem.nota()
    return diag


def _sem_ifcspace(regra: Regra):
    """Modelo aberto e sem nenhum ``IfcSpace``: não avaliável por
    ``informacao_ausente`` (ADR-006/022).

    A ausência de ambientes é o requisito de informação do ADR-007 não
    atendido — o modelo existe, o que falta é o conteúdo que o IDS exigiria."""
    return regra.nao_avaliavel(
        motivo=motivos.INFORMACAO_AUSENTE,
        mensagem="Nenhum ambiente (IfcSpace) encontrado no modelo.")


@registrar
class EDI004(Regra):
    id = "EDI-004"
    dominio = Dominio.BIM
    descricao = "Presença do programa mínimo de ambientes na UH"
    depende_de = []                       # porta do conjunto; sem pré-requisito
    ids_spec = None
    alvo = "IfcSpace (por função / LongName)"
    verbo = Verbo.EXISTENCIA
    parametro = {"ambientes_minimos": list(_AMBIENTES_MINIMOS)}
    insumos = []
    usa_visualizacao = True  # relatorio exibe os ambientes no modelo
    # Programa de necessidades pressupõe uma edificação (UH) no modelo.
    aplicabilidade = {dec.TIPO_MODELO: dec.COM_EDIFICACAO}

    def checar(self, ctx: Contexto):
        if ctx.modelo_ifc is None:
            return self.nao_avaliavel(
                motivo=motivos.INSUMO_DO_PROPONENTE_AUSENTE,
                mensagem="Modelo IFC não carregado.")

        diag = _diagnostico(ctx, self.parametro["ambientes_minimos"])
        if diag is None:
            return _sem_ifcspace(self)

        base = {
            "valor_esperado": "; ".join(sorted({c["rotulo"] for c in diag["categorias"]})),
            "valor_encontrado": f"{diag['total_ambientes']} ambiente(s)",
            "elementos": [a["global_id"] for a in diag["ambientes"]],
            "detalhe": diag,
        }
        sufixo_uh = (f" (exigência normalizada para {diag['num_uhs']} UHs"
                     f" representadas pelo contêiner)"
                     if diag.get("num_uhs", 1) > 1 else "")
        if diag["atende_programa"]:
            return self.conforme(
                mensagem=(f"Programa mínimo atendido ({diag['total_ambientes']} "
                          f"ambientes).{sufixo_uh}{diag['nota_fora_da_populacao']}"),
                **base)
        return self.nao_conforme(
            mensagem=(f"Programa mínimo incompleto. Faltam: "
                      f"{', '.join(diag['faltantes'])}.{sufixo_uh}"
                      f"{diag['nota_fora_da_populacao']}"),
            **base)


@registrar
class EDI0041(Regra):
    id = "EDI-004.1"
    dominio = Dominio.BIM
    descricao = "Varanda integrante do programa mínimo (UH multifamiliar)"
    depende_de = []              # atômica: classifica seus próprios ambientes,
                                  # independente do resultado agregado do EDI-004
    ids_spec = None
    alvo = "IfcSpace 'varanda'"
    verbo = Verbo.EXISTENCIA
    parametro = {"ambientes_minimos": ["varanda"]}
    insumos = []
    usa_visualizacao = True  # relatorio exibe os ambientes no modelo
    # Varanda multifamiliar: exige edificação e tipologia apartamento.
    aplicabilidade = {dec.TIPO_MODELO: dec.COM_EDIFICACAO,
                      dec.TIPOLOGIA: [dec.APARTAMENTO]}

    def checar(self, ctx: Contexto):
        if ctx.modelo_ifc is None:
            return self.nao_avaliavel(
                motivo=motivos.INSUMO_DO_PROPONENTE_AUSENTE,
                mensagem="Modelo IFC não carregado.")

        diag = _diagnostico(ctx, self.parametro["ambientes_minimos"])
        if diag is None:
            return _sem_ifcspace(self)

        base = {"valor_esperado": "Varanda",
                    "valor_encontrado": f"{diag['total_ambientes']} ambiente(s)",
                    "elementos": [a["global_id"] for a in diag["ambientes"]],
                    "detalhe": diag}
        sufixo_uh = (f" (exigência normalizada para {diag['num_uhs']} UHs"
                     f" representadas pelo contêiner)"
                     if diag.get("num_uhs", 1) > 1 else "")
        if diag["atende_programa"]:
            return self.conforme(
                mensagem=(f"Varanda presente na UH.{sufixo_uh}"
                          f"{diag['nota_fora_da_populacao']}"),
                **base)
        return self.nao_conforme(
            mensagem=(f"Varanda não identificada entre os ambientes do modelo."
                      f"{sufixo_uh}{diag['nota_fora_da_populacao']}"),
            **base)
