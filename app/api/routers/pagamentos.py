from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.deps import ContainerDep, UsuarioAtual
from app.api.routers import erros
from app.api.schemas import CallbackEntrada, CallbackSaida, PagamentoEntrada, PagamentoSaida
from app.domain.enums import StatusPagamento
from app.domain.errors import NaoAutenticado
from app.infrastructure.seguranca import assinatura_valida

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])


@router.post(
    "",
    status_code=201,
    response_model=PagamentoSaida,
    summary="Inicia o pagamento de um pedido (gateway mock, assíncrono)",
    responses=erros(401, 403, 404, 409, 422, 503),
)
def iniciar(dados: PagamentoEntrada, background: BackgroundTasks, c: ContainerDep, ator: UsuarioAtual):
    pagamento = c.pagamentos.iniciar(
        ator, pedido_id=dados.pedido_id, metodo=dados.metodo, token=dados.token_pagamento
    )
    background.add_task(c.entregar_callbacks_do_gateway)
    return pagamento


@router.post(
    "/webhook",
    response_model=CallbackSaida,
    summary="Callback do gateway (assinado com HMAC-SHA256)",
    responses=erros(401, 404, 422),
)
async def webhook(
    request: Request,
    c: ContainerDep,
    x_signature: Annotated[
        str | None,
        Header(description="HMAC-SHA256 (hex) do corpo bruto da requisição, com `WEBHOOK_SECRET` como chave."),
    ] = None,
):
    corpo = await request.body()
    if not assinatura_valida(c.settings.webhook_secret, corpo, x_signature):
        raise NaoAutenticado("ASSINATURA_INVALIDA", "Assinatura do webhook ausente ou inválida.")

    try:
        dados = CallbackEntrada.model_validate_json(corpo)
    except ValidationError as erro:
        raise RequestValidationError([{**e, "loc": ("body", *e["loc"])} for e in erro.errors()]) from None

    resultado = await run_in_threadpool(
        c.pagamentos.processar_callback,
        transacao_id=dados.transacao_id,
        aprovado=dados.status == "APROVADO",
        mensagem=dados.mensagem,
    )
    return CallbackSaida(
        pagamento_id=resultado.pagamento.id,
        status_pagamento=StatusPagamento(resultado.pagamento.status),
        status_pedido=resultado.status_pedido,
        processado=resultado.processado,
    )


@router.get(
    "/{pagamento_id}",
    response_model=PagamentoSaida,
    summary="Consulta um pagamento",
    responses=erros(401, 403, 404),
)
def obter(pagamento_id: int, c: ContainerDep, ator: UsuarioAtual):
    return c.pagamentos.obter(ator, pagamento_id)
