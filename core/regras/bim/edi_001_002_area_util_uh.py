"""EDI-001 / EDI-002 — Área útil mínima da unidade habitacional (UH).

Par de requisitos dimensionais sobre a **área útil da UH**, aplicados conforme a
**tipologia** da unidade (ponto de validação casa × apartamento/casa sobreposta):

    EDI-001    Área útil mínima da UH tipo casa .............. ≥ 40,00 m²
    EDI-002    Área útil mínima de apartamento/casa sobreposta ≥ 41,50 m²
               com varanda **e** ≥ 40,00 m² de área principal

Ambos dependem do programa mínimo de necessidades (EDI-004): só faz sentido
medir a área útil quando os ambientes obrigatórios existem. Como a varanda
integra a área do apartamento, o EDI-002 depende também do EDI-004.1 (presença
de varanda na UH multifamiliar); o EDI-001 (casa) não depende da varanda.

Cadeia de dependências resultante::

    EDI-004  ──►  EDI-004.1  ──►  EDI-002   (trilha multifamiliar)
        └───────────────────────►  EDI-001   (trilha casa)

O EDI-002 tem **dois limites na mesma regra** (Anexo III, item 2.I.a.ii):
``area_util_min_m2`` sobre a soma de todos os ambientes e ``area_principal_min_m2``
sobre a soma sem os ambientes de categoria ``varanda``. Como o EDI-011 faz com
largura e área, um dispositivo com dois números segue sendo **uma** regra e um
ID (Leia-me da planilha, regra 3). Só o segundo limite existe se o parâmetro o
declara: o EDI-001 continua com o limite único.

``checar`` está implementado (compartilhado pelas duas classes via
``_checar_area_util``): seleção da regra por tipologia (via ``aplicabilidade``,
não por lógica em ``checar``) e cálculo da área útil consolidada, com teste
unitário isolado em ``tests/core/regras/bim/test_edi_001_002_area_util_uh.py``.
"""

from __future__ import annotations

from core.dominio import ancora
from core.dominio.contratos.regra import Contexto, Dominio, Regra, Verbo
from core.dominio.vocabulario import declaracoes as dec
from core.dominio.vocabulario import motivos
from core.regras.registro import registrar


def _tem_area(ambiente: dict) -> bool:
    area = ambiente.get("area_m2")
    return isinstance(area, (int, float)) and not isinstance(area, bool)


def _concluir_dois_limites(regra: Regra, base: dict, triagem, sem_area: list,
                           *, total, minimo, principal, principal_min,
                           ok_total, ok_principal):
    """Veredito do EDI-002: os dois limites do item 2.I.a.ii, cada um com a sua conta.

    A mensagem diz os dois números, também quando só um reprova, porque o
    proponente precisa ver que 41,50 m² com varanda não bastam se a varanda
    consumiu a área principal.
    """
    sinal_total = "≥" if ok_total else "<"
    sinal_principal = "≥" if ok_principal else "<"
    contas = (f"área útil com varanda {total:.2f} m² {sinal_total} {minimo:.2f} m²; "
              f"área principal, sem varanda, {principal:.2f} m² "
              f"{sinal_principal} {principal_min:.2f} m²")
    if ok_total and ok_principal:
        msg = contas[0].upper() + contas[1:] + "."
        if sem_area:
            msg += f" (obs.: {len(sem_area)} ambiente(s) sem área declarada, não somados)"
        return regra.conforme(mensagem=msg + triagem.nota(), **base)
    if sem_area:
        return regra.nao_avaliavel(
            motivo=motivos.INFORMACAO_AUSENTE,
            mensagem=(f"Áreas somadas: {contas}, porém {len(sem_area)} ambiente(s) "
                      f"sem área declarada — a soma pode estar subestimada; "
                      f"não avaliável.{triagem.nota()}"),
            **base)
    return regra.nao_conforme(
        mensagem=contas[0].upper() + contas[1:] + "." + triagem.nota(), **base)


