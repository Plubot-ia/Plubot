document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('chatbot-form');
    const responseDiv = document.getElementById('response');
    const chatbotListContent = document.getElementById('chatbot-list-content');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    const chatbotNameDiv = document.getElementById('chatbot-name');
    let currentChatbotId = null;
    let messageHistory = [];

    // Debugging: Ensure DOM elements are found
    console.log('chatMessages:', chatMessages);
    console.log('chatInput:', chatInput);
    console.log('sendButton:', sendButton);
    console.log('chatbotNameDiv:', chatbotNameDiv);

    // Function to display a message in the chat
    function displayMessage(message, sender) {
        console.log(`Displaying message: ${message} from ${sender}`);
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chatbot-message', sender);
        messageDiv.innerHTML = `
            <span class="message-text">${message}</span>
            <span class="message-meta">
                <span class="message-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                <span class="message-status"><i class="fas fa-check-double"></i></span>
            </span>
        `;
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Cargar lista de chatbots
    async function loadChatbots() {
        try {
            const response = await fetch('/list-bots', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            chatbotListContent.innerHTML = '';
            data.chatbots.forEach(bot => {
                const botDiv = document.createElement('div');
                botDiv.className = 'chatbot-item';
                botDiv.innerHTML = `
                    <div>
                        <strong>${bot.name}</strong><br>
                        Tono: ${bot.tone}<br>
                        Propósito: ${bot.purpose}<br>
                        Mensaje inicial: ${bot.initial_message}
                    </div>
                    <div>
                        <button class="quantum-btn" onclick="startChat(${bot.id}, '${bot.name}', '${bot.tone}', '${bot.purpose}')">Chatear</button>
                        <button class="quantum-btn delete-btn" onclick="deleteChatbot(${bot.id})">Eliminar</button>
                    </div>
                `;
                chatbotListContent.appendChild(botDiv);
            });
        } catch (error) {
            console.error('Error al cargar los chatbots:', error);
            chatbotListContent.innerHTML = `<div>Error al cargar los chatbots: ${error.message}</div>`;
        }
    }

    // Eliminar un chatbot
    window.deleteChatbot = async function(chatbotId) {
        if (!confirm('¿Estás seguro de que quieres eliminar este chatbot?')) return;
        // Validar que chatbotId sea un número entero
        if (!Number.isInteger(chatbotId) || chatbotId <= 0) {
            alert('Error: ID del chatbot no válido');
            return;
        }
        try {
            const response = await fetch('/delete-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chatbot_id: chatbotId })
            });
            if (!response.ok) {
                throw new Error(`Error del servidor: ${response.status} ${response.statusText}`);
            }
            const data = await response.json();
            alert(data.message);
            loadChatbots(); // Recargar la lista
            if (currentChatbotId === chatbotId) {
                currentChatbotId = null;
                chatbotNameDiv.textContent = 'QuantumBot'; // Reset to default name
                chatMessages.innerHTML = '';
            }
        } catch (error) {
            console.error('Error al eliminar el chatbot:', error);
            alert('Error al eliminar el chatbot: ' + error.message);
        }
    };

    // Crear un nuevo chatbot
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('name').value;
        const tone = document.getElementById('tone').value;
        const purpose = document.getElementById('purpose').value;
        const whatsappNumber = document.getElementById('whatsapp-number').value || null;

        try {
            const response = await fetch('/create-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, tone, purpose, whatsapp_number: whatsappNumber })
            });
            const data = await response.json();
            responseDiv.textContent = data.message;
            responseDiv.classList.remove('hidden');
            form.reset();
            loadChatbots();
        } catch (error) {
            console.error('Error al crear el chatbot:', error);
            responseDiv.textContent = 'Error al conectar con el backend: ' + error.message;
            responseDiv.classList.remove('hidden');
        }
    });

    // Cargar historial de conversación
    async function loadConversationHistory(chatbotId) {
        try {
            const response = await fetch('/conversation-history', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chatbot_id: chatbotId, user_id: 'web_user' })
            });
            const data = await response.json();
            console.log('Conversation history:', data.history);
            chatMessages.innerHTML = ''; // Clear existing messages
            if (data.history && data.history.length > 0) {
                data.history.forEach(msg => {
                    displayMessage(msg.message, msg.role === 'user' ? 'user' : 'bot');
                });
            }
        } catch (error) {
            console.error('Error al cargar el historial:', error);
            displayMessage(`Error al cargar el historial: ${error.message}`, 'bot');
        }
    }

    // Iniciar chat
    window.startChat = async function(chatbotId, name, tone, purpose) {
        console.log(`Starting chat with chatbot: ${name} (ID: ${chatbotId})`);
        currentChatbotId = chatbotId;
        chatbotNameDiv.textContent = name; // Update the name in the WhatsApp header
        messageHistory = [
            { role: 'system', content: `Eres ${name}, un asistente virtual. Responde de manera ${tone}, breve y directa, usando un tono alegre. Limítate a respuestas cortas (máximo 2-3 frases). Si es posible, incluye un emoji o icono relevante al final de tu respuesta.` }
        ];

        // Load conversation history
        await loadConversationHistory(chatbotId);

        // If no history, display the initial message
        if (chatMessages.innerHTML === '') {
            const bot = (await (await fetch('/list-bots')).json()).chatbots.find(b => b.id === chatbotId);
            if (bot && bot.initial_message) {
                displayMessage(bot.initial_message, 'bot');
            } else {
                displayMessage(`¡Hola! Soy ${name}, tu asistente virtual. ¿En qué puedo ayudarte hoy? 👋`, 'bot');
            }
        }
    };

    // Enviar mensaje
    async function sendMessage() {
        if (!currentChatbotId || !chatInput.value.trim()) return;

        const message = chatInput.value.trim();
        displayMessage(message, 'user');
        chatInput.value = '';

        const typingMessage = document.createElement('div');
        typingMessage.classList.add('chatbot-message', 'bot');
        typingMessage.innerHTML = `
            <span class="message-text">Escribiendo... ⏳</span>
            <span class="message-meta">
                <span class="message-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </span>
        `;
        chatMessages.appendChild(typingMessage);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        messageHistory.push({ role: 'user', content: message });

        try {
            const response = await fetch('/api/grok', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, history: messageHistory })
            });
            const data = await response.json();
            typingMessage.remove();

            if (data.error) {
                displayMessage('Lo siento, algo salió mal. Intenta de nuevo. 😓', 'bot');
            } else {
                displayMessage(data.response, 'bot');
                messageHistory.push({ role: 'assistant', content: data.response });
            }
        } catch (error) {
            typingMessage.remove();
            displayMessage('No pude conectar con el servidor. Intenta de nuevo. 😓', 'bot');
            console.error('Error al enviar el mensaje:', error);
        }
    }

    // Event listeners for sending messages
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // Load chatbots on page load
    loadChatbots();
});