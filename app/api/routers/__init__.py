from typing import Any

from app.api.schemas import ErroSaida


def erros(*codigos: int) -> dict[int | str, dict[str, Any]]:
    descricoes = {
        401: "Sem token, token inválido/expirado ou credenciais erradas.",
        403: "Perfil sem permissão (ou recurso de outro usuário/unidade).",
        404: "Recurso inexistente.",
        409: "Conflito de estado: estoque insuficiente, transição inválida, duplicidade.",
        422: "Dados inválidos (campo ausente, formato errado, valor fora da regra).",
        503: "Gateway de pagamento indisponível.",
    }
    return {c: {"model": ErroSaida, "description": descricoes[c]} for c in codigos}
