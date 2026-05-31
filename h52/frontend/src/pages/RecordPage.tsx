import { useNavigate } from 'react-router-dom';
import { VideoRecorder } from '@/components/video/VideoRecorder';
import { Info } from 'lucide-react';

export function RecordPage() {
  const navigate = useNavigate();

  const handleComplete = (resultId: string) => {
    navigate(`/result/${resultId}`);
  };

  return (
    <div className="min-h-screen pt-24 pb-12">
      <div className="container mx-auto px-4">
      <div className="text-center mb-10">
        <h1 className="text-4xl font-bold font-display mb-4">
          视频<span className="text-gradient">情感分析</span>
        </h1>
        <p className="text-muted-foreground max-w-2xl mx-auto">
          录制一段约1分钟的视频，系统将自动分析您的语音、面部表情和文本内容，
          提供多模态情感分析结果
        </p>
      </div>

      <div className="mb-8">
        <div className="glass-card p-4 mb-6">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
            <div className="text-sm text-muted-foreground">
              <p className="font-medium text-foreground mb-1">录制提示</p>
              <ul className="space-y-1">
                <li>• 请确保光线充足，面部清晰可见</li>
                <li>• 建议在安静环境中录制以获得更好的语音识别效果</li>
                <li>• 录制时请自然表达，系统将分析约60秒的视频内容</li>
                <li>• 所有数据仅用于本次分析使用，不会永久存储</li>
              </ul>
            </div>
          </div>
        </div>

        <VideoRecorder onComplete={handleComplete} />
      </div>

      <div className="grid md:grid-cols-3 gap-6 mt-12">
        {[
          { step: '01', title: '视频录制', desc: '通过WebRTC安全采集音视频' },
          { step: '02', title: '多模态分析', desc: '提取语音、表情、文本特征' },
          { step: '03', title: '情感识别', desc: 'Transformer跨模态融合预测' },
        ].map((item, index) => (
          <div
            key={item.step}
            className="glass-card p-6 text-center animate-slide-up"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <div className="text-4xl font-bold text-primary/30 font-display mb-2">
              {item.step}
            </div>
            <h3 className="text-lg font-semibold mb-1">{item.title}</h3>
            <p className="text-sm text-muted-foreground">{item.desc}</p>
          </div>
        ))}
      </div>
    </div>
    </div>
  );
}

export default RecordPage;
