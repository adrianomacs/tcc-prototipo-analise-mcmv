"""Distância em linha reta — o **piso** de qualquer caminho, e o pré-filtro.

Dois papéis, e os dois dependem da mesma propriedade: o número devolvido aqui
nunca pode ser MAIOR que a distância caminhável real.

1. **Piso para o veredito.** Acima do limiar, reprova.
2. **Pré-filtro de quem vai ao ROTEADOR.** Quem está além do raio pela linha
   reta está além pela rede também, então pode ser excluído do *roteamento* sem
   que a conclusão do conjunto deixe de valer. Isso é o que torna legítimo
   chamar a API só para os *k* mais próximos.

   **Atenção — armadilha medida contra um recorte real.**
   O pré-filtro decide quem vai à REDE, nunca quem é MEDIDO. Medir só os
   candidatos do raio joga fora a prova da reprovação: num terreno rural sem
   nenhum equipamento no raio, o conjunto medido fica vazio e o veredito sai
   "inconclusivo" — quando na verdade todos estão demonstravelmente além do
   limiar, e o caso era de NÃO CONFORME sem nenhuma chamada de API. A haversine
   é gratuita; **meça sempre o conjunto inteiro** e use ``candidatos()`` apenas
   para escolher a quem pedir a rede.

Por que não usar a geodésica precisa
------------------------------------

Precisão aqui não é a virtude; **a direção do erro é**. Uma fórmula que erre para
mais, ainda que por um metro, quebra as duas propriedades acima: reprovaria um
equipamento que está dentro do limiar, e o excluiria do pré-filtro.

Então o cálculo é a haversine com o **menor raio de curvatura da Terra**
(``R_MINIMO_M``, o raio meridional no equador). A escolha é deliberadamente
conservadora: o número sai sistematicamente **abaixo** da geodésica no
elipsoide, e o custo é reprovar de menos, nunca de mais.

Verificado antes de virar código: 200.000 pares aleatórios no território
brasileiro, de 50 m a 5 km — **zero** casos em que o valor superou a geodésica
(referência: inverso de Vincenty no WGS 84). Subestimação máxima observada:
0,77%, cerca de 7,7 m em 1 km.

A consequência prática é pequena e declarável: um equipamento a 1.005 m do centro
é medido como ~997 m e **não** é reprovado por este módulo — fica inconclusivo,
esperando o roteamento em rede. Errar para o lado de "não sei" é o erro que este
projeto aceita.

Não depende de ``pyproj`` de propósito: a mesma linha de código roda no ambiente
de desenvolvimento e no de teste, então um teste verde aqui prova o mesmo lá.

Por que mora no domínio
-----------------------

O ``RoteadorEuclidiano`` é uma implementação da porta ``Roteador`` sem I/O
nenhum — só ``math`` e o relógio que carimba a medição. É a medida de piso que
o ADR-013 define, matemática do domínio e não adaptador de serviço; por isso
fica no anel interno (ADR-002), e a implementação em rede, que chama a API,
fica em ``core/infra/rede/ors.py``.
"""

from __future__ import annotations

import datetime
import math
from typing import Any

from core.dominio import mobilidade as ct
from core.dominio.contratos import roteador as ct_rot

# Raio meridional de curvatura no equador, WGS 84: a·(1 − e²). É o menor raio de
# curvatura do elipsoide, e usá-lo garante que a haversine subestime.
_A = 6_378_137.0
_F = 1 / 298.257223563
R_MINIMO_M = _A * (1 - _F * (2 - _F))      # ≈ 6 335 439 m


def distancia_piso_m(origem: tuple[float, float],
                     destino: tuple[float, float]) -> float:
    """Piso, em metros, da distância entre dois pontos (lat, lon) em WGS 84."""
    lat1, lon1 = float(origem[0]), float(origem[1])
    lat2, lon2 = float(destino[0]), float(destino[1])
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_MINIMO_M * math.asin(min(1.0, math.sqrt(a)))


def _agora() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def chave_destino(equipamento: Any, indice: int) -> str:
    """Identidade única do equipamento dentro de uma avaliação.

    O código INEP quando existe; caso contrário, uma chave **posicional**.

    O que NÃO serve é o nome, e isso não é preciosismo: no CSV do usuário o
    código é opcional, e "EMEI CENTRO" em dois distritos do mesmo município é
    banal. Usando o nome, os dois registros colapsam numa chave só e o mais
    distante esconde o mais próximo — ou, pior, esconde um que sequer foi
    medido, e o conjunto passa a reprovar com um candidato em aberto. É o mesmo
    defeito de chave de deduplicação que apareceu no R4a, agora na camada de
    medição.
    """
    codigo = getattr(equipamento, "codigo_inep", None)
    codigo = str(codigo).strip() if codigo is not None else ""
    return codigo or f"@{indice}"


