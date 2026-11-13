import os

os.environ["JWT_SECRET"] = "segredo-de-teste-com-mais-de-trinta-e-dois-caracteres"
os.environ["WEBHOOK_SECRET"] = "segredo-do-webhook-de-teste"
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["DATABASE_URL"] = "sqlite://"

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.infrastructure.db.models import Base
from app.infrastructure.db.seed import SENHA_PADRAO, popular
from app.infrastructure.db.session import criar_engine
from app.infrastructure.seguranca import assinar_payload
from app.main import criar_app

RECIFE, SALVADOR, FORTALEZA = 1, 2, 3
BAIAO, CARNE_DE_SOL, MOQUECA, TAPIOCA, ACARAJE = 1, 2, 3, 4, 5

CAMPOS_ERRO = {"status", "codigo", "mensagem", "detalhes", "caminho", "timestamp"}


class Api:
    def __init__(self, client: TestClient, container, settings: Settings):
        self.client = client
        self.container = container
        self.settings = settings
        self._tokens: dict[str, str] = {}

    def token(self, email: str) -> str:
        if email not in self._tokens:
            r = self.client.post("/auth/login", json={"email": email, "senha": SENHA_PADRAO})
            assert r.status_code == 200, r.text
            self._tokens[email] = r.json()["accessToken"]
        return self._tokens[email]

    def request(self, metodo: str, caminho: str, como: str | None = None, **kwargs):
        headers = kwargs.pop("headers", {})
        if como:
            headers = {"Authorization": f"Bearer {self.token(como)}", **headers}
        return self.client.request(metodo, caminho, headers=headers, **kwargs)

    def get(self, caminho, como=None, **kw):
        return self.request("GET", caminho, como, **kw)

    def post(self, caminho, como=None, **kw):
        return self.request("POST", caminho, como, **kw)

    def put(self, caminho, como=None, **kw):
        return self.request("PUT", caminho, como, **kw)

    def patch(self, caminho, como=None, **kw):
        return self.request("PATCH", caminho, como, **kw)

    def delete(self, caminho, como=None, **kw):
        return self.request("DELETE", caminho, como, **kw)

    def criar_pedido(self, como="cliente@raizes.com", itens=((BAIAO, 1),), unidade=RECIFE, canal="APP", **extra):
        corpo = {
            "unidadeId": unidade,
            "canalPedido": canal,
            "itens": [{"produtoId": p, "quantidade": q} for p, q in itens],
            **extra,
        }
        return self.post("/pedidos", como, json=corpo)

    def pagar(self, pedido_id: int, como="cliente@raizes.com", token: str | None = None, metodo="PIX"):
        corpo = {"pedidoId": pedido_id, "metodo": metodo}
        if token:
            corpo["tokenPagamento"] = token
        return self.post("/pagamentos", como, json=corpo)

    def pedido(self, pedido_id: int, como="gerente@raizes.com") -> dict:
        r = self.get(f"/pedidos/{pedido_id}", como)
        assert r.status_code == 200, r.text
        return r.json()

    def saldo_estoque(self, produto_id: int, unidade_id: int = RECIFE) -> int:
        r = self.get(f"/estoque?unidadeId={unidade_id}&produtoId={produto_id}", "gerente@raizes.com")
        assert r.status_code == 200, r.text
        return r.json()["items"][0]["quantidade"]

    def webhook(self, transacao_id: str, status: str, assinatura: str | None = "valida"):
        corpo = json.dumps({"transacaoId": transacao_id, "status": status}).encode()
        headers = {"Content-Type": "application/json"}
        if assinatura == "valida":
            headers["X-Signature"] = assinar_payload(self.settings.webhook_secret, corpo)
        elif assinatura:
            headers["X-Signature"] = assinatura
        return self.client.post("/pagamentos/webhook", content=corpo, headers=headers)


@pytest.fixture
def api():
    settings = Settings()
    engine = criar_engine(settings.database_url)
    Base.metadata.create_all(engine)
    app = criar_app(settings, engine)
    popular(app.state.container)
    with TestClient(app) as client:
        yield Api(client, app.state.container, settings)
    engine.dispose()


def assert_erro(resposta, status: int, codigo: str) -> dict:
    assert resposta.status_code == status, resposta.text
    corpo = resposta.json()
    assert set(corpo) == CAMPOS_ERRO, corpo
    assert corpo["status"] == status
    assert corpo["codigo"] == codigo, corpo
    assert isinstance(corpo["detalhes"], list)
    return corpo
