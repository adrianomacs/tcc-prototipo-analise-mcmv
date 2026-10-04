"""Leitura do modelo IFC com IfcOpenShell.

Abre o arquivo e oferece acessos basicos a geometria, quantidades, propriedades
e ao schema. As importacoes do ifcopenshell ficam dentro das funcoes para que o
restante do protótipo possa ser inspecionado sem a biblioteca instalada.
"""

from __future__ import annotations

from typing import Any


def abrir(caminho_ifc: str) -> Any:
    """Abre um arquivo IFC e devolve o objeto ifcopenshell.file."""
    import ifcopenshell

    return ifcopenshell.open(caminho_ifc)


def schema(modelo: Any) -> str:
    """Devolve o identificador do schema do modelo (ex.: 'IFC2X3', 'IFC4').

    Vazio se indisponivel. Usado para condicionar checagens que dependem de
    entidades introduzidas apenas no IFC4+ (ex.: IfcProjectedCRS).
    """
    return (getattr(modelo, "schema", "") or "").upper()


def suporta_ifc4(modelo: Any) -> bool:
    """True se o schema do modelo for IFC4 ou superior (ou desconhecido)."""
    s = schema(modelo)
    return (s == "") or s.startswith("IFC4")


def propriedades_do_elemento(elemento: Any) -> dict[str, Any]:
    """Achata os Psets/Qsets de um elemento em um dicionario simples."""
    import ifcopenshell.util.element as ue

    psets = ue.get_psets(elemento)
    achatado: dict[str, Any] = {}
    for props in psets.values():
        for chave, valor in props.items():
            if chave != "id":
                achatado[chave] = valor
    return achatado


def propriedade_de_pset(elemento: Any, pset: str, *chaves: str) -> tuple[Any, str]:
    """``(valor, "Pset.Chave")`` da primeira chave preenchida, ou ``(None, "")``.

    Complementa :func:`propriedades_do_elemento`, que **achata** todos os Psets
    num dicionário só. O achatamento serve para quem quer o valor e não se
    importa com a origem (é o caso da área), mas não serve quando a origem é
    parte da resposta: property set nomeado é um fato diferente de atributo da
    entidade, e a precedência existe porque essa diferença precisa aparecer na
    procedência. Achatado, `LandTitleID` e um homônimo de outro pset seriam
    indistinguíveis.

    Devolve a fonte junto do valor **de propósito**: quem chama não deveria ter
    de redescobrir de onde veio o que acabou de receber — é assim que procedência
    e valor se separam em silêncio quando um dos dois muda.
    """
    try:
        import ifcopenshell.util.element as ue

        props = (ue.get_psets(elemento) or {}).get(pset) or {}
    except Exception:                                    # noqa: BLE001
        return None, ""
    for chave in chaves:
        valor = props.get(chave)
        if valor not in (None, ""):
            return valor, f"{pset}.{chave}"
    return None, ""


def elementos_por_tipo(modelo: Any, tipo_ifc: str) -> list[Any]:
    """Devolve todos os elementos de um tipo IFC, sem quebrar se o tipo nao existe."""
    try:
        return list(modelo.by_type(tipo_ifc))
    except Exception:
        return []


def materiais_do_elemento(elemento: Any) -> list[str]:
    """Nomes dos materiais associados ao elemento (``IfcRelAssociatesMaterial``),
    diretamente ou pelo tipo, com conjuntos e camadas expandidos.

    Cobre as formas que o IFC admite — ``IfcMaterial``, ``IfcMaterialLayerSet``
    (e ``…Usage``), ``IfcMaterialConstituentSet``, ``IfcMaterialProfileSet`` (e
    ``…Usage``) e ``IfcMaterialList`` — e devolve só os NOMES, que é o que a
    correspondência nominal das exceções de absortância consome (DN-01;
    ``core/dominio/conhecimento/materiais_cobertura.py``). Lista vazia = nenhum
    material associado; nome vazio dentro da lista = material sem nome. Quem
    chama distingue os dois — aqui não se inventa nome nem se descarta entrada.
    """
    import ifcopenshell.util.element as ue

    try:
        material = ue.get_material(elemento, should_inherit=True)
    except Exception:
        material = None
    return _nomes_de_material(material)


