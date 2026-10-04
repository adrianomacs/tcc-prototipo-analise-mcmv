"""OpenRouteService — a distância caminhável em rede, e o único provedor dela.

Este é o módulo que permite à ferramenta **aprovar** um requisito. Até aqui ela
só sabia reprovar (quando o piso euclidiano já ultrapassa o limiar) e
declarar-se insuficiente; ``limite_inferior = False`` é a diferença, e é a única
coisa que as regras precisam saber a respeito deste arquivo.

Por que o ORS é o único
-----------------------

Um segundo provedor (Google Routes) como verificação foi considerado e
descartado. Em uma linha: divergência entre dois provedores não produz veredito sem eleger um
deles como verdade, e a Portaria não nomeia aplicação nenhuma.

Consequência declarada: a rede medida é a do OpenStreetMap. Lacuna de cobertura
do OSM vira desvio, desvio vira distância inflada, e distância inflada pode virar
falso NÃO CONFORME. Nada aqui detecta isso — é limitação do trabalho, não defeito
escondido.

Por que a matriz, e não o *directions*
--------------------------------------

``/v2/matrix/{perfil}`` resolve **uma origem × N destinos numa única chamada**,
enquanto ``/v2/directions`` custaria N chamadas para a mesma resposta. E, com
``resolve_locations``, a matriz devolve ``snapped_distance`` — o deslocamento
até a via em que o roteador encaixou cada ponto. É exatamente o diagnóstico que se quer, e ele vem de graça no endpoint mais barato, sem precisar ser
derivado comparando a geometria da rota com a origem pedida.

O ``snap`` é **diagnóstico, nunca correção**: a Portaria manda computar a
distância "a partir do centro do terreno", então o centro é a origem mesmo
quando ele cai longe da rua. O número só é registrado para que o R7 possa medir
quanto ele pesa.

...e por que o *directions* entrou assim mesmo
-----------------------------------------------------------------

A matriz **não devolve geometria**, e o traçado no mapa precisa dela. O
*directions* entrou para um subconjunto pequeno e bem definido: os equipamentos
cuja distância em **linha reta** já cabe no limiar — os únicos que podem atender
o requisito, porque a reta é piso da caminhável. Para eles, número e traçado
saem da **mesma resposta**; os demais continuam na matriz, numa chamada só.

Os dois conjuntos são **disjuntos**, então nenhum par é medido duas vezes e não
há como a tela exibir um número de um endpoint sobre um caminho do outro. Na
conferência do mesmo par contra a matriz os dois concordaram (1732,49 m × 1732,5
m; pontos encaixados idênticos), mas concordar por medição não é o mesmo que não
poder divergir por construção — e é a segunda garantia que se quis.

O ``snapped_distance`` que a matriz dá de graça é **derivado** no *directions*
do primeiro ponto da geometria, que é justamente o ponto encaixado. Conferido
contra a matriz: mesmos pontos, dígito a dígito.

Sem dependência nova
--------------------

A chamada usa ``urllib`` da biblioteca padrão, e não ``requests``. É a mesma
disciplina do ``euclidiana.py`` recusando ``pyproj``: uma dependência a menos é
um motivo a menos para o teste verde aqui não valer na máquina de quem usa — que pode
instalar pacotes numa rede corporativa sem suporte de TI.
"""

from __future__ import annotations

import datetime
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from core.dominio import euclidiana as eu
from core.dominio import mobilidade as ct
from core.dominio.contratos import roteador as ct_rot
from core.infra.rede import cache_ors as ca

URL_BASE = "https://api.openrouteservice.org"
PERFIL_PEDESTRE = "foot-walking"

# O ORS negocia formato pelo par (sufixo da URL, cabeçalho Accept), e recusa com
# HTTP 406 quando os dois discordam — ver ``cabecalhos_directions``.
ACEITA_JSON = "application/json"
ACEITA_GEOJSON = "application/geo+json, application/json"

