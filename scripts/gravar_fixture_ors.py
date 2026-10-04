"""Grava uma resposta REAL da matriz do OpenRouteService como fixture de teste.

Por que este script existe
--------------------------

Os testes do R5c rodam contra resposta gravada, com o transporte injetado. Isso
cobre bem o que pode dar errado em silêncio **na leitura** da resposta — mas não
cobre nada do que pode dar errado no **formato** dela. Enquanto a fixture for
escrita a partir da documentação, um teste verde prova apenas que o parser
corresponde à nossa leitura dos documentos.

Este script fecha essa lacuna: faz **uma** chamada real, salva a resposta crua e
em seguida roda o parser contra ela, mostrando o que virou ``Medicao``. Se o
formato for outro, aparece aqui e em nenhum outro lugar.

A chave nunca sai da sua máquina
--------------------------------

Ela é lida de ``.streamlit/secrets.toml`` (ou da variável ``ORS_API_KEY``) e
**nunca** é impressa nem gravada no arquivo de saída. O que este script produz é
a resposta do serviço, que não contém segredo nenhum.

Uso
---

    python scripts/gravar_fixture_ors.py
    python scripts/gravar_fixture_ors.py --origem -29.50186,-51.96529 \
        --destino -29.49702,-51.95661 --destino -29.50944,-51.97812

Custo: **uma** requisição de matriz. O plano gratuito do ORS comporta isso com
folga.

Modo ``--directions``
----------------------------

    python scripts/gravar_fixture_ors.py --directions

Grava a resposta do endpoint de **rota** (``/v2/directions/.../geojson``), que é
de onde sai o traçado no mapa — e, com ele, a distância que passa a decidir para
os equipamentos que podem atender o requisito. Também **uma** requisição, um
destino só.

Este modo não roda parser: ele vem ANTES do parser, porque escrever o
parser de geometria contra a documentação é exatamente o que se quer evitar. Ele inspeciona o formato e responde, na saída, as três perguntas que
decidem a implementação — onde está a geometria, onde está a distância, e se a
rota começa no ponto encaixado na via (do que depende manter o diagnóstico de
``snap`` para esses equipamentos).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.dominio import mobilidade as ct
from core.infra.rede import ors as orsm

SAIDA_PADRAO = RAIZ / "tests" / "fixtures" / "ors_matrix_real.json"
SAIDA_DIRECTIONS = RAIZ / "tests" / "fixtures" / "ors_directions_real.json"

# Terreno urbano de Estrela/RS e três pontos próximos. Servem para gravar o
# FORMATO da resposta; não precisam ser escolas reais para isso.
ORIGEM_PADRAO = (-29.50186, -51.96529)
DESTINOS_PADRAO = [(-29.49702, -51.95661),
                   (-29.50944, -51.97812),
                   (-29.48001, -51.99001)]


def _par(texto: str) -> tuple[float, float]:
    lat, lon = texto.split(",")
    return float(lat), float(lon)


def _relativo(caminho: Path) -> str:
    """Caminho relativo à raiz quando possível, absoluto quando não.

    ``Path.relative_to`` **levanta** para um caminho fora da raiz, e ``--saida``
    é um argumento público: apontá-lo para fora do repositório derrubava o
    script DEPOIS de a chamada ter sido feita e a fixture gravada — perdendo a
    requisição por causa de uma linha de log.
    """
    try:
        return str(caminho.relative_to(RAIZ))
    except ValueError:
        return str(caminho)


def ler_chave() -> str:
    """``secrets.toml`` primeiro, depois o ambiente — a mesma ordem do módulo.

    Cada passo é narrado. "Nenhuma chave encontrada" sem dizer **qual** passo
    falhou — achar o arquivo ou achar o campo dentro dele — transforma um erro de
    dois minutos numa depuração longa. Nada do conteúdo é impresso: só nomes
    de seções e de campos, nunca valores.
    """
    caminho = RAIZ / ".streamlit" / "secrets.toml"
    print(f"Raiz do projeto deduzida do script: {RAIZ}")
    print(f"Procurando segredos em: {caminho}")

    if not caminho.exists():
        print("  -> o arquivo NÃO existe nesse caminho.")
        if not (RAIZ / "core" / "roteamento").is_dir():
            print("  !! E a raiz deduzida não parece a do repositório: não há")
            print("     core/roteamento sob ela. O script provavelmente está")
            print("     fora de scripts/ — ele deduz a raiz como a pasta-mãe da")
            print("     sua. Mova-o para scripts/gravar_fixture_ors.py.")
        else:
            existentes = sorted(x.name for x in (RAIZ / ".streamlit").glob("*")) \
                if (RAIZ / ".streamlit").is_dir() else []
            print(f"     Conteúdo de .streamlit/: {existentes or 'pasta ausente'}")
        segredos = None
    else:
        texto = caminho.read_text(encoding="utf-8")
        print(f"  -> arquivo encontrado ({len(texto)} bytes).")
        segredos = _parse_toml(texto)
        if segredos is None:
            return ""
        secoes = [k for k, v in segredos.items() if isinstance(v, dict)]
        topo = [k for k, v in segredos.items() if not isinstance(v, dict)]
        print(f"     Seções encontradas: {secoes or 'nenhuma'}")
        print(f"     Campos no topo: {topo or 'nenhum'}")
        print(f"     (esperado: seção [{orsm.SECAO}] com o campo "
              f"{orsm.CAMPO_CHAVE}, ou {orsm.CAMPO_CHAVE} solto no topo)")

    chave = orsm.chave_configurada(segredos)
    if not chave and segredos is not None:
        print("  -> o arquivo foi lido, mas não tem o campo "
              f"{orsm.CAMPO_CHAVE} em nenhum dos dois lugares aceitos.")
    return chave


def _parse_toml(texto: str) -> dict | None:
    try:
        import tomllib
    except ModuleNotFoundError:
        # Python < 3.11: leitura mínima, só o bastante para achar a chave.
        print("     (sem tomllib — Python < 3.11; usando leitura simplificada)")
        secao, dados = None, {}
        for linha in texto.splitlines():
            linha = linha.split("#", 1)[0].strip()
            if linha.startswith("[") and linha.endswith("]"):
                secao = linha[1:-1].strip()
                dados[secao] = {}
            elif "=" in linha:
                k, v = linha.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if secao:
                    dados[secao][k.strip()] = v
                else:
                    dados[k.strip()] = v
        return dados
    try:
        return tomllib.loads(texto)
    except Exception as erro:
        print(f"  -> o arquivo existe mas NÃO é TOML válido: {erro}")
        print("     Formato esperado, com as aspas:")
        print(f'       [{orsm.SECAO}]')
        print(f'       {orsm.CAMPO_CHAVE} = "sua-chave-aqui"')
        return None


class _Gravador:
    """Transporte que guarda a resposta crua antes de devolvê-la ao parser."""

    def __init__(self) -> None:
        self.resposta: dict | None = None

    def __call__(self, url, corpo, cabecalhos, timeout_s):
        dados = json.dumps(corpo).encode("utf-8")
        req = urllib.request.Request(url, data=dados, headers=cabecalhos,
                                     method="POST")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            self.resposta = json.loads(resp.read().decode("utf-8"))
        return self.resposta


def gravar_directions(chave: str, origem, destino, saida: Path) -> int:
    """Uma chamada de ``/v2/directions/.../geojson`` e a inspeção do FORMATO.

    Este modo não roda parser nenhum: ele **precede** o parser, que só
    pode ser escrito depois de existir uma resposta real. O que
    ele faz é olhar a resposta e responder, de olho, as três perguntas que
    decidem a implementação:

    1. **onde está a geometria** e quantos pontos ela tem (dimensiona o que vai
       parar no ``relatorio.json``);
    2. **onde está a distância** que tem de sair da MESMA resposta que o
       traçado — é a razão inteira de trocar a matriz pelo directions;
    3. **a rota começa no ponto encaixado na via?** Se sim, o ``snap_m`` que a
       matriz dava de graça é derivável aqui (distância entre o centro pedido e
       o primeiro ponto da geometria), e o diagnóstico de snap não se perde para
       justamente os equipamentos que podem atender o requisito.

    O corpo do pedido vem de ``ors.RoteadorORS.corpo_directions``, o mesmo que a
    produção usará: fixture gravada com outro corpo testaria um formato que
    ninguém recebe.
    """
    from core.dominio import euclidiana as eu

    roteador = orsm.RoteadorORS(chave)
    url = roteador.url_directions
    corpo = roteador.corpo_directions(origem, destino)

    print(f"\nUma chamada de rota: {origem} -> {destino}")
    print(f"  {url}")
    print(f"  corpo: {json.dumps(corpo)}")

    try:
        dados = json.dumps(corpo).encode("utf-8")
        req = urllib.request.Request(url, data=dados,
                                     headers=roteador.cabecalhos_directions(),
                                     method="POST")
        with urllib.request.urlopen(req, timeout=roteador.timeout_s) as resp:
            resposta = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        corpo_erro = erro.read().decode("utf-8", "replace")[:600]
        print(f"FALHA HTTP {erro.code}: {corpo_erro}")
        print("  (406 com code 2007 é negociação de formato: o Accept tem de")
        print("   casar com o sufixo da URL — ver cabecalhos_directions.")
        print("   403 é chave sem permissão para o serviço; 429 é cota.)")
        return 2
    except (urllib.error.URLError, ValueError) as erro:
        print(f"FALHA na chamada: {erro}")
        return 2

    saida.parent.mkdir(parents=True, exist_ok=True)
    conteudo = dict(resposta)
    conteudo["_fixture"] = (
        "GRAVAÇÃO REAL de /v2/directions/foot-walking/geojson, produzida por "
        "scripts/gravar_fixture_ors.py --directions. Base do parser de "
        "geometria do R-08.")
    saida.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"Resposta crua gravada em {_relativo(saida)} "
          f"({saida.stat().st_size} bytes)")

    # --- inspeção: as três perguntas ------------------------------------
    print(f"\nCampos no topo: {sorted(k for k in resposta if not k.startswith('_'))}")

    feicoes = resposta.get("features")
    if not isinstance(feicoes, list) or not feicoes:
        print("!! Não há 'features' na resposta — o formato NÃO é o esperado "
              "para o /geojson. O parser terá de ser escrito para o que veio.")
        return 3
    feicao = feicoes[0]
    geometria = (feicao.get("geometry") or {})
    coords = geometria.get("coordinates")
    props = (feicao.get("properties") or {})
    resumo = props.get("summary") or {}

    print(f"features: {len(feicoes)} | geometry.type: {geometria.get('type')!r}")
    print(f"properties: {sorted(props)}")
    print(f"summary: {resumo}")

    if not isinstance(coords, list) or not coords:
        print("!! geometry.coordinates ausente ou vazio.")
        return 3
    print(f"\n1) GEOMETRIA: {len(coords)} pontos. "
          f"Primeiro={coords[0]} último={coords[-1]} (ORS devolve [lon, lat])")

    distancia = resumo.get("distance")
    duracao = resumo.get("duration")
    print(f"2) DISTÂNCIA na mesma resposta: {distancia} m | {duracao} s "
          + ("— OK" if isinstance(distancia, (int, float))
             else "— AUSENTE, e sem ela o directions não substitui a matriz"))

    lon0, lat0 = float(coords[0][0]), float(coords[0][1])
    lonf, latf = float(coords[-1][0]), float(coords[-1][1])
    snap_origem = eu.distancia_piso_m(origem, (lat0, lon0))
    snap_destino = eu.distancia_piso_m(destino, (latf, lonf))
    print(f"3) SNAP DERIVÁVEL? distância do centro pedido ao 1º ponto da rota: "
          f"{snap_origem:.1f} m")
    print(f"   (e do destino pedido ao último ponto: {snap_destino:.1f} m)")
    print("   Interpretação: um valor pequeno e plausível (metros a dezenas de")
    print("   metros) indica que a rota começa no ponto ENCAIXADO na via, e o")
    print("   snap_m do §5 é derivável sem a matriz. Um valor ~0 significa que o")
    print("   ORS devolve a rota começando no ponto PEDIDO, e aí o snap se perde")
    print("   para o conjunto A — decisão do autor sobre aceitar ou não.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--origem", type=_par, default=ORIGEM_PADRAO,
                   help="lat,lon do centro do terreno")
    p.add_argument("--destino", type=_par, action="append", dest="destinos",
                   help="lat,lon de um equipamento (repetível)")
    p.add_argument("--saida", type=Path, default=None)
    p.add_argument("--directions", action="store_true",
                   help="Grava a fixture do endpoint de ROTA (R-08) em vez da "
                        "matriz. Uma chamada, um destino.")
    args = p.parse_args()

    destinos = args.destinos or DESTINOS_PADRAO

    chave = ler_chave()
    if chave and args.directions:
        print(f"Chave encontrada ({len(chave)} caracteres). Não será impressa.")
        return gravar_directions(chave, args.origem, destinos[0],
                                 args.saida or SAIDA_DIRECTIONS)
    args.saida = args.saida or SAIDA_PADRAO
    if not chave:
        print("Nenhuma chave encontrada em .streamlit/secrets.toml nem em "
              "ORS_API_KEY.\nÉ exatamente o caso em que de_configuracao() "
              "devolve None e a análise segue com o piso euclidiano.")
        return 1
    print(f"Chave encontrada ({len(chave)} caracteres). Não será impressa.")

    class _Equip:
        def __init__(self, i, lat, lon):
            self.nome = f"Destino {i}"
            self.lat, self.lon = lat, lon
            self.codigo_inep = f"TESTE{i}"

    equipamentos = [_Equip(i, lat, lon) for i, (lat, lon) in enumerate(destinos)]

    gravador = _Gravador()
    roteador = orsm.RoteadorORS(chave, transporte=gravador)

    print(f"Uma chamada de matriz: 1 origem × {len(destinos)} destinos...")
    try:
        medicoes = roteador.medir(args.origem, equipamentos)
    except (urllib.error.HTTPError, urllib.error.URLError) as erro:
        # Só chega aqui se a falha for fora do medir(); dentro dele, vira
        # Medicao com erro. Mantido para a mensagem ser legível mesmo assim.
        print(f"FALHA na chamada: {erro}")
        return 2

    if gravador.resposta is None:
        print("A chamada não devolveu resposta. Veja o erro nas medições abaixo.")
    else:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        conteudo = dict(gravador.resposta)
        conteudo["_fixture"] = (
            "GRAVAÇÃO REAL da matriz do OpenRouteService, produzida por "
            "scripts/gravar_fixture_ors.py. Substitui a fixture provisória "
            "escrita a partir da documentação.")
        args.saida.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"Resposta crua gravada em {_relativo(args.saida)}")

    print("\nO que o parser leu da resposta REAL:")
    print(f"{'destino':<12} {'metros':>10} {'segundos':>10} {'snap_m':>9}  erro")
    for m in medicoes:
        metros = f"{m.metros:.2f}" if m.metros is not None else "—"
        seg = f"{m.segundos:.1f}" if m.segundos is not None else "—"
        snap = f"{m.snap_m:.2f}" if m.snap_m is not None else "—"
        print(f"{m.destino:<12} {metros:>10} {seg:>10} {snap:>9}  {m.erro or ''}")

    # O que interessa conferir de olho, porque é o que a fixture provisória
    # pode ter errado:
    campos = sorted(k for k in (gravador.resposta or {}) if not k.startswith("_"))
    print(f"\nCampos no topo da resposta: {campos}")
    tem_snap = any(m.snap_m is not None for m in medicoes)
    if tem_snap:
        print("snapped_distance da origem: SIM, o parser leu.")
    else:
        print("snapped_distance da origem: NÃO veio. O campo não existe na "
              "resposta ou tem outro nome — ajustar o parser antes de confiar "
              "no diagnóstico de snap do §5.")
    validas = [m for m in medicoes if m.valida]
    print(f"Medições com número: {len(validas)} de {len(medicoes)}")
    print(f"\nVeredito contra 1.000 m: "
          f"{ct.confrontar_conjunto(medicoes, 1000.0)[0]}")

    if not validas:
        # Sai diferente de zero para não parecer sucesso: nenhuma medição saiu.
        # Um 403 aqui é chave recusada; 429 é cota. Note que, mesmo assim, o
        # veredito acima é "inconclusivo" e nunca "não atende" — falha de
        # infraestrutura não vira não-conformidade, e este é o teste vivo disso.
        print("\nNenhuma medição saiu. A fixture NÃO foi gravada.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
