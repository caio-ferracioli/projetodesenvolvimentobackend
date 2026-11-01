from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Engine

from app.application.auditoria import ServicoAuditoria
from app.application.autenticacao import ServicoAutenticacao
from app.application.catalogo import ServicoCatalogo
from app.application.estoque import ServicoEstoque
from app.application.fidelidade import ServicoFidelidade
from app.application.pagamentos import ServicoPagamentos
from app.application.pedidos import ServicoPedidos
from app.application.usuarios import ServicoUsuarios
from app.config import Settings
from app.infrastructure.db.session import criar_engine, criar_fabrica_sessoes
from app.infrastructure.db.uow import UnidadeDeTrabalhoSqlAlchemy
from app.infrastructure.gateways.mock_pagamento import MockGatewayPagamento
from app.infrastructure.seguranca import HasherBcrypt, ServicoTokenJwt


@dataclass
class Container:
    settings: Settings
    engine: Engine
    uow: Callable[[], UnidadeDeTrabalhoSqlAlchemy]
    hasher: HasherBcrypt
    gateway: MockGatewayPagamento
    autenticacao: ServicoAutenticacao
    usuarios: ServicoUsuarios
    catalogo: ServicoCatalogo
    estoque: ServicoEstoque
    pedidos: ServicoPedidos
    pagamentos: ServicoPagamentos
    fidelidade: ServicoFidelidade
    auditoria: ServicoAuditoria

    def entregar_callbacks_do_gateway(self) -> None:
        if not self.settings.pagamento_mock_callback_automatico:
            return

        def entregar(transacao_id: str, aprovado: bool, mensagem: str) -> None:
            self.pagamentos.processar_callback(transacao_id=transacao_id, aprovado=aprovado, mensagem=mensagem)

        self.gateway.entregar_callbacks(entregar)


def montar_container(settings: Settings, engine: Engine | None = None) -> Container:
    engine = engine or criar_engine(settings.database_url)
    fabrica = criar_fabrica_sessoes(engine)

    def uow() -> UnidadeDeTrabalhoSqlAlchemy:
        return UnidadeDeTrabalhoSqlAlchemy(fabrica)

    hasher = HasherBcrypt(settings.bcrypt_rounds)
    tokens = ServicoTokenJwt(settings.jwt_secret, settings.jwt_algorithm, settings.jwt_expire_minutes)
    gateway = MockGatewayPagamento(settings.pagamento_mock_atraso_segundos)

    return Container(
        settings=settings,
        engine=engine,
        uow=uow,
        hasher=hasher,
        gateway=gateway,
        autenticacao=ServicoAutenticacao(uow, hasher, tokens),
        usuarios=ServicoUsuarios(uow, hasher),
        catalogo=ServicoCatalogo(uow),
        estoque=ServicoEstoque(uow),
        pedidos=ServicoPedidos(uow, gateway),
        pagamentos=ServicoPagamentos(uow, gateway),
        fidelidade=ServicoFidelidade(uow),
        auditoria=ServicoAuditoria(uow),
    )
