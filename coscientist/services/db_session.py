import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from coscientist.models.db_models import Base

db_url = os.environ.get("DATABASE_URL")
if db_url:
    engine = create_engine(db_url)
else:
    db_path = os.environ.get("COSCIENTIST_DB_PATH", os.path.expanduser("~/.coscientist/coscientist.db"))
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f'sqlite:///{db_path}', connect_args={'check_same_thread': False})
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
