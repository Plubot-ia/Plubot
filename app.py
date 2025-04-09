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
from celery import Celery
from contextlib import contextmanager
from datetime import timedelta

# Configuración inicial
load_dotenv()
app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise ValueError("No se encontró SECRET_KEY en las variables de entorno.")

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

# Configuración de CORS
CORS(app, resources={r"/*": {
    "origins": ["http://localhost:5000", "http://192.168.0.213:5000", "https://www.plubot.com"],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "supports_credentials": True
}})

# Configuración de Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Configuración de Celery
celery_app = Celery('tasks', broker=REDIS_URL, backend=REDIS_URL.replace('/0', '/1'))

# Cargar claves desde .env
XAI_API_KEY = os.getenv("XAI_API_KEY")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
DATABASE_URL = os.getenv("DATABASE_URL")

# Verificar claves
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
app.config["JWT_SECRET_KEY"] = "super-secret"
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config["JWT_ACCESS_COOKIE_NAME"] = "access_token"
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_COOKIE_SECURE'] = False  # Cambia a True en Render (HTTPS)
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

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

@contextmanager
def get_session():
    session = Session()
    try:
        yield session
    except Exception as e:
        session.rollback()
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
        logger.error(f"Error al extraer texto del PDF: {str(e)}")
        return ""

def summarize_history(history):
    if len(history) > 5:
        return "Resumen: " + " ".join([conv.message[:50] for conv in history[-5:]])
    return " ".join([conv.message for conv in history])

def call_grok(messages, max_tokens=150):
    if len(messages) > 4:
        messages = [messages[0]] + messages[-3:]
    
    cache_key = json.dumps(messages)
    cached = redis_client.get(cache_key)
    if cached:
        logger.info("Respuesta obtenida desde caché")
        return cached

    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "grok-2-1212", "messages": messages, "temperature": 0.5, "max_tokens": max_tokens}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()['choices'][0]['message']['content']
        redis_client.setex(cache_key, 3600, result)
        logger.info(f"Grok response: {result}")
        return result
    except (HTTPError, Timeout) as e:
        logger.error(f"Error al conectar con Grok: {str(e)}")
        return "¡Ups! Algo salió mal, intenta de nuevo. 😅"

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
        logger.error(f"Error al validar número de WhatsApp con Twilio: {str(e)}")
        return False

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

                # Generar token de verificación
                verification_token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=24))
                verification_link = url_for('verify_email', token=verification_token, _external=True)

                # Enviar correo de verificación
                try:
                    msg = Message(
                        subject="Verifica tu correo - Plubot",
                        recipients=[data.email],
                        body=f"Hola,\n\nPor favor verifica tu correo haciendo clic en este enlace: {verification_link}\n\nEste enlace expira en 24 horas.\n\nSaludos,\nEl equipo de Plubot"
                    )
                    mail.send(msg)
                    flash('Revisa tu correo para verificar tu cuenta.', 'success')
                except Exception as e:
                    logger.error(f"Error al enviar correo de verificación: {str(e)}")
                    flash('Usuario creado, pero hubo un error al enviar el correo de verificación. Contacta al soporte.', 'warning')

                return redirect(url_for('login'))
        except ValidationError as e:
            flash(str(e), 'error')
            return redirect(url_for('register'))
        except Exception as e:
            logger.error(f"Error en /register: {str(e)}")
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
        logger.error(f"Error al verificar correo: {str(e)}")
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
                    logger.error(f"Error al enviar correo de restablecimiento: {str(e)}")
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
                logger.error(f"Error al enviar correo de confirmación: {str(e)}")
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
                logger.error(f"Error al enviar correo de confirmación: {str(e)}")
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
            logger.error(f"Error al enviar correo: {str(e)}")
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
        logger.error(f"Error al enviar correo de suscripción: {str(e)}")
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
            logger.error(f"Error en /api/grok: {str(e)}")
            return jsonify({'error': f"Error al conectar con Grok: {str(e)}"}), 500
        except Exception as e:
            logger.error(f"Error en /api/grok: {str(e)}")
            return jsonify({'error': f"Error: {str(e)}"}), 500

# Rutas del creador de chatbots
@app.route('/create', methods=['GET', 'POST'])
@jwt_required()
def create_page():
    logger.info("Entrando en create_page")
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
                'flows': data.get('flows', [])
            }
            if not bot_data['name']:
                return jsonify({'status': 'error', 'message': 'El nombre es obligatorio'}), 400
            with get_session() as session:
                response = create_chatbot(**bot_data, session=session, user_id=user_id)
                return jsonify({'message': response})
        except ValidationError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error al guardar bot en /create: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 500
    
    logger.info("Renderizando create.html")
    return render_template('create.html')

