import { ProcessedImage } from '../types';

export function loadImageToCanvas(imageData: string): Promise<HTMLCanvasElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const maxSize = 512;
      let width = img.width;
      let height = img.height;
      
      if (width > maxSize || height > maxSize) {
        if (width > height) {
          height = (height / width) * maxSize;
          width = maxSize;
        } else {
          width = (width / height) * maxSize;
          height = maxSize;
        }
      }
      
      canvas.width = Math.floor(width);
      canvas.height = Math.floor(height);
      
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('无法获取Canvas上下文'));
        return;
      }
      
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      
      resolve(canvas);
    };
    img.onerror = reject;
    img.src = imageData;
  });
}

export function getGrayscaleData(canvas: HTMLCanvasElement): Uint8ClampedArray {
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('无法获取Canvas上下文');
  
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = imageData.data;
  const grayscale = new Uint8ClampedArray(canvas.width * canvas.height);
  
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    grayscale[i / 4] = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
  }
  
  return grayscale;
}

export function otsuThreshold(grayscale: Uint8ClampedArray): number {
  const histogram = new Array(256).fill(0);
  
  for (let i = 0; i < grayscale.length; i++) {
    histogram[grayscale[i]]++;
  }
  
  let sum = 0;
  for (let i = 0; i < 256; i++) {
    sum += i * histogram[i];
  }
  
  let sumB = 0;
  let wB = 0;
  let wF = 0;
  let maxVariance = 0;
  let threshold = 128;
  const total = grayscale.length;
  
  for (let i = 0; i < 256; i++) {
    wB += histogram[i];
    if (wB === 0) continue;
    
    wF = total - wB;
    if (wF === 0) break;
    
    sumB += i * histogram[i];
    const mB = sumB / wB;
    const mF = (sum - sumB) / wF;
    
    const betweenVariance = wB * wF * (mB - mF) * (mB - mF);
    
    if (betweenVariance > maxVariance) {
      maxVariance = betweenVariance;
      threshold = i;
    }
  }
  
  return threshold;
}

export function binarize(grayscale: Uint8ClampedArray, width: number, height: number, threshold?: number): Uint8ClampedArray {
  if (threshold === undefined) {
    threshold = otsuThreshold(grayscale);
  }
  
  const binary = new Uint8ClampedArray(width * height);
  
  for (let i = 0; i < grayscale.length; i++) {
    binary[i] = grayscale[i] < threshold ? 255 : 0;
  }
  
  return binary;
}

export function medianFilter(binary: Uint8ClampedArray, width: number, height: number, kernelSize: number = 3): Uint8ClampedArray {
  const result = new Uint8ClampedArray(width * height);
  const half = Math.floor(kernelSize / 2);
  
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const values: number[] = [];
      
      for (let ky = -half; ky <= half; ky++) {
        for (let kx = -half; kx <= half; kx++) {
          const px = Math.max(0, Math.min(width - 1, x + kx));
          const py = Math.max(0, Math.min(height - 1, y + ky));
          values.push(binary[py * width + px]);
        }
      }
      
      values.sort((a, b) => a - b);
      result[y * width + x] = values[Math.floor(values.length / 2)];
    }
  }
  
  return result;
}

