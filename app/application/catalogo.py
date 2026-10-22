from decimal import Decimal

from app.application.comum import FabricaUoW, Pagina, registrar_auditoria
from app.domain.entities import Estoque, Produto, Unidade, Usuario, agora, arredondar
from app.domain.errors import NaoEncontrado


class ServicoCatalogo:
    def __init__(self, uow: FabricaUoW):
        self._uow = uow


    def listar_unidades(self, *, page: int, limit: int) -> Pagina[Unidade]:
        with self._uow() as uow:
            itens, total = uow.unidades.listar(page=page, limit=limit)
        return Pagina(itens, page, limit, total)

    def obter_unidade(self, unidade_id: int) -> Unidade:
        with self._uow() as uow:
            return _unidade_ou_404(uow, unidade_id)

    def criar_unidade(
        self, ator: Usuario, *, nome: str, cidade: str, endereco: str | None, ativa: bool
    ) -> Unidade:
        with self._uow() as uow:
            unidade = uow.unidades.adicionar(Unidade(nome=nome, cidade=cidade, endereco=endereco, ativa=ativa))
            registrar_auditoria(
                uow, "UNIDADE_CRIADA", entidade="Unidade", entidade_id=unidade.id, usuario_id=ator.id
            )
            uow.commit()
            return unidade

    def atualizar_unidade(
        self, ator: Usuario, unidade_id: int, *, nome: str, cidade: str, endereco: str | None, ativa: bool
    ) -> Unidade:
        with self._uow() as uow:
            unidade = _unidade_ou_404(uow, unidade_id)
            unidade.nome, unidade.cidade, unidade.endereco, unidade.ativa = nome, cidade, endereco, ativa
            unidade.atualizado_em = agora()
            uow.unidades.salvar(unidade)
            registrar_auditoria(
                uow,
                "UNIDADE_ATUALIZADA",
                entidade="Unidade",
                entidade_id=unidade.id,
                detalhes={"ativa": ativa},
                usuario_id=ator.id,
            )
            uow.commit()
            return unidade

    def cardapio(self, unidade_id: int) -> tuple[Unidade, list[tuple[Produto, Estoque]]]:
        with self._uow() as uow:
            unidade = _unidade_ou_404(uow, unidade_id)
            return unidade, uow.estoques.cardapio(unidade_id)


    def listar_produtos(
        self, *, categoria: str | None, busca: str | None, apenas_ativos: bool, page: int, limit: int
    ) -> Pagina[Produto]:
        with self._uow() as uow:
            itens, total = uow.produtos.listar(
                categoria=categoria, busca=busca, apenas_ativos=apenas_ativos, page=page, limit=limit
            )
        return Pagina(itens, page, limit, total)

    def obter_produto(self, produto_id: int) -> Produto:
        with self._uow() as uow:
            return _produto_ou_404(uow, produto_id)

    def criar_produto(
        self,
        ator: Usuario,
        *,
        nome: str,
        descricao: str | None,
        categoria: str,
        preco: Decimal,
        ativo: bool,
    ) -> Produto:
        with self._uow() as uow:
            produto = uow.produtos.adicionar(
                Produto(
                    nome=nome,
                    descricao=descricao,
                    categoria=categoria,
                    preco=arredondar(preco),
                    ativo=ativo,
                )
            )
            registrar_auditoria(
                uow,
                "PRODUTO_CRIADO",
                entidade="Produto",
                entidade_id=produto.id,
                detalhes={"preco": produto.preco},
                usuario_id=ator.id,
            )
            uow.commit()
            return produto

    def atualizar_produto(
        self,
        ator: Usuario,
        produto_id: int,
        *,
        nome: str,
        descricao: str | None,
        categoria: str,
        preco: Decimal,
        ativo: bool,
    ) -> Produto:
        with self._uow() as uow:
            produto = _produto_ou_404(uow, produto_id)
            preco_anterior = produto.preco
            produto.nome, produto.descricao, produto.categoria = nome, descricao, categoria
            produto.preco, produto.ativo = arredondar(preco), ativo
            produto.atualizado_em = agora()
            uow.produtos.salvar(produto)
            registrar_auditoria(
                uow,
                "PRODUTO_ATUALIZADO",
                entidade="Produto",
                entidade_id=produto.id,
                detalhes={"precoAnterior": preco_anterior, "preco": produto.preco, "ativo": ativo},
                usuario_id=ator.id,
            )
            uow.commit()
            return produto

    def remover_produto(self, ator: Usuario, produto_id: int) -> None:
        with self._uow() as uow:
            produto = _produto_ou_404(uow, produto_id)
            produto.removido_em = agora()
            produto.ativo = False
            uow.produtos.salvar(produto)
            registrar_auditoria(
                uow, "PRODUTO_REMOVIDO", entidade="Produto", entidade_id=produto.id, usuario_id=ator.id
            )
            uow.commit()


def _unidade_ou_404(uow, unidade_id: int) -> Unidade:
    unidade = uow.unidades.obter(unidade_id)
    if unidade is None:
        raise NaoEncontrado("UNIDADE_NAO_ENCONTRADA", "Unidade não encontrada.")
    return unidade


def _produto_ou_404(uow, produto_id: int) -> Produto:
    produto = uow.produtos.obter(produto_id)
    if produto is None or produto.removido_em is not None:
        raise NaoEncontrado("PRODUTO_NAO_ENCONTRADO", "Produto não encontrado.")
    return produto
