import React, { useRef, useMemo, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import type { FieldDataPoint, DomainStructurePoint } from '../../types';
import { PHYSICAL_CONSTANTS } from '../../utils/physics';

interface CrystalProps {
  length: number;
  showDomainStructure: boolean;
  domainData: DomainStructurePoint[];
}

const Crystal: React.FC<CrystalProps> = ({
  length,
  showDomainStructure,
  domainData,
}) => {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const length_m = length * PHYSICAL_CONSTANTS.mm_to_m;
  const width = 0.5 * PHYSICAL_CONSTANTS.mm_to_m;
  const height = 0.3 * PHYSICAL_CONSTANTS.mm_to_m;

  const { domainMeshes } = useMemo(() => {
    const domainMeshes: { x: number; z: number; polarity: number; width: number; depth: number }[] = [];

    if (showDomainStructure && domainData.length > 0) {
      const xUnique = Array.from(new Set(domainData.map(d => Math.round(d.x * 1e12) / 1e12))).sort((a, b) => a - b);
      const zUnique = Array.from(new Set(domainData.map(d => Math.round(d.z * 1e12) / 1e12))).sort((a, b) => a - b);

      if (xUnique.length > 1 && zUnique.length > 1) {
        const dx = xUnique[1] - xUnique[0];
        const dz = zUnique[1] - zUnique[0];

        const gridData = new Map<string, number>();
        domainData.forEach((d) => {
          const xIdx = Math.round((d.x - xUnique[0]) / dx);
          const zIdx = Math.round((d.z - zUnique[0]) / dz);
          gridData.set(`${xIdx},${zIdx}`, d.polarity);
        });

        for (let xi = 0; xi < xUnique.length; xi++) {
          let zi = 0;
          while (zi < zUnique.length) {
            const currentPolarity = gridData.get(`${xi},${zi}`) || 1;
            let runLength = 1;

            while (zi + runLength < zUnique.length && gridData.get(`${xi},${zi + runLength}`) === currentPolarity) {
              runLength++;
            }

            const startZ = zUnique[zi] - dz / 2;
            const endZ = zi + runLength < zUnique.length
              ? zUnique[zi + runLength] - dz / 2
              : zUnique[zUnique.length - 1] + dz / 2;

            domainMeshes.push({
              x: xUnique[xi],
              z: (startZ + endZ) / 2,
              polarity: currentPolarity,
              width: dx * 0.95,
              depth: endZ - startZ,
            });

            zi += runLength;
          }
        }
      } else {
        domainData.forEach((d) => {
          domainMeshes.push({
            x: d.x,
            z: d.z,
            polarity: d.polarity,
            width: width / 20,
            depth: length_m / 200,
          });
        });
      }
    }

    return { domainMeshes };
  }, [domainData, showDomainStructure, width, length_m]);

  if (showDomainStructure && domainMeshes.length > 0) {
    return (
      <group>
        {domainMeshes.map((mesh, idx) => (
          <mesh
            key={idx}
            position={[mesh.x, 0, mesh.z]}
          >
            <boxGeometry args={[mesh.width, height, mesh.depth]} />
            <meshStandardMaterial
              color={mesh.polarity > 0 ? '#00d4ff' : '#ff6b35'}
              transparent
              opacity={0.8}
              roughness={0.3}
              metalness={0.1}
            />
          </mesh>
        ))}
        <mesh position={[0, 0, length_m / 2]}>
          <boxGeometry args={[width * 1.02, height * 1.02, length_m * 1.02]} />
          <meshStandardMaterial
            color="#1e3a5f"
            transparent
            opacity={0.15}
            roughness={0.1}
            metalness={0.9}
          />
        </mesh>
      </group>
    );
  }

  return (
    <mesh>
      <boxGeometry args={[width, height, length_m]} />
      <meshStandardMaterial
        color="#1e3a5f"
        transparent
        opacity={0.3}
        roughness={0.1}
        metalness={0.9}
      />
    </mesh>
  );
};

interface FieldParticlesProps {
  fieldData: FieldDataPoint[];
  time: number;
}

const FieldParticles: React.FC<FieldParticlesProps> = ({ fieldData, time }) => {
  const pointsRef = useRef<THREE.Points>(null);

  const { positions, colors, sizes } = useMemo(() => {
    const positions: number[] = [];
    const colors: number[] = [];
    const sizes: number[] = [];

    if (fieldData.length === 0) {
      return { positions, colors, sizes };
    }

    const maxAmplitude = Math.max(...fieldData.map((d) => d.amplitude));

    fieldData.forEach((d) => {
      positions.push(d.x, d.y, d.z);

      const normalizedAmp = maxAmplitude > 0 ? d.amplitude / maxAmplitude : 0;
      const hue = 0.5 - normalizedAmp * 0.3;
      const color = new THREE.Color().setHSL(hue, 1, 0.5 + normalizedAmp * 0.3);
      colors.push(color.r, color.g, color.b);

      sizes.push(0.5 + normalizedAmp * 2);
    });

    return { positions, colors, sizes };
  }, [fieldData]);

  useFrame(() => {
    if (!pointsRef.current) return;
    const geometry = pointsRef.current.geometry as THREE.BufferGeometry;
    const positionAttr = geometry.getAttribute('position') as THREE.BufferAttribute;
    const colorAttr = geometry.getAttribute('color') as THREE.BufferAttribute;

    for (let i = 0; i < fieldData.length; i++) {
      const d = fieldData[i];
      const phase = d.phase + time * 2;
      const amplitude = d.amplitude * (0.8 + 0.2 * Math.sin(phase));

      const yOffset = amplitude * Math.sin(phase) * 0.1;
      positionAttr.setY(i, d.y + yOffset);

      const maxAmplitude = Math.max(...fieldData.map((fd) => fd.amplitude));
      const normalizedAmp = maxAmplitude > 0 ? amplitude / maxAmplitude : 0;
      const hue = 0.5 - normalizedAmp * 0.3;
      const color = new THREE.Color().setHSL(hue, 1, 0.5 + normalizedAmp * 0.3);
      colorAttr.setXYZ(i, color.r, color.g, color.b);
    }

    positionAttr.needsUpdate = true;
    colorAttr.needsUpdate = true;
  });

  if (fieldData.length === 0) return null;

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(positions, 3)
  );
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geometry.setAttribute('size', new THREE.Float32BufferAttribute(sizes, 1));

  return (
    <points ref={pointsRef} geometry={geometry}>
      <pointsMaterial
        size={0.0002}
        vertexColors
        transparent
        opacity={0.8}
        sizeAttenuation
      />
    </points>
  );
};

