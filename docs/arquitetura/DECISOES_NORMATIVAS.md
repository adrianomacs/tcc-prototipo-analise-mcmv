# Decisões normativas — como este protótipo lê a Portaria

Registro das decisões de **leitura de texto normativo**: o que a Portaria MCID
nº 725/2023 (e as normas que ela cita) querem dizer quando o texto é ambíguo,
está desatualizado, remete a insumo inexistente ou diverge de outra fonte.

## Por que não é ADR

Um ADR registra decisão sobre o **sistema** — anéis, contratos, motor, onde
mora o I/O. Estas registram decisão sobre o **texto**. A diferença que importa
não é de assunto, é de **ritmo e de validade**:

- Arquitetura **estabiliza**: os três estados, o gateway e os anéis não mudam
  mais. Leitura normativa **não estabiliza**: a planilha-mãe tem mais de cem
  requisitos, e cada um pode levantar uma pergunta de leitura.
- Uma decisão de arquitetura só cai por decisão nossa. Uma decisão de leitura
  **expira sozinha** quando o regulador conserta o texto — daí o status
  `Superada pela norma`, que não existe no vocabulário dos ADRs.

Misturar as duas faria a série de ADRs crescer na velocidade da implementação
da norma, e não na da arquitetura. Este arquivo fecha a série para esse
conteúdo: leitura da Portaria entra **aqui**, e ADR fica para decisão sobre o
sistema.

**Um arquivo só.** É a razão de ser do instrumento. Entrada nova é uma seção
nova neste arquivo, nunca um arquivo novo — se ele ficar longo demais para ler
de ponta a ponta, o remédio é condensar entrada vencida, não partir em dois.

## Onde cada coisa vai

| A pergunta é… | Vai para |
|---|---|
| O que este trecho da Portaria exige, e como o lemos? | **aqui** |
| Que fonte/versão de norma externa adotamos? | **aqui** |
| Esta alternativa tem insumo público? O que fazer se não tem? | **aqui** |
| Como o sistema representa, executa ou conclui isso? | ADR |
| Que id/arquivo/modo de agregação a decisão produz? | ADR |

Caso de fronteira, e ele é comum: uma pergunta de leitura costuma **gerar** uma
decisão de sistema. Separam-se em duas entradas que se citam — a DN diz o que a
norma quer dizer, o ADR diz como o motor faz. É o par DN-08 (não se traduz
entre edições) e ADR-026 (pai + ramos): nasceram juntos, antes deste arquivo
existir, e o primeiro, que nascera ADR-025, foi convertido em DN.

## Formato de uma entrada

```markdown
## DN-NN — <título afirmativo, no presente>
**Status:** Vigente · **Requisitos:** EDI-0xx, …

**O texto.** O que a Portaria diz, citado com a referência exata (Anexo, Tabela,
item), e por que ele não decide sozinho.

**A leitura.** O que se adota, no presente do indicativo. Uma leitura por
entrada.

**Por quê, e o que se recusou.** As alternativas consideradas e o motivo da
escolha — é isto que impede a decisão de ser reaberta por esquecimento.

**Efeito.** O que muda no veredito, e o ADR que a materializa, se houver.
```

Alvo de **20 linhas**. Passar disso é sinal de que há duas leituras na mesma
entrada — ou de que a decisão é de sistema e o lugar dela é um ADR.

**Status:** `Vigente` · `Revista por DN-NN` · `Superada pela norma (dd/mm/aaaa)`
— este último quando o regulador altera o texto e a leitura deixa de ser
necessária — · `Retirada`, quando a **fonte** da leitura sai do projeto (só a
linha do índice fica, para o número não ser reaproveitado). Entrada superada
**não se apaga**: ela é a memória de por que o verificador se comportava de
outro jeito, e a avaliação dos resultados depende dessa rastreabilidade.

## Índice

| # | Título | Status |
|---|---|---|
| DN-01 | As exceções da absortância do telhado identificam-se pelo nome do material do `IfcCovering`; material sem nome não é identificável | Vigente |
| DN-02 | A absortância da parede externa não tem exceção de material, e "predominantemente / cores escuras em detalhes" não abre exceção ao valor declarado | Vigente |
| DN-03 | Georreferenciamento conclui-se só sobre entidades do IFC4; *property set* de extensão em IFC2X3 não é evidência (ex-ADR-012) | Vigente |
| DN-04 | Alternativa normativa sem insumo público é remetida à análise humana, nunca omitida (ex-ADR-014) | Vigente |
| DN-05 | O recorte avalia só equipamentos de educação públicos, ativos e de atendimento geral; conveniadas entram como sensibilidade (ex-ADR-016) | Vigente |
| DN-06 | O equipamento de educação compõe três fontes do Censo Escolar, com precedência por campo; a etapa vem da contagem de turmas (ex-ADR-017) | Vigente |
| DN-07 | *(retirada: a FRE deixou de ser fonte do protótipo; o número não se reaproveita)* | Retirada |
| DN-08 | Cláusula em vocabulário normativo superado não é traduzida; conclui-se só o que é invariante à leitura (ex-ADR-025) | Vigente |
| DN-09 | Dispensa documental de um limite verificável é requisito próprio: a ferramenta a indica e não a conclui | Vigente |

