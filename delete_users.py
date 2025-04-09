from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL.replace('postgres://', 'postgresql://'))

# Definir el modelo User
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default='user')

# Lista de correos a eliminar
emails_to_delete = [
    'seba.redigonda@gmail.com',
    'glamour-control.2e@icloud.com',
    'starstarfall.up1@gmail.com',
    'starfall.indumentaria@gmail.com',
    'voyconsciente@gmail.com',
    'lanuevaera.org@gmail.com',  # Añade aquí los correos que quieras borrar
    # Agrega más si es necesario
]

# Eliminar usuarios específicos
with Session(engine) as session:
    deleted_count = session.query(User).filter(User.email.in_(emails_to_delete)).delete(synchronize_session=False)
    session.commit()
    print(f"Se eliminaron {deleted_count} usuarios con los correos: {emails_to_delete}")