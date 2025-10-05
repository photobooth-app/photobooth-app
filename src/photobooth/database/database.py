import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from .. import DATABASE_PATH

# import here, because create_all then creates all models that were imported.
from .models import Base  # noqa: F401

SQLALCHEMY_DATABASE_FILE = f"{DATABASE_PATH}/database.sqlite"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{SQLALCHEMY_DATABASE_FILE}"


connect_args = {"check_same_thread": False}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)  # , echo=True)


def create_db_and_tables():
    db_exists = os.path.exists(SQLALCHEMY_DATABASE_FILE)
    inspector = inspect(engine)  # creates empty db, so db file check needs to be before!
    alembic_cfg = Config()

    # from your settings or environment
    alembic_cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)
    alembic_cfg.set_main_option("script_location", str(Path(Path(__file__).parent.absolute(), "alembic")))

    # Check if Alembic has already stamped the DB
    if not db_exists:
        print("Setup new sqlite database now")
        command.upgrade(alembic_cfg, "head")
    elif not inspector.has_table("alembic_version"):
        print("Existing database found that was not stamped yet. Stamp it to initial database schema and run migrations.")
        # we can stamp because there has been only 1 database out in production until today.
        command.stamp(alembic_cfg, "7e0d6dfb1b1d")
        command.upgrade(alembic_cfg, "head")
    else:
        print("Existing stamped database found. running migrations if needed.")
        command.upgrade(alembic_cfg, "head")
