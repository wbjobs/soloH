# Emotional TTS - 情感语音合成命令行工具

一个基于Python的情感语音合成命令行工具，集成Tacotron2/FastSpeech + WaveGlow/HiFi-GAN架构，支持情感控制、说话人自适应等高级功能。

## 功能特性

- **多情感支持**: 中性、高兴、悲伤、生气、惊讶五种情感
- **情感强度控制**: 0-1连续调节情感表达强度
- **混合情感**: 支持多种情感混合（如70%高兴 + 30%惊讶）
- **情感编码方式**: 
  - 参考音频编码（Reference Encoder）
  - 韵律参数直接调节（音高、时长、能量）
- **声码器选择**: 支持WaveGlow和HiFi-GAN两种声码器
- **情感验证**: 内置情感分类器验证合成质量
- **说话人自适应**: 支持从目标说话人几秒录音进行情感迁移
- **批量合成**: 支持批量文本合成

## 项目结构

```
h62/
├── src/
│   ├── models/              # 模型架构
│   │   ├── tacotron2.py     # Tacotron2模型
│   │   ├── waveglow.py      # WaveGlow声码器
│   │   ├── hifigan.py       # HiFi-GAN声码器
│   │   └── reference_encoder.py  # 参考编码器
│   ├── emotion/             # 情感控制模块
│   │   ├── emotion_controller.py  # 情感控制器
│   │   └── emotion_classifier.py  # 情感分类器
│   ├── speaker/             # 说话人自适应模块
│   │   └── speaker_adapter.py     # 说话人适配器
│   ├── inference/           # 推理引擎
│   │   ├── tts_engine.py    # TTS引擎核心
│   │   └── cli.py           # 命令行接口
│   └── utils/               # 工具模块
│       ├── config.py        # 配置管理
│       ├── audio.py         # 音频处理
│       └── text.py          # 文本处理
├── config.yaml              # 配置文件
├── requirements.txt         # 依赖列表
├── main.py                  # 主入口
└── README.md                # 本文档
```

## 安装

```bash
# 克隆项目
cd e:\soloH\h62

# 安装依赖
pip install -r requirements.txt
```

## 快速开始

### 1. 查看可用情感

```bash
python main.py list-emotions
```

### 2. 基础语音合成

```bash
# 单情感合成
python main.py synthesize --text "Hello, world!" --emotion happy

# 带强度控制
python main.py synthesize --text "Hello, world!" --emotion happy:0.8

# 混合情感（70%高兴 + 30%惊讶）
python main.py synthesize --text "Hello, world!" --emotion "happy+surprise:0.7+0.3"
```

### 3. 使用参考音频编码

```bash
python main.py synthesize \
  --text "Hello, world!" \
  --emotion happy \
  --reference-audio ./reference_audio/happy_example.wav
```

### 4. 韵律参数调节

```bash
# 提升音高，增加能量，加快语速
python main.py synthesize \
  --text "Hello, world!" \
  --emotion happy \
  --pitch-shift 0.5 \
  --energy-scale 1.2 \
  --duration-scale 0.9
```

### 5. 说话人自适应

```bash
# 从目标说话人录音提取说话人嵌入
python main.py adapt \
  --reference-audio ./target_speaker/speech1.wav \
  --reference-audio ./target_speaker/speech2.wav \
  --reference-text "This is the first transcript." \
  --reference-text "This is the second transcript." \
  --save-path ./checkpoints/speaker_embedding.pt \
  --fine-tune

# 使用自适应后的说话人进行合成
python main.py synthesize \
  --text "Hello, world!" \
  --emotion happy \
  --speaker-audio ./target_speaker/speech1.wav
```

### 6. 情感验证

```bash
# 验证已合成的音频
python main.py validate \
  --wav-path ./output/happy_int1.00.wav \
  --target-emotion happy

# 使用预训练分类器验证
python main.py validate \
  --wav-path ./output/happy_int1.00.wav \
  --target-emotion happy \
  --classifier-path ./pretrained/emotion_classifier.pt
```

## 命令详解

### `synthesize` - 语音合成