export function zhangSuenThinning(binary: Uint8ClampedArray, width: number, height: number): Uint8ClampedArray {
  const skeleton = new Uint8ClampedArray(binary);
  let changed = true;
  
  while (changed) {
    changed = false;
    
    const toDelete = new Set<number>();
    
    for (let y = 1; y < height - 1; y++) {
      for (let x = 1; x < width - 1; x++) {
        const idx = y * width + x;
        if (skeleton[idx] !== 255) continue;
        
        const p2 = skeleton[(y - 1) * width + x] === 255 ? 1 : 0;
        const p3 = skeleton[(y - 1) * width + (x + 1)] === 255 ? 1 : 0;
        const p4 = skeleton[y * width + (x + 1)] === 255 ? 1 : 0;
        const p5 = skeleton[(y + 1) * width + (x + 1)] === 255 ? 1 : 0;
        const p6 = skeleton[(y + 1) * width + x] === 255 ? 1 : 0;
        const p7 = skeleton[(y + 1) * width + (x - 1)] === 255 ? 1 : 0;
        const p8 = skeleton[y * width + (x - 1)] === 255 ? 1 : 0;
        const p9 = skeleton[(y - 1) * width + (x - 1)] === 255 ? 1 : 0;
        
        const neighbors = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9;
        if (neighbors < 2 || neighbors > 6) continue;
        
        let transitions = 0;
        const sequence = [p2, p3, p4, p5, p6, p7, p8, p9, p2];
        for (let i = 0; i < 8; i++) {
          if (sequence[i] === 0 && sequence[i + 1] === 1) {
            transitions++;
          }
        }
        if (transitions !== 1) continue;
        
        if (p2 * p4 * p6 === 0 && p4 * p6 * p8 === 0) {
          toDelete.add(idx);
        }
      }
    }
    
    for (const idx of toDelete) {
      skeleton[idx] = 0;
      changed = true;
    }
    toDelete.clear();
    
    for (let y = 1; y < height - 1; y++) {
      for (let x = 1; x < width - 1; x++) {
        const idx = y * width + x;
        if (skeleton[idx] !== 255) continue;
        
        const p2 = skeleton[(y - 1) * width + x] === 255 ? 1 : 0;
        const p3 = skeleton[(y - 1) * width + (x + 1)] === 255 ? 1 : 0;
        const p4 = skeleton[y * width + (x + 1)] === 255 ? 1 : 0;
        const p5 = skeleton[(y + 1) * width + (x + 1)] === 255 ? 1 : 0;
        const p6 = skeleton[(y + 1) * width + x] === 255 ? 1 : 0;
        const p7 = skeleton[(y + 1) * width + (x - 1)] === 255 ? 1 : 0;
        const p8 = skeleton[y * width + (x - 1)] === 255 ? 1 : 0;
        const p9 = skeleton[(y - 1) * width + (x - 1)] === 255 ? 1 : 0;
        
        const neighbors = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9;
        if (neighbors < 2 || neighbors > 6) continue;
        
        let transitions = 0;
        const sequence = [p2, p3, p4, p5, p6, p7, p8, p9, p2];
        for (let i = 0; i < 8; i++) {
          if (sequence[i] === 0 && sequence[i + 1] === 1) {
            transitions++;
          }
        }
        if (transitions !== 1) continue;
        
        if (p2 * p4 * p8 === 0 && p2 * p6 * p8 === 0) {
          toDelete.add(idx);
        }
      }
    }
    
    for (const idx of toDelete) {
      skeleton[idx] = 0;
      changed = true;
    }
  }
  
  return skeleton;
}

export function distanceTransform(binary: Uint8ClampedArray, width: number, height: number): Float32Array {
  const dist = new Float32Array(width * height);
  const INF = width + height;
  
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      dist[y * width + x] = binary[y * width + x] === 255 ? 0 : INF;
    }
  }
  
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = y * width + x;
      if (x > 0) {
        dist[idx] = Math.min(dist[idx], dist[idx - 1] + 1);
      }
      if (y > 0) {
        dist[idx] = Math.min(dist[idx], dist[idx - width] + 1);
      }
    }
  }
  
  for (let y = height - 1; y >= 0; y--) {
    for (let x = width - 1; x >= 0; x--) {
      const idx = y * width + x;
      if (x < width - 1) {
        dist[idx] = Math.min(dist[idx], dist[idx + 1] + 1);
      }
      if (y < height - 1) {
        dist[idx] = Math.min(dist[idx], dist[idx + width] + 1);
      }
    }
  }
  
  return dist;
}

export async function processImage(imageData: string): Promise<ProcessedImage & { distanceMap: Float32Array }> {
  const canvas = await loadImageToCanvas(imageData);
  const { width, height } = canvas;
  
  const grayscale = getGrayscaleData(canvas);
  let binary = binarize(grayscale, width, height);
  binary = medianFilter(binary, width, height, 3);
  
  const skeleton = zhangSuenThinning(binary, width, height);
  const distanceMap = distanceTransform(binary, width, height);
  
  return {
    width,
    height,
    binaryData: binary,
    skeletonData: skeleton,
    distanceMap
  };
}

export function createCanvasFromData(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  foreground: string = '#000000',
  background: string = '#ffffff'
): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('无法获取Canvas上下文');
  
  ctx.fillStyle = background;
  ctx.fillRect(0, 0, width, height);
  
  const imageData = ctx.createImageData(width, height);
  const pixels = imageData.data;
  
  const fgRgb = hexToRgb(foreground);
  const bgRgb = hexToRgb(background);
  
  for (let i = 0; i < data.length; i++) {
    const isForeground = data[i] > 0;
    const rgb = isForeground ? fgRgb : bgRgb;
    pixels[i * 4] = rgb.r;
    pixels[i * 4 + 1] = rgb.g;
    pixels[i * 4 + 2] = rgb.b;
    pixels[i * 4 + 3] = 255;
  }
  
  ctx.putImageData(imageData, 0, 0);
  return canvas;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : { r: 0, g: 0, b: 0 };
}
