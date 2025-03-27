document.addEventListener('DOMContentLoaded', () => {
    console.log('contact.js cargado correctamente');

    // Inicializar partículas
    particlesJS('contact-particles', {
        particles: {
            number: { value: 80, density: { enable: true, value_area: 800 } },
            color: { value: '#00e0ff' },
            shape: { type: 'circle' },
            opacity: { value: 0.5, random: true },
            size: { value: 3, random: true },
            line_linked: { enable: true, distance: 150, color: '#00e0ff', opacity: 0.4, width: 1 },
            move: { enable: true, speed: 2, direction: 'none', random: false, straight: false, out_mode: 'out', bounce: false }
        },
        interactivity: {
            detect_on: 'canvas',
            events: { onhover: { enable: true, mode: 'repulse' }, onclick: { enable: true, mode: 'push' }, resize: true },
            modes: { repulse: { distance: 100, duration: 0.4 }, push: { particles_nb: 4 } }
        },
        retina_detect: true
    });

    // Verificar si GSAP está disponible
    if (typeof gsap === 'undefined') {
        console.error('GSAP no está definido. Asegúrate de que el script de GSAP se haya cargado.');
        return;
    }

    // Verificar si los elementos existen
    const title = document.querySelector('.contact-title');
    const subtitle = document.querySelector('.contact-subtitle');
    const form = document.querySelector('.contact-form');

    console.log('Elemento .contact-title:', title);
    console.log('Elemento .contact-subtitle:', subtitle);
    console.log('Elemento .contact-form:', form);

    if (!title || !subtitle || !form) {
        console.error('Uno o más elementos no se encontraron en el DOM.');
        return;
    }

    // Animaciones con GSAP
    gsap.from('.contact-title', { opacity: 0, y: 50, duration: 1, delay: 0.5, ease: 'power3.out' });
    gsap.from('.contact-subtitle', { opacity: 0, y: 30, duration: 1, delay: 0.8, ease: 'power3.out' });
    gsap.from('.contact-form', { opacity: 0, y: 20, duration: 1, delay: 1, ease: 'power3.out' });

    // Manejo del formulario
    const contactForm = document.getElementById('contact-form');
    const button = contactForm.querySelector('.contact-btn');
    const formMessage = document.getElementById('form-message');
    const formMessageText = document.getElementById('form-message-text');
    const btnText = button.querySelector('.btn-text');
    const btnLoader = button.querySelector('.btn-loader');

    if (!contactForm || !button || !formMessage || !formMessageText || !btnText || !btnLoader) {
        console.error('Elementos del formulario no encontrados.');
        return;
    }

    contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Mostrar estado de carga
        button.disabled = true;
        btnText.classList.add('hidden');
        btnLoader.classList.remove('hidden');

        const formData = new FormData(contactForm);

        // Depuración: Verificar los datos que se están enviando
        for (let [key, value] of formData.entries()) {
            console.log(`${key}: ${value}`);
        }

        try {
            const response = await fetch(contactForm.action, {
                method: 'POST',
                body: formData,
                headers: { 'Accept': 'application/json' }
            });

            const data = await response.json();

            // Mostrar mensaje
            formMessageText.textContent = data.message;
            formMessage.classList.remove('hidden');
            formMessage.classList.add(data.status);

            // Animar el mensaje con GSAP
            gsap.fromTo('#form-message', 
                { opacity: 0, y: 20 }, 
                { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }
            );

            // Ocultar mensaje después de 3 segundos
            setTimeout(() => {
                formMessage.classList.add('hidden');
                formMessage.classList.remove('success', 'error');
            }, 3000);

            // Resetear formulario si fue exitoso
            if (data.status === 'success') {
                contactForm.reset();
            }
        } catch (error) {
            formMessageText.textContent = 'Error al enviar el mensaje. Intenta de nuevo más tarde.';
            formMessage.classList.remove('hidden');
            formMessage.classList.add('error');

            // Animar el mensaje con GSAP
            gsap.fromTo('#form-message', 
                { opacity: 0, y: 20 }, 
                { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }
            );

            // Ocultar mensaje después de 3 segundos
            setTimeout(() => {
                formMessage.classList.add('hidden');
                formMessage.classList.remove('error');
            }, 3000);
        } finally {
            // Ocultar loader
            button.disabled = false;
            btnText.classList.remove('hidden');
            btnLoader.classList.add('hidden');
        }
    });
});