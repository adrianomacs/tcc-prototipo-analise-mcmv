"""Classe-base das regras de distância a equipamento (ENQ-009, 010.1, 011.1).

As três regras do recorte fazem a mesma pergunta com parâmetros diferentes:
*existe equipamento público e ativo do ciclo X a até N metros caminháveis do
centro do terreno?* Toda a lógica mora aqui; cada regra declara só `ciclo`,
`limiar_m` e os textos.

Por que a lógica fica concentrada
---------------------------------

Não é economia de linhas — é o fechamento de **dois acoplamentos**, os dois
nascidos de defeitos reais e não de estética:

1. **O limiar não pode divergir entre o pré-filtro e o veredito.** Os dois saem
   do mesmo ``self.limiar_m``. Um chamador que usasse 1.000 num e 1.500 no outro
   produziria reprovação ilegítima *em silêncio*: o pré-filtro descartaria
   equipamentos que atendem, e o "não atende" viraria falso não-conforme.
2. **Medir é o conjunto inteiro; pré-filtrar é só quem vai à rede.** Escrito uma
   vez. Foi exatamente aqui que o R5a errou — medindo só os candidatos do raio, o
   terreno rural sem nenhum equipamento próximo saía "inconclusivo" quando todos
   estavam demonstravelmente além. A haversine é gratuita; a chamada de API não.

Por que três subclasses e não uma regra parametrizada
-----------------------------------------------------

Lição da atomização do EDI-004: cada requisito precisa falhar, ser gateado e ser
reportado **por conta própria**. Uma regra só, produzindo três resultados,
voltaria a acoplar o destino dos três — e o defeito que isso causa (uma
pendência em um requisito apagando outro) já custou uma rodada neste projeto.

A ordem dos passos é normativa
------------------------------

O ponto que não pode mudar de
lugar é a **sanidade antes do veredito**: reprovar só é permitido depois que o
insumo passou pela desconfiança, e é isso que impede lacuna de cadastro de virar
falso não-conforme.
"""

from __future__ import annotations

from typing import Any

from core.dominio import equipamentos as eq
from core.dominio import euclidiana as eu
from core.dominio import mobilidade as rot
from core.dominio.contratos import roteador as rot_rot
from core.dominio.contratos.regra import Contexto, Dominio, Regra, Verbo
from core.dominio.vocabulario import declaracoes as dec
from core.dominio.vocabulario import motivos, tipos_diagnostico

# O recorte municipal NÃO é lido aqui (ADR-011): quem o resolve é
# ``core/aplicacao/resolver_territorio.py``, pela porta ``FontesTerritoriais``,
# e ele chega pronto em ``ctx.recorte_equipamentos``.

# Chave de despacho do relatório dedicado destas regras.
TIPO_DIAGNOSTICO = tipos_diagnostico.DISTANCIA_EQUIPAMENTO

# Texto do critério de aceite, escrito UMA vez e transportado no resultado. Na
# interface ele seria reescrito à mão e envelheceria em silêncio: ``filtrar()``
# passou a restringir o atendimento, e uma legenda que ainda
# dissesse "pública e ativa" descreveria um filtro que não é mais o aplicado.
CRITERIO_ACEITE = ("rede pública (municipal, estadual ou federal), situação "
                   "ativa e atendimento à demanda escolar geral")


# ---------------------------------------------------------------------------
# Evidência para o relatório
# ---------------------------------------------------------------------------

