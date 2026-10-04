# ADR-032 — O confronto da âncora do modelo com a poligonal do terreno é aviso, nunca veredito
**Status:** Aceita

## Contexto
O EMP-001 confere a estrutura do georreferenciamento (LoGeoRef 50) e a âncora
contra o município declarado (ADR-008), mas não a coordenada. Uma primeira
versão do modelo E1 do estudo de caso tinha nível 50, CRS e município certos e uma translação de 18,64 m que
deixava a âncora 11,73 m fora da gleba. Isso passou sem nenhum alerta.
Reprovar por isso seria errado: a âncora (origem do `IfcMapConversion`) não é
o modelo, e pode cair sobre a divisa ou fora do lote.

## Decisão
Dentro do EMP-001, a âncora precisa é medida contra a poligonal do `Terreno`
declarado, no CRS métrico da poligonal, e o resultado vai para
`detalhe["posicionamento_terreno"]` e para a mensagem. Há quatro estados:
- `dentro`: distância até **5 m**, contando a borda;
- `fora`;
- `nao_avaliado`, sempre com motivo: sem natureza declarada, sem poligonal ou
  com âncora aproximada do `IfcSite`;
- `nao_aplicavel`: `edificacao_isolada`, porque a tipologia não tem posição
  própria (ADR-023). Nesse caso a distância, quando mensurável, fica só como
  `distancia_informativa_m`.

**Assimetria na mesma regra:** o município reprova (escala de km, erro
inequívoco); a poligonal só avisa (escala de m, depende de tolerância). O aviso
diz "referência compatível com o terreno", nunca "modelo contido". Os 5 m
aceitam a âncora sobre o vértice M1 (0 m) e as divergências de centímetros
entre o DWG e o memorial, e pegam o caso dos 11,73 m.

## Consequências
Fica visível um erro de coordenada que a estrutura sozinha deixa passar. Não
se detecta um erro que empurre a âncora para dentro do terreno, nem se mede
contenção geométrica (pegada × terreno), que fica de fora até existir um
modelo de implantação. Não se pode reprovar, criar motivo ou regra por
causa deste aviso, nem deduzir a natureza do modelo pela âncora.

## Evidência
- `core/regras/gis_bim/emp_001_georreferenciamento.py`: `_confrontar_terreno`,
  `TOLERANCIA_POSICIONAMENTO_M`, `JUSTIFICATIVA_POSICIONAMENTO`.
- `app/componentes/paineis.py`: `render_posicionamento_terreno`.
- `tests/core/regras/gis_bim/test_emp_001.py`: `test_veredito_do_emp001_nao_depende_da_poligonal`
  e os casos M1, E1 na primeira versão (arquivo real), E1 corrigido e `edificacao_isolada`.

## Relações
Anota o ADR-008.
