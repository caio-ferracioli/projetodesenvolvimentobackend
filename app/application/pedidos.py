from dataclasses import dataclass, field

from app.application.comum import FabricaUoW, Pagina, registrar_auditoria
from app.application.fidelidade import estornar_pontos
from app.domain.entities import (
    ItemPedido,
    MovimentacaoEstoque,
    Pagamento,
    Pedido,
    Usuario,
    agora,
    arredondar,
)
from app.domain.enums import (
    CanalPedido,
    Perfil,
    StatusPagamento,
    StatusPedido,
    TipoMovimentacaoEstoque,
)
from app.domain.errors import AcessoNegado, Conflito, NaoEncontrado, RegraDeNegocio
from app.domain.policies import exigir_acesso_ao_pedido
from app.domain.ports import GatewayPagamento, UnidadeDeTrabalho


@dataclass(frozen=True)
class ItemSolicitado:
    produto_id: int
    quantidade: int


@dataclass(frozen=True)
class NovoPedido:
    unidade_id: int
    canal_pedido: CanalPedido
    itens: list[ItemSolicitado]
    observacao: str | None = None
    cliente_id: int | None = None
    chave_idempotencia: str | None = None


@dataclass
class DetalhePedido:
    pedido: Pedido
    pagamento: Pagamento | None = None
    pagamentos: list[Pagamento] = field(default_factory=list)


def _detalhe(uow: UnidadeDeTrabalho, pedido: Pedido) -> DetalhePedido:
    pagamentos = uow.pagamentos.listar_do_pedido(pedido.id)
    return DetalhePedido(pedido, pagamentos[-1] if pagamentos else None, pagamentos)


