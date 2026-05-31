import sys
sys.path.insert(0, '.')

from ml import CTPNDetector, CRNNRecognizer, BERTPunctuator, PostProcessor
import numpy as np

print('=== 模块导入测试 ===')
print('CTPNDetector:', CTPNDetector)
print('CRNNRecognizer:', CRNNRecognizer)
print('BERTPunctuator:', BERTPunctuator)
print('PostProcessor:', PostProcessor)

print('\n=== 懒加载测试 ===')
detector = CTPNDetector(use_mock=True)
print('detector._is_loaded (before):', detector._is_loaded)
detector.load_model()
print('detector._is_loaded (after):', detector._is_loaded)

print('\n=== 检测测试 ===')
mock_image = np.zeros((800, 600, 3), dtype=np.uint8)
boxes = detector.detect(mock_image, num_columns=2, num_lines=5)
print(f'检测到 {len(boxes)} 个文本框')
if boxes:
    print('第一个框:', boxes[0])

print('\n=== 识别测试 ===')
recognizer = CRNNRecognizer(use_mock=True)
recognizer.load_model()
result = recognizer.recognize(mock_image, return_candidates=True, top_k=3)
print('识别结果:', result['text'])
print('置信度:', result['confidence'])
print('候选词数量:', len(result.get('candidates', [])))
if result.get('candidates'):
    for cand in result['candidates']:
        print(f'  - {cand["text"]} (conf: {cand["confidence"]}, variant: {cand["is_variant"]})')

print('\n=== 标点恢复测试 ===')
punctuator = BERTPunctuator(use_mock=True)
punctuator.load_model()
text = '先帝創業未半而中道崩殂今天下三分益州疲弊'
punct_result = punctuator.punctuate(text)
print('原文:', text)
print('加标点后:', punct_result['punctuated_text'])
print('标点数量:', len(punct_result['punctuations']))

print('\n=== 后处理测试 ===')
processor = PostProcessor()
processor.load_model()
boxes = detector.detect(mock_image, num_columns=2, num_lines=3)
rec_results = [recognizer.recognize(mock_image, text_index=i) for i in range(len(boxes))]
punct_results = [punctuator.punctuate(r['text']) for r in rec_results]
final_result = processor.process(boxes, rec_results, punct_results)
print('处理统计:', final_result['processing_stats'])
print('最终文本长度:', len(final_result['full_text']))

print('\n=== 上下文管理器测试 ===')
with CTPNDetector(use_mock=True) as d:
    print('在with块中已加载:', d._is_loaded)
print('退出with块后已加载:', d._is_loaded)

print('\n=== 所有测试通过! ===')
