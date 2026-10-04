"""Veredito do grupo e formatação de percentual — funções puras sobre o
`resumo`, sem nenhuma dependência de Streamlit (testáveis isoladas).

"""

from __future__ import annotations

from core.regras.base.agregacao import CONTA_CONFIRMADO  # noqa: F401 (reexportado)

COR_ESTADO = {"conforme": "#34a853", "nao_conforme": "#ea4335", "nao_avaliavel": "#fbbc04"}
ROTULO_ESTADO = {"conforme": "Conforme", "nao_conforme": "Não conforme", "nao_avaliavel": "Não avaliável"}


def _veredito_geral(resumo: dict) -> tuple[str, str]:
    """Veredito do grupo, contado sobre os REQUISITOS da Portaria.

    Usa o bloco ``normativo`` do resumo, não as linhas executadas. A
    diferença é visível e importa: um requisito aprovado pela alternativa
    por distância tem a outra alternativa remetida a parecer, e contar as
    linhas faria o grupo sair "Conforme com ressalvas" por causa dela —
    quando a Portaria diz que **qualquer** das alternativas satisfaz o
    critério, e portanto não há ressalva alguma a fazer.

    O fallback para o próprio resumo mantém relatórios antigos (e os grupos
    sem agregação, onde os dois universos coincidem) funcionando.
    """
    norm = resumo.get("normativo") or resumo
    if norm.get("nao_conforme", 0) > 0:
        return "Não conforme", COR_ESTADO["nao_conforme"]
    if norm.get("nao_avaliavel", 0) > 0:
        return "Conforme com ressalvas", COR_ESTADO["nao_avaliavel"]
    if norm.get("conforme", 0) > 0:
        return "Conforme", COR_ESTADO["conforme"]
    return "Sem regras avaliadas", "#888"


def _pct(valor) -> str:
    """Percentual, ou "—" quando o número não existe.

    ``None`` é o caso em que nada foi avaliado: mostrar "0%" ali afirmaria
    que nenhum requisito está conforme, o que é afirmação sobre conjunto
    vazio.
    """
    return "—" if valor is None else f"{valor * 100:.0f}%"


def explicacao_do_resultado(norm: dict) -> str:
    """Por que o conjunto tem o resultado que tem — a linha de baixo do card
    de síntese (ADR-034), contada em requisitos da Portaria (bloco
    ``normativo``). Usada no "Resultado final" de cada checagem e no card do
    Relatório de Checagem."""
    nc, na, c = (norm.get("nao_conforme", 0), norm.get("nao_avaliavel", 0),
                 norm.get("conforme", 0))
    if nc:
        return ("1 requisito não atende à Portaria; basta um para o conjunto "
                "não ser conforme." if nc == 1 else
                f"{nc} requisitos não atendem à Portaria; basta um para o "
                "conjunto não ser conforme.")
    if na:
        return ("Nenhum requisito avaliado reprova, mas "
                + ("1 não pôde ser avaliado" if na == 1 else
                   f"{na} não puderam ser avaliados")
                + " com o insumo entregue.")
    if c:
        return "Todos os requisitos avaliados atendem à Portaria."
    return ""


def contagens_em_requisitos(norm: dict) -> str:
    """ "2 conformes · 1 não conforme · 1 não avaliável, em 4 requisitos da
    Portaria" — a legenda única das contagens (ADR-034): conta requisitos,
    com as alternativas de um mesmo requisito valendo como um só."""
    def plural(n, s, p):
        return f"{n} {s if n == 1 else p}"
    total = norm.get("total", 0)
    return (f"{plural(norm.get('conforme', 0), 'conforme', 'conformes')} · "
            f"{plural(norm.get('nao_conforme', 0), 'não conforme', 'não conformes')} · "
            f"{plural(norm.get('nao_avaliavel', 0), 'não avaliável', 'não avaliáveis')}, "
            f"em {plural(total, 'requisito', 'requisitos')} da Portaria")