As DN-03 a DN-08 são as decisões normativas tomadas **antes** de existir este
arquivo, quando ainda nasciam como ADR (012, 014, 016, 017, 019 e 025, nessa
ordem). Cada uma foi condensada no formato acima; o arquivo do ADR ficou como
cabeçalho de remissão (`Convertida em DN-NN`), e a parte de sistema que
algumas carregavam passou ao ADR que a materializa (ADR-008, ADR-015, ADR-026
e ADR-030). A DN-07 (ex-ADR-019) foi retirada, e o arquivo do ADR com ela.

---

## DN-01 — As exceções da absortância do telhado identificam-se pelo nome do material do `IfcCovering`; material sem nome não é identificável
**Status:** Vigente · **Requisitos:** EDI-024, EDI-024.1, EDI-024.2

**O texto.** Anexo III, Tab. 1, item 4.III.i: absortância do telhado ≤ 0,6
(ZB 1, 2 e 3) ou ≤ 0,4 (ZB 4 a 8), "com exceção de coberturas em telhas de
barro não vitrificada e cobertura verde". A Portaria não diz como reconhecer
nenhuma das duas num modelo, nem o que fazer quando não se sabe.

**A leitura.** A exceção é propriedade do **material**: lê-se o nome do(s)
`IfcMaterial` associado(s) ao `IfcCovering` (direto ou pelo tipo; camadas e
constituintes expandidos). *Telha de barro não vitrificada* = material cerâmico
(barro, cerâmica, argila, terracota) **sem** termo de vitrificação (vitrificada,
esmaltada, vidrada — a esmaltada é tratada à parte em 4.III.h); *cobertura
verde* = sistema vegetado (cobertura/telhado/teto verde, *green roof*, vegetado,
substrato, grama), nunca a cor "verde" sozinha. Perfil de telha (colonial,
romana, portuguesa) não identifica material. Covering **sem material com nome**
é *não identificável*. Vocabulário: `core/dominio/conhecimento/materiais_cobertura.py`.

**Por quê, e o que se recusou.** Recusou-se inferir a exceção pela cor, pela
absortância ou pelo nome do elemento ("tinta verde" viraria cobertura verde), e
tratar material desconhecido como "não é exceção" — seria veredito por omissão
com o modelo sem entregar a informação. A dispensa da Tab. 2, item 1.II.b
(desempenho pela NBR 15.575) é documental e fica fora desta leitura.

**Efeito.** Exceção → o limite não se aplica ao covering (só exceções →
`nao_aplicavel`); sem nome → `informacao_ausente`; material comum → comparado
ao limite do ramo. Materializado em EDI-024.1/024.2 (ADR-026/027).

---

## DN-02 — A absortância da parede externa não tem exceção de material, e "predominantemente / cores escuras em detalhes" não abre exceção ao valor declarado
**Status:** Vigente · **Requisitos:** EDI-019, EDI-019.1, EDI-019.2

**O texto.** Anexo III, Tab. 1, item 4.II.a.x (redação da Portaria 489/2025):
"deve ser garantida a pintura das paredes externas **predominantemente** em
cores claras a médias (absortância solar máxima de 0,6) [ZB 1 e 2] / em cores
claras (máxima de 0,4) [ZB 3 a 6] ou o uso de acabamentos externos
predominantemente com absortância solar máxima de 0,6 / 0,4. **Cores escuras
são admitidas em detalhes.**" Nem "predominantemente" nem "detalhe" têm
definição na Portaria; e, ao contrário de 4.III.i, o item **não excetua
material nenhum**.

**A leitura.** Duas coisas. (1) **Não há exceção de material na parede**: a
lista da DN-01 (telha de barro não vitrificada, cobertura verde) é exclusiva do
telhado, e o ramo de parede não lê material — exigi-lo produziria pendência por
informação que o requisito não pede. (2) O canal de verificação é a
**absortância declarada** no `IfcCovering`, nunca a cor: acabamento escuro que
declare valor dentro do limite atende, e covering externo que declare valor
acima do limite **reprova o ramo**, ainda que os demais atendam.

