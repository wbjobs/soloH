import React, { useState, useRef } from 'react';
import { Upload, X, Image as ImageIcon } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { processSampleImage } from '../utils/characterGenerator';

interface SampleUploaderProps {
  className?: string;
}

export const SampleUploader: React.FC<SampleUploaderProps> = ({ className = '' }) => {
  const { addSample, samples } = useAppStore();
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingIndex, setProcessingIndex] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList) => {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file.type.startsWith('image/')) continue;

      setIsProcessing(true);
      setProcessingIndex(i);
      
      try {
        const imageData = await readFileAsDataURL(file);
        const defaultChar = String.fromCharCode(0x4e00 + samples.length);
        const style = await processSampleImage(
          imageData,
          defaultChar,
          `样本 ${samples.length + 1}`
        );
        addSample(style);
      } catch (error) {
        console.error('处理图片失败:', error);
        alert('图片处理失败，请确保图片清晰且包含单个汉字');
      }
    }
    
    setIsProcessing(false);
    setProcessingIndex(null);
  };

  const readFileAsDataURL = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
  };

  return (
    <div className={`${className}`}>
      <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a]">样本上传</h3>
      
      <div
        className={`upload-zone rounded-lg p-8 text-center cursor-pointer ${isDragging ? 'drag-over' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={handleFileChange}
        />
        
        {isProcessing ? (
          <div className="animate-pulse">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-[#c41e3a]/20 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-[#c41e3a] border-t-transparent rounded-full animate-spin" />
            </div>
            <p className="text-[#6b6b6b]">正在处理图片 {processingIndex !== null ? `(${processingIndex + 1})` : ''}...</p>
          </div>
        ) : (
          <>
            <Upload className="w-12 h-12 mx-auto mb-3 text-[#6b6b6b]" />
            <p className="text-[#3d3d3d] font-semibold mb-1">点击或拖拽上传样本字</p>
            <p className="text-sm text-[#6b6b6b]">支持 JPG、PNG 格式，楷书或行书为佳</p>
          </>
        )}
      </div>

      {samples.length > 0 && (
        <div className="mt-4">
          <p className="text-sm text-[#6b6b6b] mb-2">已上传样本 ({samples.length})</p>
          <div className="grid grid-cols-4 gap-2">
            {samples.map((sample, index) => (
              <SampleThumbnail key={sample.id} sample={sample} index={index} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

interface SampleThumbnailProps {
  sample: ReturnType<typeof useAppStore.getState>['samples'][0];
  index: number;
}

const SampleThumbnail: React.FC<SampleThumbnailProps> = ({ sample, index }) => {
  const { removeSample, selectedSampleId, setSelectedSampleId } = useAppStore();
  const isSelected = selectedSampleId === sample.id;

  return (
    <div 
      className={`relative group cursor-pointer rounded overflow-hidden border-2 transition-all ${
        isSelected ? 'border-[#c41e3a] shadow-md' : 'border-[#6b6b6b]/30 hover:border-[#3d3d3d]'
      }`}
      onClick={() => setSelectedSampleId(isSelected ? null : sample.id)}
    >
      <img 
        src={sample.originalImage} 
        alt={`样本 ${index + 1}`}
        className="w-full aspect-square object-cover"
      />
      <div className="absolute top-1 left-1 bg-[#1a1a1a] text-[#f5f0e6] text-xs px-1.5 py-0.5 rounded font-calligraphy">
        {index + 1}
      </div>
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-1">
        <p className="text-white text-xs truncate text-center font-calligraphy">{sample.character}</p>
      </div>
      <button
        className="absolute top-1 right-1 w-5 h-5 bg-[#c41e3a] text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
        onClick={(e) => {
          e.stopPropagation();
          removeSample(sample.id);
        }}
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
};
