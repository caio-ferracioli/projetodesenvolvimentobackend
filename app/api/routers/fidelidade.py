from fastapi import APIRouter

from app.api.deps import ContainerDep, UsuarioAtual
from app.api.routers import erros
from app.api.schemas import (
    ConsentimentoEntrada,
    FidelidadeSaida,
    MovimentacaoFidelidadeSaida,
    ResgateEntrada,
)

router = APIRouter(prefix="/fidelidade", tags=["Fidelidade"])


def _resumo(usuario, saldo: int, movimentacoes) -> FidelidadeSaida:
    return FidelidadeSaida(
        saldo=saldo,
        consentimento=usuario.consentimento_fidelidade,
        consentimento_em=usuario.consentimento_em,
        movimentacoes=[MovimentacaoFidelidadeSaida.model_validate(m) for m in movimentacoes],
    )


@router.get("", response_model=FidelidadeSaida, summary="Saldo, consentimento e extrato", responses=erros(401))
def consultar(c: ContainerDep, ator: UsuarioAtual):
    saldo, movimentacoes = c.fidelidade.consultar(ator)
    return _resumo(ator, saldo, movimentacoes)


@router.put(
    "/consentimento",
    response_model=FidelidadeSaida,
    summary="Dá ou revoga o consentimento (LGPD)",
    responses=erros(401, 422),
)
def consentimento(dados: ConsentimentoEntrada, c: ContainerDep, ator: UsuarioAtual):
    usuario = c.fidelidade.alterar_consentimento(ator, dados.consentimento)
    saldo, movimentacoes = c.fidelidade.consultar(usuario)
    return _resumo(usuario, saldo, movimentacoes)


@router.post(
    "/resgates",
    status_code=201,
    response_model=MovimentacaoFidelidadeSaida,
    summary="Resgata pontos",
    responses=erros(401, 409, 422),
)
def resgatar(dados: ResgateEntrada, c: ContainerDep, ator: UsuarioAtual):
    return c.fidelidade.resgatar(ator, dados.pontos)
