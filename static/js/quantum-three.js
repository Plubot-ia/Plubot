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
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true }); // Habilitamos antialiasing para bordes más suaves
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // Optimizamos para pantallas retina, pero limitamos a 2 para mejor rendimiento
    const canvasContainer = document.getElementById('three-canvas');

    if (canvasContainer) {
        canvasContainer.innerHTML = '';
        canvasContainer.appendChild(renderer.domElement);
        console.log("Renderer Three.js añadido al DOM");
    } else {
        console.error("Contenedor #three-canvas no encontrado");
    }

    // Luz
    const ambientLight = new THREE.AmbientLight(0x404040, 0.5); // Reducimos la intensidad para un efecto más sutil
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0x00d4ff, 1.2);
    directionalLight.position.set(5, 5, 5);
    directionalLight.castShadow = true; // Habilitamos sombras para mayor profundidad
    scene.add(directionalLight);

    // Esfera central con material más dinámico
    const geometry = new THREE.SphereGeometry(0.8, 64, 64); // Aumentamos la resolución para una esfera más suave
    const material = new THREE.MeshStandardMaterial({
        color: 0x00d4ff,
        emissive: 0x00d4ff,
        emissiveIntensity: 0.8,
        metalness: 0.7,
        roughness: 0.3
    });
    const sphere = new THREE.Mesh(geometry, material);
    sphere.castShadow = true;
    sphere.receiveShadow = true;
    scene.add(sphere);

    // Órbitas con efecto de brillo
    const orbitGeometry = new THREE.TorusGeometry(2, 0.03, 16, 100);
    const orbitMaterial = new THREE.MeshBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0.6 });
    const orbit1 = new THREE.Mesh(orbitGeometry, orbitMaterial);
    orbit1.rotation.x = Math.PI / 4;
    scene.add(orbit1);

    const orbit2 = new THREE.Mesh(orbitGeometry, orbitMaterial);
    orbit2.rotation.y = Math.PI / 4;
    scene.add(orbit2);

    // Partículas alrededor de la esfera
    const particleGeometry = new THREE.BufferGeometry();
    const particleCount = 300;
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount * 3; i += 3) {
        const radius = 2 + Math.random() * 1.5;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.random() * Math.PI;
        positions[i] = radius * Math.sin(phi) * Math.cos(theta);
        positions[i + 1] = radius * Math.sin(phi) * Math.sin(theta);
        positions[i + 2] = radius * Math.cos(phi);

        // Colores alternando entre cian y magenta
        const color = new THREE.Color(Math.random() > 0.5 ? 0x00d4ff : 0xff00ff);
        colors[i] = color.r;
        colors[i + 1] = color.g;
        colors[i + 2] = color.b;
    }

    particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const particleMaterial = new THREE.PointsMaterial({
        size: 0.05,
        vertexColors: true,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particles);

    camera.position.z = 5;

    // Shader para el fondo
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
                float wave = sin(uv.x * 15.0 + time) * cos(uv.y * 15.0 + time) * 0.5 + 0.5;
                color = mix(vec3(0.0, 0.5, 1.0), vec3(1.0, 0.0, 1.0), wave); // Gradiente entre cian y magenta
                gl_FragColor = vec4(color, 0.3);
            }
        `,
        transparent: true
    });

    const planeGeometry = new THREE.PlaneGeometry(20, 20);
    const plane = new THREE.Mesh(planeGeometry, shaderMaterial);
    plane.position.z = -5;
    scene.add(plane);

    // Animación de la escena
    let time = 0;
    function animate() {
        requestAnimationFrame(animate);

        // Rotación de la esfera y órbitas
        sphere.rotation.x += 0.01;
        sphere.rotation.y += 0.01;
        orbit1.rotation.z += 0.015;
        orbit2.rotation.z -= 0.015;

        // Animación de partículas
        const positions = particles.geometry.attributes.position.array;
        for (let i = 0; i < particleCount * 3; i += 3) {
            const radius = 2 + Math.sin(time + i) * 0.5;
            const theta = (time * 0.1 + i) % (Math.PI * 2);
            const phi = (time * 0.05 + i) % Math.PI;
            positions[i] = radius * Math.sin(phi) * Math.cos(theta);
            positions[i + 1] = radius * Math.sin(phi) * Math.sin(theta);
            positions[i + 2] = radius * Math.cos(phi);
        }
        particles.geometry.attributes.position.needsUpdate = true;

        time += 0.05;
        shaderMaterial.uniforms.time.value = time;

        renderer.render(scene, camera);
    }
    animate();
    console.log("Animación Three.js iniciada");

    // Responsividad
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
        shaderMaterial.uniforms.resolution.value.set(window.innerWidth, window.innerHeight);
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
            gsap.to(camera.position, {
                x: mouseX * 1,
                y: mouseY * 1,
                duration: 1
            });
        }
    });

    // Animación con ScrollTrigger (si está disponible)
    if (typeof ScrollTrigger !== 'undefined' && typeof gsap !== 'undefined') {
        gsap.registerPlugin(ScrollTrigger);
        gsap.to(sphere.scale, {
            x: 1.5,
            y: 1.5,
            z: 1.5,
            scrollTrigger: {
                trigger: ".auth-section",
                start: "top 80%",
                end: "bottom 20%",
                scrub: true
            }
        });
    }
}

// === Configuración de Particles.js para auth_prompt.html ===
if (typeof particlesJS !== 'undefined') {
    const particlesContainer = document.getElementById('particles-js');
    if (particlesContainer) {
        particlesContainer.innerHTML = '';
        particlesJS('particles-js', {
            particles: {
                number: { value: 80, density: { enable: true, value_area: 1000 } }, // Reducimos el número de partículas para mejor rendimiento
                color: { value: ['#00e0ff', '#ff00ff'] }, // Colores cian y magenta
                shape: { type: 'circle' },
                opacity: { value: 0.6, random: true, anim: { enable: true, speed: 1, opacity_min: 0.2 } },
                size: { value: 2, random: true, anim: { enable: true, speed: 2, size_min: 0.5 } },
                line_linked: { 
                    enable: true, 
                    distance: 120, 
                    color: '#00e0ff', 
                    opacity: 0.3, 
                    width: 1 
                },
                move: { 
                    enable: true, 
                    speed: 3, 
                    direction: 'none', 
                    random: true, 
                    straight: false, 
                    out_mode: 'out', 
                    bounce: false 
                }
            },
            interactivity: {
                detect_on: 'window',
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
        console.log("Particles.js inicializado con interacción al mouse (modo repulse) para auth_prompt.html");
    } else {
        console.error("Contenedor #particles-js no encontrado");
    }
}

// === Ajustes específicos para la página de creación (si aplica) ===
if (document.querySelector('.chatbot-section')) {
    console.log("Configurando efectos para la página de creación");
    particlesJS('particles-js', {
        particles: {
            number: { value: 100, density: { enable: true, value_area: 1000 } },
            color: { value: '#00e0ff' },
            shape: { type: 'circle' },
            opacity: { value: 0.6, random: true },
            size: { value: 2.5, random: true },
            line_linked: { enable: true, distance: 120, color: '#00e0ff', opacity: 0.3, width: 1 },
            move: { enable: true, speed: 4, direction: 'none', random: true }
        },
        interactivity: {
            detect_on: 'window',
            events: { onhover: { enable: true, mode: 'repulse' }, onclick: { enable: true, mode: 'push' }, resize: true },
            modes: { repulse: { distance: 100, duration: 0.4 }, push: { particles_nb: 3 } }
        },
        retina_detect: true
    });
}
