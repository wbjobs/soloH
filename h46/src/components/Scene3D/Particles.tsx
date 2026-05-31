import { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { Particle } from '../../types/physics';
import { VelocityColorMap } from '../../utils/colorMapping';
import { vecLength } from '../../types/physics';

interface ParticlesProps {
  particles: Particle[];
  particleRadius: number;
  showVelocityColor?: boolean;
  colorMode?: 'velocity' | 'grainType';
}

export function Particles({ particles, particleRadius, showVelocityColor = true, colorMode = 'velocity' }: ParticlesProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const colorMap = useMemo(() => new VelocityColorMap(0, 15), []);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const tempColor = useMemo(() => new THREE.Color(), []);

  const particleCount = particles.length;
  const maxParticles = 5000;

  const geometry = useMemo(() => {
    const geo = new THREE.IcosahedronGeometry(1, 1);
    return geo;
  }, []);

  const material = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      metalness: 0.1,
      roughness: 0.5,
      emissive: new THREE.Color(0x1e3a5f),
      emissiveIntensity: 0.2
    });
  }, []);

  useEffect(() => {
    if (meshRef.current) {
      meshRef.current.count = Math.min(particleCount, maxParticles);
    }
  }, [particleCount, maxParticles]);

  useFrame(() => {
    if (!meshRef.current) return;

    const mesh = meshRef.current;
    const count = Math.min(particles.length, maxParticles);

    for (let i = 0; i < count; i++) {
      const particle = particles[i];
      if (!particle || !particle.isActive) continue;

      dummy.position.set(
        particle.position.x,
        particle.position.y,
        particle.position.z
      );
      
      const displayRadius = particle.grainRadius || particleRadius;
      dummy.scale.setScalar(displayRadius);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);

      if (colorMode === 'grainType') {
        if (particle.grainType === 'coarse') {
          tempColor.setHex(0xff6b35);
        } else {
          tempColor.setHex(0x4ecdc4);
        }
        mesh.setColorAt(i, tempColor);
      } else if (showVelocityColor) {
        const speed = vecLength(particle.velocity);
        const color = colorMap.getColor(speed);
        mesh.setColorAt(i, color);
      } else {
        tempColor.setHex(0x4ecdc4);
        mesh.setColorAt(i, tempColor);
      }
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) {
      mesh.instanceColor.needsUpdate = true;
    }
  });

  return (
    <instancedMesh
      ref={meshRef}
      args={[geometry, material, maxParticles]}
      castShadow
      receiveShadow
    />
  );
}
