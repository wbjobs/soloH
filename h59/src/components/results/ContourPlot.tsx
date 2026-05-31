import React, { useRef, useEffect, useMemo } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { valueToColor, generateContourLevels, formatScientific } from '../../utils/colorMap';
import { Gauge, TrendingUp, Download, BarChart3 } from 'lucide-react';

export const ContourPlot: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { calculationResult, substrate } = useAppStore();

  const contourLevels = useMemo(() => {
    if (!calculationResult) return [];
    return generateContourLevels(
      calculationResult.minThickness,
      calculationResult.maxThickness,
      15
    );
  }, [calculationResult]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !calculationResult || !calculationResult.thicknessMatrix) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const matrix = calculationResult.thicknessMatrix;
    const nx = matrix[0].length;
    const ny = matrix.length;

    const imageData = ctx.createImageData(width, height);
    const data = imageData.data;

    for (let py = 0; py < height; py++) {
      for (let px = 0; px < width; px++) {
        const ix = Math.floor((px / width) * nx);
        const iy = Math.floor((py / height) * ny);
        const t = matrix[iy]?.[ix] || 0;
        const color = valueToColor(t, calculationResult.minThickness, calculationResult.maxThickness, 'rainbow');
        const rgbMatch = color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
        if (rgbMatch) {
          const idx = (py * width + px) * 4;
          data[idx] = parseInt(rgbMatch[1]);
          data[idx + 1] = parseInt(rgbMatch[2]);
          data[idx + 2] = parseInt(rgbMatch[3]);
          data[idx + 3] = 255;
        }
      }
    }

    ctx.putImageData(imageData, 0, 0);

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.lineWidth = 0.5;
    ctx.font = '10px Inter, sans-serif';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';

    for (let levelIdx = 1; levelIdx < contourLevels.length; levelIdx += 2) {
      const level = contourLevels[levelIdx];
      const threshold = (level - calculationResult.minThickness) / (calculationResult.maxThickness - calculationResult.minThickness);

      for (let j = 0; j < ny - 1; j++) {
        for (let i = 0; i < nx - 1; i++) {
          const v00 = (matrix[j][i] - calculationResult.minThickness) / (calculationResult.maxThickness - calculationResult.minThickness);
          const v10 = (matrix[j][i + 1] - calculationResult.minThickness) / (calculationResult.maxThickness - calculationResult.minThickness);
          const v01 = (matrix[j + 1][i] - calculationResult.minThickness) / (calculationResult.maxThickness - calculationResult.minThickness);
          const v11 = (matrix[j + 1][i + 1] - calculationResult.minThickness) / (calculationResult.maxThickness - calculationResult.minThickness);

          const crossings: { x: number; y: number }[] = [];

          if ((v00 - threshold) * (v10 - threshold) < 0) {
            const t = (threshold - v00) / (v10 - v00);
            crossings.push({ x: i + t, y: j });
          }
          if ((v10 - threshold) * (v11 - threshold) < 0) {
            const t = (threshold - v10) / (v11 - v10);
            crossings.push({ x: i + 1, y: j + t });
          }
          if ((v01 - threshold) * (v11 - threshold) < 0) {
            const t = (threshold - v01) / (v11 - v01);
            crossings.push({ x: i + t, y: j + 1 });
          }
          if ((v00 - threshold) * (v01 - threshold) < 0) {
            const t = (threshold - v00) / (v01 - v00);
            crossings.push({ x: i, y: j + t });
          }

          if (crossings.length >= 2) {
            ctx.beginPath();
            ctx.moveTo((crossings[0].x / nx) * width, (crossings[0].y / ny) * height);
            ctx.lineTo((crossings[1].x / nx) * width, (crossings[1].y / ny) * height);
            ctx.stroke();
          }
        }
      }
    }
  }, [calculationResult, contourLevels]);

  const handleExport = () => {
    if (!calculationResult) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const link = document.createElement('a');
    link.download = 'thickness_contour.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  if (!calculationResult) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500">
        <div className="text-center">
          <BarChart3 className="w-16 h-16 mx-auto mb-4 opacity-30" />
          <p className="text-sm">运行计算后显示膜厚等高线图</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-cyan-400" />
          膜厚等高线图
        </h3>
        <button
          onClick={handleExport}
          className="p-1.5 text-slate-400 hover:text-cyan-400 transition-colors"
          title="导出图片"
        >
          <Download className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 flex items-center justify-center bg-slate-900/50 rounded-lg p-2">
        <canvas
          ref={canvasRef}
          width={400}
          height={400}
          className="border border-slate-700 rounded"
        />
      </div>

      <div className="mt-3">
        <div className="flex justify-between text-xs text-slate-500 mb-1">
          <span>最小</span>
          <span>最大</span>
        </div>
        <div className="h-4 rounded-full overflow-hidden flex">
          {Array.from({ length: 100 }).map((_, i) => (
            <div
              key={i}
              className="flex-1"
              style={{
                backgroundColor: valueToColor(i / 99, 0, 1, 'rainbow'),
              }}
            />
          ))}
        </div>
        <div className="flex justify-between text-xs text-slate-400 mt-1">
          <span>{formatScientific(calculationResult.minThickness)}</span>
          <span>{formatScientific(calculationResult.avgThickness)}</span>
          <span>{formatScientific(calculationResult.maxThickness)}</span>
        </div>
      </div>
    </div>
  );
};

