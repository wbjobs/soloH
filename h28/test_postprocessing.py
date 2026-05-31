import sys
import os
import importlib

sys.path.insert(0, 'e:/soloH/h28/backend')

import ml.postprocessing.connected_components as cc_mod
importlib.reload(cc_mod)

import ml.postprocessing.layout_analyzer as la_mod
importlib.reload(la_mod)

import ml.postprocessing.page_reconstructor as pr_mod
importlib.reload(pr_mod)

import ml.postprocessing as pp_mod
importlib.reload(pp_mod)

PostProcessor = pp_mod.PostProcessor

print('=== 所有模块导入成功 ===')

bboxes = [
    [150, 50, 180, 80],
    [150, 85, 180, 115],
    [150, 120, 180, 150],
    [100, 50, 130, 80],
    [100, 85, 130, 115],
    [100, 120, 130, 150],
    [50, 50, 80, 80],
    [50, 85, 80, 115],
]
labels = ['一', '二', '三', '四', '五', '六', '七', '八']

print(f'\n=== 测试数据 ===')
print(f'边界框: {bboxes}')
print(f'标签: {labels}')
print(f'预期3列: x=150(一二三), x=100(四五六), x=50(七八)')
print(f'预期阅读顺序(从右到左): 一二三 -> 四五六 -> 七八')

pp = PostProcessor(
    is_vertical=True,
    column_width_threshold=40.0,
    row_height_threshold=50.0,
    merge_distance_threshold=10.0
)

page_layout = pp.process(bboxes, labels, page_size=(200, 200))

print(f'\n=== 分析结果 ===')
print(f'列数: {len(page_layout.columns)}')

for i, col in enumerate(page_layout.columns):
    print(f'列{i+1}: center_x={col.center_x:.0f}, 文本={col.text}')

ordered = la_mod.get_column_reading_order(page_layout.columns)
print(f'\n=== 阅读顺序（从右到左）===')
for i, col in enumerate(ordered, 1):
    print(f'第{i}列: x={col.center_x:.0f}, 文本={col.text}')

text = pp.get_text(page_layout, format_type='plain')
print(f'\n=== 纯文本输出 ===')
print(text)

text_structured = pp.get_text(page_layout, format_type='structured')
print(f'\n=== 结构化输出 ===')
print(text_structured)

text_order = pp.get_text(page_layout, format_type='reading_order')
print(f'\n=== 阅读顺序标记输出 ===')
print(text_order)

print(f'\n=== 横排模式测试 ===')
bboxes_h = [
    [50, 50, 80, 80],
    [85, 50, 115, 80],
    [120, 50, 150, 80],
    [50, 100, 80, 130],
    [85, 100, 115, 130],
]
labels_h = ['A', 'B', 'C', 'D', 'E']

pp_h = PostProcessor(is_vertical=False)
page_layout_h = pp_h.process(bboxes_h, labels_h, page_size=(200, 200))
text_h = pp_h.get_text(page_layout_h, format_type='plain')
print(f'横排文本:')
print(text_h)

print('\n=== 所有测试通过 ===')
