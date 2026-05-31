import type { LSystemConfig, LSystemRule, EnvironmentParams, GrowthModifier } from '../types';

export class LSystemParser {
  static applyRules(
    current: string,
    rules: LSystemRule[],
    randomness: number,
    random: () => number = Math.random
  ): string {
    let result = '';
    let bracketDepth = 0;
    
    for (let i = 0; i < current.length; i++) {
      const symbol = current[i];
      
      if (symbol === '[') bracketDepth++;
      if (symbol === ']') bracketDepth = Math.max(0, bracketDepth - 1);
      
      const rule = rules.find(r => r.predecessor === symbol);
      
      if (rule) {
        let selected = this.selectSuccessor(rule.successors, random);
        
        if (randomness > 0 && random() < randomness * 0.1) {
          selected = this.mutate(selected, randomness, random, bracketDepth);
        }
        
        result += selected;
        
        for (const ch of selected) {
          if (ch === '[') bracketDepth++;
          if (ch === ']') bracketDepth = Math.max(0, bracketDepth - 1);
        }
      } else {
        result += symbol;
      }
    }
    
    return result;
  }

  private static selectSuccessor(
    successors: Array<{ string: string; probability: number }>,
    random: () => number
  ): string {
    const r = random();
    let cumulative = 0;
    
    for (const s of successors) {
      cumulative += s.probability;
      if (r <= cumulative) {
        return s.string;
      }
    }
    
    return successors[successors.length - 1].string;
  }

  private static mutate(str: string, randomness: number, random: () => number, initialBracketDepth: number): string {
    const growthSymbols = ['F', 'A', 'B', 'C', 'X'];
    const rotationSymbols = ['+', '-', '&', '^', '\\', '/', '|'];
    let result = '';
    let bracketDepth = initialBracketDepth;
    let pendingOpens = 0;
    
    for (let i = 0; i < str.length; i++) {
      const char = str[i];
      const remaining = str.length - i;
      
      if (char === '[') pendingOpens++;
      if (char === ']') pendingOpens = Math.max(0, pendingOpens - 1);
      
      if (random() < randomness * 0.05) {
        const effectiveDepth = bracketDepth + pendingOpens;
        const canClose = effectiveDepth > 0;
        const canOpen = remaining > pendingOpens + 2;
        
        let symbolPool: string[];
        
        if (canOpen && random() < 0.25) {
          symbolPool = ['['];
        } else if (canClose && random() < 0.25 && pendingOpens > 0) {
          symbolPool = [']'];
        } else if (random() < 0.6) {
          symbolPool = growthSymbols;
        } else {
          symbolPool = rotationSymbols;
        }
        
        const newSymbol = symbolPool[Math.floor(random() * symbolPool.length)];
        result += newSymbol;
        
        if (newSymbol === '[') pendingOpens++;
        if (newSymbol === ']') pendingOpens = Math.max(0, pendingOpens - 1);
      } else {
        result += char;
      }
    }
    
    while (pendingOpens > 0) {
      result += ']';
      pendingOpens--;
    }
    
    return result;
  }

  static generate(
    config: LSystemConfig,
    iterations: number,
    onProgress?: (progress: number) => void
  ): string {
    let current = config.axiom;
    
    for (let i = 0; i < iterations; i++) {
      current = this.applyRules(current, config.rules, config.randomness);
      if (onProgress) {
        onProgress((i + 1) / iterations);
      }
    }
    
    return current;
  }

  static applyEnvironmentModifiers(
    config: LSystemConfig,
    env: EnvironmentParams
  ): GrowthModifier {
    const avgEnv = (env.light + env.water + env.nutrients + env.temperature) / 4;
    
    const growthRate = 0.5 + avgEnv * 1.5;
    
    const branchAngle = config.angle * (0.7 + env.temperature * 0.6);
    
    const leafSize = config.leafSize * (0.5 + env.light * 0.8 + env.water * 0.7);
    
    const stepLength = config.stepLength * (0.5 + env.nutrients * 0.8 + env.water * 0.5);
    
    const trunkRadius = config.trunkRadius * (0.6 + env.nutrients * 0.8);
    
    return {
      growthRate,
      branchAngle,
      leafSize,
      stepLength,
      trunkRadius
    };
  }
}
