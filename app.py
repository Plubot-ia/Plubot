from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, Response
from flask_mail import Mail, Message
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, set_access_cookies, unset_jwt_cookies, decode_token
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, ValidationError, RootModel
from celery import Celery
from redis.connection import ConnectionPool
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
import redis
import os
import re
import json
import logging
import bcrypt
import requests
import time
import PyPDF2
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from datetime import timedelta, datetime
from contextlib import contextmanager
import uuid
from ratelimit import limits, sleep_and_retry
import magic
from functools import lru_cache
from typing import Optional, List, Dict, Any
from requests.exceptions import HTTPError, Timeout

# Configuración inicial
load_dotenv()
app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise ValueError("No se encontró SECRET_KEY en las variables de entorno.")

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('plubot.log', maxBytes=10_000_000, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración de CORS
CORS(app, resources={r"/*": {
    "origins": [
        "http://localhost:5000",
        "http://192.168.0.213:5000",
        "https://www.plubot.com"
    ],
    "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    "allow_headers": ["Content-Type", "Authorization"],
    "supports_credentials": True
}})

# Configuración de Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
retry = Retry(ExponentialBackoff(cap=10, base=1), retries=5)
redis_pool = ConnectionPool.from_url(
    REDIS_URL,
    decode_responses=True,
    max_connections=20,
    retry=retry,
    retry_on_timeout=True,
    health_check_interval=30,
    socket_timeout=10,
    socket_connect_timeout=10
)
redis_client = redis.Redis(
    connection_pool=redis_pool,
    socket_timeout=10,
    socket_connect_timeout=10,
    retry=retry
)

def ensure_redis_connection(max_attempts=3) -> bool:
    global redis_client
    for attempt in range(max_attempts):
        try:
            redis_client.ping()
            logger.info("Conexión a Redis establecida")
            return True
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Intento {attempt + 1}/{max_attempts} - Redis no disponible: {str(e)}")
            time.sleep(2 ** attempt)
            try:
                redis_client = redis.Redis(
                    connection_pool=redis_pool,
                    socket_timeout=10,
                    socket_connect_timeout=10,
                    retry=retry
                )
                redis_client.ping()
                logger.info("Reconexión a Redis exitosa")
                return True
            except redis.exceptions.ConnectionError:
                continue
    logger.error("Redis no disponible tras varios intentos")
    return False

if not ensure_redis_connection():
    redis_client = None

# Configuración de Celery
celery_app = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL.replace('/0', '/1')
)
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    broker_pool_limit=5,
    result_expires=3600,
    broker_transport_options={
        'max_retries': 5,
        'interval_start': 1,
        'interval_step': 2,
        'interval_max': 10
    },
    result_backend_transport_options={
        'retry_policy': {
            'max_retries': 5,
            'interval_start': 1,
            'interval_step': 2,
            'interval_max': 10
        }
    }
)

# Cargar claves desde .env
XAI_API_KEY = os.getenv("XAI_API_KEY")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
DATABASE_URL = os.getenv("DATABASE_URL")

if not XAI_API_KEY:
    raise ValueError("No se encontró XAI_API_KEY en las variables de entorno.")
if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE]):
    raise ValueError("Faltan credenciales de Twilio en las variables de entorno.")
if not DATABASE_URL:
    raise ValueError("Falta DATABASE_URL en las variables de entorno.")

# Configuración de Flask-Mail
app.config.update(
    MAIL_SERVER=os.getenv('MAIL_SERVER'),
    MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
    MAIL_USE_TLS=os.getenv('MAIL_USE_TLS', 'True') == 'True',
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER')
)
mail = Mail(app)

# Configuración de Twilio
twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

# Configuración de JWT
app.config.update(
    JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY', 'super-secret'),
    JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=1),
    JWT_TOKEN_LOCATION=['cookies'],
    JWT_ACCESS_COOKIE_NAME="access_token",
    JWT_COOKIE_CSRF_PROTECT=False,
    JWT_COOKIE_SECURE=os.getenv('FLASK_ENV', 'development') != 'development',
    JWT_COOKIE_SAMESITE='Lax',
    JWT_ACCESS_COOKIE_PATH="/"
)
jwt = JWTManager(app)

# Configuración de la base de datos
engine = create_engine(
    DATABASE_URL.replace('postgres://', 'postgresql://'),
    pool_size=10,
    max_overflow=20,
    pool_timeout=30
)
Base = declarative_base()

# Modelos de base de datos
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    role = Column(String, default='user')
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