**Por quê, e o que se recusou.** Recusou-se medir predominância por área
(> 50 % da área dos coverings externos): a Portaria não escreve limiar algum, e
inventá-lo seria criar norma, além de depender de `Qto_CoveringBaseQuantities`
que os modelos do estudo de caso não trazem. Recusou-se também sair
`NAO_AVALIAVEL` sempre que um covering estoura o limite: como a cor não é lida,
um valor declarado acima do limite é um valor medido acima do limite, e a
cláusula de detalhe não o transforma em dúvida.

**Efeito.** O ramo de parede desliga a etapa de exceções
(`excecoes_por_material = False`) e conclui pelo `AbsortanciaSolar` de cada
covering externo. Materializado em EDI-019.1/019.2 (ADR-026/027).

---

## DN-03 — Georreferenciamento conclui-se só sobre entidades do IFC4; *property set* de extensão em IFC2X3 não é evidência
**Status:** Vigente (ex-ADR-012) · **Requisitos:** EMP-001

**O texto.** O EMP-001 exige o modelo georreferenciado em UTM / SIRGAS 2000 e
não diz por qual estrutura do IFC a posição se prova. `IfcProjectedCRS` e
`IfcMapConversion` (LoGeoRef 50) só existem no IFC4; para IFC2X3 há convenção
de mercado por *psets* de extensão no `IfcSite` (`ePSet_MapConversion`, …).

**A leitura.** Exige-se IFC4 para o que depende de georreferenciamento; *pset*
de extensão não é evidência de LoGeoRef 50.

**Por quê, e o que se recusou.** A via por *pset* foi **recusada**, não adiada:
não é schema, e o veredito passaria a depender de convenção
não normalizada; IFC4 é requisito de informação verificável (ISO 19650); e o
modelo do estudo de caso já é IFC4.

**Efeito.** Limita o que se **conclui**, não o que se **abre**: IFC2X3 segue
aceito e analisável pelo programa de necessidades, com a premissa declarada na
interface — sistema no ADR-008.

---

## DN-04 — Alternativa normativa sem insumo público é remetida à análise humana, nunca omitida
**Status:** Vigente (ex-ADR-014) · **Requisitos:** ENQ-010.2, ENQ-011.2, EMP-025.2

**O texto.** Anexo I, itens 3.b e 3.c: além da distância caminhável, vale a
alternativa por transporte público (escolar; escolar ou coletivo). Não há
insumo público para ela — o ORS hospedado não roteia transporte público, não há
GTFS aberto dos municípios do estudo, o itinerário escolar não é publicado —,
nem para os empreendimentos contíguos do Anexo II, 4.I.a (EMP-025.2).

**A leitura.** Alternativa que a norma admite e que nenhum insumo público
examina é requisito **remetido**: ativo, executa e sai NÃO AVALIÁVEL
(`analise_humana_documental`), nomeando o insumo que faltaria e por quê — nem
"pendente", nem "fora do recorte".

**Por quê, e o que se recusou.** Deixá-la fora foi a intenção original, e foi
recusada: o pai veria um "ou" de membro único e reprovaria por uma via que
ninguém examinou. GTFS como insumo fica fora do recorte.

**Efeito.** Num "ou" (ENQ-010/011) o pai aprova e nunca reprova; num "e"
(EMP-025), reprova e nunca aprova. Sistema: `RegraRemetida` e o teto da
agregação (ADR-015).

---

## DN-05 — O recorte avalia só equipamentos de educação públicos, ativos e de atendimento geral; conveniadas entram como sensibilidade
**Status:** Vigente (ex-ADR-016) · **Requisitos:** ENQ-009, ENQ-010.1, ENQ-011.1 e pais

**O texto.** O Anexo I exige proximidade do terreno a equipamentos de educação
sem dizer que estabelecimento conta — rede, situação, atendimento, convênio —,
e o eixo tem 31 requisitos, mais do que o recorte do protótipo comporta.

**A leitura.** Entra no recorte o requisito com insumo de fonte nacional
automática, sem mapeamento semântico, sem vistoria como caminho normal e com
"Julg. humano complementar" = Não na base; sobre esse universo, por corte de
escopo, só a educação. Conta o equipamento de rede **pública**, **ativo** e de
**atendimento geral**; a privada conveniada fica fora da regra.

**Por quê, e o que se recusou.** O critério vem da base normativa, não do
implementador. Contar a conveniada foi recusado na regra, mas o número que ela
mudaria viaja ao lado do oficial (`sensibilidade_conveniadas`).

**Efeito.** Descarte contado e reportado por motivo; lacuna de cadastro sai
`insumo_suspeito`, nunca NÃO CONFORME (`core/dominio/equipamentos.py`,
`core/regras/base/distancia_equipamento.py`).

