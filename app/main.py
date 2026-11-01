import logging
from typing import Any

from fastapi import Depends, FastAPI
from sqlalchemy import Engine, text

from app.api.deps import ContainerDep, registrar_ip
from app.api.erros import registrar_handlers
from app.api.routers import auditorias, auth, catalogo, estoque, fidelidade, pagamentos, pedidos, usuarios
from app.config import Settings, obter_settings
from app.container import montar_container

DESCRICAO = """
API REST da rede **Raízes do Nordeste**: autenticação JWT com perfis, cardápio e estoque por unidade,
pedidos multicanal, pagamento via gateway **mock assíncrono**, fidelização com consentimento (LGPD)
e auditoria de ações sensíveis.

**Como testar:** `POST /auth/login` → copie o `accessToken` → botão **Authorize** → cole o token.

**Padrão de erro (todas as falhas):**
`{"status", "codigo", "mensagem", "detalhes": [], "caminho", "timestamp"}`.
"""

TAGS = [
    {"name": "Auth", "description": "Cadastro, login e renovação de token."},
    {"name": "Usuários", "description": "Gestão de usuários e anonimização (LGPD)."},
    {"name": "Unidades", "description": "Unidades da rede e cardápio por unidade."},
    {"name": "Produtos", "description": "Catálogo de produtos."},
    {"name": "Estoque", "description": "Saldo e movimentações por unidade."},
    {"name": "Pedidos", "description": "Criação, consulta (filtro por `canalPedido`), status e cancelamento."},
    {"name": "Pagamentos", "description": "Pagamento mock assíncrono e webhook assinado."},
    {"name": "Fidelidade", "description": "Pontos, consentimento e resgate."},
    {"name": "Auditoria", "description": "Trilha de ações sensíveis."},
    {"name": "Saúde", "description": "Verificação de disponibilidade."},
]


def _padronizar_422_no_openapi(app: FastAPI) -> None:
    gerar_original = app.openapi

    def openapi() -> dict[str, Any]:
        esquema = gerar_original()
        for operacoes in esquema["paths"].values():
            for operacao in operacoes.values():
                resposta = operacao.get("responses", {}).get("422")
                if resposta and "HTTPValidationError" in str(resposta):
                    operacao["responses"]["422"] = {
                        "description": "Dados inválidos (campo ausente, formato errado, valor fora da regra).",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErroSaida"}}},
                    }
        esquemas = esquema.get("components", {}).get("schemas", {})
        esquemas.pop("HTTPValidationError", None)
        esquemas.pop("ValidationError", None)
        return esquema

    app.openapi = openapi


def criar_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or obter_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = FastAPI(
        title="Raízes do Nordeste — API Back-end (Python / FastAPI)",
        version="1.0.0",
        description=DESCRICAO,
        openapi_tags=TAGS,
        docs_url="/docs" if settings.documentacao_habilitada else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.documentacao_habilitada else None,
        dependencies=[Depends(registrar_ip)],
    )
    app.state.container = montar_container(settings, engine)
    registrar_handlers(app)

    for router in (
        auth.router,
        usuarios.router,
        catalogo.unidades,
        catalogo.produtos,
        estoque.router,
        pedidos.router,
        pagamentos.router,
        fidelidade.router,
        auditorias.router,
    ):
        app.include_router(router)

    _padronizar_422_no_openapi(app)

    @app.get("/saude", tags=["Saúde"], summary="Verifica a API e o banco")
    def saude(c: ContainerDep) -> dict[str, Any]:
        with c.engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app