class Chatbot(Base):
    __tablename__ = 'chatbots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    tone = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    initial_message = Column(Text, nullable=False)
    whatsapp_number = Column(String, unique=True, index=True)
    business_info = Column(Text)
    pdf_url = Column(String)
    pdf_content = Column(Text)
    image_url = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class Conversation(Base):
    __tablename__ = 'conversations'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chatbot_id = Column(Integer, ForeignKey('chatbots.id'), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    role = Column(String, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())

class Flow(Base):
    __tablename__ = 'flows'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chatbot_id = Column(Integer, ForeignKey('chatbots.id'), nullable=False, index=True)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
    intent = Column(String)

class MessageQuota(Base):
    __tablename__ = 'message_quotas'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    month = Column(String, nullable=False)
    message_count = Column(Integer, default=0)
    plan = Column(String, default='free')

class Template(Base):
    __tablename__ = 'templates'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    tone = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    flows = Column(Text, nullable=False)
    description = Column(Text, nullable=False)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

@contextmanager
def get_session():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error en sesión de base de datos: {str(e)}")
        raise
    finally:
        session.close()

# Modelos Pydantic para validación
class LoginModel(BaseModel):
    email: str = Field(..., min_length=5, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: str = Field(..., min_length=8)

class RegisterModel(BaseModel):
    email: str = Field(..., min_length=5, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: str = Field(..., min_length=8)

class WhatsAppNumberModel(BaseModel):
    whatsapp_number: str

    @classmethod
    def validate_whatsapp_number(cls, value):
        if not re.match(r'^\+\d{10,15}$', value):
            raise ValueError('El número de WhatsApp debe tener el formato +1234567890')
        return value

class FlowModel(BaseModel):
    user_message: str = Field(..., min_length=1)
    bot_response: str = Field(..., min_length=1)
    intent: str = Field(default="general", min_length=1)

class MenuItemModel(BaseModel):
    precio: float = Field(..., gt=0)
    descripcion: str = Field(..., min_length=1)

class MenuModel(RootModel):
    root: Dict[str, Dict[str, MenuItemModel]]

# Funciones auxiliares
def extract_text_from_pdf(file_stream) -> str:
    try:
        reader = PyPDF2.PdfReader(file_stream)
        return "".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        logger.exception(f"Error al extraer texto del PDF: {str(e)}")
        return ""

@lru_cache(maxsize=100)
def summarize_history(history: tuple) -> str:
    history = list(history)
    if len(history) > 5:
        return "Resumen: " + " ".join(conv.message[:50] for conv in history[-5:])
    return " ".join(conv.message for conv in history)

@sleep_and_retry
@limits(calls=50, period=60)
def call_grok(messages: List[Dict[str, str]], max_tokens: int = 150) -> str:
    if len(messages) > 4:
        messages = [messages[0]] + messages[-3:]
    
    cache_key = json.dumps(messages, sort_keys=True)
    if redis_client and ensure_redis_connection():
        try:
            cached_result = redis_client.get(cache_key)
            if cached_result:
                logger.info("Respuesta obtenida desde caché")
                return cached_result.decode('utf-8')
        except redis.exceptions.RedisError as e:
            logger.warning(f"Error al leer desde Redis: {str(e)}")

    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "grok-2-1212",
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": max_tokens
    }

    try:
        logger.info(f"Enviando solicitud a xAI con payload: {json.dumps(payload)}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()['choices'][0]['message']['content']
        
        if redis_client and ensure_redis_connection():
            try:
                redis_client.setex(cache_key, 3600, result)
                logger.info("Respuesta guardada en caché")
            except redis.exceptions.RedisError as e:
                logger.warning(f"Error al guardar en Redis: {str(e)}")
        
        logger.info(f"Grok response: {result}")
        return result
    except requests.exceptions.ConnectionError:
        logger.exception("Error de conexión con xAI")
        return "¡Vaya! La conexión con la IA falló, intenta de nuevo."
    except requests.exceptions.Timeout:
        logger.exception("Timeout al conectar con xAI")
        return "¡Ups! La IA tardó demasiado, intenta de nuevo."
    except requests.exceptions.HTTPError as e:
        logger.exception(f"Error HTTP con xAI: {str(e)}")
        status = e.response.status_code
        if status == 429:
            return "Demasiadas solicitudes. Espera un momento y vuelve a intentarlo."
        elif status == 401:
            return "Error de autenticación con la IA. Contacta al soporte."
        return f"Error con la IA (código {status}). Intenta de nuevo más tarde."

@celery_app.task
def process_pdf_async(chatbot_id: int, pdf_url: str):
    with get_session() as session:
        try:
            response = requests.get(pdf_url, timeout=10)
            response.raise_for_status()
            pdf_content = extract_text_from_pdf(response.content)
            chatbot = session.query(Chatbot).filter_by(id=chatbot_id).first()
            if chatbot:
                chatbot.pdf_content = pdf_content
                session.commit()
                logger.info(f"PDF procesado para chatbot {chatbot_id}")
        except Exception as e:
            logger.exception(f"Error procesando PDF para chatbot {chatbot_id}: {str(e)}")

def validate_whatsapp_number(number: str) -> bool:
    if not number.startswith('+'):
        number = '+' + number
    try:
        phone_numbers = twilio_client.api.accounts(TWILIO_SID).incoming_phone_numbers.list()
        for phone in phone_numbers:
            if phone.phone_number == number:
                logger.info(f"Número {number} encontrado en cuenta Twilio")
                return True
        logger.warning(f"Número {number} no registrado en Twilio")
        return False
    except TwilioRestException as e:
        logger.exception(f"Error al validar número de WhatsApp: {str(e)}")
        return False

def check_quota(user_id: int, session) -> bool:
    current_month = datetime.utcnow().strftime("%Y-%m")
    quota = session.query(MessageQuota).filter_by(user_id=user_id, month=current_month).first()
    if not quota:
        quota = MessageQuota(user_id=user_id, month=current_month)
        session.add(quota)
        session.commit()
    if quota.plan == 'free':
        if quota.message_count >= 75 and quota.message_count < 100:
            logger.info(f"Usuario {user_id} ha usado {quota.message_count} mensajes")
        return quota.message_count < 100
    return True

@app.route('/api/quota', methods=['GET'])
@jwt_required()
def get_quota():
    user_id = get_jwt_identity()
    with get_session() as session:
        current_month = datetime.utcnow().strftime("%Y-%m")
        quota = session.query(MessageQuota).filter_by(user_id=user_id, month=current_month).first()
        return jsonify({
            'plan': quota.plan if quota else 'free',
            'messages_used': quota.message_count if quota else 0,
            'messages_limit': 100 if (quota and quota.plan == 'free') else 'ilimitado'
        })

def increment_quota(user_id: int, session) -> MessageQuota:
    current_month = datetime.utcnow().strftime("%Y-%m")
    quota = session.query(MessageQuota).filter_by(user_id=user_id, month=current_month).first()
    if not quota:
        quota = MessageQuota(user_id=user_id, month=current_month)
        session.add(quota)
    quota.message_count += 1
    session.commit()
    return quota

def parse_menu_to_flows(menu_json: Any) -> List[Dict[str, str]]:
    try:
        if isinstance(menu_json, str):
            menu_data = json.loads(menu_json)
        else:
            menu_data = menu_json
        validated_menu = MenuModel(root=menu_data).root
        flows = []
        for category, items in validated_menu.items():
            category_response = f"📋 {category.capitalize()} disponibles:\n"
            for item_name, details in items.items():
                category_response += f"- {item_name}: {details['descripcion']} (${details['precio']})\n"
                flows.append({
                    "user_message": f"quiero {item_name.lower()}",
                    "bot_response": f"¡Buena elección! {item_name}: {details['descripcion']} por ${details['precio']}. ¿Confirmas el pedido?"
                })
            flows.append({
                "user_message": f"ver {category.lower()}",
                "bot_response": category_response
            })
        flows.append({
            "user_message": "ver menú",
            "bot_response": "¡Claro! Aquí tienes nuestro menú completo:\n" + "\n".join(
                f"📋 {category.capitalize()}: {', '.join(items.keys())}" for category, items in validated_menu.items()
            )
        })
        return flows
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear JSON de menú: {str(e)}")
        return []
    except ValidationError as e:
        logger.error(f"Formato inválido de menu_json: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error inesperado al procesar menú: {str(e)}")
        return []

def load_initial_templates():
    with get_session() as session:
        expected_templates = [
            {
                "name": "Ventas Tienda Online",
                "tone": "amigable",
                "purpose": "vender productos y responder preguntas",
                "description": "Ideal para tiendas online. Incluye flujos para saludar, mostrar catálogo y tomar pedidos.",
                "flows": json.dumps([
                    {"user_message": "hola", "bot_response": "¡Hola! Bienvenid@ a mi tienda. ¿Qué te gustaría comprar hoy? 😊"},
                    {"user_message": "precio", "bot_response": "Dime qué producto te interesa y te doy el precio al instante. 💰"}
                ])
            },
            {
                "name": "Soporte Técnico",
                "tone": "profesional",
                "purpose": "resolver problemas técnicos",
                "description": "Perfecto para empresas de tecnología. Ayuda a resolver problemas técnicos paso a paso.",
                "flows": json.dumps([
                    {"user_message": "tengo un problema", "bot_response": "Describe tu problema y te ayudaré paso a paso."},
                    {"user_message": "no funciona", "bot_response": "¿Puedes dar más detalles? Estoy aquí para solucionarlo."}
                ])
            },
            {
                "name": "Reservas de Restaurante",
                "tone": "amigable",
                "purpose": "gestionar reservas y responder consultas",
                "description": "Diseñado para restaurantes. Gestiona reservas y responde preguntas sobre el menú.",
                "flows": json.dumps([
                    {"user_message": "hola", "bot_response": "¡Hola! Bienvenid@ a nuestro restaurante. ¿Quieres reservar una mesa? 🍽️"},
                    {"user_message": "reservar", "bot_response": "Claro, dime para cuántas personas y a qué hora. ¡Te ayudo en un segundo!"},
                    {"user_message": "menú", "bot_response": "Tenemos platos deliciosos: pasta, carnes y postres. ¿Te envío el menú completo?"}
                ])
            },
            {
                "name": "Atención al Cliente - Ecommerce",
                "tone": "profesional",
                "purpose": "gestionar pedidos y devoluciones",
                "description": "Para tiendas online grandes. Gestiona pedidos, devoluciones y dudas frecuentes.",
                "flows": json.dumps([
                    {"user_message": "estado de mi pedido", "bot_response": "Por favor, dame tu número de pedido y lo verifico de inmediato."},
                    {"user_message": "devolver producto", "bot_response": "Claro, indícame el producto y el motivo. Te guiaré en el proceso de devolución."},
                    {"user_message": "hola", "bot_response": "Hola, gracias por contactarnos. ¿En qué puedo ayudarte hoy?"}
                ])
            },
            {
                "name": "Promoción de Servicios",
                "tone": "divertido",
                "purpose": "promocionar servicios y captar clientes",
                "description": "Para freelancers y agencias. Promociona servicios con un tono alegre y atractivo.",
                "flows": json.dumps([
                    {"user_message": "hola", "bot_response": "¡Hey, hola! ¿List@ para descubrir algo genial? Ofrecemos servicios que te van a encantar. 🎉"},
                    {"user_message": "qué ofreces", "bot_response": "Desde diseño épico hasta soluciones locas. ¿Qué necesitas? ¡Te lo cuento todo!"},
                    {"user_message": "precio", "bot_response": "Los precios son tan buenos que te van a hacer saltar de emoción. ¿Qué servicio te interesa?"}
                ])
            },
            {
                "name": "Asistente de Eventos",
                "tone": "amigable",
                "purpose": "gestionar invitaciones y detalles de eventos",
                "description": "Para organizadores de eventos. Gestiona invitaciones y responde dudas sobre fechas y lugares.",
                "flows": json.dumps([
                    {"user_message": "hola", "bot_response": "¡Hola! ¿Vienes a nuestro próximo evento? Te cuento todo lo que necesitas saber. 🎈"},
                    {"user_message": "cuándo es", "bot_response": "Dime qué evento te interesa y te paso la fecha y hora exactas."},
                    {"user_message": "registrarme", "bot_response": "¡Genial! Dame tu nombre y te apunto en la lista. ¿Algo más que quieras saber?"}
                ])
            },
            {
                "name": "Soporte de Suscripciones",
                "tone": "serio",
                "purpose": "gestionar suscripciones y pagos",
                "description": "Para servicios de suscripción. Gestiona cancelaciones y problemas de pago con profesionalismo.",
                "flows": json.dumps([
                    {"user_message": "cancelar suscripción", "bot_response": "Lamento que quieras cancelar. Por favor, indícame tu ID de suscripción para proceder."},
                    {"user_message": "pago fallido", "bot_response": "Verifiquemos eso. Proporcióname tu correo o número de suscripción y lo solucionamos."},
                    {"user_message": "hola", "bot_response": "Buenos días, estoy aquí para ayudarte con tu suscripción. ¿En qué puedo asistirte?"}
                ])
            }
        ]

        for template_data in expected_templates:
            template = session.query(Template).filter_by(name=template_data["name"]).first()
            if not template:
                session.add(Template(**template_data))
                logger.info(f"Plantilla '{template_data['name']}' creada.")
            else:
                for key, value in template_data.items():
                    setattr(template, key, value)
                logger.info(f"Plantilla '{template_data['name']}' actualizada.")
        session.commit()
        logger.info("Carga de plantillas completada.")

@app.route('/api/templates', methods=['GET'])
@jwt_required()
def get_templates():
    with get_session() as session:
        templates = session.query(Template).all()
        return jsonify({
            'templates': [
                {
                    'id': t.id,
                    'name': t.name,
                    'description': t.description,
                    'flows': json.loads(t.flows)
                } for t in templates
            ]
        })

# Rutas de autenticación
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = RegisterModel(**request.form)
            with get_session() as session:
                if session.query(User).filter_by(email=data.email).first():
                    flash('El email ya está registrado', 'error')
                    return redirect(url_for('register'))
                
                hashed_password = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                user = User(email=data.email, password=hashed_password)
                session.add(user)
                session.flush()

                verification_token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=24))
                verification_link = url_for('verify_email', token=verification_token, _external=True)

                try:
                    msg = Message(
                        subject="Verifica tu correo - Plubot",
                        recipients=[data.email],
                        body=f"Hola,\n\nPor favor verifica tu correo haciendo clic en este enlace: {verification_link}\n\nEste enlace expira en 24 horas.\n\nSaludos,\nEl equipo de Plubot"
                    )
                    mail.send(msg)
                    flash('Revisa tu correo para verificar tu cuenta.', 'success')
                except Exception as e:
                    logger.exception(f"Error al enviar correo de verificación: {str(e)}")
                    flash('Usuario creado, pero error al enviar correo de verificación.', 'warning')

                return redirect(url_for('login'))
        except ValidationError as e:
            flash(str(e), 'error')
            return redirect(url_for('register'))
        except Exception as e:
            logger.exception(f"Error en /register: {str(e)}")
            flash('Error al registrar. Intenta de nuevo.', 'error')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/verify_email/<token>', methods=['GET'])
def verify_email(token):
    try:
        decoded_token = decode_token(token)
        user_id = decoded_token['sub']
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                flash('Usuario no encontrado.', 'error')
                return redirect(url_for('login'))
            if user.is_verified:
                flash('Tu correo ya está verificado.', 'info')
                return redirect(url_for('login'))
            user.is_verified = True
            flash('Correo verificado con éxito.', 'success')
            return redirect(url_for('login'))
    except Exception as e:
        logger.exception(f"Error al verificar correo: {str(e)}")
        flash('Enlace de verificación inválido o expirado.', 'error')
        return redirect(url_for('register'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        logger.info(f"POST en /login con datos: {request.form}")
        try:
            data = LoginModel(**request.form)
            with get_session() as session:
                user = session.query(User).filter_by(email=data.email).first()
                if not user or not bcrypt.checkpw(data.password.encode('utf-8'), user.password.encode('utf-8')):
                    logger.warning("Credenciales inválidas")
                    flash('Credenciales inválidas', 'error')
                    return redirect(url_for('login'))
                
                if not user.is_verified:
                    logger.warning("Correo no verificado")
                    flash('Por favor verifica tu correo.', 'error')
                    return redirect(url_for('login'))

                access_token = create_access_token(identity=str(user.id))
                response = redirect(url_for('create_page'))
                set_access_cookies(response, access_token)
                flash('Inicio de sesión exitoso', 'success')
                return response
        except ValidationError as e:
            logger.error(f"Error de validación en /login: {str(e)}")
            flash(str(e), 'error')
            return redirect(url_for('login'))
        except Exception as e:
            logger.exception(f"Error en /login: {str(e)}")
            flash('Error en inicio de sesión.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route("/logout", methods=["POST"])
def logout():
    response = jsonify({"message": "Sesión cerrada"})
    unset_jwt_cookies(response)
    return response

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        with get_session() as session:
            user = session.query(User).filter_by(email=email).first()
            if user:
                try:
                    token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=1))
                    reset_link = url_for('reset_password', token=token, _external=True)
                    msg = Message(
                        subject="Restablecer tu contraseña",
                        recipients=[email],
                        body=f"Hola,\n\nPara restablecer tu contraseña, haz clic en el siguiente enlace: {reset_link}\n\nSi no solicitaste esto, ignora este correo.\n\nSaludos,\nEl equipo de Plubot"
                    )
                    mail.send(msg)
                    flash('Enlace de restablecimiento enviado a tu correo.', 'success')
                except Exception as e:
                    logger.exception(f"Error al enviar correo de restablecimiento: {str(e)}")
                    flash('Error al enviar el enlace de restablecimiento.', 'error')
            else:
                flash('No se encontró un usuario con ese correo.', 'error')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/change_password', methods=['GET', 'POST'])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user or not bcrypt.checkpw(current_password.encode('utf-8'), user.password.encode('utf-8')):
                flash('La contraseña actual es incorrecta.', 'error')
                return redirect(url_for('change_password'))

            if new_password != confirm_password:
                flash('Las contraseñas nuevas no coinciden.', 'error')
                return redirect(url_for('change_password'))

            user.password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            try:
                msg = Message(
                    subject="Tu contraseña ha sido cambiada",
                    recipients=[user.email],
                    body="Hola,\n\nTu contraseña ha sido cambiada exitosamente.\n\nSi no realizaste este cambio, contáctanos de inmediato.\n\nSaludos,\nEl equipo de Plubot"
                )
                mail.send(msg)
                flash('Contraseña cambiada con éxito.', 'success')
            except Exception as e:
                logger.exception(f"Error al enviar correo de confirmación: {str(e)}")
                flash('Contraseña cambiada, pero error al enviar notificación.', 'warning')
        return redirect(url_for('index'))
    return render_template('change_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        decoded_token = decode_token(token)
        user_id = decoded_token['sub']
    except Exception as e:
        flash('Enlace de restablecimiento inválido o expirado.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash('Las contraseñas no coinciden.', 'error')
            return redirect(url_for('reset_password', token=token))

        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                flash('Usuario no encontrado.', 'error')
                return redirect(url_for('login'))
            user.password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            try:
                msg = Message(
                    subject="Tu contraseña ha sido restablecida",
                    recipients=[user.email],
                    body="Hola,\n\nTu contraseña ha sido restablecida exitosamente.\n\nSi no realizaste este cambio, contáctanos de inmediato.\n\nSaludos,\nEl equipo de Plubot"
                )
                mail.send(msg)
                flash('Contraseña restablecida con éxito.', 'success')
            except Exception as e:
                logger.exception(f"Error al enviar correo de confirmación: {str(e)}")
                flash('Contraseña restablecida, pero error al enviar notificación.', 'warning')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

# Rutas principales
@app.route('/favicon.ico')
def favicon():
    return send_file('static/img/favicon.ico')

@app.route('/apple-touch-icon-precomposed.png')
@app.route('/apple-touch-icon.png')
def apple_touch_icon():
    return send_file('static/img/favicon.ico')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        name = request.form.get('nombre')
        email = request.form.get('email')
        message_content = request.form.get('message')

        logger.info(f"Recibido formulario: nombre={name}, email={email}")
        try:
            msg = Message(
                subject=f"Nuevo mensaje de contacto de {name}",
                recipients=['info@plubot.com'],
                body=f"Nombre: {name}\nCorreo: {email}\nMensaje: {message_content}"
            )
            mail.send(msg)
            logger.info("Correo enviado a info@plubot.com")

            confirmation_msg = Message(
                subject="Gracias por contactarnos",
                recipients=[email],
                body=f"Hola {name},\n\nGracias por tu mensaje. Nos pondremos en contacto contigo pronto.\n\nSaludos,\nEl equipo de Plubot"
            )
            mail.send(confirmation_msg)
            logger.info(f"Correo de confirmación enviado a {email}")
            return jsonify({'success': True, 'message': 'Mensaje enviado con éxito'}), 200
        except Exception as e:
            logger.exception(f"Error al enviar correo: {str(e)}")
            return jsonify({'success': False, 'message': 'Error al enviar el mensaje'}), 500
    return render_template('contact.html')

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    try:
        msg = Message(
            subject="Bienvenido a nuestro boletín",
            recipients=[email],
            body="Gracias por suscribirte al boletín de Plubot. Recibirás nuestras últimas noticias y actualizaciones.\n\nSaludos,\nEl equipo de Plubot"
        )
        mail.send(msg)
        logger.info(f"Correo de suscripción enviado a {email}")
        return jsonify({'success': True, 'message': 'Suscripción exitosa'}), 200
    except Exception as e:
        logger.exception(f"Error al enviar correo de suscripción: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al suscribirte'}), 500

@app.route('/create-prompt')
def create_prompt():
    return render_template('auth_prompt.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/case_studies')
def case_studies():
    return render_template('case_studies.html')

@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/blog/5-formas-de-usar-whatsapp-para-aumentar-tus-ventas')
def blog_whatsapp_ventas():
    return render_template('blog-whatsapp-ventas.html')

@app.route('/blog/automatizacion-para-emprendedores-como-ahorrar-tiempo')
def blog_automatizacion_emprendedores():
    return render_template('blog-automatizacion-emprendedores.html')

@app.route('/blog/el-futuro-de-la-atencion-al-cliente-ia-y-chatbots')
def blog_futuro_atencion_cliente():
    return render_template('blog-futuro-atencion-cliente.html')

@app.route('/particulas')
def particulas():
    return render_template('particulas.html')

@app.route('/api/grok', methods=['POST'])
def grok_api():
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        history = data.get('history', [])
        if not user_message:
            return jsonify({'error': 'No se proporcionó mensaje'}), 400
        
        messages = [
            {"role": "system", "content": "Eres Plubot de Plubot Web. Responde amigable, breve y con tono alegre (máx. 2-3 frases). Usa emojis si aplica."}
        ] + history + [{"role": "user", "content": user_message}]
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api.x.ai/v1/chat/completions",
                    json={
                        "model": "grok-2-1212",
                        "messages": messages,
                        "temperature": 0.5,
                        "max_tokens": 50
                    },
                    headers={
                        "Authorization": f"Bearer {XAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    timeout=10
                )
                response.raise_for_status()
                message = response.json()['choices'][0]['message']['content']
                logger.info(f"Respuesta de Grok: {message}")
                return jsonify({'response': message})
            except HTTPError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                logger.exception(f"Error en /api/grok: {str(e)}")
                return jsonify({'error': 'Error al conectar con Grok'}), 500
    except Exception as e:
        logger.exception(f"Error en /api/grok: {str(e)}")
        return jsonify({'error': 'Error al procesar la solicitud'}), 500

# Rutas del creador de chatbots
@app.route('/create', methods=['GET', 'POST'])
@jwt_required()
def create_page():
    logger.info("Entrando en create_page")
    load_initial_templates()
    user_id = get_jwt_identity()
    logger.info(f"Acceso a /create por usuario ID: {user_id}")
    
    if request.method == 'POST':
        try:
            data = request.get_json() or request.form
            bot_data = {
                'name': data.get('name'),
                'tone': data.get('tone', 'amigable'),
                'purpose': data.get('purpose', 'ayudar a los clientes'),
                'whatsapp_number': data.get('whatsapp_number'),
                'business_info': data.get('business_info'),
                'pdf_url': data.get('pdf_url'),
                'image_url': data.get('image_url'),
                'flows': data.get('flows', []),
                'menu_json': data.get('menu_json'),
                'template_id': data.get('template_id')
            }
            if not bot_data['name']:
                return jsonify({'status': 'error', 'message': 'El nombre es obligatorio'}), 400
            with get_session() as session:
                response = create_chatbot(**bot_data, session=session, user_id=user_id)
                return jsonify({'message': response})
        except ValidationError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.exception(f"Error al guardar bot en /create: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Error al crear el chatbot'}), 500
    
    logger.info("Renderizando create.html")
    return render_template('create.html')

def create_chatbot(
    name: str,
    tone: str,
    purpose: str,
    whatsapp_number: Optional[str] = None,
    business_info: Optional[str] = None,
    pdf_url: Optional[str] = None,
    image_url: Optional[str] = None,
    flows: Optional[List[Dict]] = None,
    menu_json: Optional[Any] = None,
    template_id: Optional[int] = None,
    session=None,
    user_id: Optional[str] = None
) -> str:
    logger.info(f"Creando chatbot: {name}, tono: {tone}, propósito: {purpose}")
    with session.no_autoflush:
        if template_id:
            template = session.query(Template).filter_by(id=template_id).first()
            if template:
                tone = template.tone
                purpose = template.purpose
                flows = json.loads(template.flows)
                logger.info(f"Usando plantilla {template.name} con ID {template_id}")

        if menu_json:
            menu_flows = parse_menu_to_flows(menu_json)
            flows = (flows or []) + menu_flows

        system_message = f"Eres un chatbot {tone} llamado '{name}'. Tu propósito es {purpose}. Usa un tono {tone} y gramática correcta."
        if business_info:
            system_message += f"\nNegocio: {business_info}"
        if pdf_url:
            system_message += "\nContenido del PDF será añadido tras procesar."
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": "Dame un mensaje de bienvenida."}
        ]
        initial_message = call_grok(messages, max_tokens=100)

        chatbot = Chatbot(
            name=name,
            tone=tone,
            purpose=purpose,
            initial_message=initial_message,
            whatsapp_number=whatsapp_number,
            business_info=business_info,
            pdf_url=pdf_url,
            image_url=image_url,
            user_id=user_id
        )
        session.add(chatbot)
        session.flush()

        if pdf_url:
            process_pdf_async.delay(chatbot.id, pdf_url)

        if flows:
            for index, flow in enumerate(flows):
                if flow.get('user_message') and flow.get('bot_response'):
                    session.add(Flow(
                        chatbot_id=chatbot.id,
                        user_message=flow['user_message'],
                        bot_response=flow['bot_response'],
                        position=index,
                        intent=flow.get('intent', 'general')
                    ))
        
        return f"Chatbot '{name}' creado con éxito. ID: {chatbot.id}. Mensaje inicial: {initial_message}"

@app.route('/create-bot', methods=['OPTIONS', 'POST', 'GET'])
@jwt_required()
def create_bot():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    if request.method == 'GET':
        logger.info(f"GET recibido en /create-bot desde: {request.referrer}")
        return jsonify({'message': 'GET no permitido, usa POST', 'referrer': request.referrer}), 405
    
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            logger.info("Solicitud POST recibida en /create-bot")
            data = request.get_json()
            logger.info(f"Datos recibidos: {data}")
            bot_name = data.get('name', 'Sin nombre')
            tone = data.get('tone', 'amigable')
            purpose = data.get('purpose', 'asistir a los usuarios')
            whatsapp_number = data.get('whatsapp_number')
            business_info = data.get('business_info')
            pdf_url = data.get('pdf_url')
            image_url = data.get('image_url')
            flows_raw = data.get('flows', [])
            menu_json = data.get('menu_json')
            template_id = data.get('template_id')

            flows = []
            user_messages = set()
            for flow in flows_raw:
                try:
                    validated_flow = FlowModel(**flow)
                    user_msg = validated_flow.user_message.strip().lower()
                    bot_resp = validated_flow.bot_response.strip()
                    if not user_msg or not bot_resp:
                        return jsonify({
                            'status': 'error',
                            'message': 'Mensajes de usuario y respuesta no pueden estar vacíos'
                        }), 400
                    if user_msg in user_messages:
                        return jsonify({
                            'status': 'error',
                            'message': f'Mensaje de usuario "{user_msg}" duplicado'
                        }), 400
                    user_messages.add(user_msg)
                    flows.append(validated_flow.dict())
                except ValidationError as e:
                    logger.warning(f"Flujo inválido: {flow}. Error: {str(e)}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Flujo inválido: {str(e)}'
                    }), 400

            if whatsapp_number:
                try:
                    WhatsAppNumberModel.validate_whatsapp_number(whatsapp_number)
                except ValueError:
                    return jsonify({
                        'status': 'error',
                        'message': 'Número de WhatsApp debe tener formato internacional'
                    }), 400
                
                if not validate_whatsapp_number(whatsapp_number):
                    return jsonify({
                        'status': 'error',
                        'message': 'Número de WhatsApp no habilitado para este servicio'
                    }), 400
                
                if session.query(Chatbot).filter_by(whatsapp_number=whatsapp_number).first():
                    return jsonify({
                        'status': 'error',
                        'message': f'El número {whatsapp_number} ya está vinculado'
                    }), 400

            response = create_chatbot(
                bot_name, tone, purpose, whatsapp_number, business_info,
                pdf_url, image_url, flows, menu_json, template_id,
                session=session, user_id=user_id
            )
            logger.info(f"Respuesta enviada: {response}")
            return jsonify({'message': response}), 200
        except ValidationError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.exception(f"Error en /create-bot: {str(e)}")
            return jsonify({'message': 'Error al crear el chatbot'}), 500

@app.route('/connect-whatsapp', methods=['OPTIONS', 'POST'])
@jwt_required()
def connect_whatsapp():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            data = request.get_json()
            chatbot_id = data.get('chatbot_id')
            phone_number = data.get('phone_number')

            if not chatbot_id or not phone_number:
                return jsonify({
                    'status': 'error',
                    'message': 'Faltan chatbot_id o phone_number'
                }), 400

            if not re.match(r'^\+\d{10,15}$', phone_number):
                return jsonify({
                    'status': 'error',
                    'message': 'Número debe tener formato internacional'
                }), 400

            chatbot = session.query(Chatbot).filter_by(id=chatbot_id, user_id=user_id).first()
            if not chatbot:
                return jsonify({
                    'status': 'error',
                    'message': 'Chatbot no encontrado o no tienes permiso'
                }), 404

            if not validate_whatsapp_number(phone_number):
                return jsonify({
                    'status': 'error',
                    'message': 'Número no registrado en Twilio'
                }), 400

            message = twilio_client.messages.create(
                body="¡Hola! Soy Plubot. Responde 'VERIFICAR' para conectar tu chatbot.",
                from_=f'whatsapp:{TWILIO_PHONE}',
                to=f'whatsapp:{phone_number}'
            )
            logger.info(f"Mensaje enviado a {phone_number}: {message.sid}")
            chatbot.whatsapp_number = phone_number
            session.commit()
            return jsonify({
                'status': 'success',
                'message': f'Verifica tu número {phone_number} respondiendo "VERIFICAR"'
            }), 200
        except TwilioRestException as e:
            logger.exception(f"Error con Twilio: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Error con Twilio. Verifica tus credenciales'
            }), 500
        except Exception as e:
            logger.exception(f"Error en /connect-whatsapp: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Error inesperado'
            }), 500

@app.route('/delete-bot', methods=['OPTIONS', 'POST'])
@jwt_required()
def delete_bot():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            logger.info("Solicitud recibida en /delete-bot")
            data = request.get_json()
            logger.info(f"Datos recibidos: {data}")
            chatbot_id = data.get('chatbot_id')
            if not chatbot_id:
                logger.error("Falta chatbot_id")
                return jsonify({'message': 'Falta chatbot_id'}), 400
            chatbot_id = int(chatbot_id)
            if chatbot_id <= 0:
                raise ValueError("ID debe ser positivo")
            chatbot = session.query(Chatbot).filter_by(id=chatbot_id, user_id=user_id).first()
            if not chatbot:
                logger.error(f"Chatbot {chatbot_id} no encontrado")
                return jsonify({
                    'message': 'Chatbot no encontrado o no tienes permiso'
                }), 404
            session.query(Conversation).filter_by(chatbot_id=chatbot_id).delete()
            session.query(Flow).filter_by(chatbot_id=chatbot_id).delete()
            session.delete(chatbot)
            logger.info(f"Chatbot {chatbot_id} eliminado")
            return jsonify({
                'message': f'Chatbot {chatbot_id} eliminado con éxito'
            }), 200
        except Exception as e:
            logger.exception(f"Error en /delete-bot: {str(e)}")
            return jsonify({'message': 'Error al eliminar el chatbot'}), 500

@app.route('/update-bot', methods=['OPTIONS', 'POST'])
@jwt_required()
def update_bot():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            logger.info("Solicitud recibida en /update-bot")
            data = request.get_json()
            logger.info(f"Datos recibidos: {data}")
            chatbot_id = data.get('chatbot_id')
            name = data.get('name')
            tone = data.get('tone')
            purpose = data.get('purpose')
            whatsapp_number = data.get('whatsapp_number')
            business_info = data.get('business_info')
            pdf_url = data.get('pdf_url')
            image_url = data.get('image_url')
            flows = data.get('flows', [])
            menu_json = data.get('menu_json')

            if not all([chatbot_id, name, tone, purpose]):
                logger.error("Faltan campos obligatorios")
                return jsonify({
                    'message': 'Faltan campos obligatorios'
                }), 400

            chatbot = session.query(Chatbot).filter_by(id=chatbot_id, user_id=user_id).first()
            if not chatbot:
                logger.error(f"Chatbot {chatbot_id} no encontrado")
                return jsonify({
                    'message': 'Chatbot no encontrado o no tienes permiso'
                }), 404

            validated_flows = []
            user_messages = set()
            for flow in flows:
                try:
                    validated_flow = FlowModel(**flow)
                    user_msg = validated_flow.user_message.lower()
                    if not user_msg or not validated_flow.bot_response:
                        return jsonify({
                            'status': 'error',
                            'message': 'Mensajes no pueden estar vacíos'
                        }), 400
                    if user_msg in user_messages:
                        return jsonify({
                            'status': 'error',
                            'message': f'Mensaje de usuario "{user_msg}" duplicado'
                        }), 400
                    user_messages.add(user_msg)
                    validated_flows.append(validated_flow.dict())
                except ValidationError as e:
                    logger.warning(f"Flujo inválido: {flow}. Error: {str(e)}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Flujo inválido: {str(e)}'
                    }), 400

            if whatsapp_number and whatsapp_number != chatbot.whatsapp_number:
                WhatsAppNumberModel.validate_whatsapp_number(whatsapp_number)
                if not validate_whatsapp_number(whatsapp_number):
                    return jsonify({
                        'status': 'error',
                        'message': 'Número de WhatsApp inválido'
                    }), 400
                existing_bot = session.query(Chatbot).filter_by(whatsapp_number=whatsapp_number).first()
                if existing_bot and existing_bot.id != chatbot_id:
                    return jsonify({
                        'status': 'error',
                        'message': f'Número {whatsapp_number} ya vinculado'
                    }), 400

            if menu_json:
                menu_flows = parse_menu_to_flows(menu_json)
                validated_flows = validated_flows + menu_flows

            pdf_content = chatbot.pdf_content if pdf_url == chatbot.pdf_url else None
            if pdf_url and pdf_url != chatbot.pdf_url:
                process_pdf_async.delay(chatbot_id, pdf_url)

            system_message = f"Eres un chatbot {tone} llamado '{name}'. Tu propósito es {purpose}. Usa un tono {tone} y gramática correcta."
            if business_info:
                system_message += f"\nNegocio: {business_info}"
            if pdf_content:
                system_message += f"\nContenido del PDF: {pdf_content}"
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": "Dame un mensaje de bienvenida."}
            ]
            initial_message = call_grok(messages, max_tokens=100)

            chatbot.name = name
            chatbot.tone = tone
            chatbot.purpose = purpose
            chatbot.whatsapp_number = whatsapp_number
            chatbot.business_info = business_info
            chatbot.pdf_url = pdf_url
            chatbot.image_url = image_url
            chatbot.initial_message = initial_message

            session.query(Flow).filter_by(chatbot_id=chatbot_id).delete()
            for index, flow in enumerate(validated_flows):
                if flow.get('user_message') and flow.get('bot_response'):
                    session.add(Flow(
                        chatbot_id=chatbot_id,
                        user_message=flow['user_message'],
                        bot_response=flow['bot_response'],
                        position=index,
                        intent=flow.get('intent', 'general')
                    ))
            
            logger.info(f"Chatbot {chatbot_id} actualizado")
            return jsonify({
                'message': f"Chatbot '{name}' actualizado con éxito"
            }), 200
        except ValidationError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.exception(f"Error en /update-bot: {str(e)}")
            return jsonify({'message': 'Error al actualizar el chatbot'}), 500

