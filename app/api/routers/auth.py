from fastapi import APIRouter

from app.api.deps import ContainerDep, UsuarioAtual
from app.api.routers import erros
from app.api.schemas import LoginEntrada, RegistroEntrada, TokenSaida, UsuarioSaida

router = APIRouter(prefix="/auth", tags=["Auth"])


def _token(emitido) -> TokenSaida:
    return TokenSaida(access_token=emitido.token, expires_in=emitido.expira_em_segundos)


@router.post(
    "/registro",
    status_code=201,
    response_model=UsuarioSaida,
    summary="Cadastra um cliente",
    responses=erros(409, 422),
)
def registrar(dados: RegistroEntrada, c: ContainerDep):
    return c.autenticacao.registrar_cliente(
        nome=dados.nome,
        email=dados.email,
        senha=dados.senha,
        telefone=dados.telefone,
        consentimento_fidelidade=dados.consentimento_fidelidade,
    )


@router.post("/login", response_model=TokenSaida, summary="Autentica e devolve o JWT", responses=erros(401, 422))
def login(dados: LoginEntrada, c: ContainerDep):
    return _token(c.autenticacao.login(dados.email, dados.senha))


@router.get("/me", response_model=UsuarioSaida, summary="Usuário do token", responses=erros(401))
def me(usuario: UsuarioAtual):
    return usuario


@router.post("/refresh", response_model=TokenSaida, summary="Emite um novo token", responses=erros(401))
def renovar(usuario: UsuarioAtual, c: ContainerDep):
    return _token(c.autenticacao.renovar(usuario))
