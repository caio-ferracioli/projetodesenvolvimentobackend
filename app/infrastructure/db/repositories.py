from dataclasses import fields
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.entities import (
    Auditoria,
    Estoque,
    ItemPedido,
    MovimentacaoEstoque,
    MovimentacaoFidelidade,
    Pagamento,
    Pedido,
    Produto,
    Unidade,
    Usuario,
)
from app.domain.enums import CanalPedido, StatusPedido
from app.domain.errors import Conflito
from app.infrastructure.db import models as m


def _para_entidade(cls: type, linha: Any, **extras: Any) -> Any:
    dados = {f.name: getattr(linha, f.name) for f in fields(cls) if f.name not in extras}
    return cls(**dados, **extras)


def _para_linha(modelo: type, entidade: Any, ignorar: tuple[str, ...] = ("id",)) -> Any:
    return modelo(**{f.name: getattr(entidade, f.name) for f in fields(entidade) if f.name not in ignorar})


def _copiar_para_linha(linha: Any, entidade: Any, ignorar: tuple[str, ...] = ("id",)) -> None:
    for f in fields(entidade):
        if f.name not in ignorar:
            setattr(linha, f.name, getattr(entidade, f.name))


def _paginar(sessao: Session, consulta: Select, page: int, limit: int) -> tuple[list[Any], int]:
    total = sessao.scalar(select(func.count()).select_from(consulta.order_by(None).subquery())) or 0
    linhas = sessao.scalars(consulta.limit(limit).offset((page - 1) * limit)).all()
    return list(linhas), total


class _Repositorio:
    def __init__(self, sessao: Session):
        self._s = sessao

    def _inserir(self, modelo: type, entidade: Any, ignorar: tuple[str, ...] = ("id",)) -> Any:
        linha = _para_linha(modelo, entidade, ignorar)
        self._s.add(linha)
        self._s.flush()
        entidade.id = linha.id
        return entidade


class RepositorioUsuarios(_Repositorio):
    def obter(self, usuario_id: int) -> Usuario | None:
        linha = self._s.get(m.UsuarioModel, usuario_id)
        return _para_entidade(Usuario, linha) if linha else None

    def obter_por_email(self, email: str) -> Usuario | None:
        linha = self._s.scalar(select(m.UsuarioModel).where(m.UsuarioModel.email == email))
        return _para_entidade(Usuario, linha) if linha else None

    def adicionar(self, usuario: Usuario) -> Usuario:
        try:
            return self._inserir(m.UsuarioModel, usuario)
        except IntegrityError as erro:
            if "email" in str(erro.orig):
                raise Conflito("EMAIL_JA_CADASTRADO", "Já existe um usuário com este e-mail.") from erro
            raise

    def salvar(self, usuario: Usuario) -> None:
        _copiar_para_linha(self._s.get(m.UsuarioModel, usuario.id), usuario)
        self._s.flush()

    def listar(self, *, page: int, limit: int) -> tuple[list[Usuario], int]:
        linhas, total = _paginar(self._s, select(m.UsuarioModel).order_by(m.UsuarioModel.id), page, limit)
        return [_para_entidade(Usuario, ln) for ln in linhas], total


class RepositorioUnidades(_Repositorio):
    def obter(self, unidade_id: int) -> Unidade | None:
        linha = self._s.get(m.UnidadeModel, unidade_id)
        return _para_entidade(Unidade, linha) if linha else None

    def adicionar(self, unidade: Unidade) -> Unidade:
        return self._inserir(m.UnidadeModel, unidade)

    def salvar(self, unidade: Unidade) -> None:
        _copiar_para_linha(self._s.get(m.UnidadeModel, unidade.id), unidade)
        self._s.flush()

    def listar(self, *, page: int, limit: int) -> tuple[list[Unidade], int]:
        linhas, total = _paginar(self._s, select(m.UnidadeModel).order_by(m.UnidadeModel.id), page, limit)
        return [_para_entidade(Unidade, ln) for ln in linhas], total