**参数:**
- `--text, -t`: 待合成的文本（必需）
- `--emotion, -e`: 情感标签（必需）
  - 格式: `happy`, `happy:0.8`, `happy:0.7+surprise:0.3`
- `--intensity, -i`: 情感强度（0.0-1.0，默认1.0）
- `--reference-audio, -r`: 参考音频路径（用于风格编码）
- `--speaker-audio, -s`: 目标说话人音频路径（可多个）
- `--speaker-text, -st`: 说话人音频对应的文本（可多个）
- `--fine-tune`: 是否进行微调（默认False）
- `--pitch-shift`: 音高偏移量（默认0.0）
- `--energy-scale`: 能量缩放因子（默认1.0）
- `--duration-scale`: 时长缩放因子（默认1.0）
- `--validate/--no-validate`: 是否验证合成结果（默认True）
- `--output-dir, -o`: 输出目录（默认./output）
- `--output-filename, -f`: 输出文件名
- `--tacotron-path`: Tacotron2预训练模型路径
- `--reference-encoder-path`: 参考编码器预训练模型路径
- `--vocoder-path`: 声码器预训练模型路径
- `--emotion-embedding-path`: 情感嵌入预训练路径
- `--classifier-path`: 情感分类器预训练路径

### `validate` - 情感验证

**参数:**
- `--wav-path, -w`: 待验证的WAV文件路径（必需）
- `--target-emotion, -e`: 目标情感标签（必需）
- `--target-intensity, -i`: 目标情感强度（默认1.0）
- `--classifier-path`: 预训练分类器路径

### `adapt` - 说话人自适应

**参数:**
- `--reference-audio, -r`: 参考音频路径（必需，可多个）
- `--reference-text, -t`: 参考音频对应的文本（可多个）
- `--emotion, -e`: 自适应时使用的情感
- `--fine-tune/--no-fine-tune`: 是否微调（默认True）
- `--save-path, -s`: 说话人嵌入保存路径
- `--tacotron-path`: Tacotron2预训练模型路径
- `--emotion-embedding-path`: 情感嵌入预训练路径

### `list-emotions` - 列出可用情感

### `version` - 显示版本信息

## 全局选项

- `--config, -c`: 配置文件路径（默认config.yaml）
- `--device, -d`: 设备选择（cpu/cuda，自动检测）
- `--vocoder, -v`: 声码器类型（waveglow/hifigan，默认waveglow）

## 配置文件

主要配置项（config.yaml）:

```yaml
audio:
  sampling_rate: 22050        # 采样率
  n_mel_channels: 80           # Mel频谱通道数
  hop_length: 256              # 帧移
  win_length: 1024             # 帧长

emotion:
  emotions: ["neutral", "happy", "sad", "angry", "surprise"]
  emotion_embedding_dim: 64    # 情感嵌入维度
  prosody_dim: 3               # 韵律特征维度（音高/能量/时长）

speaker_adaptation:
  dvector_dim: 256             # 说话人嵌入维度
  fine_tune_steps: 100         # 微调步数
  learning_rate: 0.0001        # 微调学习率

vocoder:
  type: "waveglow"             # 声码器类型
  n_flows: 12                  # WaveGlow流数
```

## 使用示例脚本

```python
from src.inference.tts_engine import TTSEngine

# 初始化引擎
engine = TTSEngine(
    config_path="config.yaml",
    device="cuda",
    vocoder_type="waveglow",
)

# 加载预训练模型
engine.load_pretrained_models(
    tacotron_path="./pretrained/tacotron2.pt",
    vocoder_path="./pretrained/waveglow.pt",
    emotion_embedding_path="./pretrained/emotion_embeddings.pt",
    classifier_path="./pretrained/emotion_classifier.pt",
)

# 1. 单情感合成
result = engine.synthesize(
    text="Hello, this is a happy voice!",
    emotion="happy",
    intensity=0.8,
    output_dir="./output",
)

print(f"Output: {result.output_path}")
print(f"Quality Score: {result.validation_result['quality_score']:.4f}")

# 2. 混合情感合成
result = engine.synthesize(
    text="Wow, that's amazing!",
    emotion={"happy": 0.7, "surprise": 0.3},
    output_dir="./output",
)

# 3. 说话人自适应
speaker_emb, stats = engine.adapt_speaker(
    reference_audio_paths=["./target_speaker/speech1.wav"],
    reference_texts=["Hello, this is the target speaker."],
    do_fine_tuning=True,
    save_path="./checkpoints/speaker_emb.pt",
)

# 使用自适应说话人合成
result = engine.synthesize(
    text="Hello from the adapted speaker!",
    emotion="happy",
    speaker_embedding=speaker_emb,
    output_dir="./output",
)

# 4. 韵律调节
result = engine.synthesize(
    text="I am very excited!",
    emotion="excited",
    pitch_shift=0.3,
    energy_scale=1.2,
    duration_scale=0.9,
    output_dir="./output",
)
```

