# ADR-026 — Requisito com parâmetro condicionado à zona é um pai com ramos filhos; o pai conclui por seleção exclusiva
**Status:** Aceita

> **Leitura e zona.** O ADR-025, que este ADR completa, foi
> convertido na **DN-08**: a leitura (não traduzir entre edições; concluir só o
> invariante) está lá, e a estrutura que a materializa continua aqui. A zona
> que seleciona os ramos vem do **ADR-030**, que substitui o ADR-024.

## Contexto
Quatro requisitos do Anexo III são, na verdade, **dois**, cada um escrito em
dois ramos que a zona bioclimática seleciona: absortância de parede — "ZB 1 e 2
→ ≤ 0,6" (4.II.a.x.1) e "ZB 3 a 6 → ≤ 0,4" (x.2) — e de telhado — "ZB 1 a 3 →
≤ 0,6" (4.III.i.i) e "ZB 4 a 8 → ≤ 0,4" (i.ii). Não são um "ou" (ADR-015): são
ramos **mutuamente exclusivos**, um aplica e o outro não.

Antes desta decisão, a base modelava cada par como dois irmãos de mesmo
`grupo_pai`, sem pai de verdade — a linha `EDI-024` **era** o primeiro ramo. Isso funcionava enquanto o
seletor era conhecido. O ADR-025 quebrou a premissa para o telhado: com a
cláusula presa ao vocabulário de 2005, **não se sabe qual ramo aplica**, e o
veredito que ainda assim é certo — ≤ 0,4 conforme sob qualquer leitura, > 0,6
não conforme sob qualquer leitura — é propriedade do **par**, não de nenhum dos
dois ids. Sem pai, ele não tem onde morar: ou cada ramo afirma uma
aplicabilidade que não tem, ou os dois saem NÃO AVALIÁVEL sempre e o ADR-025
vira letra morta.

## Decisão
**O item da Portaria é o pai; os ramos são filhos.** A renumeração é forçada
pela falta de um id livre para o pai, e segue a numeração da própria Portaria:

| Pai (item) | Ramo 1 | Ramo 2 |
|---|---|---|
| EDI-019 — parede, 4.II.a.x | EDI-019.1 · ZB 1–2 · ≤ 0,6 | EDI-019.2 · ZB 3–6 · ≤ 0,4 |
| EDI-024 — telhado, 4.III.i | EDI-024.1 · ZB 1–3 · ≤ 0,6 | EDI-024.2 · ZB 4–8 · ≤ 0,4 |

**Vale para as duas famílias, inclusive a que não precisa.** Na parede o
seletor é conhecido (as faixas esgotam as doze classes do ADR-024), então o pai
é degenerado — um ramo aplica, o outro não. Manter só o telhado com pai foi a
alternativa **recusada**: as quatro regras aparecem na mesma checagem, e uma
assimetria de estrutura entre parede e telhado teria de ser explicada ao
leitor sem que nenhuma diferença normativa a justificasse. O custo é
reconhecido: é a única simetria desta decisão adotada por uniformidade de
leitura, e não por necessidade normativa.

**O pai conclui por seleção exclusiva** — modo novo, `selecao_exclusiva`. Seja
`S` o conjunto de ramos que **podem** aplicar, dada a zona resolvida (ADR-024)
e a leitura admissível da cláusula (ADR-025):
- `|S| = 1` → o pai herda o veredito do ramo; os demais saem NÃO AVALIÁVEL com
  motivo `nao_aplicavel`;
- `|S| > 1` → decide a **unanimidade**: todos conformes → CONFORME, todos não
  conformes → NÃO CONFORME, e **discordância é indecisão**, não reprovação —
  NÃO AVALIÁVEL com `analise_humana_documental` e a defasagem declarada no
  detalhe. Os ramos de `S` saem NÃO AVALIÁVEL por aplicabilidade indeterminada.

O modo é novo porque nenhum dos três existentes dá a resposta certa: em
`todos`, dois candidatos com um conforme e um não conforme caem em `n_pot < k`
e o pai **reprova** — reprovaria um projeto que a norma talvez aprove, que é o
erro exato que o ADR-025 existe para impedir.

