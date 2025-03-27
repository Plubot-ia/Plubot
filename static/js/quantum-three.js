console.log("quantum-three.js cargado");

// === Inicialización y Verificaciones ===
if (typeof THREE === 'undefined') {
    console.error("Three.js no cargado");
} else {
    console.log("Three.js cargado correctamente");
}
if (typeof gsap === 'undefined') {
    console.error("GSAP no cargado");
} else {
    console.log("GSAP cargado correctamente");
}
if (typeof particlesJS === 'undefined') {
    console.error("Particles.js no cargado");
} else {
    console.log("Particles.js cargado correctamente");
}
if (typeof ScrollTrigger === 'undefined') {
    console.error("ScrollTrigger no cargado");
} else {
    console.log("ScrollTrigger cargado correctamente");
}

// === Configuración de Three.js ===
if (typeof THREE !== 'undefined') {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    const canvasContainer = document.getElementById('three-canvas');

    if (canvasContainer) {
        canvasContainer.innerHTML = '';
        canvasContainer.appendChild(renderer.domElement);
        console.log("Renderer Three.js añadido al DOM");
    } else {
        console.error("Contenedor #three-canvas no encontrado");
    }

    // Luz
    const ambientLight = new THREE.AmbientLight(0x404040);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0x00d4ff, 1);
    directionalLight.position.set(5, 5, 5);
    scene.add(directionalLight);

    // Esfera y órbitas
    const geometry = new THREE.SphereGeometry(1, 32, 32);
    const material = new THREE.MeshPhongMaterial({ color: 0x00d4ff, emissive: 0x00d4ff, emissiveIntensity: 0.5 });
    const sphere = new THREE.Mesh(geometry, material);
    scene.add(sphere);

    const orbitGeometry = new THREE.TorusGeometry(2, 0.05, 16, 100);
    const orbitMaterial = new THREE.MeshBasicMaterial({ color: 0x00d4ff });
    const orbit1 = new THREE.Mesh(orbitGeometry, orbitMaterial);
    orbit1.rotation.x = Math.PI / 4;
    scene.add(orbit1);

    const orbit2 = new THREE.Mesh(orbitGeometry, orbitMaterial);
    orbit2.rotation.y = Math.PI / 4;
    scene.add(orbit2);

    camera.position.z = 5;

    // Shader
    const shaderMaterial = new THREE.ShaderMaterial({
        uniforms: {
            time: { value: 0.0 },
            resolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) }
        },
        vertexShader: `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform float time;
            uniform vec2 resolution;
            varying vec2 vUv;
            void main() {
                vec2 uv = vUv;
                vec3 color = vec3(0.0);
                float wave = sin(uv.x * 10.0 + time) * cos(uv.y * 10.0 + time) * 0.5 + 0.5;
                color = vec3(wave * 0.1, wave * 0.5, wave);
                gl_FragColor = vec4(color, 0.5);
            }
        `,
        transparent: true
    });

    const planeGeometry = new THREE.PlaneGeometry(20, 20);
    const plane = new THREE.Mesh(planeGeometry, shaderMaterial);
    plane.position.z = -5;
    scene.add(plane);

    // Animación de la escena
    function animate() {
        requestAnimationFrame(animate);
        sphere.rotation.x += 0.01;
        sphere.rotation.y += 0.01;
        orbit1.rotation.z += 0.02;
        orbit2.rotation.z -= 0.02;
        renderer.render(scene, camera);
    }
    animate();
    console.log("Animación Three.js iniciada");

    // Animar el shader
    function animateShader() {
        shaderMaterial.uniforms.time.value += 0.05;
        requestAnimationFrame(animateShader);
    }
    animateShader();

    // Responsividad
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    // Interacción con ratón
    let mouseX = 0, mouseY = 0;
    document.addEventListener('mousemove', (event) => {
        mouseX = (event.clientX / window.innerWidth) * 2 - 1;
        mouseY = -(event.clientY / window.innerHeight) * 2 + 1;
        if (typeof gsap !== 'undefined') {
            gsap.to(sphere.rotation, {
                x: mouseY * 0.5,
                y: mouseX * 0.5,
                duration: 1
            });
        }
    });
}

// === Configuración de Particles.js ===
if (typeof particlesJS !== 'undefined') {
    const particlesContainer = document.getElementById('particles-js');
    if (particlesContainer) {
        particlesContainer.innerHTML = '';
        particlesJS('particles-js', {
            particles: {
                number: { value: 100, density: { enable: true, value_area: 1000 } },
                color: { value: '#00e0ff' },
                shape: { type: 'circle' },
                opacity: { value: 0.6, random: true, anim: { enable: true, speed: 1, opacity_min: 0.2 } },
                size: { value: 2.5, random: true, anim: { enable: true, speed: 2, size_min: 0.5 } },
                line_linked: { 
                    enable: true, 
                    distance: 120, 
                    color: '#00e0ff', 
                    opacity: 0.3, 
                    width: 1 
                },
                move: { 
                    enable: true, 
                    speed: 4, 
                    direction: 'none', 
                    random: true, 
                    straight: false, 
                    out_mode: 'out', 
                    bounce: false 
                }
            },
            interactivity: {
                detect_on: 'window', // Detecta eventos en toda la ventana
                events: {
                    onhover: { enable: true, mode: 'repulse' },
                    onclick: { enable: true, mode: 'push' },
                    resize: true
                },
                modes: {
                    repulse: { 
                        distance: 100,
                        duration: 0.4
                    },
                    push: { particles_nb: 3 }
                }
            },
            retina_detect: true
        });
        console.log("Particles.js inicializado con interacción al mouse (modo repulse)");
    } else {
        console.error("Contenedor #particles-js no encontrado");
    }
}

// === Animaciones GSAP ===
if (typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
    gsap.registerPlugin(ScrollTrigger);

    // Animaciones para la sección hero
    const heroSection = document.querySelector('.quantum-hero, .services-hero, .about-hero, .case-studies-hero');
    if (heroSection) {
        const title = heroSection.querySelector('h1');
        const subtitle = heroSection.querySelector('p');
        const button = heroSection.querySelector('a.quantum-btn');

        if (title) {
            gsap.set(title, { opacity: 0, scale: 0.5 });
            gsap.to(title, {
                opacity: 1,
                scale: 1,
                duration: 2,
                ease: "back.out(1.7)",
                delay: 0.5,
                onComplete: () => console.log("Animación del título completada")
            });
        }

        if (subtitle) {
            gsap.set(subtitle, { opacity: 0, y: 50 });
            gsap.to(subtitle, {
                opacity: 1,
                y: 0,
                duration: 1.5,
                ease: "power2.out",
                delay: 1
            });
        }

        if (button) {
            gsap.set(button, { opacity: 0, y: 50 });
            gsap.to(button, {
                opacity: 1,
                y: 0,
                duration: 1.5,
                ease: "power2.out",
                delay: 1.2
            });
        }
    }

    // Animación para las tarjetas
    const quantumCards = document.querySelectorAll('.quantum-card');
    if (quantumCards.length > 0) {
        gsap.from(quantumCards, {
            scrollTrigger: {
                trigger: ".scroll-section",
                start: "top 80%",
                end: "bottom 20%",
                toggleActions: "play none none reverse"
            },
            duration: 1,
            opacity: 0,
            y: 100,
            ease: "power2.out",
            stagger: 0.2,
            onComplete: () => console.log("Animación de las tarjetas completada")
        });
    }

    console.log("GSAP inicializado");
} else {
    console.error("GSAP o ScrollTrigger no cargados");
}