## 情感说明

| 情感 | 描述 | 典型韵律特征 |
|------|------|-------------|
| neutral | 中性 | 正常音高、正常语速、中等能量 |
| happy | 高兴 | 音高提升、语速加快、能量增加 |
| sad | 悲伤 | 音高降低、语速减慢、能量降低 |
| angry | 生气 | 音高显著提升、语速加快、能量显著增加 |
| surprise | 惊讶 | 音高提升、语速加快、中等能量 |

## 预训练模型

您需要准备以下预训练模型：
1. **Tacotron2**: 基础TTS模型
2. **Reference Encoder**: 风格/情感编码器
3. **Vocoder**: WaveGlow或HiFi-GAN声码器
4. **Emotion Embeddings**: 情感嵌入表（可选）
5. **Emotion Classifier**: 情感分类器（用于验证）

模型权重可从公开的TTS项目获取，或自行训练。

## 训练说明

### 情感分类器训练

```python
from src.emotion.emotion_classifier import EmotionClassifier
from torch.utils.data import DataLoader

# 初始化模型
classifier = EmotionClassifier(config)
optimizer = torch.optim.Adam(classifier.parameters(), lr=1e-4)
criterion = nn.CrossEntropyLoss()

# 训练循环
for epoch in range(num_epochs):
    for batch in dataloader:
        mels, labels = batch
        logits, probs = classifier(mels)
        loss = criterion(logits, labels)
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
```

### 说话人自适应微调

```python
from src.speaker.speaker_adapter import SpeakerAdaptation

# 初始化适配器
adaptation = SpeakerAdaptation(config, tacotron_model=model)

# 执行自适应
speaker_emb, stats = adaptation.adapt(
    reference_audio_paths=["speaker1.wav", "speaker2.wav"],
    reference_texts=["Text 1", "Text 2"],
    do_fine_tuning=True,
)
```

## 常见问题

**Q: 没有GPU可以使用吗？**
A: 可以，工具会自动检测并使用CPU，但合成速度会较慢。

**Q: 如何添加新的情感类型？**
A: 修改config.yaml中的emotions列表，然后重新训练情感嵌入和分类器。

**Q: 支持中文吗？**
A: 当前版本主要面向英文，可通过修改text.py中的字符集添加中文支持。

**Q: 合成的音频有杂音怎么办？**
A: 尝试以下方法：
   - 确保预训练模型正确加载
   - 调整声码器的sigma参数（WaveGlow）
   - 检查输入文本是否包含特殊字符
   - 调整trim_silence_threshold参数

## 许可证

MIT License

## 参考文献

1. Tacotron2: [Natural TTS Synthesis by Conditioning WaveNet on Mel Spectrogram Predictions](https://arxiv.org/abs/1712.05884)
2. WaveGlow: [A Flow-based Generative Network for Speech Synthesis](https://arxiv.org/abs/1811.00002)
3. HiFi-GAN: [Generative Adversarial Networks for Efficient and High Fidelity Speech Synthesis](https://arxiv.org/abs/2010.05646)
4. Reference Encoder: [Style Tokens: Unsupervised Style Modeling, Control and Transfer in End-to-End Speech Synthesis](https://arxiv.org/abs/1803.09017)
5. D-vector: [Generalized End-to-End Loss for Speaker Verification](https://arxiv.org/abs/1710.10467)
