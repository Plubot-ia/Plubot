const { useState, useEffect } = React;

const ChatbotApp = () => {
    const [isAuthenticated, setIsAuthenticated] = useState(null);
    const [name, setName] = useState('');
    const [tone, setTone] = useState('amigable');
    const [purpose, setPurpose] = useState('');
    const [whatsappNumber, setWhatsappNumber] = useState('');
    const [businessInfo, setBusinessInfo] = useState('');
    const [pdfUrl, setPdfUrl] = useState('');
    const [imageUrl, setImageUrl] = useState('');
    const [flows, setFlows] = useState([{ userMessage: '', botResponse: '' }]);
    const [chatbots, setChatbots] = useState([]);
    const [messages, setMessages] = useState([]);
    const [inputMessage, setInputMessage] = useState('');
    const [responseMessage, setResponseMessage] = useState('');
    const [selectedChatbot, setSelectedChatbot] = useState(null);
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [chatbotToDelete, setChatbotToDelete] = useState(null);
    const [uploadProgress, setUploadProgress] = useState(0);

    useEffect(() => {
        const loadChatbots = async () => {
            try {
                const response = await fetch('/list-bots', {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                });
                if (!response.ok) throw new Error('No se pudieron cargar los chatbots');
                const data = await response.json();
                setChatbots(data.chatbots || []);
                setIsAuthenticated(true);
            } catch (error) {
                setResponseMessage(`Error: ${error.message}. Redirigiendo a /login...`);
                setIsAuthenticated(false);
                setTimeout(() => window.location.href = '/login', 2000);
            }
        };
        loadChatbots();
    }, []);

    const startChat = async (chatbot) => {
        setSelectedChatbot(chatbot);
        setMessages([{ role: 'bot', content: chatbot.initial_message || 'Hola, ¿en qué puedo ayudarte?' }]);
        try {
            const response = await fetch('/conversation-history', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ chatbot_id: chatbot.id })
            });
            const data = await response.json();
            if (response.ok) {
                const historyMessages = data.history.map(msg => ({
                    role: msg.role,
                    content: msg.message
                }));
                setMessages(prev => [...prev, ...historyMessages]);
            }
        } catch (error) {
            setResponseMessage('Error al cargar el historial de conversación.');
        }
    };

    const sendMessage = async () => {
        if (!inputMessage || !selectedChatbot) return;
        const newMessage = { role: 'user', content: inputMessage };
        setMessages(prev => [...prev, newMessage]);
        setInputMessage('');
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ chatbot_id: selectedChatbot.id, message: inputMessage })
            });
            const data = await response.json();
            if (response.ok) {
                setMessages(prev => [...prev, { role: 'bot', content: data.response }]);
            } else {
                setResponseMessage(`Error: ${data.message}`);
            }
        } catch (error) {
            setResponseMessage('Error al enviar mensaje.');
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        const botData = { name, tone, purpose, whatsapp_number: whatsappNumber, business_info: businessInfo, pdf_url: pdfUrl, image_url: imageUrl, flows };
        try {
            const response = await fetch('/create-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(botData),
                credentials: 'include'  // Añadir esta línea
            });
            const data = await response.json();
            if (response.ok) {
                setResponseMessage(data.message);
                const loadResponse = await fetch('/list-bots', { 
                    method: 'GET', 
                    headers: { 'Content-Type': 'application/json' }, 
                    credentials: 'include' 
                });
                if (loadResponse.ok) {
                    const loadData = await loadResponse.json();
                    setChatbots(loadData.chatbots || []);
                }
                setName('');
                setTone('amigable');
                setPurpose('');
                setWhatsappNumber('');
                setBusinessInfo('');
                setPdfUrl('');
                setImageUrl('');
                setFlows([{ userMessage: '', botResponse: '' }]);
            } else {
                setResponseMessage(`Error: ${data.message || 'undefined'}`);  // Mejorar manejo de errores
            }
        } catch (error) {
            setResponseMessage(`Error al crear el chatbot: ${error.message}`);
        }
    };

    const handleDelete = async () => {
        if (!chatbotToDelete) return;
        try {
            const response = await fetch('/delete-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ chatbot_id: chatbotToDelete.id })
            });
            const data = await response.json();
            if (response.ok) {
                setResponseMessage(data.message);
                const loadResponse = await fetch('/list-bots', { method: 'GET', headers: { 'Content-Type': 'application/json' }, credentials: 'include' });
                if (loadResponse.ok) {
                    const loadData = await loadResponse.json();
                    setChatbots(loadData.chatbots || []);
                }
                if (selectedChatbot && selectedChatbot.id === chatbotToDelete.id) {
                    setSelectedChatbot(null);
                    setMessages([]);
                }
            } else {
                setResponseMessage(`Error: ${data.message}`);
            }
        } catch (error) {
            setResponseMessage('Error al eliminar el chatbot.');
        }
        setShowDeleteModal(false);
        setChatbotToDelete(null);
    };

    const handleFileUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('file', file);
        formData.append('type', file.type.includes('pdf') ? 'pdf' : 'image');
        try {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload-file', true);
            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable) {
                    setUploadProgress((event.loaded / event.total) * 100);
                }
            };
            xhr.onload = () => {
                if (xhr.status === 200) {
                    const data = JSON.parse(xhr.responseText);
                    if (file.type.includes('pdf')) {
                        setPdfUrl(data.file_url || '');
                        setResponseMessage('PDF subido con éxito.');
                    } else {
                        setImageUrl(data.file_url || '');
                        setResponseMessage('Imagen subida con éxito.');
                    }
                } else {
                    const data = JSON.parse(xhr.responseText);
                    setResponseMessage(`Error: ${data.message}`);
                }
                setUploadProgress(0);
            };
            xhr.onerror = () => {
                setResponseMessage('Error al subir el archivo.');
                setUploadProgress(0);
            };
            xhr.withCredentials = true;
            xhr.send(formData);
        } catch (error) {
            setResponseMessage('Error al subir el archivo.');
            setUploadProgress(0);
        }
    };

    const handleFlowChange = (index, field, value) => {
        const newFlows = [...flows];
        newFlows[index][field] = value;
        setFlows(newFlows);
    };

    const addFlow = () => setFlows([...flows, { userMessage: '', botResponse: '' }]);
    const removeFlow = (index) => setFlows(flows.filter((_, i) => i !== index));

    if (isAuthenticated === null) {
        return (
            <section className="chatbot-section">
                <div className="chatbot-container">
                    <div className="chatbot-text-column">
                        <h1 className="chatbot-title">Crea tu Plubot</h1>
                        <p className="auth-message">Verificando autenticación...</p>
                    </div>
                </div>
            </section>
        );
    }

    if (!isAuthenticated) {
        return (
            <section className="chatbot-section">
                <div className="chatbot-container">
                    <div className="chatbot-text-column">
                        <h1 className="chatbot-title">Crea tu Plubot</h1>
                        <p className="auth-message">
                            Necesitas iniciar sesión. <a href="/login">Haz clic aquí</a> para continuar.
                        </p>
                    </div>
                </div>
            </section>
        );
    }

    return (
        <section className="chatbot-section">
            <div className="chatbot-container">
                <div className="chatbot-text-column">
                    <h1 className="chatbot-title">Crea tu Plubot</h1>
                    <div className="bot-config">
                        <h2>Configura tu Chatbot</h2>
                        <form onSubmit={handleSubmit}>
                            <div className="form-grid">
                                <input className="contact-input" type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre del Chatbot" required />
                                <select className="contact-select" value={tone} onChange={(e) => setTone(e.target.value)}>
                                    <option value="amigable">Amigable</option>
                                    <option value="profesional">Profesional</option>
                                    <option value="divertido">Divertido</option>
                                    <option value="serio">Serio</option>
                                </select>
                                <input className="contact-input" type="text" value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="Propósito (ej. ventas, soporte)" required />
                                <input className="contact-input" type="text" value={whatsappNumber} onChange={(e) => setWhatsappNumber(e.target.value)} placeholder="Número de WhatsApp (+1234567890)" />
                            </div>
                            <textarea className="contact-textarea" value={businessInfo} onChange={(e) => setBusinessInfo(e.target.value)} placeholder="Información del negocio (opcional)" />
                            <div className="form-grid">
                                <input className="contact-input" type="url" value={pdfUrl} onChange={(e) => setPdfUrl(e.target.value)} placeholder="URL del PDF (opcional)" />
                                <input className="contact-input" type="url" value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="URL de la Imagen (opcional)" />
                            </div>
                            <div className="file-upload">
                                <label>Subir PDF o Imagen (máx. 5MB)</label>
                                <input type="file" accept=".pdf,image/*" onChange={handleFileUpload} />
                                {uploadProgress > 0 && (
                                    <div className="progress-bar">
                                        <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
                                    </div>
                                )}
                            </div>
                            <h3>Flujos de Conversación</h3>
                            {flows.map((flow, index) => (
                                <div className="flow-item" key={index}>
                                    <input className="contact-input" type="text" value={flow.userMessage} onChange={(e) => handleFlowChange(index, 'userMessage', e.target.value)} placeholder="Mensaje del usuario" />
                                    <input className="contact-input" type="text" value={flow.botResponse} onChange={(e) => handleFlowChange(index, 'botResponse', e.target.value)} placeholder="Respuesta del bot" />
                                    {flows.length > 1 && (
                                        <button type="button" className="quantum-btn delete-btn" onClick={() => removeFlow(index)}>Eliminar</button>
                                    )}
                                </div>
                            ))}
                            <div className="flow-buttons">
                                <button type="button" className="quantum-btn magenta" onClick={addFlow}>Agregar Flujo</button>
                            </div>
                            <div className="form-buttons">
                                <button type="submit" className="quantum-btn">Crear Chatbot</button>
                            </div>
                        </form>
                        {responseMessage && <div className="response-message">{responseMessage}</div>}
                    </div>

                    <div className="chatbot-list">
                        <h2>Tus Chatbots</h2>
                        {chatbots.length > 0 ? (
                            chatbots.map(bot => (
                                <div className="chatbot-item" key={bot.id}>
                                    <div className="chatbot-item-details">
                                        <strong>{bot.name}</strong> - {bot.purpose} (Tono: {bot.tone})
                                        {bot.whatsapp_number && ` | WhatsApp: ${bot.whatsapp_number}`}
                                    </div>
                                    <div className="chatbot-item-buttons">
                                        <button className="quantum-btn magenta" onClick={() => startChat(bot)}>Chatear</button>
                                        <button className="quantum-btn delete-btn" onClick={() => { setChatbotToDelete(bot); setShowDeleteModal(true); }}>Eliminar</button>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <p>No hay chatbots disponibles.</p>
                        )}
                    </div>
                </div>

                {selectedChatbot && (
                    <div className="chatbot-mobile-column">
                        <div className="large-mobile-frame">
                            <div className="mobile-device">
                                <div className="mobile-notch"></div>
                                <div className="mobile-screen">
                                    <div className="chatbot-widget">
                                        <div className="whatsapp-header">
                                            <div className="whatsapp-contact">
                                                <div className="whatsapp-avatar">
                                                    <i className="fas fa-robot"></i>
                                                </div>
                                                <div className="whatsapp-info">
                                                    <span className="whatsapp-name">{selectedChatbot.name}</span>
                                                    <span className="whatsapp-number">{selectedChatbot.whatsapp_number || 'Plubot'}</span>
                                                </div>
                                            </div>
                                            <div className="whatsapp-actions">
                                                <i className="fas fa-phone"></i>
                                                <i className="fas fa-video"></i>
                                                <i className="fas fa-ellipsis-v"></i>
                                            </div>
                                        </div>
                                        <div className="whatsapp-body">
                                            {messages.map((msg, index) => (
                                                <div key={index} className={`chatbot-message ${msg.role}`}>
                                                    {msg.content}
                                                    <div className="message-meta">
                                                        <span className="message-time">{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                                        {msg.role === 'user' && <span className="message-status"><i className="fas fa-check-double"></i></span>}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                        <div className="whatsapp-input">
                                            <div className="input-wrapper">
                                                <i className="fas fa-smile input-icon"></i>
                                                <input type="text" value={inputMessage} onChange={(e) => setInputMessage(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && sendMessage()} placeholder="Escribe un mensaje..." />
                                                <i className="fas fa-paperclip input-icon"></i>
                                            </div>
                                            <button onClick={sendMessage}><i className="fas fa-paper-plane"></i></button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <div className={`modal ${showDeleteModal ? '' : 'hidden'}`}>
                <div className="modal-content">
                    <h2>Confirmar Eliminación</h2>
                    <p>¿Estás seguro de que deseas eliminar el chatbot "{chatbotToDelete?.name}"? Esta acción no se puede deshacer.</p>
                    <div className="modal-actions">
                        <button className="confirm-btn" onClick={handleDelete}>Sí, Eliminar</button>
                        <button className="cancel-btn" onClick={() => setShowDeleteModal(false)}>Cancelar</button>
                    </div>
                </div>
            </div>
        </section>
    );
};

ReactDOM.render(<ChatbotApp />, document.getElementById('root'));