def linhas_medidas(aceitos, medicoes, limiar_m: float, raio_m: float,
                   determinante) -> list[dict]:
    """Uma linha por equipamento avaliado, com o que a medição dele autoriza.

    O casamento entre equipamento e medição é feito pela **chave de destino**
    (``euclidiana.chave_destino``), nunca pelo nome nem pela posição na lista de
    medições: duas escolas homônimas colapsariam numa chave e a não medida
    sumiria atrás da medida — o defeito que fazia o conjunto
    reprovar com um candidato em aberto.

    ``classificacao`` vem de ``rot.classificar``, de onde sai também o veredito.
    Recalculá-la aqui abriria a porta para a tela discordar da regra.

    **As duas medições viajam juntas:** ``metros`` é a que decide, e
    ``metros_linha_reta`` / ``metros_rede`` são as duas leituras do mesmo par, cada
    uma sob sua métrica (ver ``rot.por_metrica``). Elas não participam do veredito —
    estão aqui porque o relatório se reproduz do JSON, e exibir só o número que
    decidiu esconde o desvio da malha viária, que é a primeira coisa que se quer ver
    ao desconfiar de uma distância. ``erro_rede`` diz por que um par não tem medida
    de rede, distinguindo "não foi ao roteador" de "o roteador não conseguiu".
    """
    melhor = rot.melhor_por_destino(medicoes)
    metricas = rot.por_metrica(medicoes)
    chave_determinante = determinante.destino if determinante is not None else None

    linhas: list[dict] = []
    for i, e in enumerate(aceitos):
        chave = eu.chave_destino(e, i)
        m = melhor.get(chave)
        metros = m.metros if m is not None else None
        do_par = metricas.get(chave, {})
        reta = do_par.get(rot_rot.METRICA_LINHA_RETA)
        rede = do_par.get(rot_rot.METRICA_REDE_PEDESTRE)
        linhas.append({
            "destino": chave,
            "nome": e.nome,
            "codigo_inep": e.codigo_inep,
            "lat": e.lat,
            "lon": e.lon,
            "rede": e.rede,
            "situacao": e.situacao,
            "atendimento": e.atendimento,
            "conveniada": e.conveniada,
            "endereco": e.endereco,
            "fonte": e.fonte,
            "precisao": e.precisao,
            "metros": metros,
            # As duas leituras do mesmo par, para exibição lado a lado.
            "metros_linha_reta": reta.metros if reta is not None and reta.valida else None,
            "metros_rede": rede.metros if rede is not None and rede.valida else None,
            "erro_rede": (rede.erro if rede is not None
                          else "fora do raio da distância caminhável"),
            # O TRAÇADO, quando houve. Vem da medição de REDE — nunca da
            # que decide: se o piso euclidiano vencesse a fusão por qualquer
            # motivo, a linha exibiria uma rota sem o número que ela mede.
            "rota": (rede.detalhe.get("rota")
                     if rede is not None and rede.valida else None),
            # Qual endpoint produziu o número de rede desta linha. Com dois em
            # uso na mesma análise, duas linhas com o mesmo rótulo de métrica
            # podem ter procedências diferentes, e isso não pode ficar implícito.
            "endpoint": (rede.detalhe.get("endpoint", "")
                         if rede is not None else ""),
            "metrica": m.metrica if m is not None else "",
            "provedor": m.provedor if m is not None else "",
            "limite_inferior": m.limite_inferior if m is not None else None,
            "erro": (m.erro if m is not None else "equipamento não medido"),
            "classificacao": rot.classificar(m, limiar_m),
            # "No raio" é quem seria mandado ao roteador de rede — NÃO é quem
            # foi avaliado (todos foram). É o recorte do mapa, e o campo existe
            # para a tela não reconstruir o pré-filtro por conta própria.
            "no_raio": metros is not None and metros <= raio_m,
            "determinante": chave == chave_determinante,
        })
    # Ordenado pela LINHA RETA, não pela medida que decide. Duas
    # razões: a linha reta existe para todos os aceitos, então a ordem fica
    # completa e estável, e os que não foram ao roteador — os únicos sem número de
    # rede — caem no fim, em vez de intercalar lacunas no meio da tabela.
    #
    # Quem precisa do "mais próximo" NÃO deve confiar nesta ordem: o menor em
    # linha reta pode não ser o menor em rede. Calcule o mínimo por `metros`
    # explicitamente (ver ``_ui_comum.painel_enq_resumo``).
    linhas.sort(key=lambda linha: (linha["metros_linha_reta"] is None,
                                   linha["metros_linha_reta"] or 0.0))
    return linhas


