import { useRef, useMemo, useEffect, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { createBridgeWithPillars } from '../../utils/objLoader';
import { BridgeParams } from '../../types/physics';

interface BridgePillarProps {
  params: BridgeParams;
  onMeshCreated?: (mesh: THREE.Mesh) => void;
}

export function BridgePillar({ params, onMeshCreated }: BridgePillarProps) {
  const groupRef = useRef<THREE.Group>(null);
  const [bridgeData, setBridgeData] = useState<{ group: THREE.Group; mesh: THREE.Mesh } | null>(null);

  useEffect(() => {
    const position = new THREE.Vector3(params.position.x, params.position.y, params.position.z);
    const scale = new THREE.Vector3(params.scale.x, params.scale.y, params.scale.z);
    const data = createBridgeWithPillars(position, scale);
    setBridgeData(data);

    if (onMeshCreated) {
      onMeshCreated(data.mesh);
    }
  }, [params, onMeshCreated]);

  const collisionMeshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (collisionMeshRef.current) {
      const time = state.clock.elapsedTime;
      if (collisionMeshRef.current.material instanceof THREE.MeshStandardMaterial) {
        collisionMeshRef.current.material.emissiveIntensity = 0.1 + Math.sin(time * 2) * 0.05;
      }
    }
  });

  if (!bridgeData) return null;

  return (
    <group>
      <primitive object={bridgeData.group} />
      <mesh ref={collisionMeshRef} visible={false} position={[params.position.x, params.position.y, params.position.z]} scale={[params.scale.x, params.scale.y, params.scale.z]}>
        <boxGeometry args={[22, 14, 6]} />
        <meshStandardMaterial color={0xff0000} emissive={0xff0000} emissiveIntensity={0.2} transparent opacity={0.3} />
      </mesh>
    </group>
  );
}
