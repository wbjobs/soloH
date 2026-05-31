import { useEffect, useRef } from 'react';
import { useAudioStore } from '../../store/useAudioStore';

export const PhaseIndicator = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const { phaseDifference, currentBand, isPlaying, averageAmplitude } = useAudioStore();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const draw = () => {
      const width = canvas.width;
      const height = canvas.height;
      const centerX = width / 2;
      const centerY = height / 2;
      const radius = Math.min(width, height) / 2 - 10;

      ctx.clearRect(0, 0, width, height);

      ctx.strokeStyle = 'rgba(255,255,255,0.1)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
      ctx.stroke();

      ctx.strokeStyle = 'rgba(255,255,255,0.05)';
      for (let i = 0; i < 12; i++) {
        const angle = (i / 12) * Math.PI * 2;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(
          centerX + Math.cos(angle) * radius,
          centerY + Math.sin(angle) * radius
        );
        ctx.stroke();
      }

      if (isPlaying) {
        const glowIntensity = 0.5 + averageAmplitude * 0.5;

        const gradient = ctx.createRadialGradient(
          centerX, centerY, 0,
          centerX, centerY, radius
        );
        gradient.addColorStop(0, currentBand.color + Math.floor(glowIntensity * 60).toString(16).padStart(2, '0'));
        gradient.addColorStop(0.7, currentBand.color + '20');
        gradient.addColorStop(1, 'transparent');

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();

        const leftAngle = 0;
        const rightAngle = phaseDifference;

        const leftX = centerX + Math.cos(leftAngle) * radius * 0.8;
        const leftY = centerY + Math.sin(leftAngle) * radius * 0.8;
        const rightX = centerX + Math.cos(rightAngle) * radius * 0.8;
        const rightY = centerY + Math.sin(rightAngle) * radius * 0.8;

        ctx.fillStyle = currentBand.color;
        ctx.shadowColor = currentBand.color;
        ctx.shadowBlur = 15;
        ctx.beginPath();
        ctx.arc(leftX, leftY, 6 + averageAmplitude * 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#f59e0b';
        ctx.shadowColor = '#f59e0b';
        ctx.beginPath();
        ctx.arc(rightX, rightY, 6 + averageAmplitude * 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.shadowBlur = 0;
        ctx.strokeStyle = 'rgba(255,255,255,0.3)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(leftX, leftY);
        ctx.lineTo(rightX, rightY);
        ctx.stroke();
        ctx.setLineDash([]);

        const phaseDegrees = ((phaseDifference * 180) / Math.PI) % 360;
        ctx.fillStyle = 'rgba(255,255,255,0.8)';
        ctx.font = '10px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`相位差: ${phaseDegrees.toFixed(1)}°`, centerX, height - 8);
      }

      animationRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [phaseDifference, currentBand, isPlaying, averageAmplitude]);

  return (
    <canvas
      ref={canvasRef}
      width={120}
      height={120}
      className="w-28 h-28"
    />
  );
};