class RepositorioProdutos(_Repositorio):
    def obter(self, produto_id: int) -> Produto | None:
        linha = self._s.get(m.ProdutoModel, produto_id)
        return _para_entidade(Produto, linha) if linha else None

    def obter_varios(self, ids: list[int]) -> dict[int, Produto]:
        linhas = self._s.scalars(select(m.ProdutoModel).where(m.ProdutoModel.id.in_(ids))).all()
        return {ln.id: _para_entidade(Produto, ln) for ln in linhas}

    def adicionar(self, produto: Produto) -> Produto:
        return self._inserir(m.ProdutoModel, produto)

    def salvar(self, produto: Produto) -> None:
        _copiar_para_linha(self._s.get(m.ProdutoModel, produto.id), produto)
        self._s.flush()

    def listar(
        self, *, categoria: str | None, busca: str | None, apenas_ativos: bool, page: int, limit: int
    ) -> tuple[list[Produto], int]:
        consulta = select(m.ProdutoModel).where(m.ProdutoModel.removido_em.is_(None))
        if apenas_ativos:
            consulta = consulta.where(m.ProdutoModel.ativo.is_(True))
        if categoria:
            consulta = consulta.where(m.ProdutoModel.categoria == categoria)
        if busca:
            consulta = consulta.where(m.ProdutoModel.nome.ilike(f"%{busca}%"))
        linhas, total = _paginar(self._s, consulta.order_by(m.ProdutoModel.id), page, limit)
        return [_para_entidade(Produto, ln) for ln in linhas], total


class RepositorioEstoques(_Repositorio):
    def obter_por_id(self, estoque_id: int) -> Estoque | None:
        linha = self._s.get(m.EstoqueModel, estoque_id)
        return _para_entidade(Estoque, linha) if linha else None

    def obter(self, unidade_id: int, produto_id: int) -> Estoque | None:
        linha = self._s.scalar(
            select(m.EstoqueModel).where(
                m.EstoqueModel.unidade_id == unidade_id, m.EstoqueModel.produto_id == produto_id
            )
        )
        return _para_entidade(Estoque, linha) if linha else None

    def obter_varios(self, unidade_id: int, produto_ids: list[int]) -> dict[int, Estoque]:
        linhas = self._s.scalars(
            select(m.EstoqueModel).where(
                m.EstoqueModel.unidade_id == unidade_id, m.EstoqueModel.produto_id.in_(produto_ids)
            )
        ).all()
        return {ln.produto_id: _para_entidade(Estoque, ln) for ln in linhas}

    def adicionar(self, estoque: Estoque) -> Estoque:
        return self._inserir(m.EstoqueModel, estoque)

    def salvar(self, estoque: Estoque) -> None:
        _copiar_para_linha(self._s.get(m.EstoqueModel, estoque.id), estoque)
        self._s.flush()

    def ajustar(self, estoque_id: int, delta: int) -> int | None:
        self._s.flush()
        resultado = self._s.execute(
            update(m.EstoqueModel)
            .where(m.EstoqueModel.id == estoque_id, m.EstoqueModel.quantidade + delta >= 0)
            .values(quantidade=m.EstoqueModel.quantidade + delta)
            .execution_options(synchronize_session=False)
        )
        if resultado.rowcount == 0:
            return None
        self._s.expire_all()
        return self._s.scalar(select(m.EstoqueModel.quantidade).where(m.EstoqueModel.id == estoque_id))

    def listar(
        self, *, unidade_id: int | None, produto_id: int | None, page: int, limit: int
    ) -> tuple[list[tuple[Estoque, Produto]], int]:
        consulta = select(m.EstoqueModel, m.ProdutoModel).join(
            m.ProdutoModel, m.ProdutoModel.id == m.EstoqueModel.produto_id
        )
        if unidade_id is not None:
            consulta = consulta.where(m.EstoqueModel.unidade_id == unidade_id)
        if produto_id is not None:
            consulta = consulta.where(m.EstoqueModel.produto_id == produto_id)
        consulta = consulta.order_by(m.EstoqueModel.unidade_id, m.ProdutoModel.nome)

        total = self._s.scalar(select(func.count()).select_from(consulta.order_by(None).subquery())) or 0
        pares = self._s.execute(consulta.limit(limit).offset((page - 1) * limit)).all()
        return [(_para_entidade(Estoque, e), _para_entidade(Produto, p)) for e, p in pares], total

    def cardapio(self, unidade_id: int) -> list[tuple[Produto, Estoque]]:
        pares = self._s.execute(
            select(m.ProdutoModel, m.EstoqueModel)
            .join(m.EstoqueModel, m.EstoqueModel.produto_id == m.ProdutoModel.id)
            .where(
                m.EstoqueModel.unidade_id == unidade_id,
                m.EstoqueModel.disponivel.is_(True),
                m.ProdutoModel.ativo.is_(True),
                m.ProdutoModel.removido_em.is_(None),
            )
            .order_by(m.ProdutoModel.categoria, m.ProdutoModel.nome)
        ).all()
        return [(_para_entidade(Produto, p), _para_entidade(Estoque, e)) for p, e in pares]

    def adicionar_movimentacao(self, mov: MovimentacaoEstoque) -> MovimentacaoEstoque:
        return self._inserir(m.MovimentacaoEstoqueModel, mov)

    def listar_movimentacoes(
        self, *, unidade_id: int | None, produto_id: int | None, page: int, limit: int
    ) -> tuple[list[MovimentacaoEstoque], int]:
        consulta = select(m.MovimentacaoEstoqueModel).join(
            m.EstoqueModel, m.EstoqueModel.id == m.MovimentacaoEstoqueModel.estoque_id
        )
        if unidade_id is not None:
            consulta = consulta.where(m.EstoqueModel.unidade_id == unidade_id)
        if produto_id is not None:
            consulta = consulta.where(m.EstoqueModel.produto_id == produto_id)
        linhas, total = _paginar(self._s, consulta.order_by(m.MovimentacaoEstoqueModel.id.desc()), page, limit)
        return [_para_entidade(MovimentacaoEstoque, ln) for ln in linhas], total


