import { useRef, useEffect, useState, useCallback } from 'react';
import type { ScoreEditorProps, BBox } from '@/types';

interface Transform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

interface ViewState {
  isDragging: boolean;
  lastX: number;
  lastY: number;
  highlightIndex: number;
}

export default function ScoreEditor({
  imageUrl,
  jianziList,
  selectedId,
  onSelect,
}: ScoreEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const animationRef = useRef<number>(0);

  const [transform, setTransform] = useState<Transform>({
    scale: 1,
    offsetX: 0,
    offsetY: 0,
  });

  const [viewState, setViewState] = useState<ViewState>({
    isDragging: false,
    lastX: 0,
    lastY: 0,
    highlightIndex: -1,
  });

  const [imageLoaded, setImageLoaded] = useState(false);

  const screenToImageCoords = useCallback(
    (screenX: number, screenY: number): { x: number; y: number } | null => {
      const canvas = canvasRef.current;
      const image = imageRef.current;
      if (!canvas || !image) return null;

      const rect = canvas.getBoundingClientRect();
      const canvasX = screenX - rect.left;
      const canvasY = screenY - rect.top;

      const imageX = (canvasX - transform.offsetX) / transform.scale;
      const imageY = (canvasY - transform.offsetY) / transform.scale;

      if (imageX < 0 || imageX > image.width || imageY < 0 || imageY > image.height) {
        return null;
      }

      return { x: imageX, y: imageY };
    },
    [transform]
  );

  const bboxContainsPoint = useCallback((bbox: BBox, x: number, y: number): boolean => {
    return (
      x >= bbox.x &&
      x <= bbox.x + bbox.width &&
      y >= bbox.y &&
      y <= bbox.y + bbox.height
    );
  }, []);

  const handleCanvasClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (viewState.isDragging) return;

      const coords = screenToImageCoords(e.clientX, e.clientY);
      if (!coords) {
        onSelect(null);
        return;
      }

      for (let i = jianziList.length - 1; i >= 0; i--) {
        const jianzi = jianziList[i];
        if (bboxContainsPoint(jianzi.bbox, coords.x, coords.y)) {
          onSelect(jianzi.id);
          return;
        }
      }

      onSelect(null);
    },
    [jianziList, onSelect, screenToImageCoords, bboxContainsPoint, viewState.isDragging]
  );

  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    setTransform((prev) => {
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const newScale = Math.max(0.1, Math.min(5, prev.scale * delta));

      const scaleFactor = newScale / prev.scale;
      const newOffsetX = mouseX - (mouseX - prev.offsetX) * scaleFactor;
      const newOffsetY = mouseY - (mouseY - prev.offsetY) * scaleFactor;

      return {
        scale: newScale,
        offsetX: newOffsetX,
        offsetY: newOffsetY,
      };
    });
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (e.button === 0) {
      setViewState((prev) => ({
        ...prev,
        isDragging: true,
        lastX: e.clientX,
        lastY: e.clientY,
      }));
    }
  }, []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!viewState.isDragging) return;

      const deltaX = e.clientX - viewState.lastX;
      const deltaY = e.clientY - viewState.lastY;

      setTransform((prev) => ({
        ...prev,
        offsetX: prev.offsetX + deltaX,
        offsetY: prev.offsetY + deltaY,
      }));

      setViewState((prev) => ({
        ...prev,
        lastX: e.clientX,
        lastY: e.clientY,
      }));
    },
    [viewState.isDragging, viewState.lastX, viewState.lastY]
  );

  const handleMouseUp = useCallback(() => {
    setViewState((prev) => ({
      ...prev,
      isDragging: false,
    }));
  }, []);

  const handleMouseLeave = useCallback(() => {
    setViewState((prev) => ({
      ...prev,
      isDragging: false,
    }));
  }, []);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    const image = imageRef.current;

    if (!canvas || !ctx || !image) return;

    const time = Date.now() / 1000;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = '#2D1A0F';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.translate(transform.offsetX, transform.offsetY);
    ctx.scale(transform.scale, transform.scale);

    ctx.drawImage(image, 0, 0);

    jianziList.forEach((jianzi, index) => {
      const isSelected = jianzi.id === selectedId;
      const isHighlighted = index === viewState.highlightIndex;

      const { x, y, width, height } = jianzi.bbox;

      let pulseAlpha = 0.15;
      let borderWidth = 2;

      if (isHighlighted) {
        pulseAlpha = 0.3 + 0.2 * Math.sin(time * 4);
        borderWidth = 4;
      } else if (isSelected) {
        pulseAlpha = 0.25 + 0.1 * Math.sin(time * 2);
        borderWidth = 3;
      }

      if (isSelected || isHighlighted) {
        ctx.fillStyle = `rgba(192, 57, 43, ${pulseAlpha})`;
        ctx.fillRect(x, y, width, height);
      }

      ctx.strokeStyle = isSelected || isHighlighted ? '#C0392B' : '#4A2C1A';
      ctx.lineWidth = borderWidth / transform.scale;
      ctx.strokeRect(x, y, width, height);

      ctx.fillStyle = isSelected || isHighlighted ? '#C0392B' : '#4A2C1A';
      ctx.font = `${14 / transform.scale}px KaiTi, serif`;
      ctx.fillText(`#${index + 1}`, x, y - 5 / transform.scale);

      const confidenceText = `${(jianzi.confidence * 100).toFixed(0)}%`;
      ctx.font = `${10 / transform.scale}px Arial, sans-serif`;
      ctx.fillStyle = 'rgba(74, 44, 26, 0.8)';
      ctx.fillText(confidenceText, x + width - 40 / transform.scale, y - 5 / transform.scale);
    });

    ctx.restore();

    animationRef.current = requestAnimationFrame(draw);
  }, [transform, jianziList, selectedId, viewState.highlightIndex]);

  useEffect(() => {
    if (!imageUrl) return;

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      imageRef.current = img;
      setImageLoaded(true);

      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (canvas && container) {
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;

        const scaleX = canvas.width / img.width;
        const scaleY = canvas.height / img.height;
        const scale = Math.min(scaleX, scaleY, 1) * 0.9;

        const offsetX = (canvas.width - img.width * scale) / 2;
        const offsetY = (canvas.height - img.height * scale) / 2;

        setTransform({ scale, offsetX, offsetY });
      }
    };
    img.src = imageUrl;

    return () => {
      img.onload = null;
    };
  }, [imageUrl]);

  useEffect(() => {
    if (!imageLoaded) return;

    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const resizeObserver = new ResizeObserver(() => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, [imageLoaded]);

  useEffect(() => {
    if (imageLoaded) {
      animationRef.current = requestAnimationFrame(draw);
    }
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [draw, imageLoaded]);

  const handleHighlightPlay = useCallback(() => {
    if (jianziList.length === 0) return;

    let index = 0;
    const playNext = () => {
      if (index >= jianziList.length) {
        setViewState((prev) => ({ ...prev, highlightIndex: -1 }));
        return;
      }
      setViewState((prev) => ({ ...prev, highlightIndex: index }));
      index++;
      setTimeout(playNext, 500);
    };
    playNext();
  }, [jianziList]);

  const handleResetView = useCallback(() => {
    const image = imageRef.current;
    const canvas = canvasRef.current;
    if (!image || !canvas) return;

    const scaleX = canvas.width / image.width;
    const scaleY = canvas.height / image.height;
    const scale = Math.min(scaleX, scaleY, 1) * 0.9;

    const offsetX = (canvas.width - image.width * scale) / 2;
    const offsetY = (canvas.height - image.height * scale) / 2;

    setTransform({ scale, offsetX, offsetY });
  }, []);

  const handleZoomIn = useCallback(() => {
    setTransform((prev) => ({
      ...prev,
      scale: Math.min(5, prev.scale * 1.2),
    }));
  }, []);

  const handleZoomOut = useCallback(() => {
    setTransform((prev) => ({
      ...prev,
      scale: Math.max(0.1, prev.scale / 1.2),
    }));
  }, []);

  return (
    <div className="flex flex-col h-full bg-tanmu-dark">
      <div className="flex items-center justify-between px-4 py-2 bg-tanmu border-b border-tanmu-light">
        <div className="flex items-center gap-2">
          <button
            onClick={handleZoomOut}
            className="px-3 py-1 text-xuanzhi bg-tanmu-light hover:bg-tanmu rounded transition-colors"
          >
            −
          </button>
          <span className="text-xuanzhi text-sm min-w-[60px] text-center">
            {(transform.scale * 100).toFixed(0)}%
          </span>
          <button
            onClick={handleZoomIn}
            className="px-3 py-1 text-xuanzhi bg-tanmu-light hover:bg-tanmu rounded transition-colors"
          >
            +
          </button>
          <button
            onClick={handleResetView}
            className="px-3 py-1 text-xuanzhi bg-tanmu-light hover:bg-tanmu rounded transition-colors text-sm"
          >
            重置视图
          </button>
        </div>
        <button
          onClick={handleHighlightPlay}
          className="px-4 py-1 text-xuanzhi bg-zhusha hover:bg-zhusha-light rounded transition-colors text-sm"
        >
          播放高亮
        </button>
      </div>
      <div
        ref={containerRef}
        className="flex-1 relative overflow-hidden"
        style={{ cursor: viewState.isDragging ? 'grabbing' : 'grab' }}
      >
        <canvas
          ref={canvasRef}
          onClick={handleCanvasClick}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
          className="block w-full h-full"
        />
        {!imageLoaded && (
          <div className="absolute inset-0 flex items-center justify-center text-xuanzhi text-lg">
            加载中...
          </div>
        )}
      </div>
      <div className="px-4 py-2 bg-tanmu border-t border-tanmu-light text-xuanzhi text-xs text-center">
        滚轮缩放 · 拖拽平移 · 点击选择减字
      </div>
    </div>
  );
}