def _checar_area_util(regra: Regra, ctx: Contexto):
    """Consolida a área útil (soma dos IfcSpace da população) e compara ao mínimo.

    Comum a EDI-001 (casa, 40 m²) e EDI-002 (apto/sobreposta, 41,5 m² com varanda
    e 40 m² de área principal). O cumprimento do programa mínimo é garantido pela
    dependência de EDI-004, então aqui apenas se soma e compara. Robustez: se há ambientes **sem área** e a soma
    disponível não alcança o mínimo, o resultado é NÃO AVALIÁVEL (a soma pode
    estar subestimada) em vez de reprovar indevidamente.

    Normalização por UH: o mínimo é multiplicado pelas UHs que o contêiner em
    análise **representa** (ADR-021) e comparado à soma total do modelo — mesma
    limitação assumida de ``programa_ambientes.avaliar_programa`` (valida em
    agregado, não separa espacialmente cada UH).

    O piso de 1 é da regra, não do contêiner: ``unidades_representadas`` vale 0
    quando não há entrega declarada, e multiplicar o parâmetro normativo por
    zero faria qualquer modelo atender a um mínimo de 0 m² — ausência de
    declaração viraria aprovação. Medir contra uma UH é o que o protótipo já
    fazia quando ninguém declarava o número, e é o conservador dos dois erros.

    Com o parâmetro ``area_principal_min_m2`` a regra confere um segundo limite:
    a **área principal** é a soma dos ambientes que não são varanda, e o
    ambiente sem área não entra em nenhuma das duas somas. A conclusão é a dos
    dois limites juntos. Atender aos dois é conforme, e isso vale mesmo com
    ambiente sem área, porque somar menos só pode errar contra o proponente. Falhar
    em qualquer um com ambiente sem área é não avaliável, pela mesma razão do
    limite único (a soma pode estar subestimada); falhar sem lacuna é não
    conforme. O mínimo principal é normalizado pelas UHs como o total (ADR-021).

    Os dois "não avaliável" desta função — nenhum ``IfcSpace`` e soma abaixo do
    mínimo com ambientes sem área — saem com ``informacao_ausente``
    (ADR-006/022): nos dois casos o modelo existe e o que falta é conteúdo que
    o requisito de informação (ADR-007) exigiria — ambientes, ou a quantidade
    de área deles.
    """
    if ctx.modelo_ifc is None:
        return regra.nao_avaliavel(motivo=motivos.INSUMO_DO_PROPONENTE_AUSENTE,
                                   mensagem="Modelo IFC não carregado.")

    from core.dominio.conhecimento import catalogo_ambientes as pa

    triagem = ctx.leitura_modelo.triar_ambientes()
    ambientes = triagem.populacao
    if not ambientes:
        return regra.nao_avaliavel(
            motivo=motivos.INFORMACAO_AUSENTE,
            mensagem="Nenhum ambiente (IfcSpace) encontrado no modelo." + triagem.nota())

    # A soma exclui os fantasmas do exportador. Eles repetem a área declarada
    # de um ambiente real e a contariam duas vezes (ADR-031).
    cons = pa.consolidar_areas(ambientes)
    cons["fora_da_populacao"] = triagem.fora
    minimo_unitario = regra.parametro["area_util_min_m2"]
    num_uhs = max(1, ancora.unidades_representadas(ctx))
    minimo = minimo_unitario * num_uhs
    total = cons["area_util_total"]
    sem_area = cons["ambientes_sem_area"]
    cons["area_min"] = minimo
    # A chave do diagnóstico segue chamando-se ``num_uhs``: é contrato do
    # relatório (``artefatos/relatorios/<chave>.json``) e do painel que o lê.
    # Renomeá-la é mexer em relatório e tela, não em regra.
    cons["num_uhs"] = num_uhs
    ok_total = total >= minimo

    principal_unitario = regra.parametro.get("area_principal_min_m2")
    dois_limites = principal_unitario is not None
    ok_principal = True
    if dois_limites:
        # Area principal = tudo o que não é varanda. A categoria vem da
        # classificação nominal já feita por ``consolidar_areas``.
        varanda = round(sum(
            float(a["area_m2"]) for a in cons["ambientes"]
            if a.get("categoria") == "varanda" and _tem_area(a)), 2)
        principal = round(total - varanda, 2)
        principal_min = principal_unitario * num_uhs
        ok_principal = principal >= principal_min
        cons.update({"area_varanda": varanda, "area_principal": principal,
                     "area_principal_min": principal_min,
                     "atende_area_util": ok_total,
                     "atende_area_principal": ok_principal})
    cons["atende"] = ok_total and ok_principal

    esperado = f"≥ {minimo:.2f} m²"
    if num_uhs > 1:
        esperado += f" ({num_uhs} UH × {minimo_unitario:.2f} m²)"
    encontrado = f"{total:.2f} m²"
    if dois_limites:
        esperado += f" com varanda e ≥ {principal_min:.2f} m² de área principal"
        if num_uhs > 1:
            esperado += f" ({num_uhs} UH × {principal_unitario:.2f} m²)"
        encontrado += f" com varanda, {principal:.2f} m² de área principal"

    base = {
        "valor_esperado": esperado,
        "valor_encontrado": encontrado,
        "unidade": "m2",
        "elementos": [a["global_id"] for a in cons["ambientes"] if a.get("global_id")],
        "detalhe": cons,
    }

    if dois_limites:
        return _concluir_dois_limites(
            regra, base, triagem, sem_area,
            total=total, minimo=minimo, principal=principal,
            principal_min=principal_min, ok_total=ok_total,
            ok_principal=ok_principal)

    if total >= minimo:
        msg = f"Área útil consolidada {total:.2f} m² ≥ {minimo:.2f} m²."
        if sem_area:
            msg += f" (obs.: {len(sem_area)} ambiente(s) sem área declarada, não somados)"
        return regra.conforme(mensagem=msg + triagem.nota(), **base)

    if sem_area:  # soma abaixo do mínimo, mas incompleta -> não avaliável
        return regra.nao_avaliavel(
            motivo=motivos.INFORMACAO_AUSENTE,
            mensagem=(f"Área somada {total:.2f} m² < {minimo:.2f} m², porém "
                      f"{len(sem_area)} ambiente(s) sem área declarada — a soma pode "
                      f"estar subestimada; não avaliável.{triagem.nota()}"),
            **base)

    return regra.nao_conforme(
        mensagem=(f"Área útil consolidada {total:.2f} m² < {minimo:.2f} m²."
                  + triagem.nota()),
        **base)


