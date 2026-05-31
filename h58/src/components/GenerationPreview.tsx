import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Play, Pause, RotateCcw, SkipBack, SkipForward } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { clearCanvas, drawStrokesAnimated, drawStrokeWithVariableWidth } from '../utils/canvasRenderer';
import { fuseStyles } from '../utils/styleModel';
import { calculateLayout, applyRubbingEffectToCanvas, getLayoutBackground, getInkColor } from '../utils/layoutUtils';
import { generateSealSVG, generateSignatureSVG } from '../utils/layoutUtils';

interface GenerationPreviewProps {
  className?: string;
}

export const GenerationPreview: React.FC<GenerationPreviewProps> = ({ className = '' }) => {
  const {
    generatedCharacters,
    parameters,
    layout,
    seal,
    signature,
    rubbing,
    samples,
    isPlaying,
    currentStrokeIndex,
    currentCharacterIndex,
    setIsPlaying,
    setCurrentStrokeIndex,
    setCurrentCharacterIndex,
    resetAnimation
  } = useAppStore();

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const [strokeProgress, setStrokeProgress] = useState(0);

  const styleFeatures = fuseStyles(samples);
  const charSize = 200;

  const currentChar = generatedCharacters[currentCharacterIndex];
  const totalCharacters = generatedCharacters.length;
  const totalStrokes = currentChar?.strokes.length || 0;

  const layoutResult = useMemo(() => {
    if (totalCharacters === 0) {
      return { positions: [], totalWidth: charSize, totalHeight: charSize, lines: 1 };
    }
    return calculateLayout(generatedCharacters, charSize, layout);
  }, [generatedCharacters, layout, totalCharacters, charSize]);

  const { positions, totalWidth, totalHeight } = layoutResult;
  const padding = 40;
  const extraBottom = (signature.enabled || seal.enabled) ? 80 : 0;
  const canvasWidth = Math.max(totalWidth + padding * 2, charSize);
  const canvasHeight = Math.max(totalHeight + padding * 2 + extraBottom, charSize);

  const bgColor = getLayoutBackground(canvasWidth, canvasHeight, rubbing);
  const inkColor = getInkColor(rubbing, '#1a1a1a');

  const renderFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || totalCharacters === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, canvasWidth, canvasHeight);

    for (let i = 0; i < totalCharacters; i++) {
      const char = generatedCharacters[i];
      const pos = positions[i];
      if (!char || !pos || char.character.trim() === '') continue;

      ctx.save();
      
      const cx = charSize / 2;
      const cy = charSize / 2;
      const tx = pos.x + padding;
      const ty = pos.y + padding;
      
      ctx.translate(tx, ty);
      ctx.translate(cx, cy);
      ctx.rotate(pos.rotation);
      ctx.scale(pos.scale, pos.scale);
      ctx.translate(-cx, -cy);

      if (i < currentCharacterIndex) {
        for (const stroke of char.strokes) {
          drawStrokeWithVariableWidth(
            ctx,
            stroke,
            parameters,
            styleFeatures,
            inkColor,
            1
          );
        }
      } else if (i === currentCharacterIndex) {
        drawStrokesAnimated(
          ctx,
          char.strokes,
          parameters,
          styleFeatures,
          currentStrokeIndex,
          strokeProgress,
          inkColor,
          true
        );
      }

      ctx.restore();
    }

    if (signature.enabled && signature.text) {
      const sigX = (canvasWidth * signature.positionX) / 100;
      const sigY = canvasHeight - 60 + (signature.positionY - 75) * 0.5;
      
      ctx.save();
      ctx.translate(sigX, sigY);
      ctx.rotate((signature.rotation * Math.PI) / 180);
      
      ctx.fillStyle = inkColor;
      ctx.font = `${signature.fontSize}px 'ZCOOL XiaoWei', 'STKaiti', 'KaiTi', serif`;
      if (signature.style === 'cursive') {
        ctx.font = `italic ${signature.fontSize}px 'Ma Shan Zheng', 'STKaiti', 'KaiTi', cursive`;
      } else if (signature.style === 'regular') {
        ctx.font = `${signature.fontSize}px 'Noto Serif SC', 'SimSun', serif`;
      }
      ctx.fillText(signature.text, 0, signature.fontSize * 0.7);
      ctx.restore();
    }

    if (seal.enabled && seal.text) {
      const sealX = (canvasWidth * seal.positionX) / 100;
      const sealY = canvasHeight - 80 + (seal.positionY - 90) * 0.5;
      
      ctx.save();
      ctx.translate(sealX, sealY);
      ctx.rotate((seal.rotation * Math.PI) / 180);
      ctx.globalAlpha = seal.opacity;
      
      ctx.strokeStyle = seal.color;
      ctx.lineWidth = 2;
      const half = seal.size / 2;
      
      if (seal.style === 'circle') {
        ctx.beginPath();
        ctx.arc(half, half, half - 2, 0, Math.PI * 2);
        ctx.stroke();
      } else if (seal.style === 'oval') {
        ctx.beginPath();
        ctx.ellipse(half, half, half - 2, half * 0.7 - 2, 0, 0, Math.PI * 2);
        ctx.stroke();
      } else {
        ctx.strokeRect(1, 1, seal.size - 2, seal.size - 2);
      }
      
      ctx.fillStyle = seal.color;
      ctx.font = `bold ${Math.max(8, seal.size / (seal.text.length > 2 ? 2.5 : 2))}px 'Ma Shan Zheng', 'STKaiti', 'KaiTi', serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      
      const chars = seal.text.split('');
      if (chars.length <= 2) {
        ctx.fillText(seal.text, half, half);
      } else {
        const charsPerLine = Math.ceil(Math.sqrt(chars.length));
        const lines = Math.ceil(chars.length / charsPerLine);
        const fontSize = Math.max(8, seal.size / (charsPerLine + 1));
        ctx.font = `bold ${fontSize}px 'Ma Shan Zheng', 'STKaiti', 'KaiTi', serif`;
        const lineHeight = fontSize * 1.1;
        const startY = half - (lines * lineHeight) / 2 + lineHeight / 2;
        
        for (let line = 0; line < lines; line++) {
          const lineChars = chars.slice(line * charsPerLine, (line + 1) * charsPerLine);
          ctx.fillText(lineChars.join(''), half, startY + line * lineHeight);
        }
      }
      ctx.restore();
    }

    if (rubbing.enabled) {
      applyRubbingEffectToCanvas(ctx, canvasWidth, canvasHeight, rubbing);
    }
  }, [generatedCharacters, positions, currentCharacterIndex, currentStrokeIndex, strokeProgress, parameters, styleFeatures, totalCharacters, canvasWidth, canvasHeight, bgColor, inkColor, seal, signature, rubbing]);

  useEffect(() => {
    renderFrame();
  }, [renderFrame]);

  useEffect(() => {
    if (!isPlaying || !currentChar || totalCharacters === 0) {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
      return;
    }

    let lastTime = 0;
    const baseSpeed = (100 - parameters.speed) / 25 + 0.2;

    const animate = (timestamp: number) => {
      if (lastTime === 0) lastTime = timestamp;
      const delta = timestamp - lastTime;
      
      if (delta > 16) {
        lastTime = timestamp;
        
        setStrokeProgress(prev => {
          const newProgress = prev + baseSpeed * 0.02;
          
          if (newProgress >= 1) {
            if (currentStrokeIndex < totalStrokes - 1) {
              setCurrentStrokeIndex(currentStrokeIndex + 1);
              return 0;
            } else if (currentCharacterIndex < totalCharacters - 1) {
              setCurrentCharacterIndex(currentCharacterIndex + 1);
              setCurrentStrokeIndex(0);
              return 0;
            } else {
              setIsPlaying(false);
              return 1;
            }
          }
          return newProgress;
        });
      }

      if (isPlaying) {
        animationRef.current = requestAnimationFrame(animate);
      }
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isPlaying, currentChar, currentStrokeIndex, currentCharacterIndex, totalStrokes, totalCharacters, parameters.speed, setCurrentStrokeIndex, setCurrentCharacterIndex, setIsPlaying]);

  const handlePlayPause = () => {
    if (currentCharacterIndex >= totalCharacters - 1 && 
        currentStrokeIndex >= totalStrokes - 1 && 
        strokeProgress >= 1) {
      resetAnimation();
      setIsPlaying(true);
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  const handleReset = () => {
    resetAnimation();
    setStrokeProgress(0);
  };

  const handlePrevStroke = () => {
    setIsPlaying(false);
    if (strokeProgress > 0) {
      setStrokeProgress(0);
    } else if (currentStrokeIndex > 0) {
      setCurrentStrokeIndex(currentStrokeIndex - 1);
      setStrokeProgress(1);
    } else if (currentCharacterIndex > 0) {
      setCurrentCharacterIndex(currentCharacterIndex - 1);
      const prevChar = generatedCharacters[currentCharacterIndex - 1];
      if (prevChar) {
        setCurrentStrokeIndex(prevChar.strokes.length - 1);
        setStrokeProgress(1);
      }
    }
  };

  const handleNextStroke = () => {
    setIsPlaying(false);
    if (strokeProgress < 1) {
      setStrokeProgress(1);
    } else if (currentStrokeIndex < totalStrokes - 1) {
      setCurrentStrokeIndex(currentStrokeIndex + 1);
      setStrokeProgress(0);
    } else if (currentCharacterIndex < totalCharacters - 1) {
      setCurrentCharacterIndex(currentCharacterIndex + 1);
      setCurrentStrokeIndex(0);
      setStrokeProgress(0);
    }
  };

  const handleCharacterClick = (index: number) => {
    setIsPlaying(false);
    setCurrentCharacterIndex(index);
    setCurrentStrokeIndex(0);
    setStrokeProgress(0);
  };

  if (totalCharacters === 0) {
    return (
      <div className={`${className}`}>
        <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a]">生成预览</h3>
        <div className="canvas-container rounded-lg overflow-hidden h-[200px] grid-lines flex items-center justify-center">
          <p className="text-[#6b6b6b] text-sm">输入文本并点击生成按钮</p>
        </div>
      </div>
    );
  }

  const overallProgress = totalCharacters > 0
    ? ((currentCharacterIndex + (currentStrokeIndex + strokeProgress) / Math.max(totalStrokes, 1)) / totalCharacters) * 100
    : 0;

  return (
    <div className={`${className}`}>
      <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a]">生成预览</h3>
      
      <div className="canvas-container rounded-lg overflow-hidden relative">
        <canvas
          ref={canvasRef}
          width={canvasWidth}
          height={canvasHeight}
          className="w-full h-auto"
        />
        
        <div className="absolute top-2 left-2 flex gap-1">
          {generatedCharacters.map((char, index) => (
            <button
              key={index}
              onClick={() => handleCharacterClick(index)}
              className={`w-8 h-8 rounded text-xs font-bold transition-all ${
                index === currentCharacterIndex
                  ? 'bg-[#c41e3a] text-white'
                  : index < currentCharacterIndex
                  ? 'bg-[#1a1a1a] text-white'
                  : 'bg-[#e8e0cf] text-[#6b6b6b]'
              }`}
            >
              {index + 1}
            </button>
          ))}
        </div>
      </div>
      
      <div className="mt-3 mb-2">
        <div className="h-1 bg-[#e8e0cf] rounded-full overflow-hidden">
          <div 
            className="h-full bg-[#c41e3a] transition-all duration-100"
            style={{ width: `${overallProgress}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-[#6b6b6b] mt-1">
          <span>第 {currentCharacterIndex + 1}/{totalCharacters} 字</span>
          <span>第 {currentStrokeIndex + 1}/{Math.max(totalStrokes, 1)} 笔</span>
          <span>{Math.round(overallProgress)}%</span>
        </div>
      </div>
      
      <div className="flex items-center justify-center gap-2">
        <button
          onClick={handleReset}
          className="w-10 h-10 flex items-center justify-center rounded-full bg-[#e8e0cf] hover:bg-[#d8cfb8] transition-colors"
          title="重置"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
        
        <button
          onClick={handlePrevStroke}
          disabled={currentCharacterIndex === 0 && currentStrokeIndex === 0 && strokeProgress === 0}
          className="w-10 h-10 flex items-center justify-center rounded-full bg-[#e8e0cf] hover:bg-[#d8cfb8] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="上一笔"
        >
          <SkipBack className="w-4 h-4" />
        </button>
        
        <button
          onClick={handlePlayPause}
          className="w-14 h-14 flex items-center justify-center rounded-full bg-[#c41e3a] text-white hover:bg-[#b01a33] transition-colors shadow-lg"
          title={isPlaying ? '暂停' : '播放'}
        >
          {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 ml-1" />}
        </button>
        
        <button
          onClick={handleNextStroke}
          disabled={currentCharacterIndex >= totalCharacters - 1 && currentStrokeIndex >= totalStrokes - 1 && strokeProgress >= 1}
          className="w-10 h-10 flex items-center justify-center rounded-full bg-[#e8e0cf] hover:bg-[#d8cfb8] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="下一笔"
        >
          <SkipForward className="w-4 h-4" />
        </button>
      </div>
      
      <div className="mt-4">
        <div className="flex gap-2 overflow-x-auto scrollbar-ink pb-2">
          {generatedCharacters.map((char, index) => (
            <div
              key={index}
              onClick={() => handleCharacterClick(index)}
              className={`flex-shrink-0 w-16 h-16 flex items-center justify-center rounded-lg cursor-pointer transition-all ${
                index === currentCharacterIndex
                  ? 'bg-[#c41e3a] text-white'
                  : 'bg-[#e8e0cf] text-[#1a1a1a] hover:bg-[#d8cfb8]'
              }`}
            >
              <span className="font-calligraphy text-2xl">{char.character}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
