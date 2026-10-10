import warnings

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

warnings.filterwarnings("ignore", message=".*does \\*not\\* support Decimal objects natively.*")


def criar_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        em_memoria = ":memory:" in database_url or database_url in ("sqlite://", "sqlite:///")
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=StaticPool if em_memoria else None,
        )

        @event.listens_for(engine, "connect")
        def _ligar_chaves_estrangeiras(conexao, _registro):
            cursor = conexao.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(database_url, pool_pre_ping=True)


def criar_fabrica_sessoes(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