interface LaserBeamProps {
  length: number;
  color: string;
  startZ: number;
  endZ: number;
}

const LaserBeam: React.FC<LaserBeamProps> = ({ length, color, startZ, endZ }) => {
  const length_m = length * PHYSICAL_CONSTANTS.mm_to_m;

  const points = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    const steps = 100;
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      const z = startZ + t * (endZ - startZ);
      const waist = 50 * PHYSICAL_CONSTANTS.um_to_m;
      const zR = (Math.PI * waist * waist * 2.2) / (1064 * PHYSICAL_CONSTANTS.nm_to_m);
      const currentWaist = waist * Math.sqrt(1 + Math.pow((z - length_m / 2) / zR, 2));
      pts.push(new THREE.Vector3(0, 0, z));
    }
    return pts;
  }, [startZ, endZ, length]);

  const curve = new THREE.CatmullRomCurve3(points);

  return (
    <mesh>
      <tubeGeometry args={[curve, 100, 0.00005, 8, false]} />
      <meshBasicMaterial color={color} transparent opacity={0.6} />
    </mesh>
  );
};

interface GridFloorProps {
  length: number;
}

const GridFloor: React.FC<GridFloorProps> = ({ length }) => {
  const length_m = length * PHYSICAL_CONSTANTS.mm_to_m;
  return (
    <gridHelper
      args={[length_m * 1.5, 20, '#1e3a5f', '#0f1e2f']}
      position={[0, -0.0005, length_m / 2]}
    />
  );
};

