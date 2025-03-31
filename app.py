from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os
import requests
import time

load_dotenv()
app = Flask(__name__)

# Depuración para verificar que las variables se cargaron
print("WHATSAPP_ACCESS_TOKEN:", os.getenv('WHATSAPP_ACCESS_TOKEN'))
print("WHATSAPP_VERIFY_TOKEN:", os.getenv('WHATSAPP_VERIFY_TOKEN'))
print("WHATSAPP_PHONE_NUMBER_ID:", os.getenv('WHATSAPP_PHONE_NUMBER_ID'))

# Cargar la clave API desde el archivo .env
XAI_API_KEY = os.getenv("XAI_API_KEY")

# Verificar que la clave API esté presente
if not XAI_API_KEY:
    raise ValueError("No se encontró la clave API en el archivo .env. Asegúrate de que XAI_API_KEY esté definida.")

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

# Nueva ruta para el formulario de suscripción en el footer
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

# Nueva ruta para la página de prueba de partículas
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
        

# Agregar esta ruta al final de tu archivo Flask
@app.route('/whatsapp/webhook', methods=['GET'])
def verify_webhook():
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    expected_token = os.getenv('WHATSAPP_VERIFY_TOKEN')
    print(f"Received token: {token}, Expected token: {expected_token}")  # Depuración
    if token == expected_token:
        print("Verification successful!")
        return challenge, 200
    print("Verification failed!")
    return jsonify({'status': 'error', 'message': 'Verification failed'}), 403

@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    # Imprimir los datos crudos recibidos
    raw_data = request.get_data(as_text=True)
    print(f"Raw data received: {raw_data}")

    # Intentar parsear los datos como JSON
    data = request.get_json(silent=True)
    if data is None:
        print("Failed to parse JSON data")
        return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400

    print(f"Parsed data: {data}")

    # Verificar si es una notificación de suscripción
    if data.get('object') != 'whatsapp_business_account' or 'entry' not in data:
        print("Invalid data format")
        return jsonify({'status': 'error', 'message': 'Invalid data format'}), 400

    entry = data['entry'][0]
    if 'changes' not in entry:
        print("No 'changes' field in entry")
        return jsonify({'status': 'error', 'message': 'No changes in entry'}), 400

    change = entry['changes'][0]
    if 'value' not in change or change['field'] != 'messages':
        print("No 'value' field or incorrect field")
        return jsonify({'status': 'error', 'message': 'No value or incorrect field'}), 400

    value = change['value']
    if 'messages' not in value:
        print("No 'messages' field in value")
        return jsonify({'status': 'error', 'message': 'No messages in value'}), 400

    messages = value['messages']
    if not messages:
        print("Messages list is empty")
        return jsonify({'status': 'error', 'message': 'No messages in list'}), 400

    try:
        message = messages[0]['text']['body']
        sender = messages[0]['from']
        print(f"Message: {message}, Sender: {sender}")  # Depuración
    except (KeyError, IndexError) as e:
        print(f"Error extracting message: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid message format'}), 400

    # Respuesta estática para probar
    reply = "¡Hola! Soy QuantumBot. Esto es una respuesta de prueba."

    whatsapp_api_url = f"https://graph.facebook.com/v20.0/{os.getenv('WHATSAPP_PHONE_NUMBER_ID')}/messages"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "text",
        "text": {"body": reply}
    }
    print(f"Sending reply to WhatsApp: {payload}")  # Depuración
    try:
        response = requests.post(whatsapp_api_url, json=payload, headers=headers)
        response.raise_for_status()  # Lanza una excepción si la solicitud falla
    except requests.exceptions.RequestException as e:
        print(f"Error sending reply to WhatsApp: {e}, Response: {response.text}")
        return jsonify({'status': 'error', 'message': 'Failed to send reply'}), 500

    print("Reply sent successfully")
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)