from app.domain.entities import Pedido, Usuario
from app.domain.enums import Perfil
from app.domain.errors import AcessoNegado

EQUIPE_DA_UNIDADE = (Perfil.ATENDENTE, Perfil.COZINHA)
EQUIPE_GERAL = (Perfil.GERENTE, Perfil.ADMIN)


def pode_acessar_pedido(ator: Usuario, pedido: Pedido) -> bool:
    if ator.perfil in EQUIPE_GERAL:
        return True
    if ator.perfil == Perfil.CLIENTE:
        return pedido.cliente_id == ator.id
    return ator.unidade_id is not None and ator.unidade_id == pedido.unidade_id


def exigir_acesso_ao_pedido(ator: Usuario, pedido: Pedido) -> None:
    if not pode_acessar_pedido(ator, pedido):
        raise AcessoNegado("ACESSO_NEGADO", "Você não tem acesso a este pedido.")
