import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import (
    AcessoNegado,
    Conflito,
    ErroDeDominio,
    NaoAutenticado,
    NaoEncontrado,
    RegraDeNegocio,
    ServicoIndisponivel,
)

logger = logging.getLogger("raizes.api")

STATUS_POR_ERRO: list[tuple[type[ErroDeDominio], int]] = [
    (NaoAutenticado, 401),
    (AcessoNegado, 403),
    (NaoEncontrado, 404),
    (Conflito, 409),
    (RegraDeNegocio, 422),
    (ServicoIndisponivel, 503),
]

CODIGOS_HTTP = {
    400: "REQUISICAO_INVALIDA",
    401: "NAO_AUTENTICADO",
    403: "ACESSO_NEGADO",
    404: "RECURSO_NAO_ENCONTRADO",
    405: "METODO_NAO_PERMITIDO",
    415: "TIPO_DE_MIDIA_NAO_SUPORTADO",
}


def resposta_erro(
    request: Request,
    status: int,
    codigo: str,
    mensagem: str,
    detalhes: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    corpo = {
        "status": status,
        "codigo": codigo,
        "mensagem": mensagem,
        "detalhes": jsonable_encoder(detalhes or []),
        "caminho": request.url.path,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return JSONResponse(status_code=status, content=corpo, headers=headers)


def traduzir(erro: dict[str, Any]) -> str:
    tipo, ctx = erro.get("type", ""), erro.get("ctx") or {}
    aceitos = str(ctx.get("expected", "")).replace(" or ", " ou ")
    mensagens = {
        "missing": "Campo obrigatório.",
        "json_invalid": "JSON malformado.",
        "string_type": "Deve ser um texto.",
        "int_type": "Deve ser um número inteiro.",
        "int_parsing": "Deve ser um número inteiro.",
        "bool_parsing": "Deve ser verdadeiro ou falso.",
        "bool_type": "Deve ser verdadeiro ou falso.",
        "decimal_parsing": "Deve ser um valor numérico.",
        "decimal_type": "Deve ser um valor numérico.",
        "decimal_max_places": f"Use no máximo {ctx.get('decimal_places')} casas decimais.",
        "decimal_max_digits": "Valor grande demais.",
        "model_attributes_type": "O corpo deve ser um objeto JSON.",
        "dict_type": "O corpo deve ser um objeto JSON.",
        "list_type": "Deve ser uma lista.",
        "greater_than_equal": f"Deve ser maior ou igual a {ctx.get('ge')}.",
        "greater_than": f"Deve ser maior que {ctx.get('gt')}.",
        "less_than_equal": f"Deve ser menor ou igual a {ctx.get('le')}.",
        "less_than": f"Deve ser menor que {ctx.get('lt')}.",
        "string_too_short": f"Deve ter no mínimo {ctx.get('min_length')} caracteres.",
        "string_too_long": f"Deve ter no máximo {ctx.get('max_length')} caracteres.",
        "too_short": f"Deve ter no mínimo {ctx.get('min_length')} item(ns).",
        "too_long": f"Deve ter no máximo {ctx.get('max_length')} item(ns).",
        "enum": f"Valor inválido. Valores aceitos: {aceitos}.",
        "literal_error": f"Valor inválido. Valores aceitos: {aceitos}.",
    }
    if tipo in mensagens:
        return mensagens[tipo]
    if "email" in str(erro.get("msg", "")).lower():
        return "E-mail inválido."
    return str(erro.get("msg", "Valor inválido."))


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ErroDeDominio)
    async def _dominio(request: Request, erro: ErroDeDominio) -> JSONResponse:
        status = next((s for tipo, s in STATUS_POR_ERRO if isinstance(erro, tipo)), 400)
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
        return resposta_erro(request, status, erro.codigo, erro.mensagem, erro.detalhes, headers)

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, erro: RequestValidationError) -> JSONResponse:
        detalhes = []
        for e in erro.errors():
            caminho = [str(parte) for parte in e["loc"][1:]] if e["loc"] and e["loc"][0] in (
                "body", "query", "path", "header"
            ) else [str(parte) for parte in e["loc"]]
            detalhes.append({"campo": ".".join(caminho) or "corpo", "mensagem": traduzir(e)})
        return resposta_erro(request, 422, "VALIDACAO_FALHOU", "Os dados enviados são inválidos.", detalhes)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, erro: StarletteHTTPException) -> JSONResponse:
        codigo = CODIGOS_HTTP.get(erro.status_code, "ERRO_HTTP")
        mensagem = "Rota não encontrada." if erro.status_code == 404 else str(erro.detail)
        return resposta_erro(request, erro.status_code, codigo, mensagem, headers=getattr(erro, "headers", None))

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, erro: Exception) -> JSONResponse:
        logger.exception("Erro não tratado em %s %s", request.method, request.url.path)
        return resposta_erro(request, 500, "ERRO_INTERNO", "Erro interno do servidor.")
