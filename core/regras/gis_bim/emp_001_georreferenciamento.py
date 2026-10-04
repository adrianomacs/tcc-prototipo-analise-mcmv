"""EMP-001 — Modelo georreferenciado (UTM / SIRGAS 2000) + localização declarada.

Avalia o georreferenciamento do modelo em dois aspectos, dentro do MESMO
requisito (mantém a taxonomia da Portaria — sem granular ".1" criada pelo
protótipo):

1. **Estrutura (LoGeoRef)** — escala de Clemen & Görne (2019). A barra de
   conformidade é fixa no nível 50 (IfcProjectedCRS + IfcMapConversion, com
   CRS consistente em SIRGAS 2000 / UTM): abaixo disso o requisito é não
   conforme, reportando o nível atingido e as lacunas.
2. **Posicionamento (confronto com a localização declarada)** — quando o
   usuário declara UF/município, a âncora geográfica do modelo é confrontada
   com a malha municipal oficial (IBGE, sob demanda + cache):
     * âncora DENTRO do município  -> mantém a conformidade;
     * âncora FORA do município    -> NÃO CONFORME (georreferenciamento
       presente, porém posicionamento divergente da localização declarada);
     * confronto não avaliável (sem malha/rede ou âncora não derivável) ->
       CONFORME COM RESSALVA (o núcleo normativo foi atendido; a ressalva
       fica explícita na mensagem e no detalhe).

3. **Aviso de posicionamento (âncora × poligonal do terreno)** — ADR-032. A
   âncora (origem do ``IfcMapConversion``) é confrontada com a poligonal do
   ``Terreno`` declarado, no CRS métrico da poligonal, com tolerância de
   ``TOLERANCIA_POSICIONAMENTO_M``. É **aviso**: vai para o detalhe
   (``posicionamento_terreno``) e para a mensagem, e **nunca** muda o
   veredito. O município reprova porque a escala é de quilômetros e o erro é
   inequívoco; a poligonal só avisa porque a escala é de metros, depende de
   tolerância e a âncora não é o modelo — mede-se "referência compatível com
   o terreno", não "modelo contido". Para ``edificacao_isolada`` o aviso é
   "não aplicável": a tipologia não tem posição própria (ADR-023).

Cumpre papel duplo (Passo 3): é a verificação do EMP-001 e a porta da trilha
espacial — regras GIS e GIS+BIM dependem deste requisito estar conforme.

A natureza do modelo declarada pelo usuário não altera a barra; apenas adapta a
narrativa do diagnóstico. Ela vem do **contêiner âncora da execução**
(``core.dominio.ancora.conteiner_da_execucao``), e não de um campo fixo do
empreendimento: decisão do ADR-023 — com o contêiner
podendo pertencer ao ``Terreno``, a uma unidade tipo ou a uma edificação, a
fonte única e honesta é o que esta análise de fato abriu. Por isso o EMP-001 **não
muda de fonte** e o veredito do estudo de caso é preservado.
"""

from __future__ import annotations

from core.dominio import ancora
from core.dominio.conhecimento.georreferenciamento import LOGEOREF_ALVO
from core.dominio.contratos.regra import Contexto, Dominio, Regra, Verbo
from core.dominio.vocabulario import declaracoes as dec
from core.dominio.vocabulario import motivos
from core.regras.registro import registrar

# --- Aviso de posicionamento (ADR-032) --------------------------------------
# 5 m: absorve a âncora sobre um vértice da divisa (a gleba autoral ancora em
# M1, distância 0) e a divergência centimétrica entre o DWG de implantação e a
# tabela do memorial; pega a translação de 18,64 m do E1 da primeira rodada,
# que levou a âncora a 11,73 m fora da gleba. Não é parâmetro
# normativo — a Portaria não fala de âncora —, por isso não mora em
# ``parametro``.
TOLERANCIA_POSICIONAMENTO_M = 5.0

POS_DENTRO = "dentro"
POS_FORA = "fora"
POS_NAO_AVALIADO = "nao_avaliado"
POS_NAO_APLICAVEL = "nao_aplicavel"

ROTULO_POSICIONAMENTO = {
    POS_DENTRO: "referência compatível com o terreno",
    POS_FORA: "referência fora do terreno declarado",
    POS_NAO_AVALIADO: "não avaliado",
    POS_NAO_APLICAVEL: "não aplicável à natureza declarada",
}

