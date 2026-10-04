"""Base dos RAMOS de absortância solar por zona bioclimática (ADR-026/027).

Um requisito de absortância do Anexo III é um **pai** (o item da Portaria) com
dois **ramos** que a zona bioclimática seleciona — telhado: ZB 1–3 → ≤ 0,6 e
ZB 4–8 → ≤ 0,4 (4.III.i); parede externa: ZB 1–2 → ≤ 0,6 e ZB 3–6 → ≤ 0,4
(4.II.a.x). O pai é uma ``RegraAgregacao`` em modo ``selecao_exclusiva``; cada
ramo é uma subclasse desta base, um arquivo por id (ADR-005). Esta base é o
equivalente, para a absortância, do que ``distancia_equipamento`` é para as
regras de distância: a mecânica comum, sem veredito próprio.

O que um ramo faz, na ordem
---------------------------

1. **População alvo** — pelo *hook* ``populacao(leitura)``, que cada família
   define, sempre com DUAS condições (ADR-027). O LADO (parede × cobertura)
   vem de ``classificacao_covering``: pelo hospedeiro quando há
   ``IfcRelCoversBldgElements``, e, sem relação, pelo ``PredefinedType`` do
   próprio covering (emenda ao ADR-027 — o Revit não autora a relação).
   Telhado: lado de cobertura **e** ``PredefinedType = ROOFING``. Parede
   externa: lado de parede **e** ``Pset_CoveringCommon.IsExternal`` declarado
   no próprio covering, conferido contra o ``Pset_WallCommon`` do hospedeiro
   quando a relação existe — divergência entre as duas declarações bloqueia o
   ramo (``CHAVE_BLOQUEIO``) em vez de escolher um lado. Nunca se itera
   ``IfcCovering`` cru, nem se infere o lado por geometria ou nome: covering
   fora das condições é REPORTADO no detalhe, não avaliado.
2. **Exceções da Portaria, no ramo** — só onde a Portaria as escreve. No
   telhado (DN-01) o material do covering decide: telha de barro não
   vitrificada ou cobertura verde → o limite não se aplica àquele covering;
   material sem nome → não identificável, e o ramo não conclui. Nunca conforme
   por omissão. Na parede, 4.II.a.x não traz exceção alguma (DN-02) e o ramo
   desliga a etapa inteira por ``excecoes_por_material = False``: exigir
   material ali produziria pendência por informação que o requisito não pede.
3. **Veredito sob o próprio limite** — ``AbsortanciaSolar`` de cada covering
   restante contra ``limite``, que é parâmetro do ramo. O que se lê do
   contexto é a **zona** (``ctx.zona_bioclimatica``, ADR-030), não o limite.
   A propriedade é exigida pelo NOME, em **qualquer** property set
   (``propriedades_do_elemento`` achata todos), porque o IFC não tem
   absortância solar de superfície opaca em pset padrão e
   ``ThermalTransmittance`` é outra grandeza: ela é requisito de informação do
   contratante, e exigir um nome de pset que ninguém publicou rejeitaria
   modelos por convenção não combinada (ADR-027).
4. **Aplicabilidade** — a zona seleciona o ramo (``zonas``, classes da edição
   de 2024) ou não; cláusula presa ao vocabulário de 2005 (``zonas`` vazio) é
   **indeterminada** em todo município (DN-08), e zona não resolvida também.
   O ramo emite veredito só quando é APLICÁVEL; nos outros dois casos sai NÃO
   AVALIÁVEL e deixa no ``detalhe`` o que o pai precisa — a aplicabilidade e o
   veredito que teria (``agregacao.CHAVE_APLICABILIDADE`` /
   ``CHAVE_VEREDITO_RAMO``). Ramo nunca afirma aplicabilidade que não tem.

O executor não muda e o contrato de ``Regra`` não ganha campo: tudo acima é
``checar`` (ADR-005 e a recusa da Fase R3 a atributo novo em ``Regra``).
"""

from __future__ import annotations

from typing import Any

from core.dominio.conhecimento import materiais_cobertura as mat
from core.dominio.contratos.regra import Contexto, Dominio, Regra, Resultado, Verbo
from core.dominio.vocabulario import declaracoes as dec
from core.dominio.vocabulario import motivos, tipos_diagnostico
from core.regras.base import agregacao as ag

