
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
  const [responseMessage, setResponseMessage] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);

  useEffect(() => {
    const loadChatbots = async () => {
      try {
        const response = await fetch('/list-bots', { credentials: 'include' });
        const data = await response.json();
        setChatbots(data.chatbots || []);
        setIsAuthenticated(true);
      } catch (error) {
        setResponseMessage(`Error: ${error.message}`);
        setIsAuthenticated(false);
        setTimeout(() => window.location.href = '/login', 2000);
      }
    };
    loadChatbots();
  }, []);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', file.type.includes('pdf') ? 'pdf' : 'image');

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload-file', true);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        setUploadProgress((event.loaded / event.total) * 100);
      }
    };
    xhr.onload = () => {
      const data = JSON.parse(xhr.responseText);
      if (xhr.status === 200) {
        if (file.type.includes('pdf')) {
          setPdfUrl(data.file_url || '');
        } else {
          setImageUrl(data.file_url || '');
        }
        setResponseMessage('Archivo subido con éxito.');
      } else {
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
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const botData = { name, tone, purpose, whatsapp_number: whatsappNumber, business_info: businessInfo, pdf_url: pdfUrl, image_url: imageUrl, flows };
    try {
      const response = await fetch('/create-bot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(botData)
      });
      const data = await response.json();
      if (response.ok) {
        setResponseMessage(data.message);
        setName('');
        setTone('amigable');
        setPurpose('');
        setWhatsappNumber('');
        setBusinessInfo('');
        setPdfUrl('');
        setImageUrl('');
        setFlows([{ userMessage: '', botResponse: '' }]);
        const refresh = await fetch('/list-bots', { credentials: 'include' });
        const newData = await refresh.json();
        setChatbots(newData.chatbots || []);
      } else {
        setResponseMessage(`Error: ${data.message}`);
      }
    } catch (error) {
      setResponseMessage('Error al crear el chatbot.');
    }
  };

  const handleFlowChange = (index, field, value) => {
    const newFlows = [...flows];
    newFlows[index][field] = value;
    setFlows(newFlows);
  };

  const addFlow = () => setFlows([...flows, { userMessage: '', botResponse: '' }]);
  const removeFlow = (index) => setFlows(flows.filter((_, i) => i !== index));

  if (isAuthenticated === null) return <p>Cargando...</p>;
  if (!isAuthenticated) return <p>No autenticado. Redirigiendo...</p>;

  return (
    <section className="chatbot-section">
      <h1 className="chatbot-title">Crea tu Plubot</h1>
      <form className="bot-config" onSubmit={handleSubmit}>
        <input className="contact-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre del Chatbot" required />
        <select className="contact-select" value={tone} onChange={(e) => setTone(e.target.value)}>
          <option value="amigable">Amigable</option>
          <option value="profesional">Profesional</option>
        </select>
        <input className="contact-input" value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="Propósito" required />
        <input className="contact-input" value={whatsappNumber} onChange={(e) => setWhatsappNumber(e.target.value)} placeholder="WhatsApp" />
        <textarea className="contact-textarea" value={businessInfo} onChange={(e) => setBusinessInfo(e.target.value)} placeholder="Información del negocio" />
        <input className="contact-input" value={pdfUrl} onChange={(e) => setPdfUrl(e.target.value)} placeholder="URL del PDF" />
        <input className="contact-input" value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="URL de la Imagen" />

        <input type="file" accept=".pdf,image/*" onChange={handleFileUpload} />
        {uploadProgress > 0 && (
          <div className="progress-bar">
            <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
          </div>
        )}

        <h3>Flujos de conversación</h3>
        {flows.map((flow, index) => (
          <div key={index} className="flow-item">
            <input className="contact-input" value={flow.userMessage} onChange={(e) => handleFlowChange(index, 'userMessage', e.target.value)} placeholder="Mensaje del usuario" />
            <input className="contact-input" value={flow.botResponse} onChange={(e) => handleFlowChange(index, 'botResponse', e.target.value)} placeholder="Respuesta del bot" />
            {flows.length > 1 && <button type="button" className="quantum-btn delete-btn" onClick={() => removeFlow(index)}>Eliminar</button>}
          </div>
        ))}

        <button type="button" className="quantum-btn magenta" onClick={addFlow}>Agregar flujo</button>
        <button type="submit" className="quantum-btn">Crear Chatbot</button>
        {responseMessage && <div className="response-message">{responseMessage}</div>}
      </form>

      <h2 className="chatbot-title">Tus Chatbots</h2>
      <ul>
        {chatbots.map(bot => (
          <li key={bot.id}>{bot.name} - {bot.purpose}</li>
        ))}
      </ul>
    </section>
  );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<ChatbotApp />);