def _pedido_para_entidade(linha: m.PedidoModel) -> Pedido:
    itens = [_para_entidade(ItemPedido, i) for i in linha.itens]
    return _para_entidade(Pedido, linha, itens=itens)


class RepositorioPedidos(_Repositorio):
    def obter(self, pedido_id: int) -> Pedido | None:
        linha = self._s.get(m.PedidoModel, pedido_id)
        return _pedido_para_entidade(linha) if linha else None

    def obter_por_chave(self, criado_por_id: int, chave: str) -> Pedido | None:
        linha = self._s.scalar(
            select(m.PedidoModel).where(
                m.PedidoModel.criado_por_id == criado_por_id, m.PedidoModel.chave_idempotencia == chave
            )
        )
        return _pedido_para_entidade(linha) if linha else None

    def adicionar(self, pedido: Pedido) -> Pedido:
        linha = _para_linha(m.PedidoModel, pedido, ignorar=("id", "itens"))
        linha.itens = [_para_linha(m.ItemPedidoModel, i, ignorar=("id", "pedido_id")) for i in pedido.itens]
        self._s.add(linha)
        try:
            self._s.flush()
        except IntegrityError as erro:
            if "chave_idempotencia" in str(erro.orig):
                raise Conflito(
                    "CHAVE_IDEMPOTENCIA_DUPLICADA", "Já existe um pedido com esta chave de idempotência."
                ) from erro
            raise
        pedido.id = linha.id
        for entidade, nova in zip(pedido.itens, linha.itens, strict=True):
            entidade.id, entidade.pedido_id = nova.id, linha.id
        return pedido

    def salvar(self, pedido: Pedido) -> None:
        _copiar_para_linha(self._s.get(m.PedidoModel, pedido.id), pedido, ignorar=("id", "itens"))
        self._s.flush()

    def listar(
        self,
        *,
        cliente_id: int | None,
        unidade_id: int | None,
        canal_pedido: CanalPedido | None,
        status: StatusPedido | None,
        page: int,
        limit: int,
    ) -> tuple[list[Pedido], int]:
        consulta = select(m.PedidoModel)
        if cliente_id is not None:
            consulta = consulta.where(m.PedidoModel.cliente_id == cliente_id)
        if unidade_id is not None:
            consulta = consulta.where(m.PedidoModel.unidade_id == unidade_id)
        if canal_pedido is not None:
            consulta = consulta.where(m.PedidoModel.canal_pedido == canal_pedido)
        if status is not None:
            consulta = consulta.where(m.PedidoModel.status == status)
        linhas, total = _paginar(self._s, consulta.order_by(m.PedidoModel.id.desc()), page, limit)
        return [_pedido_para_entidade(ln) for ln in linhas], total