---

## DN-06 — O equipamento de educação compõe três fontes do Censo Escolar, com precedência por campo; a etapa vem da contagem de turmas
**Status:** Vigente (ex-ADR-017) · **Requisitos:** ENQ-009, ENQ-010.1, ENQ-011.1

**O texto.** ENQ-010.1/011.1 separam o fundamental em anos iniciais e finais, e
nenhuma fonte do INEP responde sozinha: o Catálogo de Escolas tem coordenada e
não separa a etapa (em Estrela, zero aptas a dois dos três requisitos); o
microdado `Tabela_Escola` tem rede e situação, sem coordenada nem etapa.

**A leitura.** Precedência **por campo**: identidade, rede e situação de
`Tabela_Escola`; etapa pela contagem de turmas de `Tabela_Turma` (turma > 0 é
oferta); coordenada, endereço e convênio do Catálogo — com procedência por campo.

**Por quê, e o que se recusou.** Recusaram-se os *proxies* de nome parecido,
conferidos contra o Catálogo em escala nacional: `IN_COMUM_FUND_AI` é
indicador de educação especial, não de etapa (daria 14 das 29 escolas de
Estrela como "fundamental I"), e `IN_PODER_PUBLICO_PARCERIA` não é `conveniada`.

**Efeito.** Composição em `core/infra/gis/inep.py`. O recorte municipal é
snapshot versionado com procedência por sha256, sem a base nacional (327 MB),
na disciplina de snapshot do ADR-030.

---

## DN-08 — Cláusula em vocabulário normativo superado não é traduzida; conclui-se só o que é invariante à leitura
**Status:** Vigente (ex-ADR-025) · **Requisitos:** EDI-024, EDI-024.1, EDI-024.2 (EDI-016 e EDI-036.3 sem regra)

**O texto.** A Portaria 489/2025 migrou parte das cláusulas de zona para as
doze classes da ABNT TR 15220-3-1:2024 e deixou outras nas oito zonas de 2005,
que a norma já não publica: telhado "1, 2 e 3" / "4 a 8" (4.III.i), ventilação
"7 e 8", esquadrias "6" e "7". A numeração não se preserva: Brasília era Z4
(≤ 0,4) e é 3B — lida pelo dígito, ≤ 0,6.

**A leitura.** Não se traduz entre edições — nem pelo dígito, nem por analogia,
nem por tabela que não seja da ABNT. As faixas do telhado particionam o
zoneamento de 2005: α ≤ 0,4 é conforme e α > 0,6 é não conforme **sob qualquer
leitura**; só (0,4; 0,6] é indecidível — NÃO AVALIÁVEL
(`analise_humana_documental`) com a causa declarada.

**Por quê, e o que se recusou.** Recusaram-se a leitura pelo dígito (muda
veredito de projeto real) e a remessa em bloco (descarta vereditos certos).
Obtida a tabela municipal da NBR 15220-3:2005 com procedência, revê-se esta DN.

**Efeito.** O invariante mora no pai: sistema no ADR-026; a zona, no ADR-030.

---

## DN-09 — Dispensa documental de um limite verificável é requisito próprio: a ferramenta a indica e não a conclui
**Status:** Vigente · **Requisitos:** EMP-068 (× EMP-025.2), EDI-036.4 (× EDI-019, EDI-024, EDI-036.1–036.3); sem regra: EMP-009/009.1, EDI-047.3, EDI-049.5, VAL-003.1

**O texto.** A Portaria afasta limites verificáveis por condição documental: o
Art. 4º, §§ 1º e 2º dispensa a contiguidade (obra federal, emergência ou
calamidade, imóvel da SPU — Portaria 1.079/2026); a Tab. 2 do Anexo III,
item 1.II.b–c, dispensa absortância e transmitância quando a envoltória
comprova desempenho intermediário ou superior; outras alíneas trocam o limite
por lei municipal, laudo ou anuência.

**A leitura.** A dispensa é requisito próprio, com linha própria e método
documental. Não muda o veredito da regra que ela afastaria: a regra diz o que o
modelo mostra, e a dispensa é matéria do analista.

**Por quê, e o que se recusou.** Recusou-se presumir a dispensa (aprovaria por
omissão), ignorá-la (a norma a concede) e pendurá-la como filho do agregador
implementado (a filiação é o contrato testado com o código, ADR-015).

**Efeito.** Registrada na base de requisitos
(`config/Base_Requisitos_Portaria_MCID_725.xlsx`, Leia-me, regra 5). A DN-01 já a registrava para o
telhado; vale também para a parede externa (EDI-019).
