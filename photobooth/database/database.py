from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine

from .. import DATA_PATH

# import here, because create_all then creates all models that were imported.
from . import models  # noqa: F401 https://sqlmodel.tiangolo.com/tutorial/code-structure/#order-matters

sqlite_file_name = f"{DATA_PATH}/database.sqlite"
sqlite_url = f"sqlite:///{sqlite_file_name}"


connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
