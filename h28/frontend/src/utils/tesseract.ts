import { createWorker, type Worker, PSM } from 'tesseract.js';
import type { TextBox, PageResult, TextLine } from '../types';
import { getImageUrl } from '../api';

type PageSegMode = 'auto' | 'block' | 'line' | 'word' | 'vertical';

class TesseractOCR {
  private worker: Worker | null = null;
  private isInitialized = false;
  private useFallback = false;

  async init(pageSegMode: PageSegMode = 'auto'): Promise<void> {
    if (this.isInitialized && this.worker) {
      return;
    }

    const psmMap: Record<PageSegMode, PSM> = {
      auto: PSM.AUTO,
      block: PSM.SINGLE_BLOCK,
      line: PSM.SINGLE_LINE,
      word: PSM.SINGLE_WORD,
      vertical: PSM.SINGLE_BLOCK_VERT_TEXT,
    };

    try {
      this.worker = await createWorker(['chi_tra', 'chi_sim', 'eng'], 1, {
        logger: (m) => console.log('[Tesseract]', m),
      });

      await this.worker.setParameters({
        preserve_interword_spaces: '1',
        tessedit_pageseg_mode: psmMap[pageSegMode],
      });

      this.isInitialized = true;
      this.useFallback = false;
    } catch (error) {
      console.warn('[Tesseract] Failed to initialize, using fallback mode');
      this.useFallback = true;
      this.isInitialized = true;
    }
  }

  private bboxToQuadPoints(bbox: { x0: number; y0: number; x1: number; y1: number }): {
    x1: number; y1: number; x2: number; y2: number;
    x3: number; y3: number; x4: number; y4: number;
  } {
    return {
      x1: bbox.x0, y1: bbox.y0,
      x2: bbox.x1, y2: bbox.y0,
      x3: bbox.x1, y3: bbox.y1,
      x4: bbox.x0, y4: bbox.y1,
    };
  }

  async recognize(
    image: string | File | HTMLImageElement | HTMLCanvasElement,
    onProgress?: (progress: number, stage: string) => void,
    pageSegMode: PageSegMode = 'auto'
  ): Promise<{ text: string; confidence: number; textLines: TextLine[] }> {
    if (!this.isInitialized) {
      await this.init(pageSegMode);
    }

    if (onProgress) {
      onProgress(10, 'initializing');
    }

    if (this.useFallback) {
      return this.fallbackRecognize(image, onProgress);
    }

    try {
      if (onProgress) {
        onProgress(30, 'recognizing');
      }

      const result = await this.worker!.recognize(image);
      const { data } = result;

      if (onProgress) {
        onProgress(80, 'processing');
      }

      const textLines: TextLine[] = [];

      if (data.lines) {
        data.lines.forEach((line, lineIndex) => {
          if (line.bbox) {
            const quadPoints = this.bboxToQuadPoints(line.bbox);
            const textBox: TextBox = {
              id: `box-${lineIndex}`,
              ...quadPoints,
              confidence: line.confidence || 0,
            };

            const textLine: TextLine = {
              id: `line-${lineIndex}`,
              textBox,
              content: line.text || '',
              confidence: line.confidence || 0,
              candidates: line.words?.flatMap((w) => w.choices?.map((c) => c.text) || []) || [],
              columnIndex: 0,
              lineIndex,
            };

            textLines.push(textLine);
          }
        });
      }

      if (onProgress) {
        onProgress(100, 'completed');
      }

      return {
        text: data.text || '',
        confidence: data.confidence || 0,
        textLines,
      };
    } catch (error) {
      console.warn('[Tesseract] Recognition failed, using fallback:', error);
      return this.fallbackRecognize(image, onProgress);
    }
  }

  private async fallbackRecognize(
    image: string | File | HTMLImageElement | HTMLCanvasElement,
    onProgress?: (progress: number, stage: string) => void
  ): Promise<{ text: string; confidence: number; textLines: TextLine[] }> {
    if (onProgress) {
      onProgress(50, 'fallback_recognizing');
    }

    const textLines: TextLine[] = [];

    if (image instanceof HTMLImageElement || image instanceof HTMLCanvasElement) {
      const width = image instanceof HTMLImageElement ? image.width : image.width;
      const height = image instanceof HTMLImageElement ? image.height : image.height;

      const textBox: TextBox = {
        id: 'box-fallback',
        x1: 0, y1: 0,
        x2: width, y2: 0,
        x3: width, y3: height,
        x4: 0, y4: height,
        confidence: 0,
      };

      textLines.push({
        id: 'line-fallback',
        textBox,
        content: '',
        confidence: 0,
        candidates: [],
        columnIndex: 0,
        lineIndex: 0,
      });
    }

    if (onProgress) {
      onProgress(100, 'completed');
    }

    return {
      text: '',
      confidence: 0,
      textLines,
    };
  }

  async recognizeImageFile(
    file: File,
    onProgress?: (progress: number, stage: string) => void,
    options: { verticalText?: boolean } = {}
  ): Promise<PageResult> {
    const img = new Image();
    const url = URL.createObjectURL(file);

    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error('Failed to load image'));
      img.src = url;
    });

    const pageSegMode: PageSegMode = options.verticalText ? 'vertical' : 'auto';
    const result = await this.recognize(file, onProgress, pageSegMode);

    const columns: TextLine[][] = [result.textLines];

    URL.revokeObjectURL(url);

    return {
      pageNumber: 1,
      width: img.width,
      height: img.height,
      imageUrl: getImageUrl(url),
      textLines: result.textLines,
      columns,
    };
  }

  async recognizeVerticalText(
    image: string | File | HTMLImageElement | HTMLCanvasElement,
    onProgress?: (progress: number, stage: string) => void
  ): Promise<{ text: string; confidence: number; textLines: TextLine[] }> {
    return this.recognize(image, onProgress, 'vertical');
  }

  async terminate(): Promise<void> {
    if (this.worker) {
      await this.worker.terminate();
      this.worker = null;
    }
    this.isInitialized = false;
    this.useFallback = false;
  }
}

export const tesseractOCR = new TesseractOCR();

export const generateId = (): string => {
  return `id-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

export const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
};

export const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export default tesseractOCR;
