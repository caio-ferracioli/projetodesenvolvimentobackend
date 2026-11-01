from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import GERENCIA, SOMENTE_ADMIN, ContainerDep, Pagina, UsuarioAtual
from app.api.routers import erros
from app.api.schemas import (
    CardapioItemSaida,
    CardapioSaida,
    PaginaSaida,
    ProdutoEntrada,
    ProdutoSaida,
    UnidadeEntrada,
    UnidadeSaida,
    paginar,
)

unidades = APIRouter(prefix="/unidades", tags=["Unidades"])
produtos = APIRouter(prefix="/produtos", tags=["Produtos"])


@unidades.get("", response_model=PaginaSaida[UnidadeSaida], summary="Lista unidades", responses=erros(401, 422))
def listar_unidades(c: ContainerDep, p: Pagina, _: UsuarioAtual):
    return paginar(c.catalogo.listar_unidades(page=p.page, limit=p.limit), UnidadeSaida)


@unidades.get(
    "/{unidade_id}/cardapio",
    response_model=CardapioSaida,
    summary="Cardápio da unidade (público)",
    responses=erros(404),
)
def cardapio(unidade_id: int, c: ContainerDep):
    unidade, linhas = c.catalogo.cardapio(unidade_id)
    return CardapioSaida(
        unidade=UnidadeSaida.model_validate(unidade),
        itens=[
            CardapioItemSaida(
                produto_id=produto.id,
                nome=produto.nome,
                descricao=produto.descricao,
                categoria=produto.categoria,
                preco=produto.preco,
                disponivel=estoque.quantidade > 0,
            )
            for produto, estoque in linhas
        ],
    )


@unidades.get("/{unidade_id}", response_model=UnidadeSaida, summary="Detalha uma unidade", responses=erros(401, 404))
def obter_unidade(unidade_id: int, c: ContainerDep, _: UsuarioAtual):
    return c.catalogo.obter_unidade(unidade_id)


@unidades.post(
    "",
    status_code=201,
    response_model=UnidadeSaida,
    summary="Cria unidade (ADMIN)",
    responses=erros(401, 403, 422),
)
def criar_unidade(dados: UnidadeEntrada, c: ContainerDep, ator: UsuarioAtual, _=SOMENTE_ADMIN):
    return c.catalogo.criar_unidade(
        ator, nome=dados.nome, cidade=dados.cidade, endereco=dados.endereco, ativa=dados.ativa
    )


@unidades.put(
    "/{unidade_id}",
    response_model=UnidadeSaida,
    summary="Atualiza unidade (ADMIN)",
    responses=erros(401, 403, 404, 422),
)
def atualizar_unidade(
    unidade_id: int, dados: UnidadeEntrada, c: ContainerDep, ator: UsuarioAtual, _=SOMENTE_ADMIN
):
    return c.catalogo.atualizar_unidade(
        ator, unidade_id, nome=dados.nome, cidade=dados.cidade, endereco=dados.endereco, ativa=dados.ativa
    )


@produtos.get("", response_model=PaginaSaida[ProdutoSaida], summary="Lista produtos", responses=erros(401, 422))
def listar_produtos(
    c: ContainerDep,
    p: Pagina,
    _: UsuarioAtual,
    categoria: Annotated[str | None, Query(max_length=60)] = None,
    q: Annotated[str | None, Query(max_length=60, description="Busca pelo nome.")] = None,
    apenas_ativos: Annotated[bool, Query(alias="apenasAtivos")] = True,
):
    return paginar(
        c.catalogo.listar_produtos(
            categoria=categoria, busca=q, apenas_ativos=apenas_ativos, page=p.page, limit=p.limit
        ),
        ProdutoSaida,
    )


@produtos.get("/{produto_id}", response_model=ProdutoSaida, summary="Detalha um produto", responses=erros(401, 404))
def obter_produto(produto_id: int, c: ContainerDep, _: UsuarioAtual):
    return c.catalogo.obter_produto(produto_id)


@produtos.post(
    "",
    status_code=201,
    response_model=ProdutoSaida,
    summary="Cadastra produto (GERENTE, ADMIN)",
    responses=erros(401, 403, 422),
)
def criar_produto(dados: ProdutoEntrada, c: ContainerDep, ator: UsuarioAtual, _=GERENCIA):
    return c.catalogo.criar_produto(
        ator,
        nome=dados.nome,
        descricao=dados.descricao,
        categoria=dados.categoria,
        preco=dados.preco,
        ativo=dados.ativo,
    )


@produtos.put(
    "/{produto_id}",
    response_model=ProdutoSaida,
    summary="Atualiza produto (GERENTE, ADMIN)",
    responses=erros(401, 403, 404, 422),
)
def atualizar_produto(produto_id: int, dados: ProdutoEntrada, c: ContainerDep, ator: UsuarioAtual, _=GERENCIA):
    return c.catalogo.atualizar_produto(
        ator,
        produto_id,
        nome=dados.nome,
        descricao=dados.descricao,
        categoria=dados.categoria,
        preco=dados.preco,
        ativo=dados.ativo,
    )


@produtos.delete(
    "/{produto_id}",
    status_code=204,
    response_class=Response,
    summary="Remove produto — exclusão lógica (GERENTE, ADMIN)",
    responses=erros(401, 403, 404),
)
def remover_produto(produto_id: int, c: ContainerDep, ator: UsuarioAtual, _=GERENCIA):
    c.catalogo.remover_produto(ator, produto_id)
    return Response(status_code=204)