_NATUREZAS_POSICIONAVEIS = ("terreno", "terreno_com_edificacoes")

JUSTIFICATIVA_POSICIONAMENTO = (
    "O confronto com o município reprova e o confronto com a poligonal só "
    "avisa: o município está na escala de quilômetros e o erro é inequívoco; "
    "a poligonal está na escala de metros, depende de tolerância, e a âncora "
    "(origem do IfcMapConversion) não é o modelo — pode cair legitimamente "
    "sobre a divisa ou fora do lote. O aviso mede se a referência é compatível "
    "com o terreno, não se o modelo está contido nele, nem se a referência "
    "está correta: um erro que desloque a âncora para dentro passa sem aviso.")

# Nota interpretativa por tipo de modelo declarado (apenas narrativa).
_NOTA_TIPO = {
    "terreno": "Modelo de terreno: o georreferenciamento e a referencia espacial "
               "do empreendimento; o nivel 50 e esperado.",
    "edificacao_isolada": "Edificacao isolada: modelos assim costumam vir em "
               "coordenadas locais; sem o nivel 50, nao habilitam as checagens espaciais.",
    "terreno_com_edificacoes": "Modelo federado: o referencial deve provir do terreno "
               "e ser compartilhado pela edificacao.",
}


@registrar
class EMP001(Regra):
    id = "EMP-001"
    dominio = Dominio.GIS_BIM
    descricao = "Modelo georreferenciado em UTM / SIRGAS 2000 (LoGeoRef 50)"
    depende_de = []
    ids_spec = None  # checagem estrutural do IFC; nao depende de propriedade nominal
    alvo = "IfcProject / IfcSite"
    verbo = Verbo.ATRIBUTO
    parametro = {"logeoref_alvo": LOGEOREF_ALVO}
    insumos = []  # le o georreferenciamento do proprio IFC; nao exige upload extra
    usa_visualizacao = True  # relatorio exibe o modelo posicionado no globo

    def checar(self, ctx: Contexto):
        if ctx.modelo_ifc is None:
            return self.nao_avaliavel(
                motivo=motivos.INSUMO_DO_PROPONENTE_AUSENTE,
                mensagem="Modelo IFC nao carregado; nao avaliavel.")

        # O LoGeoRef é calculado na ingestão, pela composição, ao lado do CRS
        # (ADR-036): a verificação por redundância faz parte da preparação do
        # modelo, e a regra só julga o diagnóstico com o alvo do parâmetro.
        diag = ctx.georref.get("logeoref")
        if diag is None:
            erro = ctx.georref.get("logeoref_erro") or (
                "diagnóstico LoGeoRef não calculado na ingestão")
            return self.nao_avaliavel(motivo=motivos.ERRO_DE_EXECUCAO,
                                      mensagem=f"Erro ao executar a checagem: {erro}")
        conteiner = ancora.conteiner_da_execucao(ctx)
        tipo_modelo = conteiner.natureza if conteiner is not None else ""
        nota = _NOTA_TIPO.get(tipo_modelo, "")

        detalhe = diag.to_dict()
        try:
            detalhe["localizacao"] = (
                ctx.leitura_modelo.consistencia_localizacao().to_dict())
        except Exception:
            pass

        try:
            detalhe["procedencia"] = (
                ctx.leitura_modelo.procedencia_georreferenciamento())
        except Exception:
            pass

        # Confronto âncora × município declarado (quando houver declaração).
        cross = _confrontar_localizacao(ctx)
        if cross is not None:
            detalhe["localizacao_declarada"] = cross

        # Aviso âncora × poligonal (ADR-032): calculado sempre, antes de
        # qualquer ramo de veredito, e nunca lido por eles.
        posicao = _confrontar_terreno(ctx, tipo_modelo)
        detalhe["posicionamento_terreno"] = posicao
        nota = _juntar(_frase_posicionamento(posicao), nota)

        base = {
            "valor_esperado": "LoGeoRef 50",
            "valor_encontrado": f"LoGeoRef {diag.nivel}",
            "elementos": diag.elementos,
            "detalhe": detalhe,
        }

        if not diag.atinge_alvo:
            lacunas = "; ".join(diag.lacunas) if diag.lacunas else "informacoes de georreferenciamento"
            msg = f"Nivel atingido: {diag.nivel} (alvo 50). Faltam: {lacunas}."
            return self.nao_conforme(mensagem=_juntar(msg, nota), **base)

        msg = f"Georreferenciamento completo (nivel 50). {diag.consistencia_msg}"

        if cross is None:  # sem declaração de localização: comportamento original
            return self.conforme(mensagem=_juntar(msg, nota), **base)

        if cross["avaliado"] and cross["dentro"] is False:
            msg = (f"Georreferenciamento estruturado (nivel 50), porem a ancora do "
                   f"modelo esta FORA dos limites de {cross['municipio']}/{cross['uf']} "
                   f"declarados. {cross['mensagem']}")
            return self.nao_conforme(mensagem=_juntar(msg, nota), **base)

        if cross["avaliado"]:  # dentro do município declarado
            msg += (f" Posicionamento confirmado dentro de "
                    f"{cross['municipio']}/{cross['uf']} (malha IBGE).")
            return self.conforme(mensagem=_juntar(msg, nota), **base)

        # Confronto não avaliável -> conforme com ressalva explícita.
        msg += (f" RESSALVA: confronto com a localizacao declarada "
                f"({cross['municipio']}/{cross['uf']}) nao avaliado — {cross['motivo']}")
        return self.conforme(mensagem=_juntar(msg, nota), **base)


