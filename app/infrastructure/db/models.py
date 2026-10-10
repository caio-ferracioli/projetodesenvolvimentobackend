from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.enums import (
    CanalPedido,
    MetodoPagamento,
    Perfil,
    StatusPagamento,
    StatusPedido,
    TipoMovimentacaoEstoque,
    TipoMovimentacaoFidelidade,
)

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UTCDateTime(TypeDecorator):

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


def _agora() -> datetime:
    return datetime.now(UTC)


def _enum(cls: type, tamanho: int = 30) -> SAEnum:
    return SAEnum(cls, native_enum=False, length=tamanho, create_constraint=False, validate_strings=True)


class UnidadeModel(Base):
    __tablename__ = "unidades"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    cidade: Mapped[str] = mapped_column(String(80))
    endereco: Mapped[str | None] = mapped_column(String(200))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora)
    atualizado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora, onupdate=_agora)


class UsuarioModel(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[Perfil] = mapped_column(_enum(Perfil, 20), index=True)
    telefone: Mapped[str | None] = mapped_column(String(30))
    unidade_id: Mapped[int | None] = mapped_column(ForeignKey("unidades.id", ondelete="SET NULL"))
    consentimento_fidelidade: Mapped[bool] = mapped_column(Boolean, default=False)
    consentimento_em: Mapped[datetime | None] = mapped_column(UTCDateTime)
    anonimizado_em: Mapped[datetime | None] = mapped_column(UTCDateTime)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora)
    atualizado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora, onupdate=_agora)


class ProdutoModel(Base):
    __tablename__ = "produtos"
    __table_args__ = (CheckConstraint("preco >= 0", name="preco_nao_negativo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str | None] = mapped_column(Text)
    categoria: Mapped[str] = mapped_column(String(60), index=True)
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    removido_em: Mapped[datetime | None] = mapped_column(UTCDateTime)
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora)
    atualizado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora, onupdate=_agora)


class EstoqueModel(Base):
    __tablename__ = "estoques"
    __table_args__ = (
        UniqueConstraint("unidade_id", "produto_id", name="uq_estoques_unidade_produto"),
        CheckConstraint("quantidade >= 0", name="quantidade_nao_negativa"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"))
    quantidade: Mapped[int] = mapped_column(Integer, default=0)
    disponivel: Mapped[bool] = mapped_column(Boolean, default=True)


class MovimentacaoEstoqueModel(Base):
    __tablename__ = "movimentacoes_estoque"

    id: Mapped[int] = mapped_column(primary_key=True)
    estoque_id: Mapped[int] = mapped_column(ForeignKey("estoques.id"), index=True)
    tipo: Mapped[TipoMovimentacaoEstoque] = mapped_column(_enum(TipoMovimentacaoEstoque))
    variacao: Mapped[int] = mapped_column(Integer)
    saldo_apos: Mapped[int] = mapped_column(Integer)
    motivo: Mapped[str | None] = mapped_column(String(255))
    pedido_id: Mapped[int | None] = mapped_column(ForeignKey("pedidos.id", ondelete="SET NULL"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora)


class PedidoModel(Base):
    __tablename__ = "pedidos"
    __table_args__ = (
        UniqueConstraint("criado_por_id", "chave_idempotencia", name="uq_pedidos_chave_idempotencia"),
        Index("ix_pedidos_unidade_status", "unidade_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))
    canal_pedido: Mapped[CanalPedido] = mapped_column(_enum(CanalPedido, 20), index=True)
    status: Mapped[StatusPedido] = mapped_column(_enum(StatusPedido), index=True)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    observacao: Mapped[str | None] = mapped_column(String(255))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(255))
    chave_idempotencia: Mapped[str | None] = mapped_column(String(80))
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora)
    atualizado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora, onupdate=_agora)

    itens: Mapped[list["ItemPedidoModel"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", lazy="selectin", order_by="ItemPedidoModel.id"
    )


class ItemPedidoModel(Base):
    __tablename__ = "itens_pedido"
    __table_args__ = (CheckConstraint("quantidade > 0", name="quantidade_positiva"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id", ondelete="CASCADE"), index=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"))
    nome_produto: Mapped[str] = mapped_column(String(120))
    quantidade: Mapped[int] = mapped_column(Integer)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    pedido: Mapped[PedidoModel] = relationship(back_populates="itens")


class PagamentoModel(Base):
    __tablename__ = "pagamentos"
    __table_args__ = (
        Index(
            "uq_pagamentos_pendente_por_pedido",
            "pedido_id",
            unique=True,
            sqlite_where=text("status = 'PENDENTE'"),
            postgresql_where=text("status = 'PENDENTE'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"), index=True)
    metodo: Mapped[MetodoPagamento] = mapped_column(_enum(MetodoPagamento))
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[StatusPagamento] = mapped_column(_enum(StatusPagamento))
    transacao_externa: Mapped[str | None] = mapped_column(String(80), unique=True)
    mensagem: Mapped[str | None] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora)
    atualizado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora, onupdate=_agora)


class MovimentacaoFidelidadeModel(Base):
    __tablename__ = "movimentacoes_fidelidade"
    __table_args__ = (
        UniqueConstraint("pedido_id", "tipo", name="uq_movimentacoes_fidelidade_pedido_tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    pedido_id: Mapped[int | None] = mapped_column(ForeignKey("pedidos.id", ondelete="SET NULL"))
    tipo: Mapped[TipoMovimentacaoFidelidade] = mapped_column(_enum(TipoMovimentacaoFidelidade))
    pontos: Mapped[int] = mapped_column(Integer)
    descricao: Mapped[str | None] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora)


class AuditoriaModel(Base):
    __tablename__ = "auditorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    acao: Mapped[str] = mapped_column(String(60), index=True)
    entidade: Mapped[str | None] = mapped_column(String(60))
    entidade_id: Mapped[int | None] = mapped_column(Integer)
    detalhes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(45))
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime, default=_agora, index=True)
