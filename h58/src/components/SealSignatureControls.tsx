import React, { useState } from 'react';
import { Stamp, PenTool, Move, RotateCw, Type, Palette } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

interface SealSignatureControlsProps {
  className?: string;
}

export const SealSignatureControls: React.FC<SealSignatureControlsProps> = ({ className = '' }) => {
  const { seal, signature, setSeal, setSignature } = useAppStore();
  const [activeTab, setActiveTab] = useState<'seal' | 'signature'>('seal');

  const presetSeals = [
    { text: '墨韵', label: '墨韵' },
    { text: '手书', label: '手书' },
    { text: '某某之印', label: '之印' },
    { text: '珍藏', label: '珍藏' },
  ];

  const presetSignatures = [
    { text: '手书', label: '手书' },
    { text: '敬书', label: '敬书' },
    { text: '戏墨', label: '戏墨' },
    { text: '某某书', label: '某书' },
  ];

  return (
    <div className={`${className}`}>
      <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a] flex items-center gap-2">
        <Stamp className="w-5 h-5 text-[#c41e3a]" />
        落款与印章
      </h3>
      
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setActiveTab('signature')}
          className={`flex-1 py-2 px-3 text-sm rounded flex items-center justify-center gap-1 transition-all ${
            activeTab === 'signature'
              ? 'bg-[#1a1a1a] text-[#f5f0e6]'
              : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
          }`}
        >
          <PenTool className="w-4 h-4" />
          落款
        </button>
        <button
          onClick={() => setActiveTab('seal')}
          className={`flex-1 py-2 px-3 text-sm rounded flex items-center justify-center gap-1 transition-all ${
            activeTab === 'seal'
              ? 'bg-[#1a1a1a] text-[#f5f0e6]'
              : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
          }`}
        >
          <Stamp className="w-4 h-4" />
          印章
        </button>
      </div>
      
      {activeTab === 'signature' && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="signature-enabled"
              checked={signature.enabled}
              onChange={(e) => setSignature({ enabled: e.target.checked })}
              className="w-4 h-4 accent-[#c41e3a]"
            />
            <label htmlFor="signature-enabled" className="text-sm text-[#3d3d3d]">
              启⽤落款
            </label>
          </div>
          
          <div>
            <label className="text-xs text-[#6b6b6b] mb-1 block">落款文本</label>
            <input
              type="text"
              value={signature.text}
              onChange={(e) => setSignature({ text: e.target.value })}
              placeholder="输入落款文字"
              maxLength={10}
              className="w-full px-3 py-2 border border-[#d8cfb8] rounded bg-white text-sm focus:outline-none focus:border-[#c41e3a]"
            />
          </div>
          
          <div className="flex flex-wrap gap-1">
            {presetSignatures.map((preset) => (
              <button
                key={preset.label}
                onClick={() => setSignature({ text: preset.text, enabled: true })}
                className="px-2 py-1 text-xs bg-[#e8e0cf] hover:bg-[#d8cfb8] rounded transition-colors"
              >
                {preset.label}
              </button>
            ))}
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
                <Type className="w-4 h-4 text-[#6b6b6b]" />
                字号
              </label>
              <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
                {signature.fontSize}px
              </span>
            </div>
            <input
              type="range"
              min="10"
              max="36"
              value={signature.fontSize}
              onChange={(e) => setSignature({ fontSize: parseInt(e.target.value) })}
              className="w-full slider-ink"
            />
          </div>
          
          <div>
            <label className="text-xs text-[#6b6b6b] mb-1 block">书体风格</label>
            <div className="flex gap-2">
              {(['regular', 'running', 'cursive'] as const).map((style) => (
                <button
                  key={style}
                  onClick={() => setSignature({ style })}
                  className={`flex-1 py-1 text-xs rounded transition-all ${
                    signature.style === style
                      ? 'bg-[#c41e3a] text-white'
                      : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
                  }`}
                >
                  {style === 'regular' ? '楷书' : style === 'running' ? '行书' : '草书'}
                </button>
              ))}
            </div>
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
                <Move className="w-4 h-4 text-[#6b6b6b]" />
                水平位置
              </label>
              <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
                {signature.positionX}%
              </span>
            </div>
            <input
              type="range"
              min="10"
              max="95"
              value={signature.positionX}
              onChange={(e) => setSignature({ positionX: parseInt(e.target.value) })}
              className="w-full slider-ink"
            />
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
                <Move className="w-4 h-4 text-[#6b6b6b]" />
                垂直位置
              </label>
              <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
                {signature.positionY}%
              </span>
            </div>
            <input
              type="range"
              min="50"
              max="95"
              value={signature.positionY}
              onChange={(e) => setSignature({ positionY: parseInt(e.target.value) })}
              className="w-full slider-ink"
            />
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
                <RotateCw className="w-4 h-4 text-[#6b6b6b]" />
                旋转角度
              </label>
              <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
                {signature.rotation}°
              </span>
            </div>
            <input
              type="range"
              min="-15"
              max="15"
              value={signature.rotation}
              onChange={(e) => setSignature({ rotation: parseInt(e.target.value) })}
              className="w-full slider-ink"
            />
          </div>
          
          <div>
            <label className="text-sm text-[#3d3d3d] flex items-center gap-1 mb-1">
              <Palette className="w-4 h-4 text-[#6b6b6b]" />
              墨色
            </label>
            <div className="flex gap-2">
              {['#1a1a1a', '#3d3d3d', '#6b6b6b', '#c41e3a'].map((color) => (
                <button
                  key={color}
                  onClick={() => setSignature({ color })}
                  className={`w-8 h-8 rounded-full border-2 transition-all ${
                    signature.color === color ? 'border-[#c41e3a] scale-110' : 'border-transparent'
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
        </div>
      )}
      
      {activeTab === 'seal' && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="seal-enabled"
              checked={seal.enabled}
              onChange={(e) => setSeal({ enabled: e.target.checked })}
              className="w-4 h-4 accent-[#c41e3a]"
            />
            <label htmlFor="seal-enabled" className="text-sm text-[#3d3d3d]">
              启⽤印章
            </label>
          </div>
          
          <div>
            <label className="text-xs text-[#6b6b6b] mb-1 block">印章文字</label>
            <input
              type="text"
              value={seal.text}
              onChange={(e) => setSeal({ text: e.target.value })}
              placeholder="输入印章文字（1-4字）"
              maxLength={4}
              className="w-full px-3 py-2 border border-[#d8cfb8] rounded bg-white text-sm focus:outline-none focus:border-[#c41e3a]"
            />
          </div>
          
          <div className="flex flex-wrap gap-1">
            {presetSeals.map((preset) => (
              <button
                key={preset.label}
                onClick={() => setSeal({ text: preset.text, enabled: true })}
                className="px-2 py-1 text-xs bg-[#e8e0cf] hover:bg-[#d8cfb8] rounded transition-colors"
              >
                {preset.label}
              </button>
            ))}
          </div>
          
          <div>
            <label className="text-xs text-[#6b6b6b] mb-1 block">印章形状</label>
            <div className="flex gap-2">
              {(['square', 'circle', 'oval'] as const).map((style) => (
                <button
                  key={style}
                  onClick={() => setSeal({ style })}
                  className={`flex-1 py-2 text-xs rounded transition-all ${
                    seal.style === style
                      ? 'bg-[#c41e3a] text-white'
                      : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
                  }`}
                >
                  {style === 'square' ? '方形' : style === 'circle' ? '圆形' : '椭圆'}
                </button>
              ))}
            </div>
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
                <Type className="w-4 h-4 text-[#6b6b6b]" />
                印章大小
              </label>
              <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
                {seal.size}px
              </span>
            </div>
            <input
              type="range"
              min="20"
              max="80"
              value={seal.size}
              onChange={(e) => setSeal({ size: parseInt(e.target.value) })}
              className="w-full slider-ink"
            />
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
                <Move className="w-4 h-4 text-[#6b6b6b]" />
                水平位置
              </label>
              <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
                {seal.positionX}%
              </span>
            </div>
            <input
              type="range"
              min="10"
              max="95"
              value={seal.positionX}
              onChange={(e) => setSeal({ positionX: parseInt(e.target.value) })}
              className="w-full slider-ink"
            />
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
                <Move className="w-4 h-4 text-[#6b6b6b]" />
                垂直位置
              </label>
              <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
                {seal.positionY}%
              </span>
            </div>
            <input
              type="range"
              min="50"
              max="95"
              value={seal.positionY}
              onChange={(e) => setSeal({ positionY: parseInt(e.target.value) })}
              className="w-full slider-ink"
            />
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
                <RotateCw className="w-4 h-4 text-[#6b6b6b]" />
                旋转角度
              </label>
              <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
                {seal.rotation}°
              </span>
            </div>
            <input
              type="range"
              min="-15"
              max="15"
              value={seal.rotation}
              onChange={(e) => setSeal({ rotation: parseInt(e.target.value) })}
              className="w-full slider-ink"
            />
          </div>
          
          <div>
            <label className="text-sm text-[#3d3d3d] flex items-center gap-1 mb-1">
              <Palette className="w-4 h-4 text-[#6b6b6b]" />
              印泥颜色
            </label>
            <div className="flex gap-2">
              {['#c41e3a', '#8b0000', '#dc143c', '#1a1a1a'].map((color) => (
                <button
                  key={color}
                  onClick={() => setSeal({ color })}
                  className={`w-8 h-8 rounded-full border-2 transition-all ${
                    seal.color === color ? 'border-[#1a1a1a] scale-110' : 'border-transparent'
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-[#3d3d3d]">
                不透明度
              </label>
              <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
                {Math.round(seal.opacity * 100)}%
              </span>
            </div>
            <input
              type="range"
              min="50"
              max="100"
              value={Math.round(seal.opacity * 100)}
              onChange={(e) => setSeal({ opacity: parseInt(e.target.value) / 100 })}
              className="w-full slider-ink"
            />
          </div>
        </div>
      )}
    </div>
  );
};
