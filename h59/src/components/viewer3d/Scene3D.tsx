import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';
import { useAppStore } from '../../store/useAppStore';
import { valueToColor } from '../../utils/colorMap';
import type { SourceConfig, SubstrateConfig, OccluderConfig } from '../../types';
import { generateMotionPoses } from '../../engine/substrates';

interface SourceMeshProps {
  source: SourceConfig;
  index: number;
  isEmitting: boolean;
}

const SourceMesh: React.FC<SourceMeshProps> = ({ source, index, isEmitting }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const particlesRef = useRef<THREE.Points>(null);

  const color = useMemo(() => {
    const colors = ['#f97316', '#ef4444', '#8b5cf6', '#06b6d4', '#22c55e'];
    return colors[index % colors.length];
  }, [index]);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.01;
    }

    if (particlesRef.current && isEmitting) {
      const positions = particlesRef.current.geometry.attributes.position.array as Float32Array;
      for (let i = 0; i < positions.length; i += 3) {
        positions[i + 2] += 2;
        if (positions[i + 2] > 50) {
          positions[i] = (Math.random() - 0.5) * 20;
          positions[i + 1] = (Math.random() - 0.5) * 20;
          positions[i + 2] = 0;
        }
      }
      particlesRef.current.geometry.attributes.position.needsUpdate = true;
    }
  });

  const particlesGeometry = useMemo(() => {
    const positions = new Float32Array(100 * 3);
    for (let i = 0; i < 100; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 2] = Math.random() * 50;
    }
    return new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(positions, 3));
  }, []);

  const euler = new THREE.Euler(
    source.orientation.x,
    source.orientation.y,
    source.orientation.z,
    source.orientation.order as THREE.EulerOrder
  );

  const shape = useMemo(() => {
    switch (source.type) {
      case 'point':
        return <sphereGeometry args={[8, 16, 16]} />;
      case 'small_face':
        return <cylinderGeometry args={[0, 10, 15, 8]} />;
      case 'extended':
        return <boxGeometry args={[15, 8, 15]} />;
      default:
        return <sphereGeometry args={[8, 16, 16]} />;
    }
  }, [source.type]);

  return (
    <group position={[source.position.x, source.position.y, source.position.z]} rotation={euler}>
      <mesh ref={meshRef}>
        {shape}
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.5} />
      </mesh>
      {isEmitting && (
        <points ref={particlesRef} geometry={particlesGeometry}>
          <pointsMaterial color={color} size={1.5} transparent opacity={0.8} />
        </points>
      )}
    </group>
  );
};

interface SubstrateMeshProps {
  substrate: SubstrateConfig;
  thicknessData?: number[][];
}

