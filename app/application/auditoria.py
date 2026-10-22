from app.application.comum import FabricaUoW, Pagina
from app.domain.entities import Auditoria


class ServicoAuditoria:
    def __init__(self, uow: FabricaUoW):
        self._uow = uow

    def listar(
        self, *, acao: str | None, entidade: str | None, usuario_id: int | None, page: int, limit: int
    ) -> Pagina[Auditoria]:
        with self._uow() as uow:
            itens, total = uow.auditorias.listar(
                acao=acao, entidade=entidade, usuario_id=usuario_id, page=page, limit=limit
            )
        return Pagina(itens, page, limit, total)