# Chave de despacho do relatório dedicado.
TIPO_DIAGNOSTICO = tipos_diagnostico.ABSORTANCIA

# Como cada covering da população entrou no veredito do ramo.
SIT_ATENDE = "atende"
SIT_NAO_ATENDE = "nao_atende"
SIT_EXCECAO = "excecao"                       # DN-01: o limite não se aplica
SIT_MATERIAL_NAO_IDENTIFICAVEL = "material_nao_identificavel"
SIT_SEM_ABSORTANCIA = "sem_absortancia"

ROTULO_SITUACAO = {
    SIT_ATENDE: "atende ao limite",
    SIT_NAO_ATENDE: "acima do limite",
    SIT_EXCECAO: "exceção da Portaria — limite não se aplica",
    SIT_MATERIAL_NAO_IDENTIFICAVEL: "material não identificável",
    SIT_SEM_ABSORTANCIA: "absortância não informada",
}


def populacao_cobertura(leitura: Any) -> tuple[list[Any], dict]:
    """``(coverings alvo, diagnóstico)`` do telhado: lado de cobertura por
    ``classificacao_covering`` **e** ``PredefinedType = ROOFING`` (ADR-027).

    O lado vem do hospedeiro quando a relação existe e, sem relação, do
    ``PredefinedType`` do próprio covering (herdado do tipo quando a ocorrência
    não declara). A segunda condição não é redundante no primeiro caso:
    ``IfcRoof`` como hospedeiro classifica o covering como cobertura mesmo sem
    ``PredefinedType``, e o ADR-027 exige o ``ROOFING`` como requisito de
    informação verificável — é ele que distingue "a ferramenta deduziu" de
    "o modelo declarou". No covering órfão as duas condições coincidem (só o
    ``ROOFING`` o põe do lado da cobertura). O que ficou de fora vai nomeado no
    diagnóstico, para o relatório dizer o que falta ao modelo.
    """
    particao = leitura.classificar_revestimentos()
    alvo = [c for c in particao.cobertura if leitura.predefinido(c) == "ROOFING"]
    sem_roofing = [c for c in particao.cobertura if c not in alvo]
    pelo_hospedeiro = [c for c in particao.cobertura
                       if particao.origem.get(c) == leitura.origem_hospedeiro]
    diag = {
        "criterio": "lado de cobertura (hospedeiro por IfcRelCoversBldgElements "
                    "ou, sem relação, PredefinedType do próprio covering) E "
                    "PredefinedType = ROOFING",
        "total_coverings": (len(particao.parede) + len(particao.cobertura)
                            + len(particao.nao_classificado)),
        "parede": len(particao.parede),
        "cobertura_pelo_hospedeiro": len(pelo_hospedeiro),
        "cobertura_pelo_predefinido": len(particao.cobertura) - len(pelo_hospedeiro),
        "cobertura_sem_roofing": [_gid(c) for c in sem_roofing],
        "nao_classificados": [_gid(c) for c in particao.nao_classificado],
        "alvo": [_gid(c) for c in alvo],
        "mensagem_vazia": (
            "Nenhum IfcCovering de cobertura classificado no modelo (hospedeiro "
            "de cobertura, ou PredefinedType = ROOFING declarado no próprio "
            "covering) — requisito de informação não entregue; "
            f"{len(sem_roofing)} covering(s) com hospedeiro de cobertura sem "
            f"ROOFING, {len(particao.nao_classificado)} não classificado(s), "
            f"{len(particao.parede)} de parede."),
    }
    return alvo, diag


# Bloqueio que a POPULAÇÃO impõe ao ramo: ``(motivo, mensagem)``. Existe
# porque há causa que nasce antes de qualquer covering ser avaliado — a
# declaração de externalidade que se contradiz (ADR-027) — e que não é
# "população vazia": há elementos, e é justamente por isso que não se conclui.
CHAVE_BLOQUEIO = "bloqueio"

# Como a externalidade de um covering de parede foi resolvida (ADR-027).
EXT_EXTERNA = "declarada_externa"
EXT_INTERNA = "declarada_interna"
EXT_SEM_DECLARACAO = "sem_declaracao"
EXT_DIVERGENTE = "divergente"

PSET_COVERING = "Pset_CoveringCommon"
PSET_PAREDE = "Pset_WallCommon"
PROP_EXTERNO = "IsExternal"