class ServicoPedidos:
    def __init__(self, uow: FabricaUoW, gateway: GatewayPagamento):
        self._uow = uow
        self._gateway = gateway


    def criar(self, ator: Usuario, dados: NovoPedido) -> tuple[DetalhePedido, bool]:
        if dados.chave_idempotencia:
            existente = self._buscar_por_chave(ator, dados.chave_idempotencia)
            if existente:
                return existente, False

        try:
            with self._uow() as uow:
                pedido = self._persistir(uow, ator, dados)
                uow.commit()
                return _detalhe(uow, pedido), True
        except Conflito as erro:
            if erro.codigo == "CHAVE_IDEMPOTENCIA_DUPLICADA" and dados.chave_idempotencia:
                existente = self._buscar_por_chave(ator, dados.chave_idempotencia)
                if existente:
                    return existente, False
            raise

    def _buscar_por_chave(self, ator: Usuario, chave: str) -> DetalhePedido | None:
        with self._uow() as uow:
            pedido = uow.pedidos.obter_por_chave(ator.id, chave)
            return _detalhe(uow, pedido) if pedido else None

    def _persistir(self, uow: UnidadeDeTrabalho, ator: Usuario, dados: NovoPedido) -> Pedido:
        unidade = uow.unidades.obter(dados.unidade_id)
        if unidade is None:
            raise NaoEncontrado("UNIDADE_NAO_ENCONTRADA", "Unidade não encontrada.")
        if not unidade.ativa:
            raise RegraDeNegocio("UNIDADE_INATIVA", "A unidade informada está inativa.")
        if ator.perfil == Perfil.ATENDENTE and ator.unidade_id != unidade.id:
            raise AcessoNegado("ACESSO_NEGADO", "O atendente só registra pedidos da própria unidade.")
        if not dados.itens:
            raise RegraDeNegocio("PEDIDO_SEM_ITENS", "O pedido precisa ter ao menos um item.")

        cliente_id = self._resolver_cliente(uow, ator, dados.cliente_id)

        quantidades: dict[int, int] = {}
        for item in dados.itens:
            if item.quantidade < 1:
                raise RegraDeNegocio("QUANTIDADE_INVALIDA", "A quantidade de cada item deve ser maior que zero.")
            quantidades[item.produto_id] = quantidades.get(item.produto_id, 0) + item.quantidade

        produtos = uow.produtos.obter_varios(list(quantidades))
        ausentes = [pid for pid in quantidades if pid not in produtos]
        if ausentes:
            raise NaoEncontrado(
                "PRODUTO_NAO_ENCONTRADO",
                "Um ou mais produtos informados não existem.",
                [{"produtoId": pid} for pid in ausentes],
            )

        estoques = uow.estoques.obter_varios(unidade.id, list(quantidades))
        problemas = []
        for pid, qtd in quantidades.items():
            estoque, produto = estoques.get(pid), produtos[pid]
            disponivel = estoque.quantidade if (estoque and estoque.disponivel and produto.vendavel) else 0
            if disponivel < qtd:
                problemas.append({"produtoId": pid, "solicitado": qtd, "disponivel": disponivel})
        if problemas:
            raise Conflito(
                "ESTOQUE_INSUFICIENTE",
                "Estoque insuficiente ou produto indisponível nesta unidade.",
                problemas,
            )

        itens = [
            ItemPedido(
                produto_id=pid,
                nome_produto=produtos[pid].nome,
                quantidade=qtd,
                preco_unitario=produtos[pid].preco,
                subtotal=arredondar(produtos[pid].preco * qtd),
            )
            for pid, qtd in quantidades.items()
        ]
        pedido = Pedido(
            cliente_id=cliente_id,
            criado_por_id=ator.id,
            unidade_id=unidade.id,
            canal_pedido=dados.canal_pedido,
            observacao=dados.observacao,
            chave_idempotencia=dados.chave_idempotencia,
            itens=itens,
        )
        pedido.recalcular_total()
        pedido = uow.pedidos.adicionar(pedido)

        registrar_auditoria(
            uow,
            "PEDIDO_CRIADO",
            entidade="Pedido",
            entidade_id=pedido.id,
            detalhes={
                "canalPedido": pedido.canal_pedido,
                "unidadeId": pedido.unidade_id,
                "valorTotal": pedido.valor_total,
                "itens": len(itens),
            },
            usuario_id=ator.id,
        )
        return pedido

    @staticmethod
    def _resolver_cliente(uow: UnidadeDeTrabalho, ator: Usuario, cliente_id: int | None) -> int | None:
        if ator.perfil == Perfil.CLIENTE:
            return ator.id
        if cliente_id is None:
            return None
        cliente = uow.usuarios.obter(cliente_id)
        if cliente is None or cliente.perfil != Perfil.CLIENTE or cliente.anonimizado:
            raise NaoEncontrado("CLIENTE_NAO_ENCONTRADO", "Cliente informado não existe.")
        return cliente.id


    def listar(
        self,
        ator: Usuario,
        *,
        canal_pedido: CanalPedido | None,
        status: StatusPedido | None,
        unidade_id: int | None,
        page: int,
        limit: int,
    ) -> Pagina[Pedido]:
        cliente_id = None
        if ator.perfil == Perfil.CLIENTE:
            cliente_id = ator.id
        elif ator.perfil in (Perfil.ATENDENTE, Perfil.COZINHA):
            unidade_id = ator.unidade_id

        with self._uow() as uow:
            itens, total = uow.pedidos.listar(
                cliente_id=cliente_id,
                unidade_id=unidade_id,
                canal_pedido=canal_pedido,
                status=status,
                page=page,
                limit=limit,
            )
        return Pagina(itens, page, limit, total)

    def obter(self, ator: Usuario, pedido_id: int) -> DetalhePedido:
        with self._uow() as uow:
            pedido = self._pedido_ou_404(uow, pedido_id)
            exigir_acesso_ao_pedido(ator, pedido)
            return _detalhe(uow, pedido)

    @staticmethod
    def _pedido_ou_404(uow: UnidadeDeTrabalho, pedido_id: int) -> Pedido:
        pedido = uow.pedidos.obter(pedido_id)
        if pedido is None:
            raise NaoEncontrado("PEDIDO_NAO_ENCONTRADO", "Pedido não encontrado.")
        return pedido


    def atualizar_status(
        self, ator: Usuario, pedido_id: int, novo: StatusPedido, motivo: str | None
    ) -> DetalhePedido:
        if novo == StatusPedido.CANCELADO:
            return self.cancelar(ator, pedido_id, motivo)

        permitidos = {
            StatusPedido.PRONTO: (Perfil.COZINHA, Perfil.GERENTE, Perfil.ADMIN),
            StatusPedido.ENTREGUE: (Perfil.ATENDENTE, Perfil.GERENTE, Perfil.ADMIN),
        }.get(novo)
        if permitidos is None:
            raise RegraDeNegocio(
                "STATUS_NAO_PERMITIDO",
                "Só é possível definir manualmente os status PRONTO, ENTREGUE ou CANCELADO.",
            )
        if ator.perfil not in permitidos:
            raise AcessoNegado("ACESSO_NEGADO", f"O perfil {ator.perfil} não pode mover o pedido para {novo}.")

        with self._uow() as uow:
            pedido = self._pedido_ou_404(uow, pedido_id)
            exigir_acesso_ao_pedido(ator, pedido)

            anterior = pedido.status
            pedido.transicionar(novo)
            uow.pedidos.salvar(pedido)
            registrar_auditoria(
                uow,
                "PEDIDO_STATUS_ALTERADO",
                entidade="Pedido",
                entidade_id=pedido.id,
                detalhes={"de": anterior, "para": novo},
                usuario_id=ator.id,
            )
            uow.commit()
            return _detalhe(uow, pedido)

    def cancelar(self, ator: Usuario, pedido_id: int, motivo: str | None) -> DetalhePedido:
        if ator.perfil == Perfil.COZINHA:
            raise AcessoNegado("ACESSO_NEGADO", "A cozinha não cancela pedidos.")

        with self._uow() as uow:
            pedido = self._pedido_ou_404(uow, pedido_id)
            exigir_acesso_ao_pedido(ator, pedido)
            if ator.perfil == Perfil.CLIENTE and pedido.status == StatusPedido.EM_PREPARO:
                raise AcessoNegado(
                    "CANCELAMENTO_SOMENTE_EQUIPE",
                    "Pedido já em preparo só pode ser cancelado pela equipe da unidade.",
                )

            anterior = pedido.status
            pedido.transicionar(StatusPedido.CANCELADO)
            pedido.motivo_cancelamento = motivo
            uow.pedidos.salvar(pedido)

            aprovado = next(
                (p for p in uow.pagamentos.listar_do_pedido(pedido.id) if p.status == StatusPagamento.APROVADO),
                None,
            )
            if aprovado:
                self._gateway.estornar(aprovado.transacao_externa)
                aprovado.status = StatusPagamento.ESTORNADO
                aprovado.mensagem = "Estornado por cancelamento do pedido (mock)."
                aprovado.atualizado_em = agora()
                uow.pagamentos.salvar(aprovado)
                devolver_estoque(uow, pedido, ator)
                estornar_pontos(uow, pedido)

            registrar_auditoria(
                uow,
                "PEDIDO_CANCELADO",
                entidade="Pedido",
                entidade_id=pedido.id,
                detalhes={
                    "statusAnterior": anterior,
                    "motivo": motivo,
                    "pagamentoEstornado": aprovado is not None,
                },
                usuario_id=ator.id,
            )
            uow.commit()
            return _detalhe(uow, pedido)


def devolver_estoque(uow: UnidadeDeTrabalho, pedido: Pedido, ator: Usuario | None) -> None:
    for item in sorted(pedido.itens, key=lambda i: i.produto_id):
        estoque = uow.estoques.obter(pedido.unidade_id, item.produto_id)
        if estoque is None:
            continue
        saldo = uow.estoques.ajustar(estoque.id, item.quantidade)
        uow.estoques.adicionar_movimentacao(
            MovimentacaoEstoque(
                estoque_id=estoque.id,
                tipo=TipoMovimentacaoEstoque.ESTORNO_PEDIDO,
                variacao=item.quantidade,
                saldo_apos=saldo if saldo is not None else estoque.quantidade,
                motivo=f"Cancelamento do pedido #{pedido.id}",
                pedido_id=pedido.id,
                usuario_id=ator.id if ator else None,
            )
        )
