# ADR-031 — Ambiente com indício de defeito de autoria sai da população das regras e é reportado, nunca avaliado
**Status:** Aceita

## Contexto
Os Rooms do RVT real do Estrela I exportados como `IfcSpace` trazem dez
ambientes "fantasma": Room não colocado ou não fechado, que o Revit exporta
com a caixa padrão de 6' × 8' (1,829 × 2,438 m) em volta do ponto de
inserção e com a `NetFloorArea` do ambiente real. Lidos como legítimos, eles
produzem veredito falso com a cara de verdadeiro: o EDI-008 reprova a "sala"
de 1,83 m (a real tem 4,735 m), e o EDI-004 conta uma sala e um banheiro a
mais. A classificação já tem precedente: o covering não classificado do
ADR-027 fica fora do cálculo e aparece no relatório. Faltava a mesma regra
para ambiente, e ela muda a população que as regras avaliam. Um diagnóstico
do ADR-023 só marca, então isso é decisão de sistema.

## Decisão
`core/infra/ifc/extrator_ambientes.triar` separa os `IfcSpace` em
**população** e **fora da população**, por três sinais: (S1) ponto de
inserção coincidente com o de outro ambiente do mesmo pavimento; (S2) pegada
e área declarada divergindo mais que **1,10** (maior/menor); (S3) pegada
igual à caixa padrão de 6' × 8'. O ambiente sai com **dois sinais ou mais**.
Nenhum sinal marca sozinho. O exportador IFC2X3 do Revit põe todo `IfcSpace`
do pavimento no mesmo ponto (S1 em 41 ambientes legítimos do D1), e S3 é
convenção de um exportador só. As regras que leem ambientes (EDI-001/002,
EDI-004/004.1, EDI-007/008/009, EDI-011) avaliam só a população, e a soma da
área útil também exclui os fantasmas. Cada regra devolve os ambientes que
ficaram fora em `detalhe["fora_da_populacao"]`, com os sinais e os números
de cada um, e o cita na mensagem. Nada sai em silêncio.

## Consequências
O NC falso deixa de ter a cara do verdadeiro: no E2, o EDI-008 conclui sobre
as salas reais, e o relatório mostra o que foi excluído e por quê. Os
limiares vêm de medição. O pior legítimo nos 12 arquivos tem razão 1,0026, e
o fantasma mais discreto tem 1,09 (por isso a Cozinha só sai por S1 + S3).
Defeito de autoria que não produz dois sinais continua na população, como a
"Cozinha" vazada de 130,9 m² da cobertura: a pegada bate com a área e o
ponto é único. Fica declarado como limitação. Não se pode: corrigir,
reposicionar ou redimensionar o ambiente; avaliá-lo "com ressalva"; ou
retirar um ambiente por nome.

## Evidência
- `core/infra/ifc/extrator_ambientes.py`: `triar`, `Triagem`, sinais e limiares.
- `core/regras/bim/edi_001_002_area_util_uh.py`, `edi_004_programa_necessidades.py`,
  `edi_007_008_009_larguras.py`, `edi_011_varanda.py`.
- `tests/core/infra/ifc/test_extrator_ambientes.py` (um teste por sinal, com o dublê).
- `tests/scripts/test_cenarios_estrela_i.py` (E2 real: 5 salas, 8 banheiros).
