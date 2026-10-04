# ADR-008 — EMP-001 é portão da trilha espacial, não abortador global
**Status:** Aceita

> **Premissa IFC4.** Este ADR recebe a parte de sistema do antigo
> ADR-012, convertido na **DN-03** (IFC4 para georreferenciamento). A premissa
> é **declarada na interface** — ao lado do envio do modelo e sobre todo
> resultado que dependa dela, dizendo que a via por *pset* foi levantada e
> descartada — e **não é veto na porta**: IFC2X3 abre e segue analisável pelo
> programa de necessidades (lê `IfcSpace` e quantidades, iguais nos dois
> schemas), e o EMP-001 reporta LoGeoRef inalcançável. Evidência:
> `schema_suportavel()` e `PREMISSA_IFC4*` em `core/infra/ifc/leitor_modelo.py`;
> `aviso_premissa_ifc4()` em `app/componentes/avisos.py`;
> `tests/core/infra/ifc/test_leitor_modelo.py::test_a_premissa_nao_vira_veto_na_porta`.

> **Confronto com o terreno.** O EMP-001 tem um terceiro
> confronto, o da âncora com a poligonal do terreno. Esse confronto é **aviso**
> e não entra no portão nem no veredito (ADR-032).

## Contexto
O EMP-001 verifica se o modelo IFC está georreferenciado em UTM / SIRGAS 2000
com `IfcProjectedCRS` + `IfcMapConversion` (LoGeoRef 50). Uma leitura inicial
supôs que a reprovação dele deveria abortar a análise inteira, já que "sem
georreferenciamento não há análise espacial". A suposição estava errada:
georreferenciamento é pré-requisito de **uma trilha**, não de todas.

## Decisão
A falha do EMP-001 gateia apenas o que depende de posição derivada do modelo.
As regras de enquadramento (ENQ) declaram `depende_de = []` e `exige_terreno =
"ponto"`: o que elas exigem é um `Terreno` com centro válido, qualquer que seja
a procedência — poligonal desenhada no mapa, clique, digitação ou extração do
IFC. O gate de terreno é **atômico por regra** (uma regra dimensional não é
bloqueada porque outra exigia geometria). A alternativa — dependência
condicional à `terreno.origem` — foi considerada e **recusada**: o executor
resolve dependências por ordenação topológica estática, e dependência dinâmica
exigiria alterá-lo, risco desproporcional ao ganho.

## Consequências
Fica fácil avaliar o enquadramento de um empreendimento sem nenhum IFC — que é
como o módulo roda. Fica fácil, também, separar conformidade de
posicionabilidade: um modelo não conforme por datum estrangeiro continua
posicionável na cena 3D (ADR-009). Fica difícil explicar o EMP-001 em uma
frase: ele cumpre papel duplo, verificação normativa e porta da trilha
espacial, e a mensagem precisa distinguir "não conforme por datum/projeção" de
"sem georreferenciamento". Não se pode dar ao EMP-001 efeito global nem
introduzir dependência dinâmica entre regras.

## Evidência
- `core/regras/gis_bim/emp_001_georreferenciamento.py` (docstring "papel duplo";
  barra fixa em LoGeoRef 50; ressalva quando o confronto não é avaliável).
- `core/regras/base/distancia_equipamento.py`: `depende_de = []`,
  `exige_terreno = "ponto"` — herdado por ENQ-009/010.1/011.1.
- Gate atômico no executor: `Regra.exige_terreno` em
  `core/dominio/contratos/regra.py`.
- `tests/core/regras/gis_bim/test_emp_001.py` (a regra);
  `tests/core/infra/ifc/georref/test_logeoref.py` e `test_consistencia.py`
  (a leitura que a alimenta).
- `tests/core/regras/gis/test_enq_distancia.py` (as ENQ não dependem do portão),
  `tests/core/aplicacao/test_executor.py`, `tests/app/servicos/test_requisitos.py`.