@app.route('/list-bots', methods=['GET'])
@jwt_required()
def list_bots():
    user_id = get_jwt_identity()
    logger.info(f"Usuario autenticado: {user_id}")
    with get_session() as session:
        chatbots = session.query(Chatbot).filter_by(user_id=user_id).all()
        chatbots_data = [
            {
                'id': bot.id,
                'name': bot.name,
                'tone': bot.tone,
                'purpose': bot.purpose,
                'whatsapp_number': bot.whatsapp_number,
                'initial_message': bot.initial_message
            } for bot in chatbots
        ]
        return jsonify({'chatbots': chatbots_data})

@app.route('/conversation-history', methods=['OPTIONS', 'POST'])
@jwt_required()
def conversation_history():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            logger.info("Solicitud recibida en /conversation-history")
            data = request.get_json()
            logger.info(f"Datos recibidos: {data}")
            chatbot_id = data.get('chatbot_id')
            user_id_from_data = data.get('user_id', 'web_user')
            if not chatbot_id:
                return jsonify({'message': 'Falta chatbot_id'}), 400
            chatbot = session.query(Chatbot).filter_by(id=chatbot_id, user_id=user_id).first()
            if not chatbot:
                return jsonify({
                    'message': 'Chatbot no encontrado o no tienes permiso'
                }), 404
            history = session.query(Conversation).filter_by(
                chatbot_id=chatbot_id,
                user_id=user_id_from_data
            ).order_by(Conversation.timestamp).all()
            history_list = [{'role': conv.role, 'message': conv.message} for conv in history]
            logger.info(f"Historial enviado para chatbot {chatbot_id}")
            return jsonify({'history': history_list}), 200
        except Exception as e:
            logger.exception(f"Error en /conversation-history: {str(e)}")
            return jsonify({'message': 'Error al obtener historial'}), 500