interface FieldVisualizationProps {
  fieldData: FieldDataPoint[];
  domainData: DomainStructurePoint[];
  crystalLength: number;
  showDomainStructure: boolean;
  showField: boolean;
  showLaserBeam: boolean;
}

export const FieldVisualization: React.FC<FieldVisualizationProps> = ({
  fieldData,
  domainData,
  crystalLength,
  showDomainStructure = true,
  showField = true,
  showLaserBeam = true,
}) => {
  const length_m = crystalLength * PHYSICAL_CONSTANTS.mm_to_m;

  return (
    <div className="w-full h-full rounded-lg overflow-hidden" style={{ background: '#050a14' }}>
      <Canvas dpr={[1, 2]}>
        <PerspectiveCamera
          makeDefault
          position={[length_m * 0.8, length_m * 0.5, length_m * 1.2]}
          fov={50}
        />
        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          minDistance={0.001}
          maxDistance={0.1}
        />

        <ambientLight intensity={0.3} />
        <pointLight position={[0.01, 0.01, 0.01]} intensity={1} color="#00d4ff" />
        <pointLight position={[-0.01, 0.01, 0.05]} intensity={0.5} color="#ff6b35" />
        <directionalLight position={[0, 0.02, 0]} intensity={0.3} />

        <fog attach="fog" args={['#050a14', 0.005, 0.1]} />

        <Crystal
          length={crystalLength}
          showDomainStructure={showDomainStructure}
          domainData={domainData}
        />

        {showField && <FieldParticles fieldData={fieldData} time={0} />}

        {showLaserBeam && (
          <>
            <LaserBeam
              length={crystalLength}
              color="#00d4ff"
              startZ={-length_m * 0.2}
              endZ={length_m * 1.2}
            />
          </>
        )}

        <GridFloor length={crystalLength} />

        <axesHelper args={[length_m * 0.1]} position={[0, 0.001, 0]} />
      </Canvas>
    </div>
  );
};

interface DomainStructure2DProps {
  data: DomainStructurePoint[];
  crystalLength: number;
}

