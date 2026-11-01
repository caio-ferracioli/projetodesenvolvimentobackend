from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer
from pydantic.alias_generators import to_camel

from app.application.comum import Pagina
from app.domain.enums import (
    CanalPedido,
    MetodoPagamento,
    Perfil,
    StatusPagamento,
    StatusPedido,
    TipoMovimentacaoEstoque,
    TipoMovimentacaoFidelidade,
)

Dinheiro = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


class Esquema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        str_strip_whitespace=True,
    )


class DetalheErro(Esquema):
    campo: str | None = None
    mensagem: str | None = None


class ErroSaida(Esquema):

    status: int = Field(examples=[422])
    codigo: str = Field(examples=["VALIDACAO_FALHOU"])
    mensagem: str = Field(examples=["Os dados enviados são inválidos."])
    detalhes: list[dict[str, Any]] = Field(
        default_factory=list, examples=[[{"campo": "canalPedido", "mensagem": "Campo obrigatório."}]]
    )
    caminho: str = Field(examples=["/pedidos"])
    timestamp: datetime


class PaginaSaida[T](Esquema):
    items: list[T]
    page: int
    limit: int
    total: int
    pages: int


def paginar[T, R](pagina: Pagina[T], converter: type[R]) -> dict[str, Any]:
    return {
        "items": [converter.model_validate(i) for i in pagina.itens],
        "page": pagina.page,
        "limit": pagina.limit,
        "total": pagina.total,
        "pages": pagina.paginas,
    }


class RegistroEntrada(Esquema):
    nome: str = Field(min_length=2, max_length=120, examples=["Ana Souza"])
    email: EmailStr = Field(examples=["ana@exemplo.com"])
    senha: str = Field(min_length=8, max_length=64, examples=["Senha@123"])
    telefone: str | None = Field(default=None, max_length=30)
    consentimento_fidelidade: bool = Field(
        default=False, description="LGPD: aceite explícito do programa de fidelidade (pode ser revogado depois)."
    )


class LoginEntrada(Esquema):
    email: EmailStr = Field(examples=["cliente@raizes.com"])
    senha: str = Field(min_length=1, max_length=64, examples=["Senha@123"])


class TokenSaida(Esquema):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = Field(description="Validade do token, em segundos.")


class UsuarioSaida(Esquema):
    id: int
    nome: str
    email: str
    perfil: Perfil
    telefone: str | None
    unidade_id: int | None
    consentimento_fidelidade: bool
    consentimento_em: datetime | None
    criado_em: datetime


class UsuarioEntrada(Esquema):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=64)
    perfil: Perfil
    unidade_id: int | None = Field(default=None, description="Obrigatória para ATENDENTE e COZINHA.")
    telefone: str | None = Field(default=None, max_length=30)


class UnidadeEntrada(Esquema):
    nome: str = Field(min_length=2, max_length=120)
    cidade: str = Field(min_length=2, max_length=80)
    endereco: str | None = Field(default=None, max_length=200)
    ativa: bool = True


class UnidadeSaida(Esquema):
    id: int
    nome: str
    cidade: str
    endereco: str | None
    ativa: bool


class ProdutoEntrada(Esquema):
    nome: str = Field(min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=1000)
    categoria: str = Field(min_length=2, max_length=60)
    preco: Decimal = Field(gt=0, max_digits=10, decimal_places=2, examples=[38.9])
    ativo: bool = True


class ProdutoSaida(Esquema):
    id: int
    nome: str
    descricao: str | None
    categoria: str
    preco: Dinheiro
    ativo: bool


class CardapioItemSaida(Esquema):
    produto_id: int
    nome: str
    descricao: str | None
    categoria: str
    preco: Dinheiro
    disponivel: bool = Field(description="False quando o saldo da unidade zerou.")


class CardapioSaida(Esquema):
    unidade: UnidadeSaida
    itens: list[CardapioItemSaida]


class EstoqueSaida(Esquema):
    id: int
    unidade_id: int
    produto_id: int
    produto_nome: str
    quantidade: int
    disponivel: bool


