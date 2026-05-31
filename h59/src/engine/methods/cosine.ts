import type { SourceConfig, SubstrateConfig, CalculationResult, OccluderConfig, Euler, Vector3 } from '../../types';
import { generateSubstratePoints, generateMotionPoses, type SubstratePoint } from '../substrates';
import { getCosineLawThickness } from '../sources';
import { checkOcclusion } from '../occlusion';
import { eulerRotate } from '../math/vector';

const eulerRotateLocal = (v: Vector3, euler: Euler): Vector3 => eulerRotate(v, euler);

export const calculateThicknessCosine = (
  sources: SourceConfig[],
  substrate: SubstrateConfig,
  occluders: OccluderConfig[],
  onProgress?: (progress: number, message: string) => void
): CalculationResult => {
  const nx = substrate.resolution.x;
  const ny = substrate.resolution.y;

  const motionPoses = generateMotionPoses(
    substrate.position,
    substrate.orientation,
    substrate.motion
  );

  const basePoints = generateSubstratePoints({
    ...substrate,
    position: { x: 0, y: 0, z: 0 },
    orientation: { x: 0, y: 0, z: 0, order: 'XYZ' },
  });

  const nPoints = basePoints.length;
  const nPoses = motionPoses.length;

  const thickness = new Float64Array(nPoints);
  const xCoords = new Float64Array(nx);
  const yCoords = new Float64Array(ny);

  for (let i = 0; i < nx; i++) {
    xCoords[i] = ((i / (nx - 1)) * 2 - 1) * (substrate.size.width / 2);
  }
  for (let j = 0; j < ny; j++) {
    yCoords[j] = ((j / (ny - 1)) * 2 - 1) * (substrate.size.height / 2);
  }

  const totalWork = nPoints * sources.length * nPoses;
  let currentWork = 0;
  const progressInterval = Math.max(1, Math.floor(totalWork / 100));

  for (let poseIdx = 0; poseIdx < nPoses; poseIdx++) {
    const pose = motionPoses[poseIdx];
    const poseWeight = 1 / nPoses;

    const transformedPoints = basePoints.map((bp) => {
      const rotatedPos = eulerRotateLocal(bp.position, pose.orientation);
      const rotatedNormal = eulerRotateLocal(bp.normal, pose.orientation);
      const worldPos = {
        x: pose.position.x + rotatedPos.x,
        y: pose.position.y + rotatedPos.y,
        z: pose.position.z + rotatedPos.z,
      };
      return {
        position: worldPos,
        normal: rotatedNormal,
        uv: bp.uv,
      };
    });

    transformedPoints.forEach((point: SubstratePoint, idx: number) => {
      let poseThickness = 0;

      sources.forEach((source) => {
        const isOccluded = occluders.length > 0 && checkOcclusion(
          source.position,
          point.position,
          occluders
        );

        if (!isOccluded) {
          const sourceThickness = getCosineLawThickness(
            source,
            source.position,
            point.position,
            point.normal
          );
          poseThickness += sourceThickness * poseWeight;
        }

        currentWork++;
        if (currentWork % progressInterval === 0 && onProgress) {
          const progress = (currentWork / totalWork) * 100;
          const poseInfo = nPoses > 1 ? ` (姿态 ${poseIdx + 1}/${nPoses})` : '';
          onProgress(progress, `计算膜厚分布... ${progress.toFixed(0)}%${poseInfo}`);
        }
      });

      thickness[idx] += poseThickness;
    });
  }

  let maxThickness = -Infinity;
  let minThickness = Infinity;
  let sumThickness = 0;

  for (let i = 0; i < nPoints; i++) {
    const t = thickness[i];
    maxThickness = Math.max(maxThickness, t);
    minThickness = Math.min(minThickness, t);
    sumThickness += t;
  }

  const avgThickness = sumThickness / nPoints;
  const uniformity = maxThickness > 0 
    ? (1 - (maxThickness - minThickness) / (maxThickness + minThickness)) * 100
    : 0;

  const thicknessMatrix: number[][] = [];
  for (let j = 0; j < ny; j++) {
    const row: number[] = [];
    for (let i = 0; i < nx; i++) {
      row.push(thickness[j * nx + i]);
    }
    thicknessMatrix.push(row);
  }

  if (onProgress) {
    onProgress(100, '计算完成');
  }

  return {
    thickness,
    coordinates: { x: xCoords, y: yCoords },
    uniformity,
    maxThickness,
    minThickness,
    avgThickness,
    thicknessMatrix,
  };
};
