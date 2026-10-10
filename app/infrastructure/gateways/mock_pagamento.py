import logging
import secrets
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import MetodoPagamento
from app.domain.errors import GatewayIndisponivel
from app.domain.ports import CobrancaIniciada

logger = logging.getLogger(__name__)

TOKEN_RECUSADO = "tok_recusado"
TOKEN_TIMEOUT = "tok_timeout"
TOKEN_SEM_RETORNO = "tok_sem_retorno"
LIMITE_POR_TRANSACAO = Decimal("5000.00")


@dataclass(frozen=True)
class _CallbackAgendado:
    transacao_id: str
    aprovado: bool
    mensagem: str


class MockGatewayPagamento:
    def __init__(self, atraso_segundos: float = 0.0):
        self._atraso = atraso_segundos
        self._pendentes: deque[_CallbackAgendado] = deque()
        self.estornos: list[str] = []

    def iniciar_cobranca(
        self, *, referencia: str, valor: Decimal, metodo: MetodoPagamento, token: str | None
    ) -> CobrancaIniciada:
        if token == TOKEN_TIMEOUT:
            raise GatewayIndisponivel("GATEWAY_TIMEOUT", "Timeout ao contatar o gateway de pagamento (mock).")

        transacao = f"MOCK-{secrets.token_hex(6).upper()}"
        if token == TOKEN_SEM_RETORNO:
            return CobrancaIniciada(transacao)

        if token == TOKEN_RECUSADO:
            callback = _CallbackAgendado(transacao, False, "Pagamento recusado pelo emissor (mock).")
        elif valor > LIMITE_POR_TRANSACAO:
            callback = _CallbackAgendado(
                transacao, False, "Pagamento recusado: valor acima do limite permitido (mock)."
            )
        else:
            callback = _CallbackAgendado(transacao, True, "Pagamento aprovado (mock).")
        self._pendentes.append(callback)
        return CobrancaIniciada(transacao)

    def estornar(self, transacao_id: str) -> None:
        self.estornos.append(transacao_id)

    def entregar_callbacks(self, entregar: Callable[[str, bool, str], object]) -> int:
        entregues = 0
        while True:
            try:
                callback = self._pendentes.popleft()
            except IndexError:
                return entregues
            if self._atraso:
                time.sleep(self._atraso)
            try:
                entregar(callback.transacao_id, callback.aprovado, callback.mensagem)
                entregues += 1
            except Exception:
                logger.exception("Falha ao processar o callback da transação %s", callback.transacao_id)
