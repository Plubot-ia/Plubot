document.addEventListener('DOMContentLoaded', () => {
    console.log("main.js cargado");

// === Manejo del Formulario de Contacto ===
const contactForm = document.getElementById('contact-form');
const formMessage = document.getElementById('form-message');
const formMessageText = document.getElementById('form-message-text');
const submitBtn = document.querySelector('.contact-btn');
const btnText = submitBtn?.querySelector('.btn-text');
const btnLoader = submitBtn?.querySelector('.btn-loader');

if (contactForm && formMessage && formMessageText && submitBtn && btnText && btnLoader) {
    contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        btnText.classList.add('hidden');
        btnLoader.classList.remove('hidden');
        submitBtn.disabled = true;

        const formData = new FormData(contactForm);

        try {
            const response = await fetch(contactForm.action, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            // Actualizar el mensaje
            formMessageText.textContent = data.message;
            formMessage.classList.remove('hidden', 'success', 'error');
            formMessage.classList.add(data.status || (response.ok ? 'success' : 'error')); // Usamos data.status si está disponible, sino response.ok

            // Asegurarnos de que el mensaje sea visible
            formMessage.style.opacity = '1';
            formMessage.style.display = 'block';

            // Restablecer el formulario si fue exitoso
            if (response.ok) {
                contactForm.reset();
            }

            // Ocultar el mensaje después de 5 segundos
            setTimeout(() => {
                formMessage.classList.add('hidden');
                formMessage.style.opacity = '0';
                formMessage.style.display = 'none';
            }, 5000);
        } catch (error) {
            // Manejo de errores en caso de fallo en la solicitud
            formMessageText.textContent = 'Error al enviar el mensaje. Intenta de nuevo.';
            formMessage.classList.remove('hidden', 'success', 'error');
            formMessage.classList.add('error');
            formMessage.style.opacity = '1';
            formMessage.style.display = 'block';

            setTimeout(() => {
                formMessage.classList.add('hidden');
                formMessage.style.opacity = '0';
                formMessage.style.display = 'none';
            }, 5000);

            console.error('Error en el envío del formulario:', error);
        } finally {
            // Restablecer el botón
            btnText.classList.remove('hidden');
            btnLoader.classList.add('hidden');
            submitBtn.disabled = false;
        }
    });
} else {
    console.error('Elementos del formulario de contacto no encontrados:', {
        contactForm, formMessage, formMessageText, submitBtn, btnText, btnLoader
    });
}


 

    // === Inicialización y Verificaciones ===
    // Verificar si GSAP está disponible
    if (typeof gsap === 'undefined') {
        console.warn("GSAP no está disponible. Algunas animaciones no funcionarán.");
    }

    // === Animaciones Iniciales ===
    // Restablecer estado de la galería al cargar o recargar
    const galleryItems = document.querySelectorAll('.galeria-item');
    if (galleryItems.length > 0 && typeof gsap !== 'undefined') {
        galleryItems.forEach(item => {
            gsap.set(item, { y: 0, scale: 1, boxShadow: '0 5px 15px rgba(0, 0, 0, 0.1)' });
            const cover = item.querySelector('.galeria-cover');
            const title = item.querySelector('.galeria-title');
            if (cover) gsap.set(cover, { scale: 1, opacity: 1 });
            if (title) gsap.set(title, { y: 0, color: '#fff' });
        });
    }

    // Animaciones del Logo
    const logoImage = document.querySelector('.logo-image');
    const logoText = document.querySelector('.logo-text');
    if (logoImage && logoText && typeof gsap !== 'undefined') {
        // Animación de entrada para la imagen del logo
        gsap.from(logoImage, {
            x: -50,
            opacity: 0,
            duration: 1.5,
            ease: 'power3.out',
            onComplete: () => {
                // Efecto de pulso cíclico
                gsap.to(logoImage, {
                    scale: 1.1,
                    duration: 1,
                    repeat: -1,
                    yoyo: true,
                    ease: 'sine.inOut'
                });
                // Resplandor cíclico
                gsap.to(logoImage, {
                    filter: 'drop-shadow(0 0 10px rgba(0, 224, 255, 0.8))',
                    duration: 1.5,
                    repeat: -1,
                    yoyo: true,
                    ease: 'sine.inOut'
                });
            }
        });

        // Animación de entrada para el texto del logo
        const letters = logoText.textContent.split('');
        logoText.textContent = '';
        letters.forEach(letter => {
            const span = document.createElement('span');
            span.textContent = letter === ' ' ? '\u00A0' : letter;
            span.style.display = 'inline-block';
            logoText.appendChild(span);
        });

        gsap.from(logoText, {
            x: 50,
            opacity: 0,
            duration: 1.5,
            ease: 'power3.out',
            delay: 0.3
        });

        gsap.from(logoText.children, {
            opacity: 0,
            y: 20,
            duration: 0.5,
            stagger: 0.05,
            ease: 'power2.out',
            delay: 0.5,
            onComplete: () => {
                gsap.to(logoText, {
                    textShadow: '0 0 10px rgba(0, 224, 255, 0.8)',
                    duration: 1.5,
                    repeat: -1,
                    yoyo: true,
                    ease: 'sine.inOut'
                });
            }
        });
    }

    // Elementos del héroe
    const heroSubtitle = document.querySelector('.hero-subtitle');
    const heroBtn = document.querySelector('.hero-btn');
    const heroOverlay = document.querySelector('.hero-overlay');
    const navbar = document.querySelector('.navbar');

    // Animaciones del héroe
    if (heroSubtitle && typeof gsap !== 'undefined') {
        gsap.from(heroSubtitle, { opacity: 0, y: 30, duration: 1.5, ease: 'power3.out' });
    }
    if (heroBtn && typeof gsap !== 'undefined') {
        gsap.from(heroBtn, { opacity: 0, scale: 0.5, duration: 1.2, delay: 0.6, ease: 'elastic.out(1, 0.5)' });
    }
    if (heroOverlay && typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
        gsap.to(heroOverlay, {
            y: '20%',
            ease: 'none',
            scrollTrigger: {
                trigger: '.hero',
                start: 'top top',
                end: 'bottom top',
                scrub: true
            }
        });
    }

    // Animación inicial del navbar
    if (navbar && typeof gsap !== 'undefined') {
        gsap.from(navbar, {
            y: -100,
            duration: 1,
            ease: 'power2.out',
            onComplete: () => {
                navbar.style.willChange = 'auto';
                navbar.style.transform = 'translateZ(0)';
            }
        });
    }

    // === Interacciones del Usuario ===
    // Control de visibilidad del navbar al hacer scroll
    let lastScrollTop = 0;
    window.addEventListener('scroll', () => {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop;
        const navbarHeight = 60;

        if (navbar) {
            if (scrollTop <= navbarHeight) {
                navbar.classList.remove('hidden');
                navbar.classList.toggle('scrolled', scrollTop > 50);
            } else if (scrollTop > lastScrollTop) {
                navbar.classList.add('hidden');
            } else {
                navbar.classList.remove('hidden');
            }
            navbar.classList.toggle('scrolled', scrollTop > 50);
            lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
        }
    }, { passive: true });

    // Menú hamburguesa
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.nav-links');
    const body = document.body;

    if (hamburger && navLinks) {
        console.log("Hamburguesa y navLinks encontrados");
        hamburger.addEventListener('click', () => {
            console.log("Hamburguesa clicada");
            hamburger.classList.toggle('active');
            navLinks.classList.toggle('active');
            body.classList.toggle('menu-open');
        });

        document.addEventListener('click', (e) => {
            if (!hamburger.contains(e.target) && !navLinks.contains(e.target)) {
                console.log("Clic fuera del menú, cerrando...");
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
                body.classList.remove('menu-open');
            }
        });

        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                console.log("Enlace clicado, cerrando menú...");
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
                body.classList.remove('menu-open');
            });
        });
    } else {
        console.error("Hamburguesa o navLinks no encontrados:", { hamburger, navLinks });
    }

    // Buscador minimalista
    const searchToggle = document.querySelector('.search-toggle');
    const searchForm = document.querySelector('.search-form');

    if (searchToggle && searchForm) {
        searchToggle.addEventListener('click', (e) => {
            e.preventDefault();
            searchForm.classList.toggle('active');
            if (searchForm.classList.contains('active')) {
                const searchInput = document.querySelector('.search-input');
                if (searchInput) searchInput.focus();
            }
        });
    } else {
        console.error('Error: .search-toggle o .search-form no encontrados en el DOM');
    }

    // === Animaciones con Intersection Observer ===
