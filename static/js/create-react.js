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
    const [isLoading, setIsLoading] = useState(false);
    const [templates, setTemplates] = useState([]);
    const [selectedTemplate, setSelectedTemplate] = useState('');
    // Nuevos estados para las mejoras
    const [step, setStep] = useState(1); // Paso actual del asistente
    const [previewMessage, setPreviewMessage] = useState(''); // Vista previa
    const [quota, setQuota] = useState({ messages_used: 0, messages_limit: 100 }); // Estado del plan

    // Cargar chatbots, plantillas y cuota al montar el componente
    useEffect(() => {
        const loadInitialData = async () => {
            try {
                // Cargar chatbots
                const botsResponse = await fetch('/list-bots', {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                });
                if (!botsResponse.ok) throw new Error('No se pudieron cargar los chatbots');
                const botsData = await botsResponse.json();
                setChatbots(botsData.chatbots || []);
                setIsAuthenticated(true);

                // Cargar plantillas
                const templatesResponse = await fetch('/api/templates', {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                });
                if (templatesResponse.ok) {
                    const templatesData = await templatesResponse.json();
                    setTemplates(templatesData.templates || []);
                }

                // Cargar estado de la cuota
                const quotaResponse = await fetch('/api/quota', {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                });
                if (quotaResponse.ok) {
                    const quotaData = await quotaResponse.json();
                    setQuota(quotaData);
                }
            } catch (error) {
                setResponseMessage(`Error: ${error.message}. Redirigiendo a /login...`);
                setIsAuthenticated(false);
                setTimeout(() => window.location.href = '/login', 2000);
            }
        };
        loadInitialData();
    }, []);

    // Controlar visibilidad del loader global
    useEffect(() => {
        document.getElementById('global-loader').classList.toggle('hidden', !isLoading);
    }, [isLoading]);

    const startChat = async (chatbot) => {
        setSelectedChatbot(chatbot);
        setMessages([{ role: 'bot', content: chatbot.initial_message || 'Hola, ¿en qué puedo ayudarte?' }]);
        setIsLoading(true);
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
            } else {
                setResponseMessage(`Error al cargar historial: ${data.message}`);
            }
        } catch (error) {
            setResponseMessage('Error al cargar el historial de conversación.');
        } finally {
            setIsLoading(false);
        }
    };

    const sendMessage = async () => {
        if (!inputMessage || !selectedChatbot) return;
        const newMessage = { role: 'user', content: inputMessage };
        setMessages(prev => [...prev, newMessage]);
        setInputMessage('');
        setIsLoading(true);
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
                // Actualizar cuota después de enviar mensaje
                const quotaResponse = await fetch('/api/quota', { credentials: 'include' });
                if (quotaResponse.ok) setQuota(await quotaResponse.json());
            } else if (response.status === 403) {
                setResponseMessage('Límite de 100 mensajes alcanzado. Suscríbete al plan premium en <a href="/pricing" class="text-blue-500 underline">aquí</a>.');
            } else {
                setResponseMessage(`Error: ${data.message}`);
            }
        } catch (error) {
            setResponseMessage('Error al enviar mensaje.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        const botData = { 
            name, tone, purpose, whatsapp_number: whatsappNumber, 
            business_info: businessInfo, pdf_url: pdfUrl, image_url: imageUrl, flows,
            template_id: selectedTemplate || null
        };
        try {
            const response = await fetch('/create-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(botData),
            });
            const data = await response.json();
            if (response.ok) {
                setResponseMessage(data.message);
                const botsResponse = await fetch('/list-bots', { method: 'GET', headers: { 'Content-Type': 'application/json' }, credentials: 'include' });
                if (botsResponse.ok) {
                    const botsData = await botsResponse.json();
                    setChatbots(botsData.chatbots || []);
                }
                setName('');
                setTone('amigable');
                setPurpose('');
                setWhatsappNumber('');
                setBusinessInfo('');
                setPdfUrl('');
                setImageUrl('');
                setFlows([{ userMessage: '', botResponse: '' }]);
                setSelectedTemplate('');
                setStep(1); // Reiniciar al paso 1
            } else {
                setResponseMessage(data.message);
            }
        } catch (error) {
            setResponseMessage('Error al conectar con el servidor. Por favor, revisa tu conexión e intenta de nuevo.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleDelete = async () => {
        if (!chatbotToDelete) return;
        setIsLoading(true);
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
        } finally {
            setIsLoading(false);
            setShowDeleteModal(false);
            setChatbotToDelete(null);
        }
    };

    const handleFileUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('file', file);
        formData.append('type', file.type.includes('pdf') ? 'pdf' : 'image');
        setIsLoading(true);
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
                        setResponseMessage(`PDF subido con éxito: ${data.file_url}`);
                    } else {
                        setImageUrl(data.file_url || '');
                        setResponseMessage(`Imagen subida con éxito: ${data.file_url}`);
                    }
                } else {
                    const data = JSON.parse(xhr.responseText);
                    setResponseMessage(`Error: ${data.message}`);
                }
                setUploadProgress(0);
                setIsLoading(false);
            };
            xhr.onerror = () => {
                setResponseMessage('Error al subir el archivo.');
                setUploadProgress(0);
                setIsLoading(false);
            };
            xhr.withCredentials = true;
            xhr.send(formData);
        } catch (error) {
            setResponseMessage('Error al subir el archivo.');
            setUploadProgress(0);
            setIsLoading(false);
        }
    };

    const handleFlowChange = (index, field, value) => {
        const newFlows = [...flows];
        newFlows[index][field] = value;
        setFlows(newFlows);
    };

    const addFlow = () => setFlows([...flows, { userMessage: '', botResponse: '' }]);
    const removeFlow = (index) => setFlows(flows.filter((_, i) => i !== index));

    const connectWhatsapp = async (chatbot) => {
        setIsLoading(true);
        try {
            const response = await fetch('/connect-whatsapp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ chatbot_id: chatbot.id, phone_number: chatbot.whatsapp_number })
            });
            const data = await response.json();
            if (response.ok) {
                setResponseMessage(data.message);
            } else {
                setResponseMessage(`Error: ${data.message}`);
            }
        } catch (error) {
            setResponseMessage('Error al conectar con WhatsApp.');
        } finally {
            setIsLoading(false);
        }
    };

    // Nueva función para renderizar los pasos del asistente
    const renderStep = () => {
        const previewResponse = flows.find(f => f.userMessage.toLowerCase() === previewMessage.toLowerCase())?.botResponse || 'Escribe un mensaje para ver la respuesta.';
        switch (step) {
            case 1:
                return (
                    <div className="mb-6">
                        <h2 className="text-xl font-semibold mb-4">Paso 1: Nombre y Tono</h2>
                        <input className="contact-input mb-2" type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre del Chatbot" required />
                        <select className="contact-select mb-2" value={tone} onChange={(e) => setTone(e.target.value)}>
                            <option value="amigable">Amigable</option>
                            <option value="profesional">Profesional</option>
                            <option value="divertido">Divertido</option>
                            <option value="serio">Serio</option>
                        </select>
                        <input className="contact-input mb-2" type="text" value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="Propósito (ej. ventas, soporte)" required />
                        <button type="button" className="quantum-btn" onClick={() => setStep(2)} disabled={!name || !purpose}>Siguiente</button>
                    </div>
                );
            case 2:
                return (
                    <div className="mb-6">
                        <h2 className="text-xl font-semibold mb-4">Paso 2: Plantilla (Opcional)</h2>
                        <select className="contact-select w-full mb-2" value={selectedTemplate} onChange={(e) => setSelectedTemplate(e.target.value)}>
                            <option value="">Sin plantilla</option>
                            {templates.map(template => (
                                <option key={template.id} value={template.id}>{template.name}</option>
                            ))}
                        </select>
                        <div className="flex space-x-2">
                            <button type="button" className="quantum-btn magenta" onClick={() => setStep(1)}>Atrás</button>
                            <button type="button" className="quantum-btn" onClick={() => setStep(3)}>Siguiente</button>
                        </div>
                    </div>
                );
            case 3:
                return (
                    <div className="mb-6">
                        <h2 className="text-xl font-semibold mb-4">Paso 3: Flujos de Conversación</h2>
                        {flows.map((flow, index) => (
                            <div className="flow-item mb-2" key={index}>
                                <input className="contact-input" type="text" value={flow.userMessage} onChange={(e) => handleFlowChange(index, 'userMessage', e.target.value)} placeholder="Mensaje del usuario" />
                                <input className="contact-input" type="text" value={flow.botResponse} onChange={(e) => handleFlowChange(index, 'botResponse', e.target.value)} placeholder="Respuesta del bot" />
                                {flows.length > 1 && (
                                    <button type="button" className="quantum-btn delete-btn" onClick={() => removeFlow(index)}>Eliminar</button>
                                )}
                            </div>
                        ))}
                        <div className="mb-2">
                            <input className="contact-input w-full" type="text" value={previewMessage} onChange={(e) => setPreviewMessage(e.target.value)} placeholder="Prueba un mensaje aquí" />
                            <p className="mt-2 text-gray-600">Respuesta: {previewResponse}</p>
                        </div>
                        <button type="button" className="quantum-btn magenta mb-2" onClick={addFlow}>Agregar Flujo</button>
                        <div className="flex space-x-2">
                            <button type="button" className="quantum-btn magenta" onClick={() => setStep(2)}>Atrás</button>
                            <button type="button" className="quantum-btn" onClick={() => setStep(4)}>Siguiente</button>
                        </div>
                    </div>
                );
            case 4:
                return (
                    <div className="mb-6">
                        <h2 className="text-xl font-semibold mb-4">Paso 4: Conectar WhatsApp</h2>
                        <input className="contact-input mb-2" type="text" value={whatsappNumber} onChange={(e) => setWhatsappNumber(e.target.value)} placeholder="Número de WhatsApp (+1234567890)" />
                        <textarea className="contact-textarea mb-2" value={businessInfo} onChange={(e) => setBusinessInfo(e.target.value)} placeholder="Información del negocio (opcional)" />
                        <div className="form-grid mb-2">
                            <input className="contact-input" type="url" value={pdfUrl} onChange={(e) => setPdfUrl(e.target.value)} placeholder="URL del PDF (opcional)" />
                            <input className="contact-input" type="url" value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="URL de la Imagen (opcional)" />
                        </div>
                        <div className="file-upload mb-2">
                            <label>Subir PDF o Imagen (máx. 5MB)</label>
                            <input type="file" accept=".pdf,image/*" onChange={handleFileUpload} />
                            {uploadProgress > 0 && (
                                <div className="progress-bar">
                                    <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
                                </div>
                            )}
                        </div>
                        <div className="flex space-x-2">
                            <button type="button" className="quantum-btn magenta" onClick={() => setStep(3)}>Atrás</button>
                            <button type="submit" className="quantum-btn" onClick={handleSubmit} disabled={isLoading}>
                                {isLoading ? 'Creando...' : 'Finalizar y Crear'}
                            </button>
                        </div>
                    </div>
                );
            default:
                return null;
        }
    };

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
                        {/* Información de cuota */}
                        <div className="quota-info mb-4">
                            <p>Mensajes usados: {quota.messages_used}/{quota.messages_limit}</p>
                            {quota.messages_used >= 75 && (
                                <p className="text-yellow-500">¡Estás cerca del límite! Suscríbete al plan premium <a href="/pricing" className="text-blue-500 underline">aquí</a>.</p>
                            )}
                        </div>
                        <form onSubmit={handleSubmit}>
                            {renderStep()}
                        </form>
                        {responseMessage && (
                            <div className="response-message" dangerouslySetInnerHTML={{ __html: responseMessage }} />
                        )}
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
                                        <button className="quantum-btn magenta" onClick={() => startChat(bot)} disabled={isLoading}>
                                            {isLoading ? 'Cargando...' : 'Chatear'}
                                        </button>
                                        {bot.whatsapp_number && (
                                            <button className="quantum-btn bg-green-500 text-white" onClick={() => connectWhatsapp(bot)} disabled={isLoading}>
                                                {isLoading ? 'Conectando...' : 'Conectar WhatsApp'}
                                            </button>
                                        )}
                                        <button className="quantum-btn delete-btn" onClick={() => { setChatbotToDelete(bot); setShowDeleteModal(true); }} disabled={isLoading}>
                                            Eliminar
                                        </button>
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
                                            {isLoading && <div className="text-center text-gray-500">Cargando...</div>}
                                        </div>
                                        <div className="whatsapp-input">
                                            <div className="input-wrapper">
                                                <i className="fas fa-smile input-icon"></i>
                                                <input type="text" value={inputMessage} onChange={(e) => setInputMessage(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && sendMessage()} placeholder="Escribe un mensaje..." disabled={isLoading} />
                                                <i className="fas fa-paperclip input-icon"></i>
                                            </div>
                                            <button onClick={sendMessage} disabled={isLoading}><i className="fas fa-paper-plane"></i></button>
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
                        <button className="confirm-btn bg-red-500 text-white" onClick={handleDelete} disabled={isLoading}>
                            {isLoading ? 'Eliminando...' : 'Sí, Eliminar'}
                        </button>
                        <button className="cancel-btn" onClick={() => setShowDeleteModal(false)} disabled={isLoading}>Cancelar</button>
                    </div>
                </div>
            </div>
        </section>
    );
};

ReactDOM.render(<ChatbotApp />, document.getElementById('root'));