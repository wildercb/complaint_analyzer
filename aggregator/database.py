# aggregator/database.py

import os
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from elasticsearch import Elasticsearch
from datetime import datetime

Base = declarative_base()

class Complaint(Base):
    __tablename__ = 'complaints'

    id = Column(Integer, primary_key=True)
    type = Column(String(50), nullable=False)
    content = Column(JSON, nullable=False)
    category = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

def setup_database():
    db_user = os.environ.get('POSTGRES_USER', 'postgres')
    db_pass = os.environ.get('POSTGRES_PASSWORD', 'postgres')
    db_host = os.environ.get('POSTGRES_HOST', 'localhost')
    db_port = os.environ.get('POSTGRES_PORT', '5433')
    db_name = 'complaints'
    db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    return engine, SessionLocal

engine, SessionLocal = setup_database()

es = Elasticsearch([os.environ.get('ELASTICSEARCH_URL', 'http://localhost:9200')])