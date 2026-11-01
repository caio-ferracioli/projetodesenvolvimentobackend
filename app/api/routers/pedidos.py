from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.deps import ContainerDep, Pagina, UsuarioAtual, exigir_perfil
from app.api.routers import erros
from app.api.schemas import (
    PagamentoSaida,
    PaginaSaida,
    PedidoEntrada,
    PedidoSaida,
    StatusEntrada,
    paginar,
)
from app.application.pedidos import DetalhePedido, ItemSolicitado, NovoPedido
from app.domain.entities import Usuario
from app.domain.enums import CanalPedido, Perfil, StatusPedido

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

QUEM_PEDE = exigir_perfil(Perfil.CLIENTE, Perfil.ATENDENTE, Perfil.GERENTE, Perfil.ADMIN)


def pedido_saida(detalhe: DetalhePedido) -> PedidoSaida:
    saida = PedidoSaida.model_validate(detalhe.pedido)
    if detalhe.pagamento:
        saida.pagamento = PagamentoSaida.model_validate(detalhe.pagamento)
    return saida


@router.get(
    "",
    response_model=PaginaSaida[PedidoSaida],
    summary="Lista pedidos (filtra por canalPedido e status)",
    responses=erros(401, 422),
)
def listar(
    c: ContainerDep,
    p: Pagina,
    ator: UsuarioAtual,
    canal_pedido: Annotated[
        CanalPedido | None, Query(alias="canalPedido", description="APP, TOTEM, BALCAO, PICKUP ou WEB.")
    ] = None,
    status: Annotated[StatusPedido | None, Query()] = None,
    unidade_id: Annotated[int | None, Query(alias="unidadeId", ge=1)] = None,
):
    return paginar(
        c.pedidos.listar(
            ator, canal_pedido=canal_pedido, status=status, unidade_id=unidade_id, page=p.page, limit=p.limit
        ),
        PedidoSaida,
    )


@router.post(
    "",
    status_code=201,
    response_model=PedidoSaida,
    summary="Cria pedido (valida itens e estoque)",
    responses=erros(401, 403, 404, 409, 422)
    | {200: {"description": "Replay: mesma `Idempotency-Key` já usada, devolve o pedido original."}},
)
def criar(
    dados: PedidoEntrada,
    response: Response,
    c: ContainerDep,
    ator: Annotated[Usuario, Depends(QUEM_PEDE)],
    idempotency_key: Annotated[
        str | None,
        Header(
            max_length=80,
            description="Opcional. Reenviar a mesma chave não cria outro pedido (útil em retry de rede).",
        ),
    ] = None,
):
    detalhe, criado = c.pedidos.criar(
        ator,
        NovoPedido(
            unidade_id=dados.unidade_id,
            canal_pedido=dados.canal_pedido,
            itens=[ItemSolicitado(i.produto_id, i.quantidade) for i in dados.itens],
            observacao=dados.observacao,
            cliente_id=dados.cliente_id,
            chave_idempotencia=idempotency_key,
        ),
    )
    if not criado:
        response.status_code = 200
        response.headers["Idempotency-Replayed"] = "true"
    return pedido_saida(detalhe)


@router.get("/{pedido_id}", response_model=PedidoSaida, summary="Detalha um pedido", responses=erros(401, 403, 404))
def obter(pedido_id: int, c: ContainerDep, ator: UsuarioAtual):
    return pedido_saida(c.pedidos.obter(ator, pedido_id))


@router.patch(
    "/{pedido_id}/status",
    response_model=PedidoSaida,
    summary="Atualiza o status (PRONTO, ENTREGUE ou CANCELADO)",
    responses=erros(401, 403, 404, 409, 422),
)
def atualizar_status(pedido_id: int, dados: StatusEntrada, c: ContainerDep, ator: UsuarioAtual):
    return pedido_saida(c.pedidos.atualizar_status(ator, pedido_id, dados.status, dados.motivo))
