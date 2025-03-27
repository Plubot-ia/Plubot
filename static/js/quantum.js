// Configuración de Particles.js
particlesJS('particles-js', {
    particles: {
        number: { value: 100, density: { enable: true, value_area: 800 } },
        color: { value: '#00d4ff' },
        shape: { type: 'circle' },
        opacity: { value: 0.5, random: true },
        size: { value: 3, random: true },
        line_linked: { enable: true, distance: 150, color: '#00d4ff', opacity: 0.4, width: 1 },
        move: { enable: true, speed: 6, direction: 'none', random: false, straight: false, out_mode: 'out', bounce: false }
    },
    interactivity: {
        detect_on: 'canvas',
        events: { onhover: { enable: true, mode: 'repulse' }, onclick: { enable: true, mode: 'push' }, resize: true },
        modes: { repulse: { distance: 100, duration: 0.4 }, push: { particles_nb: 4 } }
    },
    retina_detect: true
});

// Registro de ScrollTrigger con GSAP
gsap.registerPlugin(ScrollTrigger);

// Animación inicial del título, subtítulo y botón
gsap.from(".quantum-title", {
    duration: 2,
    opacity: 0,
    scale: 0.5,
    ease: "back.out(1.7)",
    delay: 0.5
});

gsap.from(".quantum-subtitle", {
    duration: 1.5,
    opacity: 0,
    y: 50,
    ease: "power2.out",
    delay: 1
});

gsap.from(".quantum-btn", {
    duration: 1.5,
    opacity: 0,
    y: 50,
    ease: "power2.out",
    delay: 1.2
});

// Animación de scroll para la sección inferior
gsap.from(".quantum-card", {
    scrollTrigger: {
        trigger: ".scroll-section",
        start: "top 80%",
        end: "bottom 20%",
        toggleActions: "play none none reverse"
    },
    duration: 1,
    opacity: 0,
    y: 100,
    ease: "power2.out"
});