def _confrontar_localizacao(ctx: Contexto) -> dict | None:
    """Confronta a âncora do modelo com o município declarado.

    Devolve None quando não há declaração de município; caso contrário, um
    dicionário com ``avaliado`` (bool), ``dentro`` (bool | None), ``motivo``
    (quando não avaliado) e os dados declarados/derivados para o relatório.
    """
    declaracoes = ctx.empreendimento.declaracoes or {}
    codigo = str(declaracoes.get(dec.MUNICIPIO_IBGE) or "").strip()
    if not codigo:
        return None

    resultado = {
        "uf": declaracoes.get(dec.UF, ""),
        "municipio": declaracoes.get(dec.MUNICIPIO, ""),
        "municipio_ibge": codigo,
        "avaliado": False,
        "dentro": None,
        "ancora": None,
        "fonte": "",
        "mensagem": "",
        "motivo": "",
    }

    try:
        anc = ctx.leitura_modelo.derivar_ancora()
    except Exception as exc:
        resultado["motivo"] = f"falha ao derivar a ancora ({exc!r})."
        return resultado

    if not anc.disponivel:
        resultado["motivo"] = (f"ancora geografica nao derivavel do modelo "
                               f"({anc.mensagem or 'sem origem reprojetavel'}).")
        return resultado

    resultado["ancora"] = {"lat": anc.lat, "lon": anc.lon, "modo": anc.modo}

    try:
        res = ctx.fontes_territoriais.conferir_ponto_no_municipio(
            codigo, anc.lat, anc.lon)
    except Exception as exc:
        resultado["motivo"] = f"falha no confronto com a malha ({exc!r})."
        return resultado

    resultado["fonte"] = res.fonte
    resultado["mensagem"] = res.mensagem
    if res.dentro is None:
        resultado["motivo"] = res.mensagem or "malha municipal indisponivel."
        return resultado

    resultado["avaliado"] = True
    resultado["dentro"] = bool(res.dentro)
    return resultado