# Os dois endpoints usados. Entram na chave do cache: a matriz devolve número, o
# directions devolve número E geometria, e confundi-los devolve uma rota ausente
# sem erro nenhum. Ver ``cache.chave_par``.
ENDPOINT_MATRIZ = "matrix"
ENDPOINT_ROTA = "directions"

# O serviço aceita até 3.500 elementos (origens × destinos) por requisição. O
# limite daqui é **deliberadamente menor**: um lote pequeno falha pequeno. Se a
# chamada estoura, só os destinos daquele lote ficam sem número — e um destino
# sem número nunca reprova o conjunto (``confrontar_conjunto``), então o custo de
# uma falha parcial é um INCONCLUSIVO honesto em vez de um lote inteiro perdido.
MAX_DESTINOS_POR_CHAMADA = 50

TIMEOUT_PADRAO_S = 20.0


def _agora() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _transporte_urllib(url: str, corpo: dict, cabecalhos: dict,
                       timeout_s: float) -> dict:
    dados = json.dumps(corpo).encode("utf-8")
    req = urllib.request.Request(url, data=dados, headers=cabecalhos,
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


class RoteadorORS:
    """Provedor de rede pedestre. Implementa ``contrato.Roteador``.

    ``transporte`` é injetável para que o teste exercite o **parser** contra
    resposta gravada sem tocar a rede. O que se testa aqui é a leitura da
    resposta e o que ela vira em ``Medicao`` — não o serviço.
    """

    provedor = ct_rot.PROVEDOR_ORS
    metrica = ct_rot.METRICA_REDE_PEDESTRE
    limite_inferior = False

    def __init__(self, chave: str, *, perfil: str = PERFIL_PEDESTRE,
                 url_base: str = URL_BASE,
                 transporte: Callable[..., dict] | None = None,
                 timeout_s: float = TIMEOUT_PADRAO_S,
                 max_destinos: int = MAX_DESTINOS_POR_CHAMADA,
                 cache: ca.CacheRoteamento | None = None) -> None:
        if not chave:
            # Sem chave não se constrói um roteador de rede pela metade: quem
            # decide o que fazer na ausência dela é ``de_configuracao``.
            raise ValueError("RoteadorORS exige uma chave de API")
        self.chave = chave
        self.perfil = perfil
        self.url_base = url_base.rstrip("/")
        self._transporte = transporte or _transporte_urllib
        self.timeout_s = timeout_s
        self.max_destinos = max(1, int(max_destinos))
        self.cache = cache

    # -- interno -----------------------------------------------------------

    @property
    def url(self) -> str:
        return f"{self.url_base}/v2/matrix/{self.perfil}"

    # -- directions: o PEDIDO ---------------------------------------
    #
    # O corpo do PEDIDO mora aqui, e não em ``scripts/gravar_fixture_ors.py``
    # (modo ``--directions``), para que fixture e produção
    # **não possam divergir**: uma fixture gravada com um corpo diferente do que
    # a produção envia testaria um formato que ninguém recebe.

    @property
    def url_directions(self) -> str:
        """Variante **GeoJSON** do endpoint de rota.

        Escolhida sobre a polilinha codificada (o padrão de ``/v2/directions/
        {perfil}``) para não termos de escrever e testar um decodificador: o
        ``/geojson`` devolve as coordenadas já em pares. Menos parser nosso é
        menos superfície para errar em silêncio.
        """
        return f"{self.url_base}/v2/directions/{self.perfil}/geojson"

    @staticmethod
    def corpo_directions(origem: tuple[float, float],
                         destino: tuple[float, float]) -> dict:
        """Corpo do pedido de rota — **uma** origem, **um** destino.

        Mesma armadilha do ``_pedir``, e por isso a mesma disciplina: o ORS fala
        ``[lon, lat]``, a ordem inversa da que este projeto usa em toda parte. A
        inversão acontece aqui, num lugar só, e é testada — trocada, ela não
        estoura: devolve uma rota plausível entre dois pontos errados.

        ``instructions: False`` porque não se exibe rota falada em lugar nenhum;
        pedir as instruções só engorda a resposta que vai para o ``relatorio.json``.
        """
        return {
            "coordinates": [[float(origem[1]), float(origem[0])],
                            [float(destino[1]), float(destino[0])]],
            "instructions": False,
        }

    def _cabecalhos(self, aceita: str = ACEITA_JSON) -> dict:
        return {"Authorization": self.chave,
                "Content-Type": "application/json; charset=utf-8",
                "Accept": aceita}

    def cabecalhos_directions(self) -> dict:
        """Cabeçalhos do pedido de ROTA. O ``Accept`` casa com o sufixo da URL.

        **Achado contra o serviço real, e não contra a
        documentação.** A primeira chamada ao ``/v2/directions/.../geojson``
        voltou **HTTP 406** com ``code 2007 — "This response format is not
        supported"``, apesar de a chave estar correta (chave recusada devolve
        403, não 406). A causa é negociação de formato: o ORS exige que o
        ``Accept`` concorde com o sufixo da URL, e ``application/json`` — certo
        para a matriz — é recusado no endpoint GeoJSON.

        É o motivo de a fixture vir antes do parser: escrito contra a
        documentação, o parser estaria pronto e correto, e a chamada nunca
        chegaria nele.
        """
        return self._cabecalhos(ACEITA_GEOJSON)

    def _pedir(self, origem: tuple[float, float],
               pontos: list[tuple[float, float]]) -> dict:
        # ATENÇÃO: o ORS recebe e devolve coordenadas em [lon, lat] — a ordem
        # inversa da que este projeto usa em toda parte. Inverter aqui, num
        # lugar só, e testar a inversão: trocado, o erro não estoura, apenas
        # devolve distâncias plausíveis e erradas (um ponto no Rio Grande do Sul
        # vira um ponto no oceano, e o serviço responde "não roteável" ou
        # encaixa numa via a centenas de quilômetros).
        locais = [[float(origem[1]), float(origem[0])]]
        locais += [[float(lon), float(lat)] for lat, lon in pontos]
        corpo = {
            "locations": locais,
            "sources": [0],
            "destinations": list(range(1, len(locais))),
            "metrics": ["distance", "duration"],
            "units": "m",
            "resolve_locations": True,
        }
        return self._transporte(self.url, corpo, self._cabecalhos(),
                                self.timeout_s)

    @staticmethod
    def _linha(resposta: dict, nome: str) -> list:
        """Primeira (e única) linha da matriz para a métrica pedida."""
        matriz = resposta.get(nome)
        if not isinstance(matriz, list) or not matriz:
            return []
        primeira = matriz[0]
        return primeira if isinstance(primeira, list) else []

    @staticmethod
    def _procedencia(resposta: dict) -> dict:
        """A safra da malha que produziu o número.

        Achado ao gravar uma resposta real: o ORS declara em
        ``metadata.engine`` a data do grafo e a do extrato do OpenStreetMap. É
        **procedência**, no mesmo padrão do ``.json`` que acompanha o recorte do
        INEP — e aqui ela importa ainda mais, porque a rede muda por baixo do
        número sem que nada no terreno mude. Sem isso, "1.732 m a pé" é um número
        sem data; com isso, é um número contra uma malha identificável, e o
        NÃO CONFORME de hoje continua explicável daqui a um ano.
        """
        engine = (resposta.get("metadata") or {}).get("engine") or {}
        if not isinstance(engine, dict):
            return {}
        campos = ("graph_date", "osm_date", "version")
        return {k: engine[k] for k in campos if engine.get(k)}

    @staticmethod
    def _snap(resposta: dict, nome: str, indice: int) -> float | None:
        itens = resposta.get(nome)
        if not isinstance(itens, list) or indice >= len(itens):
            return None
        item = itens[indice]
        if not isinstance(item, dict):
            return None
        valor = item.get("snapped_distance")
        return float(valor) if isinstance(valor, (int, float)) else None

    # -- contrato ----------------------------------------------------------

    def medir(self, origem: tuple[float, float], destinos: list[Any],
              chaves: list[str] | None = None) -> list[ct.Medicao]:
        """Uma ``Medicao`` por destino, na ordem recebida.

        **Contrato com o chamador, e é onde mora a armadilha.** A chave de cada
        medição vem de ``euclidiana.chave_destino(equipamento, indice)``, e o
        ``indice`` é a posição **nesta lista**. O ``melhor_por_destino`` funde a
        medição de rede com o piso euclidiano *pela chave* — então, para
        equipamento sem ``codigo_inep`` (chave posicional ``@n``), passar aqui
        uma sublista com posições diferentes das usadas na medição euclidiana
        faz a fusão não acontecer: o piso sobrevive ao lado da medição exata, o
        conjunto continua INCONCLUSIVO e nada estoura. Falha silenciosa, com
        resultado plausível.

        Enquanto ``candidatos()`` não devolver o índice original, a regra deve
        passar **a mesma lista** que mediu com a euclidiana. Ver o teste
        ``test_chave_posicional_de_uma_sublista_nao_funde_com_o_piso``, que
        documenta o defeito em vez de fingir que ele não existe.
        """
        agora = _agora()
        medicoes: list[ct.Medicao | None] = [None] * len(destinos)
        pendentes: list[tuple[int, tuple[float, float]]] = []

        def chave_de(indice: int, equipamento) -> str:
            if chaves is not None:
                return chaves[indice]
            return eu.chave_destino(equipamento, indice)

        for i, e in enumerate(destinos):
            chave = chave_de(i, e)
            rotulo = getattr(e, "nome", "") or chave
            lat, lon = getattr(e, "lat", None), getattr(e, "lon", None)
            if lat is None or lon is None:
                medicoes[i] = self._falha(chave, rotulo, agora,
                                          "equipamento sem coordenada")
                continue
            guardado = self._do_cache(origem, (float(lat), float(lon)),
                                      ENDPOINT_MATRIZ)
            if guardado is not None:
                medicoes[i] = ct.Medicao(
                    destino=chave, rotulo=rotulo,
                    metros=guardado.get("metros"),
                    segundos=guardado.get("segundos"),
                    provedor=self.provedor, metrica=self.metrica,
                    limite_inferior=self.limite_inferior,
                    snap_m=guardado.get("snap_m"),
                    obtido_em=guardado.get("obtido_em", agora),
                    detalhe={"do_cache": True,
                             "endpoint": ENDPOINT_MATRIZ,
                             "arredondamento_m": guardado.get("arredondamento_m"),
                             **(guardado.get("procedencia") or {})})
                continue
            pendentes.append((i, (float(lat), float(lon))))

        for inicio in range(0, len(pendentes), self.max_destinos):
            lote = pendentes[inicio:inicio + self.max_destinos]
            self._medir_lote(origem, lote, destinos, medicoes, agora, chave_de)

        if self.cache is not None:
            self.cache.salvar()
        return [m for m in medicoes if m is not None]

    def _medir_lote(self, origem, lote, destinos, medicoes, agora,
                    chave_de) -> None:
        try:
            resposta = self._pedir(origem, [p for _, p in lote])
        except (OSError, ValueError) as erro:
            # Rede fora, chave recusada, cota estourada, JSON quebrado: todos
            # viram "não medido", nunca uma reprovação. Um candidato sem número
            # impede o conjunto de reprovar — é a regra do contrato, e é o que
            # impede uma falha de infraestrutura de virar não-conformidade.
            for i, _ in lote:
                e = destinos[i]
                chave = chave_de(i, e)
                medicoes[i] = self._falha(
                    chave, getattr(e, "nome", "") or chave, agora,
                    f"{type(erro).__name__}: {erro}")
            return

        distancias = self._linha(resposta, "distances")
        duracoes = self._linha(resposta, "durations")
        snap_origem = self._snap(resposta, "sources", 0)
        procedencia = self._procedencia(resposta)

        for pos, (i, ponto) in enumerate(lote):
            e = destinos[i]
            chave = chave_de(i, e)
            rotulo = getattr(e, "nome", "") or chave
            metros = distancias[pos] if pos < len(distancias) else None
            segundos = duracoes[pos] if pos < len(duracoes) else None
            if not isinstance(metros, (int, float)):
                # A matriz do ORS devolve null para par não roteável (ilha sem
                # ligação a pé, ponto fora da malha). Não é zero e não é
                # "distante": é ausência de medição.
                medicoes[i] = self._falha(chave, rotulo, agora,
                                          "par sem rota na malha do provedor")
                continue
            snap_destino = self._snap(resposta, "destinations", pos)
            medicoes[i] = ct.Medicao(
                destino=chave, rotulo=rotulo, metros=float(metros),
                segundos=float(segundos) if isinstance(segundos, (int, float))
                else None,
                provedor=self.provedor, metrica=self.metrica,
                limite_inferior=self.limite_inferior,
                snap_m=snap_origem, obtido_em=agora,
                detalhe={"perfil": self.perfil,
                         "endpoint": ENDPOINT_MATRIZ,
                         "snap_destino_m": snap_destino, **procedencia})
            self._para_o_cache(origem, ponto, medicoes[i], ENDPOINT_MATRIZ)

    # -- directions: a RESPOSTA -------------------------------------

    @staticmethod
    def ler_rota(resposta: dict) -> dict:
        """Lê a resposta de rota. Devolve ``{}`` quando ela não traz uma.

        Escrito contra ``tests/fixtures/ors_directions_real.json`` — gravado do
        serviço —, e não contra a documentação. O que a resposta
        real ensinou, e que vale registrar porque nada disso era dedutível:

        * a geometria tem **duas** dimensões por ponto, sem elevação, e vem em
          ``[lon, lat]`` como no resto da API. A inversão acontece aqui;
        * ``properties.summary`` traz ``distance``/``duration`` para a rota
          inteira — é o número que substitui o da matriz para este par;
        * os **extremos da geometria são os pontos encaixados na via**, e não os
          pedidos: conferidos contra a matriz do mesmo par, batem dígito a dígito
          com ``sources[0].location`` e ``destinations[0].location``. É o que
          torna o ``snap`` derivável aqui (ver ``medir_rota``);
        * ``properties.warnings`` existe mesmo sem se pedir informação extra, e
          é carregado adiante: um aviso do provedor sobre a qualidade da rota não
          pode sumir entre a resposta e o relatório.
        """
        feicoes = resposta.get("features")
        if not isinstance(feicoes, list) or not feicoes:
            return {}
        feicao = feicoes[0] if isinstance(feicoes[0], dict) else {}
        coords = ((feicao.get("geometry") or {}).get("coordinates")
                  if isinstance(feicao.get("geometry"), dict) else None)
        if not isinstance(coords, list) or not coords:
            return {}

        pares: list[list[float]] = []
        for ponto in coords:
            if isinstance(ponto, (list, tuple)) and len(ponto) >= 2:
                # [lon, lat] -> [lat, lon]: a convenção do projeto, invertida
                # num lugar só, como no pedido.
                pares.append([float(ponto[1]), float(ponto[0])])
        if not pares:
            return {}

        props = feicao.get("properties") or {}
        resumo = props.get("summary") or {}
        metros = resumo.get("distance")
        segundos = resumo.get("duration")
        return {
            "coordenadas": pares,
            "metros": float(metros) if isinstance(metros, (int, float)) else None,
            "segundos": (float(segundos) if isinstance(segundos, (int, float))
                         else None),
            "avisos": [a.get("message") for a in (props.get("warnings") or [])
                       if isinstance(a, dict) and a.get("message")],
        }

    def medir_rota(self, origem: tuple[float, float],
                   destino: tuple[float, float], *, chave: str,
                   rotulo: str = "") -> ct.Medicao:
        """Uma ``Medicao`` com **geometria**, para um único par.

        Número e traçado saem da **mesma resposta**, que é a razão inteira de
        usar o *directions* aqui: desenhar um caminho de um endpoint ao lado de
        um número de outro arriscaria a tela contradizer a regra na mesma linha.
        (Numa conferência os dois endpoints concordaram no mesmo par
        — 1732,49 m na matriz contra 1732,5 m na rota —, mas concordar por
        medição não é o mesmo que não poder divergir por construção.)

        O ``snap_m`` é **derivado** do primeiro ponto da geometria, que é o ponto
        encaixado na via. Sem isso, trocar de endpoint custaria o diagnóstico de
        snap justamente nos equipamentos que podem atender o requisito.
        """
        agora = _agora()
        rotulo = rotulo or chave
        guardado = self._do_cache(origem, destino, ENDPOINT_ROTA)
        if guardado is not None:
            return ct.Medicao(
                destino=chave, rotulo=rotulo, metros=guardado.get("metros"),
                segundos=guardado.get("segundos"), provedor=self.provedor,
                metrica=self.metrica, limite_inferior=self.limite_inferior,
                snap_m=guardado.get("snap_m"),
                obtido_em=guardado.get("obtido_em", agora),
                detalhe={"do_cache": True, "endpoint": ENDPOINT_ROTA,
                         "rota": guardado.get("rota"),
                         "arredondamento_m": guardado.get("arredondamento_m"),
                         **(guardado.get("procedencia") or {})})

        try:
            resposta = self._transporte(self.url_directions,
                                        self.corpo_directions(origem, destino),
                                        self.cabecalhos_directions(),
                                        self.timeout_s)
        except (OSError, ValueError) as erro:
            return self._falha(chave, rotulo, agora,
                               f"{type(erro).__name__}: {erro}",
                               endpoint=ENDPOINT_ROTA)

        lida = self.ler_rota(resposta)
        if not lida or lida.get("metros") is None:
            return self._falha(chave, rotulo, agora,
                               "resposta de rota sem geometria ou sem distância",
                               endpoint=ENDPOINT_ROTA)

        coords = lida["coordenadas"]
        medicao = ct.Medicao(
            destino=chave, rotulo=rotulo, metros=lida["metros"],
            segundos=lida["segundos"], provedor=self.provedor,
            metrica=self.metrica, limite_inferior=self.limite_inferior,
            snap_m=eu.distancia_piso_m(origem, tuple(coords[0])),
            obtido_em=agora,
            detalhe={"perfil": self.perfil, "endpoint": ENDPOINT_ROTA,
                     "rota": coords,
                     "snap_destino_m": eu.distancia_piso_m(destino,
                                                           tuple(coords[-1])),
                     "avisos_do_provedor": lida["avisos"],
                     **self._procedencia(resposta)})
        self._para_o_cache(origem, destino, medicao, ENDPOINT_ROTA,
                           extra={"rota": coords})
        return medicao

    def _falha(self, chave: str, rotulo: str, agora: str,
               erro: str, endpoint: str = ENDPOINT_MATRIZ) -> ct.Medicao:
        return ct.Medicao(destino=chave, rotulo=rotulo, metros=None,
                          provedor=self.provedor, metrica=self.metrica,
                          limite_inferior=self.limite_inferior,
                          obtido_em=agora, erro=erro,
                          detalhe={"endpoint": endpoint})

    # -- cache -------------------------------------------------------------

    def _do_cache(self, origem, destino, endpoint: str) -> dict | None:
        if self.cache is None:
            return None
        return self.cache.obter(
            ca.chave_par(self.provedor, self.perfil, origem, destino, endpoint))

    def _para_o_cache(self, origem, destino, medicao: ct.Medicao,
                      endpoint: str, extra: dict | None = None) -> None:
        if self.cache is None:
            return
        self.cache.guardar(
            ca.chave_par(self.provedor, self.perfil, origem, destino, endpoint),
            {"metros": medicao.metros, "segundos": medicao.segundos,
             "snap_m": medicao.snap_m, "obtido_em": medicao.obtido_em,
             # A procedência viaja com o valor guardado: uma medição relida do
             # cache tem de continuar dizendo contra qual malha foi feita.
             "procedencia": {k: v for k, v in medicao.detalhe.items()
                             if k in ("graph_date", "osm_date", "version")},
             # A GEOMETRIA também é guardada (``extra``). Um acerto de cache que
             # devolvesse só o número deixaria a tela sem traçado e sem erro —
             # exatamente a falha silenciosa que o endpoint na chave evita.
             **(extra or {})})


# ---------------------------------------------------------------------------
# Construção a partir da configuração
# ---------------------------------------------------------------------------

VARIAVEL_AMBIENTE = "ORS_API_KEY"


CAMPO_CHAVE = "ors_api_key"
SECAO = "roteamento"


def _de_mapa(mapa, campo: str) -> str:
    """Lê ``campo`` de qualquer coisa que se comporte como mapa.

    Deliberadamente **não** usa ``isinstance(x, dict)``. O ``st.secrets`` do
    Streamlit devolve um ``AttrDict``, que é um Mapping mas não uma subclasse de
    ``dict`` — e o teste por ``isinstance`` fazia a chave sumir em silêncio
    dentro do app, degradando para a euclidiana como se não houvesse chave
    nenhuma.
    """
    try:
        valor = mapa.get(campo)
    except (AttributeError, TypeError):
        return ""
    return str(valor).strip() if valor is not None else ""


def chave_configurada(segredos=None, ambiente: dict | None = None) -> str:
    """A chave, de ``secrets.toml`` ou do ambiente — nesta ordem.

    ``segredos`` é o ``st.secrets`` (ou um mapa equivalente), lido sem importar
    o Streamlit: esta camada não conhece a interface.

    Aceita a chave em ``[roteamento].ors_api_key`` (o formato do
    ``secrets.toml.example``) **ou** solta no topo do arquivo, que é o arranjo
    mais comum em projetos Streamlit. Ser tolerante aqui custa três linhas; ser
    estrito custa uma depuração para descobrir que a chave estava no
    lugar "errado" e o sistema dizia apenas "nenhuma chave".
    """
    if segredos is not None:
        secao = None
        try:
            secao = segredos.get(SECAO)
        except (AttributeError, TypeError):
            secao = None
        if secao is not None:
            valor = _de_mapa(secao, CAMPO_CHAVE)
            if valor:
                return valor
        valor = _de_mapa(segredos, CAMPO_CHAVE)      # solta no topo
        if valor:
            return valor
    ambiente = os.environ if ambiente is None else ambiente
    return str(ambiente.get(VARIAVEL_AMBIENTE, "")).strip()


def de_configuracao(segredos: dict | None = None, ambiente: dict | None = None,
                    **kwargs) -> RoteadorORS | None:
    """O roteador de rede, ou ``None`` quando não há chave configurada.

    ``None`` é a degradação declarada: sem chave a análise segue
    com o piso euclidiano, **declarando a métrica** — os requisitos de distância
    saem NÃO AVALIÁVEL por ``metrica_insuficiente`` em vez de serem inventados.
    Devolver ``None`` em vez de um roteador que finge medir mantém essa
    declaração honesta: quem não tem rede não diz que tem.
    """
    chave = chave_configurada(segredos, ambiente)
    return RoteadorORS(chave, **kwargs) if chave else None
