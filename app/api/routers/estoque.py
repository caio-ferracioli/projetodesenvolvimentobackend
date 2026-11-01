from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import EQUIPE, GERENCIA, ContainerDep, Pagina, UsuarioAtual
from app.api.routers import erros
from app.api.schemas import (
    DisponibilidadeEntrada,
    EstoqueSaida,
    MovimentacaoEstoqueEntrada,
    MovimentacaoEstoqueSaida,
    PaginaSaida,
    paginar,
)
from app.domain.enums import TipoMovimentacaoEstoque

router = APIRouter(prefix="/estoque", tags=["Estoque"])


def _saida(estoque, produto) -> EstoqueSaida:
    return EstoqueSaida(
        id=estoque.id,
        unidade_id=estoque.unidade_id,
        produto_id=estoque.produto_id,
        produto_nome=produto.nome,
        quantidade=estoque.quantidade,
        disponivel=estoque.disponivel,
    )


@router.get(
    "",
    response_model=PaginaSaida[EstoqueSaida],
    summary="Saldo por unidade (equipe)",
    dependencies=[EQUIPE],
    responses=erros(401, 403, 422),
)
def saldos(
    c: ContainerDep,
    p: Pagina,
    ator: UsuarioAtual,
    unidade_id: Annotated[int | None, Query(alias="unidadeId", ge=1)] = None,
    produto_id: Annotated[int | None, Query(alias="produtoId", ge=1)] = None,
):
    pagina = c.estoque.listar(ator, unidade_id=unidade_id, produto_id=produto_id, page=p.page, limit=p.limit)
    return {
        "items": [_saida(e, prod) for e, prod in pagina.itens],
        "page": pagina.page,
        "limit": pagina.limit,
        "total": pagina.total,
        "pages": pagina.paginas,
    }


@router.get(
    "/movimentacoes",
    response_model=PaginaSaida[MovimentacaoEstoqueSaida],
    summary="Histórico de movimentações (equipe)",
    dependencies=[EQUIPE],
    responses=erros(401, 403, 422),
)
def movimentacoes(
    c: ContainerDep,
    p: Pagina,
    ator: UsuarioAtual,
    unidade_id: Annotated[int | None, Query(alias="unidadeId", ge=1)] = None,
    produto_id: Annotated[int | None, Query(alias="produtoId", ge=1)] = None,
):
    return paginar(
        c.estoque.listar_movimentacoes(
            ator, unidade_id=unidade_id, produto_id=produto_id, page=p.page, limit=p.limit
        ),
        MovimentacaoEstoqueSaida,
    )


@router.post(
    "/movimentacoes",
    status_code=201,
    response_model=MovimentacaoEstoqueSaida,
    summary="Entrada, saída ou ajuste de estoque (GERENTE, ADMIN)",
    responses=erros(401, 403, 404, 409, 422),
)
def registrar_movimentacao(dados: MovimentacaoEstoqueEntrada, c: ContainerDep, ator: UsuarioAtual, _=GERENCIA):
    return c.estoque.registrar_movimentacao(
        ator,
        unidade_id=dados.unidade_id,
        produto_id=dados.produto_id,
        tipo=TipoMovimentacaoEstoque(dados.tipo),
        quantidade=dados.quantidade,
        motivo=dados.motivo,
    )


@router.patch(
    "/{estoque_id}/disponibilidade",
    response_model=EstoqueSaida,
    summary="Bloqueia/libera a venda do item na unidade (GERENTE, ADMIN)",
    responses=erros(401, 403, 404, 422),
)
def disponibilidade(
    estoque_id: int, dados: DisponibilidadeEntrada, c: ContainerDep, ator: UsuarioAtual, _=GERENCIA
):
    estoque = c.estoque.definir_disponibilidade(ator, estoque_id, dados.disponivel)
    produto = c.catalogo.obter_produto(estoque.produto_id)
    return _saida(estoque, produto)
