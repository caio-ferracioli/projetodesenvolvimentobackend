from dataclasses import dataclass

from app.application.comum import FabricaUoW, registrar_auditoria
from app.application.fidelidade import acumular_pontos
from app.domain.entities import MovimentacaoEstoque, Pagamento, Pedido, Usuario, agora
from app.domain.enums import (
    MetodoPagamento,
    Perfil,
    StatusPagamento,
    StatusPedido,
    TipoMovimentacaoEstoque,
)
from app.domain.errors import (
    AcessoNegado,
    Conflito,
    GatewayIndisponivel,
    NaoEncontrado,
    ServicoIndisponivel,
)
from app.domain.policies import exigir_acesso_ao_pedido
from app.domain.ports import GatewayPagamento, UnidadeDeTrabalho


@dataclass(frozen=True)
class ResultadoCallback:
    pagamento: Pagamento
    status_pedido: StatusPedido
    processado: bool


class ServicoPagamentos:
    def __init__(self, uow: FabricaUoW, gateway: GatewayPagamento):
        self._uow = uow
        self._gateway = gateway


    def iniciar(
        self, ator: Usuario, *, pedido_id: int, metodo: MetodoPagamento, token: str | None
    ) -> Pagamento:
        if ator.perfil == Perfil.COZINHA:
            raise AcessoNegado("ACESSO_NEGADO", "A cozinha não registra pagamentos.")

        with self._uow() as uow:
            pedido = uow.pedidos.obter(pedido_id)
            if pedido is None:
                raise NaoEncontrado("PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.")
            exigir_acesso_ao_pedido(ator, pedido)
            if not pedido.aceita_pagamento:
                raise Conflito(
                    "PEDIDO_NAO_PAGAVEL", f"Pedido com status {pedido.status} não aceita pagamento."
                )
            if any(p.status == StatusPagamento.PENDENTE for p in uow.pagamentos.listar_do_pedido(pedido.id)):
                raise Conflito(
                    "PAGAMENTO_EM_ANDAMENTO",
                    "Já existe um pagamento aguardando confirmação do gateway para este pedido.",
                )
            pagamento = uow.pagamentos.adicionar(
                Pagamento(pedido_id=pedido.id, metodo=metodo, valor=pedido.valor_total)
            )
            uow.commit()
            pagamento_id, valor = pagamento.id, pagamento.valor

        try:
            cobranca = self._gateway.iniciar_cobranca(
                referencia=f"PED-{pedido_id}-PAG-{pagamento_id}", valor=valor, metodo=metodo, token=token
            )
        except GatewayIndisponivel:
            with self._uow() as uow:
                pagamento = uow.pagamentos.obter(pagamento_id)
                pagamento.status = StatusPagamento.FALHA
                pagamento.mensagem = "Gateway de pagamento indisponível. Tente novamente."
                pagamento.atualizado_em = agora()
                uow.pagamentos.salvar(pagamento)
                registrar_auditoria(
                    uow,
                    "PAGAMENTO_FALHA_GATEWAY",
                    entidade="Pagamento",
                    entidade_id=pagamento_id,
                    detalhes={"pedidoId": pedido_id},
                    usuario_id=ator.id,
                )
                uow.commit()
            raise ServicoIndisponivel(
                "GATEWAY_INDISPONIVEL",
                "O gateway de pagamento está indisponível no momento. O pedido foi mantido; tente novamente.",
                [{"pedidoId": pedido_id, "pagamentoId": pagamento_id}],
            ) from None

        with self._uow() as uow:
            pagamento = uow.pagamentos.obter(pagamento_id)
            pagamento.transacao_externa = cobranca.transacao_id
            pagamento.mensagem = "Cobrança enviada ao gateway; aguardando confirmação."
            pagamento.atualizado_em = agora()
            uow.pagamentos.salvar(pagamento)
            registrar_auditoria(
                uow,
                "PAGAMENTO_INICIADO",
                entidade="Pagamento",
                entidade_id=pagamento_id,
                detalhes={
                    "pedidoId": pedido_id,
                    "valor": pagamento.valor,
                    "metodo": metodo,
                    "transacao": cobranca.transacao_id,
                },
                usuario_id=ator.id,
            )
            uow.commit()
            return pagamento


    def processar_callback(
        self, *, transacao_id: str, aprovado: bool, mensagem: str | None
    ) -> ResultadoCallback:
        with self._uow() as uow:
            pagamento = uow.pagamentos.obter_por_transacao(transacao_id)
            if pagamento is None:
                raise NaoEncontrado("PAGAMENTO_NAO_ENCONTRADO", "Transação desconhecida.")
            pedido = uow.pedidos.obter(pagamento.pedido_id)

            if pagamento.status != StatusPagamento.PENDENTE:
                return ResultadoCallback(pagamento, pedido.status, processado=False)

            if not aprovado:
                self._registrar_recusa(uow, pagamento, pedido, mensagem)
            elif not pedido.aceita_pagamento:
                self._estornar(uow, pagamento, "Pedido não aceita mais pagamento; valor estornado (mock).")
                registrar_auditoria(
                    uow,
                    "PAGAMENTO_ESTORNADO_PEDIDO_ENCERRADO",
                    entidade="Pagamento",
                    entidade_id=pagamento.id,
                    detalhes={"pedidoId": pedido.id, "statusPedido": pedido.status},
                )
            else:
                falhas = self._baixar_estoque(uow, pedido)
                if falhas:
                    uow.rollback()
                    self._cancelar_por_falta_de_estoque(uow, pagamento, pedido, falhas)
                else:
                    self._registrar_aprovacao(uow, pagamento, pedido, mensagem)

            uow.commit()
            return ResultadoCallback(pagamento, pedido.status, processado=True)

    def _registrar_aprovacao(
        self, uow: UnidadeDeTrabalho, pagamento: Pagamento, pedido: Pedido, mensagem: str | None
    ) -> None:
        pagamento.status = StatusPagamento.APROVADO
        pagamento.mensagem = mensagem or "Pagamento aprovado (mock)."
        pagamento.atualizado_em = agora()
        uow.pagamentos.salvar(pagamento)

        pedido.transicionar(StatusPedido.EM_PREPARO)
        uow.pedidos.salvar(pedido)

        pontos = acumular_pontos(uow, pedido)
        registrar_auditoria(
            uow,
            "PAGAMENTO_APROVADO",
            entidade="Pagamento",
            entidade_id=pagamento.id,
            detalhes={
                "pedidoId": pedido.id,
                "valor": pagamento.valor,
                "metodo": pagamento.metodo,
                "transacao": pagamento.transacao_externa,
                "pontos": pontos,
            },
        )

    @staticmethod
    def _registrar_recusa(
        uow: UnidadeDeTrabalho, pagamento: Pagamento, pedido: Pedido, mensagem: str | None
    ) -> None:
        pagamento.status = StatusPagamento.RECUSADO
        pagamento.mensagem = mensagem or "Pagamento recusado (mock)."
        pagamento.atualizado_em = agora()
        uow.pagamentos.salvar(pagamento)

        if pedido.status == StatusPedido.AGUARDANDO_PAGAMENTO:
            pedido.transicionar(StatusPedido.PAGAMENTO_RECUSADO)
            uow.pedidos.salvar(pedido)
        registrar_auditoria(
            uow,
            "PAGAMENTO_RECUSADO",
            entidade="Pagamento",
            entidade_id=pagamento.id,
            detalhes={"pedidoId": pedido.id, "valor": pagamento.valor, "motivo": pagamento.mensagem},
        )

    @staticmethod
    def _baixar_estoque(uow: UnidadeDeTrabalho, pedido: Pedido) -> list[dict]:
        falhas: list[dict] = []
        for item in sorted(pedido.itens, key=lambda i: i.produto_id):
            estoque = uow.estoques.obter(pedido.unidade_id, item.produto_id)
            saldo = None
            if estoque and estoque.disponivel:
                saldo = uow.estoques.ajustar(estoque.id, -item.quantidade)
            if saldo is None:
                falhas.append(
                    {
                        "produtoId": item.produto_id,
                        "solicitado": item.quantidade,
                        "disponivel": estoque.quantidade if estoque else 0,
                    }
                )
                continue
            uow.estoques.adicionar_movimentacao(
                MovimentacaoEstoque(
                    estoque_id=estoque.id,
                    tipo=TipoMovimentacaoEstoque.BAIXA_PEDIDO,
                    variacao=-item.quantidade,
                    saldo_apos=saldo,
                    motivo=f"Pagamento aprovado do pedido #{pedido.id}",
                    pedido_id=pedido.id,
                )
            )
        return falhas

    def _cancelar_por_falta_de_estoque(
        self, uow: UnidadeDeTrabalho, pagamento: Pagamento, pedido: Pedido, falhas: list[dict]
    ) -> None:
        self._estornar(uow, pagamento, "Estoque esgotado após a aprovação; valor estornado (mock).")
        pedido.transicionar(StatusPedido.CANCELADO)
        pedido.motivo_cancelamento = "ESTOQUE_ESGOTADO_APOS_PAGAMENTO"
        uow.pedidos.salvar(pedido)
        registrar_auditoria(
            uow,
            "PEDIDO_CANCELADO_SEM_ESTOQUE",
            entidade="Pedido",
            entidade_id=pedido.id,
            detalhes={"itens": falhas, "pagamentoId": pagamento.id},
        )

    def _estornar(self, uow: UnidadeDeTrabalho, pagamento: Pagamento, mensagem: str) -> None:
        if pagamento.transacao_externa:
            self._gateway.estornar(pagamento.transacao_externa)
        pagamento.status = StatusPagamento.ESTORNADO
        pagamento.mensagem = mensagem
        pagamento.atualizado_em = agora()
        uow.pagamentos.salvar(pagamento)


    def obter(self, ator: Usuario, pagamento_id: int) -> Pagamento:
        with self._uow() as uow:
            pagamento = uow.pagamentos.obter(pagamento_id)
            if pagamento is None:
                raise NaoEncontrado("PAGAMENTO_NAO_ENCONTRADO", "Pagamento não encontrado.")
            if ator.perfil == Perfil.COZINHA:
                raise AcessoNegado("ACESSO_NEGADO", "A cozinha não consulta pagamentos.")
            pedido = uow.pedidos.obter(pagamento.pedido_id)
            exigir_acesso_ao_pedido(ator, pedido)
            return pagamento