const observerOptions = {
    root: null,
    rootMargin: '100px 0px',
    threshold: 0.2
};

const observer = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry, index) => {
        if (entry.isIntersecting) {
            const el = entry.target;

            // Animación para services-details
            if (el.classList.contains('services-details')) {
                el.classList.add('visible'); // Añadimos la clase 'visible' para activar la transición definida en CSS
                observer.unobserve(el); // Dejamos de observar este elemento
            }
            // Animaciones existentes con data-aos
            else if (el.dataset.aos === 'fade-up') {
                gsap.fromTo(el, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.8, delay: index * 0.1, ease: 'power2.out', onComplete: () => observer.unobserve(el) });
            } else if (el.dataset.aos === 'zoom-in') {
                gsap.fromTo(el, { opacity: 0, scale: 0.95 }, { opacity: 1, scale: 1, duration: 0.6, delay: index * 0.05, ease: 'power2.out', onComplete: () => observer.unobserve(el) });
            } else if (el.dataset.aos === 'fade-down') {
                gsap.fromTo(el, { opacity: 0, y: -30 }, { opacity: 1, y: 0, duration: 0.8, delay: index * 0.1, ease: 'power2.out', onComplete: () => observer.unobserve(el) });
            }
        }
    });
}, observerOptions);

// Observamos los elementos con data-aos y la sección services-details
document.querySelectorAll('[data-aos], .services-details').forEach(el => observer.observe(el));

   // === Animaciones de la Tech Section ===