**Quem conta é o pai.** Em conformidade e cobertura (ADR-015) o requisito da
Portaria é o pai; os ramos não entram no denominador — mesmo tratamento que
ENQ-010/010.1/010.2 já recebe. Sem isso, o telhado indeterminado derrubaria a
cobertura duas vezes por um requisito só.

Nada disso toca o executor nem o contrato de `Regra`: é um quarto modo em
`core/regras/base/agregacao.py` e um arquivo de regra-pai por família (ADR-005).

## Consequências
Fica fácil dizer a verdade sobre o telhado — o par conclui quando pode e se
cala quando não pode, sem que nenhum ramo minta sobre a própria aplicabilidade.
Fica fácil ler o relatório: parede e telhado têm a mesma forma. Fica fácil
absorver uma futura migração da Portaria: o ramo indeterminado vira determinado
e o pai degenera, sem mudança de estrutura. Fica difícil o modo novo: é o
primeiro pai do projeto que **reprova**, e o teste que o prende tem de cobrir a
discordância, que é o caso em que ele deve se calar. Não se pode usar
`selecao_exclusiva` para "ou" normativo (isso é `qualquer`, ADR-014/015), nem
deixar um ramo emitir veredito quando a própria aplicabilidade está em aberto,
nem contar ramo no denominador da cobertura.

## Evidência
Telhado:
- `MODO_SELECAO_EXCLUSIVA`, `selecao_exclusiva()` e
  `RegraAgregacao._checar_selecao_exclusiva` em `core/regras/base/agregacao.py`.
  O canal ramo → pai é o `detalhe` do ramo (`CHAVE_APLICABILIDADE`,
  `CHAVE_VEREDITO_RAMO`): o pai não lê zona, insumo nem limite.
- `core/regras/gis_bim/edi_024_absortancia.py` (pai), `edi_024_1_telhado_zb_1_3.py`
  e `edi_024_2_telhado_zb_4_8.py` (ramos), sobre a base
  `core/regras/base/absortancia.py`; ativos em `config/regras_ativas.yaml`.
- Planilha-mãe renumerada (EDI-024 pai, Agregação; 024.1 ZB 1–3; 024.2 ZB 4–8 —
  300 linhas) e o CSV derivado que então havia em `config/` regerado (retirado
  depois, por não ter consumidor); §6 de
  `tests/core/regras/base/test_agregacao.py` verde.
- `tests/core/regras/base/test_agregacao.py` §7
  (`::test_discordancia_e_indecisao_na_selecao_exclusiva_e_reprovacao_em_todos`)
  prende a diferença contra `todos`; `relatorio_json._normativo` já tira os
  ramos do denominador pelo `detalhe["tipo"]` do pai.
Parede, sobre a mesma base e o mesmo modo, sem linha nova no executor:
- `core/regras/gis_bim/edi_019_absortancia_parede.py` (pai),
  `edi_019_1_parede_zb_1_2.py` e `edi_019_2_parede_zb_3_6.py` (ramos); ativos
  em `config/regras_ativas.yaml`; planilha-mãe renumerada (EDI-019 pai; 019.1
  ZB 1–2; 019.2 ZB 3–6 — 301 linhas) e o mesmo CSV derivado regerado.
- Aqui o pai é **degenerado**, como este ADR previu: a cláusula está no
  vocabulário vigente e as faixas esgotam as doze classes (ADR-024), então um
  ramo aplica, o outro sai `nao_aplicavel` e o pai herda — `SELECAO_HERDADO`
  em todas as doze
  (`tests/core/regras/gis_bim/test_edi_019_absortancia_parede.py`). O caminho da
  unanimidade só se alcança com a zona não resolvida.
- A parede não tem exceção de material (DN-02), e a externalidade do covering
  é a decisão que o ADR-027 fechou.

## Relações
**Completa o ADR-025** (que decidiu o veredito e não a estrutura) e
**estende o ADR-015** (quarto modo de agregação). A uniformização com a
parede tem a alternativa recusada registrada acima.
