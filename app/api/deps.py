from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.comum import ip_da_requisicao
from app.container import Container
from app.domain.entities import Usuario
from app.domain.enums import Perfil
from app.domain.errors import AcessoNegado, NaoAutenticado

esquema_bearer = HTTPBearer(
    auto_error=False,
    description="Cole o `accessToken` retornado por `POST /auth/login`.",
)


def obter_container(request: Request) -> Container:
    return request.app.state.container


async def registrar_ip(request: Request) -> None:
    ip_da_requisicao.set(request.client.host if request.client else None)


def usuario_atual(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
    container: Annotated[Container, Depends(obter_container)],
) -> Usuario:
    if credenciais is None:
        raise NaoAutenticado("TOKEN_AUSENTE", "Informe o token no cabeçalho Authorization: Bearer <token>.")
    return container.autenticacao.autenticar(credenciais.credentials)


def exigir_perfil(*perfis: Perfil):

    def dependencia(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
        if usuario.perfil not in perfis:
            raise AcessoNegado(
                "PERFIL_SEM_PERMISSAO",
                f"O perfil {usuario.perfil} não tem permissão para esta operação.",
                [{"perfisPermitidos": [str(p) for p in perfis]}],
            )
        return usuario

    return dependencia


class ParametrosPagina:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="Página (começa em 1).")] = 1,
        limit: Annotated[int, Query(ge=1, le=100, description="Itens por página (máximo 100).")] = 10,
    ):
        self.page = page
        self.limit = limit


Pagina = Annotated[ParametrosPagina, Depends()]
ContainerDep = Annotated[Container, Depends(obter_container)]
UsuarioAtual = Annotated[Usuario, Depends(usuario_atual)]

SOMENTE_ADMIN = Depends(exigir_perfil(Perfil.ADMIN))
GERENCIA = Depends(exigir_perfil(Perfil.GERENTE, Perfil.ADMIN))
EQUIPE = Depends(exigir_perfil(Perfil.ATENDENTE, Perfil.COZINHA, Perfil.GERENTE, Perfil.ADMIN))