if (typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
    const techSection = document.querySelector('.tech-section');
    const techTitle = document.querySelector('.tech-title');
    const techIntro = document.querySelector('.tech-intro');
    const techCards = document.querySelectorAll('.tech-card');

    if (techSection && techTitle && techIntro && techCards.length > 0) {
        // Animación del título
        gsap.fromTo(
            techTitle,
            { opacity: 0, y: 50 },
            {
                opacity: 1,
                y: 0,
                duration: 1,
                ease: 'power3.out',
                scrollTrigger: {
                    trigger: techSection,
                    start: 'top 80%',
                    toggleActions: 'play none none reverse'
                }
            }
        );

        // Animación del párrafo introductorio
        gsap.fromTo(
            techIntro,
            { opacity: 0, y: 30 },
            {
                opacity: 1,
                y: 0,
                duration: 1,
                delay: 0.3,
                ease: 'power3.out',
                scrollTrigger: {
                    trigger: techSection,
                    start: 'top 80%',
                    toggleActions: 'play none none reverse'
                }
            }
        );

        // Animación de las tarjetas con stagger e iluminación
        gsap.fromTo(
            techCards,
            { 
                opacity: 0, 
                y: 40, 
                boxShadow: '0 4px 12px rgba(0, 224, 255, 0.1)' // Estado inicial
            },
            {
                opacity: 1,
                y: 0,
                boxShadow: '0 6px 16px rgba(0, 224, 255, 0.3)', // Iluminación al aparecer
                duration: 0.8,
                stagger: 0.2,
                ease: 'power2.out',
                scrollTrigger: {
                    trigger: techSection,
                    start: 'top 70%',
                    toggleActions: 'play none none reverse'
                }
            }
        );
    } else {
        console.warn('Elementos de .tech-section no encontrados:', { techSection, techTitle, techIntro, techCards });
    }
}

    // Animaciones de hover para la galería
    if (typeof gsap !== 'undefined') {
        const isMobile = window.innerWidth < 768;
        galleryItems.forEach(item => {
            const cover = item.querySelector('.galeria-cover');
            const title = item.querySelector('.galeria-title');

            if (!isMobile) {
                item.addEventListener('mouseenter', () => {
                    gsap.to(item, {
                        y: -20,
                        scale: 1.05,
                        boxShadow: '0 15px 30px rgba(0, 0, 0, 0.25), 0 0 20px rgba(255, 202, 40, 0.5)',
                        duration: 0.4,
                        ease: 'elastic.out(1, 0.5)',
                    });
                    if (cover) {
                        gsap.to(cover, {
                            scale: 1.1,
                            opacity: 0.85,
                            duration: 0.4,
                            ease: 'power2.out'
                        });
                    }
                    if (title) {
                        gsap.to(title, {
                            y: -10,
                            color: '#ffca28',
                            duration: 0.4,
                            ease: 'power2.out'
                        });
                    }
                });

                item.addEventListener('mouseleave', () => {
                    gsap.to(item, {
                        y: 0,
                        scale: 1,
                        boxShadow: '0 5px 15px rgba(0, 0, 0, 0.1)',
                        duration: 0.4,
                        ease: 'power2.out'
                    });
                    if (cover) {
                        gsap.to(cover, {
                            scale: 1,
                            opacity: 1,
                            duration: 0.4,
                            ease: 'power2.out'
                        });
                    }
                    if (title) {
                        gsap.to(title, {
                            y: 0,
                            color: '#fff',
                            duration: 0.4,
                            ease: 'power2.out'
                        });
                    }
                });
            }
        });
    }

    // === Modo Oscuro ===
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    const toggleIcon = darkModeToggle ? darkModeToggle.querySelector('.dark-mode-icon') : null;

    if (darkModeToggle && body) {
        const isDarkMode = localStorage.getItem('darkMode') === 'true';
        if (isDarkMode) {
            body.classList.add('dark-mode');
            if (toggleIcon) toggleIcon.classList.add('light-icon');
        } else {
            if (toggleIcon) toggleIcon.classList.add('dark-icon');
        }

        darkModeToggle.addEventListener('click', () => {
            body.classList.toggle('dark-mode');
            const darkModeEnabled = body.classList.contains('dark-mode');
            localStorage.setItem('darkMode', darkModeEnabled);
            if (toggleIcon) {
                toggleIcon.classList.toggle('light-icon');
                toggleIcon.classList.toggle('dark-icon');
            }
            if (typeof gsap !== 'undefined') {
                gsap.to(body, {
                    backgroundColor: darkModeEnabled ? '#1a1a1a' : '#f8f1e9',
                    color: darkModeEnabled ? '#e0e0e0' : '#333',
                    duration: 0.5,
                    ease: 'power2.out'
                });
            }
        });
    } else {
        console.error('Error: #dark-mode-toggle o body no encontrados en el DOM');
    }

    // === Mensajes Flash ===
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(message => {
        message.classList.add('show');
        setTimeout(() => {
            message.classList.remove('show');
        }, 3000);
    });

    // === Búsqueda Avanzada con Fuse.js ===
    if (document.querySelector('.busqueda')) {
        const reflexiones = window.reflexionesData || [];
        const fuse = new Fuse(reflexiones, {
            keys: ['titulo', 'contenido', 'categoria'],
            threshold: 0.3,
            includeScore: true
        });

        const searchInput = document.querySelector('.search-input');
        const resultsList = document.getElementById('results-list');
        const totalResults = document.getElementById('total-results');
        const searchQuery = document.getElementById('search-query');

        if (searchInput && resultsList && totalResults && searchQuery) {
            searchInput.addEventListener('input', (e) => {
                const query = e.target.value.trim();
                if (!query) {
                    resultsList.innerHTML = reflexiones.map(result => `
                        <li class="resultado-item" style="border: 1px solid red; margin: 10px 0; padding: 10px;">
                            <div class="resultado-imagen">
                                ${result.imagen ? `<img src="${result.imagen}" alt="${result.titulo}" class="resultado-cover" style="border: 2px solid green; max-width: 200px; height: auto;">` : '<p>Sin imagen</p>'}
                            </div>
                            <div class="resultado-content">
                                <h2><a href="/reflexion/${result.id}">${result.titulo}</a></h2>
                                <p class="categoria">${result.categoria.charAt(0).toUpperCase() + result.categoria.slice(1)}</p>
                                <div class="resultado-extracto">
                                    <p>${result.contenido.substring(0, 200)}${result.contenido.length > 200 ? '...' : ''}</p>
                                </div>
                            </div>
                        </li>
                    `).join('');
                    totalResults.textContent = reflexiones.length;
                    searchQuery.textContent = '';
                    return;
                }

                const results = fuse.search(query);
                totalResults.textContent = results.length;
                searchQuery.textContent = query;

                resultsList.innerHTML = results.map(result => `
                    <li class="resultado-item" style="border: 1px solid red; margin: 10px 0; padding: 10px;">
                        <div class="resultado-imagen">
                            ${result.item.imagen ? `<img src="${result.item.imagen}" alt="${result.item.titulo}" class="resultado-cover" style="border: 2px solid green; max-width: 200px; height: auto;">` : '<p>Sin imagen</p>'}
                        </div>
                        <div class="resultado-content">
                            <h2><a href="/reflexion/${result.item.id}">${result.item.titulo}</a></h2>
                            <p class="categoria">${result.item.categoria.charAt(0).toUpperCase() + result.item.categoria.slice(1)}</p>
                            <div class="resultado-extracto">
                                <p>${result.item.contenido.substring(0, 200)}${result.item.contenido.length > 200 ? '...' : ''}</p>
                            </div>
                        </li>
                `).join('') || `<p class="no-resultados">No se encontraron resultados para "${query}".</p>`;
            });
        }
    }

    

    // === Lazy Loading de Imágenes ===
    const inlineImages = document.querySelectorAll('.blog-text img[src], .post-content img[src]');
    inlineImages.forEach(img => {
        if (!img.classList.contains('lazyload')) {
            const src = img.getAttribute('src');
            img.setAttribute('data-src', src);
            img.removeAttribute('src');
            img.classList.add('lazyload');
        }
    });

   // === Chatbot ===