@registrar
class EDI001(Regra):
    id = "EDI-001"
    dominio = Dominio.BIM
    descricao = "Área útil mínima da UH tipo casa (≥ 40,00 m²)"
    depende_de = ["EDI-004"]              # programa de necessidades satisfeito
    ids_spec = None
    alvo = "IfcSpace (soma das áreas úteis da UH)"
    verbo = Verbo.DIMENSIONAL
    parametro = {"area_util_min_m2": 40.00}
    insumos = []
    usa_visualizacao = True  # relatorio exibe os ambientes no modelo
    # UH tipo casa: exige edificação e tipologia casa.
    aplicabilidade = {dec.TIPO_MODELO: dec.COM_EDIFICACAO,
                      dec.TIPOLOGIA: [dec.CASA]}

    def checar(self, ctx: Contexto):
        return _checar_area_util(self, ctx)


@registrar
class EDI002(Regra):
    id = "EDI-002"
    dominio = Dominio.BIM
    descricao = "Área útil mínima de apartamento / casa sobreposta (≥ 41,50 m²)"
    depende_de = ["EDI-004", "EDI-004.1"]  # programa-base + varanda (multifamiliar)
    ids_spec = None
    alvo = "IfcSpace (soma das áreas úteis da UH, incl. varanda)"
    verbo = Verbo.DIMENSIONAL
    parametro = {"area_util_min_m2": 41.50, "area_principal_min_m2": 40.00}
    insumos = []
    usa_visualizacao = True  # relatorio exibe os ambientes no modelo
    # UH multifamiliar: exige edificação e tipologia apartamento.
    aplicabilidade = {dec.TIPO_MODELO: dec.COM_EDIFICACAO,
                      dec.TIPOLOGIA: [dec.APARTAMENTO]}

    def checar(self, ctx: Contexto):
        return _checar_area_util(self, ctx)