def populacao_parede(leitura: Any) -> tuple[list[Any], dict]:
    """``(coverings alvo, diagnóstico)`` da parede EXTERNA: hospedeiro
    ``IfcWall`` por ``classificacao_covering`` **e** ``IsExternal`` declarado
    no ``Pset_CoveringCommon`` do PRÓPRIO covering (ADR-027).

    Por que a propriedade é do covering, e não do hospedeiro. O ADR-027 decidiu
    que o requisito de informação recai sobre o elemento classificado, não
    sobre a relação ``IfcRelCoversBldgElements`` — que o Revit e o Archicad
    raramente autoram. ``IsExternal`` não é exigência inventada para este
    protótipo: é propriedade do ``Pset_CoveringCommon`` padrão desde o IFC4,
    ao lado das que o requisito já lê. Fazer o requisito depender do
    hospedeiro repetiria, na parede, a fragilidade que o ADR-027 nomeou.

    O hospedeiro entra como CONFERÊNCIA, não como fonte: quando a relação
    existe e o ``IfcWall`` também declara ``Pset_WallCommon.IsExternal``, os
    dois têm de concordar. Discordando, o ramo não escolhe um lado — bloqueia
    com ``inconsistencia_declaratoria`` (ADR-022), porque é o proponente quem
    declarou as duas coisas e é dele a correção. Nenhuma heurística geométrica decide externalidade (ADR-027).
    """
    particao = leitura.classificar_revestimentos()
    alvo: list[Any] = []
    internos: list[Any] = []
    sem_declaracao: list[Any] = []
    divergentes: list[Any] = []
    pelo_hospedeiro = [c for c in particao.parede
                       if particao.origem.get(c) == leitura.origem_hospedeiro]

    for covering in particao.parede:
        proprio, _ = leitura.propriedade_de_pset(covering, PSET_COVERING, PROP_EXTERNO)
        hospedeiro = particao.hospedeiro.get(covering)
        do_hospedeiro = None
        if hospedeiro is not None:
            do_hospedeiro, _ = leitura.propriedade_de_pset(
                hospedeiro, PSET_PAREDE, PROP_EXTERNO)
        if proprio is None:
            sem_declaracao.append(covering)
        elif do_hospedeiro is not None and bool(do_hospedeiro) != bool(proprio):
            divergentes.append(covering)
        elif bool(proprio):
            alvo.append(covering)
        else:
            internos.append(covering)

    diag = {
        "criterio": f"lado de parede (hospedeiro IfcWall por IfcRelCoversBldgElements "
                    f"ou, sem relação, PredefinedType = CLADDING do próprio covering) E "
                    f"{PSET_COVERING}.{PROP_EXTERNO} = True, conferido contra "
                    f"{PSET_PAREDE}.{PROP_EXTERNO} do hospedeiro quando declarado",
        "total_coverings": (len(particao.parede) + len(particao.cobertura)
                            + len(particao.nao_classificado)),
        "cobertura": len(particao.cobertura),
        "parede_pelo_hospedeiro": len(pelo_hospedeiro),
        "parede_pelo_predefinido": len(particao.parede) - len(pelo_hospedeiro),
        EXT_INTERNA: [_gid(c) for c in internos],
        EXT_SEM_DECLARACAO: [_gid(c) for c in sem_declaracao],
        EXT_DIVERGENTE: [_gid(c) for c in divergentes],
        "nao_classificados": [_gid(c) for c in particao.nao_classificado],
        "alvo": [_gid(c) for c in alvo],
        "mensagem_vazia": (
            "Nenhum IfcCovering de parede externa classificado no modelo "
            f"(hospedeiro IfcWall, ou PredefinedType = CLADDING declarado no "
            f"próprio covering, E {PSET_COVERING}.{PROP_EXTERNO} = True) — "
            "requisito de informação não entregue; "
            f"{len(sem_declaracao)} covering(s) de parede sem "
            f"'{PROP_EXTERNO}' declarado, {len(internos)} declarado(s) "
            f"interno(s), {len(particao.nao_classificado)} não classificado(s), "
            f"{len(particao.cobertura)} de cobertura."),
    }
    if divergentes:
        diag[CHAVE_BLOQUEIO] = (
            motivos.INCONSISTENCIA_DECLARATORIA,
            (f"{len(divergentes)} covering(s) de parede declaram "
            f"'{PROP_EXTERNO}' em contradição com o IfcWall que os hospeda: "
            f"{'; '.join(_gid(c) for c in divergentes)}. As duas declarações "
            "são do proponente e o protótipo não escolhe entre elas "
            "— a divergência se resolve na declaração, não no veredito."))
    return alvo, diag


