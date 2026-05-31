import { useMemo, useRef, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { generateRiverBedTerrain, TerrainGenerateParams } from '../../utils/terrainGenerator';

interface TerrainProps {
  params: TerrainGenerateParams;
  onTerrainGenerated?: (heights: number[][]) => void;
}

export function Terrain({ params, onTerrainGenerated }: TerrainProps) {
  const meshRef = useRef<THREE.Mesh>(null);

  const { geometry, heights } = useMemo(() => {
    const terrainData = generateRiverBedTerrain(params);

    const { resolution, width, depth } = params;
    const geo = new THREE.PlaneGeometry(width, depth, resolution - 1, resolution - 1);
    geo.rotateX(-Math.PI / 2);

    const positions = geo.attributes.position;
    for (let i = 0; i < positions.count; i++) {
      const ix = i % resolution;
      const iz = Math.floor(i / resolution);
      const h = terrainData.heights[ix][iz];
      positions.setY(i, h);
    }

    geo.computeVertexNormals();
    geo.attributes.position.needsUpdate = true;

    return { geometry: geo, heights: terrainData.heights };
  }, [params]);

  useEffect(() => {
    if (onTerrainGenerated && heights) {
      onTerrainGenerated(heights);
    }
  }, [heights, onTerrainGenerated]);

  const material = useMemo(() => {
    const mat = new THREE.MeshStandardMaterial({
      vertexColors: false,
      color: 0x5d4e37,
      roughness: 0.9,
      metalness: 0.1,
      flatShading: false
    });
    return mat;
  }, []);

  useFrame((state) => {
    if (meshRef.current && meshRef.current.material instanceof THREE.MeshStandardMaterial) {
      const time = state.clock.elapsedTime;
      meshRef.current.material.emissiveIntensity = 0.05 + Math.sin(time * 0.5) * 0.02;
    }
  });

  return (
    <mesh ref={meshRef} geometry={geometry} material={material} receiveShadow>
    </mesh>
  );
}