class MovimentacaoEstoqueEntrada(Esquema):
    unidade_id: int
    produto_id: int
    tipo: Literal["ENTRADA", "SAIDA", "AJUSTE"]
    quantidade: int = Field(ge=0, le=100000, description="Em AJUSTE é o novo saldo absoluto.")
    motivo: str | None = Field(default=None, max_length=255)


class MovimentacaoEstoqueSaida(Esquema):
    id: int
    estoque_id: int
    tipo: TipoMovimentacaoEstoque
    variacao: int
    saldo_apos: int
    motivo: str | None
    pedido_id: int | None
    usuario_id: int | None
    criado_em: datetime


class DisponibilidadeEntrada(Esquema):
    disponivel: bool


class ItemPedidoEntrada(Esquema):
    produto_id: int = Field(ge=1)
    quantidade: int = Field(ge=1, le=99)


class PedidoEntrada(Esquema):
    unidade_id: int = Field(ge=1)
    canal_pedido: CanalPedido = Field(description="Obrigatório. Valores: APP, TOTEM, BALCAO, PICKUP, WEB.")
    itens: list[ItemPedidoEntrada] = Field(min_length=1, max_length=50)
    observacao: str | None = Field(default=None, max_length=255)
    cliente_id: int | None = Field(
        default=None, ge=1, description="Só para a equipe (balcão): cliente que está sendo atendido."
    )


class ItemPedidoSaida(Esquema):
    produto_id: int
    nome_produto: str
    quantidade: int
    preco_unitario: Dinheiro
    subtotal: Dinheiro


class PagamentoSaida(Esquema):
    id: int
    pedido_id: int
    metodo: MetodoPagamento
    valor: Dinheiro
    status: StatusPagamento
    transacao_externa: str | None
    mensagem: str | None
    criado_em: datetime
    atualizado_em: datetime


class PedidoSaida(Esquema):
    id: int
    cliente_id: int | None
    unidade_id: int
    canal_pedido: CanalPedido
    status: StatusPedido
    valor_total: Dinheiro
    observacao: str | None
    motivo_cancelamento: str | None
    itens: list[ItemPedidoSaida]
    pagamento: PagamentoSaida | None = Field(default=None, description="Tentativa de pagamento mais recente.")
    criado_em: datetime
    atualizado_em: datetime


class StatusEntrada(Esquema):
    status: StatusPedido
    motivo: str | None = Field(default=None, max_length=255, description="Usado no cancelamento.")


class PagamentoEntrada(Esquema):
    pedido_id: int = Field(ge=1)
    metodo: MetodoPagamento
    token_pagamento: str | None = Field(
        default=None,
        max_length=100,
        description="Mock: tok_recusado (recusa), tok_timeout (gateway fora), tok_sem_retorno (fica PENDENTE).",
    )


class CallbackEntrada(Esquema):
    transacao_id: str = Field(min_length=1, max_length=80)
    status: Literal["APROVADO", "RECUSADO"]
    mensagem: str | None = Field(default=None, max_length=255)


class CallbackSaida(Esquema):
    pagamento_id: int
    status_pagamento: StatusPagamento
    status_pedido: StatusPedido
    processado: bool = Field(description="False quando a notificação era repetida (nada foi alterado).")


class MovimentacaoFidelidadeSaida(Esquema):
    id: int
    tipo: TipoMovimentacaoFidelidade
    pontos: int
    pedido_id: int | None
    descricao: str | None
    criado_em: datetime


class FidelidadeSaida(Esquema):
    saldo: int
    consentimento: bool
    consentimento_em: datetime | None
    movimentacoes: list[MovimentacaoFidelidadeSaida]


class ConsentimentoEntrada(Esquema):
    consentimento: bool


class ResgateEntrada(Esquema):
    pontos: int = Field(ge=1, le=1_000_000)


class AuditoriaSaida(Esquema):
    id: int
    usuario_id: int | None
    acao: str
    entidade: str | None
    entidade_id: int | None
    detalhes: dict[str, Any]
    ip: str | None
    criado_em: datetime
