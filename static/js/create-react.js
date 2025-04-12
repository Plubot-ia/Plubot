const { useState, useEffect, useCallback, useMemo } = React;
const { ReactFlow, ReactFlowProvider, useNodesState, useEdgesState, Background, Controls, addEdge } = ReactFlow;

const CustomNode = ({ data, id }) => {
    const [userMessage, setUserMessage] = useState(data.userMessage || '');
    const [botResponse, setBotResponse] = useState(data.botResponse || '');
    const [condition, setCondition] = useState(data.condition || '');

    useEffect(() => {
        const loadInitialData = async () => {
            try {
                const [botsRes, templatesRes, quotaRes] = await Promise.all([
                    fetch('/list-bots', { credentials: 'include' }),
                    fetch('/api/templates', { credentials: 'include' }),
                    fetch('/api/quota', { credentials: 'include' })
                ]);
    
                if (!botsRes.ok) throw new Error(`Error al cargar bots: ${botsRes.statusText}`);
                if (!templatesRes.ok) throw new Error(`Error al cargar plantillas: ${templatesRes.statusText}`);
                if (!quotaRes.ok) throw new Error(`Error al cargar cuota: ${quotaRes.statusText}`);
    
                const botsData = await botsRes.json();
                const templatesData = await templatesRes.json();
                const quotaData = await quotaRes.json();
    
                setChatbots(botsData.chatbots || []);
                setTemplates(templatesData.templates || []);
                setQuota(quotaData);
                setIsAuthenticated(true);
            } catch (error) {
                console.error('Error en loadInitialData:', error);
                setIsAuthenticated(false);
                setResponseMessage(`Error al cargar datos iniciales: ${error.message}. Redirigiendo...`);
                setTimeout(() => window.location.href = '/login', 2000);
            }
        };
        loadInitialData();
    }, []);

const nodeTypes = { custom: CustomNode };

const ChatbotApp = () => {
    const [isAuthenticated, setIsAuthenticated] = useState(null);
    const [name, setName] = useState('');
    const [tone, setTone] = useState('amigable');
    const [purpose, setPurpose] = useState('');
    const [whatsappNumber, setWhatsappNumber] = useState('');
    const [businessInfo, setBusinessInfo] = useState('');
    const [pdfUrl, setPdfUrl] = useState('');
    const [imageUrl, setImageUrl] = useState('');
    const [menuJson, setMenuJson] = useState('');
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesState] = useEdgesState([]);
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
    const [step, setStep] = useState(1);
    const [previewMessage, setPreviewMessage] = useState('');
    const [quota, setQuota] = useState({ messages_used: 0, messages_limit: 100 });
    const [editingBot, setEditingBot] = useState(null);
    const [whatsappError, setWhatsappError] = useState('');
    const [menuJsonError, setMenuJsonError] = useState('');
    const [previewNodes, setPreviewNodes] = useState([]);
    const [previewEdges, setPreviewEdges, onPreviewEdgesChange] = useEdgesState([]);
    const [isPreviewing, setIsPreviewing] = useState(false);
    const [previewTemplateId, setPreviewTemplateId] = useState(null);

    // Sincronización de progreso
    useEffect(() => {
        const steps = document.querySelectorAll('.progress-step');
        steps.forEach((s, i) => s.classList.toggle('active', i + 1 === step));
    }, [step]);

    // Modal de ayuda
    useEffect(() => {
        const helpBtn = document.getElementById('help-btn');
        const helpModal = document.getElementById('help-modal');
        const closeBtn = document.getElementById('close-help-btn');
        helpBtn.onclick = () => helpModal.classList.remove('hidden');
        closeBtn.onclick = () => helpModal.classList.add('hidden');
    }, []);

    // Carga inicial
    useEffect(() => {
        const loadInitialData = async () => {
            try {
                const [botsRes, templatesRes, quotaRes] = await Promise.all([
                    fetch('/list-bots', { credentials: 'include' }),
                    fetch('/api/templates', { credentials: 'include' }),
                    fetch('/api/quota', { credentials: 'include' })
                ]);
                if (!botsRes.ok) throw new Error('No autenticado');
                setChatbots((await botsRes.json()).chatbots || []);
                setTemplates((await templatesRes.json()).templates || []);
                setQuota(await quotaRes.json());
                setIsAuthenticated(true);
            } catch (error) {
                setIsAuthenticated(false);
                setResponseMessage('No autenticado. Redirigiendo...');
                setTimeout(() => window.location.href = '/login', 2000);
            }
        };
        loadInitialData();
    }, []);

    // Validaciones
    const validateWhatsappNumber = useCallback((number) => {
        const regex = /^\+\d{10,15}$/;
        setWhatsappError(number && !regex.test(number) ? 'Formato inválido (ej. +1234567890)' : '');
    }, []);

    const validateMenuJson = useCallback((json) => {
        if (!json) return setMenuJsonError('');
        try {
            JSON.parse(json);
            setMenuJsonError('');
        } catch {
            setMenuJsonError('JSON inválido');
        }
    }, []);

    // Manejo de nodos
    const updateFlowFromNode = useCallback((id, { userMessage, botResponse, condition }) => {
        setNodes(nodes => nodes.map(node => 
            node.id === id ? { ...node, data: { ...node.data, userMessage, botResponse, condition } } : node
        ));
    }, []);

    const onConnect = useCallback((params) => setEdges(eds => addEdge(params, eds)), [setEdges]);

    const addNewNode = useCallback(() => {
        const newId = `node-${nodes.length}`; // Asegura un ID único
        const newNode = {
            id: newId,
            type: 'custom',
            data: { userMessage: '', botResponse: '', condition: '', onChange: updateFlowFromNode },
            position: { x: 250, y: nodes.length * 100 + 50 }
        };
        setNodes(nds => [...nds, newNode]);
    }, [nodes, updateFlowFromNode]);

    // Plantillas
    const applyTemplate = useCallback((templateId) => {
        const template = templates.find(t => t.id === templateId);
        if (template) {
            setTone(template.tone);
            setPurpose(template.purpose);
            setSelectedTemplate(templateId);
            const newNodes = template.flows.map((flow, i) => ({
                id: `${i}`,
                type: 'custom',
                data: { userMessage: flow.user_message, botResponse: flow.bot_response, condition: '', onChange: updateFlowFromNode },
                position: { x: 250, y: i * 100 + 50 }
            }));
            setNodes(newNodes);
            setEdges([]);
            setStep(3);
        }
    }, [templates, updateFlowFromNode]);

    const previewTemplate = useCallback((templateId) => {
        const template = templates.find(t => t.id === templateId);
        if (template) {
            const newNodes = template.flows.map((flow, i) => ({
                id: `${i}`,
                type: 'custom',
                data: { userMessage: flow.user_message, botResponse: flow.bot_response, condition: '', onChange: () => {} },
                position: { x: 250, y: i * 100 + 50 }
            }));
            setPreviewNodes(newNodes);
            setPreviewEdges([]);
            setIsPreviewing(true);
            setPreviewTemplateId(templateId);
        }
    }, [templates]);

    const confirmTemplate = useCallback(() => {
        applyTemplate(previewTemplateId);
        setIsPreviewing(false);
    }, [previewTemplateId, applyTemplate]);

    const cancelPreview = useCallback(() => {
        setIsPreviewing(false);
        setPreviewNodes([]);
        setPreviewEdges([]);
        setPreviewTemplateId(null);
    }, []);

    // Formulario y envío
    const handleSubmit = async (e) => {
        e.preventDefault();
        if (whatsappError || menuJsonError) return;
        setIsLoading(true);
        const flowData = nodes.map(node => ({
            userMessage: node.data.userMessage,
            botResponse: node.data.botResponse,
            condition: node.data.condition
        }));
        const botData = {
            name, tone, purpose, whatsapp_number: whatsappNumber,
            business_info: businessInfo, pdf_url: pdfUrl, image_url: imageUrl,
            flows: flowData, template_id: selectedTemplate || null, menu_json: menuJson,
            ...(editingBot && { chatbot_id: editingBot.id })
        };
        const endpoint = editingBot ? '/update-bot' : '/create-bot';
        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(botData)
            });
            const data = await res.json();
            if (res.ok) {
                setChatbots((await (await fetch('/list-bots', { credentials: 'include' })).json()).chatbots || []);
                setResponseMessage(data.message);
                resetForm();
            } else {
                setResponseMessage(data.message);
            }
        } catch {
            setResponseMessage('Error al guardar el chatbot');
        } finally {
            setIsLoading(false);
        }
    };

    const resetForm = useCallback(() => {
        setName(''); setTone('amigable'); setPurpose(''); setWhatsappNumber('');
        setBusinessInfo(''); setPdfUrl(''); setImageUrl(''); setMenuJson('');
        setNodes([]); setEdges([]); setSelectedTemplate(''); setStep(1);
        setEditingBot(null); setWhatsappError(''); setMenuJsonError('');
        setIsPreviewing(false); setPreviewNodes([]); setPreviewEdges([]);
        setPreviewTemplateId(null);
    }, []);

    // Chat y previsualización
    const startChat = async (chatbot) => {
        setSelectedChatbot(chatbot);
        setMessages([{ role: 'bot', content: chatbot.initial_message || 'Hola, ¿en qué puedo ayudarte?' }]);
        setIsLoading(true);
        try {
            const res = await fetch('/conversation-history', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ chatbot_id: chatbot.id })
            });
            const data = await res.json();
            if (res.ok) {
                setMessages(prev => [...prev, ...data.history.map(msg => ({ role: msg.role, content: msg.message }))]);
            }
        } catch {
            setResponseMessage('Error al cargar historial');
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
            const res = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ chatbot_id: selectedChatbot.id, message: inputMessage })
            });
            const data = await res.json();
            if (res.ok) {
                setMessages(prev => [...prev, { role: 'bot', content: data.response }]);
                const quotaRes = await fetch('/api/quota', { credentials: 'include' });
                if (quotaRes.ok) setQuota(await quotaRes.json());
            } else if (res.status === 403) {
                setResponseMessage('Límite de mensajes alcanzado. Suscríbete en <a href="/pricing">aquí</a>.');
            } else {
                setResponseMessage(data.message);
            }
        } catch {
            setResponseMessage('Error al enviar mensaje');
        } finally {
            setIsLoading(false);
        }
    };

    const handleDelete = async () => {
        if (!chatbotToDelete) return;
        setIsLoading(true);
        try {
            const res = await fetch('/delete-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ chatbot_id: chatbotToDelete.id })
            });
            const data = await res.json();
            if (res.ok) {
                setChatbots((await (await fetch('/list-bots', { credentials: 'include' })).json()).chatbots || []);
                setResponseMessage(data.message);
                if (selectedChatbot?.id === chatbotToDelete.id) {
                    setSelectedChatbot(null);
                    setMessages([]);
                }
            } else {
                setResponseMessage(data.message);
            }
        } catch {
            setResponseMessage('Error al eliminar');
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
                if (event.lengthComputable) setUploadProgress((event.loaded / event.total) * 100);
            };
            xhr.onload = () => {
                if (xhr.status === 200) {
                    const data = JSON.parse(xhr.responseText);
                    if (file.type.includes('pdf')) setPdfUrl(data.file_url || '');
                    else setImageUrl(data.file_url || '');
                    setResponseMessage(`Archivo subido: ${data.file_url}`);
                } else {
                    setResponseMessage(JSON.parse(xhr.responseText).message);
                }
                setUploadProgress(0);
                setIsLoading(false);
            };
            xhr.onerror = () => {
                setResponseMessage('Error al subir archivo');
                setUploadProgress(0);
                setIsLoading(false);
            };
            xhr.withCredentials = true;
            xhr.send(formData);
        } catch {
            setResponseMessage('Error al subir archivo');
            setUploadProgress(0);
            setIsLoading(false);
        }
    };

    const connectWhatsapp = async (chatbot) => {
        setIsLoading(true);
        try {
            const res = await fetch('/connect-whatsapp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ chatbot_id: chatbot.id, phone_number: chatbot.whatsapp_number })
            });
            const data = await res.json();
            setResponseMessage(data.message);
        } catch {
            setResponseMessage('Error al conectar WhatsApp');
        } finally {
            setIsLoading(false);
        }
    };

    const handleEdit = async (chatbot) => {
        setEditingBot(chatbot);
        setName(chatbot.name);
        setTone(chatbot.tone);
        setPurpose(chatbot.purpose);
        setWhatsappNumber(chatbot.whatsapp_number || '');
        setBusinessInfo(chatbot.business_info || '');
        setPdfUrl(chatbot.pdf_url || '');
        setImageUrl(chatbot.image_url || '');
        setMenuJson('');
        try {
            const res = await fetch('/conversation-history', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ chatbot_id: chatbot.id })
            });
            const data = await res.json();
            const botFlows = data.history
                .filter(msg => msg.role === 'user')
                .map((msg, i) => {
                    const botRes = data.history.find((r, j) => j > i && r.role === 'bot');
                    return { userMessage: msg.message, botResponse: botRes?.message || '', condition: '' };
                });
            const newNodes = botFlows.map((flow, i) => ({
                id: `${i}`,
                type: 'custom',
                data: { ...flow, onChange: updateFlowFromNode },
                position: { x: 250, y: i * 100 + 50 }
            }));
            setNodes(newNodes);
            setEdges([]);
            setStep(1);
        } catch {
            setResponseMessage('Error al cargar historial para edición');
        }
    };

    const renderStep = () => {
        const previewResponse = useMemo(() => {
            const node = nodes.find(n => n.data.userMessage.toLowerCase() === previewMessage.toLowerCase());
            return node?.data.botResponse || 'Escribe un mensaje para previsualizar';
        }, [nodes, previewMessage]);

        switch (step) {
            case 1:
                return (
                    <div className="mb-8">
                        <h2 className="text-xl font-semibold mb-6 text-white">Paso 1: Información Básica</h2>
                        <input
                            className="contact-input mb-4"
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="Nombre del Chatbot"
                            required
                        />
                        <select
                            className="contact-select mb-4"
                            value={tone}
                            onChange={(e) => setTone(e.target.value)}
                        >
                            <option value="amigable">Amigable</option>
                            <option value="profesional">Profesional</option>
                            <option value="divertido">Divertido</option>
                            <option value="serio">Serio</option>
                        </select>
                        <input
                            className="contact-input mb-4"
                            type="text"
                            value={purpose}
                            onChange={(e) => setPurpose(e.target.value)}
                            placeholder="Propósito (ej. ventas, soporte)"
                            required
                        />
                        <button
                            type="button"
                            className="quantum-btn w-full"
                            onClick={() => setStep(2)}
                            disabled={!name || !purpose}
                        >
                            Siguiente
                        </button>
                    </div>
                );
            case 2:
                return (
                    <div className="mb-8">
                        <h2 className="text-xl font-semibold mb-6 text-white">Paso 2: Plantilla (Opcional)</h2>
                        {isPreviewing ? (
                            <div>
                                <div className="react-flow__container" style={{ height: '400px', marginBottom: '20px' }}>
                                    <ReactFlowProvider>
                                        <ReactFlow
                                            nodes={previewNodes}
                                            edges={previewEdges}
                                            onNodesChange={() => {}}
                                            onEdgesChange={onPreviewEdgesChange}
                                            onConnect={() => {}}
                                            nodeTypes={nodeTypes}
                                            fitView
                                        >
                                            <Background />
                                            <Controls />
                                        </ReactFlow>
                                    </ReactFlowProvider>
                                </div>
                                <div className="flex space-x-4">
                                    <button className="quantum-btn magenta flex-1" onClick={cancelPreview}>Cancelar</button>
                                    <button className="quantum-btn flex-1" onClick={confirmTemplate}>Confirmar</button>
                                </div>
                            </div>
                        ) : (
                            <>
                                {templates.map(template => (
                                    <div key={template.id} className="template-card mb-4 p-4 bg-gray-800 rounded" draggable onDragStart={(e) => e.dataTransfer.setData('templateId', template.id)}>
                                        <h3 className="text-lg font-semibold text-white">{template.name}</h3>
                                        <p className="text-gray-300">{template.description}</p>
                                        <ul className="text-gray-400 mt-2">
                                            {template.flows.map((flow, i) => (
                                                <li key={i}>{flow.user_message} → {flow.bot_response}</li>
                                            ))}
                                        </ul>
                                        <div className="flex space-x-2 mt-2">
                                            <button className="quantum-btn" onClick={() => previewTemplate(template.id)}>Previsualizar</button>
                                            <button className="quantum-btn" onClick={() => applyTemplate(template.id)}>Usar</button>
                                        </div>
                                    </div>
                                ))}
                                <div className="flex space-x-4">
                                    <button className="quantum-btn magenta flex-1" onClick={() => setStep(1)}>Atrás</button>
                                    <button className="quantum-btn flex-1" onClick={() => setStep(3)}>Omitir</button>
                                </div>
                            </>
                        )}
                    </div>
                );
            case 3:
                return (
                    <div className="mb-8">
                        <h2 className="text-xl font-semibold mb-6 text-white">Paso 3: Personalización</h2>
                        <div className="react-flow__container" style={{ height: '500px', marginBottom: '20px' }} onDrop={(e) => {
                            const templateId = e.dataTransfer.getData('templateId');
                            if (templateId) applyTemplate(templateId);
                            e.preventDefault();
                        }} onDragOver={(e) => e.preventDefault()}>
                            <ReactFlowProvider>
                                <ReactFlow
                                    nodes={nodes}
                                    edges={edges}
                                    onNodesChange={onNodesChange}
                                    onEdgesChange={onEdgesState}
                                    onConnect={onConnect}
                                    nodeTypes={nodeTypes}
                                    fitView
                                >
                                    <Background />
                                    <Controls />
                                    <div style={{ position: 'absolute', top: 10, left: 10, zIndex: 100 }}>
                                        <button className="quantum-btn" onClick={addNewNode}>Añadir Nodo</button>
                                    </div>
                                </ReactFlow>
                            </ReactFlowProvider>
                        </div>
                        <div className="mb-4">
                            <input
                                className="contact-input w-full mb-2"
                                type="text"
                                value={previewMessage}
                                onChange={(e) => setPreviewMessage(e.target.value)}
                                placeholder="Prueba un mensaje"
                            />
                            <p className="text-gray-400">Respuesta: {previewResponse}</p>
                        </div>
                        <div className="flex space-x-4">
                            <button className="quantum-btn magenta flex-1" onClick={() => setStep(2)}>Atrás</button>
                            <button className="quantum-btn flex-1" onClick={() => setStep(4)}>Siguiente</button>
                        </div>
                    </div>
                );
            case 4:
                return (
                    <div className="mb-8">
                        <h2 className="text-xl font-semibold mb-6 text-white">Paso 4: Revisión</h2>
                        <input
                            className="contact-input mb-4"
                            type="text"
                            value={whatsappNumber}
                            onChange={(e) => { setWhatsappNumber(e.target.value); validateWhatsappNumber(e.target.value); }}
                            placeholder="Número de WhatsApp (+1234567890)"
                        />
                        {whatsappError && <p className="text-red-500 mb-4">{whatsappError}</p>}
                        <textarea
                            className="contact-textarea mb-4"
                            value={businessInfo}
                            onChange={(e) => setBusinessInfo(e.target.value)}
                            placeholder="Información del negocio (opcional)"
                        />
                        <div className="form-grid mb-4">
                            <input
                                className="contact-input"
                                type="url"
                                value={pdfUrl}
                                onChange={(e) => setPdfUrl(e.target.value)}
                                placeholder="URL del PDF (opcional)"
                            />
                            <input
                                className="contact-input"
                                type="url"
                                value={imageUrl}
                                onChange={(e) => setImageUrl(e.target.value)}
                                placeholder="URL de la Imagen (opcional)"
                            />
                        </div>
                        <textarea
                            className="contact-textarea mb-4"
                            value={menuJson}
                            onChange={(e) => { setMenuJson(e.target.value); validateMenuJson(e.target.value); }}
                            placeholder='Menú en JSON (opcional): {"Cafés": {"Latte": {"precio": 3.5}}}'
                        />
                        {menuJsonError && <p className="text-red-500 mb-4">{menuJsonError}</p>}
                        <div className="file-upload mb-4">
                            <label className="text-gray-300">Subir PDF o Imagen (máx. 5MB)</label>
                            <input type="file" accept=".pdf,image/*" onChange={handleFileUpload} />
                            {uploadProgress > 0 && (
                                <div className="progress-bar">
                                    <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
                                </div>
                            )}
                        </div>
                        <div className="flex space-x-4">
                            <button className="quantum-btn magenta flex-1" onClick={() => setStep(3)}>Atrás</button>
                            <button className="quantum-btn flex-1" onClick={handleSubmit} disabled={isLoading || whatsappError || menuJsonError}>
                                {isLoading ? 'Guardando...' : (editingBot ? 'Actualizar' : 'Crear')}
                            </button>
                        </div>
                    </div>
                );
            default:
                return null;
        }
    };

    if (isAuthenticated === null) {
        return <div className="text-white text-center p-4">Cargando datos iniciales...</div>;
    }
    if (!isAuthenticated) {
        return (
            <div className="text-white text-center p-4">
                Necesitas iniciar sesión. <a href="/login" className="text-blue-500 underline">Haz clic aquí</a>.
            </div>
        );
    }

    return (
        <section className="chatbot-section">
            <div className="chatbot-container grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="chatbot-text-column">
                    <h1 className="chatbot-title text-4xl md:text-5xl mb-6">Crea tu Plubot</h1>
                    <div className="bot-config p-6 bg-gray-900 rounded-lg">
                        <h2 className="text-2xl mb-4 text-white">Configura tu Chatbot</h2>
                        <div className="quota-info mb-4 text-gray-300">
                            <p>Mensajes usados: {quota.messages_used}/{quota.messages_limit}</p>
                            {quota.messages_used >= 75 && (
                                <p className="text-yellow-500">
                                    ¡Cerca del límite! Suscríbete <a href="/pricing" className="text-blue-500">aquí</a>.
                                </p>
                            )}
                        </div>
                        <form onSubmit={handleSubmit}>{renderStep()}</form>
                        {responseMessage && <div className="response-message mt-4 text-white" dangerouslySetInnerHTML={{ __html: responseMessage }} />}
                    </div>
                    <div className="chatbot-list mt-8">
                        <h2 className="text-xl font-semibold mb-6 text-white">Tus Chatbots</h2>
                        {chatbots.length > 0 ? chatbots.map(bot => (
                            <div className="chatbot-item p-4 mb-4 bg-gray-800 rounded" key={bot.id}>
                                <div className="chatbot-item-details text-base text-white">
                                    <strong>{bot.name}</strong> - {bot.purpose} (Tono: {bot.tone})
                                    {bot.whatsapp_number && ` | WhatsApp: ${bot.whatsapp_number}`}
                                </div>
                                <div className="chatbot-item-buttons mt-2 flex gap-2 flex-wrap">
                                    <button className="quantum-btn magenta" onClick={() => startChat(bot)} disabled={isLoading}>
                                        {isLoading ? 'Cargando...' : 'Chatear'}
                                    </button>
                                    {bot.whatsapp_number && (
                                        <button className="quantum-btn whatsapp-btn" onClick={() => connectWhatsapp(bot)} disabled={isLoading}>
                                            {isLoading ? 'Conectando...' : 'Conectar WhatsApp'}
                                        </button>
                                    )}
                                    <button className="quantum-btn" onClick={() => handleEdit(bot)} disabled={isLoading}>Editar</button>
                                    <button className="quantum-btn delete-btn" onClick={() => { setChatbotToDelete(bot); setShowDeleteModal(true); }} disabled={isLoading}>Eliminar</button>
                                </div>
                            </div>
                        )) : <p className="text-gray-400">No hay chatbots disponibles.</p>}
                    </div>
                </div>
                {selectedChatbot && (
                    <div className="chatbot-mobile-column">
                        <div className="large-mobile-frame">
                            <div className="mobile-device">
                                <div className="mobile-notch"></div>
                                <div className="mobile-screen">
                                    <div className="chatbot-widget">
                                        <div className="whatsapp-header flex justify-between p-2 bg-green-600 text-white">
                                            <div className="whatsapp-contact flex items-center">
                                                <div className="whatsapp-avatar mr-2"><i className="fas fa-robot"></i></div>
                                                <div className="whatsapp-info">
                                                    <span className="whatsapp-name">{selectedChatbot.name}</span>
                                                    <span className="whatsapp-number block text-sm">{selectedChatbot.whatsapp_number || 'Plubot'}</span>
                                                </div>
                                            </div>
                                            <div className="whatsapp-actions flex gap-2">
                                                <i className="fas fa-phone"></i>
                                                <i className="fas fa-video"></i>
                                                <i className="fas fa-ellipsis-v"></i>
                                            </div>
                                        </div>
                                        <div className="whatsapp-body p-4 h-96 overflow-y-auto bg-gray-100">
                                            {messages.map((msg, i) => (
                                                <div key={i} className={`chatbot-message ${msg.role} mb-3 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                                                    <span className={`inline-block p-2 rounded ${msg.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-300'}`}>
                                                        {msg.content}
                                                    </span>
                                                    <div className="message-meta text-xs text-gray-500 mt-1">
                                                        <span>{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                                        {msg.role === 'user' && <span className="ml-1"><i className="fas fa-check-double"></i></span>}
                                                    </div>
                                                </div>
                                            ))}
                                            {isLoading && <div className="loading-indicator text-center text-gray-500">Cargando...</div>}
                                        </div>
                                        <div className="whatsapp-input flex p-2 bg-white">
                                            <div className="input-wrapper flex-1 flex items-center">
                                                <i className="fas fa-smile input-icon mr-2 text-gray-500"></i>
                                                <input
                                                    type="text"
                                                    value={inputMessage}
                                                    onChange={(e) => setInputMessage(e.target.value)}
                                                    onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                                                    placeholder="Escribe un mensaje..."
                                                    className="flex-1 border-none outline-none"
                                                    disabled={isLoading}
                                                />
                                                <i className="fas fa-paperclip input-icon ml-2 text-gray-500"></i>
                                            </div>
                                            <button onClick={sendMessage} disabled={isLoading} className="ml-2 text-blue-500">
                                                <i className="fas fa-paper-plane"></i>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
            <div className={`modal ${showDeleteModal ? '' : 'hidden'}`}>
                <div className="modal-content bg-gray-900 text-white p-6 rounded-lg">
                    <h2 className="text-xl mb-4">Confirmar Eliminación</h2>
                    <p>¿Seguro que deseas eliminar "{chatbotToDelete?.name}"? Esta acción es irreversible.</p>
                    <div className="modal-actions flex gap-4 mt-4">
                        <button className="confirm-btn bg-red-500 text-white p-2 rounded" onClick={handleDelete} disabled={isLoading}>
                            {isLoading ? 'Eliminando...' : 'Sí, Eliminar'}
                        </button>
                        <button className="cancel-btn bg-gray-700 p-2 rounded" onClick={() => setShowDeleteModal(false)} disabled={isLoading}>Cancelar</button>
                    </div>
                </div>
            </div>
        </section>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<ChatbotApp />);}