let messageHistory = [
    {"role": "system", "content": "Eres QuantumBot, un asistente virtual de Quantum Web. Responde de manera amigable, breve y directa, usando un tono alegre. Limítate a respuestas cortas (máximo 2-3 frases). Si es posible, incluye un emoji o icono relevante al final de tu respuesta."}
];

// Solo ejecutamos el código del chatbot si estamos en la página que tiene el widget (index.html)
const chatbotWidget = document.querySelector('.chatbot-widget');
if (chatbotWidget) {
    const chatbotToggle = document.querySelector('.chatbot-toggle');
    const chatbotInput = document.querySelector('.chatbot-input input');
    const chatbotSend = document.querySelector('.chatbot-input button');
    const chatbotBody = document.querySelector('.chatbot-body');

    if (chatbotToggle && chatbotInput && chatbotSend && chatbotBody) {
        // Mostrar mensaje inicial
        if (!chatbotBody.querySelector('.chatbot-message.bot')) {
            const initialMessage = document.createElement('div');
            initialMessage.classList.add('chatbot-message', 'bot');
            initialMessage.innerHTML = '¡Hola! Soy QuantumBot, tu asistente virtual. ¿En qué puedo ayudarte hoy? 👋';
            chatbotBody.appendChild(initialMessage);
        }

        // Mostrar el chatbot después de 2 segundos
        setTimeout(() => {
            chatbotWidget.classList.add('active');
        }, 2000);

        // Evento para cerrar/abrir el chatbot
        chatbotToggle.addEventListener('click', () => {
            chatbotWidget.classList.toggle('active');
        });

        // Evento para enviar mensaje
        chatbotSend.addEventListener('click', sendMessage);
        chatbotInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        async function sendMessage() {
            const message = chatbotInput.value.trim();
            if (message) {
                const userMessage = document.createElement('div');
                userMessage.classList.add('chatbot-message', 'user');
                userMessage.textContent = message;
                chatbotBody.appendChild(userMessage);
                chatbotInput.value = '';

                const typingMessage = document.createElement('div');
                typingMessage.classList.add('chatbot-message', 'bot');
                typingMessage.innerHTML = 'Escribiendo... ⏳';
                chatbotBody.appendChild(typingMessage);
                chatbotBody.scrollTop = chatbotBody.scrollHeight;

                messageHistory.push({"role": "user", "content": message});

                try {
                    const response = await fetch('/api/grok', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ message, history: messageHistory })
                    });

                    const data = await response.json();
                    typingMessage.remove();

                    if (data.error) {
                        const errorMessage = document.createElement('div');
                        errorMessage.classList.add('chatbot-message', 'bot', 'error');
                        errorMessage.innerHTML = 'Lo siento, algo salió mal. Intenta de nuevo. 😓';
                        chatbotBody.appendChild(errorMessage);
                    } else {
                        const botMessage = document.createElement('div');
                        botMessage.classList.add('chatbot-message', 'bot');
                        botMessage.innerHTML = data.response;
                        chatbotBody.appendChild(botMessage);
                        messageHistory.push({"role": "assistant", "content": data.response});
                    }
                } catch (error) {
                    typingMessage.remove();
                    const errorMessage = document.createElement('div');
                    errorMessage.classList.add('chatbot-message', 'bot', 'error');
                    errorMessage.innerHTML = 'No pude conectar con el servidor. Intenta de nuevo. 😓';
                    chatbotBody.appendChild(errorMessage);
                }

                chatbotBody.scrollTop = chatbotBody.scrollHeight;
            }
        }
    } else {
        console.error('Uno o más elementos del chatbot no se encontraron en el DOM.');
    }
}
});

