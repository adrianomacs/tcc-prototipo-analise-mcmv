"""Conversão de geometria IFC -> glTF/GLB (passo 1 da visualização).

Usa o serializador glTF do IfcOpenShell para gerar um GLB binário a partir do
modelo IFC. Cada elemento vira um nó nomeado pelo seu GlobalId (preparando o
destaque por elemento — Nível 2). As coordenadas são as do mundo local do
modelo; o posicionamento geográfico é tratado adiante (passo 2 da visualização, em ``georref/ancora.py``).

Filtragem de tipos (importante): é possível EXCLUIR ou INCLUIR categorias IFC
na exportação (ex.: omitir IfcSpace, que polui a cena como volume translúcido,
ou aberturas/anotações). Essa filtragem ocorre apenas na geração do GLB — o
arquivo IFC NÃO é modificado, preservando estrutura e semântica para as
checagens. Os tipos excluídos sequer têm a geometria calculada, o que também
acelera modelos pesados.

Uso:
    python -m core.infra.exportadores.gltf entradas/ifc/modelo.ifc artefatos/modelo.glb
    python -m core.infra.exportadores.gltf in.ifc out.glb --excluir IfcSpace IfcOpeningElement
    python -m core.infra.exportadores.gltf in.ifc out.glb --limpo
"""

from __future__ import annotations

import gc
import os
from collections.abc import Iterable

# Preset de "visualização limpa": categorias que normalmente só poluem a cena
# (volumes de espaços, aberturas/vazios, anotações e grids) e não correspondem
# a geometria construída relevante para inspeção visual.
PRESET_VISUALIZACAO_LIMPA = ("IfcSpace", "IfcOpeningElement", "IfcAnnotation",
                             "IfcGrid", "IfcGridAxis")


def exportar(caminho_ifc: str, destino_glb: str, *, world_coords: bool = True,
             usar_guids: bool = True, y_up: bool = True,
             excluir_tipos: Iterable[str] | None = None,
             incluir_tipos: Iterable[str] | None = None) -> str:
    """Converte um arquivo IFC em GLB. Retorna o caminho do GLB gerado."""
    import ifcopenshell

    modelo = ifcopenshell.open(caminho_ifc)
    return exportar_modelo(modelo, destino_glb, world_coords=world_coords,
                           usar_guids=usar_guids, y_up=y_up,
                           excluir_tipos=excluir_tipos, incluir_tipos=incluir_tipos)


def exportar_modelo(modelo, destino_glb: str, *, world_coords: bool = True,
                    usar_guids: bool = True, y_up: bool = True,
                    excluir_tipos: Iterable[str] | None = None,
                    incluir_tipos: Iterable[str] | None = None) -> str:
    """Converte um objeto ifcopenshell.file (já aberto) em GLB.

    ``incluir_tipos`` e ``excluir_tipos`` são mutuamente exclusivos; se ambos
    vierem, ``incluir_tipos`` prevalece. O IFC não é alterado em nenhum caso.
    """
    from ifcopenshell import geom

    if incluir_tipos and excluir_tipos:
        excluir_tipos = None  # include tem prioridade

    pasta = os.path.dirname(os.path.abspath(destino_glb))
    os.makedirs(pasta, exist_ok=True)

    settings = geom.settings()
    if world_coords:
        _set(settings, "use-world-coords", True)

    ser = geom.serializer_settings()
    if usar_guids:
        _set(ser, "use-element-guids", True)   # nó nomeado pelo GlobalId
    if y_up:
        _set(ser, "y-up", True)                # convenção glTF (consumida pelo CesiumJS)

    serializer = geom.serializers.gltf(destino_glb, settings, ser)
    serializer.setFile(modelo)
    try:
        serializer.setUnitNameAndMagnitude("METER", 1.0)
    except Exception:
        pass
    serializer.writeHeader()

    # Filtragem por tipo direto no iterador: a geometria dos tipos descartados
    # nem chega a ser calculada (sem tocar no IFC).
    kwargs = {}
    if incluir_tipos:
        kwargs["include"] = tuple(incluir_tipos)
    elif excluir_tipos:
        kwargs["exclude"] = tuple(excluir_tipos)

    it = geom.iterator(settings, modelo, **kwargs)
    n = 0
    if it.initialize():
        while True:
            serializer.write(it.get())
            n += 1
            if not it.next():
                break
    serializer.finalize()
    # Liberar o objeto C++ faz o flush final do arquivo (finalize sozinho não basta).
    del serializer
    gc.collect()

    if n == 0:
        raise ValueError(
            "Nenhuma geometria exportável após a filtragem. "
            "Revise incluir_tipos/excluir_tipos ou o conteúdo do modelo."
        )
    return destino_glb


def _set(cfg, nome: str, valor) -> None:
    """Aplica uma opção de settings ignorando nomes não suportados pela versão."""
    try:
        cfg.set(nome, valor)
    except Exception:
        pass


def _cli() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Converte IFC em GLB (glTF binário).")
    p.add_argument("ifc", help="Caminho do arquivo IFC de entrada.")
    p.add_argument("glb", help="Caminho do GLB de saída.")
    p.add_argument("--excluir", nargs="*", default=None, metavar="IfcTipo",
                   help="Tipos IFC a omitir da exportação (ex.: IfcSpace IfcOpeningElement).")
    p.add_argument("--incluir", nargs="*", default=None, metavar="IfcTipo",
                   help="Exporta SOMENTE estes tipos IFC.")
    p.add_argument("--limpo", action="store_true",
                   help=f"Aplica o preset de visualização limpa: {', '.join(PRESET_VISUALIZACAO_LIMPA)}.")
    args = p.parse_args()

    excluir = args.excluir
    if args.limpo and not args.incluir:
        excluir = list(PRESET_VISUALIZACAO_LIMPA) + list(args.excluir or [])

    destino = exportar(args.ifc, args.glb, excluir_tipos=excluir, incluir_tipos=args.incluir)
    print(f"GLB gerado: {destino} ({os.path.getsize(destino)} bytes)")


if __name__ == "__main__":
    _cli()
