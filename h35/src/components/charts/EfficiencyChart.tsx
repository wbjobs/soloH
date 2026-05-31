import React, { useRef, useEffect } from 'react';
import type { EfficiencyCurvePoint, CoupledWaveResult } from '../../types';
import { PHYSICAL_CONSTANTS } from '../../utils/physics';

interface EfficiencyChartProps {
  data: EfficiencyCurvePoint[];
  xLabel?: string;
  yLabel?: string;
  title?: string;
  scanType?: 'wavelength' | 'temperature' | 'angle' | 'length';
}

const COLORS = {
  pump: '#00d4ff',
  signal: '#ff6b35',
  idler: '#a855f7',
  grid: 'rgba(255, 255, 255, 0.1)',
  text: '#e2e8f0',
  background: '#0a1628',
};

export const EfficiencyChart: React.FC<EfficiencyChartProps> = ({
  data,
  xLabel = '信号光波长 (nm)',
  yLabel = '转换效率 (%)',
  title = '转换效率曲线',
  scanType = 'wavelength',
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
    const padding = { top: 40, right: 20, bottom: 50, left: 70 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;

    ctx.fillStyle = COLORS.background;
    ctx.fillRect(0, 0, width, height);

    if (data.length === 0) {
      ctx.fillStyle = COLORS.text;
      ctx.font = '14px Inter';
      ctx.textAlign = 'center';
      ctx.fillText('暂无数据，请先进行计算', width / 2, height / 2);
      return;
    }

    let xMin = Math.min(...data.map((d) => d.wavelength));
    let xMax = Math.max(...data.map((d) => d.wavelength));
    const yMin = 0;
    const yMax = Math.max(...data.map((d) => d.efficiency)) * 1.1 || 100;

    if (xMin === xMax) {
      xMin -= 1;
      xMax += 1;
    }

    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 1;

    const xTickCount = 6;
    for (let i = 0; i <= xTickCount; i++) {
      const x = padding.left + (i / xTickCount) * plotWidth;
      ctx.beginPath();
      ctx.moveTo(x, padding.top);
      ctx.lineTo(x, padding.top + plotHeight);
      ctx.stroke();

      const xValue = xMin + (i / xTickCount) * (xMax - xMin);
      ctx.fillStyle = COLORS.text;
      ctx.font = '11px JetBrains Mono';
      ctx.textAlign = 'center';
      ctx.fillText(xValue.toFixed(1), x, padding.top + plotHeight + 20);
    }

    const yTickCount = 5;
    for (let i = 0; i <= yTickCount; i++) {
      const y = padding.top + (i / yTickCount) * plotHeight;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left + plotWidth, y);
      ctx.stroke();

      const yValue = yMax - (i / yTickCount) * (yMax - yMin);
      ctx.fillStyle = COLORS.text;
      ctx.font = '11px JetBrains Mono';
      ctx.textAlign = 'right';
      ctx.fillText(yValue.toFixed(2), padding.left - 10, y + 4);
    }

    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + plotHeight);
    gradient.addColorStop(0, 'rgba(0, 212, 255, 0.4)');
    gradient.addColorStop(1, 'rgba(0, 212, 255, 0.05)');

    ctx.beginPath();
    data.forEach((point, i) => {
      const x =
        padding.left + ((point.wavelength - xMin) / (xMax - xMin)) * plotWidth;
      const y =
        padding.top + ((yMax - point.efficiency) / (yMax - yMin)) * plotHeight;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.strokeStyle = COLORS.signal;
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.lineTo(
      padding.left + ((data[data.length - 1].wavelength - xMin) / (xMax - xMin)) * plotWidth,
      padding.top + plotHeight
    );
    ctx.lineTo(padding.left, padding.top + plotHeight);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 14px Inter';
    ctx.textAlign = 'center';
    ctx.fillText(title, width / 2, 25);

    ctx.font = '12px Inter';
    ctx.textAlign = 'center';
    let xLabelText = xLabel;
    if (scanType === 'temperature') xLabelText = '温度 (°C)';
    else if (scanType === 'angle') xLabelText = '角度 (°)';
    else if (scanType === 'length') xLabelText = '晶体长度 (mm)';
    ctx.fillText(xLabelText, width / 2, height - 10);

    ctx.save();
    ctx.translate(20, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText(yLabel, 0, 0);
    ctx.restore();

    const maxPoint = data.reduce(
      (max, point) => (point.efficiency > max.efficiency ? point : max),
      data[0]
    );
    const maxX =
      padding.left + ((maxPoint.wavelength - xMin) / (xMax - xMin)) * plotWidth;
    const maxY =
      padding.top + ((yMax - maxPoint.efficiency) / (yMax - yMin)) * plotHeight;

    ctx.beginPath();
    ctx.arc(maxX, maxY, 5, 0, Math.PI * 2);
    ctx.fillStyle = COLORS.signal;
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#fff';
    ctx.font = '11px JetBrains Mono';
    ctx.textAlign = 'left';
    let peakLabel = '';
    if (scanType === 'wavelength') peakLabel = `峰值: ${maxPoint.efficiency.toFixed(2)}% @ ${maxPoint.wavelength.toFixed(1)}nm`;
    else if (scanType === 'temperature') peakLabel = `峰值: ${maxPoint.efficiency.toFixed(2)}% @ ${maxPoint.wavelength.toFixed(1)}°C`;
    else if (scanType === 'angle') peakLabel = `峰值: ${maxPoint.efficiency.toFixed(2)}% @ ${maxPoint.wavelength.toFixed(1)}°`;
    else if (scanType === 'length') peakLabel = `峰值: ${maxPoint.efficiency.toFixed(2)}% @ ${maxPoint.wavelength.toFixed(1)}mm`;
    ctx.fillText(peakLabel, maxX + 10, maxY - 10);
  }, [data, xLabel, yLabel, title, scanType]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full rounded-lg"
      style={{ background: COLORS.background }}
    />
  );
};

interface IntensityEvolutionChartProps {
  data: CoupledWaveResult | null;
}

export const IntensityEvolutionChart: React.FC<IntensityEvolutionChartProps> = ({ data }) => {
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
    const padding = { top: 40, right: 80, bottom: 50, left: 70 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;

    ctx.fillStyle = COLORS.background;
    ctx.fillRect(0, 0, width, height);

    if (!data || data.z.length === 0) {
      ctx.fillStyle = COLORS.text;
      ctx.font = '14px Inter';
      ctx.textAlign = 'center';
      ctx.fillText('暂无数据，请先计算耦合波方程', width / 2, height / 2);
      return;
    }

    const xMax = data.z[data.z.length - 1] / PHYSICAL_CONSTANTS.mm_to_m;
    const allIntensities = [
      ...data.pumpIntensity,
      ...data.signalIntensity,
      ...data.idlerIntensity,
    ];
    const yMax = Math.max(...allIntensities) * 1.1;

    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 1;

    const xTickCount = 6;
    for (let i = 0; i <= xTickCount; i++) {
      const x = padding.left + (i / xTickCount) * plotWidth;
      ctx.beginPath();
      ctx.moveTo(x, padding.top);
      ctx.lineTo(x, padding.top + plotHeight);
      ctx.stroke();

      const xValue = (i / xTickCount) * xMax;
      ctx.fillStyle = COLORS.text;
      ctx.font = '11px JetBrains Mono';
      ctx.textAlign = 'center';
      ctx.fillText(xValue.toFixed(1), x, padding.top + plotHeight + 20);
    }

    const yTickCount = 5;
    for (let i = 0; i <= yTickCount; i++) {
      const y = padding.top + (i / yTickCount) * plotHeight;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left + plotWidth, y);
      ctx.stroke();

      const yValue = yMax - (i / yTickCount) * yMax;
      ctx.fillStyle = COLORS.text;
      ctx.font = '11px JetBrains Mono';
      ctx.textAlign = 'right';
      ctx.fillText(yValue.toExponential(2), padding.left - 10, y + 4);
    }

    function plotCurve(
      values: number[],
      color: string,
      label: string,
      isDashed: boolean = false
    ) {
      ctx.beginPath();
      if (isDashed) {
        ctx.setLineDash([5, 5]);
      } else {
        ctx.setLineDash([]);
      }

      values.forEach((value, i) => {
        const x = padding.left + (i / (values.length - 1)) * plotWidth;
        const y = padding.top + ((yMax - value) / yMax) * plotHeight;

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.setLineDash([]);
    }

    plotCurve(data.pumpIntensity, COLORS.pump, '泵浦光');
    plotCurve(data.signalIntensity, COLORS.signal, '信号光');
    plotCurve(data.idlerIntensity, COLORS.idler, '闲频光', true);

    const legendY = padding.top + 20;
    const legendItems = [
      { color: COLORS.pump, label: '泵浦光' },
      { color: COLORS.signal, label: '信号光' },
      { color: COLORS.idler, label: '闲频光' },
    ];

    legendItems.forEach((item, i) => {
      const y = legendY + i * 20;
      ctx.fillStyle = item.color;
      ctx.fillRect(padding.left + plotWidth + 10, y - 8, 15, 3);
      ctx.fillStyle = COLORS.text;
      ctx.font = '12px Inter';
      ctx.textAlign = 'left';
      ctx.fillText(item.label, padding.left + plotWidth + 30, y + 4);
    });

    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 14px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('光强演化曲线', width / 2, 25);

    ctx.font = '12px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('晶体长度 (mm)', width / 2, height - 10);

    ctx.save();
    ctx.translate(20, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText('光强 (W/m²)', 0, 0);
    ctx.restore();

    if (data.conversionEfficiency !== undefined) {
      ctx.fillStyle = COLORS.signal;
      ctx.font = 'bold 12px JetBrains Mono';
      ctx.textAlign = 'right';
      ctx.fillText(
        `转换效率: ${data.conversionEfficiency.toFixed(2)}%`,
        width - 20,
        height - 20
      );
    }
  }, [data]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full rounded-lg"
      style={{ background: COLORS.background }}
    />
  );
};

interface ToleranceDisplayProps {
  bandwidth: number;
  temperatureTolerance: number;
  angleTolerance: number;
  wavelengthTolerance: number;
}

export const ToleranceDisplay: React.FC<ToleranceDisplayProps> = ({
  bandwidth,
  temperatureTolerance,
  angleTolerance,
  wavelengthTolerance,
}) => {
  const tolerances = [
    {
      label: '相位匹配带宽',
      value: bandwidth,
      unit: 'nm',
      color: COLORS.pump,
    },
    {
      label: '温度容许公差',
      value: temperatureTolerance,
      unit: '°C·cm',
      color: COLORS.signal,
    },
    {
      label: '角度容许公差',
      value: angleTolerance,
      unit: 'mrad·cm',
      color: COLORS.idler,
    },
    {
      label: '波长容许公差',
      value: wavelengthTolerance,
      unit: 'nm·cm',
      color: '#22c55e',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3">
      {tolerances.map((tol, i) => (
        <div
          key={i}
          className="p-4 rounded-lg border border-white/10 bg-white/5"
        >
          <div className="text-xs text-gray-400 mb-1">{tol.label}</div>
          <div className="flex items-baseline gap-1">
            <span
              className="text-xl font-bold font-mono"
              style={{ color: tol.color }}
            >
              {tol.value.toFixed(3)}
            </span>
            <span className="text-xs text-gray-400">{tol.unit}</span>
          </div>
        </div>
      ))}
    </div>
  );
};