// === Efectos de Tarjetas ===
const cards = document.querySelectorAll('.case-study, .service-card');
if (typeof gsap !== 'undefined') {
    cards.forEach(card => {
        // Efecto al entrar (hover)
        card.addEventListener('mouseenter', () => {
            gsap.to(card, {
                scale: 1.02, // Escala ligera para dar sensación de interacción
                duration: 0.3,
                ease: 'power2.out'
            });

            // Añadir un resplandor suave al título dentro de la tarjeta
            const title = card.querySelector('h2');
            if (title) {
                gsap.to(title, {
                    color: '#00e0ff', // Cambia el color del título a cian
                    textShadow: '0 0 8px rgba(0, 224, 255, 0.5)', // Resplandor suave
                    duration: 0.3,
                    ease: 'power2.out'
                });
            }
        });

        // Efecto al salir (mouseleave)
        card.addEventListener('mouseleave', () => {
            gsap.to(card, {
                scale: 1, // Vuelve a la escala original
                duration: 0.3,
                ease: 'power2.out'
            });

            // Restaurar el título
            const title = card.querySelector('h2');
            if (title) {
                gsap.to(title, {
                    color: '#ffffff', // Color original del título
                    textShadow: 'none', // Quitar el resplandor
                    duration: 0.3,
                    ease: 'power2.out'
                });
            }
        });
    });
}