export const StatisticsPanel: React.FC = () => {
  const { calculationResult, optimizationResult, optimizationHistory } = useAppStore();

  if (!calculationResult) {
    return null;
  }

  const getUniformityColor = (value: number) => {
    if (value >= 95) return 'text-green-400';
    if (value >= 90) return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
        <Gauge className="w-4 h-4 text-cyan-400" />
        统计数据
      </h3>

      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 bg-slate-900/50 rounded-lg border border-slate-700">
          <p className="text-xs text-slate-500 mb-1">均匀性</p>
          <p className={`text-2xl font-bold font-mono ${getUniformityColor(calculationResult.uniformity)}`}>
            {calculationResult.uniformity.toFixed(2)}%
          </p>
        </div>

        <div className="p-3 bg-slate-900/50 rounded-lg border border-slate-700">
          <p className="text-xs text-slate-500 mb-1">平均膜厚</p>
          <p className="text-lg font-semibold text-cyan-400 font-mono">
            {formatScientific(calculationResult.avgThickness)}
          </p>
        </div>

        <div className="p-3 bg-slate-900/50 rounded-lg border border-slate-700">
          <p className="text-xs text-slate-500 mb-1">最大膜厚</p>
          <p className="text-sm text-orange-400 font-mono">
            {formatScientific(calculationResult.maxThickness)}
          </p>
        </div>

        <div className="p-3 bg-slate-900/50 rounded-lg border border-slate-700">
          <p className="text-xs text-slate-500 mb-1">最小膜厚</p>
          <p className="text-sm text-blue-400 font-mono">
            {formatScientific(calculationResult.minThickness)}
          </p>
        </div>
      </div>

      {optimizationResult && (
        <div className="p-3 bg-gradient-to-r from-cyan-900/30 to-blue-900/30 rounded-lg border border-cyan-700/50">
          <p className="text-xs text-cyan-400 mb-2 font-semibold">✓ 优化结果</p>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">最终均匀性</span>
              <span className="text-green-400 font-mono">{optimizationResult.bestUniformity.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">迭代次数</span>
              <span className="text-slate-300 font-mono">{optimizationResult.iterations}</span>
            </div>
            {optimizationResult.bestPositions.map((pos, idx) => (
              <div key={pos.sourceId} className="pt-1 border-t border-slate-700/50">
                <p className="text-slate-400 mb-1">源 {idx + 1} 位置</p>
                <p className="text-slate-300 font-mono text-[10px]">
                  ({pos.position.x.toFixed(1)}, {pos.position.y.toFixed(1)}, {pos.position.z.toFixed(1)})
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {optimizationHistory.length > 0 && (
        <div className="p-3 bg-slate-900/50 rounded-lg border border-slate-700">
          <p className="text-xs text-slate-400 mb-2">优化收敛曲线</p>
          <div className="h-20 flex items-end gap-0.5">
            {optimizationHistory.slice(-20).map((entry, idx) => (
              <div
                key={idx}
                className="flex-1 bg-gradient-to-t from-cyan-600 to-cyan-400 rounded-t transition-all"
                style={{
                  height: `${Math.max(5, ((entry.bestUniformity - 50) / 50) * 100)}%`,
                }}
                title={`迭代 ${entry.iteration + 1}: ${entry.bestUniformity.toFixed(2)}%`}
              />
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-slate-500 mt-1">
            <span>迭代</span>
            <span>均匀性(%)</span>
          </div>
        </div>
      )}
    </div>
  );
};
