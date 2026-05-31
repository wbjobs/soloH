import { useEffect, useRef } from 'react';
import { useAudioStore } from '../../store/useAudioStore';

export const WaveformChart = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const { timeDataLeft, timeDataRight, currentBand, isPlaying } = useAudioStore();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const draw = () => {
      const width = canvas.width;
      const height = canvas.height;
      const centerY = height / 2;

      ctx.clearRect(0, 0, width, height);

      ctx.strokeStyle = 'rgba(255,255,255,0.1)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, centerY);
      ctx.lineTo(width, centerY);
      ctx.stroke();

      if (isPlaying) {
        ctx.strokeStyle = currentBand.color;
        ctx.lineWidth = 2;
        ctx.shadowColor = currentBand.color;
        ctx.shadowBlur = 8;
        ctx.beginPath();

        for (let i = 0; i < timeDataLeft.length; i++) {
          const x = (i / timeDataLeft.length) * width;
          const y = centerY + timeDataLeft[i] * centerY * 0.8;

          if (i === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();

        ctx.strokeStyle = '#f59e0b';
        ctx.shadowColor = '#f59e0b';
        ctx.beginPath();
        for (let i = 0; i < timeDataRight.length; i++) {
          const x = (i / timeDataRight.length) * width;
          const y = centerY + timeDataRight[i] * centerY * 0.8 + 2;

          if (i === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
      }

      ctx.shadowBlur = 0;
      animationRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [timeDataLeft, timeDataRight, currentBand, isPlaying]);

  return (
    <canvas
      ref={canvasRef}
      width={800}
      height={80}
      className="w-full h-full"
    />
  );
};