// === Loader ===
window.addEventListener('load', () => {
    const loader = document.querySelector('.loader');
    if (loader) {
        loader.classList.add('hidden');
    }
});

// === Transiciones de Enlaces ===
document.querySelectorAll('a[href]').forEach(link => {
    link.addEventListener('click', (e) => {
        const href = link.getAttribute('href');
        if (href && !href.startsWith('#') && !link.getAttribute('target') && typeof gsap !== 'undefined') {
            e.preventDefault();
            gsap.to('body', {
                opacity: 0,
                duration: 0.5,
                ease: 'power2.out',
                onComplete: () => {
                    window.location.href = href;
                }
            });
        }
    });
});

// === Efecto Matrix ===
const matrixCanvas = document.getElementById('matrix-canvas');
if (matrixCanvas) {
    const ctx = matrixCanvas.getContext('2d');
    const section = matrixCanvas.parentElement; // matrix-section

    // Función para redimensionar el canvas
    function resizeCanvas() {
        matrixCanvas.width = section.offsetWidth; // Usamos el ancho del contenedor padre (matrix-section)
        matrixCanvas.height = section.offsetHeight; // Altura del contenedor padre
        // Recalculamos las columnas después de redimensionar
        columns = Math.ceil(matrixCanvas.width / fontSize); // Redondeamos hacia arriba
        drops = Array(columns).fill(1); // Reiniciamos las gotas
    }

    // Esperamos a que el DOM y los estilos estén completamente cargados
    window.addEventListener('load', () => {
        resizeCanvas(); // Redimensionamos inicialmente
    });

    // También redimensionamos en caso de que la ventana cambie de tamaño
    window.addEventListener('resize', () => {
        resizeCanvas();
    });

    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()_+-=[]{}|;:,.<>?';
    const fontSize = 14;
    let columns = Math.ceil(matrixCanvas.width / fontSize); // Redondeamos hacia arriba
    let drops = Array(columns).fill(1);

    function drawMatrix() {
        ctx.fillStyle = 'rgba(18, 18, 18, 0.05)';
        ctx.fillRect(0, 0, matrixCanvas.width, matrixCanvas.height);

        ctx.fillStyle = '#00e0ff';
        ctx.font = fontSize + 'px monospace';

        for (let i = 0; i < drops.length; i++) {
            const text = chars.charAt(Math.floor(Math.random() * chars.length));
            const xPos = i * fontSize;
            // Solo dibujamos si la posición está dentro del ancho del canvas
            if (xPos < matrixCanvas.width) {
                ctx.fillText(text, xPos, drops[i] * fontSize);
            }

            if (drops[i] * fontSize > matrixCanvas.height && Math.random() > 0.975) {
                drops[i] = 0;
            }
            drops[i]++;
        }
    }

    setInterval(drawMatrix, 50);
}
// === Animaciones para Case Studies ===
if (typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
    const caseStudiesSection = document.querySelector('.case-studies-list');
    const caseStudyCards = document.querySelectorAll('.case-study-card');

    if (caseStudiesSection && caseStudyCards.length > 0) {
        // Animación de entrada para las tarjetas
        caseStudyCards.forEach((card, index) => {
            const direction = card.dataset.aos === 'fade-right' ? -100 : 100;
            gsap.fromTo(
                card,
                { opacity: 0, x: direction },
                {
                    opacity: 1,
                    x: 0,
                    duration: 1,
                    ease: 'power3.out',
                    scrollTrigger: {
                        trigger: card,
                        start: 'top 85%', // Ajustado para que inicie un poco antes
                        toggleActions: 'play none none reverse'
                    }
                }
            );
        });

        // Efecto de paralaje para las tarjetas
        caseStudyCards.forEach(card => {
            const speed = parseFloat(card.dataset.parallaxSpeed) || 0.2;
            gsap.to(card, {
                y: () => 100 * speed, // Reducimos el desplazamiento a un valor fijo (100px base) ajustado por speed
                ease: 'none',
                scrollTrigger: {
                    trigger: caseStudiesSection,
                    start: 'top 80%', // Comienza antes
                    end: 'bottom 20%', // Termina antes para dejar espacio al CTA
                    scrub: 1, // Suavizamos el movimiento (valor menor para más control)
                    invalidateOnRefresh: true // Recalcula al redimensionar
                }
            });
        });

        // Animación de hover para las tarjetas (ya incluida en .case-study)
    } else {
        console.warn('Elementos de .case-studies-list no encontrados:', { caseStudiesSection, caseStudyCards });
    }
}