const SubstrateMesh: React.FC<SubstrateMeshProps> = ({ substrate, thicknessData }) => {
  const meshRef = useRef<THREE.Mesh>(null);

  const geometry = useMemo(() => {
    if (substrate.type === 'stl' && substrate.stlData) {
      const geom = new THREE.BufferGeometry();
      geom.setAttribute('position', new THREE.BufferAttribute(substrate.stlData.vertices, 3));
      geom.setAttribute('normal', new THREE.BufferAttribute(substrate.stlData.normals, 3));
      geom.setIndex(new THREE.BufferAttribute(substrate.stlData.faces, 1));
      geom.computeVertexNormals();
      return geom;
    }

    const nx = substrate.resolution.x;
    const ny = substrate.resolution.y;
    const geom = new THREE.PlaneGeometry(
      substrate.size.width,
      substrate.size.height,
      nx - 1,
      ny - 1
    );

    if (substrate.type === 'sphere' || substrate.type === 'aspheric') {
      const positions = geom.attributes.position.array as Float32Array;
      const curvature = substrate.size.curvature || 0.01;
      const k = -1;

      for (let i = 0; i < positions.length; i += 3) {
        const x = positions[i];
        const y = positions[i + 1];
        const r2 = x * x + y * y;

        if (substrate.type === 'sphere') {
          const radius = substrate.size.radius || 100;
          positions[i + 2] = Math.sqrt(Math.max(0, radius * radius - r2)) - radius;
        } else {
          const sqrtTerm = Math.sqrt(Math.max(0, 1 - (1 + k) * curvature * curvature * r2));
          positions[i + 2] = (curvature * r2) / (1 + sqrtTerm);
        }
      }
      geom.attributes.position.needsUpdate = true;
      geom.computeVertexNormals();
    }

    return geom;
  }, [substrate]);

  const material = useMemo(() => {
    if (thicknessData && thicknessData.length > 0) {
      const nx = substrate.resolution.x;
      const ny = substrate.resolution.y;
      const colors = new Float32Array(nx * ny * 3);

      let maxT = -Infinity;
      let minT = Infinity;
      for (let j = 0; j < ny; j++) {
        for (let i = 0; i < nx; i++) {
          const t = thicknessData[j]?.[i] || 0;
          maxT = Math.max(maxT, t);
          minT = Math.min(minT, t);
        }
      }

      for (let j = 0; j < ny; j++) {
        for (let i = 0; i < nx; i++) {
          const idx = (j * nx + i) * 3;
          const t = thicknessData[j]?.[i] || 0;
          const color = new THREE.Color(valueToColor(t, minT, maxT, 'rainbow'));
          colors[idx] = color.r;
          colors[idx + 1] = color.g;
          colors[idx + 2] = color.b;
        }
      }

      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      return new THREE.MeshStandardMaterial({
        vertexColors: true,
        side: THREE.DoubleSide,
        roughness: 0.4,
        metalness: 0.1,
      });
    }

    return new THREE.MeshStandardMaterial({
      color: '#4a5568',
      side: THREE.DoubleSide,
      roughness: 0.4,
      metalness: 0.1,
      transparent: true,
      opacity: 0.9,
    });
  }, [thicknessData, substrate.resolution, geometry]);

  const groupRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);

  const motionPoses = useMemo(() => {
    if (substrate.motion?.enabled && substrate.motion.type !== 'none') {
      return generateMotionPoses(
        substrate.position,
        substrate.orientation,
        substrate.motion
      );
    }
    return null;
  }, [substrate.position, substrate.orientation, substrate.motion]);

  const euler = new THREE.Euler(
    substrate.orientation.x,
    substrate.orientation.y,
    substrate.orientation.z,
    substrate.orientation.order as THREE.EulerOrder
  );

  useFrame((state, delta) => {
    if (groupRef.current && motionPoses && motionPoses.length > 1) {
      timeRef.current += delta;
      const speedFactor = 0.5;
      const t = ((timeRef.current * speedFactor) % 1);
      const poseIndex = Math.floor(t * motionPoses.length);
      const nextPoseIndex = (poseIndex + 1) % motionPoses.length;
      const lerpT = (t * motionPoses.length) % 1;

      const pose = motionPoses[poseIndex];
      const nextPose = motionPoses[nextPoseIndex];

      groupRef.current.position.x = THREE.MathUtils.lerp(
        pose.position.x,
        nextPose.position.x,
        lerpT
      );
      groupRef.current.position.y = THREE.MathUtils.lerp(
        pose.position.y,
        nextPose.position.y,
        lerpT
      );
      groupRef.current.position.z = THREE.MathUtils.lerp(
        pose.position.z,
        nextPose.position.z,
        lerpT
      );

      const e1 = new THREE.Euler(
        pose.orientation.x,
        pose.orientation.y,
        pose.orientation.z,
        pose.orientation.order as THREE.EulerOrder
      );
      const e2 = new THREE.Euler(
        nextPose.orientation.x,
        nextPose.orientation.y,
        nextPose.orientation.z,
        nextPose.orientation.order as THREE.EulerOrder
      );

      const q1 = new THREE.Quaternion().setFromEuler(e1);
      const q2 = new THREE.Quaternion().setFromEuler(e2);
      const q = new THREE.Quaternion().slerpQuaternions(q1, q2, lerpT);

      groupRef.current.quaternion.copy(q);
    }
  });

  return (
    <group ref={groupRef}>
      <mesh
        ref={meshRef}
        geometry={geometry}
        material={material}
        position={motionPoses ? [0, 0, 0] : [substrate.position.x, substrate.position.y, substrate.position.z]}
        rotation={motionPoses ? undefined : euler}
      />
    </group>
  );
};

