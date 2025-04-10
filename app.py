from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, Response
from flask_mail import Mail, Message
from flask_cors import CORS
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from twilio.twiml.messaging_response import MessagingResponse
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, set_access_cookies, unset_jwt_cookies, decode_token
from pydantic import BaseModel, Field, ValidationError
import re
import os
import requests
import time
import PyPDF2
import json
import logging
import bcrypt
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from requests.exceptions import HTTPError, Timeout
import redis
from redis.connection import ConnectionPool
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
from celery import Celery
from contextlib import contextmanager
from datetime import timedelta
import uuid
from ratelimit import limits, sleep_and_retry

# Configuración inicial
load_dotenv()
app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise ValueError("No se encontró SECRET_KEY en las variables de entorno.")

# Configuración de logging mejorada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('plubot.log'),  # Guardar logs en archivo
        logging.StreamHandler()  # Mostrar logs en consola
    ]
)
logger = logging.getLogger(__name__)

# Configuración de CORS
CORS(app, resources={r"/*": {
    "origins": ["http://localhost:5000", "http://192.168.0.213:5000", "https://www.plubot.com"],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "supports_credentials": True
}})

# Configuración de Redis con mejoras
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
retry = Retry(ExponentialBackoff(cap=10, base=1), retries=5)  # Aumentamos retries a 5
redis_pool = ConnectionPool.from_url(
    REDIS_URL,
    decode_responses=True,
    max_connections=20,  # Aumentado para mayor escalabilidad
    retry=retry,
    retry_on_timeout=True,
    health_check_interval=30,
    socket_timeout=10,  # Aumentado para evitar timeouts prematuros
    socket_connect_timeout=10
)

# Inicializamos el cliente Redis con el pool
redis_client = redis.Redis(
    connection_pool=redis_pool,
    socket_timeout=10,
    socket_connect_timeout=10,
    retry=retry
)

# Función para verificar y reconectar Redis si falla
def ensure_redis_connection():
    global redis_client
    try:
        redis_client.ping()
        logger.info("Conexión a Redis establecida correctamente")
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Redis no disponible: {str(e)}. Intentando reconectar...")
        try:
            redis_client = redis.Redis(
                connection_pool=redis_pool,
                socket_timeout=10,
                socket_connect_timeout=10,
                retry=retry
            )
            redis_client.ping()
            logger.info("Reconexión a Redis exitosa")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Fallo al reconectar a Redis: {str(e)}. Usando modo sin caché.")
            return False
    return True

