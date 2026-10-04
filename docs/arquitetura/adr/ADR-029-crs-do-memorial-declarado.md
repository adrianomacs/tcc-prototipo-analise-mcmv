# ADR-029 — O CRS do CSV de memorial é declarado na importação, nunca deduzido das coordenadas
**Status:** Aceita

## Contexto
A entrada do terreno por CSV de memorial descritivo traz coordenadas
**projetadas** (E/N, UTM), e a planilha de cálculos real do estudo de caso —
como toda tabela de projeto de implantação — não declara CRS nenhum: nem
datum, nem fuso, nem hemisfério. Deduzir o CRS do próprio dado é impossível
por construção: o mesmo par E/N existe em todos os fusos UTM, nos dois
hemisférios — a dedução assumiria exatamente o que se quer descobrir. A
alternativa de exigir metadado de CRS dentro do arquivo tornaria o CSV
incompatível com a planilha real, que é o insumo que a entrada existe para
receber.

## Decisão
O CRS é uma **declaração do usuário no ato da importação** — nunca campo do
arquivo, nunca dedução das coordenadas. A tela sugere como padrão o EPSG
derivado do **município declarado** no empreendimento (fuso + hemisfério do
centro da malha IBGE → SIRGAS 2000 / UTM, `geometria.epsg_metrico`), e aceita
outro código EPSG projetado. O arquivo permanece tabela pura de vértices,
copiável de qualquer planilha de implantação. A declaração e a sua fonte ficam
na procedência (`epsg_origem`, `epsg_origem_fonte`: `sugerido_do_municipio` |
`informado_pelo_usuario`). Coordenadas locais/topográficas ficam fora: valor
implausível para UTM é recusado com explicação — sem amarração não há
território.

## Consequências
Fica fácil importar a planilha real sem editá-la. A escolha errada de fuso ou
hemisfério não passa em silêncio: a validação é em camadas — plausibilidade
das faixas E/N, área de uso oficial do CRS declarado (o mesmo raciocínio do
`leitor_crs`, um nível acima) e o confronto do centro com os limites
municipais na confirmação do terreno, que já existia e pega o erro grosseiro
de zona. Não se pode: deduzir CRS de coordenada projetada; aceitar memorial
sem amarração; nem levar EPSG de arquivo ao domínio — o `dominio/` segue
recebendo WGS 84 pronto (ADR-002).

## Evidência
- `core/infra/gis/csv_memorial.py` (adaptador; validações em camadas; CLI).
- `app/servicos/territorio.py`: `epsg_sugerido()`.
- `app/paginas/checagens/checagem_enquadramento.py` (modo CSV do memorial).
- `tests/core/infra/gis/test_csv_memorial.py`.