def _confrontar_terreno(ctx: Contexto, natureza: str) -> dict:
    """Confronta a âncora do modelo com a poligonal do terreno declarado.

    Aviso, não veredito (ADR-032). Estados: ``dentro`` (distância à poligonal
    até a tolerância — dentro, na borda ou fora por menos que ela), ``fora``,
    ``nao_avaliado`` (sempre com ``motivo``) e ``nao_aplicavel``
    (``edificacao_isolada``: a distância, quando mensurável, fica só como
    ``distancia_informativa_m``). A medida é no CRS métrico da poligonal, que
    é o do ``Terreno``; a âncora chega em WGS 84 e é reprojetada para ele.
    """
    resultado = {
        "estado": POS_NAO_AVALIADO,
        "rotulo": ROTULO_POSICIONAMENTO[POS_NAO_AVALIADO],
        "natureza": natureza,
        "tolerancia_m": TOLERANCIA_POSICIONAMENTO_M,
        "distancia_m": None,
        "distancia_informativa_m": None,
        "crs": "",
        "ancora": None,
        "terreno": None,
        "motivo": "",
        "mensagem": "",
        "justificativa": JUSTIFICATIVA_POSICIONAMENTO,
    }

    def _fechar(estado: str, mensagem: str, motivo: str = "") -> dict:
        resultado["estado"] = estado
        resultado["rotulo"] = ROTULO_POSICIONAMENTO[estado]
        resultado["mensagem"] = mensagem
        resultado["motivo"] = motivo
        return resultado

    isolada = natureza == "edificacao_isolada"
    if not isolada and natureza not in _NATUREZAS_POSICIONAVEIS:
        return _fechar(POS_NAO_AVALIADO, "",
                       "natureza do modelo não declarada.")

    terreno = ctx.empreendimento.terreno
    medida = _medir(ctx, terreno, resultado)

    if isolada:
        texto = ("a tipologia isolada não tem posição própria; a âncora "
                 "vem do modelo de implantação")
        if medida is not None:
            resultado["distancia_informativa_m"] = medida
            texto += (f" — distância informativa da âncora à poligonal: "
                      f"{_metros(medida)}")
        return _fechar(POS_NAO_APLICAVEL, texto + ".")

    if medida is None:
        return _fechar(POS_NAO_AVALIADO, "", resultado["motivo"])

    resultado["distancia_m"] = medida
    tol = _metros(TOLERANCIA_POSICIONAMENTO_M)
    if medida <= TOLERANCIA_POSICIONAMENTO_M:
        onde = ("dentro da poligonal ou sobre a divisa" if medida == 0.0
                else f"a {_metros(medida)} da poligonal")
        return _fechar(POS_DENTRO, f"âncora {onde} (tolerância {tol}).")
    return _fechar(POS_FORA, f"âncora a {_metros(medida)} da poligonal do "
                             f"terreno declarado, além da tolerância de {tol}.")


def _medir(ctx: Contexto, terreno, resultado: dict) -> float | None:
    """Distância (m) da âncora precisa à poligonal, ou None com ``motivo``."""
    if terreno is None:
        resultado["motivo"] = "nenhum terreno declarado."
        return None
    if not terreno.tem_poligonal:
        resultado["motivo"] = "o terreno declarado não tem poligonal (só o centro)."
        return None
    resultado["terreno"] = {"origem": terreno.origem, "precisao": terreno.precisao}
    resultado["crs"] = terreno.crs_metrico

    try:
        anc = ctx.leitura_modelo.derivar_ancora()
    except Exception as exc:
        resultado["motivo"] = f"falha ao derivar a âncora ({exc!r})."
        return None
    if anc.disponivel:
        resultado["ancora"] = {"lat": anc.lat, "lon": anc.lon, "modo": anc.modo}
    if anc.modo != "preciso" or not anc.disponivel:
        resultado["motivo"] = ("âncora sem IfcMapConversion (modo "
                               f"{anc.modo}): a lat/long do IfcSite não é a "
                               "origem das coordenadas compartilhadas.")
        return None

    try:
        from shapely.geometry import Point

        from core.dominio import geometria
        x, y = geometria.reprojetar_ponto(anc.lon, anc.lat, geometria.CRS_GEOGRAFICO,
                                          terreno.crs_metrico)
        distancia = float(terreno.poligonal.distance(Point(x, y)))
    except Exception as exc:
        resultado["motivo"] = f"falha na medida no CRS da poligonal ({exc!r})."
        return None
    if distancia != distancia or distancia == float("inf"):  # NaN / inf
        resultado["motivo"] = "âncora não reprojetável para o CRS da poligonal."
        return None
    return round(distancia, 2)


def _frase_posicionamento(pos: dict) -> str:
    """A frase do aviso que entra na mensagem do EMP-001 (ADR-032)."""
    estado = pos["estado"]
    if estado == POS_FORA:
        return f"AVISO de posicionamento (não altera o veredito): {pos['mensagem']}"
    if estado == POS_DENTRO:
        return f"Posicionamento: referência compatível com o terreno — {pos['mensagem']}"
    if estado == POS_NAO_APLICAVEL:
        return "Posicionamento no terreno: não aplicável à natureza declarada."
    return f"Posicionamento no terreno: não avaliado — {pos['motivo']}"


def _metros(valor: float) -> str:
    from core.dominio.terreno import formatar_numero
    return f"{formatar_numero(valor)} m"


def _juntar(msg: str, nota: str) -> str:
    return f"{msg} {nota}".strip() if nota else msg
