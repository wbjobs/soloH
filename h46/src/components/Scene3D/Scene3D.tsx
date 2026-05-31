import { useRef, useEffect, useCallback } from 'react';
import { Canvas, useThree, useFrame } from '@react-three/fiber';
import { OrbitControls, Stars, Environment } from '@react-three/drei';
import { EffectComposer, Bloom, FXAA } from '@react-three/postprocessing';
import * as THREE from 'three';
import { Particles } from './Particles';
import { Terrain } from './Terrain';
import { BridgePillar } from './BridgePillar';
import { useSimulationStore } from '../../store/useSimulationStore';
import { useParameterStore } from '../../store/useParameterStore';
import { Particle } from '../../types/physics';
import { generateFileName } from '../../utils/csvExporter';
import { VideoRecorder } from '../../utils/videoRecorder';

interface Scene3DProps {
  onCanvasReady?: (canvas: HTMLCanvasElement) => void;
}

function Lighting() {
  return (
    <>
      <ambientLight intensity={0.3} color={0x404060} />
      <hemisphereLight args={[0x87ceeb, 0x1a1a2e, 0.4]} />
      <directionalLight
        position={[30, 50, 30]}
        intensity={1.2}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-far={200}
        shadow-camera-left={-60}
        shadow-camera-right={60}
        shadow-camera-top={60}
        shadow-camera-bottom={-60}
      >
        <orthographicCamera attach="shadow-camera" args={[-60, 60, 60, -60]} />
      </directionalLight>
      <pointLight position={[-20, 20, -20]} intensity={0.3} color={0x4ecdc4} />
      <pointLight position={[20, 10, 20]} intensity={0.2} color={0xff6b35} />
    </>
  );
}

function SimulationLoop() {
  const { step, updateFPS, isRunning, isPaused } = useSimulationStore();
  const lastTimeRef = useRef(0);
  const frameCountRef = useRef(0);
  const fpsTimeRef = useRef(0);

  useFrame((state, delta) => {
    if (!isRunning || isPaused) return;

    const dt = Math.min(delta, 0.016);
    step(dt);

    frameCountRef.current++;
    fpsTimeRef.current += delta;
    
    if (fpsTimeRef.current >= 0.5) {
      const fps = frameCountRef.current / fpsTimeRef.current;
      updateFPS(Math.round(fps));
      frameCountRef.current = 0;
      fpsTimeRef.current = 0;
    }
  });

  return null;
}

function SceneContent({ onBridgeMesh, onTerrainHeights }: {
  onBridgeMesh: (mesh: THREE.Mesh) => void;
  onTerrainHeights: (heights: number[][]) => void;
}) {
  const { particles } = useSimulationStore();
  const { sphParams, terrainParams, bridgeParams } = useParameterStore();

  const handleBridgeMeshCreated = useCallback((mesh: THREE.Mesh) => {
    onBridgeMesh(mesh);
  }, [onBridgeMesh]);

  const handleTerrainGenerated = useCallback((heights: number[][]) => {
    onTerrainHeights(heights);
  }, [onTerrainHeights]);

  return (
    <>
      <Lighting />
      <Terrain params={terrainParams} onTerrainGenerated={handleTerrainGenerated} />
      <BridgePillar params={bridgeParams} onMeshCreated={handleBridgeMeshCreated} />
      <Particles 
        particles={particles} 
        particleRadius={sphParams.particleRadius}
        showVelocityColor={true}
      />
      <Stars radius={300} depth={60} count={5000} factor={4} fade speed={0.5} />
      <EffectComposer>
        <Bloom luminanceThreshold={0.2} luminanceSmoothing={0.9} intensity={1.5} mipmapBlur />
        <FXAA />
      </EffectComposer>
    </>
  );
}

export function Scene3D({ onCanvasReady }: Scene3DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { getEngine } = useSimulationStore();
  const { setBridgeMesh, setTerrainHeights } = useParameterStore();

  const handleBridgeMesh = useCallback((mesh: THREE.Mesh) => {
    const engine = getEngine();
    if (engine) {
      engine.setBridgeMesh(mesh);
    }
    setBridgeMesh(mesh);
  }, [getEngine, setBridgeMesh]);

  const handleTerrainHeights = useCallback((heights: number[][]) => {
    const engine = getEngine();
    if (engine) {
      engine.setTerrain(heights, {
        width: 80,
        depth: 100,
        resolution: 128
      });
    }
    setTerrainHeights(heights);
  }, [getEngine, setTerrainHeights]);

  useEffect(() => {
    if (canvasRef.current && onCanvasReady) {
      onCanvasReady(canvasRef.current);
    }
  }, [onCanvasReady]);

  return (
    <Canvas
      ref={canvasRef}
      shadows
      camera={{ position: [0, 25, 40], fov: 60, near: 0.1, far: 1000 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      onCreated={({ gl, scene }) => {
        gl.setClearColor(0x0a192f);
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.2;
        scene.fog = new THREE.FogExp2(0x0a192f, 0.008);
      }}
    >
      <SimulationLoop />
      <SceneContent 
        onBridgeMesh={handleBridgeMesh} 
        onTerrainHeights={handleTerrainHeights}
      />
      <OrbitControls
        enableDamping
        dampingFactor={0.05}
        minDistance={10}
        maxDistance={150}
        maxPolarAngle={Math.PI / 2.1}
      />
    </Canvas>
  );
}
