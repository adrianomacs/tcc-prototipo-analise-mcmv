"""Roda UM cenário da escada do Estrela I e mostra o perfil dos 14 requisitos.

Uso, da raiz do repositório (ou de qualquer lugar — o script se posiciona)::

    python scripts/rodar_cenario.py E0            # o caso base, sem rede
    python scripts/rodar_cenario.py E1 --ors      # com o OpenRouteService
    python scripts/rodar_cenario.py --listar      # os ids e o que existe

O que ele faz
-------------
1. Lê a lista fechada de cenários em ``config/cenarios_estrela_i.yaml`` (id,
   família, pai, papel do arquivo) e acha o arquivo do cenário pelo prefixo:
   ``entradas/ifc/estrela_i/<id>_*.ifc`` e ``entradas/gis/estrela_i/<id>_*.csv``.
   O que o cenário não traz em arquivo próprio ele herda do pai — o modelo BIM
   ou o terreno —, até chegar ao E0, o caso base, cujo arquivo é ``E0_asis.ifc``,
   achado como os outros (sem via especial).
2. Roda ``core.composicao.rodar`` cinco vezes — uma por checagem, como
   as cinco telas fazem — sobre as declarações do ``artefatos/empreendimento.json``
   CORRENTE, **sem alterá-lo**: o empreendimento entra num instantâneo em
   memória (mesmo ``id``/``versao``), com o contêiner do cenário pendurado na
   unidade tipo (ADR-021/023) e, se o cenário trouxer terreno próprio, com o
   terreno substituído. Os cinco relatórios saem em
   ``artefatos/cenarios/<id>/<chave>.json`` — os mesmos ``relatorio.json`` das
   telas (ADR-001), saída regerável e não versionada.
3. Imprime o perfil dos **14 requisitos da Portaria** —
   estado e motivo por requisito —, lado a lado com o E0 quando
   ``artefatos/cenarios/E0/`` já existe, marcando o que mudou. É o instrumento
   para conferir cada variante no dia em que a exporta.

Sem rede por padrão
-------------------
``--ors`` liga o provedor de rede (chave em ``ORS_API_KEY`` ou em
``.streamlit/secrets.toml``, cache em ``artefatos/cache_roteamento/``). Sem
ele, ENQ-010.1/011.1 saem por ``metrica_insuficiente`` (ADR-013) — no nível
do requisito, o perfil do E0 é o mesmo com ou sem rede (ENQ-009 reprova pela
linha reta; os pais ENQ-010/011 são não avaliáveis nos dois casos, DN-04),
e é por isso que o comando é determinístico por padrão. O cenário ``D4``
força a execução sem rede mesmo com ``--ors``: é o que ele isola.

Por que só o núcleo
-------------------
O script importa o núcleo pela API pública (``core.composicao`` e o
que ela já expõe) e nada de ``app/`` — o mesmo ponto de entrada da CLI do
pipeline. O que a interface faz antes de chamar o pipeline (pendurar o
contêiner no dono, fundir as declarações locais, filtrar os ids executáveis)
é reproduzido aqui em poucas linhas, citando o serviço correspondente, para
que um desvio entre o comando e a tela seja achado de leitura, não de
comportamento.
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import math
import os
import sys

# A raiz do projeto: o pipeline lê ``config/settings.yaml`` por caminho
# relativo (como a CLI dele), então o script trabalha sempre a partir dela.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import yaml  # noqa: E402

from core import composicao  # noqa: E402
from core.aplicacao import grupos as grupos_mod  # noqa: E402
from core.dominio import ancora  # noqa: E402
from core.dominio.modelo_bim import ModeloBIM  # noqa: E402
from core.dominio.vocabulario import declaracoes as dec  # noqa: E402
from core.dominio.vocabulario import motivos  # noqa: E402
from core.infra.persistencia import empreendimento_json  # noqa: E402
from core.regras.registro import regras_registradas  # noqa: E402

CONFIG_CENARIOS = os.path.join("config", "cenarios_estrela_i.yaml")
ARQUIVO_PERFIL = "perfil.json"

ABREVIATURA_ESTADO = {"conforme": "C", "nao_conforme": "NC",
                      "nao_avaliavel": "NA"}


# ---------------------------------------------------------------------------
# A lista fechada
# ---------------------------------------------------------------------------

def carregar_config(caminho: str = CONFIG_CENARIOS) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def cenarios(config: dict) -> dict[str, dict]:
    """``{id: cenário}`` na ordem do arquivo."""
    return {c["id"]: c for c in config.get("cenarios") or []}


def arquivo_do_cenario(config: dict, id_cenario: str, extensao: str) -> str | None:
    """O ``<id>_*.<ext>`` do cenário, ou ``None``; mais de um é erro de pasta."""
    pasta = config["pastas"]["ifc" if extensao == "ifc" else "gis"]
    achados = sorted(glob.glob(os.path.join(pasta, f"{id_cenario}_*.{extensao}")))
    if len(achados) > 1:
        raise SystemExit(f"Mais de um arquivo para {id_cenario} em {pasta}: "
                         f"{[os.path.basename(a) for a in achados]} — um por caso.")
    return achados[0] if achados else None


def modelo_de(config: dict, id_cenario: str) -> str | None:
    """O IFC que as checagens BIM leem neste cenário: o próprio, ou o do pai."""
    c = cenarios(config)[id_cenario]
    if c.get("arquivo") == "modelo":
        # Todo cenário, o E0 inclusive, acha o arquivo pelo prefixo na pasta
        # das variantes — sem via especial para o caso base (``E0_asis.ifc`` é o
        # arquivo, como os outros).
        return arquivo_do_cenario(config, id_cenario, "ifc")
    return modelo_de(config, c["pai"]) if c.get("pai") else None


def fonte_do_terreno(config: dict, id_cenario: str) -> tuple[str, str | None]:
    """``("csv", caminho)`` · ``("ifc", caminho)`` · ``("empreendimento", None)``.

    Um ``<id>_*.csv`` presente define o terreno do cenário, qualquer que seja
    a família (ADR-029); um ``<id>_*.ifc`` com papel ``terreno`` também. Sem
    nenhum dos dois, o terreno é o do pai — e, no E0, o do
    ``empreendimento.json`` (a poligonal do memorial confirmada na tela).
    """
    c = cenarios(config)[id_cenario]
    csv = arquivo_do_cenario(config, id_cenario, "csv")
    if csv:
        return "csv", csv
    if c.get("arquivo") == "terreno":
        ifc = arquivo_do_cenario(config, id_cenario, "ifc")
        return ("ifc", ifc) if ifc else ("ausente", None)
    if c.get("pai"):
        return fonte_do_terreno(config, c["pai"])
    return "empreendimento", None


def faltando(config: dict, id_cenario: str) -> str:
    """Por que o cenário NÃO pode rodar hoje — ``""`` quando pode.

    É a frase do ``pytest.skip`` do teste de integração e do erro do comando:
    a mesma nos dois, para que "pulou" e "recusou" digam a mesma coisa.
    """
    c = cenarios(config).get(id_cenario)
    if c is None:
        return f"id {id_cenario!r} não está em {CONFIG_CENARIOS}"
    papel = c.get("arquivo")
    if papel == "tela":
        return (f"{id_cenario} só se produz na interface (tela), não por "
                f"arquivo — ver §15 dos achados")
    if c.get("csv") and not arquivo_do_cenario(config, id_cenario, "csv"):
        return (f"arquivo {config['pastas']['gis']}/{id_cenario}_*.csv não "
                f"existe (variante da Etapa C4 ainda não produzida)")
    if papel in ("modelo", "terreno") and not arquivo_do_cenario(
            config, id_cenario, "ifc"):
        return (f"arquivo {config['pastas']['ifc']}/{id_cenario}_*.ifc não "
                f"existe (variante da Etapa C4 ainda não produzida)")
    if modelo_de(config, id_cenario) is None:
        return (f"{id_cenario} roda sobre o modelo do pai ({c.get('pai')}), e "
                f"{config['pastas']['ifc']}/{c.get('pai')}_*.ifc não existe "
                f"(variante da Etapa C4 ainda não produzida)")
    if fonte_do_terreno(config, id_cenario)[0] == "ausente":
        return f"o IFC de terreno de {id_cenario} não existe"
    return ""


# ---------------------------------------------------------------------------
# O instantâneo da análise (o que a tela faz antes de chamar o pipeline)
# ---------------------------------------------------------------------------

def carregar_empreendimento():
    """O ``artefatos/empreendimento.json`` corrente — nunca gravado de volta."""
    emp = empreendimento_json.ler("artefatos")
    if emp is None:
        raise SystemExit("artefatos/empreendimento.json não existe: declare o "
                         "caso base em 2.1.1 conforme docs/tcc/caso_base_estrela_i.md.")
    return emp


def terreno_do_cenario(config: dict, id_cenario: str, emp):
    """O terreno com que este cenário roda, e de onde veio."""
    fonte, caminho = fonte_do_terreno(config, id_cenario)
    if fonte == "empreendimento":
        return emp.terreno, "empreendimento.json"
    if fonte == "csv":
        from core.infra.gis import csv_memorial

        leitura = csv_memorial.ler(caminho, epsg=config["caso_base"]["epsg_memorial"])
        if not leitura.ok:
            raise SystemExit(f"CSV do memorial {caminho}: {leitura.erro}")
        return leitura.terreno, caminho
    from core.infra.ifc import extrator_terreno

    res = extrator_terreno.resolver_arquivo(caminho)
    if not res.ok:
        raise SystemExit(f"IFC de terreno {caminho}: " + "; ".join(res.diagnostico))
    return res.terreno, caminho


def instantaneo(emp, caminho_ifc: str, natureza: str, unidades_representadas: int,
                terreno=None):
    """O empreendimento COMO ESTA ANÁLISE O VÊ, e o contêiner âncora.

    Reproduz ``app.servicos.analise._instantaneo_da_analise`` sem alvo (a
    dedução da CLI): o ``ModeloBIM`` do arquivo vai para a única unidade tipo
    declarada (ADR-021/023) — no caso base, "Apartamento T+1" —, e as
    declarações ganham a tipologia lida dos donos do contêiner e a natureza
    do modelo como declaração local. O objeto lido do disco não muda: tudo é
    ``dataclasses.replace``.
    """
    conteiner = ModeloBIM(caminho=caminho_ifc, natureza=natureza,
                          unidades_representadas=unidades_representadas)
    unidades_tipo = list(emp.unidades_tipo)
    dona = ancora.unidade_tipo_em_analise(emp)
    if dona is not None:
        unidades_tipo = [dataclasses.replace(u, modelo=conteiner)
                         if u.id == dona.id else u for u in unidades_tipo]
    mudancas: dict = {"unidades_tipo": unidades_tipo}
    if terreno is not None:
        mudancas["terreno"] = terreno
    anexado = dataclasses.replace(emp, **mudancas)

    declaracoes = dict(anexado.declaracoes)
    tipologia = ancora.tipologia_em_analise(anexado, conteiner)
    if tipologia:
        declaracoes[dec.TIPOLOGIA] = tipologia
    declaracoes[dec.TIPO_MODELO] = natureza
    return dataclasses.replace(anexado, declaracoes=declaracoes), conteiner


def ids_executaveis(grupo_id: str, declaracoes: dict) -> list[str]:
    """As regras do grupo ativas, registradas e aplicáveis às declarações —
    o mesmo filtro de ``app.servicos.grupos.ids_executaveis``."""
    grupo = grupos_mod.carregar()[grupo_id]
    with open(os.path.join("config", "regras_ativas.yaml"), encoding="utf-8") as f:
        ativas = {str(x).strip() for x in (yaml.safe_load(f) or {}).get("ativas") or []}
    registradas = regras_registradas()
    return [rid for rid in grupo.ids
            if rid in ativas and rid in registradas
            and registradas[rid].motivo_inaplicavel(declaracoes) is None]


def roteador_de_rede(cache=True):
    """O provedor ORS, ou ``None`` com aviso — a chave é lida na BORDA, aqui."""
    from core.infra.rede import ors

    segredos = None
    caminho = os.path.join(".streamlit", "secrets.toml")
    if os.path.exists(caminho):
        import re

        m = re.search(r'ors_api_key\s*=\s*"([^"]+)"',
                      open(caminho, encoding="utf-8").read())
        if m:
            segredos = {"roteamento": {"ors_api_key": m.group(1)}}
    rede = ors.de_configuracao(segredos=segredos,
                               cache=composicao._cache_padrao() if cache else None)
    if rede is None:
        print(f"[roteamento] sem chave do OpenRouteService ({ors.VARIAVEL_AMBIENTE} "
              "ou .streamlit/secrets.toml): as regras de distância saem por "
              "metrica_insuficiente.")
    return rede


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def rodar_cenario(config: dict, id_cenario: str, *, ors: bool = False,
                  saida: str | None = None, silencioso: bool = True) -> dict:
    """Roda as cinco checagens do cenário e devolve ``{chave: relatório}``.

    ``saida`` sobrescreve ``artefatos/cenarios/<id>/`` (o teste usa uma pasta
    temporária, para não confundir a saída de uso com a da suíte).
    """
    motivo = faltando(config, id_cenario)
    if motivo:
        raise SystemExit(motivo)
    c = cenarios(config)[id_cenario]
    base = config["caso_base"]
    emp = carregar_empreendimento()
    terreno, origem_terreno = terreno_do_cenario(config, id_cenario, emp)
    caminho_ifc = modelo_de(config, id_cenario)
    uh = int(c.get("unidades_representadas") or base["unidades_representadas"])
    terreno_proprio = None if origem_terreno == "empreendimento.json" else terreno
    analisado, conteiner = instantaneo(emp, caminho_ifc, base["natureza"], uh,
                                       terreno=terreno_proprio)
    sem_modelo = (dataclasses.replace(emp, terreno=terreno_proprio)
                  if terreno_proprio is not None else emp)

    usa_rede = ors and c.get("ors", True)
    rede = roteador_de_rede() if usa_rede else None
    pasta = saida or os.path.join(config["pastas"]["saida"], id_cenario)
    os.makedirs(pasta, exist_ok=True)

    if not silencioso:
        print(f"cenário {id_cenario} ({c['familia']}, pai {c.get('pai') or '—'}) · "
              f"empreendimento {emp.id} v{emp.versao}")
        print(f"  modelo BIM : {caminho_ifc} · {uh} UH representadas")
        print(f"  terreno    : {origem_terreno} · {terreno.resumo() if terreno else '—'}")
        print(f"  rede       : {'ORS' if rede is not None else 'sem provedor (linha reta)'}")

    relatorios: dict[str, dict] = {}
    for checagem in config["checagens"]:
        chave, grupo_id = checagem["chave"], checagem["grupo"]
        destino = os.path.join(pasta, f"{chave}.json")
        if checagem.get("modelo"):
            ids = ids_executaveis(grupo_id, analisado.declaracoes)
            relatorio = composicao.rodar(empreendimento=analisado, conteiner=conteiner,
                                       ids_selecionados=ids, destino_rel=destino)
        else:
            # Sem modelo: o insumo é o empreendimento como está no disco
            # (terreno, localização, UH previstas), SEM contêiner pendurado —
            # como ``analise.analisar_sem_modelo`` e ``analisar_enquadramento``
            # recebem da tela. Com o contêiner na unidade tipo a dedução da
            # âncora abriria o IFC só para as regras GIS o ignorarem.
            ids = ids_executaveis(grupo_id, sem_modelo.declaracoes)
            relatorio = composicao.rodar(
                empreendimento=sem_modelo, ids_selecionados=ids,
                roteador_rede=rede if checagem.get("rede") else None,
                destino_rel=destino)
        if relatorio.get("erro_ingestao"):
            raise SystemExit(f"{chave}: {relatorio['erro_ingestao']}")
        relatorios[chave] = relatorio

    with open(os.path.join(pasta, ARQUIVO_PERFIL), "w", encoding="utf-8") as f:
        json.dump({"cenario": id_cenario, "familia": c["familia"],
                   "pai": c.get("pai"), "modelo": caminho_ifc,
                   "terreno": origem_terreno, "unidades_representadas": uh,
                   "rede": "ors" if rede is not None else None,
                   "requisitos": perfil(config, relatorios)},
                  f, ensure_ascii=False, indent=2)
    return relatorios


# ---------------------------------------------------------------------------
# O perfil dos 14 requisitos
# ---------------------------------------------------------------------------

def perfil(config: dict, relatorios: dict[str, dict]) -> list[dict]:
    """Uma linha por REQUISITO da Portaria, na ordem das checagens.

    A unidade é a do ``resumo.normativo.ids`` de cada relatório (R6b): os
    membros de uma agregação — alternativas B, ramos por zona, EMP-025.x —
    não contam; contam os pais. É a mesma régua do relatório por requisito e
    da cobertura consolidada, e por isso não há lista de ids escrita aqui.
    """
    linhas: list[dict] = []
    for checagem in config["checagens"]:
        rel = relatorios.get(checagem["chave"])
        if not rel:
            continue
        por_id = {r["requisito"]: r for r in rel.get("por_requisito") or []}
        for rid in (rel.get("resumo") or {}).get("normativo", {}).get("ids") or []:
            r = por_id[rid]
            linhas.append({
                "requisito": rid,
                "checagem": checagem["chave"],
                "estado": r["estado"],
                "motivo": (r.get("detalhe") or {}).get(motivos.CHAVE) or "",
                "valor_encontrado": r.get("valor_encontrado"),
                "mensagem": r.get("mensagem") or "",
            })
    return linhas


def ler_relatorios(config: dict, id_cenario: str) -> dict[str, dict] | None:
    """Os cinco relatórios gravados em ``artefatos/cenarios/<id>/``, ou ``None``
    se algum falta — a fonte é sempre o relatório, nunca o ``perfil.json``,
    que é resumo para leitura."""
    pasta = os.path.join(config["pastas"]["saida"], id_cenario)
    relatorios: dict[str, dict] = {}
    for checagem in config["checagens"]:
        caminho = os.path.join(pasta, f"{checagem['chave']}.json")
        if not os.path.isfile(caminho):
            return None
        with open(caminho, encoding="utf-8") as f:
            relatorios[checagem["chave"]] = json.load(f)
    return relatorios


def ler_perfil(config: dict, id_cenario: str) -> list[dict] | None:
    """O perfil dos 14 requisitos de um cenário já rodado, ou ``None``."""
    relatorios = ler_relatorios(config, id_cenario)
    return perfil(config, relatorios) if relatorios else None


def celula(linha: dict | None) -> str:
    """``C`` · ``NC`` · ``NA(motivo)`` — a célula das tabelas de cenários."""
    if linha is None:
        return "—"
    estado = ABREVIATURA_ESTADO.get(linha["estado"], linha["estado"])
    if linha["estado"] == "nao_avaliavel":
        return f"NA({linha['motivo'] or 'sem motivo'})"
    return estado


def mesmo_veredito(a: dict, b: dict) -> bool:
    """Estado e motivo iguais — o "mesmo veredito", no nível do
    requisito. Os números vão por ``numeros_iguais``, quando cabem."""
    return (a["estado"], a["motivo"]) == (b["estado"], b["motivo"])


def numeros_iguais(a, b, rel_tol: float = 1e-9) -> bool:
    """``valor_encontrado`` igual, com tolerância nos floats."""
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=rel_tol, abs_tol=0.0)
    return a == b


def imprimir_perfil(id_cenario: str, linhas: list[dict],
                    referencia: list[dict] | None, rotulo_ref: str = "E0") -> None:
    """A tabela do comando: uma linha por requisito; a coluna de referência
    (o E0) e a de "mudou?" só quando há E0 gravado e o cenário não é ele."""
    ref = {r["requisito"]: r for r in referencia or []}
    com_ref = bool(ref) and id_cenario != rotulo_ref
    cab = f"{'requisito':<11} {'checagem':<14} "
    cab += f"{rotulo_ref:<22} " if com_ref else ""
    cab += f"{id_cenario:<22}" + ("  mudou?" if com_ref else "")
    print()
    print(cab)
    print("-" * len(cab))
    concluidos = conformes = 0
    for linha in linhas:
        texto = f"{linha['requisito']:<11} {linha['checagem']:<14} "
        if com_ref:
            base = ref.get(linha["requisito"])
            mudou = ("—" if base is None else
                     ("sim" if not mesmo_veredito(base, linha) else "não"))
            texto += f"{celula(base):<22} {celula(linha):<22}  {mudou}"
        else:
            texto += f"{celula(linha):<22}"
        print(texto)
        if linha["estado"] != "nao_avaliavel":
            concluidos += 1
            conformes += linha["estado"] == "conforme"
    total = len(linhas)
    print("-" * len(cab))
    print(f"cobertura     : {concluidos}/{total} concluídos")
    print("conformidade  : " + (f"{conformes}/{concluidos} conformes"
                                if concluidos else "— (nenhum concluído)"))


def _listar(config: dict) -> None:
    for c in config["cenarios"]:
        motivo = faltando(config, c["id"])
        print(f"{c['id']:<4} {c['familia']:<14} pai={c.get('pai') or '—':<3} "
              f"{c['rotulo']:<22} {'pronto' if not motivo else motivo}")


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Roda um cenário da escada do Estrela I (§15 dos achados).")
    parser.add_argument("id", nargs="?", help="E0, E1, …, D1, …, V1, …")
    parser.add_argument("--ors", action="store_true",
                        help="Liga o provedor de rede (chave em ORS_API_KEY ou "
                             ".streamlit/secrets.toml). Sem ele o comando é "
                             "determinístico e as distâncias vêm em linha reta.")
    parser.add_argument("--listar", action="store_true",
                        help="Lista os cenários e diz qual arquivo falta a cada um.")
    args = parser.parse_args()
    config = carregar_config()
    if args.listar or not args.id:
        _listar(config)
        return
    id_cenario = args.id.upper()
    relatorios = rodar_cenario(config, id_cenario, ors=args.ors, silencioso=False)
    linhas = perfil(config, relatorios)
    referencia = None if id_cenario == "E0" else ler_perfil(config, "E0")
    if id_cenario != "E0" and referencia is None:
        print("\n(sem artefatos/cenarios/E0/ para comparar — rode "
              "`python scripts/rodar_cenario.py E0` primeiro)")
    imprimir_perfil(id_cenario, linhas, referencia)
    print(f"\nrelatórios em {os.path.join(config['pastas']['saida'], id_cenario)}/")


if __name__ == "__main__":
    _cli()