class RepositorioPagamentos(_Repositorio):
    def obter(self, pagamento_id: int) -> Pagamento | None:
        linha = self._s.get(m.PagamentoModel, pagamento_id)
        return _para_entidade(Pagamento, linha) if linha else None

    def obter_por_transacao(self, transacao_externa: str) -> Pagamento | None:
        linha = self._s.scalar(
            select(m.PagamentoModel).where(m.PagamentoModel.transacao_externa == transacao_externa)
        )
        return _para_entidade(Pagamento, linha) if linha else None

    def listar_do_pedido(self, pedido_id: int) -> list[Pagamento]:
        linhas = self._s.scalars(
            select(m.PagamentoModel).where(m.PagamentoModel.pedido_id == pedido_id).order_by(m.PagamentoModel.id)
        ).all()
        return [_para_entidade(Pagamento, ln) for ln in linhas]

    def adicionar(self, pagamento: Pagamento) -> Pagamento:
        try:
            return self._inserir(m.PagamentoModel, pagamento)
        except IntegrityError as erro:
            if "pagamentos" in str(erro.orig):
                raise Conflito(
                    "PAGAMENTO_EM_ANDAMENTO",
                    "Já existe um pagamento aguardando confirmação do gateway para este pedido.",
                ) from erro
            raise

    def salvar(self, pagamento: Pagamento) -> None:
        _copiar_para_linha(self._s.get(m.PagamentoModel, pagamento.id), pagamento)
        self._s.flush()


class RepositorioFidelidade(_Repositorio):
    def saldo(self, usuario_id: int) -> int:
        return (
            self._s.scalar(
                select(func.coalesce(func.sum(m.MovimentacaoFidelidadeModel.pontos), 0)).where(
                    m.MovimentacaoFidelidadeModel.usuario_id == usuario_id
                )
            )
            or 0
        )

    def adicionar(self, mov: MovimentacaoFidelidade) -> MovimentacaoFidelidade:
        return self._inserir(m.MovimentacaoFidelidadeModel, mov)

    def obter_do_pedido(self, pedido_id: int, tipo: str) -> MovimentacaoFidelidade | None:
        linha = self._s.scalar(
            select(m.MovimentacaoFidelidadeModel).where(
                m.MovimentacaoFidelidadeModel.pedido_id == pedido_id, m.MovimentacaoFidelidadeModel.tipo == tipo
            )
        )
        return _para_entidade(MovimentacaoFidelidade, linha) if linha else None

    def listar(self, usuario_id: int, *, limite: int) -> list[MovimentacaoFidelidade]:
        linhas = self._s.scalars(
            select(m.MovimentacaoFidelidadeModel)
            .where(m.MovimentacaoFidelidadeModel.usuario_id == usuario_id)
            .order_by(m.MovimentacaoFidelidadeModel.id.desc())
            .limit(limite)
        ).all()
        return [_para_entidade(MovimentacaoFidelidade, ln) for ln in linhas]


class RepositorioAuditorias(_Repositorio):
    def adicionar(self, auditoria: Auditoria) -> Auditoria:
        return self._inserir(m.AuditoriaModel, auditoria)

    def listar(
        self, *, acao: str | None, entidade: str | None, usuario_id: int | None, page: int, limit: int
    ) -> tuple[list[Auditoria], int]:
        consulta = select(m.AuditoriaModel)
        if acao:
            consulta = consulta.where(m.AuditoriaModel.acao == acao)
        if entidade:
            consulta = consulta.where(m.AuditoriaModel.entidade == entidade)
        if usuario_id is not None:
            consulta = consulta.where(m.AuditoriaModel.usuario_id == usuario_id)
        linhas, total = _paginar(self._s, consulta.order_by(m.AuditoriaModel.id.desc()), page, limit)
        return [_para_entidade(Auditoria, ln) for ln in linhas], total
