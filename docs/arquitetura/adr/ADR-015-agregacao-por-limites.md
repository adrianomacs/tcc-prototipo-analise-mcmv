# ADR-015 — Agregação por limites [n_conf, n_pot]; conformidade e cobertura contam requisitos da Portaria, não execuções
**Status:** Aceita

> **Estendida pelo ADR-026**: um quarto modo, `selecao_exclusiva`,
> para o par de ramos que a zona bioclimática seleciona. Os três modos abaixo,
> `por_limites()` e a contagem por requisitos da Portaria seguem como estão — o
> modo novo entra porque nenhum deles responde certo quando o seletor é
> desconhecido.

> **Alternativa remetida.** Este ADR recebe a parte de sistema do antigo
> ADR-014, convertido na **DN-04** (alternativa sem insumo público é
> remetida). `RegraRemetida` (`core/regras/base/remessa.py`) é regra ativa que
> executa e sai NÃO AVALIÁVEL com `analise_humana_documental`, o insumo que
> faltaria e o motivo — nem requisito ausente, nem implementado. No pai ela é
> membro não avaliável, e o teto que isso impõe viaja em
> `detalhe["reprovabilidade"]`, preso pelo único `xfail` estrito da suíte
> (`tests/core/regras/base/test_agregacao.py::test_pai_reprovaria_se_a_alternativa_b_fosse_avaliavel`).
> Instâncias: ENQ-010.2, ENQ-011.2 e EMP-025.2.

## Contexto
Requisitos-pai agregam membros (qualquer / todos / contagem mínima k) sobre
um universo em que quase nenhum município terá o conjunto completo de
camadas de insumo. A pergunta era dupla: como um pai decide quando um membro
está NÃO AVALIÁVEL em vez de decidido, e como o módulo reporta seu resultado
global sem confundir "não atende" com "não sei".

## Decisão
Duas métricas, não uma: **Conformidade** = conformes / (conformes + não
conformes), só entre o que foi possível avaliar; **Cobertura** = avaliáveis /
aplicáveis, quanto do enquadramento os insumos disponíveis alcançaram — as
duas contam **requisitos da Portaria** aplicáveis à análise, nunca linhas de
execução ou casos de teste. Um enquadramento com 60% de cobertura é análise
honesta, não falha. Na agregação por contagem com limiar k: `n_conf` =
membros confirmados conformes, `n_pot` = `n_conf` + membros ainda não
avaliáveis (melhor cenário); `n_conf >= k` decide CONFORME, `n_pot < k`
decide NÃO CONFORME, e no meio o pai fica NÃO AVALIÁVEL reportando
`[n_conf, n_pot]` contra k. Membro sem resultado conta como não avaliável,
nunca como inexistente. A filiação (membros, modo, k) é atributo de classe da
regra-pai, não YAML — `grupos_requisitos.yaml` é espelho de tela, não fonte
de veredito — e é confrontada em teste contra a coluna "Grupo (pai)" da
planilha-mãe.

## Consequências
Fica fácil fechar parte do enquadramento mesmo com lacunas e mostrar QUANTO
falta ("3 a 6 confirmados, exigidos 4" é informação; "não avaliável" seco
não é). Fica fácil comunicar o estado do módulo com dois números que não se
confundem entre si. Fica difícil (propriedade da norma somada ao insumo, não
bug) um pai cuja lacuna é estrutural — como as alternativas remetidas
(ADR-014) — sair da faixa "nunca reprova"; viaja declarado em
`detalhe["reprovabilidade"]`. Não se pode usar `depende_de` para a filiação
de agregação: o executor transformaria dependência não conforme em NÃO
AVALIÁVEL sem executar a regra, o caso exato que o agregador existe para
julgar.

## Evidência
- `core/regras/base/agregacao.py`: `por_limites()`, `k_de()`,
  `class RegraAgregacao`.
- `core/regras/gis/enq_010_fundamental_i.py`,
  `enq_011_fundamental_ii.py` (`agrega`, `modo`).
- `tests/core/regras/base/test_agregacao.py` (33 testes; §6 confronta a filiação com
  `Base_Requisitos_Portaria_MCID_725.xlsx`;
  `::test_teto_declarado_no_resultado`,
  `::test_pai_reprovaria_se_a_alternativa_b_fosse_avaliavel`).