# Verificamos conexión al iniciar
if not ensure_redis_connection():
    redis_client = None  # Solo se establece como None si falla tras intentar reconectar

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
    broker_pool_limit=5,  # Aumentado para más conexiones
    result_expires=3600,  # Tiempo de expiración de resultados
    broker_transport_options={
        'max_retries': 5,  # Más intentos de reconexión
        'interval_start': 1,
        'interval_step': 2,
        'interval_max': 10
    },
    result_backend_transport_options={
        'retry_policy': {
            'max_retries': 5,  # Más intentos
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
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
mail = Mail(app)

# Configuración de Twilio
twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

# Configuración de JWT
app.config["JWT_SECRET_KEY"] = "super-secret"  # Cambia en producción
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config["JWT_ACCESS_COOKIE_NAME"] = "access_token"
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_COOKIE_SECURE'] = os.getenv('FLASK_ENV', 'development') != 'development'
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'
app.config["JWT_ACCESS_COOKIE_PATH"] = "/"
jwt = JWTManager(app)

# Configuración de la base de datos
engine = create_engine(DATABASE_URL.replace('postgres://', 'postgresql://'))
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default='user')
    is_verified = Column(Boolean, default=False)

class Chatbot(Base):
    __tablename__ = 'chatbots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    tone = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    initial_message = Column(Text, nullable=False)
    whatsapp_number = Column(String, unique=True)
    business_info = Column(Text)
    pdf_url = Column(String)
    pdf_content = Column(Text)
    image_url = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

class Conversation(Base):
    __tablename__ = 'conversations'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chatbot_id = Column(Integer, ForeignKey('chatbots.id'), nullable=False)
    user_id = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    role = Column(String, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())

class Flow(Base):
    __tablename__ = 'flows'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chatbot_id = Column(Integer, ForeignKey('chatbots.id'), nullable=False)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
    intent = Column(String)

class MessageQuota(Base):  # Nuevo modelo para límite de mensajes
    __tablename__ = 'message_quotas'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    month = Column(String, nullable=False)  # Formato: "YYYY-MM"
    message_count = Column(Integer, default=0)
    plan = Column(String, default='free')  # 'free' o 'premium'

class Template(Base):  # Nuevo modelo para plantillas
    __tablename__ = 'templates'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    tone = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    flows = Column(Text, nullable=False)  # JSON con flujos predefinidos

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

@contextmanager
def get_session():
    session = Session()
    try:
        yield session
    except Exception as e:
        session.rollback()
        logger.exception(f"Error en sesión de base de datos: {str(e)}")
        raise e
    finally:
        session.close()

# Modelos Pydantic para validación
class LoginModel(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)

class RegisterModel(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)

class WhatsAppNumberModel(BaseModel):
    whatsapp_number: str

    @classmethod
    def validate_whatsapp_number(cls, value):
        if not re.match(r'^\+\d{10,15}$', value):
            raise ValueError('El número de WhatsApp debe tener el formato +1234567890')
        return value

# Funciones auxiliares
def extract_text_from_pdf(file_stream):
    try:
        reader = PyPDF2.PdfReader(file_stream)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        logger.exception(f"Error al extraer texto del PDF: {str(e)}")
        return ""

def summarize_history(history):
    if len(history) > 5:
        return "Resumen: " + " ".join([conv.message[:50] for conv in history[-5:]])
    return " ".join([conv.message for conv in history])

@sleep_and_retry
@limits(calls=50, period=60)  # Límite de tasa para la API de xAI
def call_grok(messages, max_tokens=150):
    if len(messages) > 4:
        messages = [messages[0]] + messages[-3:]
    
    cache_key = json.dumps(messages)
    result = None

    # Intentamos usar caché solo si Redis está disponible
    if redis_client and ensure_redis_connection():
        try:
            result = redis_client.get(cache_key)
            if result:
                logger.info("Respuesta obtenida desde caché")
                return result
        except redis.exceptions.ConnectionError as e:
            logger.warning(f"Error al leer desde Redis: {str(e)}. Continuando sin caché.")
        except redis.exceptions.TimeoutError as e:
            logger.warning(f"Timeout en Redis: {str(e)}. Continuando sin caché.")

    # Si no hay caché o falla, llamamos a la API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "grok-2-1212", "messages": messages, "temperature": 0.5, "max_tokens": max_tokens}
    try:
        logger.info(f"Enviando solicitud a xAI con payload: {json.dumps(payload)}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()['choices'][0]['message']['content']
        
        # Guardamos en caché solo si Redis está disponible
        if redis_client and ensure_redis_connection():
            try:
                redis_client.setex(cache_key, 3600, result)
                logger.info("Respuesta guardada en caché")
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
                logger.warning(f"Error al guardar en Redis: {str(e)}. Continuando sin caché.")
        
        logger.info(f"Grok response: {result}")
        return result
    except requests.exceptions.ConnectionError as e:
        logger.exception(f"Error de conexión con xAI: {str(e)}")
        return "¡Vaya! La conexión con la IA falló, intenta de nuevo en un momento."
    except requests.exceptions.Timeout as e:
        logger.exception(f"Timeout al conectar con xAI: {str(e)}")
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
def process_pdf_async(chatbot_id, pdf_url):
    with get_session() as session:
        response = requests.get(pdf_url)
        pdf_content = extract_text_from_pdf(response.content)
        chatbot = session.query(Chatbot).filter_by(id=chatbot_id).first()
        if chatbot:
            chatbot.pdf_content = pdf_content
            session.commit()
        logger.info(f"PDF procesado para chatbot {chatbot_id}")

def validate_whatsapp_number(number):
    if not number.startswith('+'):
        number = '+' + number
    try:
        phone_numbers = twilio_client.api.accounts(TWILIO_SID).incoming_phone_numbers.list()
        for phone in phone_numbers:
            if phone.phone_number == number:
                logger.info(f"Número {number} encontrado en tu cuenta Twilio.")
                return True
        logger.warning(f"Número {number} no está registrado en tu cuenta Twilio.")
        return False
    except TwilioRestException as e:
        logger.exception(f"Error al validar número de WhatsApp con Twilio: {str(e)}")
        return False

def check_quota(user_id, session):
    current_month = time.strftime("%Y-%m")
    quota = session.query(MessageQuota).filter_by(user_id=user_id, month=current_month).first()
    if not quota:
        quota = MessageQuota(user_id=user_id, month=current_month)
        session.add(quota)
        session.commit()
    if quota.plan == 'free':
        if quota.message_count >= 75 and quota.message_count < 100:
            logger.info(f"Usuario {user_id} ha usado {quota.message_count} mensajes. Notificando...")
            # Aquí podrías enviar un correo o notificación
        return quota.message_count < 100
    return True

@app.route('/api/quota', methods=['GET'])
@jwt_required()
def get_quota():
    user_id = get_jwt_identity()
    with get_session() as session:
        current_month = time.strftime("%Y-%m")
        quota = session.query(MessageQuota).filter_by(user_id=user_id, month=current_month).first()
        return jsonify({
            'plan': quota.plan if quota else 'free',
            'messages_used': quota.message_count if quota else 0,
            'messages_limit': 100 if (quota and quota.plan == 'free') else 'ilimitado'
        })

def increment_quota(user_id, session):  # Nueva función para incrementar cuota
    current_month = time.strftime("%Y-%m")
    quota = session.query(MessageQuota).filter_by(user_id=user_id, month=current_month).first()
    if not quota:
        quota = MessageQuota(user_id=user_id, month=current_month)
        session.add(quota)
    quota.message_count += 1
    session.commit()
    return quota

def load_initial_templates():
    with get_session() as session:
        if not session.query(Template).count():
            templates = [
                # Plantillas existentes
                Template(
                    name="Ventas Tienda Online",
                    tone="amigable",
                    purpose="vender productos y responder preguntas",
                    flows=json.dumps([
                        {"user_message": "hola", "bot_response": "¡Hola! Bienvenid@ a mi tienda. ¿Qué te gustaría comprar hoy? 😊"},
                        {"user_message": "precio", "bot_response": "Dime qué producto te interesa y te doy el precio al instante. 💰"}
                    ])
                ),
                Template(
                    name="Soporte Técnico",
                    tone="profesional",
                    purpose="resolver problemas técnicos",
                    flows=json.dumps([
                        {"user_message": "tengo un problema", "bot_response": "Describe tu problema y te ayudaré paso a paso."},
                        {"user_message": "no funciona", "bot_response": "¿Puedes dar más detalles? Estoy aquí para solucionarlo."}
                    ])
                ),
                # Nuevas plantillas
                Template(
                    name="Reservas de Restaurante",
                    tone="amigable",
                    purpose="gestionar reservas y responder consultas",
                    flows=json.dumps([
                        {"user_message": "hola", "bot_response": "¡Hola! Bienvenid@ a nuestro restaurante. ¿Quieres reservar una mesa? 🍽️"},
                        {"user_message": "reservar", "bot_response": "Claro, dime para cuántas personas y a qué hora. ¡Te ayudo en un segundo!"},
                        {"user_message": "menú", "bot_response": "Tenemos platos deliciosos: pasta, carnes y postres. ¿Te envío el menú completo?"}
                    ])
                ),
                Template(
                    name="Atención al Cliente - Ecommerce",
                    tone="profesional",
                    purpose="gestionar pedidos y devoluciones",
                    flows=json.dumps([
                        {"user_message": "estado de mi pedido", "bot_response": "Por favor, dame tu número de pedido y lo verifico de inmediato."},
                        {"user_message": "devolver producto", "bot_response": "Claro, indícame el producto y el motivo. Te guiaré en el proceso de devolución."},
                        {"user_message": "hola", "bot_response": "Hola, gracias por contactarnos. ¿En qué puedo ayudarte hoy?"}
                    ])
                ),
                Template(
                    name="Promoción de Servicios",
                    tone="divertido",
                    purpose="promocionar servicios y captar clientes",
                    flows=json.dumps([
                        {"user_message": "hola", "bot_response": "¡Hey, hola! ¿List@ para descubrir algo genial? Ofrecemos servicios que te van a encantar. 🎉"},
                        {"user_message": "qué ofreces", "bot_response": "Desde diseño épico hasta soluciones locas. ¿Qué necesitas? ¡Te lo cuento todo!"},
                        {"user_message": "precio", "bot_response": "Los precios son tan buenos que te van a hacer saltar de emoción. ¿Qué servicio te interesa?"}
                    ])
                ),
                Template(
                    name="Asistente de Eventos",
                    tone="amigable",
                    purpose="gestionar invitaciones y detalles de eventos",
                    flows=json.dumps([
                        {"user_message": "hola", "bot_response": "¡Hola! ¿Vienes a nuestro próximo evento? Te cuento todo lo que necesitas saber. 🎈"},
                        {"user_message": "cuándo es", "bot_response": "Dime qué evento te interesa y te paso la fecha y hora exactas."},
                        {"user_message": "registrarme", "bot_response": "¡Genial! Dame tu nombre y te apunto en la lista. ¿Algo más que quieras saber?"}
                    ])
                ),
                Template(
                    name="Soporte de Suscripciones",
                    tone="serio",
                    purpose="gestionar suscripciones y pagos",
                    flows=json.dumps([
                        {"user_message": "cancelar suscripción", "bot_response": "Lamento que quieras cancelar. Por favor, indícame tu ID de suscripción para proceder."},
                        {"user_message": "pago fallido", "bot_response": "Verifiquemos eso. Proporcióname tu correo o número de suscripción y lo solucionamos."},
                        {"user_message": "hola", "bot_response": "Buenos días, estoy aquí para ayudarte con tu suscripción. ¿En qué puedo asistirte?"}
                    ])
                )
            ]
            session.add_all(templates)
            session.commit()
            logger.info("Plantillas iniciales cargadas.")

@app.route('/api/templates', methods=['GET'])
@jwt_required()
def get_templates():
    with get_session() as session:
        templates = session.query(Template).all()
        return jsonify({'templates': [{'id': t.id, 'name': t.name} for t in templates]})

# Rutas de autenticación
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = RegisterModel(**request.form)
            with get_session() as session:
                existing_user = session.query(User).filter_by(email=data.email).first()
                if existing_user:
                    flash('El email ya está registrado', 'error')
                    return redirect(url_for('register'))
                hashed_password = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                user = User(email=data.email, password=hashed_password, is_verified=False)
                session.add(user)
                session.commit()

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
                    flash('Usuario creado, pero hubo un error al enviar el correo de verificación. Contacta al soporte.', 'warning')

                return redirect(url_for('login'))
        except ValidationError as e:
            flash(str(e), 'error')
            return redirect(url_for('register'))
        except Exception as e:
            logger.exception(f"Error en /register: {str(e)}")
            flash(str(e), 'error')
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
                flash('Tu correo ya está verificado. Inicia sesión.', 'info')
                return redirect(url_for('login'))
            user.is_verified = True
            session.commit()
            flash('Correo verificado con éxito. Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
    except Exception as e:
        logger.exception(f"Error al verificar correo: {str(e)}")
        flash('El enlace de verificación es inválido o ha expirado.', 'error')
        return redirect(url_for('register'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        logger.info(f"POST en /login con datos: {request.form}")
        try:
            data = LoginModel(**request.form)
            logger.info(f"Datos validados: {data.email}")
            with get_session() as session:
                user = session.query(User).filter_by(email=data.email).first()
                if not user:
                    logger.warning("Usuario no encontrado")
                    flash('Credenciales inválidas', 'error')
                    return redirect(url_for('login'))
                
                if not bcrypt.checkpw(data.password.encode('utf-8'), user.password.encode('utf-8')):
                    logger.warning("Contraseña incorrecta")
                    flash('Credenciales inválidas', 'error')
                    return redirect(url_for('login'))
                
                if not user.is_verified:
                    logger.warning("Correo no verificado")
                    flash('Por favor verifica tu correo antes de iniciar sesión.', 'error')
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
            flash(f"Error en inicio de sesión: {str(e)}", 'error')
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
                    flash('Se ha enviado un enlace de restablecimiento a tu correo.', 'success')
                except Exception as e:
                    logger.exception(f"Error al enviar correo de restablecimiento: {str(e)}")
                    flash(f'Error al enviar el enlace de restablecimiento: {str(e)}', 'error')
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
            session.commit()

            try:
                msg = Message(
                    subject="Tu contraseña ha sido cambiada",
                    recipients=[user.email],
                    body="Hola,\n\nTu contraseña ha sido cambiada exitosamente.\n\nSi no realizaste este cambio, por favor contáctanos de inmediato.\n\nSaludos,\nEl equipo de Plubot"
                )
                mail.send(msg)
                flash('Contraseña cambiada con éxito.', 'success')
            except Exception as e:
                logger.exception(f"Error al enviar correo de confirmación: {str(e)}")
                flash(f'Contraseña cambiada, pero hubo un error al enviar la notificación: {str(e)}', 'warning')
        return redirect(url_for('index'))
    return render_template('change_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        decoded_token = decode_token(token)
        user_id = decoded_token['sub']
    except Exception as e:
        flash('El enlace de restablecimiento es inválido o ha expirado.', 'error')
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
            session.commit()

            try:
                msg = Message(
                    subject="Tu contraseña ha sido restablecida",
                    recipients=[user.email],
                    body="Hola,\n\nTu contraseña ha sido restablecida exitosamente.\n\nSi no realizaste este cambio, por favor contáctanos de inmediato.\n\nSaludos,\nEl equipo de Plubot"
                )
                mail.send(msg)
                flash('Contraseña restablecida con éxito. Por favor inicia sesión.', 'success')
            except Exception as e:
                logger.exception(f"Error al enviar correo de confirmación: {str(e)}")
                flash(f'Contraseña restablecida, pero hubo un error al enviar la notificación: {str(e)}', 'warning')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

# Rutas principales
@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('img/favicon.ico')

@app.route('/apple-touch-icon-precomposed.png')
@app.route('/apple-touch-icon.png')
def apple_touch_icon():
    return app.send_static_file('img/favicon.ico')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        name = request.form.get('nombre')
        email = request.form.get('email')
        message_content = request.form.get('message')

        logger.info(f"Recibido formulario: nombre={name}, email={email}, mensaje={message_content}")

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
            return jsonify({'success': False, 'message': f'Error al enviar el mensaje: {str(e)}'}), 500
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
        return jsonify({'success': False, 'message': f'Error al suscribirte: {str(e)}'}), 500
    
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
            response = requests.post("https://api.x.ai/v1/chat/completions", json={
                "model": "grok-2-1212", "messages": messages, "temperature": 0.5, "max_tokens": 50
            }, headers={"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"}, timeout=10)
            response.raise_for_status()
            grok_response = response.json()
            message = grok_response['choices'][0]['message']['content']
            logger.info(f"Respuesta de Grok en /api/grok: {message}")
            return jsonify({'response': message})
        except HTTPError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            logger.exception(f"Error en /api/grok: {str(e)}")
            return jsonify({'error': f"Error al conectar con Grok: {str(e)}"}), 500
        except Exception as e:
            logger.exception(f"Error en /api/grok: {str(e)}")
            return jsonify({'error': f"Error: {str(e)}"}), 500

# Rutas del creador de chatbots
@app.route('/create', methods=['GET', 'POST'])
@jwt_required()
def create_page():
    logger.info("Entrando en create_page")
    load_initial_templates()  # Cargar plantillas al acceder
    user_id = get_jwt_identity()
    logger.info(f"Acceso a /create por usuario ID: {user_id}")
    logger.info(f"Headers: {request.headers}")
    logger.info(f"Cookies: {request.cookies}")
    if request.method == 'POST':
        try:
            data = request.get_json() or request.form
            bot_data = {
                'name': data.get('name'),
                'tone': data.get('tone', 'amigable'),
                'purpose': data.get('purpose', 'ayudar a los clientes'),
                'whatsapp_number': data.get('whatsapp_number', None),
                'business_info': data.get('business_info', None),
                'pdf_url': data.get('pdf_url', None),
                'image_url': data.get('image_url', None),
                'flows': data.get('flows', []),
                'template_id': data.get('template_id', None)  # Nuevo campo para plantillas
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
            return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 500
    
    logger.info("Renderizando create.html")
    return render_template('create.html')

def create_chatbot(name, tone, purpose, whatsapp_number=None, business_info=None, pdf_url=None, image_url=None, flows=None, template_id=None, session=None, user_id=None):
    logger.info(f"Creando chatbot con nombre: {name}, tono: {tone}, propósito: {purpose}")
    if template_id:
        template = session.query(Template).filter_by(id=template_id).first()
        if template:
            tone = template.tone
            purpose = template.purpose
            flows = json.loads(template.flows)
            logger.info(f"Usando plantilla {template.name} con ID {template_id}")

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
        name=name, tone=tone, purpose=purpose, initial_message=initial_message,
        whatsapp_number=whatsapp_number, business_info=business_info, pdf_url=pdf_url, 
        image_url=image_url, user_id=user_id
    )
    session.add(chatbot)
    session.commit()
    chatbot_id = chatbot.id

    if pdf_url:
        process_pdf_async.delay(chatbot_id, pdf_url)

    if flows:
        for index, flow in enumerate(flows):
            if flow.get('userMessage') and flow.get('botResponse'):
                intent = flow.get('intent', 'general')
                flow_entry = Flow(chatbot_id=chatbot_id, user_message=flow['userMessage'], bot_response=flow['botResponse'], position=index, intent=intent)
                session.add(flow_entry)
    session.commit()
    return f"Chatbot '{name}' creado con éxito. ID: {chatbot_id}. Mensaje inicial: {initial_message}"

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
            whatsapp_number = data.get('whatsapp_number', None)
            business_info = data.get('business_info', None)
            pdf_url = data.get('pdf_url', None)
            image_url = data.get('image_url', None)
            flows = data.get('flows', [])
            template_id = data.get('template_id', None)

            if whatsapp_number:
                try:
                    WhatsAppNumberModel.validate_whatsapp_number(whatsapp_number)
                except ValueError as e:
                    return jsonify({'status': 'error', 'message': 'El número de WhatsApp debe tener el formato internacional, como +1234567890.'}), 400
                
                if not validate_whatsapp_number(whatsapp_number):
                    return jsonify({
                        'status': 'error', 
                        'message': 'El número de WhatsApp no está habilitado para este servicio. Usa un número válido o déjalo en blanco para continuar sin WhatsApp.'
                    }), 400
                
                existing_bot = session.query(Chatbot).filter_by(whatsapp_number=whatsapp_number).first()
                if existing_bot:
                    return jsonify({
                        'status': 'error', 
                        'message': f'El número {whatsapp_number} ya está vinculado al chatbot "{existing_bot.name}" (ID: {existing_bot.id}). Usa otro número o déjalo en blanco.'
                    }), 400

            response = create_chatbot(bot_name, tone, purpose, whatsapp_number, business_info, pdf_url, image_url, flows, template_id, session=session, user_id=user_id)
            logger.info(f"Respuesta enviada: {response}")
            return jsonify({'message': response}), 200
        except ValidationError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.exception(f"Error en /create-bot: {str(e)}")
            return jsonify({'message': f"Error inesperado al crear el chatbot: {str(e)}"}), 500

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
                return jsonify({'status': 'error', 'message': 'Faltan chatbot_id o phone_number'}), 400

            # Validar formato del número
            if not re.match(r'^\+\d{10,15}$', phone_number):
                return jsonify({'status': 'error', 'message': 'El número debe tener formato internacional, ej. +1234567890'}), 400

            chatbot = session.query(Chatbot).filter_by(id=chatbot_id, user_id=user_id).first()
            if not chatbot:
                return jsonify({'status': 'error', 'message': 'Chatbot no encontrado o no tienes permiso'}), 404

            if not validate_whatsapp_number(phone_number):
                return jsonify({'status': 'error', 'message': 'El número no está registrado en Twilio. Regístralo primero.'}), 400

            message = twilio_client.messages.create(
                body="¡Hola! Soy Plubot. Responde 'VERIFICAR' para conectar tu chatbot. Si necesitas ayuda, visita https://www.plubot.com/support.",
                from_=f'whatsapp:{TWILIO_PHONE}',
                to=f'whatsapp:{phone_number}'
            )
            logger.info(f"Mensaje enviado a {phone_number}: {message.sid}")
            chatbot.whatsapp_number = phone_number
            session.commit()
            return jsonify({'status': 'success', 'message': f'Verifica tu número {phone_number} respondiendo "VERIFICAR" en WhatsApp.'}), 200
        except TwilioRestException as e:
            return jsonify({'status': 'error', 'message': f'Error con Twilio: {str(e)}. Verifica tus credenciales.'}), 500
        except Exception as e:
            logger.exception(f"Error en /connect-whatsapp: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Error inesperado: {str(e)}'}), 500       

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
                logger.error(f"Chatbot {chatbot_id} no encontrado o no tienes permiso")
                return jsonify({'message': f'Chatbot {chatbot_id} no encontrado o no tienes permiso'}), 404
            session.query(Conversation).filter_by(chatbot_id=chatbot_id).delete()
            session.query(Flow).filter_by(chatbot_id=chatbot_id).delete()
            session.delete(chatbot)
            session.commit()
            logger.info(f"Chatbot {chatbot_id} eliminado")
            return jsonify({'message': f'Chatbot {chatbot_id} eliminado con éxito'}), 200
        except Exception as e:
            logger.exception(f"Error en /delete-bot: {str(e)}")
            return jsonify({'message': f"Error: {str(e)}"}), 500

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

            if not all([chatbot_id, name, tone, purpose]):
                logger.error("Faltan campos obligatorios")
                return jsonify({'message': 'Faltan campos obligatorios'}), 400

            chatbot = session.query(Chatbot).filter_by(id=chatbot_id, user_id=user_id).first()
            if not chatbot:
                logger.error(f"Chatbot {chatbot_id} no encontrado o no tienes permiso")
                return jsonify({'message': 'Chatbot no encontrado o no tienes permiso'}), 404

            if whatsapp_number and whatsapp_number != chatbot.whatsapp_number:
                WhatsAppNumberModel.validate_whatsapp_number(whatsapp_number)
                if not validate_whatsapp_number(whatsapp_number):
                    return jsonify({'status': 'error', 'message': 'Número de WhatsApp inválido o no disponible'}), 400
                existing_bot = session.query(Chatbot).filter_by(whatsapp_number=whatsapp_number).first()
                if existing_bot and existing_bot.id != chatbot_id:
                    return jsonify({'status': 'error', 'message': f'El número {whatsapp_number} ya está vinculado al chatbot "{existing_bot.name}" (ID: {existing_bot.id}).'}), 400

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
            for index, flow in enumerate(flows):
                if flow.get('userMessage') and flow.get('botResponse'):
                    intent = flow.get('intent', 'general')
                    session.add(Flow(chatbot_id=chatbot_id, user_message=flow['userMessage'], bot_response=flow['botResponse'], position=index, intent=intent))
            
            session.commit()
            logger.info(f"Chatbot {chatbot_id} actualizado")
            return jsonify({'message': f"Chatbot '{name}' actualizado con éxito"}), 200
        except ValidationError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.exception(f"Error en /update-bot: {str(e)}")
            return jsonify({'message': f"Error: {str(e)}"}), 500

@app.route('/list-bots', methods=['GET'])
@jwt_required()
def list_bots():
    user_id = get_jwt_identity()
    logger.info(f"[DEBUG] Usuario autenticado: {user_id}")
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
                return jsonify({'message': 'Chatbot no encontrado o no tienes permiso'}), 404
            history = session.query(Conversation).filter_by(chatbot_id=chatbot_id, user_id=user_id_from_data).order_by(Conversation.timestamp).all()
            history_list = [{'role': conv.role, 'message': conv.message} for conv in history]
            logger.info(f"Historial enviado para chatbot {chatbot_id}")
            return jsonify({'history': history_list}), 200
        except Exception as e:
            logger.exception(f"Error en /conversation-history: {str(e)}")
            return jsonify({'message': f"Error: {str(e)}"}), 500

@app.route('/chat', methods=['OPTIONS', 'POST'])
@jwt_required()
def chat():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            logger.info("Solicitud recibida en /chat")
            data = request.get_json()
            logger.info(f"Datos recibidos: {data}")
            chatbot_id = data.get('chatbot_id')
            user_id_from_data = data.get('user_id', 'web_user')
            message = data.get('message')
            if not chatbot_id or not message:
                return jsonify({'message': 'Faltan chatbot_id o message'}), 400

            if not check_quota(user_id, session):
                return jsonify({'message': 'Límite de 100 mensajes alcanzado. Suscríbete al plan premium.'}), 403

            chatbot = session.query(Chatbot).filter_by(id=chatbot_id, user_id=user_id).first()
            if not chatbot:
                return jsonify({'message': 'Chatbot no encontrado o no tienes permiso'}), 404
            
            flows = session.query(Flow).filter_by(chatbot_id=chatbot_id).order_by(Flow.position).all()
            response = next((flow.bot_response for flow in flows if flow.user_message.lower() in message.lower()), None)
            
            if not response:
                history = session.query(Conversation).filter_by(chatbot_id=chatbot_id, user_id=user_id_from_data).order_by(Conversation.timestamp).all()
                system_message = f"Eres un chatbot {chatbot.tone} llamado '{chatbot.name}'. Tu propósito es {chatbot.purpose}. Usa un tono {chatbot.tone} y gramática correcta."
                if chatbot.business_info:
                    system_message += f"\nNegocio: {chatbot.business_info}"
                if chatbot.pdf_content:
                    system_message += f"\nContenido del PDF: {chatbot.pdf_content}"
                messages = [{"role": "system", "content": system_message}]
                if history:
                    messages.extend([{"role": conv.role, "content": conv.message} for conv in history[-5:]])
                messages.append({"role": "user", "content": message})
                max_tokens = 150 if len(message) < 100 else 300
                response = call_grok(messages, max_tokens=max_tokens)
                if chatbot.image_url and "logo" in message.lower():
                    response += f"\nLogo: {chatbot.image_url}"

            session.add(Conversation(chatbot_id=chatbot_id, user_id=user_id_from_data, message=message, role="user"))
            session.add(Conversation(chatbot_id=chatbot_id, user_id=user_id_from_data, message=response, role="assistant"))
            session.commit()
            increment_quota(user_id, session)
            logger.info(f"Respuesta enviada: {response}")
            return jsonify({'response': response}), 200
        except Exception as e:
            logger.exception(f"Error en /chat: {str(e)}")
            return jsonify({'message': f"Error: {str(e)}"}), 500

@app.route('/upload-file', methods=['POST'])
@jwt_required()
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No se proporcionó archivo'}), 400
    file = request.files['file']
    file_type = request.form.get('type')
    if file_type not in ['pdf', 'image']:
        return jsonify({'message': 'Tipo de archivo no válido.'}), 400

    file.seek(0, os.SEEK_END)
    if file.tell() > 5 * 1024 * 1024:
        return jsonify({'message': 'Archivo demasiado grande (máx. 5MB).'}), 400
    file.seek(0)

    filename = f"{uuid.uuid4()}_{file.filename}"
    upload_dir = os.path.join('static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    file_url = f"/static/uploads/{filename}"
    if file_type == 'pdf':
        logger.info("PDF subido y procesado")
    else:
        logger.info(f"Imagen subida: {file_url}")

    return jsonify({'file_url': file_url}), 200

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
                resp.message(f"¡Número verificado! Tu chatbot '{chatbot.name}' ya está conectado a WhatsApp.")
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
                            response = "¡Buena pregunta! 😊 Tienes 100 mensajes gratis al mes para empezar, y por solo 19.99 USD/mes tienes mensajes ilimitados y más funciones. ¿Quieres probarlo en https://www.plubot.com/create?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in info_keywords):
                            response = "Plubot es una plataforma para crear chatbots personalizados que se integran con WhatsApp. 🚀 Automatizan tu negocio y aumentan tus ventas. ¿Te gustaría saber más?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in action_keywords):
                            response = "¡Genial! 🚀 Ve a https://www.plubot.com/register para empezar. Si necesitas ayuda, estoy aquí. 😊 ¿Qué tipo de negocio tienes?"
                            state["step"] = "ask_business_type"
                        else:
                            response = "¡Hola! Soy Plubot. 😊 ¿Qué tipo de negocio tienes? Un Plubot puede ayudarte a automatizar y crecer."
                            state["step"] = "ask_business_type"
                    elif state["step"] == "awaiting_response":
                        if any(k in incoming_msg_lower for k in price_keywords):
                            response = "¡Entendido! 😊 Tienes 100 mensajes gratis al mes, y por solo 19.99 USD/mes tienes mensajes ilimitados y más funciones. ¿Quieres empezar en https://www.plubot.com/register?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in info_keywords):
                            response = "Plubot te permite crear chatbots para WhatsApp que trabajan 24/7. 🚀 Automatizan procesos, aumentan ventas y ahorran tiempo. ¿Te interesa probar en https://www.plubot.com/create?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in business_keywords):
                            state["data"]["business_type"] = incoming_msg
                            response = "¡Entendido! 😊 ¿Qué necesitas que haga tu Plubot (ventas, reservas, soporte)? Di 'listo' si no necesitas nada más."
                            state["step"] = "ask_needs"
                        elif any(k in incoming_msg_lower for k in action_keywords):
                            response = "¡Genial! 🚀 Ve a https://www.plubot.com/register para empezar. Si necesitas ayuda, estoy aquí. 😊 ¿Qué tipo de negocio tienes?"
                            state["step"] = "ask_business_type"
                        else:
                            messages = [
                                {"role": "system", "content": QUANTUM_WEB_CONTEXT_FULL},
                                {"role": "user", "content": incoming_msg}
                            ]
                            response = call_grok(messages, max_tokens=150)
                            state["step"] = "ask_business_type"
                    elif state["step"] == "ask_business_type":
                        state["data"]["business_type"] = incoming_msg
                        response = "¡Entendido! 😊 ¿Qué necesitas que haga tu Plubot (ventas, reservas, soporte)? Di 'listo' si no necesitas nada más."
                        state["step"] = "ask_needs"
                    elif state["step"] == "ask_needs":
                        state["data"]["needs"].append(incoming_msg_lower)
                        response = "¡Perfecto! 😊 ¿Algo más que quieras que haga? Di 'listo' si terminaste."
                        state["step"] = "more_needs"
                    elif state["step"] == "more_needs":
                        if incoming_msg_lower == "listo":
                            needs = state["data"]["needs"]
                            if "ventas" in " ".join(needs):
                                response = "¡Genial! 😊 ¿Cuántos productos incluirías en el catálogo? Esto nos ayudará a personalizar tu Plubot."
                                state["step"] = "ask_sales_details"
                            elif "soporte" in " ".join(needs):
                                response = "¡Entendido! 😊 ¿Cuántos clientes gestionas por día? Esto nos ayudará a optimizar tu Plubot."
                                state["step"] = "ask_support_details"
                            elif "reservas" in " ".join(needs):
                                response = "¡Perfecto! 😊 ¿Cuántas reservas esperas por día? Esto nos ayudará a configurar tu Plubot."
                                state["step"] = "ask_reservations_details"
                            else:
                                response = "¡Listo! 🚀 Te contactaremos en 24 horas con más info. Mientras tanto, ¿quieres crear tu Plubot en https://www.plubot.com/create?"
                                state["step"] = "done"
                                state["data"]["contacted"] = True
                        else:
                            state["data"]["needs"].append(incoming_msg_lower)
                            response = "¡Anotado! 😊 ¿Algo más? Di 'listo' si terminaste."
                    elif state["step"] == "ask_sales_details":
                        state["data"]["specifics"]["products"] = incoming_msg
                        response = "¡Gracias! 🚀 Te contactaremos en 24 horas con más info. Mientras tanto, crea tu Plubot en https://www.plubot.com/create."
                        state["step"] = "done"
                        state["data"]["contacted"] = True
                    elif state["step"] == "ask_support_details":
                        state["data"]["specifics"]["daily_clients"] = incoming_msg
                        response = "¡Gracias! 🚀 Te contactaremos en 24 horas con más info. Mientras tanto, crea tu Plubot en https://www.plubot.com/create."
                        state["step"] = "done"
                        state["data"]["contacted"] = True
                    elif state["step"] == "ask_reservations_details":
                        state["data"]["specifics"]["daily_reservations"] = incoming_msg
                        response = "¡Gracias! 🚀 Te contactaremos en 24 horas con más info. Mientras tanto, crea tu Plubot en https://www.plubot.com/create."
                        state["step"] = "done"
                        state["data"]["contacted"] = True
                    elif state["step"] == "done":
                        if any(k in incoming_msg_lower for k in price_keywords):
                            response = "¡Entendido! 😊 Tienes 100 mensajes gratis al mes, y por solo 19.99 USD/mes tienes mensajes ilimitados y más funciones. ¿Quieres empezar en https://www.plubot.com/register?"
                            state["step"] = "awaiting_response"
                        elif any(k in incoming_msg_lower for k in action_keywords):
                            response = "¡Genial! 🚀 Ve a https://www.plubot.com/register para empezar. Si necesitas ayuda, estoy aquí. 😊 ¿Qué tipo de negocio tienes?"
                            state["step"] = "ask_business_type"
                        else:
                            messages = [
                                {"role": "system", "content": QUANTUM_WEB_CONTEXT_FULL},
                                {"role": "user", "content": incoming_msg}
                            ]
                            response = call_grok(messages, max_tokens=150)

                set_conversation_state(sender, state)
        else:
            user_id = chatbot.user_id
            if not check_quota(user_id, session):
                resp = MessagingResponse()
                resp.message("Límite de 100 mensajes alcanzado. Suscríbete al plan premium en https://www.plubot.com.")
                return str(resp)

            chatbot_id, name, tone, purpose, business_info, pdf_content, image_url = chatbot.id, chatbot.name, chatbot.tone, chatbot.purpose, chatbot.business_info, chatbot.pdf_content, chatbot.image_url
            flows = session.query(Flow).filter_by(chatbot_id=chatbot_id).order_by(Flow.position).all()
            response = next((flow.bot_response for flow in flows if flow.user_message.lower() in incoming_msg.lower()), None)
            if not response:
                history = session.query(Conversation).filter_by(chatbot_id=chatbot_id, user_id=sender).order_by(Conversation.timestamp).all()
                system_message = f"Eres un chatbot {tone} llamado '{name}'. Tu propósito es {purpose}. Usa un tono {tone} y gramática correcta."
                if business_info:
                    system_message += f"\nNegocio: {business_info}"
                if pdf_content:
                    system_message += f"\nContenido del PDF: {pdf_content}"
                messages = [{"role": "system", "content": system_message}]
                if history:
                    messages.extend([{"role": conv.role, "content": conv.message} for conv in history[-5:]])
                messages.append({"role": "user", "content": incoming_msg})
                max_tokens = 150 if len(incoming_msg) < 100 else 300
                response = call_grok(messages, max_tokens=max_tokens)
                if image_url and "logo" in incoming_msg.lower():
                    response += f"\nLogo: {image_url}"

            session.add(Conversation(chatbot_id=chatbot_id, user_id=sender, message=incoming_msg, role="user"))
            session.add(Conversation(chatbot_id=chatbot_id, user_id=sender, message=response, role="assistant"))
            session.commit()
            increment_quota(user_id, session)

    resp = MessagingResponse()
    resp.message(response)
    logger.info(f"Respuesta enviada a {sender}: {response}")
    if 'state' in locals() and state.get("step") == "done":
        logger.info(f"Datos de conversación para {sender}: {state['data']}")
        try:
            redis_client.delete(f"conversation_state:{sender}")
        except redis.exceptions.ConnectionError as e:
            logger.exception(f"Error al eliminar estado de conversación en Redis: {str(e)}")
    return str(resp)  


def get_conversation_state(sender):
    default_state = {"step": "greet", "data": {"business_type": None, "needs": [], "specifics": {}, "contacted": False}}
    if redis_client and ensure_redis_connection():
        try:
            state = redis_client.get(f"conversation_state:{sender}")
            if state:
                return json.loads(state)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logger.exception(f"Error al conectar con Redis en get_conversation_state: {str(e)}. Usando estado por defecto.")
    else:
        logger.warning("Redis no disponible. Usando estado por defecto.")
    return default_state

def set_conversation_state(sender, state):
    if redis_client and ensure_redis_connection():
        try:
            redis_client.setex(f"conversation_state:{sender}", 3600, json.dumps(state))
            logger.info(f"Estado de conversación guardado para {sender}")
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logger.exception(f"Error al conectar con Redis en set_conversation_state: {str(e)}. Estado no guardado.")
    else:
        logger.warning("Redis no disponible. Estado no guardado en caché.")

QUANTUM_WEB_CONTEXT_FULL = """
Plubot es una plataforma tipo Wix para crear chatbots personalizados (llamados "Plubots") que se integran con WhatsApp y trabajan 24/7. Nos especializamos en ayudar a negocios de todos los tamaños (tiendas online, restaurantes, clínicas, hoteles, academias, etc.) a automatizar procesos, aumentar ventas y ahorrar tiempo.

**¿Qué ofrecemos?**
- Creación fácil de chatbots: Regístrate en https://www.plubot.com/register, crea tu Plubot en https://www.plubot.com/create, y personalízalo en minutos.
- Integración con WhatsApp: Conecta tu Plubot a WhatsApp usando un número registrado en Twilio y empieza a interactuar con tus clientes.
- Automatización para negocios: Respuestas automáticas, gestión de citas, seguimiento de clientes, integración con catálogos, y más.
- Resultados comprobados: Tiendas online aumentan ventas un 30%, hoteles reducen carga administrativa un 40%, clínicas optimizan gestión un 50%.

**¿Cómo funciona la plataforma?**
1. **Registro**: Ve a https://www.plubot.com/register, ingresa tu email y contraseña, y verifica tu cuenta.
2. **Creación del Plubot**: En https://www.plubot.com/create, define el nombre, tono (amigable, profesional, etc.), propósito (ventas, soporte, reservas, etc.), y sube info de tu negocio (como un PDF).
3. **Configuración**: Personaliza tu Plubot con flujos conversacionales (preguntas y respuestas predefinidas) y datos de tu negocio.
4. **Conexión a WhatsApp**: Ve a la sección "Conectar a WhatsApp", ingresa tu número registrado en Twilio, y verifica el número siguiendo las instrucciones.
5. **Operatividad**: Una vez conectado, tu Plubot responde automáticamente a tus clientes en WhatsApp 24/7.

**Planes y precios**
- **Plan gratuito**: 100 mensajes al mes para que pruebes tu Plubot sin costo.
- **Plan premium**: Por 19.99 USD/mes, tienes mensajes ilimitados, integración con CRM, análisis de datos, y soporte prioritario.
- Beneficio del plan premium: Ideal para negocios en crecimiento que necesitan automatización avanzada y soporte continuo.

**Beneficios de usar un Plubot**
- Ahorro de tiempo: Automatiza tareas repetitivas como responder preguntas, agendar citas o tomar pedidos.
- Aumento de ventas: Tiendas online pueden aumentar ventas un 30% con un Plubot que guía a los clientes y cierra ventas.
- Mejora de eficiencia: Clínicas y hoteles reducen su carga administrativa hasta un 50% al delegar tareas a un Plubot.
- Disponibilidad 24/7: Tu Plubot responde a tus clientes en cualquier momento, incluso mientras duermes.

**Tono y estilo**
- Usa un tono amigable, profesional y persuasivo. Ejemplo: "¡Hola! Soy Plubot, tu asistente para crear chatbots increíbles. 😊 ¿En qué puedo ayudarte hoy?"
- Sé breve (2-3 frases máximo) a menos que el usuario pida más detalles.
- Usa emojis de forma moderada para dar un toque amigable (😊, 🚀, 💡).
- Siempre incluye una llamada a la acción para motivar al usuario a registrarse o crear un Plubot. Ejemplo: "¿Quieres crear tu Plubot ahora? Ve a https://www.plubot.com/create. 🚀"
- Si no entiendes algo, pide aclaraciones de forma natural. Ejemplo: "¡Gracias por tu mensaje! ¿Podrías contarme un poco más sobre tu negocio para ayudarte mejor? 😊"

**Ejemplos de respuestas persuasivas**
- Si el usuario duda: "Un Plubot puede ahorrarte horas de trabajo y aumentar tus ventas un 30%. 💰 ¿Te gustaría probar el plan gratuito en https://www.plubot.com/register?"
- Si el usuario pregunta por precios: "¡Buena pregunta! 😊 Tienes 100 mensajes gratis al mes para empezar, y por solo 19.99 USD/mes tienes mensajes ilimitados y más funciones. ¿Quieres probarlo?"
- Si el usuario menciona su negocio: "¡Genial! 😊 Un Plubot puede ayudarte a [beneficio específico]. ¿Quieres crearlo ahora en https://www.plubot.com/create?"
"""

@app.route('/fallback', methods=['POST'])
def fallback():
    logger.error("Webhook principal falló. Datos recibidos: %s", request.values)
    return "OK", 200

@app.route('/status-callback', methods=['POST'])
def status_callback():
    message_status = request.values.get('MessageStatus', 'unknown')
    message_sid = request.values.get('MessageSid', 'unknown')
    logger.info(f"Estado del mensaje {message_sid}: {message_status}")
    return "OK", 200

@app.route('/test-redis', methods=['GET'])
def test_redis():
    try:
        redis_client.set('test_key', 'test_value')
        value = redis_client.get('test_key')
        return jsonify({"status": "success", "value": value})
    except redis.exceptions.ConnectionError as e:
        logger.exception(f"Error en /test-redis: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
PREDEFINED_FLOWS = [
    {"user_message": "hola", "bot_response": "¡Hola! Soy Plubot, tu asistente para crear chatbots increíbles. 😊 ¿En qué puedo ayudarte hoy?", "intent": "greeting"},
    {"user_message": "cuanto cuesta", "bot_response": "El plan básico de Plubot comienza en $10/mes y te permite crear hasta 3 chatbots. El plan premium, que incluye funciones avanzadas, cuesta $25/mes. ¿Te gustaría saber más?", "intent": "pricing"},
    {"user_message": "tengo una tienda", "bot_response": "¡Genial! Un chatbot puede ayudarte a automatizar tus ventas y atender a tus clientes 24/7. ¿Quieres crear uno ahora? Puedo guiarte paso a paso.", "intent": "business_type"},
    {"user_message": "quiero crear un chatbot", "bot_response": "¡Perfecto! Puedo ayudarte a crear tu chatbot. Primero, ¿para qué quieres usarlo? Por ejemplo, ¿para ventas, soporte al cliente o algo más?", "intent": "create_chatbot"},
]

def load_predefined_flows():
    with get_session() as session:
        chatbot = session.query(Chatbot).filter_by(name="Plubot").first()
        if not chatbot:
            chatbot = Chatbot(
                name="Plubot",
                tone="amigable",
                purpose="asistir a los usuarios de Plubot y cerrar ventas",
                initial_message="¡Hola! Soy Plubot, tu asistente para crear chatbots increíbles. 😊 ¿En qué puedo ayudarte hoy?",
                user_id=1
            )
            session.add(chatbot)
            session.commit()

        existing_flows = session.query(Flow).filter_by(chatbot_id=chatbot.id).count()
        if existing_flows == 0:
            for index, flow in enumerate(PREDEFINED_FLOWS):
                flow_entry = Flow(
                    chatbot_id=chatbot.id,
                    user_message=flow["user_message"],
                    bot_response=flow["bot_response"],
                    position=index,
                    intent=flow["intent"]
                )
                session.add(flow_entry)
            session.commit()
            logger.info(f"Se cargaron {len(PREDEFINED_FLOWS)} flujos predefinidos para el chatbot Plubot.")

load_predefined_flows()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)