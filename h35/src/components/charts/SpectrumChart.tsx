import React, { useRef, useEffect } from 'react';
import type { SpectrumPoint } from '../../types';

interface SpectrumChartProps {
  data: SpectrumPoint[];
  title?: string;
}

const COLORS = {
  spectrum: '#00d4ff',
  grid: 'rgba(255, 255, 255, 0.1)',
  text: '#e2e8f0',
  background: '#0a1628',
  peak: '#ff6b35',
};

export const SpectrumChart: React.FC<SpectrumChartProps> = ({
  data,
  title = '信号光谱',
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
      ctx.fillText('暂无数据，请先进行频谱分析', width / 2, height / 2);
      return;
    }

    const xMin = Math.min(...data.map((d) => d.wavelength));
    const xMax = Math.max(...data.map((d) => d.wavelength));
    const yMin = 0;
    const yMax = Math.max(...data.map((d) => d.amplitude)) * 1.1;

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
      ctx.fillText(xValue.toFixed(0), x, padding.top + plotHeight + 20);
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
      ctx.fillText(yValue.toExponential(2), padding.left - 10, y + 4);
    }

    ctx.beginPath();
    data.forEach((point, i) => {
      const x =
        padding.left + ((point.wavelength - xMin) / (xMax - xMin)) * plotWidth;
      const y =
        padding.top + ((yMax - point.amplitude) / (yMax - yMin)) * plotHeight;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + plotHeight);
    gradient.addColorStop(0, 'rgba(0, 212, 255, 0.5)');
    gradient.addColorStop(1, 'rgba(0, 212, 255, 0.05)');

    ctx.strokeStyle = COLORS.spectrum;
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

    const peaks = findPeaks(data, 0.3);
    peaks.slice(0, 3).forEach((peak) => {
      const x =
        padding.left + ((peak.wavelength - xMin) / (xMax - xMin)) * plotWidth;
      const y =
        padding.top + ((yMax - peak.amplitude) / (yMax - yMin)) * plotHeight;

      ctx.beginPath();
      ctx.moveTo(x, padding.top + plotHeight);
      ctx.lineTo(x, y);
      ctx.strokeStyle = COLORS.peak;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = COLORS.peak;
      ctx.fill();

      ctx.fillStyle = COLORS.peak;
      ctx.font = '10px JetBrains Mono';
      ctx.textAlign = 'center';
      ctx.fillText(`${peak.wavelength.toFixed(0)}nm`, x, y - 10);
    });

    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 14px Inter';
    ctx.textAlign = 'center';
    ctx.fillText(title, width / 2, 25);

    ctx.font = '12px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('波长 (nm)', width / 2, height - 10);

    ctx.save();
    ctx.translate(20, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText('幅度 (a.u.)', 0, 0);
    ctx.restore();
  }, [data, title]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full rounded-lg"
      style={{ background: COLORS.background }}
    />
  );
};

function findPeaks(
  data: SpectrumPoint[],
  threshold: number = 0.1
): { wavelength: number; amplitude: number }[] {
  const peaks: { wavelength: number; amplitude: number }[] = [];
  const maxAmplitude = Math.max(...data.map((s) => s.amplitude));

  for (let i = 1; i < data.length - 1; i++) {
    if (
      data[i].amplitude > data[i - 1].amplitude &&
      data[i].amplitude > data[i + 1].amplitude &&
      data[i].amplitude > threshold * maxAmplitude
    ) {
      peaks.push({
        wavelength: data[i].wavelength,
        amplitude: data[i].amplitude,
      });
    }
  }

  return peaks.sort((a, b) => b.amplitude - a.amplitude);
}
