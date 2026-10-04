# ADR-005 — Uma regra = um arquivo, com registro por autodescoberta
**Status:** Aceita

## Contexto
A base de requisitos do PMCMV tem 299 itens atômicos; o protótipo implementa um
recorte e precisa crescer requisito a requisito, sem que acrescentar uma
checagem obrigue a editar o motor. Uma lista central de regras — dicionário ou
`if/elif` no executor — transforma cada requisito novo em alteração de código
compartilhado, exatamente onde um erro afeta todos os vereditos.

## Decisão
Cada checagem é um módulo autocontido em `core/regras/<bim|gis|gis_bim>/`,
com uma subclasse de `Regra` que declara seu próprio metadado como atributos
de classe (`id`, `dominio`, `descricao`, `depende_de`, `agrega`, `ids_spec`,
`alvo`, `verbo`, `parametro`, `insumos`, `exige_terreno`, `aplicabilidade`,
`remete_a`) e implementa um único método, `checar(ctx)`. Um registro central
com autodescoberta encontra as regras sozinho: o decorador `@registrar` inscreve
a classe e `descobrir()` importa recursivamente `core.regras` com
`pkgutil.walk_packages`. **Acrescentar uma regra = criar um arquivo**; o
executor não muda. Id duplicado levanta `ValueError` no import — falha alta e
imediata, não veredito silencioso. A subpasta acompanha o domínio declarado no
metadado da regra (`bim/`, `gis/` ou `gis_bim/`), e não o tipo de arquivo que
ela lê.

## Consequências
Fica fácil rastrear requisito → arquivo → teste e desativar seleções por
configuração (`config/regras_ativas.yaml`, `grupos_requisitos.yaml`) sem tocar
no código. Fica difícil renomear pacote de regra: a autodescoberta é por
varredura, e a coexistência de um pacote antigo com o novo derruba a suíte
inteira com "Regra duplicada" — por isso uma mudança de pacote move as regras
de uma só vez, sem fachada. Não se pode editar o executor para acomodar uma regra
específica: metadado declarativo é o único canal de comunicação regra → motor.

## Evidência
- `core/regras/registro.py` (`registrar`, `descobrir`, `regras_registradas`,
  CLI `python -m core.regras.registro --listar`).
- `core/dominio/contratos/regra.py` (classe-base `Regra` e o metadado).
- 25 regras no registro, cada uma na pasta do domínio que declara: 8 em
  `core/regras/bim/`, 10 em `core/regras/gis/` e 7 em `core/regras/gis_bim/`.
- `tests/core/aplicacao/test_executor.py` (registro e execução),
  `tests/core/regras/base/test_agregacao.py`.
- Lacuna conhecida: não há teste unitário dedicado às regras `edi_*`.