@app.route('/chat', methods=['OPTIONS', 'POST'])
@jwt_required()
def chat():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    
    user_id = get_jwt_identity()
    is_mobile = 'Mobile' in request.headers.get('User-Agent', '')
    with get_session() as session:
        try:
            logger.info("Solicitud recibida en /chat")
            data = request.get_json()
            logger.info(f"Datos recibidos: {data}")
            chatbot_id = data.get('chatbot_id')
            user_id_from_data = data.get('user_id', 'web_user')
            message = data.get('message')
            if not chatbot_id or not message:
                return jsonify({
                    'message': 'Faltan chatbot_id o message'
                }), 400

            if not check_quota(user_id, session):
                return jsonify({
                    'message': 'Límite de 100 mensajes alcanzado. Suscríbete al plan premium.'
                }), 403

            chatbot = session.query(Chatbot).filter_by(id=chatbot_id, user_id=user_id).first()
            if not chatbot:
                return jsonify({
                    'message': 'Chatbot no encontrado o no tienes permiso'
                }), 404
            
            flows = session.query(Flow).filter_by(chatbot_id=chatbot_id).order_by(Flow.position).all()
            response = next(
                (flow.bot_response for flow in flows if flow.user_message.lower() in message.lower()),
                None
            )
            
            if not response:
                history = session.query(Conversation).filter_by(
                    chatbot_id=chatbot_id,
                    user_id=user_id_from_data
                ).order_by(Conversation.timestamp).all()
                system_message = f"Eres un chatbot {chatbot.tone} llamado '{chatbot.name}'. Tu propósito es {chatbot.purpose}. Usa un tono {chatbot.tone} y gramática correcta."
                if chatbot.business_info:
                    system_message += f"\nNegocio: {chatbot.business_info}"
                if chatbot.pdf_content:
                    system_message += f"\nContenido del PDF: {chatbot.pdf_content}"
                messages = [{"role": "system", "content": system_message}]
                if history:
                    messages.extend([{"role": conv.role, "content": conv.message} for conv in history[-5:]])
                messages.append({"role": "user", "content": message})
                max_tokens = 100 if is_mobile else (150 if len(message) < 100 else 300)
                response = call_grok(messages, max_tokens=max_tokens)
                if chatbot.image_url and "logo" in message.lower() and not is_mobile:
                    response += f"\nLogo: {chatbot.image_url}"

            session.add(Conversation(
                chatbot_id=chatbot_id,
                user_id=user_id_from_data,
                message=message,
                role="user"
            ))
            session.add(Conversation(
                chatbot_id=chatbot_id,
                user_id=user_id_from_data,
                message=response,
                role="assistant"
            ))
            increment_quota(user_id, session)
            logger.info(f"Respuesta enviada: {response}")
            return jsonify({'response': response}), 200
        except Exception as e:
            logger.exception(f"Error en /chat: {str(e)}")
            return jsonify({'message': 'Error al procesar el chat'}), 500

