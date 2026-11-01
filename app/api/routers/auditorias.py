from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import GERENCIA, ContainerDep, Pagina
from app.api.routers import erros
from app.api.schemas import AuditoriaSaida, PaginaSaida, paginar

router = APIRouter(prefix="/auditorias", tags=["Auditoria"])


@router.get(
    "",
    response_model=PaginaSaida[AuditoriaSaida],
    summary="Trilha de auditoria (GERENTE, ADMIN)",
    dependencies=[GERENCIA],
    responses=erros(401, 403, 422),
)
def listar(
    c: ContainerDep,
    p: Pagina,
    acao: Annotated[str | None, Query(max_length=60, description="Ex.: PEDIDO_CRIADO, PAGAMENTO_APROVADO.")] = None,
    entidade: Annotated[str | None, Query(max_length=60)] = None,
    usuario_id: Annotated[int | None, Query(alias="usuarioId", ge=1)] = None,
):
    return paginar(
        c.auditoria.listar(acao=acao, entidade=entidade, usuario_id=usuario_id, page=p.page, limit=p.limit),
        AuditoriaSaida,
    )