def _gid(elemento: Any) -> str:
    return str(getattr(elemento, "GlobalId", "") or "")


class RamoAbsortancia(Regra):
    """Um ramo de absortância. A subclasse declara ``id``, ``descricao``,
    ``limite``, ``zonas``/``zonas_texto``, ``ref_portaria`` e ``populacao``."""

    dominio = Dominio.GIS_BIM
    verbo = Verbo.ATRIBUTO
    depende_de: list[str] = []
    ids_spec = None       # ADR-007: a regra conclui sozinha; o IDS é do contratante
    alvo = "IfcCovering"
    exige_terreno = ""
    aplicabilidade = {dec.TIPO_MODELO: dec.COM_EDIFICACAO}

    # Sem contraparte nativa no IFC (ADR-027): procurada pelo NOME, em
    # qualquer pset do covering. Trocar por leitura de pset nomeado é decisão
    # de quando a CAIXA publicar a especificação, não ajuste de código.
    propriedade = "AbsortanciaSolar"
    limite: float = 0.0
    # Classes da ABNT TR 15220-3-1:2024 que selecionam este ramo. VAZIO = a
    # cláusula está no vocabulário de 2005 e não se traduz (DN-08): o ramo é
    # candidato em todo município, com aplicabilidade indeterminada.
    zonas: tuple[str, ...] = ()
    zonas_texto = ""      # como a Portaria escreve a faixa ("1, 2 e 3")
    ref_portaria = ""
    familia = "cobertura"  # como a população é chamada nas mensagens
    # A Portaria excetua material só no telhado (DN-01): 4.II.a.x não traz
    # exceção nenhuma. Na parede, portanto, o material é irrelevante — e
    # exigi-lo produziria `informacao_ausente` por uma informação que o
    # requisito não pede (DN-02).
    excecoes_por_material = True

    # -- hooks -------------------------------------------------------------

    def populacao(self, leitura: Any) -> tuple[list[Any], dict]:
        """``(alvo, diagnóstico)`` lidos pela porta ``LeituraModelo`` (ADR-036)."""
        raise NotImplementedError(f"{self.id}: a família não declarou a população.")

    def aplicabilidade_na_zona(self, zona: Any) -> tuple[str, str]:
        """``(agregacao.RAMO_*, explicação)`` para a zona resolvida (ou None)."""
        if not self.zonas:
            return ag.RAMO_INDETERMINADA, (
                f"A faixa \"zonas {self.zonas_texto}\" está no zoneamento da NBR "
                "15220-3:2005, que a edição vigente (ABNT TR 15220-3-1:2024) "
                "não publica; a numeração não se preserva e não se traduz. "
                "O ramo é candidato em todo município.")
        if zona is None:
            return ag.RAMO_INDETERMINADA, (
                "Zona bioclimática não resolvida para o município: não se sabe "
                "qual ramo aplica.")
        classe = str(getattr(zona, "classe", zona))
        if classe in self.zonas:
            return ag.RAMO_APLICAVEL, (
                f"Zona {classe} está na faixa \"{self.zonas_texto}\" deste ramo.")
        return ag.RAMO_INAPLICAVEL, (
            f"Zona {classe} não está na faixa \"{self.zonas_texto}\" deste ramo.")

    # -- checagem ----------------------------------------------------------

    def checar(self, ctx: Contexto) -> Resultado:
        if ctx.modelo_ifc is None:
            return self.nao_avaliavel(
                motivo=motivos.INSUMO_DO_PROPONENTE_AUSENTE,
                mensagem="Modelo IFC não carregado.")

        leitura = ctx.leitura_modelo
        alvo, diag_pop = self.populacao(leitura)
        zona = ctx.zona_bioclimatica
        aplic, explicacao = self.aplicabilidade_na_zona(zona)
        base_detalhe = {
            "tipo": TIPO_DIAGNOSTICO,
            "limite": self.limite,
            "propriedade": self.propriedade,
            "ref_portaria": self.ref_portaria,
            "zonas_texto": self.zonas_texto,
            "zona_resolvida": _zona_dict(zona),
            "explicacao_aplicabilidade": explicacao,
            "populacao": diag_pop,
            "coverings": [],
            ag.CHAVE_APLICABILIDADE: aplic,
            ag.CHAVE_VEREDITO_RAMO: "",
        }

        bloqueio = diag_pop.get(CHAVE_BLOQUEIO)
        if bloqueio:
            motivo_bloqueio, mensagem_bloqueio = bloqueio
            return self.nao_avaliavel(motivo=motivo_bloqueio,
                                      mensagem=mensagem_bloqueio,
                                      detalhe=base_detalhe)

        if not alvo:
            return self.nao_avaliavel(
                motivo=motivos.INFORMACAO_AUSENTE,
                mensagem=diag_pop.get("mensagem_vazia")
                or f"Nenhum IfcCovering de {self.familia} classificado no modelo.",
                detalhe=base_detalhe)

        coverings = [self._avaliar(c, leitura) for c in alvo]
        base_detalhe["coverings"] = coverings
        elementos = [c["global_id"] for c in coverings]
        estado_proprio, motivo_proprio, msg_propria = self._veredito_proprio(coverings)
        # Só um veredito de verdade viaja ao pai; "não avaliável" é ausência
        # de veredito, e a causa dele já está em ``motivo_proprio``.
        base_detalhe[ag.CHAVE_VEREDITO_RAMO] = (
            estado_proprio if estado_proprio in ("conforme", "nao_conforme") else "")
        base_detalhe["mensagem_sob_o_proprio_limite"] = msg_propria
        comparados = [c["absortancia"] for c in coverings
                      if c["situacao"] in (SIT_ATENDE, SIT_NAO_ATENDE)]
        comuns = {
            "valor_esperado": f"<= {self.limite}",
            "valor_encontrado": (max(comparados) if comparados else None),
            "unidade": "absortância (adimensional)",
            "elementos": elementos,
            "detalhe": base_detalhe,
        }

        # 1) O ramo não concluiu sob o próprio limite: a causa é dele, e vem
        #    antes da aplicabilidade — é o que destrava, seja qual for a zona.
        if motivo_proprio:
            return self.nao_avaliavel(motivo=motivo_proprio, mensagem=msg_propria,
                                      **comuns)
        # 2) Aplicável: o veredito próprio É o veredito.
        if aplic == ag.RAMO_APLICAVEL:
            if estado_proprio == "conforme":
                return self.conforme(mensagem=msg_propria, **comuns)
            return self.nao_conforme(mensagem=msg_propria, **comuns)
        # 3) Inaplicável: NÃO AVALIÁVEL por não aplicável (ADR-026), com o
        #    veredito que teria declarado — informativo, o pai o ignora.
        if aplic == ag.RAMO_INAPLICAVEL:
            return self.nao_avaliavel(
                motivo=motivos.NAO_APLICAVEL,
                mensagem=f"Ramo não aplicável: {explicacao} Sob o próprio limite "
                         f"daria {_rotulo(estado_proprio)} — {msg_propria}",
                **comuns)
        # 4) Indeterminada: o ramo se cala sobre a aplicabilidade e entrega ao
        #    pai o veredito sob o próprio limite (DN-08, ADR-026).
        return self.nao_avaliavel(
            motivo=motivos.ANALISE_HUMANA_DOCUMENTAL,
            mensagem=f"Aplicabilidade indeterminada: {explicacao} Sob o próprio "
                     f"limite (<= {self.limite}) a {self.familia} daria "
                     f"{_rotulo(estado_proprio)} — {msg_propria} Quem conclui é o "
                     "requisito-pai.",
            **comuns)

    # -- um covering -------------------------------------------------------

    def _avaliar(self, covering: Any, leitura: Any) -> dict:
        gid = _gid(covering)
        if self.excecoes_por_material:
            materiais = list(leitura.materiais_do_elemento(covering))
            excecao, material, termo = mat.classificar_materiais(materiais)
        else:
            materiais, excecao, material, termo = [], "", "", ""
        props = leitura.propriedades_do_elemento(covering)
        valor = props.get(self.propriedade)
        absortancia = float(valor) if isinstance(valor, (int, float)) \
            and not isinstance(valor, bool) else None

        if excecao:
            situacao = SIT_EXCECAO
        elif self.excecoes_por_material and not mat.identificavel(materiais):
            situacao = SIT_MATERIAL_NAO_IDENTIFICAVEL
        elif absortancia is None:
            situacao = SIT_SEM_ABSORTANCIA
        else:
            situacao = SIT_ATENDE if absortancia <= self.limite else SIT_NAO_ATENDE

        return {
            "global_id": gid,
            "nome": str(getattr(covering, "Name", "") or "") or gid,
            "materiais": materiais,
            "excecao": excecao or "",
            "rotulo_excecao": mat.ROTULO.get(excecao, "") if excecao else "",
            "material_da_excecao": material or "",
            "termo_casado": termo or "",
            "absortancia": absortancia,
            "situacao": situacao,
            "rotulo_situacao": ROTULO_SITUACAO[situacao],
        }

    def _veredito_proprio(self, coverings: list[dict]) -> tuple[str, str, str]:
        """``(estado_value, motivo_nao_avaliavel, mensagem)`` sob o próprio limite.

        Ordem: um covering acima do limite reprova (medido é medido); depois,
        qualquer covering sem material identificável ou sem absortância impede
        a conclusão; só exceções (nada comparável) é não aplicável; senão,
        conforme. Nunca conforme por omissão (DN-01).
        """
        por = {s: [c for c in coverings if c["situacao"] == s] for s in ROTULO_SITUACAO}
        n = len(coverings)

        def nomes(lista: list[dict]) -> str:
            return "; ".join(f"{c['nome']} ({c['absortancia']})"
                             if c["absortancia"] is not None else c["nome"]
                             for c in lista)

        if por[SIT_NAO_ATENDE]:
            return ("nao_conforme", "",
                    (f"Absortância acima de {self.limite} em {len(por[SIT_NAO_ATENDE])} "
                    f"de {n} covering(s) de {self.familia}: {nomes(por[SIT_NAO_ATENDE])}."))
        pendentes = por[SIT_MATERIAL_NAO_IDENTIFICAVEL] + por[SIT_SEM_ABSORTANCIA]
        if pendentes:
            partes = []
            if por[SIT_MATERIAL_NAO_IDENTIFICAVEL]:
                partes.append(f"material não identificável em "
                              f"{nomes(por[SIT_MATERIAL_NAO_IDENTIFICAVEL])} — sem "
                              "material com nome não se sabe se é exceção da Portaria")
            if por[SIT_SEM_ABSORTANCIA]:
                partes.append(f"'{self.propriedade}' ausente em "
                              f"{nomes(por[SIT_SEM_ABSORTANCIA])}")
            return ("nao_avaliavel", motivos.INFORMACAO_AUSENTE,
                    (f"{len(pendentes)} de {n} covering(s) sem informação para "
                    f"concluir: {'; '.join(partes)}. Nunca conforme por omissão."))
        if not por[SIT_ATENDE]:
            excecoes = "; ".join(f"{c['nome']} — {c['rotulo_excecao']} "
                                 f"('{c['material_da_excecao']}')"
                                 for c in por[SIT_EXCECAO])
            return ("nao_avaliavel", motivos.NAO_APLICAVEL,
                    (f"Todo covering de {self.familia} é exceção da Portaria: {excecoes}. "
                    "O limite de absortância não se aplica."))
        ressalva = (f" ({len(por[SIT_EXCECAO])} covering(s) excetuado(s) pela "
                    "Portaria, fora da comparação)" if por[SIT_EXCECAO] else "")
        return ("conforme", "",
                (f"{len(por[SIT_ATENDE])} covering(s) de {self.familia} com absortância "
                f"<= {self.limite}{ressalva}: {nomes(por[SIT_ATENDE])}."))


def _zona_dict(zona: Any) -> dict:
    if zona is None:
        return {"classe": "", "fonte": "", "herdada": False, "origens": []}
    return {
        "classe": str(getattr(zona, "classe", zona)),
        "fonte": str(getattr(zona, "fonte", "") or ""),
        "herdada": bool(getattr(zona, "herdada", False)),
        "origens": list(getattr(zona, "origens", ()) or ()),
    }


def _rotulo(estado_value: str) -> str:
    return {"conforme": "CONFORME", "nao_conforme": "NÃO CONFORME"}.get(
        estado_value, "sem veredito")
