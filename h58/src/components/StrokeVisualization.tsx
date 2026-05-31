import React, { useEffect, useRef, useState } from 'react';
import { Eye, EyeOff, Grid3X3 } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { clearCanvas, drawAllStrokes, drawStrokeOrderLabels, drawGrid } from '../utils/canvasRenderer';
import { fuseStyles } from '../utils/styleModel';
import { createCanvasFromData } from '../utils/imageProcessor';

interface StrokeVisualizationProps {
  className?: string;
}

export const StrokeVisualization: React.FC<StrokeVisualizationProps> = ({ className = '' }) => {
  const { samples, selectedSampleId, parameters } = useAppStore();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [showLabels, setShowLabels] = useState(true);
  const [showGrid, setShowGrid] = useState(false);
  const [viewMode, setViewMode] = useState<'strokes' | 'skeleton' | 'original'>('strokes');

  const selectedSample = samples.find(s => s.id === selectedSampleId) || samples[0];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    clearCanvas(ctx, width, height);

    if (!selectedSample) {
      ctx.fillStyle = '#6b6b6b';
      ctx.font = '16px "Noto Serif SC", serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('上传样本字后查看笔画分析', width / 2, height / 2);
      return;
    }

    if (showGrid) {
      drawGrid(ctx, width, height);
    }

    if (viewMode === 'original') {
      const img = new Image();
      img.onload = () => {
        ctx.drawImage(img, 0, 0, width, height);
      };
      img.src = selectedSample.originalImage;
      return;
    }

    const styleFeatures = fuseStyles(samples);

    if (viewMode === 'strokes') {
      drawAllStrokes(ctx, selectedSample.strokes, parameters, styleFeatures, '#1a1a1a', true);
      
      if (showLabels) {
        drawStrokeOrderLabels(ctx, selectedSample.strokes, '#c41e3a');
      }
    } else if (viewMode === 'skeleton') {
      const tempCanvas = createCanvasFromData(
        new Uint8ClampedArray(selectedSample.strokes.flatMap(s => 
          s.points.map(p => 255)
        )),
        width,
        height
      );
      
      ctx.drawImage(tempCanvas, 0, 0);
      
      for (let i = 0; i < selectedSample.strokes.length; i++) {
        const stroke = selectedSample.strokes[i];
        const colors = ['#c41e3a', '#b8860b', '#2e7d32', '#1565c0', '#6a1b9a', '#e65100'];
        const color = colors[i % colors.length];
        
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        for (let j = 0; j < stroke.points.length; j++) {
          const p = stroke.points[j];
          if (j === 0) {
            ctx.moveTo(p.x, p.y);
          } else {
            ctx.lineTo(p.x, p.y);
          }
        }
        ctx.stroke();
        
        if (showLabels && stroke.points.length > 0) {
          const start = stroke.points[0];
          ctx.fillStyle = 'rgba(255,255,255,0.9)';
          ctx.beginPath();
          ctx.arc(start.x, start.y, 12, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#c41e3a';
          ctx.font = 'bold 12px sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText((i + 1).toString(), start.x, start.y);
        }
      }
    }
  }, [selectedSample, parameters, showLabels, showGrid, viewMode, samples]);

  if (!selectedSample) {
    return (
      <div className={`${className}`}>
        <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a]">笔画分析</h3>
        <div className="canvas-container rounded-lg overflow-hidden aspect-square grid-lines flex items-center justify-center">
          <p className="text-[#6b6b6b] text-sm">上传样本字后查看笔画分析</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-calligraphy text-xl text-[#1a1a1a]">笔画分析</h3>
        <div className="flex items-center gap-1 text-xs text-[#6b6b6b]">
          <span className="font-calligraphy text-lg">{selectedSample.character}</span>
          <span>·</span>
          <span>{selectedSample.strokes.length} 笔</span>
        </div>
      </div>
      
      <div className="flex gap-2 mb-3">
        <ViewModeButton 
          active={viewMode === 'strokes'} 
          onClick={() => setViewMode('strokes')}
          label="笔画"
        />
        <ViewModeButton 
          active={viewMode === 'skeleton'} 
          onClick={() => setViewMode('skeleton')}
          label="骨架"
        />
        <ViewModeButton 
          active={viewMode === 'original'} 
          onClick={() => setViewMode('original')}
          label="原图"
        />
      </div>
      
      <div className="canvas-container rounded-lg overflow-hidden aspect-square relative">
        <canvas
          ref={canvasRef}
          width={400}
          height={400}
          className="w-full h-full"
        />
      </div>
      
      <div className="flex gap-4 mt-3">
        <button
          onClick={() => setShowLabels(!showLabels)}
          className={`flex items-center gap-1 text-sm px-3 py-1.5 rounded transition-colors ${
            showLabels ? 'bg-[#1a1a1a] text-[#f5f0e6]' : 'bg-[#e8e0cf] text-[#3d3d3d]'
          }`}
        >
          {showLabels ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
          顺序标注
        </button>
        
        <button
          onClick={() => setShowGrid(!showGrid)}
          className={`flex items-center gap-1 text-sm px-3 py-1.5 rounded transition-colors ${
            showGrid ? 'bg-[#1a1a1a] text-[#f5f0e6]' : 'bg-[#e8e0cf] text-[#3d3d3d]'
          }`}
        >
          <Grid3X3 className="w-4 h-4" />
          网格
        </button>
      </div>
      
      <div className="mt-4 space-y-2">
        <h4 className="text-sm font-semibold text-[#3d3d3d]">笔画列表</h4>
        <div className="max-h-40 overflow-y-auto scrollbar-ink space-y-1">
          {selectedSample.strokes.map((stroke, index) => (
            <div 
              key={stroke.id}
              className="flex items-center gap-3 px-2 py-1.5 bg-[#e8e0cf]/30 rounded text-sm"
            >
              <span className="w-6 h-6 flex items-center justify-center bg-[#c41e3a] text-white rounded-full text-xs font-bold font-calligraphy">
                {index + 1}
              </span>
              <span className="text-[#3d3d3d]">{getStrokeTypeName(stroke.type)}</span>
              <span className="text-[#6b6b6b] text-xs ml-auto">
                {stroke.points.length} 点
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

interface ViewModeButtonProps {
  active: boolean;
  onClick: () => void;
  label: string;
}

const ViewModeButton: React.FC<ViewModeButtonProps> = ({ active, onClick, label }) => (
  <button
    onClick={onClick}
    className={`px-3 py-1 text-sm rounded transition-all ${
      active 
        ? 'bg-[#1a1a1a] text-[#f5f0e6]' 
        : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
    }`}
  >
    {label}
  </button>
);

function getStrokeTypeName(type: string): string {
  const names: Record<string, string> = {
    'horizontal': '横',
    'vertical': '竖',
    'diagonal-down': '撇',
    'diagonal-up': '捺',
    'dot': '点',
    'turn': '折',
    'curve': '弯',
    'line': '线',
    'unknown': '未知'
  };
  return names[type] || type;
}
