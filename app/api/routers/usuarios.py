from fastapi import APIRouter, Response

from app.api.deps import GERENCIA, SOMENTE_ADMIN, ContainerDep, Pagina, UsuarioAtual
from app.api.routers import erros
from app.api.schemas import PaginaSaida, UsuarioEntrada, UsuarioSaida, paginar

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.get(
    "",
    response_model=PaginaSaida[UsuarioSaida],
    summary="Lista usuários (GERENTE, ADMIN)",
    dependencies=[GERENCIA],
    responses=erros(401, 403, 422),
)
def listar(c: ContainerDep, p: Pagina):
    return paginar(c.usuarios.listar(page=p.page, limit=p.limit), UsuarioSaida)


@router.post(
    "",
    status_code=201,
    response_model=UsuarioSaida,
    summary="Cria usuário de qualquer perfil (ADMIN)",
    responses=erros(401, 403, 404, 409, 422),
)
def criar(dados: UsuarioEntrada, c: ContainerDep, ator: UsuarioAtual, _=SOMENTE_ADMIN):
    return c.usuarios.criar(
        ator,
        nome=dados.nome,
        email=dados.email,
        senha=dados.senha,
        perfil=dados.perfil,
        unidade_id=dados.unidade_id,
        telefone=dados.telefone,
    )


@router.delete(
    "/{usuario_id}",
    status_code=204,
    response_class=Response,
    summary="Anonimiza o titular (LGPD) — ADMIN ou o próprio usuário",
    responses=erros(401, 403, 404, 409),
)
def anonimizar(usuario_id: int, c: ContainerDep, ator: UsuarioAtual):
    c.usuarios.anonimizar(ator, usuario_id)
    return Response(status_code=204)