class RoteadorEuclidiano:
    """Provedor sempre disponível: sem rede, sem chave, sem cota.

    Declara ``limite_inferior = True``, que é o que impede qualquer regra de
    aprovar um requisito com o número dele.
    """

    provedor = ct_rot.PROVEDOR_EUCLIDIANA
    metrica = ct_rot.METRICA_LINHA_RETA
    limite_inferior = True

    def medir(self, origem: tuple[float, float], destinos: list[Any],
              chaves: list[str] | None = None) -> list[ct.Medicao]:
        agora = _agora()
        medicoes: list[ct.Medicao] = []
        for i, e in enumerate(destinos):
            lat, lon = getattr(e, "lat", None), getattr(e, "lon", None)
            chave = chaves[i] if chaves is not None else chave_destino(e, i)
            rotulo = getattr(e, "nome", "") or chave
            if lat is None or lon is None:
                medicoes.append(ct.Medicao(
                    destino=chave, rotulo=rotulo, metros=None,
                    provedor=self.provedor, metrica=self.metrica,
                    limite_inferior=self.limite_inferior,
                    obtido_em=agora, erro="equipamento sem coordenada"))
                continue
            medicoes.append(ct.Medicao(
                destino=chave, rotulo=rotulo,
                metros=distancia_piso_m(origem, (lat, lon)),
                provedor=self.provedor, metrica=self.metrica,
                limite_inferior=self.limite_inferior, obtido_em=agora))
        return medicoes


# ---------------------------------------------------------------------------
# Pré-filtro
# ---------------------------------------------------------------------------

FATOR_RAIO_PADRAO = 2.0


def raio_de_busca(limiar_m: float, fator: float = FATOR_RAIO_PADRAO) -> float:
    """Raio do pré-filtro. **Nunca menor que o limiar** — ver ``candidatos``."""
    return max(float(limiar_m), float(limiar_m) * float(fator))


def candidatos(origem: tuple[float, float], equipamentos: list[Any],
               limiar_m: float,
               fator: float = FATOR_RAIO_PADRAO) -> tuple[list[tuple[Any, float]], float]:
    """``([(equipamento, piso_m)] ordenado pelo piso, raio usado)``.

    Devolve **quem merece uma chamada ao roteador de rede** — e nada além disso.
    Não é "o conjunto a avaliar": ver a armadilha no topo do módulo. Lista vazia
    aqui significa "ninguém precisa ir à rede", e não "nada a concluir": com o
    conjunto inteiro medido em linha reta, esse caso é justamente o do NÃO
    CONFORME de graça.

    **A invariante que torna o descarte legítimo:** o raio é sempre ``>=`` o
    limiar. Quem fica de fora tem piso maior que o raio, logo maior que o
    limiar, logo distância em rede maior que o limiar — está provadamente fora, e
    excluí-lo não muda o veredito do conjunto.

    Se o raio pudesse ser menor que o limiar, o descarte passaria a esconder
    candidatos que atendem, e o "NÃO ATENDE" viraria falso não-conforme. Por isso
    ``raio_de_busca`` impõe o piso em vez de confiar no chamador.
    """
    raio = raio_de_busca(limiar_m, fator)
    dentro: list[tuple[Any, float]] = []
    for e in equipamentos:
        lat, lon = getattr(e, "lat", None), getattr(e, "lon", None)
        if lat is None or lon is None:
            continue
        d = distancia_piso_m(origem, (lat, lon))
        if d <= raio:
            dentro.append((e, d))
    dentro.sort(key=lambda par: par[1])
    return dentro, raio


def candidatos_indexados(origem: tuple[float, float], equipamentos: list[Any],
                         limiar_m: float,
                         fator: float = FATOR_RAIO_PADRAO
                         ) -> tuple[list[tuple[Any, float, int]], float]:
    """Como ``candidatos``, mas carregando o **índice na lista original**.

    Existe porque a chave de um equipamento sem ``codigo_inep`` é posicional, e
    a posição que vale é a da lista INTEIRA — a que foi medida com a euclidiana.
    Quem recebe só o subconjunto não tem como reconstruí-la, e derivar a chave da
    posição no subconjunto quebra a fusão entre o piso e a medição de rede em
    silêncio.

    ``candidatos`` segue existindo e inalterada: quem só quer saber *quem* iria à
    rede não precisa do índice.
    """
    raio = raio_de_busca(limiar_m, fator)
    dentro: list[tuple[Any, float, int]] = []
    for i, e in enumerate(equipamentos):
        lat, lon = getattr(e, "lat", None), getattr(e, "lon", None)
        if lat is None or lon is None:
            continue
        d = distancia_piso_m(origem, (lat, lon))
        if d <= raio:
            dentro.append((e, d, i))
    dentro.sort(key=lambda t: t[1])
    return dentro, raio
