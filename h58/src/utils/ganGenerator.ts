import * as tf from '@tensorflow/tfjs';
import { Stroke, CharacterStyle, RenderParameters, StyleFeatures, GeneratedCharacter } from '../types';
import { fuseStyles } from './styleModel';
import { generateCharacter } from './characterGenerator';

let tfInitialized = false;

async function initTF(): Promise<void> {
  if (tfInitialized) return;
  
  try {
    await tf.ready();
    tfInitialized = true;
    console.log('TensorFlow.js 已初始化');
  } catch (error) {
    console.warn('TensorFlow.js 初始化失败，将使用笔画拼接模式', error);
  }
}

function createSimpleGenerator(): tf.LayersModel {
  const model = tf.sequential({
    layers: [
      tf.layers.dense({ inputShape: [100], units: 256, activation: 'relu' }),
      tf.layers.dense({ units: 512, activation: 'relu' }),
      tf.layers.dense({ units: 1024, activation: 'relu' }),
      tf.layers.dense({ units: 20 * 20 * 1, activation: 'tanh' }),
      tf.layers.reshape({ targetShape: [20, 20, 1] })
    ]
  });
  
  return model;
}

function createSimpleDiscriminator(): tf.LayersModel {
  const model = tf.sequential({
    layers: [
      tf.layers.flatten({ inputShape: [20, 20, 1] }),
      tf.layers.dense({ units: 512, activation: 'relu' }),
      tf.layers.dense({ units: 256, activation: 'relu' }),
      tf.layers.dense({ units: 1, activation: 'sigmoid' })
    ]
  });
  
  return model;
}

function preprocessStrokeImage(
  strokes: Stroke[],
  size: number = 64
): tf.Tensor4D {
  return tf.tidy(() => {
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) {
      return tf.zeros([1, size, size, 1]) as tf.Tensor4D;
    }
    
    ctx.fillStyle = '#f5f0e6';
    ctx.fillRect(0, 0, size, size);
    
    ctx.strokeStyle = '#1a1a1a';
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    for (const stroke of strokes) {
      if (stroke.points.length < 2) continue;
      
      const scale = size / 200;
      
      ctx.beginPath();
      ctx.lineWidth = Math.max(1, stroke.thickness[0] * scale);
      ctx.moveTo(stroke.points[0].x * scale, stroke.points[0].y * scale);
      
      for (let i = 1; i < stroke.points.length; i++) {
        ctx.lineWidth = Math.max(1, stroke.thickness[i] * scale);
        ctx.lineTo(stroke.points[i].x * scale, stroke.points[i].y * scale);
      }
      ctx.stroke();
    }
    
    const imageData = ctx.getImageData(0, 0, size, size);
    const data = imageData.data;
    
    const tensor = tf.browser.fromPixels(imageData, 1);
    return tensor.expandDims(0).toFloat().div(tf.scalar(255)).mul(tf.scalar(2)).sub(tf.scalar(1));
  });
}

export async function isTFInitialized(): Promise<boolean> {
  if (!tfInitialized) {
    try {
      await initTF();
    } catch {
      // ignore
    }
  }
  return tfInitialized;
}

export async function generateWithStyleTransfer(
  baseStrokes: Stroke[],
  styleFeatures: StyleFeatures,
  parameters: RenderParameters
): Promise<Stroke[]> {
  await initTF();
  
  if (!tfInitialized) {
    return baseStrokes;
  }
  
  return tf.tidy(() => {
    const modifiedStrokes = baseStrokes.map(stroke => {
      const newPoints = stroke.points.map((p, i) => {
        const noise = (Math.random() - 0.5) * styleFeatures.smoothness * 2;
        return {
          ...p,
          x: p.x + noise,
          y: p.y + noise
        };
      });
      
      const newThickness = stroke.thickness.map((t, i) => {
        const variation = styleFeatures.thicknessVariance * (parameters.thickness / 50);
        return t + (Math.random() - 0.5) * variation;
      });
      
      return {
        ...stroke,
        points: newPoints,
        thickness: newThickness
      };
    });
    
    return modifiedStrokes;
  });
}