// Animaciones para la sección de blog
if (typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
    const blogPostsSection = document.querySelector('.blog-posts');
    const blogPosts = document.querySelectorAll('.blog-post');

    if (blogPostsSection && blogPosts.length > 0) {
        // Animación de entrada para cada entrada de blog
        blogPosts.forEach((post, index) => {
            gsap.fromTo(
                post,
                { opacity: 0, y: 30 },
                {
                    opacity: 1,
                    y: 0,
                    duration: 0.8,
                    ease: 'power2.out',
                    scrollTrigger: {
                        trigger: post,
                        start: 'top 85%',
                        toggleActions: 'play none none reverse'
                    },
                    delay: index * 0.1 // Stagger sutil
                }
            );
        });

        // Animación del título de la sección
        const blogTitle = document.querySelector('.blog-container h2');
        if (blogTitle) {
            gsap.fromTo(
                blogTitle,
                { opacity: 0, y: 20 },
                {
                    opacity: 1,
                    y: 0,
                    duration: 1,
                    ease: 'power3.out',
                    scrollTrigger: {
                        trigger: blogPostsSection,
                        start: 'top 80%',
                        toggleActions: 'play none none reverse'
                    }
                }
            );
        }
    }
}
document.addEventListener('DOMContentLoaded', () => {
    const footerForm = document.getElementById('footer-contact-form');
    const footerMessage = document.getElementById('footer-form-message');
    const footerMessageText = document.getElementById('footer-form-message-text');
    const footerSubmitBtn = footerForm.querySelector('.contact-btn');
    const footerBtnText = footerSubmitBtn.querySelector('.btn-text');
    const footerBtnLoader = footerSubmitBtn.querySelector('.btn-loader');

    if (footerForm) {
        footerForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Mostrar loader
            footerSubmitBtn.disabled = true;
            footerBtnText.classList.add('hidden');
            footerBtnLoader.classList.remove('hidden');

            const formData = new FormData(footerForm);

            try {
                const response = await fetch(footerForm.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'Accept': 'application/json'
                    }
                });

                const result = await response.json();

                // Mostrar mensaje
                footerMessageText.textContent = result.message;
                footerMessage.classList.remove('hidden');
                footerMessage.classList.add(result.status);

                // Ocultar mensaje después de 3 segundos
                setTimeout(() => {
                    footerMessage.classList.add('hidden');
                    footerMessage.classList.remove('success', 'error');
                }, 3000);

                // Resetear formulario si fue exitoso
                if (result.status === 'success') {
                    footerForm.reset();
                }
            } catch (error) {
                footerMessageText.textContent = 'Error al enviar el mensaje. Intenta de nuevo más tarde.';
                footerMessage.classList.remove('hidden');
                footerMessage.classList.add('error');
                setTimeout(() => {
                    footerMessage.classList.add('hidden');
                    footerMessage.classList.remove('error');
                }, 3000);
            } finally {
                // Ocultar loader
                footerSubmitBtn.disabled = false;
                footerBtnText.classList.remove('hidden');
                footerBtnLoader.classList.add('hidden');
            }
        });
    }
});