def _nomes_de_material(material: Any) -> list[str]:
    if material is None:
        return []

    def e(tipo: str) -> bool:
        is_a = getattr(material, "is_a", None)
        return callable(is_a) and bool(is_a(tipo))

    if e("IfcMaterial"):
        return [str(getattr(material, "Name", "") or "")]
    if e("IfcMaterialLayerSetUsage"):
        return _nomes_de_material(getattr(material, "ForLayerSet", None))
    if e("IfcMaterialProfileSetUsage"):
        return _nomes_de_material(getattr(material, "ForProfileSet", None))
    if e("IfcMaterialLayerSet"):
        itens = getattr(material, "MaterialLayers", None) or []
    elif e("IfcMaterialConstituentSet"):
        itens = getattr(material, "MaterialConstituents", None) or []
    elif e("IfcMaterialProfileSet"):
        itens = getattr(material, "MaterialProfiles", None) or []
    elif e("IfcMaterialList"):
        return [n for m in (getattr(material, "Materials", None) or [])
                for n in _nomes_de_material(m)]
    else:
        return []
    return [n for item in itens
            for n in _nomes_de_material(getattr(item, "Material", None))]

# ---------------------------------------------------------------------------
# Abertura defensiva (schema não suportado pela versão do IfcOpenShell)
# ---------------------------------------------------------------------------
# Motivo concreto (2026-09-10): ``UT_GeoRef_1.ifc`` declara IFC4X3_RC2 — um
# *release candidate* que o IfcOpenShell 0.8.5 recusa com ``SchemaError``. Sem
# tratamento, o usuário recebe um traceback (e mais um "Exception ignored" do
# ``file.__del__`` do próprio IfcOpenShell, que é ruído dele, não do projeto).
# Um protótipo que se propõe a dizer o que falta no modelo não pode falhar
# assim: o schema não suportado é um DIAGNÓSTICO de insumo, não um crash.

_MAX_HEADER = 8192


def schema_declarado(caminho_ifc: str) -> str:
    """Schema declarado no header do arquivo (ex.: 'IFC4X3_RC2'), ou ''.

    Lê o texto do header em vez de abrir o modelo: é o único jeito de nomear o
    schema exatamente quando o IfcOpenShell se recusa a abri-lo.
    """
    import re

    try:
        with open(caminho_ifc, "r", encoding="utf-8", errors="ignore") as f:
            cabecalho = f.read(_MAX_HEADER)
    except OSError:
        return ""
    achado = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", cabecalho)
    return achado.group(1).strip() if achado else ""


# Schemas IFC publicados. A lista serve para RECONHECER um candidato a versão
# pelo header (sufixo _RC, ou nome fora do conjunto) e emitir a mensagem certa
# mesmo quando o motivo da falha vem embrulhado de outra forma pela biblioteca.
SCHEMAS_PUBLICADOS = frozenset({
    "IFC2X2", "IFC2X3", "IFC4", "IFC4X1", "IFC4X2",
    "IFC4X3", "IFC4X3_ADD1", "IFC4X3_ADD2", "IFC4X3_TC1",
})


def schema_suportavel(schema: str) -> bool:
    """False para candidato a versão (ex.: IFC4X3_RC2) ou schema desconhecido."""
    s = (schema or "").strip().upper()
    return bool(s) and "_RC" not in s and s in SCHEMAS_PUBLICADOS


