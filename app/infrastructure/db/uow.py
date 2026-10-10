from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.db import repositories as r


class UnidadeDeTrabalhoSqlAlchemy:
    def __init__(self, fabrica_sessoes: sessionmaker[Session]):
        self._fabrica = fabrica_sessoes
        self._sessao: Session | None = None

    def __enter__(self) -> Self:
        self._sessao = self._fabrica()
        self.usuarios = r.RepositorioUsuarios(self._sessao)
        self.unidades = r.RepositorioUnidades(self._sessao)
        self.produtos = r.RepositorioProdutos(self._sessao)
        self.estoques = r.RepositorioEstoques(self._sessao)
        self.pedidos = r.RepositorioPedidos(self._sessao)
        self.pagamentos = r.RepositorioPagamentos(self._sessao)
        self.fidelidade = r.RepositorioFidelidade(self._sessao)
        self.auditorias = r.RepositorioAuditorias(self._sessao)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self._sessao.close()

    def commit(self) -> None:
        self._sessao.commit()

    def rollback(self) -> None:
        self._sessao.rollback()
