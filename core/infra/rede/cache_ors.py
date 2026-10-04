"""Cache das medições de rede — por par (origem, destino), não por análise.

Por que existe: a chamada de rede é o único passo caro da avaliação, e ele é
**repetido**. Reabrir o relatório, reconfirmar o mesmo terreno, rodar de novo os
três requisitos sobre o mesmo município — tudo isso volta a perguntar a mesma
distância entre os mesmos dois pontos. A resposta não muda entre uma execução e a
seguinte; o que muda é a cota consumida.

A chave é o **par de pontos**, e não a análise que os pediu. Assim uma medição
feita para o ENQ-009 serve ao ENQ-010.1 quando a mesma escola aparece nos dois
recortes — o que é comum, porque um estabelecimento pode ofertar mais de uma
etapa.

Arredondamento das coordenadas
------------------------------

As coordenadas entram na chave arredondadas a ``CASAS_DECIMAIS`` (5 casas,
~1,1 m no equador). Sem isso o cache nunca acertaria: o centróide recalculado a
partir da mesma poligonal difere na décima casa decimal, e cada execução geraria
uma chave nova.

O erro que o arredondamento admite é de ~1 m contra limiares de 1.000 e 1.500 m.
Ele é **declarado** no valor guardado (``arredondamento_m``) em vez de ficar
implícito, porque um número que veio do cache não foi medido exatamente daquele
ponto — e quem audita o resultado tem direito de saber disso.

Sem prazo de validade, de propósito
-----------------------------------

A rede do OpenStreetMap muda, então uma medição guardada envelhece. Mas expirar
por tempo trocaria um erro visível por um invisível: o número mudaria sozinho
entre duas execuções do mesmo terreno, e o relatório de ontem deixaria de se
reproduzir. Cada entrada carrega ``obtido_em``; **invalidar é decisão explícita**
— apagar o arquivo, ou passar ``ignorar_cache=True``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# 5 casas ≈ 1,1 m. Ver o cabeçalho do módulo.
CASAS_DECIMAIS = 5
ARREDONDAMENTO_M = 1.2


def _ponto(coord: tuple[float, float]) -> str:
    return f"{round(float(coord[0]), CASAS_DECIMAIS):.5f},{round(float(coord[1]), CASAS_DECIMAIS):.5f}"


def chave_par(provedor: str, perfil: str, origem: tuple[float, float],
              destino: tuple[float, float], endpoint: str) -> str:
    """Chave canônica de um par origem→destino, por provedor, perfil e endpoint.

    O perfil entra na chave porque ``foot-walking`` e ``driving-car`` respondem
    números diferentes para os mesmos dois pontos — omiti-lo faria uma medição
    contaminar a outra em silêncio.

    **O endpoint entra pelo mesmo motivo, e por um pior.** A
    matriz devolve número; o *directions* devolve número **e geometria**. Um par
    medido pela matriz numa execução — quando estava na faixa que só precisa de
    número — seria servido do cache na execução seguinte, em que ele caiu no
    subconjunto que precisa de traçado: o número viria certo e a rota viria
    **ausente**, sem erro nenhum aparecer. A tela simplesmente não desenharia, e
    não haveria onde perguntar por quê.

    Entradas gravadas antes desta mudança ficam inalcançáveis, o que é seguro
    justamente pelo que este módulo declara no cabeçalho: o cache é otimização,
    nunca insumo. Elas serão remedidas uma vez e regravadas com a chave nova.
    """
    return (f"{provedor}|{perfil}|{endpoint}|"
            f"{_ponto(origem)}|{_ponto(destino)}")


class CacheRoteamento:
    """Cache em memória, opcionalmente persistido em JSON.

    Sem ``caminho`` funciona só em memória — é o modo dos testes e o padrão
    quando o app não quer deixar rastro em disco.
    """

    def __init__(self, caminho: str | os.PathLike | None = None) -> None:
        self.caminho = Path(caminho) if caminho else None
        self._dados: dict[str, dict] = {}
        self._sujo = False
        self.acertos = 0
        self.faltas = 0
        if self.caminho and self.caminho.exists():
            self._carregar()

    def _carregar(self) -> None:
        try:
            bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Cache corrompido não derruba a análise: ele é otimização, nunca
            # insumo. Começa vazio e volta a se encher.
            self._dados = {}
            return
        self._dados = bruto.get("entradas", {}) if isinstance(bruto, dict) else {}

    def obter(self, chave: str) -> dict | None:
        valor = self._dados.get(chave)
        if valor is None:
            self.faltas += 1
        else:
            self.acertos += 1
        return valor

    def guardar(self, chave: str, valor: dict) -> None:
        self._dados[chave] = dict(valor, arredondamento_m=ARREDONDAMENTO_M)
        self._sujo = True

    def salvar(self) -> None:
        """Grava em disco, de forma atômica. Sem ``caminho``, não faz nada."""
        if not self.caminho or not self._sujo:
            return
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        # versao 2: a chave passou a incluir o ENDPOINT (ver ``chave_par``). O
        # carregador ignora este campo de propósito — entradas antigas apenas
        # não são mais alcançadas —, mas o arquivo tem de dizer a verdade sobre
        # o formato que carrega.
        conteudo = json.dumps(
            {"versao": 2, "casas_decimais": CASAS_DECIMAIS,
             "entradas": self._dados},
            ensure_ascii=False, indent=1)
        # Escrita atômica: um Ctrl-C no meio do dump deixaria um JSON truncado,
        # e na execução seguinte o cache inteiro seria descartado como corrompido.
        fd, tmp = tempfile.mkstemp(dir=str(self.caminho.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(conteudo)
            os.replace(tmp, self.caminho)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        self._sujo = False

    def resumo(self) -> dict:
        """Para o relatório declarar quantas medições não custaram chamada."""
        return {"acertos": self.acertos, "faltas": self.faltas,
                "entradas": len(self._dados),
                "arredondamento_m": ARREDONDAMENTO_M}
