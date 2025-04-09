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
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    const canvasContainer = document.getElementById('three-canvas');

    if (canvasContainer) {
        canvasContainer.innerHTML = '';
        canvasContainer.appendChild(renderer.domElement);
        console.log("Renderer Three.js añadido al DOM");
    } else {
        console.error("Contenedor #three-canvas no encontrado");
    }

    // Luz
    const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8); // Luz blanca más suave
    directionalLight.position.set(5, 5, 5);
    scene.add(directionalLight);

    // Esfera central
    const geometry = new THREE.SphereGeometry(0.8, 32, 32);
    const material = new THREE.MeshStandardMaterial({
        color: 0xaaaaaa, // Gris claro
        emissive: 0xaaaaaa,
        emissiveIntensity: 0.3,
        metalness: 0.8,
        roughness: 0.4
    });
    const sphere = new THREE.Mesh(geometry, material);
    scene.add(sphere);

    // Órbitas
    const orbitGeometry = new THREE.TorusGeometry(2, 0.02, 16, 100);
    const orbitMaterial = new THREE.MeshBasicMaterial({ color: 0x00aaff, transparent: true, opacity: 0.4 });
    const orbit1 = new THREE.Mesh(orbitGeometry, orbitMaterial);
    orbit1.rotation.x = Math.PI / 4;
    scene.add(orbit1);

    const orbit2 = new THREE.Mesh(orbitGeometry, orbitMaterial);
    orbit2.rotation.y = Math.PI / 4;
    scene.add(orbit2);

    // Partículas minimalistas
    const particleGeometry = new THREE.BufferGeometry();
    const particleCount = 100; // Reducimos el número de partículas
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount * 3; i += 3) {
        const radius = 2 + Math.random() * 1;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.random() * Math.PI;
        positions[i] = radius * Math.sin(phi) * Math.cos(theta);
        positions[i + 1] = radius * Math.sin(phi) * Math.sin(theta);
        positions[i + 2] = radius * Math.cos(phi);

        const color = new THREE.Color(0x00aaff); // Cian apagado
        colors[i] = color.r;
        colors[i + 1] = color.g;
        colors[i + 2] = color.b;
    }

    particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const particleMaterial = new THREE.PointsMaterial({
        size: 0.03,
        vertexColors: true,
        transparent: true,
        opacity: 0.5,
        blending: THREE.AdditiveBlending
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particles);

    camera.position.z = 5;

    // Fondo simple (sin shader)
    const planeGeometry = new THREE.PlaneGeometry(20, 20);
    const planeMaterial = new THREE.MeshBasicMaterial({ color: 0x1a1a2e, transparent: true, opacity: 0.5 });
    const plane = new THREE.Mesh(planeGeometry, planeMaterial);
    plane.position.z = -5;
    scene.add(plane);

    // Animación
    let time = 0;
    function animate() {
        requestAnimationFrame(animate);
        sphere.rotation.x += 0.005; // Rotación más lenta
        sphere.rotation.y += 0.005;
        orbit1.rotation.z += 0.01;
        orbit2.rotation.z -= 0.01;

        const positions = particles.geometry.attributes.position.array;
        for (let i = 0; i < particleCount * 3; i += 3) {
            const radius = 2 + Math.sin(time + i) * 0.3;
            const theta = (time * 0.05 + i) % (Math.PI * 2);
            const phi = (time * 0.03 + i) % Math.PI;
            positions[i] = radius * Math.sin(phi) * Math.cos(theta);
            positions[i + 1] = radius * Math.sin(phi) * Math.sin(theta);
            positions[i + 2] = radius * Math.cos(phi);
        }
        particles.geometry.attributes.position.needsUpdate = true;

        time += 0.03;
        renderer.render(scene, camera);
    }
    animate();
    console.log("Animación Three.js iniciada");

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
                x: mouseY * 0.3,
                y: mouseX * 0.3,
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
                number: { value: 50, density: { enable: true, value_area: 1000 } }, // Menos partículas
                color: { value: '#00aaff' }, // Cian apagado
                shape: { type: 'circle' },
                opacity: { value: 0.4, random: true },
                size: { value: 1.5, random: true },
                line_linked: { 
                    enable: true, 
                    distance: 100, 
                    color: '#00aaff', 
                    opacity: 0.2, 
                    width: 0.5 
                },
                move: { 
                    enable: true, 
                    speed: 2, // Movimiento más lento
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
                    onclick: { enable: false },
                    resize: true
                },
                modes: {
                    repulse: { 
                        distance: 80,
                        duration: 0.4
                    }
                }
            },
            retina_detect: true
        });
        console.log("Particles.js inicializado con interacción al mouse (modo repulse)");
    } else {
        console.error("Contenedor #particles-js no encontrado");
    }
}