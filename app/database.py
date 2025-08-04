import os
from dotenv import load_dotenv
from sqlmodel import create_engine, Session
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)

def get_session():
    with Session(engine) as session:
        yield session


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
