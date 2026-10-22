from app.application.comum import FabricaUoW, registrar_auditoria
from app.domain.entities import MovimentacaoFidelidade, Pedido, Usuario, calcular_pontos
from app.domain.enums import TipoMovimentacaoFidelidade
from app.domain.errors import Conflito, RegraDeNegocio
from app.domain.ports import UnidadeDeTrabalho


def acumular_pontos(uow: UnidadeDeTrabalho, pedido: Pedido) -> int:
    if pedido.cliente_id is None:
        return 0
    cliente = uow.usuarios.obter(pedido.cliente_id)
    if cliente is None or cliente.anonimizado or not cliente.consentimento_fidelidade:
        return 0
    if uow.fidelidade.obter_do_pedido(pedido.id, TipoMovimentacaoFidelidade.ACUMULO):
        return 0

    pontos = calcular_pontos(pedido.valor_total)
    if pontos <= 0:
        return 0
    uow.fidelidade.adicionar(
        MovimentacaoFidelidade(
            usuario_id=cliente.id,
            pedido_id=pedido.id,
            tipo=TipoMovimentacaoFidelidade.ACUMULO,
            pontos=pontos,
            descricao=f"Pontos do pedido #{pedido.id}",
        )
    )
    return pontos


def estornar_pontos(uow: UnidadeDeTrabalho, pedido: Pedido) -> None:
    acumulo = uow.fidelidade.obter_do_pedido(pedido.id, TipoMovimentacaoFidelidade.ACUMULO)
    if acumulo is None or uow.fidelidade.obter_do_pedido(pedido.id, TipoMovimentacaoFidelidade.ESTORNO):
        return
    uow.fidelidade.adicionar(
        MovimentacaoFidelidade(
            usuario_id=acumulo.usuario_id,
            pedido_id=pedido.id,
            tipo=TipoMovimentacaoFidelidade.ESTORNO,
            pontos=-acumulo.pontos,
            descricao=f"Estorno do pedido #{pedido.id}",
        )
    )


class ServicoFidelidade:
    def __init__(self, uow: FabricaUoW):
        self._uow = uow

    def consultar(self, ator: Usuario) -> tuple[int, list[MovimentacaoFidelidade]]:
        with self._uow() as uow:
            return uow.fidelidade.saldo(ator.id), uow.fidelidade.listar(ator.id, limite=20)

    def alterar_consentimento(self, ator: Usuario, consentiu: bool) -> Usuario:
        with self._uow() as uow:
            usuario = uow.usuarios.obter(ator.id)
            usuario.definir_consentimento(consentiu)
            uow.usuarios.salvar(usuario)
            registrar_auditoria(
                uow,
                "CONSENTIMENTO_FIDELIDADE_ALTERADO",
                entidade="Usuario",
                entidade_id=usuario.id,
                detalhes={"consentimento": consentiu},
                usuario_id=usuario.id,
            )
            uow.commit()
            return usuario

    def resgatar(self, ator: Usuario, pontos: int) -> MovimentacaoFidelidade:
        if pontos < 1:
            raise RegraDeNegocio("PONTOS_INVALIDOS", "Informe uma quantidade de pontos maior que zero.")
        with self._uow() as uow:
            usuario = uow.usuarios.obter(ator.id)
            if not usuario.consentimento_fidelidade:
                raise RegraDeNegocio(
                    "CONSENTIMENTO_NECESSARIO",
                    "É necessário consentir com o programa de fidelidade antes de resgatar pontos.",
                )
            saldo = uow.fidelidade.saldo(usuario.id)
            if pontos > saldo:
                raise Conflito(
                    "SALDO_INSUFICIENTE",
                    "Saldo de pontos insuficiente para o resgate.",
                    [{"solicitado": pontos, "saldo": saldo}],
                )
            mov = uow.fidelidade.adicionar(
                MovimentacaoFidelidade(
                    usuario_id=usuario.id,
                    tipo=TipoMovimentacaoFidelidade.RESGATE,
                    pontos=-pontos,
                    descricao="Resgate de pontos",
                )
            )
            registrar_auditoria(
                uow,
                "FIDELIDADE_RESGATE",
                entidade="Usuario",
                entidade_id=usuario.id,
                detalhes={"pontos": pontos},
                usuario_id=usuario.id,
            )
            uow.commit()
            return mov
