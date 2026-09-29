from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.domain.enums import (
    CanalPedido,
    MetodoPagamento,
    Perfil,
    StatusPagamento,
    StatusPedido,
    TipoMovimentacaoEstoque,
    TipoMovimentacaoFidelidade,
)
from app.domain.errors import Conflito

CENTAVO = Decimal("0.01")
PONTOS_POR_REAL = 1


def agora() -> datetime:
    return datetime.now(UTC)


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def calcular_pontos(valor_total: Decimal) -> int:
    return int(valor_total) * PONTOS_POR_REAL


@dataclass(kw_only=True)
class Unidade:
    id: int | None = None
    nome: str
    cidade: str
    endereco: str | None = None
    ativa: bool = True
    criado_em: datetime = field(default_factory=agora)
    atualizado_em: datetime = field(default_factory=agora)


@dataclass(kw_only=True)
class Usuario:
    id: int | None = None
    nome: str
    email: str
    senha_hash: str
    perfil: Perfil
    telefone: str | None = None
    unidade_id: int | None = None
    consentimento_fidelidade: bool = False
    consentimento_em: datetime | None = None
    anonimizado_em: datetime | None = None
    criado_em: datetime = field(default_factory=agora)
    atualizado_em: datetime = field(default_factory=agora)

    @property
    def anonimizado(self) -> bool:
        return self.anonimizado_em is not None

    def definir_consentimento(self, consentiu: bool) -> None:
        self.consentimento_fidelidade = consentiu
        self.consentimento_em = agora() if consentiu else None

    def anonimizar(self) -> None:
        self.nome = "Titular anonimizado"
        self.email = f"anonimizado-{self.id}@anonimo.invalid"
        self.telefone = None
        self.senha_hash = "!"
        self.consentimento_fidelidade = False
        self.consentimento_em = None
        self.anonimizado_em = agora()


@dataclass(kw_only=True)
class Produto:
    id: int | None = None
    nome: str
    descricao: str | None = None
    categoria: str
    preco: Decimal
    ativo: bool = True
    removido_em: datetime | None = None
    criado_em: datetime = field(default_factory=agora)
    atualizado_em: datetime = field(default_factory=agora)

    @property
    def vendavel(self) -> bool:
        return self.ativo and self.removido_em is None


@dataclass(kw_only=True)
class Estoque:

    id: int | None = None
    unidade_id: int
    produto_id: int
    quantidade: int = 0
    disponivel: bool = True

    def pode_atender(self, quantidade: int) -> bool:
        return self.disponivel and self.quantidade >= quantidade


@dataclass(kw_only=True)
class MovimentacaoEstoque:
    id: int | None = None
    estoque_id: int
    tipo: TipoMovimentacaoEstoque
    variacao: int
    saldo_apos: int
    motivo: str | None = None
    pedido_id: int | None = None
    usuario_id: int | None = None
    criado_em: datetime = field(default_factory=agora)


@dataclass(kw_only=True)
class ItemPedido:
    id: int | None = None
    pedido_id: int | None = None
    produto_id: int
    nome_produto: str
    quantidade: int
    preco_unitario: Decimal
    subtotal: Decimal


@dataclass(kw_only=True)
class Pedido:
    id: int | None = None
    cliente_id: int | None = None
    criado_por_id: int | None = None
    unidade_id: int
    canal_pedido: CanalPedido
    status: StatusPedido = StatusPedido.AGUARDANDO_PAGAMENTO
    valor_total: Decimal = Decimal("0.00")
    observacao: str | None = None
    motivo_cancelamento: str | None = None
    chave_idempotencia: str | None = None
    itens: list[ItemPedido] = field(default_factory=list)
    criado_em: datetime = field(default_factory=agora)
    atualizado_em: datetime = field(default_factory=agora)

    def recalcular_total(self) -> Decimal:
        self.valor_total = arredondar(sum((i.subtotal for i in self.itens), Decimal("0")))
        return self.valor_total

    def transicionar(self, novo: StatusPedido) -> None:
        if not self.status.pode_ir_para(novo):
            raise Conflito(
                "TRANSICAO_STATUS_INVALIDA",
                f"Não é possível mudar o pedido de {self.status} para {novo}.",
            )
        self.status = novo

    @property
    def aceita_pagamento(self) -> bool:
        return self.status in (StatusPedido.AGUARDANDO_PAGAMENTO, StatusPedido.PAGAMENTO_RECUSADO)


@dataclass(kw_only=True)
class Pagamento:
    id: int | None = None
    pedido_id: int
    metodo: MetodoPagamento
    valor: Decimal
    status: StatusPagamento = StatusPagamento.PENDENTE
    transacao_externa: str | None = None
    mensagem: str | None = None
    criado_em: datetime = field(default_factory=agora)
    atualizado_em: datetime = field(default_factory=agora)


@dataclass(kw_only=True)
class MovimentacaoFidelidade:
    id: int | None = None
    usuario_id: int
    pedido_id: int | None = None
    tipo: TipoMovimentacaoFidelidade
    pontos: int
    descricao: str | None = None
    criado_em: datetime = field(default_factory=agora)


@dataclass(kw_only=True)
class Auditoria:
    id: int | None = None
    usuario_id: int | None = None
    acao: str
    entidade: str | None = None
    entidade_id: int | None = None
    detalhes: dict[str, Any] = field(default_factory=dict)
    ip: str | None = None
    criado_em: datetime = field(default_factory=agora)