def abrir_seguro(caminho_ifc: str) -> tuple[Any, str]:
    """``(modelo, erro)`` — nunca levanta. ``erro`` vazio significa sucesso.

    O schema é avaliado pelo **header**, antes de tentar abrir: é o que permite
    nomear o problema com precisão (e dar a mesma resposta em qualquer
    ambiente, com ou sem IfcOpenShell instalado).
    """
    # O schema é propriedade do ARQUIVO: avaliá-lo antes de importar a
    # biblioteca faz a resposta ser a mesma em qualquer ambiente — e é a
    # informação que o usuário precisa, independente do que está instalado.
    #
    # O header VETA apenas o que ele identifica positivamente como não
    # publicável (sufixo `_RC`, ou um nome fora do conjunto). Header ausente ou
    # ilegível NÃO é veto: a autoridade sobre "este arquivo abre?" é a
    # biblioteca, e recusar sem tentar rejeitaria um arquivo válido cujo header
    # a regex não alcançou (encoding incomum, cabeçalho acima de 8 KB). O
    # pipeline inteiro — e com ele as telas de Georreferenciamento e Programa de
    # necessidades — entra por esta porta, então um veto largo custaria caro.
    schema = schema_declarado(caminho_ifc)
    if schema and not schema_suportavel(schema):
        return None, _erro_de_schema(schema, _versao_ifcopenshell())

    try:
        import ifcopenshell
    except Exception as exc:
        return None, f"IfcOpenShell indisponível no ambiente ({exc})."

    versao = getattr(ifcopenshell, "version", "?")
    try:
        return ifcopenshell.open(caminho_ifc), ""
    except Exception as exc:
        nome = type(exc).__name__
        if nome == "SchemaError" or "schema" in str(exc).lower():
            return None, _erro_de_schema(schema, versao)
        return None, f"Falha ao abrir o IFC ({nome}: {exc})."


def _versao_ifcopenshell() -> str:
    try:
        import ifcopenshell
        return str(getattr(ifcopenshell, "version", "?"))
    except Exception:
        return "não instalado"


# ---------------------------------------------------------------------------
# Premissa do trabalho: georreferenciamento estruturado exige IFC4
# ---------------------------------------------------------------------------
# Decisão de escopo. Não é limitação descoberta, é **escopo cravado**, e a
# diferença importa para quem lê: a possibilidade de georreferenciar IFC2X3
# por property sets de extensão (``ePSet_ProjectedCRS`` / ``ePSet_MapConversion``)
# foi levantada, verificada no acervo e deliberadamente deixada de fora.
#
# Os textos moram aqui, junto do predicado, por um motivo prático já aprendido
# neste projeto: legenda digitada na tela envelhece em silêncio quando o critério
# muda. Quem exibe importa daqui.

def georreferencia_estruturada(schema: str) -> bool:
    """True se o SCHEMA comporta ``IfcProjectedCRS`` + ``IfcMapConversion``.

    São as entidades do LoGeoRef 50, introduzidas no IFC4. Schema vazio (modelo
    não carregado, ou biblioteca que não informa) não é tratado como reprovação:
    quem decide sobre um modelo ausente é a camada que o pediu.
    """
    s = (schema or "").strip().upper()
    return (s == "") or s.startswith("IFC4")


PREMISSA_IFC4 = (
    "Este trabalho adota o **IFC4** como premissa para o georreferenciamento: "
    "as entidades que o sustentam — `IfcProjectedCRS` e `IfcMapConversion`, o "
    "LoGeoRef 50 — existem apenas a partir do IFC4."
)

PREMISSA_IFC4_CONSEQUENCIA = (
    "Deste modelo **não é possível derivar a poligonal** do terreno; no máximo o "
    "**centro**, e apenas se o IfcSite trouxer `RefLatitude`/`RefLongitude`. As "
    "verificações que exigem a poligonal sairão NÃO AVALIÁVEIS, e o EMP-001 sairá "
    "não conforme **por limitação do schema** — não por defeito do projeto."
)

PREMISSA_IFC4_ALTERNATIVA_RECUSADA = (
    "Existe convenção de mercado para georreferenciar IFC2X3 por *property sets* "
    "(`ePSet_ProjectedCRS` / `ePSet_MapConversion`). Ela foi levantada e **deixada "
    "fora do escopo** deste trabalho: property set de extensão não é entidade do "
    "schema, e o veredito passaria a depender de convenção não normalizada."
)


def _erro_de_schema(schema: str, versao: str) -> str:
    return (f"O arquivo declara o schema **{schema or 'desconhecido'}**, que a "
            f"versão instalada do IfcOpenShell ({versao}) não suporta. Exporte "
            "o modelo em **IFC4** (ou IFC4X3_ADD2) e envie de novo — candidatos "
            "a versão (sufixo `_RC`) não são schemas publicados e nenhuma "
            "ferramenta os lê de forma confiável.")
