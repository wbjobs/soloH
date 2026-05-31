import { useEffect, useRef } from 'react';
import { useAudioStore } from '../../store/useAudioStore';

export const SpectrumChart = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const { frequencyData, currentBand, isPlaying } = useAudioStore();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const draw = () => {
      const width = canvas.width;
      const height = canvas.height;

      ctx.clearRect(0, 0, width, height);

      const gradient = ctx.createLinearGradient(0, height, 0, 0);
      gradient.addColorStop(0, currentBand.color + '40');
      gradient.addColorStop(0.5, currentBand.color + 'aa');
      gradient.addColorStop(1, currentBand.color);

      const barCount = 64;
      const barWidth = width / barCount - 2;
      const dataStep = Math.floor(frequencyData.length / barCount);

      for (let i = 0; i < barCount; i++) {
        const dataIndex = i * dataStep;
        const value = isPlaying ? frequencyData[dataIndex] : 0;
        const barHeight = (value / 255) * height * 0.9;

        const x = i * (barWidth + 2);
        const y = height - barHeight;

        ctx.fillStyle = gradient;
        ctx.shadowColor = currentBand.color;
        ctx.shadowBlur = isPlaying ? 10 : 0;
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, 2);
        ctx.fill();
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
  }, [frequencyData, currentBand, isPlaying]);

  return (
    <canvas
      ref={canvasRef}
      width={800}
      height={100}
      className="w-full h-full"
    />
  );
};
