from app.application.comum import FabricaUoW, Pagina, registrar_auditoria
from app.domain.entities import Estoque, MovimentacaoEstoque, Produto, Usuario
from app.domain.enums import TipoMovimentacaoEstoque
from app.domain.errors import Conflito, NaoEncontrado, RegraDeNegocio
from app.domain.policies import EQUIPE_DA_UNIDADE

MANUAIS = (TipoMovimentacaoEstoque.ENTRADA, TipoMovimentacaoEstoque.SAIDA, TipoMovimentacaoEstoque.AJUSTE)


def _escopo_unidade(ator: Usuario, unidade_id: int | None) -> int | None:
    if ator.perfil in EQUIPE_DA_UNIDADE:
        return ator.unidade_id
    return unidade_id


class ServicoEstoque:
    def __init__(self, uow: FabricaUoW):
        self._uow = uow

    def listar(
        self, ator: Usuario, *, unidade_id: int | None, produto_id: int | None, page: int, limit: int
    ) -> Pagina[tuple[Estoque, Produto]]:
        with self._uow() as uow:
            itens, total = uow.estoques.listar(
                unidade_id=_escopo_unidade(ator, unidade_id), produto_id=produto_id, page=page, limit=limit
            )
        return Pagina(itens, page, limit, total)

    def listar_movimentacoes(
        self, ator: Usuario, *, unidade_id: int | None, produto_id: int | None, page: int, limit: int
    ) -> Pagina[MovimentacaoEstoque]:
        with self._uow() as uow:
            itens, total = uow.estoques.listar_movimentacoes(
                unidade_id=_escopo_unidade(ator, unidade_id), produto_id=produto_id, page=page, limit=limit
            )
        return Pagina(itens, page, limit, total)

    def registrar_movimentacao(
        self,
        ator: Usuario,
        *,
        unidade_id: int,
        produto_id: int,
        tipo: TipoMovimentacaoEstoque,
        quantidade: int,
        motivo: str | None,
    ) -> MovimentacaoEstoque:
        if tipo not in MANUAIS:
            raise RegraDeNegocio("TIPO_INVALIDO", "Tipo de movimentação inválido para lançamento manual.")
        if tipo != TipoMovimentacaoEstoque.AJUSTE and quantidade < 1:
            raise RegraDeNegocio("QUANTIDADE_INVALIDA", "A quantidade deve ser maior que zero.")

        with self._uow() as uow:
            if uow.unidades.obter(unidade_id) is None:
                raise NaoEncontrado("UNIDADE_NAO_ENCONTRADA", "Unidade não encontrada.")
            produto = uow.produtos.obter(produto_id)
            if produto is None or produto.removido_em is not None:
                raise NaoEncontrado("PRODUTO_NAO_ENCONTRADO", "Produto não encontrado.")

            estoque = uow.estoques.obter(unidade_id, produto_id)
            if estoque is None:
                if tipo == TipoMovimentacaoEstoque.SAIDA:
                    raise NaoEncontrado(
                        "ESTOQUE_NAO_ENCONTRADO", "Este produto não possui estoque nesta unidade."
                    )
                estoque = uow.estoques.adicionar(Estoque(unidade_id=unidade_id, produto_id=produto_id))

            delta = {
                TipoMovimentacaoEstoque.ENTRADA: quantidade,
                TipoMovimentacaoEstoque.SAIDA: -quantidade,
                TipoMovimentacaoEstoque.AJUSTE: quantidade - estoque.quantidade,
            }[tipo]

            saldo = uow.estoques.ajustar(estoque.id, delta)
            if saldo is None:
                raise Conflito(
                    "ESTOQUE_INSUFICIENTE",
                    "Estoque insuficiente para a saída solicitada.",
                    [{"produtoId": produto_id, "solicitado": quantidade, "disponivel": estoque.quantidade}],
                )

            mov = uow.estoques.adicionar_movimentacao(
                MovimentacaoEstoque(
                    estoque_id=estoque.id,
                    tipo=tipo,
                    variacao=delta,
                    saldo_apos=saldo,
                    motivo=motivo,
                    usuario_id=ator.id,
                )
            )
            registrar_auditoria(
                uow,
                "ESTOQUE_MOVIMENTADO",
                entidade="Estoque",
                entidade_id=estoque.id,
                detalhes={
                    "tipo": tipo,
                    "variacao": delta,
                    "saldoApos": saldo,
                    "unidadeId": unidade_id,
                    "produtoId": produto_id,
                },
                usuario_id=ator.id,
            )
            uow.commit()
            return mov

    def definir_disponibilidade(self, ator: Usuario, estoque_id: int, disponivel: bool) -> Estoque:
        with self._uow() as uow:
            estoque = uow.estoques.obter_por_id(estoque_id)
            if estoque is None:
                raise NaoEncontrado("ESTOQUE_NAO_ENCONTRADO", "Registro de estoque não encontrado.")
            estoque.disponivel = disponivel
            uow.estoques.salvar(estoque)
            registrar_auditoria(
                uow,
                "ESTOQUE_DISPONIBILIDADE_ALTERADA",
                entidade="Estoque",
                entidade_id=estoque.id,
                detalhes={"disponivel": disponivel},
                usuario_id=ator.id,
            )
            uow.commit()
            return estoque
