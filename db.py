from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config import POSTGRES_URI

Base = declarative_base()
engine = create_async_engine(POSTGRES_URI, echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)