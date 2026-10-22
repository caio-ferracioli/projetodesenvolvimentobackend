from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.entities import Auditoria
from app.domain.ports import UnidadeDeTrabalho

FabricaUoW = Callable[[], UnidadeDeTrabalho]

ip_da_requisicao: ContextVar[str | None] = ContextVar("ip_da_requisicao", default=None)


@dataclass(frozen=True)
class Pagina[T]:
    itens: list[T]
    page: int
    limit: int
    total: int

    @property
    def paginas(self) -> int:
        return max(1, -(-self.total // self.limit))


def registrar_auditoria(
    uow: UnidadeDeTrabalho,
    acao: str,
    *,
    entidade: str | None = None,
    entidade_id: int | None = None,
    detalhes: dict[str, Any] | None = None,
    usuario_id: int | None = None,
) -> None:
    uow.auditorias.adicionar(
        Auditoria(
            usuario_id=usuario_id,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhes=_serializavel(detalhes or {}),
            ip=ip_da_requisicao.get(),
        )
    )


def _serializavel(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, dict):
        return {k: _serializavel(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_serializavel(v) for v in valor]
    return valor
