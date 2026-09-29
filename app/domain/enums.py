from enum import StrEnum


class Perfil(StrEnum):
    CLIENTE = "CLIENTE"
    ATENDENTE = "ATENDENTE"
    COZINHA = "COZINHA"
    GERENTE = "GERENTE"
    ADMIN = "ADMIN"


class CanalPedido(StrEnum):
    APP = "APP"
    TOTEM = "TOTEM"
    BALCAO = "BALCAO"
    PICKUP = "PICKUP"
    WEB = "WEB"


class MetodoPagamento(StrEnum):
    PIX = "PIX"
    CARTAO_CREDITO = "CARTAO_CREDITO"
    CARTAO_DEBITO = "CARTAO_DEBITO"


class StatusPagamento(StrEnum):
    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"
    FALHA = "FALHA"
    ESTORNADO = "ESTORNADO"


class TipoMovimentacaoEstoque(StrEnum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    AJUSTE = "AJUSTE"
    BAIXA_PEDIDO = "BAIXA_PEDIDO"
    ESTORNO_PEDIDO = "ESTORNO_PEDIDO"


class TipoMovimentacaoFidelidade(StrEnum):
    ACUMULO = "ACUMULO"
    RESGATE = "RESGATE"
    ESTORNO = "ESTORNO"


class StatusPedido(StrEnum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    PAGAMENTO_RECUSADO = "PAGAMENTO_RECUSADO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"

    def transicoes(self) -> tuple["StatusPedido", ...]:
        return _TRANSICOES[self]

    def pode_ir_para(self, novo: "StatusPedido") -> bool:
        return novo in _TRANSICOES[self]


_TRANSICOES: dict[StatusPedido, tuple[StatusPedido, ...]] = {
    StatusPedido.AGUARDANDO_PAGAMENTO: (
        StatusPedido.EM_PREPARO,
        StatusPedido.PAGAMENTO_RECUSADO,
        StatusPedido.CANCELADO,
    ),
    StatusPedido.PAGAMENTO_RECUSADO: (StatusPedido.EM_PREPARO, StatusPedido.CANCELADO),
    StatusPedido.EM_PREPARO: (StatusPedido.PRONTO, StatusPedido.CANCELADO),
    StatusPedido.PRONTO: (StatusPedido.ENTREGUE,),
    StatusPedido.ENTREGUE: (),
    StatusPedido.CANCELADO: (),
}
