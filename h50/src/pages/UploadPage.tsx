import { useState, useCallback, useRef } from 'react';
import { Upload, RotateCw, Sliders, Play, X, Image as ImageIcon, FileText } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';

interface PreprocessOptions {
  rotation: number;
  threshold: number;
  autoContrast: boolean;
  deskew: boolean;
}

export default function UploadPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState('');
  const [preprocessOptions, setPreprocessOptions] = useState<PreprocessOptions>({
    rotation: 0,
    threshold: 128,
    autoContrast: true,
    deskew: true,
  });

  const handleFileSelect = useCallback((file: File) => {
    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件');
      return;
    }

    setFileName(file.name);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setProgress(0);
    setProgressText('');
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleFileSelect(files[0]);
      }
    },
    [handleFileSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleFileSelect(files[0]);
      }
    },
    [handleFileSelect]
  );

  const handleClearImage = useCallback(() => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setFileName('');
    setProgress(0);
    setProgressText('');
    setPreprocessOptions({
      rotation: 0,
      threshold: 128,
      autoContrast: true,
      deskew: true,
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [previewUrl]);

  const handleRotate = useCallback(() => {
    setPreprocessOptions((prev) => ({
      ...prev,
      rotation: (prev.rotation + 90) % 360,
    }));
  }, []);

  const handleStartRecognition = useCallback(async () => {
    if (!previewUrl) return;

    setIsProcessing(true);
    setProgress(0);
    setProgressText('正在上传图片...');

    const steps = [
      { progress: 20, text: '正在上传图片...' },
      { progress: 40, text: '正在预处理图像...' },
      { progress: 60, text: '正在检测减字位置...' },
      { progress: 80, text: '正在识别减字组件...' },
      { progress: 100, text: '识别完成，正在跳转...' },
    ];

    for (const step of steps) {
      await new Promise((resolve) => setTimeout(resolve, 800));
      setProgress(step.progress);
      setProgressText(step.text);
    }

    await new Promise((resolve) => setTimeout(resolve, 500));
    navigate('/editor', { state: { imageUrl: previewUrl, fileName } });
  }, [previewUrl, navigate, fileName]);

  return (
    <div className="min-h-screen bg-xuanzhi">
      <header className="bg-tanmu text-xuanzhi py-6 px-8 shadow-lg">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-3xl font-kai font-bold">古琴减字谱识别系统</h1>
          <p className="text-xuanzhi/80 mt-1">上传谱面图像，智能识别减字谱</p>
        </div>
      </header>

      <main className="max-w-6xl mx-auto p-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={!previewUrl ? handleClick : undefined}
              className={cn(
                'relative border-4 border-dashed rounded-xl transition-all duration-300 min-h-[500px] flex items-center justify-center overflow-hidden',
                isDragging
                  ? 'border-zhusha bg-zhusha/10 scale-[1.02]'
                  : previewUrl
                    ? 'border-tanmu/30 bg-xuanzhi-dark cursor-default'
                    : 'border-tanmu/50 bg-xuanzhi-dark hover:border-zhusha/70 hover:bg-xuanzhi cursor-pointer'
              )}
              style={{
                backgroundImage: previewUrl
                  ? 'none'
                  : `
                    radial-gradient(circle at 20% 30%, rgba(74, 44, 26, 0.05) 0%, transparent 50%),
                    radial-gradient(circle at 80% 70%, rgba(192, 57, 43, 0.05) 0%, transparent 50%),
                    repeating-linear-gradient(
                      0deg,
                      transparent,
                      transparent 20px,
                      rgba(74, 44, 26, 0.03) 20px,
                      rgba(74, 44, 26, 0.03) 21px
                    )
                  `,
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleInputChange}
                className="hidden"
              />

              {previewUrl ? (
                <>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleClearImage();
                    }}
                    className="absolute top-4 right-4 z-10 p-2 bg-tanmu/80 text-xuanzhi rounded-full hover:bg-zhusha transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                  <div
                    className="max-w-full max-h-full p-8 transition-transform duration-300"
                    style={{ transform: `rotate(${preprocessOptions.rotation}deg)` }}
                  >
                    <img
                      src={previewUrl}
                      alt="预览"
                      className="max-w-full max-h-[450px] object-contain shadow-2xl"
                      style={{
                        filter: preprocessOptions.autoContrast
                          ? 'contrast(1.1) brightness(1.05)'
                          : 'none',
                      }}
                    />
                  </div>
                  <div className="absolute bottom-4 left-4 right-4 bg-tanmu/80 text-xuanzhi px-4 py-2 rounded-lg text-sm flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    <span className="truncate">{fileName}</span>
                  </div>
                </>
              ) : (
                <div className="text-center p-12">
                  <div
                    className={cn(
                      'w-24 h-24 mx-auto mb-6 rounded-full flex items-center justify-center transition-colors',
                      isDragging ? 'bg-zhusha/20' : 'bg-tanmu/10'
                    )}
                  >
                    <Upload
                      className={cn(
                        'w-12 h-12 transition-colors',
                        isDragging ? 'text-zhusha' : 'text-tanmu'
                      )}
                    />
                  </div>
                  <h3 className="text-2xl font-kai text-tanmu mb-3">拖拽图片到此处</h3>
                  <p className="text-tanmu/70 mb-6">或点击选择文件</p>
                  <div className="flex items-center justify-center gap-4 text-sm text-tanmu/60">
                    <span className="flex items-center gap-1">
                      <ImageIcon className="w-4 h-4" />
                      支持 JPG、PNG、BMP
                    </span>
                    <span>建议分辨率 300DPI 以上</span>
                  </div>
                </div>
              )}

              {isProcessing && (
                <div className="absolute inset-0 bg-xuanzhi/95 flex flex-col items-center justify-center z-20">
                  <div className="w-64 mb-6">
                    <div className="text-center mb-4">
                      <div className="text-4xl font-kai text-zhusha font-bold mb-2">
                        {progress}%
                      </div>
                      <p className="text-tanmu">{progressText}</p>
                    </div>
                    <div className="h-3 bg-tanmu/20 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-zhusha to-zhusha-light transition-all duration-500 ease-out"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {[0, 1, 2, 3, 4].map((i) => (
                      <div
                        key={i}
                        className={cn(
                          'w-3 h-3 rounded-full transition-all duration-300',
                          progress > i * 20 ? 'bg-zhusha' : 'bg-tanmu/30'
                        )}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-xuanzhi-dark rounded-xl p-6 border border-tanmu/20 shadow-lg">
              <h3 className="text-lg font-kai font-bold text-tanmu mb-4 flex items-center gap-2">
                <Sliders className="w-5 h-5" />
                预处理选项
              </h3>

              <div className="space-y-5">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm text-tanmu/70">图像旋转</label>
                    <button
                      onClick={handleRotate}
                      disabled={!previewUrl}
                      className={cn(
                        'p-2 rounded-lg transition-colors flex items-center gap-1 text-sm',
                        previewUrl
                          ? 'bg-tanmu/10 text-tanmu hover:bg-tanmu/20'
                          : 'bg-tanmu/5 text-tanmu/40 cursor-not-allowed'
                      )}
                    >
                      <RotateCw className="w-4 h-4" />
                      {preprocessOptions.rotation}°
                    </button>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm text-tanmu/70">二值化阈值</label>
                    <span className="text-sm font-mono text-tanmu">
                      {preprocessOptions.threshold}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="255"
                    value={preprocessOptions.threshold}
                    onChange={(e) =>
                      setPreprocessOptions((prev) => ({
                        ...prev,
                        threshold: parseInt(e.target.value),
                      }))
                    }
                    disabled={!previewUrl}
                    className="w-full h-2 bg-tanmu/20 rounded-lg appearance-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed accent-zhusha"
                  />
                  <div className="flex justify-between text-xs text-tanmu/50 mt-1">
                    <span>偏暗</span>
                    <span>适中</span>
                    <span>偏亮</span>
                  </div>
                </div>

                <div className="space-y-3 pt-2 border-t border-tanmu/10">
                  <label className="flex items-center justify-between cursor-pointer">
                    <span className="text-sm text-tanmu/70">自动对比度</span>
                    <div
                      onClick={() =>
                        setPreprocessOptions((prev) => ({
                          ...prev,
                          autoContrast: !prev.autoContrast,
                        }))
                      }
                      className={cn(
                        'w-10 h-6 rounded-full transition-colors relative',
                        preprocessOptions.autoContrast ? 'bg-zhusha' : 'bg-tanmu/30'
                      )}
                    >
                      <div
                        className={cn(
                          'absolute top-1 w-4 h-4 bg-white rounded-full transition-transform',
                          preprocessOptions.autoContrast ? 'translate-x-5' : 'translate-x-1'
                        )}
                      />
                    </div>
                  </label>

                  <label className="flex items-center justify-between cursor-pointer">
                    <span className="text-sm text-tanmu/70">自动倾斜校正</span>
                    <div
                      onClick={() =>
                        setPreprocessOptions((prev) => ({
                          ...prev,
                          deskew: !prev.deskew,
                        }))
                      }
                      className={cn(
                        'w-10 h-6 rounded-full transition-colors relative',
                        preprocessOptions.deskew ? 'bg-zhusha' : 'bg-tanmu/30'
                      )}
                    >
                      <div
                        className={cn(
                          'absolute top-1 w-4 h-4 bg-white rounded-full transition-transform',
                          preprocessOptions.deskew ? 'translate-x-5' : 'translate-x-1'
                        )}
                      />
                    </div>
                  </label>
                </div>
              </div>
            </div>

            <button
              onClick={handleStartRecognition}
              disabled={!previewUrl || isProcessing}
              className={cn(
                'w-full py-4 px-6 rounded-xl font-kai font-bold text-lg transition-all flex items-center justify-center gap-3 shadow-lg',
                previewUrl && !isProcessing
                  ? 'bg-gradient-to-r from-zhusha to-zhusha-light text-xuanzhi hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]'
                  : 'bg-tanmu/30 text-xuanzhi/50 cursor-not-allowed'
              )}
            >
              <Play className="w-6 h-6" />
              开始识别
            </button>

            <div className="bg-xuanzhi-dark rounded-xl p-5 border border-tanmu/20">
              <h4 className="text-sm font-kai font-bold text-tanmu mb-3">使用说明</h4>
              <ul className="text-sm text-tanmu/70 space-y-2">
                <li className="flex items-start gap-2">
                  <span className="text-zhusha mt-0.5">•</span>
                  上传清晰的古琴减字谱扫描件或照片
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-zhusha mt-0.5">•</span>
                  调整预处理参数优化识别效果
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-zhusha mt-0.5">•</span>
                  点击开始识别，等待处理完成
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-zhusha mt-0.5">•</span>
                  在编辑器中校对和修改识别结果
                </li>
              </ul>
            </div>
          </div>
        </div>
      </main>

      <footer className="bg-tanmu text-xuanzhi/60 py-4 px-8 mt-12 text-center text-sm">
        <p>古琴减字谱智能识别系统 · 传承千年琴韵</p>
      </footer>
    </div>
  );
}
