from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.infrastructure.db.models import Base

RAIZ = Path(__file__).resolve().parents[1]


def _config(url: str) -> Config:
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migrations_criam_exatamente_o_esquema_dos_modelos(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migrado.db').as_posix()}"
    command.upgrade(_config(url), "head")

    engine = create_engine(url)
    tabelas = set(inspect(engine).get_table_names()) - {"alembic_version"}
    assert tabelas == set(Base.metadata.tables)

    with engine.connect() as conexao:
        diferencas = compare_metadata(MigrationContext.configure(conexao), Base.metadata)
    assert diferencas == [], f"migration diverge dos modelos: {diferencas}"
    engine.dispose()


def test_downgrade_remove_tudo(tmp_path):
    url = f"sqlite:///{(tmp_path / 'ida_e_volta.db').as_posix()}"
    command.upgrade(_config(url), "head")
    command.downgrade(_config(url), "base")

    engine = create_engine(url)
    assert set(inspect(engine).get_table_names()) - {"alembic_version"} == set()
    engine.dispose()
