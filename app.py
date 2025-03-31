from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os
import requests
import time
from twilio.rest import Client  # Importación para Twilio
from twilio.base.exceptions import TwilioRestException  # Para manejar errores de Twilio

load_dotenv()
app = Flask(__name__)

# Depuración para verificar que las variables se cargaron
print("TWILIO_ACCOUNT_SID:", os.getenv('TWILIO_ACCOUNT_SID'))
print("TWILIO_AUTH_TOKEN:", os.getenv('TWILIO_AUTH_TOKEN'))
print("TWILIO_WHATSAPP_NUMBER:", os.getenv('TWILIO_WHATSAPP_NUMBER'))

# Cargar la clave API de xAI y Twilio desde el archivo .env
XAI_API_KEY = os.getenv("XAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")  # Ejemplo: whatsapp:+15556396032

# Verificar que las claves estén presentes
if not XAI_API_KEY:
    raise ValueError("No se encontró la clave XAI_API_KEY en el archivo .env.")
if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_NUMBER:
    raise ValueError("Faltan credenciales de Twilio en el archivo .env (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER).")

# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Inicializar Flask-Mail
mail = Mail(app)

# Rutas básicas
@app.route('/')
def index():
    return render_template('index.html')

# Ruta unificada para manejar ambos formularios de contacto
@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre', 'Usuario del Footer')  # Nombre opcional, con valor predeterminado
            email = request.form.get('email')
            mensaje = request.form.get('message')  # Busca 'message', que ahora coincide con ambos formularios

            # Validación más específica
            if not email:
                return jsonify({'status': 'error', 'message': 'El campo de correo electrónico es requerido.'}), 400
            if not mensaje:
                return jsonify({'status': 'error', 'message': 'El campo de mensaje es requerido.'}), 400

            # Crear el correo
            msg = Message(
                subject=f'Nuevo mensaje de contacto de {nombre}',
                recipients=['quantumweb.ia@gmail.com'],  # Reemplaza con tu correo real
                body=f'Nombre: {nombre}\nEmail: {email}\nMensaje: {mensaje}'
            )

            # Enviar el correo
            mail.send(msg)

            return jsonify({'status': 'success', 'message': 'Mensaje enviado con éxito. ¡Gracias por contactarnos!'}), 200
        except Exception as e:
            print(f"Error al enviar el correo: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Error al enviar el mensaje: {str(e)}'}), 500

    return render_template('contact.html')

# Ruta para el formulario de suscripción en el footer
@app.route('/subscribe', methods=['POST'])
def subscribe():
    if request.method == 'POST':
        try:
            email = request.form.get('email')

            if not email:
                return jsonify({'status': 'error', 'message': 'El campo de correo electrónico es requerido.'}), 400

            msg_to_subscriber = Message(
                subject='¡Gracias por suscribirte a Quantum Web!',
                recipients=[email],
                body=f'Hola,\n\nGracias por suscribirte a nuestro boletín. ¡Pronto recibirás actualizaciones y noticias de Quantum Web!\n\nSaludos,\nEl equipo de Quantum Web'
            )
            msg_to_admin = Message(
                subject='Nueva suscripción al boletín',
                recipients=['quantumweb.ia@gmail.com'],
                body=f'Nuevo suscriptor:\nEmail: {email}'
            )
            mail.send(msg_to_subscriber)
            mail.send(msg_to_admin)
            return jsonify({'status': 'success', 'message': '¡Gracias por suscribirte! Revisa tu correo para confirmar.'}), 200
        except Exception as e:
            print(f"Error al procesar la suscripción: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Error al procesar tu suscripción. Intenta de nuevo.'}), 500
    return jsonify({'status': 'error', 'message': 'Método no permitido'}), 405

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

# Ruta para la página del chatbot
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

# Ruta para la página de prueba de partículas
@app.route('/particulas')
def particulas():
    return render_template('particulas.html')

# Ruta para manejar solicitudes al API de Grok
@app.route('/api/grok', methods=['POST'])
def grok_api():
    data = request.get_json()
    user_message = data.get('message', '')
    history = data.get('history', [])

    if not user_message:
        return jsonify({'error': 'No se proporcionó un mensaje'}), 400

    # Construir el historial de mensajes
    messages = [
        {"role": "system", "content": "Eres QuantumBot, un asistente virtual de Quantum Web. Responde de manera amigable, breve y directa, usando un tono alegre. Limítate a respuestas cortas (máximo 2-3 frases). Si es posible, incluye un emoji o icono relevante al final de tu respuesta."}
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Configura la solicitud al API de Grok usando el modelo grok-2-1212
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "grok-2-1212",
        "messages": messages,
        "temperature": 0.5,  # Menor para respuestas más predecibles y menos creativas
        "max_tokens": 50     # Reducimos a 50 tokens para respuestas cortas
    }

    # Implementar reintentos en caso de error 429 (límite de solicitudes)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            grok_response = response.json()
            message = grok_response['choices'][0]['message']['content']
            return jsonify({'response': message})
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return jsonify({'error': f"Error al conectar con el API de Grok: {str(e)}"}), 500
        except requests.exceptions.RequestException as e:
            return jsonify({'error': f"Error al conectar con el API de Grok: {str(e)}"}), 500

# Ruta para manejar mensajes de WhatsApp con Twilio
@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    # Imprimir los datos crudos recibidos
    raw_data = request.get_data(as_text=True)
    print(f"Raw data received: {raw_data}")

    # Twilio envía datos en formato application/x-www-form-urlencoded
    data = request.form
    print(f"Parsed data: {data}")

    # Extraer el mensaje y el remitente desde los parámetros de Twilio
    try:
        message = data.get('Body')  # El cuerpo del mensaje
        sender = data.get('From')   # Número del remitente (ejemplo: whatsapp:+5492216996564)
        if not message or not sender:
            print("Missing message or sender")
            return jsonify({'status': 'error', 'message': 'Missing message or sender'}), 400
        print(f"Message: {message}, Sender: {sender}")
    except KeyError as e:
        print(f"Error extracting message: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid message format'}), 400

    # Respuesta estática para probar
    reply = "¡Hola! Soy QuantumBot. Esto es una respuesta de prueba."

    # Configurar el cliente de Twilio
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    # Enviar la respuesta usando Twilio
    try:
        message_response = client.messages.create(
            body=reply,
            from_=TWILIO_WHATSAPP_NUMBER,  # Número de Twilio habilitado para WhatsApp
            to=sender                      # Número del remitente
        )
        print(f"Reply sent successfully: SID {message_response.sid}")
    except TwilioRestException as e:
        print(f"Error sending reply to WhatsApp via Twilio: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Failed to send reply: {str(e)}'}), 500

    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)