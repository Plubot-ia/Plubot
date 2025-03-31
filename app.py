from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os
import requests
import time
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

load_dotenv()
app = Flask(__name__)

# Depuración para verificar que las variables se cargaron
print("TWILIO_SID:", os.getenv('TWILIO_SID'))
print("TWILIO_TOKEN:", os.getenv('TWILIO_TOKEN'))
print("TWILIO_PHONE:", os.getenv('TWILIO_PHONE'))

# Cargar la clave API de xAI y Twilio desde el archivo .env
XAI_API_KEY = os.getenv("XAI_API_KEY")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")  # Ejemplo: whatsapp:+14155238886

# Verificar que las claves estén presentes
if not XAI_API_KEY:
    raise ValueError("No se encontró la clave XAI_API_KEY en el archivo .env.")
if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_PHONE:
    raise ValueError("Faltan credenciales de Twilio en el archivo .env (TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE).")

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

@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre', 'Usuario del Footer')
            email = request.form.get('email')
            mensaje = request.form.get('message')

            if not email:
                return jsonify({'status': 'error', 'message': 'El campo de correo electrónico es requerido.'}), 400
            if not mensaje:
                return jsonify({'status': 'error', 'message': 'El campo de mensaje es requerido.'}), 400

            msg = Message(
                subject=f'Nuevo mensaje de contacto de {nombre}',
                recipients=['quantumweb.ia@gmail.com'],
                body=f'Nombre: {nombre}\nEmail: {email}\nMensaje: {mensaje}'
            )
            mail.send(msg)
            return jsonify({'status': 'success', 'message': 'Mensaje enviado con éxito. ¡Gracias por contactarnos!'}), 200
        except Exception as e:
            print(f"Error al enviar el correo: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Error al enviar el mensaje: {str(e)}'}), 500
    return render_template('contact.html')

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
        return jsonify({'error': 'No se proporcionó un mensaje'}), 400

    messages = [
        {"role": "system", "content": "Eres QuantumBot, un asistente virtual de Quantum Web. Responde de manera amigable, breve y directa, usando un tono alegre. Limítate a respuestas cortas (máximo 2-3 frases). Si es posible, incluye un emoji o icono relevante al final de tu respuesta."}
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "grok-2-1212",
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": 50
    }

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

@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    raw_data = request.get_data(as_text=True)
    print(f"Raw data received: {raw_data}")

    data = request.form
    print(f"Parsed data: {data}")

    try:
        message = data.get('Body')
        sender = data.get('From')
        if not message or not sender:
            print("Missing message or sender")
            return jsonify({'status': 'error', 'message': 'Missing message or sender'}), 400
        print(f"Message: {message}, Sender: {sender}")
    except KeyError as e:
        print(f"Error extracting message: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid message format'}), 400

    reply = "¡Hola! Soy QuantumBot. Esto es una respuesta de prueba."

    client = Client(TWILIO_SID, TWILIO_TOKEN)
    try:
        message_response = client.messages.create(
            body=reply,
            from_=TWILIO_PHONE,  # whatsapp:+14155238886
            to=sender            # whatsapp:+5492216996564
        )
        print(f"Reply sent successfully: SID {message_response.sid}")
    except TwilioRestException as e:
        print(f"Error sending reply to WhatsApp via Twilio: {str(e)}")
        # Devolvemos 200 para Twilio, incluso si falla el envío
        return jsonify({'status': 'error', 'message': f'Failed to send reply: {str(e)}'}), 200

    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)