def descartados_no_raio(descartados, centro: tuple[float, float],
                        raio_m: float) -> list[dict]:
    """Equipamentos descartados pelos filtros que caem dentro do raio de busca.

    Existem para responder, na tela, à pergunta que um não-conforme sempre
    levanta: *e aquela escola ali na esquina?*. Sem coordenada não há como situar
    no raio, e a linha fica de fora daqui — mas continua contada em
    ``filtragem.por_motivo``, que é global.
    """
    proximos: list[dict] = []
    for e, motivo in descartados:
        if e.lat is None or e.lon is None:
            continue
        metros = eu.distancia_piso_m(centro, (e.lat, e.lon))
        if metros > raio_m:
            continue
        proximos.append({
            "nome": e.nome, "codigo_inep": e.codigo_inep,
            "lat": e.lat, "lon": e.lon, "rede": e.rede,
            "situacao": e.situacao, "atendimento": e.atendimento,
            "conveniada": e.conveniada, "metros": metros,
            "motivo": motivo,
            "rotulo_motivo": eq.ROTULO_DESCARTE.get(motivo, motivo),
        })
    proximos.sort(key=lambda linha: linha["metros"])
    return proximos


class RegraDistanciaEquipamento(Regra):
    """Base das três regras-folha de proximidade a equipamento de educação."""

    dominio = Dominio.GIS
    verbo = Verbo.ESPACIAL
    # Não depende do EMP-001: o gate é o terreno, senão três dos quatro modos de
    # entrada ficariam inúteis.
    depende_de: list[str] = []
    exige_terreno = "ponto"
    alvo = "terreno × equipamentos de educação"

    ciclo: str = ""
    limiar_m: float = 0.0

    # -- passos ------------------------------------------------------------

    def checar(self, ctx: Contexto):
        codigo = str(ctx.empreendimento.codigo_ibge or "").strip()
        if not codigo:
            # Declaração do proponente, não conteúdo do modelo (ADR-033).
            return self.nao_avaliavel(
                motivo=motivos.INSUMO_DO_PROPONENTE_AUSENTE,
                mensagem="Município não declarado em Informações Gerais; sem "
                         "ele não há recorte de equipamentos a consultar.")

        recorte = self._recorte(ctx, codigo)
        if recorte is None:
            # No fluxo da composição só chega aqui sem recorte quando a leitura
            # falhou (o resolvedor registra a causa no log): o mesmo estado e o
            # mesmo motivo de quando a regra relia o arquivo e o executor isolava
            # a exceção. Contexto montado à mão sem território cai aqui também.
            return self.nao_avaliavel(
                motivo=motivos.ERRO_DE_EXECUCAO,
                mensagem=(f"O recorte de equipamentos do município {codigo} não "
                          "foi resolvido antes da execução (leitura com falha ou "
                          "contexto sem território)."),
                detalhe={"municipio_ibge": codigo})
        if not recorte.disponivel:
            return self.nao_avaliavel(
                motivo=motivos.INSUMO_AUSENTE,
                mensagem=(f"Não há recorte de equipamentos para o município "
                          f"{codigo}. Gere-o com "
                          f"'scripts/gerar_equipamentos.py --municipio {codigo}' "
                          "ou forneça o CSV complementar de equipamentos."),
                detalhe={"municipio_ibge": codigo, "recorte": recorte.origem})

        filtragem = eq.filtrar(recorte.equipamentos, ciclo=self.ciclo)
        centro = tuple(ctx.empreendimento.terreno.centro_wgs84)

        # A população do Censo chega resolvida em ``ctx.populacao_municipal``
        # (ADR-030); sem ela o sinal de contagem implausível fica inativo e
        # DECLARADO como inativo, nunca subentendido como "não disparou".
        populacao = self._populacao_municipal(ctx)
        suspeitas = eq.sanidade(
            filtragem.aceitos, ciclo=self.ciclo,
            total_no_conjunto=filtragem.total,
            populacao_municipal=populacao)
        inativos = eq.sinais_inativos(populacao_municipal=populacao)

        roteador = eu.RoteadorEuclidiano()
        # O conjunto INTEIRO é medido: é o que sustenta a reprovação.
        medicoes = roteador.medir(centro, filtragem.aceitos)
        # O pré-filtro só escolhe quem iria ao roteador de rede.
        a_rotear, raio = eu.candidatos_indexados(centro, filtragem.aceitos,
                                                 self.limiar_m)
        medicoes, rede = self._medir_em_rede(ctx, centro, a_rotear, medicoes)

        veredito, determinante = rot.confrontar_conjunto(medicoes, self.limiar_m)

        if determinante is not None:
            extra = eq.suspeita_por_distancia(determinante.metros)
            if extra is not None:
                suspeitas = list(suspeitas) + [extra]

        detalhe = self._detalhe(ctx, codigo, filtragem, suspeitas, inativos,
                                determinante, raio, len(a_rotear), veredito,
                                medicoes=medicoes, centro=centro, rede=rede,
                                procedencia=recorte.procedencia)
        return self._veredito(veredito, determinante, suspeitas, detalhe)

    # -- auxiliares --------------------------------------------------------

    def _recorte(self, ctx, codigo: str):
        """O recorte do município resolvido pela aplicação, ou ``None``.

        O único caminho é ``ctx.recorte_equipamentos``, entregue por
        ``aplicacao/resolver_territorio.py`` antes de o executor rodar — a regra
        não sabe de arquivo nenhum (ADR-011). O caminho legado, que remontava o
        recorte a partir de uma pasta quando o ``Contexto`` vinha montado à mão,
        saiu: era a última dependência do anel de regras para o anel externo.

        O código tem de bater: um recorte resolvido para outro município (não
        acontece pela composição, que resolve a partir do mesmo empreendimento) é
        ignorado, e não usado.
        """
        resolvido = getattr(ctx, "recorte_equipamentos", None)
        if resolvido is not None and resolvido.codigo_ibge == codigo:
            return resolvido
        return None

    def _medir_em_rede(self, ctx, centro, a_rotear, medicoes):
        """Acrescenta as medições de rede às euclidianas. Nunca substitui.

        As duas listas convivem, e ``melhor_por_destino`` escolhe a que conclui.
        Substituir seria perder o piso de quem o provedor não conseguiu rotear —
        e é justamente o piso que sustenta a reprovação nesses casos.

        **As chaves são calculadas aqui, com o índice na lista INTEIRA**
        (``a_rotear`` carrega esse índice, que é a razão de
        ``candidatos_indexados`` existir). Derivá-las da posição no subconjunto
        faria a fusão falhar em silêncio para equipamento sem código INEP.

        Sem provedor de rede configurado, devolve o que entrou: os requisitos
        saem NÃO AVALIÁVEL por ``metrica_insuficiente``, que é a degradação
        declarada — e não uma aprovação inventada com o piso.
        """
        info = {"provedor": None, "candidatos": len(a_rotear),
                "medidos": 0, "falhas": 0}
        provedor = self._roteador_de_rede(ctx)
        if provedor is None or not a_rotear:
            info["motivo"] = ("sem provedor de rede configurado"
                              if provedor is None
                              else "nenhum candidato dentro do raio")
            return medicoes, info

        # O conjunto que vai à rede se parte em DOIS, disjuntos.
        #
        #   A) linha reta <= 1x o limiar -> endpoint de ROTA (número + traçado)
        #   B) o resto, até 2x o limiar  -> matriz (só o número)
        #
        # O critério de A é o da assimetria entre linha reta e rede: como a
        # reta é piso da caminhável, **só estes podem atender** o requisito, e
        # são os únicos para os quais desenhar um caminho ajuda a averiguar. Os
        # de B já estão provadamente fora; eles continuam sendo medidos porque a
        # coluna "Em rede" existe para mostrar as duas distâncias lado a lado.
        #
        # Disjuntos importa: nenhum par é medido pelos dois endpoints, então a
        # tela não tem como exibir o número de um sobre o caminho do outro.
        #
        # ``medir_rota`` ausente (provedor de terceiro, ou duble de teste que só
        # implementa ``medir``) degrada para o comportamento anterior: tudo pela
        # matriz, sem geometria. Sem traçado é pior, mas continua correto.
        com_rota = callable(getattr(provedor, "medir_rota", None))
        para_rota: list[tuple[Any, str]] = []
        alvos: list[Any] = []
        chaves: list[str] = []
        for e, piso, indice in a_rotear:
            chave = eu.chave_destino(e, indice)
            if com_rota and piso <= self.limiar_m:
                para_rota.append((e, chave))
            else:
                alvos.append(e)
                chaves.append(chave)
        info["para_rota"] = len(para_rota)
        info["para_matriz"] = len(alvos)

        em_rede: list = []
        try:
            if alvos:
                em_rede += provedor.medir(centro, alvos, chaves=chaves)
            for e, chave in para_rota:
                em_rede.append(provedor.medir_rota(
                    centro, (float(e.lat), float(e.lon)),
                    chave=chave, rotulo=getattr(e, "nome", "") or chave))
        except Exception as erro:                      # noqa: BLE001
            # O provedor já converte falha em Medicao sem número; isto aqui é o
            # cinto de segurança para um provedor de terceiro que não o faça.
            # Uma exceção subindo daqui derrubaria a regra INTEIRA, e a análise
            # perderia até o piso euclidiano que já estava medido.
            info["motivo"] = f"{type(erro).__name__}: {erro}"
            return list(medicoes) + list(em_rede), info

        info["provedor"] = getattr(provedor, "provedor", "")
        info["metrica"] = getattr(provedor, "metrica", "")
        info["medidos"] = sum(1 for m in em_rede if m.valida)
        info["falhas"] = sum(1 for m in em_rede if not m.valida)
        proc = next((m.detalhe for m in em_rede if m.valida), {}) or {}
        info["procedencia_malha"] = {k: proc[k] for k in
                                     ("graph_date", "osm_date", "version")
                                     if k in proc}
        return list(medicoes) + list(em_rede), info

    def _roteador_de_rede(self, ctx):
        """O provedor de rede, ou ``None``.

        Vem de ``ctx.roteador`` (campo tipado) e, na falta
        dele, de ``ctx.config["roteador_rede"]`` — a injeção por chave de string
        de antes, mantida como legado para contextos montados à mão. Os dois são
        preenchidos pela borda: o app (que sabe do ``st.secrets`` e do cache em
        disco) ou o teste.

        O motor NÃO lê variável de ambiente aqui, e a tentação de ler é grande —
        seria uma linha, e pouparia fiação no app. Mas então a suíte passaria a
        chamar a API de verdade na máquina de quem tivesse ``ORS_API_KEY``
        exportada: os mesmos testes dariam resultados diferentes em máquinas
        diferentes, gastariam cota e ficariam dependentes de rede. Configuração
        entra pela borda; o núcleo é determinístico. Quem lê o ambiente é
        ``ors.de_configuracao``, chamada pelo app e pelos scripts.
        """
        tipado = getattr(ctx, "roteador", None)
        if tipado is not None:
            return tipado
        return (ctx.config or {}).get("roteador_rede")

    def _populacao_municipal(self, ctx: Contexto) -> int | None:
        """Habitantes do município (Censo 2022), ou ``None`` quando não há.

        O contexto carrega o ``PopulacaoMunicipal`` com procedência, não o
        número solto (ADR-030); a sanidade só precisa dos habitantes. Um valor
        que não seja inteiro positivo conta como ausente, porque um piso de
        plausibilidade calculado sobre lixo produziria suspeita falsa — e
        suspeita de lacuna trava a reprovação, o que já seria mudar veredito.
        """
        bruto = getattr(ctx, "populacao_municipal", None)
        habitantes = getattr(bruto, "populacao", bruto)
        if isinstance(habitantes, bool) or not isinstance(habitantes, int):
            return None
        return habitantes if habitantes > 0 else None

    def _veredito(self, veredito: str, determinante, suspeitas, detalhe: dict):
        comuns = {"valor_esperado": self.limiar_m,
                  "valor_encontrado": determinante.metros if determinante else None,
                  "unidade": "m", "detalhe": detalhe}

        if veredito == rot.VEREDITO_INCONCLUSIVO:
            # Duas causas MUITO diferentes caem em "inconclusivo", e chamar as
            # duas de `metrica_insuficiente` mandaria o usuário configurar um
            # roteador para resolver um problema de cadastro.
            #
            # Sem determinante não houve o que medir: o conjunto do ciclo está
            # vazio. A métrica não é o obstáculo — o insumo é.
            if determinante is None:
                return self.nao_avaliavel(
                    motivo=(motivos.INSUMO_SUSPEITO if suspeitas
                            else motivos.INSUMO_AUSENTE),
                    mensagem=(self._frase_suspeitas(suspeitas) or
                              "Nenhum equipamento do ciclo exigido no recorte "
                              "do município."),
                    **comuns)
            # Com determinante, o insumo existe e foi medido: o que falta é
            # poder de conclusão da métrica. Causa distinta, e ação distinta.
            return self.nao_avaliavel(
                motivo=motivos.METRICA_INSUFICIENTE,
                mensagem=self._mensagem_inconclusivo(determinante), **comuns)

        if veredito == rot.VEREDITO_ATENDE:
            if eq.impede_aprovar(suspeitas):
                return self.nao_avaliavel(
                    motivo=motivos.INSUMO_SUSPEITO,
                    mensagem="Há equipamento dentro do limiar, mas a coordenada "
                             "do cadastro é duvidosa — ela pode estar aproximando "
                             "falsamente. " + self._frase_suspeitas(suspeitas),
                    **comuns)
            return self.conforme(mensagem=self._mensagem_conforme(determinante),
                                 **comuns)

        # VEREDITO_NAO_ATENDE
        if eq.impede_reprovar(suspeitas):
            return self.nao_avaliavel(
                motivo=motivos.INSUMO_SUSPEITO,
                mensagem="Nenhum equipamento dentro do limiar, mas o cadastro "
                         "não passou nas verificações de sanidade — a ausência "
                         "pode ser de REGISTRO, não de escola. "
                         + self._frase_suspeitas(suspeitas),
                **comuns)
        return self.nao_conforme(mensagem=self._mensagem_nao_conforme(determinante),
                                 **comuns)

    # -- textos ------------------------------------------------------------

    def _frase_suspeitas(self, suspeitas) -> str:
        return " ".join(s.mensagem for s in suspeitas)

    def _mensagem_conforme(self, m) -> str:
        return (f"{m.rotulo} a {m.metros:.0f} m ({rot_rot.ROTULO_METRICA[m.metrica]}), "
                f"dentro do limiar de {self.limiar_m:.0f} m.")

    def _mensagem_nao_conforme(self, m) -> str:
        if m is None:
            return f"Nenhum equipamento dentro de {self.limiar_m:.0f} m."
        if m.limite_inferior:
            return (f"O equipamento mais próximo está a {m.metros:.0f} m em linha "
                    f"reta, acima do limiar de {self.limiar_m:.0f} m — e a "
                    "distância caminhável só pode ser maior.")
        return (f"O equipamento mais próximo está a {m.metros:.0f} m "
                f"({rot_rot.ROTULO_METRICA[m.metrica]}), acima do limiar de "
                f"{self.limiar_m:.0f} m.")

    def _mensagem_inconclusivo(self, m) -> str:
        if m is None:
            return ("Não foi possível medir a distância a nenhum equipamento do "
                    "ciclo exigido.")
        return (f"O mais próximo está a {m.metros:.0f} m em LINHA RETA, abaixo do "
                f"limiar de {self.limiar_m:.0f} m. "
                + motivos.ACAO[motivos.METRICA_INSUFICIENTE])

    # -- diagnóstico -------------------------------------------------------

    def _detalhe(self, ctx, codigo, filtragem, suspeitas, inativos, determinante,
                 raio, quantos_a_rotear, veredito, *, medicoes, centro,
                 rede=None, procedencia=None) -> dict:
        proc = procedencia if procedencia is not None else {}
        return {
            # Chave de despacho do relatório (``app/paginas/relatorio.py``): sem
            # ela as ENQ caem no painel genérico, que só sabe mostrar o JSON.
            "tipo": TIPO_DIAGNOSTICO,
            "municipio_ibge": codigo,
            "municipio": self._municipio(ctx, codigo, proc),
            "ciclo": self.ciclo,
            "rotulo_ciclo": eq.ROTULO_CICLO.get(self.ciclo, self.ciclo),
            "criterio_aceite": CRITERIO_ACEITE,
            "limiar_m": self.limiar_m,
            "veredito_metrico": veredito,
            "determinante": determinante.to_dict() if determinante else None,
            "filtragem": filtragem.to_dict(),
            "raio_de_busca_m": raio,
            "candidatos_para_roteamento": quantos_a_rotear,
            # O que a rede fez, incluindo quando não fez nada e por quê. Sem
            # isso, "NÃO AVALIÁVEL por métrica insuficiente" não distingue
            # "não há chave configurada" de "o provedor falhou" — e as duas
            # pedem ações diferentes de quem lê o relatório.
            "roteamento_de_rede": rede or {},
            # A EVIDÊNCIA, e não só a conclusão: o conjunto medido, equipamento a
            # equipamento, com o que cada medição autoriza concluir. É o que
            # permite ao relatório se reproduzir a partir do JSON — a mesma razão
            # pela qual o descarte é contabilizado e não silencioso.
            "equipamentos": linhas_medidas(filtragem.aceitos, medicoes,
                                           self.limiar_m, raio, determinante),
            # Descartados DENTRO DO RAIO. Uma escola privada a 300 m é o que o
            # analista precisa ver para entender um não-conforme; uma descartada
            # a 40 km é ruído. As contagens por motivo seguem globais, acima.
            "descartados_no_raio": descartados_no_raio(filtragem.descartados,
                                                       centro, raio),
            "suspeitas": [{**s.to_dict(), "classe": eq.classe_da_suspeita(s.codigo)}
                          for s in suspeitas],
            # Declarar o que NÃO foi verificado é tão importante quanto o que
            # foi: sem isso, "nenhuma suspeita" se confunde com "nada checado".
            "sinais_nao_verificados": inativos,
            "procedencia_recorte": proc,
            # A geometria VAI JUNTO. Buscá-la do
            # ``artefatos/terreno.json`` na hora de desenhar faria o mapa do
            # relatório mostrar um terreno redefinido DEPOIS da análise — a
            # mesma família do defeito do município divergente.
            "terreno": self._terreno(ctx),
        }

    def _municipio(self, ctx, codigo, proc: dict) -> dict:
        """Nome e UF do município, do recorte ou das declarações da tela."""
        declaradas = ctx.empreendimento.declaracoes or {}
        return {
            "ibge": codigo,
            "nome": proc.get("nome_municipio") or declaradas.get(dec.MUNICIPIO) or "",
            "uf": proc.get("uf") or declaradas.get(dec.UF) or "",
        }

    def _terreno(self, ctx) -> dict:
        t = ctx.empreendimento.terreno
        lat, lon = (getattr(t, "centro_wgs84", None) or (None, None))
        return {
            "origem": getattr(t, "origem", ""),
            "nivel": getattr(t, "nivel", ""),
            "precisao": getattr(t, "precisao", ""),
            "crs_metrico": getattr(t, "crs_metrico", ""),
            "centro_wgs84": {"lat": lat, "lon": lon},
            "poligonal_wgs84": getattr(t, "poligonal_wgs84", None),
            "area_m2": getattr(t, "area_m2", None),
        }
