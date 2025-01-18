from sqlalchemy import create_engine

from .. import DATABASE_PATH

# import here, because create_all then creates all models that were imported.
from .models import Base  # noqa: F401

SQLALCHEMY_DATABASE_FILE = f"{DATABASE_PATH}/database.sqlite"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{SQLALCHEMY_DATABASE_FILE}"


connect_args = {"check_same_thread": False}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)  # , echo=True)

# not used until now, could be used instead normal Session() below
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# def get_session():
#     with Session(engine) as session:
#         yield session
# SessionDep = Annotated[Session, Depends(get_session)]


def create_db_and_tables():
    Base.metadata.create_all(bind=engine)
