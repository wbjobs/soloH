import { ImpactForceData, Vector3 } from '../types/physics';

export function exportImpactForceToCSV(
  impactHistory: ImpactForceData[]): string {
  const headers = [
    '时间(s)',
    '总冲击力_X(N)',
    '总冲击力_Y(N)',
    '总冲击力_Z(N)',
    '总冲击力大小(N)',
    '细颗粒冲击力(N)',
    '粗颗粒冲击力(N)',
    '细颗粒冲击数',
    '粗颗粒冲击数',
    '最大压强(Pa)',
    '冲击粒子数',
    '冲击面积(m²)',
    '平均速度(m/s)',
    '冲击力均值(N)',
    '冲击力标准差(N)',
    '冲击力偏度',
    '压强均值(Pa)',
    '压强标准差(Pa)',
    '压强偏度'
  ].join(',');

  const rows = impactHistory.map(data => {
    const forceMagnitude = Math.sqrt(
      data.totalForce.x * data.totalForce.x +
      data.totalForce.y * data.totalForce.y +
      data.totalForce.z * data.totalForce.z
    );
    
    const fineForceMag = data.fineParticleForce ? Math.sqrt(
      data.fineParticleForce.x * data.fineParticleForce.x +
      data.fineParticleForce.y * data.fineParticleForce.y +
      data.fineParticleForce.z * data.fineParticleForce.z
    ) : 0;
    
    const coarseForceMag = data.coarseParticleForce ? Math.sqrt(
      data.coarseParticleForce.x * data.coarseParticleForce.x +
      data.coarseParticleForce.y * data.coarseParticleForce.y +
      data.coarseParticleForce.z * data.coarseParticleForce.z
    ) : 0;
    
    return [
      data.timestamp.toFixed(4),
      data.totalForce.x.toFixed(4),
      data.totalForce.y.toFixed(4),
      data.totalForce.z.toFixed(4),
      forceMagnitude.toFixed(4),
      fineForceMag.toFixed(4),
      coarseForceMag.toFixed(4),
      (data.fineParticleCount || 0).toString(),
      (data.coarseParticleCount || 0).toString(),
      data.maxPressure.toFixed(2),
      data.particleCount.toString(),
      data.impactArea.toFixed(6),
      data.averageVelocity.toFixed(4),
      data.probabilityDistribution?.forceMean.toFixed(4) || '',
      data.probabilityDistribution?.forceStd.toFixed(4) || '',
      data.probabilityDistribution?.forceSkewness.toFixed(4) || '',
      data.probabilityDistribution?.pressureMean.toFixed(2) || '',
      data.probabilityDistribution?.pressureStd.toFixed(2) || '',
      data.probabilityDistribution?.pressureSkewness.toFixed(4) || ''
    ].join(',');
  });

  return [headers, ...rows].join('\n');
}

export function exportProbabilityDistributionToCSV(
  distribution: any): string {
  if (!distribution) return '';

  let csv = '=== 冲击力概率分布 ===\n';
  csv += '区间下限(N),区间上限(N),计数,概率,超越概率\n';
  for (const bin of distribution.forceHistogram || []) {
    csv += `${bin.minValue.toFixed(4)},${bin.maxValue.toFixed(4)},${bin.count},${bin.probability.toFixed(6)},${bin.exceedanceProbability.toFixed(6)}\n`;
  }

  csv += '\n=== 压强概率分布 ===\n';
  csv += '区间下限(Pa),区间上限(Pa),计数,概率,超越概率\n';
  for (const bin of distribution.pressureHistogram || []) {
    csv += `${bin.minValue.toFixed(2)},${bin.maxValue.toFixed(2)},${bin.count},${bin.probability.toFixed(6)},${bin.exceedanceProbability.toFixed(6)}\n`;
  }

  csv += '\n=== 重现期 ===\n';
  csv += '重现期(年),设计冲击力(N),设计压强(Pa)\n';
  for (const rp of distribution.returnPeriods || []) {
    csv += `${rp.period},${rp.force.toFixed(4)},${rp.pressure.toFixed(2)}\n`;
  }

  csv += '\n=== 统计特征 ===\n';
  csv += `冲击力均值(N),${distribution.forceMean?.toFixed(4) || ''}\n`;
  csv += `冲击力标准差(N),${distribution.forceStd?.toFixed(4) || ''}\n`;
  csv += `冲击力偏度,${distribution.forceSkewness?.toFixed(4) || ''}\n`;
  csv += `压强均值(Pa),${distribution.pressureMean?.toFixed(2) || ''}\n`;
  csv += `压强标准差(Pa),${distribution.pressureStd?.toFixed(2) || ''}\n`;
  csv += `压强偏度,${distribution.pressureSkewness?.toFixed(4) || ''}\n`;

  return csv;
}

export function downloadCSV(csvContent: string, filename: string): void {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  URL.revokeObjectURL(url);
}

export function exportParticlesToCSV(particles: any[], simulationTime: number): string {
  const headers = [
    '粒子ID',
    '模拟时间(s)',
    '位置X(m)',
    '位置Y(m)',
    '位置Z(m)',
    '速度X(m/s)',
    '速度Y(m/s)',
    '速度Z(m/s)',
    '速度大小(m/s)',
    '密度(kg/m³)',
    '压力(Pa)'
  ].join(',');

  const rows = particles.map(p => {
    const speed = Math.sqrt(
      p.velocity.x * p.velocity.x +
      p.velocity.y * p.velocity.y +
      p.velocity.z * p.velocity.z
    );
    
    return [
      p.id.toString(),
      simulationTime.toFixed(4),
      p.position.x.toFixed(4),
      p.position.y.toFixed(4),
      p.position.z.toFixed(4),
      p.velocity.x.toFixed(4),
      p.velocity.y.toFixed(4),
      p.velocity.z.toFixed(4),
      speed.toFixed(4),
      p.density.toFixed(2),
      p.pressure.toFixed(2)
    ].join(',');
  });

  return [headers, ...rows].join('\n');
}

export function generateFileName(prefix: string, extension: string): string {
  const now = new Date();
  const timestamp = now.getFullYear().toString() +
    (now.getMonth() + 1).toString().padStart(2, '0') +
    now.getDate().toString().padStart(2, '0') + '_' +
    now.getHours().toString().padStart(2, '0') +
    now.getMinutes().toString().padStart(2, '0') +
    now.getSeconds().toString().padStart(2, '0');
  
  return `${prefix}_${timestamp}.${extension}`;
}

export function exportStatsToCSV(
  peakForce: number, peakPressure: number, totalImpulse: Vector3, duration: number, particleCount: number): string {
  const headers = [
    '指标',
    '数值',
    '单位'
  ].join(',');

  const impulseMagnitude = Math.sqrt(
    totalImpulse.x * totalImpulse.x +
    totalImpulse.y * totalImpulse.y +
    totalImpulse.z * totalImpulse.z
  );

  const rows = [
    ['峰值冲击力', peakForce.toFixed(4), 'N'].join(','),
    ['峰值压强', peakPressure.toFixed(2), 'Pa'].join(','),
    ['总冲量_X', totalImpulse.x.toFixed(4), 'N·s'].join(','),
    ['总冲量大小', impulseMagnitude.toFixed(4), 'N·s'].join(','),
    ['模拟时长', duration.toFixed(4), 's'].join(','),
    ['粒子数量', particleCount.toString(), '个'].join(',')
  ];

  return [headers, ...rows].join('\n');
}