export const DomainStructure2D: React.FC<DomainStructure2DProps> = ({
  data,
  crystalLength,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;

    ctx.fillStyle = '#050a14';
    ctx.fillRect(0, 0, width, height);

    if (data.length === 0) {
      ctx.fillStyle = '#e2e8f0';
      ctx.font = '14px Inter';
      ctx.textAlign = 'center';
      ctx.fillText('暂无畴结构数据，请先生成', width / 2, height / 2);
      return;
    }

    const padding = { top: 30, right: 20, bottom: 40, left: 60 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;

    const length_m = crystalLength * PHYSICAL_CONSTANTS.mm_to_m;

    const xUnique = Array.from(new Set(data.map(d => Math.round(d.x * 1e12) / 1e12))).sort((a, b) => a - b);
    const zUnique = Array.from(new Set(data.map(d => Math.round(d.z * 1e12) / 1e12))).sort((a, b) => a - b);

    const xMin = Math.min(...xUnique);
    const xMax = Math.max(...xUnique);
    const zMin = 0;
    const zMax = length_m;

    const gridData = new Map<string, number>();
    let dx = 1, dz = 1;

    if (xUnique.length > 1 && zUnique.length > 1) {
      dx = xUnique[1] - xUnique[0];
      dz = zUnique[1] - zUnique[0];

      data.forEach((d) => {
        const xIdx = Math.round((d.x - xUnique[0]) / dx);
        const zIdx = Math.round((d.z - zUnique[0]) / dz);
        gridData.set(`${xIdx},${zIdx}`, d.polarity);
      });
    }

    if (gridData.size > 0) {
      const cellWidthPx = plotWidth / xUnique.length * 0.98;
      const cellHeightPx = plotHeight / zUnique.length * 0.98;

      for (let xi = 0; xi < xUnique.length; xi++) {
        let zi = 0;
        while (zi < zUnique.length) {
          const currentPolarity = gridData.get(`${xi},${zi}`) || 1;
          let runLength = 1;

          while (zi + runLength < zUnique.length && gridData.get(`${xi},${zi + runLength}`) === currentPolarity) {
            runLength++;
          }

          const x = xUnique[xi];
          const zStart = zUnique[zi];
          const zEnd = zi + runLength < zUnique.length
            ? zUnique[zi + runLength]
            : zUnique[zUnique.length - 1] + dz;

          const px = padding.left + ((x - xMin) / (xMax - xMin || 1)) * plotWidth;
          const pzStart = padding.top + (1 - (zStart - zMin) / (zMax - zMin || 1)) * plotHeight;
          const pzEnd = padding.top + (1 - (zEnd - zMin) / (zMax - zMin || 1)) * plotHeight;

          const w = cellWidthPx;
          const h = Math.max(1, pzEnd - pzStart);

          ctx.fillStyle = currentPolarity > 0 ? '#00d4ff' : '#ff6b35';
          ctx.fillRect(px - w / 2, pzStart, w, h);

          zi += runLength;
        }
      }
    } else {
      const uniquePoints = new Map<string, number>();
      data.forEach((d) => {
        const key = `${Math.round(d.x * 1e12)},${Math.round(d.z * 1e12)}`;
        if (!uniquePoints.has(key)) {
          uniquePoints.set(key, d.polarity);
        }
      });

      uniquePoints.forEach((polarity, key) => {
        const [x, z] = key.split(',').map(Number).map(v => v / 1e12);
        const px = padding.left + ((x - xMin) / (xMax - xMin || 1)) * plotWidth;
        const pz = padding.top + (1 - (z - zMin) / (zMax - zMin || 1)) * plotHeight;

        const w = Math.max(2, plotWidth / Math.sqrt(uniquePoints.size) * 0.9);
        const h = Math.max(2, plotHeight / Math.sqrt(uniquePoints.size) * 0.9);

        ctx.fillStyle = polarity > 0 ? '#00d4ff' : '#ff6b35';
        ctx.fillRect(px - w / 2, pz - h / 2, w, h);
      });
    }

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 1;

    for (let i = 0; i <= 5; i++) {
      const z = padding.top + (i / 5) * plotHeight;
      ctx.beginPath();
      ctx.moveTo(padding.left, z);
      ctx.lineTo(padding.left + plotWidth, z);
      ctx.stroke();

      const zValue = (1 - i / 5) * crystalLength;
      ctx.fillStyle = '#e2e8f0';
      ctx.font = '10px JetBrains Mono';
      ctx.textAlign = 'right';
      ctx.fillText(zValue.toFixed(1), padding.left - 5, z + 3);
    }

    ctx.fillStyle = '#e2e8f0';
    ctx.font = 'bold 14px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('周期极化畴结构', width / 2, 20);

    ctx.font = '12px Inter';
    ctx.fillText('传播方向 z (mm)', width / 2, height - 10);

    ctx.save();
    ctx.translate(15, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('横向 x', 0, 0);
    ctx.restore();

    const legendY = 50;
    ctx.fillStyle = '#00d4ff';
    ctx.fillRect(width - 100, legendY, 15, 15);
    ctx.fillStyle = '#e2e8f0';
    ctx.font = '11px Inter';
    ctx.textAlign = 'left';
    ctx.fillText('+z 方向', width - 80, legendY + 12);

    ctx.fillStyle = '#ff6b35';
    ctx.fillRect(width - 100, legendY + 25, 15, 15);
    ctx.fillStyle = '#e2e8f0';
    ctx.fillText('-z 方向', width - 80, legendY + 37);
  }, [data, crystalLength]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full rounded-lg"
      style={{ background: '#050a14' }}
    />
  );
};