@app.route('/upload-file', methods=['POST'])
@jwt_required()
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No se proporcionó archivo'}), 400
    file = request.files['file']
    file_type = request.form.get('type')
    if file_type not in ['pdf', 'image']:
        return jsonify({'message': 'Tipo de archivo no válido'}), 400

    file.seek(0, os.SEEK_END)
    if file.tell() > 5 * 1024 * 1024:
        return jsonify({'message': 'Archivo demasiado grande (máx. 5MB)'}), 400
    file.seek(0)

    mime = magic.Magic(mime=True)
    file_buffer = file.read()
    mime_type = mime.from_buffer(file_buffer)
    file.seek(0)

    allowed_mime_types = {
        'pdf': ['application/pdf'],
        'image': ['image/jpeg', 'image/png', 'image/gif']
    }
    if mime_type not in allowed_mime_types[file_type]:
        return jsonify({
            'message': f'Tipo de archivo no permitido. Se esperaba {file_type}'
        }), 400

    filename = f"{uuid.uuid4()}_{file.filename}"
    upload_dir = os.path.join('static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    file_url = f"/static/uploads/{filename}"
    logger.info(f"Archivo subido: {file_url}")
    return jsonify({'file_url': file_url}), 200

# Operaciones de Redis
def safe_redis_get(key: str, default: Any = None) -> Any:
    if redis_client and ensure_redis_connection():
        try:
            value = redis_client.get(key)
            return json.loads(value) if value else default
        except redis.exceptions.RedisError as e:
            logger.warning(f"Error al leer de Redis para clave {key}: {str(e)}")
            return default
    logger.warning(f"Redis no disponible para get: {key}")
    return default

def safe_redis_set(key: str, value: Any, expire_seconds: Optional[int] = None):
    if redis_client and ensure_redis_connection():
        try:
            serialized_value = json.dumps(value)
            if expire_seconds:
                redis_client.setex(key, expire_seconds, serialized_value)
            else:
                redis_client.set(key, serialized_value)
            logger.debug(f"Valor guardado en Redis para clave {key}")
        except redis.exceptions.RedisError as e:
            logger.warning(f"Error al escribir en Redis para clave {key}: {str(e)}")
    else:
        logger.warning(f"Redis no disponible para set: {key}")

def get_conversation_state(sender: str) -> Dict[str, Any]:
    default_state = {
        "step": "greet",
        "data": {
            "business_type": "",
            "needs": [],
            "specifics": {},
            "contacted": False
        }
    }
    return safe_redis_get(f"conv_state:{sender}", default_state)

def set_conversation_state(sender: str, state: Dict[str, Any]):
    safe_redis_set(f"conv_state:{sender}", state, expire_seconds=86400)  # Expira en 24 horas

# Ruta para manejar mensajes de WhatsApp
@app.route('/whatsapp', methods=['POST'])
def whatsapp():
    logger.info(f"Solicitud recibida en /whatsapp: {request.values}")
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', 'unknown')
    to_number = request.values.get('To', 'unknown')
    logger.info(f"Mensaje recibido de {sender} para {to_number}: {incoming_msg}")

    if not incoming_msg:
        resp = MessagingResponse()
        resp.message("No se recibió mensaje válido. Envía algo.")
        return str(resp)

    with get_session() as session:
        chatbot = session.query(Chatbot).filter_by(whatsapp_number=to_number).first()
        
        if not chatbot:
            chatbot = session.query(Chatbot).filter_by(whatsapp_number=sender).first()
            if chatbot and incoming_msg.upper() == "VERIFICAR":
                chatbot.whatsapp_number = to_number
                session.commit()
                resp = MessagingResponse()
                resp.message(f"¡Número verificado! Tu chatbot '{chatbot.name}' conectado.")
                logger.info(f"Número {sender} verificado para chatbot {chatbot.id}")
                return str(resp)
            else:
                state = get_conversation_state(sender)
                incoming_msg_lower = incoming_msg.lower()

                info_keywords = ["saber más", "información", "qué son", "cómo funcionan", "detalles", "qué es", "qué haces"]
                price_keywords = ["precio", "coste", "cuánto cuesta", "valor", "tarifa"]
                greeting_keywords = ["hola", "buenos", "buenas", "hey", "cómo estás"]
                business_keywords = ["tengo", "mi negocio", "tienda", "restaurante", "clínica", "hotel"]
                action_keywords = ["quiero crear", "cómo empiezo", "estoy listo", "listo"]

                response = None
                flows = session.query(Flow).filter_by(chatbot_id=1).order_by(Flow.position).all()
                for flow in flows:
                    if flow.user_message.lower() in incoming_msg_lower:
                        response = flow.bot_response
                        break

                if not response:
                    if state["step"] == "greet":
                        if any(k in incoming_msg_lower for k in greeting_keywords):
                            response = "¡Hola! Soy Plubot, tu asistente para crear chatbots increíbles. 😊 ¿En qué puedo ayudarte hoy?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in price_keywords):
                            response = "¡Buena pregunta! 😊 Tienes 100 mensajes gratis al mes, y por 19.99 USD/mes tienes mensajes ilimitados. ¿Quieres probar en https://www.plubot.com/create?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in info_keywords):
                            response = "Plubot es una plataforma para crear chatbots para WhatsApp. 🚀 Automatizan tu negocio y aumentan ventas. ¿Te gustaría saber más?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in action_keywords):
                            response = "¡Genial! 🚀 Ve a https://www.plubot.com/register para empezar. ¿Qué tipo de negocio tienes?"
                            state["step"] = "ask_business_type"
                        else:
                            response = "¡Hola! Soy Plubot. 😊 ¿Qué tipo de negocio tienes? Un Plubot puede ayudarte a automatizar y crecer."
                            state["step"] = "ask_business_type"
                    elif state["step"] == "awaiting_response":
                        if any(k in incoming_msg_lower for k in price_keywords):
                            response = "¡Entendido! 😊 Tienes 100 mensajes gratis al mes, y por 19.99 USD/mes tienes mensajes ilimitados. ¿Quieres empezar en https://www.plubot.com/register?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in info_keywords):
                            response = "Plubot te permite crear chatbots para WhatsApp que trabajan 24/7. 🚀 Automatizan procesos y ahorran tiempo. ¿Te interesa probar en https://www.plubot.com/create?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in business_keywords):
                            state["data"]["business_type"] = incoming_msg
                            response = "¡Entendido! 😊 ¿Qué necesita tu Plubot (ventas, reservas, soporte)? Di 'listo' si no necesitas nada más."
                            state["step"] = "ask_needs"
                        elif any(k in incoming_msg_lower for k in action_keywords):
                            response = "¡Genial! 🚀 Ve a https://www.plubot.com/register para empezar. ¿Qué tipo de negocio tienes?"
                            state["step"] = "ask_business_type"
                        else:
                            messages = [
                                {"role": "system", "content": "Eres Plubot, un asistente útil y amigable de Plubot Web. Responde breve, con tono alegre y emojis si aplica."},
                                {"role": "user", "content": incoming_msg}
                            ]
                            response = call_grok(messages, max_tokens=150)
                            state["step"] = "ask_business_type"
                    elif state["step"] == "ask_business_type":
                        state["data"]["business_type"] = incoming_msg
                        response = "¡Entendido! 😊 ¿Qué necesita tu Plubot (ventas, reservas, soporte)? Di 'listo' si no necesitas nada más."
                        state["step"] = "ask_needs"
                    elif state["step"] == "ask_needs":
                        state["data"]["needs"].append(incoming_msg_lower)
                        response = "¡Perfecto! 😊 ¿Algo más que quieras que haga? Di 'listo' si terminaste."
                        state["step"] = "more_needs"
                    elif state["step"] == "more_needs":
                        if incoming_msg_lower == "listo":
                            needs = state["data"]["needs"]
                            if "ventas" in " ".join(needs):
                                response = "¡Genial! 😊 ¿Cuántos productos incluirías en el catálogo?"
                                state["step"] = "ask_sales_details"
                            elif "soporte" in " ".join(needs):
                                response = "¡Entendido! 😊 ¿Cuántos clientes gestionas por día?"
                                state["step"] = "ask_support_details"
                            elif "reservas" in " ".join(needs):
                                response = "¡Perfecto! 😊 ¿Cuántas reservas esperas por día?"
                                state["step"] = "ask_reservations_details"
                            else:
                                response = "¡Listo! 🚀 Te contactaremos en 24 horas. Crea tu Plubot en https://www.plubot.com/create."
                                state["step"] = "done"
                                state["data"]["contacted"] = True
                        else:
                            state["data"]["needs"].append(incoming_msg_lower)
                            response = "¡Anotado! 😊 ¿Algo más? Di 'listo' si terminaste."
                    elif state["step"] == "ask_sales_details":
                        state["data"]["specifics"]["products"] = incoming_msg
                        response = "¡Gracias! 🚀 Te contactaremos en 24 horas. Crea tu Plubot en https://www.plubot.com/create."
                        state["step"] = "done"
                        state["data"]["contacted"] = True
                    elif state["step"] == "ask_support_details":
                        state["data"]["specifics"]["daily_clients"] = incoming_msg
                        response = "¡Gracias! 🚀 Te contactaremos en 24 horas. Crea tu Plubot en https://www.plubot.com/create."
                        state["step"] = "done"
                        state["data"]["contacted"] = True
                    elif state["step"] == "ask_reservations_details":
                        state["data"]["specifics"]["daily_reservations"] = incoming_msg
                        response = "¡Gracias! 🚀 Te contactaremos en 24 horas. Crea tu Plubot en https://www.plubot.com/create."
                        state["step"] = "done"
                        state["data"]["contacted"] = True
                    elif state["step"] == "done":
                        if any(k in incoming_msg_lower for k in price_keywords):
                            response = "¡Entendido! 😊 Tienes 100 mensajes gratis al mes, y por 19.99 USD/mes tienes mensajes ilimitados. ¿Quieres empezar en https://www.plubot.com/register?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in action_keywords):
                            response = "¡Genial! 🚀 Ve a https://www.plubot.com/register para empezar. ¿Qué tipo de negocio tienes?"
                            state["step"] = "ask_business_type"
                        else:
                            messages = [
                                {"role": "system", "content": "Eres Plubot, un asistente útil y amigable de Plubot Web. Responde breve, con tono alegre y emojis si aplica."},
                                {"role": "user", "content": incoming_msg}
                            ]
                            response = call_grok(messages, max_tokens=150)

                set_conversation_state(sender, state)
        else:
            user_id = chatbot.user_id
            if not check_quota(user_id, session):
                resp = MessagingResponse()
                resp.message("Límite de 100 mensajes alcanzado. Suscríbete en https://www.plubot.com.")
                return str(resp)

            chatbot_id = chatbot.id
            flows = session.query(Flow).filter_by(chatbot_id=chatbot_id).order_by(Flow.position).all()
            response = next(
                (flow.bot_response for flow in flows if flow.user_message.lower() in incoming_msg.lower()),
                None
            )
            if not response:
                history = session.query(Conversation).filter_by(
                    chatbot_id=chatbot_id,
                    user_id=sender
                ).order_by(Conversation.timestamp).all()
                system_message = f"Eres un chatbot {chatbot.tone} llamado '{chatbot.name}'. Tu propósito es {chatbot.purpose}. Usa un tono {chatbot.tone} y gramática correcta."
                if chatbot.business_info:
                    system_message += f"\nNegocio: {chatbot.business_info}"
                if chatbot.pdf_content:
                    system_message += f"\nContenido del PDF: {chatbot.pdf_content}"
                messages = [{"role": "system", "content": system_message}]
                if history:
                    messages.extend([{"role": conv.role, "content": conv.message} for conv in history[-5:]])
                messages.append({"role": "user", "content": incoming_msg})
                response = call_grok(messages, max_tokens=150)

            session.add(Conversation(
                chatbot_id=chatbot_id,
                user_id=sender,
                message=incoming_msg,
                role="user"
            ))
            session.add(Conversation(
                chatbot_id=chatbot_id,
                user_id=sender,
                message=response,
                role="assistant"
            ))
            increment_quota(user_id, session)

        resp = MessagingResponse()
        resp.message(response)
        logger.info(f"Respuesta enviada a {sender}: {response}")
        return str(resp)

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_ENV', 'development') == 'development', host='0.0.0.0', port=5000)