interface OccluderMeshProps {
  occluder: OccluderConfig;
  index: number;
}

const OccluderMesh: React.FC<OccluderMeshProps> = ({ occluder, index }) => {
  const meshRef = useRef<THREE.Mesh>(null);

  const geometry = useMemo(() => {
    switch (occluder.shape) {
      case 'box':
        return new THREE.BoxGeometry(
          occluder.size.width || 20,
          occluder.size.height || 20,
          occluder.size.depth || 20
        );
      case 'cylinder':
        return new THREE.CylinderGeometry(
          occluder.size.radius || 10,
          occluder.size.radius || 10,
          occluder.size.height || 20,
          16
        );
      case 'sphere':
        return new THREE.SphereGeometry(
          occluder.size.radius || 10,
          16,
          16
        );
    }
  }, [occluder.shape, occluder.size]);

  const euler = new THREE.Euler(
    occluder.orientation.x,
    occluder.orientation.y,
    occluder.orientation.z,
    occluder.orientation.order as THREE.EulerOrder
  );

  const color = useMemo(() => {
    const colors = ['#f59e0b', '#84cc16', '#ec4899', '#06b6d4', '#8b5cf6'];
    return colors[index % colors.length];
  }, [index]);

  const edgesGeometry = useMemo(() => {
    return new THREE.EdgesGeometry(geometry);
  }, [geometry]);

  return (
    <group position={[occluder.position.x, occluder.position.y, occluder.position.z]} rotation={euler}>
      <mesh ref={meshRef} geometry={geometry}>
        <meshStandardMaterial
          color={color}
          transparent
          opacity={0.6}
          side={THREE.DoubleSide}
          metalness={0.3}
          roughness={0.5}
        />
      </mesh>
      <lineSegments geometry={edgesGeometry}>
        <lineBasicMaterial color={color} transparent opacity={0.8} />
      </lineSegments>
    </group>
  );
};

export const Scene3D: React.FC = () => {
  const { sources, substrate, occluders, calculationResult, isCalculating, isOptimizing } = useAppStore();

  return (
    <div className="w-full h-full bg-[#0A1929]">
      <Canvas
        camera={{ position: [0, -400, 200], fov: 50 }}
        gl={{ antialias: true, alpha: false }}
      >
        <color attach="background" args={['#0A1929']} />
        <fog attach="fog" args={['#0A1929', 500, 1500]} />

        <ambientLight intensity={0.4} />
        <directionalLight position={[200, 200, 200]} intensity={1} color="#ffffff" />
        <directionalLight position={[-200, -100, 100]} intensity={0.5} color="#60a5fa" />

        <Grid
          position={[0, 0, -250]}
          rotation={[0, 0, 0]}
          args={[1000, 1000, 20, 20]}
          cellSize={50}
          cellThickness={0.5}
          cellColor="#1e3a5f"
          sectionSize={200}
          sectionThickness={1}
          sectionColor="#3b82f6"
          fadeDistance={1000}
          fadeStrength={1}
          followCamera={false}
        />

        <axesHelper args={[100]} />

        {sources.map((source, index) => (
          <SourceMesh
            key={source.id}
            source={source}
            index={index}
            isEmitting={isCalculating || isOptimizing}
          />
        ))}

        <SubstrateMesh
          substrate={substrate}
          thicknessData={calculationResult?.thicknessMatrix}
        />

        {occluders.map((occluder, index) => (
          <OccluderMesh
            key={occluder.id}
            occluder={occluder}
            index={index}
          />
        ))}

        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          minDistance={50}
          maxDistance={1500}
        />

        <EffectComposer>
          <Bloom luminanceThreshold={0.2} luminanceSmoothing={0.9} intensity={0.5} />
        </EffectComposer>
      </Canvas>
    </div>
  );
};