def create_chatbot(name, tone, purpose, whatsapp_number=None, business_info=None, pdf_url=None, image_url=None, flows=None, session=None, user_id=None):
    logger.info(f"Creando chatbot con nombre: {name}, tono: {tone}, propósito: {purpose}")
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

            if whatsapp_number:
                WhatsAppNumberModel.validate_whatsapp_number(whatsapp_number)
                if not validate_whatsapp_number(whatsapp_number):
                    return jsonify({'status': 'error', 'message': 'El número de WhatsApp no está registrado en Twilio.'}), 400
                existing_bot = session.query(Chatbot).filter_by(whatsapp_number=whatsapp_number).first()
                if existing_bot:
                    return jsonify({'status': 'error', 'message': f'El número {whatsapp_number} ya está vinculado al chatbot "{existing_bot.name}" (ID: {existing_bot.id}).'}), 400

            response = create_chatbot(bot_name, tone, purpose, whatsapp_number, business_info, pdf_url, image_url, flows, session=session, user_id=user_id)
            logger.info(f"Respuesta enviada: {response}")
            return jsonify({'message': response}), 200
        except ValidationError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error en /create-bot: {str(e)}")
            return jsonify({'message': f"Error: {str(e)}"}), 500

@app.route('/connect-whatsapp', methods=['OPTIONS', 'POST'])
@jwt_required()
def connect_whatsapp():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    
    user_id = get_jwt_identity()
    with get_session() as session:
        try:
            logger.info("Solicitud recibida en /connect-whatsapp")
            data = request.get_json()
            logger.info(f"Datos recibidos: {data}")
            chatbot_id = data.get('chatbot_id')
            phone_number = data.get('phone_number')

            if not chatbot_id or not phone_number:
                return jsonify({'status': 'error', 'message': 'Faltan chatbot_id o phone_number'}), 400

            chatbot = session.query(Chatbot).filter_by(id=chatbot_id, user_id=user_id).first()
            if not chatbot:
                return jsonify({'status': 'error', 'message': 'Chatbot no encontrado o no tienes permiso'}), 404

            existing_bot = session.query(Chatbot).filter_by(whatsapp_number=phone_number).first()
            if existing_bot and existing_bot.id != chatbot_id:
                return jsonify({'status': 'error', 'message': f'El número {phone_number} ya está vinculado al chatbot "{existing_bot.name}" (ID: {existing_bot.id}).'}), 400

            try:
                message = twilio_client.messages.create(
                    body="Hola, soy Quantum Web. Responde con 'VERIFICAR' para conectar tu número a tu chatbot.",
                    from_=f'whatsapp:{TWILIO_PHONE}',
                    to=f'whatsapp:{phone_number}'
                )
                logger.info(f"Mensaje de verificación enviado a {phone_number}: {message.sid}")
            except TwilioRestException as e:
                logger.error(f"Error al enviar mensaje de verificación: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Error al enviar mensaje de verificación: {str(e)}'}), 500

            chatbot.whatsapp_number = phone_number
            session.commit()

            return jsonify({'status': 'success', 'message': f'Se envió un mensaje de verificación a {phone_number}. Responde con "VERIFICAR" para completar el proceso.'}), 200
        except Exception as e:
            logger.error(f"Error en /connect-whatsapp: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 500

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
            logger.error(f"Error en /delete-bot: {str(e)}")
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
            logger.error(f"Error en /update-bot: {str(e)}")
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
            logger.error(f"Error en /conversation-history: {str(e)}")
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
            logger.info(f"Respuesta enviada: {response}")
            return jsonify({'response': response}), 200
        except Exception as e:
            logger.error(f"Error en /chat: {str(e)}")
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

    if file_type == 'pdf':
        pdf_content = extract_text_from_pdf(file)
        logger.info("PDF subido y procesado")
        return jsonify({'file_content': pdf_content}), 200
    else:
        image_url = f"/static/uploads/{file.filename}"
        upload_dir = os.path.join('static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, file.filename))
        logger.info(f"Imagen subida: {image_url}")
        return jsonify({'file_url': image_url}), 200

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
                info_keywords = ["saber más", "información", "qué son", "cómo funcionan", "detalles"]
                price_keywords = ["precio", "coste", "cuánto cuesta", "valor", "tarifa"]
                needs_max_tokens = 300 if any(k in incoming_msg.lower() for k in info_keywords + price_keywords) else 150

                if state["step"] == "greet":
                    if incoming_msg.lower().startswith(("hola", "buenos", "buenas", "hey")):
                        response = "¡Hola! Soy QuantumBot de Quantum Web, un placer conocerte. ¿En qué puedo ayudarte hoy? 😊"
                        state["step"] = "awaiting_response"
                    else:
                        if any(k in incoming_msg.lower() for k in price_keywords):
                            response = "¡Hola! Para darte el mejor precio, dime más sobre tu negocio. ¿Qué tipo de negocio tienes? 😊"
                        else:
                            response = "¡Hola! Soy QuantumBot de Quantum Web. ¿Qué tipo de negocio tienes? 😊"
                        state["step"] = "ask_business_type"
                elif state["step"] == "awaiting_response":
                    if any(k in incoming_msg.lower() for k in price_keywords):
                        response = "¡Entendido! Para un precio exacto, dime qué tipo de negocio tienes. 😊"
                        state["step"] = "ask_business_type"
                    else:
                        messages = [{"role": "system", "content": QUANTUM_WEB_CONTEXT_FULL + "\nInterpreta y responde antes de preguntar por el negocio."}, {"role": "user", "content": incoming_msg}]
                        response = call_grok(messages, max_tokens=needs_max_tokens)
                        state["step"] = "ask_business_type"
                elif state["step"] == "ask_business_type":
                    state["data"]["business_type"] = incoming_msg
                    response = "¡Entendido! ¿Qué necesitas que haga tu chatbot (ventas, reservas, soporte)? 😊"
                    state["step"] = "ask_needs"
                elif state["step"] == "ask_needs":
                    state["data"]["needs"].append(incoming_msg.lower())
                    response = "¡Perfecto! ¿Algo más que quieras que haga? Di 'listo' si terminaste. 😊"
                    state["step"] = "more_needs"
                elif state["step"] == "more_needs":
                    if incoming_msg.lower() == "listo":
                        needs = state["data"]["needs"]
                        if "ventas" in " ".join(needs):
                            response = "¡Genial! ¿Cuántos productos incluirías en el catálogo? 😊"
                            state["step"] = "ask_sales_details"
                        elif "soporte" in " ".join(needs):
                            response = "¡Entendido! ¿Cuántos clientes gestionas por día? 😊"
                            state["step"] = "ask_support_details"
                        elif "reservas" in " ".join(needs):
                            response = "¡Perfecto! ¿Cuántas reservas esperas por día? 😊"
                            state["step"] = "ask_reservations_details"
                        else:
                            response = "¡Listo! Te contactaremos en 24 horas con más info. ¡Gracias! 😊"
                            state["step"] = "done"
                            state["data"]["contacted"] = True
                    else:
                        state["data"]["needs"].append(incoming_msg.lower())
                        response = "¡Anotado! ¿Algo más? Di 'listo' si terminaste. 😊"
                elif state["step"] == "ask_sales_details":
                    state["data"]["specifics"]["products"] = incoming_msg
                    response = "¡Gracias! Te contactaremos en 24 horas con más info y precios personalizados. 😊"
                    state["step"] = "done"
                    state["data"]["contacted"] = True
                elif state["step"] == "ask_support_details":
                    state["data"]["specifics"]["daily_clients"] = incoming_msg
                    response = "¡Gracias! Te contactaremos en 24 horas con más info y precios personalizados. 😊"
                    state["step"] = "done"
                    state["data"]["contacted"] = True
                elif state["step"] == "ask_reservations_details":
                    state["data"]["specifics"]["daily_reservations"] = incoming_msg
                    response = "¡Gracias! Te contactaremos en 24 horas con más info y precios personalizados. 😊"
                    state["step"] = "done"
                    state["data"]["contacted"] = True
                elif state["step"] == "done":
                    messages = [{"role": "system", "content": QUANTUM_WEB_CONTEXT_SHORT}, {"role": "user", "content": incoming_msg}]
                    if any(k in incoming_msg.lower() for k in price_keywords):
                        response = "¡Entendido! Para un precio exacto, dime qué tipo de negocio tienes. 😊"
                        state["step"] = "ask_business_type"
                    else:
                        response = call_grok(messages, max_tokens=needs_max_tokens)

                set_conversation_state(sender, state)
        else:
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

    resp = MessagingResponse()
    resp.message(response)
    logger.info(f"Respuesta enviada a {sender}: {response}")
    if 'state' in locals() and state.get("step") == "done":
        logger.info(f"Datos de conversación para {sender}: {state['data']}")
        redis_client.delete(f"conversation_state:{sender}")
    return str(resp)

def get_conversation_state(sender):
    state = redis_client.get(f"conversation_state:{sender}")
    if state:
        return json.loads(state)
    return {"step": "greet", "data": {"business_type": None, "needs": [], "specifics": {}, "contacted": False}}

def set_conversation_state(sender, state):
    redis_client.setex(f"conversation_state:{sender}", 3600, json.dumps(state))

QUANTUM_WEB_CONTEXT_FULL = """
Quantum Web es una empresa dedicada a la creación e implementación de chatbots inteligentes optimizados para WhatsApp, que trabajan 24/7. Nos especializamos en soluciones de IA para pequeños negocios, grandes empresas, tiendas online, hoteles, academias, clínicas, restaurantes, y más. 

Ofrecemos:
- Chatbots para WhatsApp: Respuestas automáticas 24/7, integración con catálogos, seguimiento de clientes.
- Automatización para pequeños negocios: Respuestas personalizadas, gestión de citas, notificaciones.
- Optimización para grandes empresas: Automatización de procesos, integración con CRM, análisis de datos.
- Ejemplos: Tiendas online (30% más ventas), hoteles (40% menos carga), logística (70% menos consultas), clínicas (50% menos gestión).

Nuestra misión es responder con amabilidad y empatía, escuchar al cliente, y optimizar procesos para liberar tiempo, aumentar ventas y mejorar la eficiencia.
"""

QUANTUM_WEB_CONTEXT_SHORT = """
Eres QuantumBot de Quantum Web. Responde con amabilidad y empatía, usa un tono alegre y respuestas cortas (2-3 frases max). Incluye emojis cuando sea apropiado.
"""

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)