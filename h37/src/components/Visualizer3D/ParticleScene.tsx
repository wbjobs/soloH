import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { useAudioStore } from '../../store/useAudioStore';

const PARTICLE_COUNT = 3000;

export const ParticleScene = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const particlesRef = useRef<THREE.Points | null>(null);
  const starsRef = useRef<THREE.Points | null>(null);
  const composerRef = useRef<EffectComposer | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const timeRef = useRef(0);
  const originalPositionsRef = useRef<Float32Array | null>(null);
  const bloomPassRef = useRef<UnrealBloomPass | null>(null);
  const lightsRef = useRef<THREE.PointLight[]>([]);
  const isMountedRef = useRef(false);

  const { frequencyData, averageAmplitude, beatFrequency, currentBand, isPlaying } = useAudioStore();

  useEffect(() => {
    if (!containerRef.current || isMountedRef.current) return;
    isMountedRef.current = true;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0e1a);
    scene.fog = new THREE.FogExp2(0x0a0e1a, 0.02);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(
      75,
      containerRef.current.clientWidth / containerRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.z = 15;
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const composer = new EffectComposer(renderer);
    const renderPass = new RenderPass(scene, camera);
    composer.addPass(renderPass);

    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(containerRef.current.clientWidth, containerRef.current.clientHeight),
      1.5,
      0.4,
      0.85
    );
    composer.addPass(bloomPass);
    composerRef.current = composer;
    bloomPassRef.current = bloomPass;

    const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
    scene.add(ambientLight);

    const pointLight1 = new THREE.PointLight(0x6366f1, 2, 50);
    pointLight1.position.set(10, 10, 10);
    scene.add(pointLight1);

    const pointLight2 = new THREE.PointLight(0x3b82f6, 2, 50);
    pointLight2.position.set(-10, -10, 10);
    scene.add(pointLight2);

    const pointLight3 = new THREE.PointLight(0x10b981, 1.5, 50);
    pointLight3.position.set(0, 10, -10);
    scene.add(pointLight3);

    lightsRef.current = [pointLight1, pointLight2, pointLight3];

    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(PARTICLE_COUNT * 3);
    const colors = new Float32Array(PARTICLE_COUNT * 3);
    const sizes = new Float32Array(PARTICLE_COUNT);
    const originalPositions = new Float32Array(PARTICLE_COUNT * 3);
    originalPositionsRef.current = originalPositions;

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;
      const radius = Math.random() * 10 + 2;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.random() * Math.PI;

      positions[i3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i3 + 2] = radius * Math.cos(phi);

      originalPositions[i3] = positions[i3];
      originalPositions[i3 + 1] = positions[i3 + 1];
      originalPositions[i3 + 2] = positions[i3 + 2];

      const color = new THREE.Color();
      color.setHSL(0.6 + Math.random() * 0.2, 0.8, 0.5 + Math.random() * 0.3);
      colors[i3] = color.r;
      colors[i3 + 1] = color.g;
      colors[i3 + 2] = color.b;

      sizes[i] = Math.random() * 2 + 0.5;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    const material = new THREE.PointsMaterial({
      size: 0.1,
      vertexColors: true,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true
    });

    const particles = new THREE.Points(geometry, material);
    scene.add(particles);
    particlesRef.current = particles;

    const starGeometry = new THREE.BufferGeometry();
    const starPositions = new Float32Array(2000 * 3);
    for (let i = 0; i < 2000; i++) {
      const i3 = i * 3;
      starPositions[i3] = (Math.random() - 0.5) * 200;
      starPositions[i3 + 1] = (Math.random() - 0.5) * 200;
      starPositions[i3 + 2] = (Math.random() - 0.5) * 200;
    }
    starGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    const starMaterial = new THREE.PointsMaterial({
      size: 0.05,
      color: 0xffffff,
      transparent: true,
      opacity: 0.6
    });
    const stars = new THREE.Points(starGeometry, starMaterial);
    scene.add(stars);
    starsRef.current = stars;

    const handleResize = () => {
      if (!containerRef.current || !camera || !renderer || !composer) return;
      camera.aspect = containerRef.current.clientWidth / containerRef.current.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
      composer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
      bloomPass.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    const bandColorRef = { current: new THREE.Color(currentBand.color) };

    const animate = () => {
      if (!isMountedRef.current) return;
      animationFrameRef.current = requestAnimationFrame(animate);
      timeRef.current += 0.016;

      const particles = particlesRef.current;
      const stars = starsRef.current;
      const originalPositions = originalPositionsRef.current;
      const bloomPass = bloomPassRef.current;
      const lights = lightsRef.current;

      if (!particles || !originalPositions || !bloomPass || !stars || !camera) return;

      const positions = particles.geometry.attributes.position.array as Float32Array;
      const colors = particles.geometry.attributes.color.array as Float32Array;
      const sizes = particles.geometry.attributes.size.array as Float32Array;

      const bandColor = bandColorRef.current;
      const amp = isPlaying ? averageAmplitude : 0;
      const beatSpeed = beatFrequency * 0.1;

      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const i3 = i * 3;

        const freqIndex = Math.floor((i / PARTICLE_COUNT) * frequencyData.length);
        const freqValue = isPlaying ? frequencyData[freqIndex] / 255 : 0;

        const noiseX = Math.sin(timeRef.current * beatSpeed + i * 0.1) * 0.5;
        const noiseY = Math.cos(timeRef.current * beatSpeed * 0.7 + i * 0.15) * 0.5;
        const noiseZ = Math.sin(timeRef.current * beatSpeed * 0.5 + i * 0.2) * 0.5;

        const displacement = 1 + freqValue * 3 + amp * 2;

        positions[i3] = originalPositions[i3] * displacement + noiseX * freqValue * 2;
        positions[i3 + 1] = originalPositions[i3 + 1] * displacement + noiseY * freqValue * 2;
        positions[i3 + 2] = originalPositions[i3 + 2] * displacement + noiseZ * freqValue * 2;

        const colorMix = Math.min(1, freqValue + amp * 0.5);
        colors[i3] = bandColor.r * colorMix + (1 - colorMix) * 0.4;
        colors[i3 + 1] = bandColor.g * colorMix + (1 - colorMix) * 0.4;
        colors[i3 + 2] = bandColor.b * colorMix + (1 - colorMix) * 0.8;

        sizes[i] = (0.5 + freqValue * 2 + amp) * 0.1;
      }

      particles.geometry.attributes.position.needsUpdate = true;
      particles.geometry.attributes.color.needsUpdate = true;
      particles.geometry.attributes.size.needsUpdate = true;

      particles.rotation.y += 0.002 + amp * 0.01;
      particles.rotation.x += 0.001 + amp * 0.005;
      stars.rotation.y += 0.0005;

      camera.position.x = Math.sin(timeRef.current * 0.1) * 2;
      camera.position.y = Math.cos(timeRef.current * 0.15) * 1;
      camera.lookAt(0, 0, 0);

      const lightIntensity = 1 + amp * 3;
      if (lights.length === 3) {
        lights[0].intensity = lightIntensity;
        lights[1].intensity = lightIntensity;
        lights[2].intensity = lightIntensity * 0.8;

        lights[0].color = bandColor;
        lights[1].color = new THREE.Color(bandColor).offsetHSL(0.1, 0, 0);
        lights[2].color = new THREE.Color(bandColor).offsetHSL(-0.1, 0, 0);
      }

      bloomPass.strength = 1 + amp * 2;

      composer.render();
    };
    animate();

    const updateBandColor = () => {
      bandColorRef.current = new THREE.Color(currentBand.color);
      if (particlesRef.current) {
        const colors = particlesRef.current.geometry.attributes.color.array as Float32Array;
        const bandColor = bandColorRef.current;
        for (let i = 0; i < PARTICLE_COUNT; i++) {
          const i3 = i * 3;
          colors[i3] = bandColor.r * 0.4 + 0.2;
          colors[i3 + 1] = bandColor.g * 0.4 + 0.2;
          colors[i3 + 2] = bandColor.b * 0.4 + 0.5;
        }
        particlesRef.current.geometry.attributes.color.needsUpdate = true;
      }
    };

    let lastBandId = currentBand.id;
    const checkBandChange = () => {
      const state = useAudioStore.getState();
      if (state.currentBand.id !== lastBandId) {
        lastBandId = state.currentBand.id;
        updateBandColor();
      }
    };
    const bandCheckInterval = setInterval(checkBandChange, 100);

    return () => {
      isMountedRef.current = false;
      clearInterval(bandCheckInterval);

      window.removeEventListener('resize', handleResize);

      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }

      if (containerRef.current && renderer.domElement) {
        containerRef.current.removeChild(renderer.domElement);
      }

      geometry.dispose();
      material.dispose();
      starGeometry.dispose();
      starMaterial.dispose();

      if (composer) {
        composer.dispose();
      }

      renderer.dispose();

      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry?.dispose();
          if (Array.isArray(object.material)) {
            object.material.forEach((m) => m.dispose());
          } else {
            object.material?.dispose();
          }
        }
      });

      sceneRef.current = null;
      cameraRef.current = null;
      rendererRef.current = null;
      particlesRef.current = null;
      starsRef.current = null;
      composerRef.current = null;
      bloomPassRef.current = null;
      lightsRef.current = [];
      originalPositionsRef.current = null;
    };
  }, []);

  return <div ref={containerRef} className="w-full h-full" />;
};