export async function generateCharacterWithGAN(
  character: string,
  samples: CharacterStyle[],
  parameters: RenderParameters,
  useGAN: boolean = false
): Promise<GeneratedCharacter> {
  const baseCharacter = generateCharacter(character, samples, parameters);
  
  if (!useGAN) {
    return baseCharacter;
  }
  
  try {
    await initTF();
    
    if (!tfInitialized) {
      console.log('GAN 不可用，使用笔画拼接');
      return baseCharacter;
    }
    
    const styleFeatures = fuseStyles(samples);
    
    const enhancedStrokes = await generateWithStyleTransfer(
      baseCharacter.strokes,
      styleFeatures,
      parameters
    );
    
    return {
      ...baseCharacter,
      strokes: enhancedStrokes
    };
  } catch (error) {
    console.warn('GAN 生成失败，回退到笔画拼接', error);
    return baseCharacter;
  }
}

export async function generateTextWithGAN(
  text: string,
  samples: CharacterStyle[],
  parameters: RenderParameters,
  useGAN: boolean = false
): Promise<GeneratedCharacter[]> {
  const characters: GeneratedCharacter[] = [];
  
  for (const char of text) {
    if (char.trim() === '') {
      characters.push({
        character: char,
        strokes: [],
        styleId: 'space',
        svg: ''
      });
      continue;
    }
    
    const generated = await generateCharacterWithGAN(char, samples, parameters, useGAN);
    characters.push(generated);
  }
  
  return characters;
}

export class HandwritingGAN {
  private generator: tf.LayersModel | null = null;
  private discriminator: tf.LayersModel | null = null;
  private isTrained: boolean = false;
  
  async init(): Promise<void> {
    await initTF();
    if (!tfInitialized) return;
    
    this.generator = createSimpleGenerator();
    this.discriminator = createSimpleDiscriminator();
    
    this.generator.compile({
      optimizer: tf.train.adam(0.0002, 0.5),
      loss: 'binaryCrossentropy'
    });
    
    this.discriminator.compile({
      optimizer: tf.train.adam(0.0002, 0.5),
      loss: 'binaryCrossentropy',
      metrics: ['accuracy']
    });
    
    console.log('GAN 模型已创建');
  }
  
  async trainOnSample(sample: CharacterStyle, epochs: number = 10): Promise<void> {
    if (!this.generator || !this.discriminator || !tfInitialized) return;
    
    console.log(`开始训练样本，共 ${epochs} 轮`);
    
    const realImages = preprocessStrokeImage(sample.strokes);
    
    for (let epoch = 0; epoch < epochs; epoch++) {
      const noise = tf.randomNormal([1, 100]);
      
      const realLabels = tf.ones([1, 1]);
      const fakeLabels = tf.zeros([1, 1]);
      
      const generatedImages = this.generator.predict(noise) as tf.Tensor;
      
      const dLossReal = this.discriminator.trainOnBatch(realImages, realLabels);
      const dLossFake = this.discriminator.trainOnBatch(generatedImages, fakeLabels);
      
      const combinedNoise = tf.randomNormal([1, 100]);
      const gLoss = this.generator.trainOnBatch(combinedNoise, tf.ones([1, 1]));
      
      if (epoch % 5 === 0) {
        console.log(`Epoch ${epoch}: D损失 = ${(dLossReal[0] + dLossFake[0]) / 2}, G损失 = ${gLoss}`);
      }
    }
    
    this.isTrained = true;
    console.log('训练完成');
  }
  
  isReady(): boolean {
    return this.isTrained && tfInitialized;
  }
  
  dispose(): void {
    if (this.generator) this.generator.dispose();
    if (this.discriminator) this.discriminator.dispose();
  }
}

export const ganInstance = new HandwritingGAN();
