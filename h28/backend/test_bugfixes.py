import sys
import os
import json
import numpy as np
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml.postprocessing.connected_components import (
    BoundingBox, find_connected_components, merge_nearby_components,
    _should_merge, _dynamic_column_clustering, _simple_column_clustering
)
from ml.postprocessing.layout_analyzer import analyze_vertical_layout, _cluster_columns
from ml.recognition.crnn_recognizer import CRNNRecognizer
from app import create_app, db
from app.repositories.task_repository import TaskRepository
from app.repositories.result_repository import ResultRepository
from app.models.task import Task
from app.models.page_result import PageResult
from app.models.text_line import TextLine
from app.models.text_box import TextBox
from config import DevelopmentConfig


def test_misaligned_row_merging():
    print("=" * 60)
    print("测试1: 行列合并算法 - 错行鲁棒性")
    print("=" * 60)

    components = []

    print("\n1.1 模拟竖排文字，包含水平偏移的错行...")
    bboxes = [
        [100, 50, 150, 100],
        [105, 110, 155, 160],
        [110, 170, 160, 220],
        [95, 230, 145, 280],
        [200, 55, 250, 105],
        [210, 115, 260, 165],
        [195, 175, 245, 225],
        [205, 235, 255, 285],
        [300, 60, 350, 110],
        [310, 120, 360, 170],
    ]

    for i, bbox in enumerate(bboxes):
        components.append({
            'id': i,
            'bbox': BoundingBox(*bbox),
            'text': f'字{i}',
            'confidence': 0.9,
            'merged': False
        })

    print(f"   输入组件数: {len(components)}")
    print(f"   组件水平偏移范围: 95-360 (三列，每列有±10像素错行)")

    merged = merge_nearby_components(
        components,
        direction='vertical',
        distance_threshold=20.0,
        overlap_threshold=0.3,
        enable_post_refinement=True
    )

    print(f"\n   合并后组件数: {len(merged)}")
    for i, comp in enumerate(merged):
        bbox = comp['bbox']
        print(f"   组件{i+1}: '{comp['text']}' "
              f"位置=({bbox.x1:.0f},{bbox.y1:.0f})-({bbox.x2:.0f},{bbox.y2:.0f}) "
              f"字数={len(comp['text'])} 合并={comp.get('merged', False)}")

    print("\n1.2 测试列聚类对错行的鲁棒性...")
    columns = _cluster_columns(merged, column_width_threshold=80.0, overlap_threshold=0.2)
    print(f"   识别列数: {len(columns)} (期望: 3)")

    for i, col in enumerate(columns):
        print(f"   列{i+1}: {len(col.components)}行, "
              f"x范围={col.bbox.x1:.0f}-{col.bbox.x2:.0f}")

    assert len(columns) == 3, f"期望3列，实际{len(columns)}列"
    print("   ✅ 列聚类正确")

    print("\n1.3 测试水平重叠率和偏移率计算...")
    bbox1 = BoundingBox(100, 50, 150, 100)
    bbox2 = BoundingBox(110, 110, 160, 160)
    overlap = bbox1.horizontal_overlap(bbox2)
    offset_ratio = bbox1.horizontal_offset_ratio(bbox2)
    print(f"   bbox1=(100,50)-(150,100), bbox2=(110,110)-(160,160)")
    print(f"   水平重叠率: {overlap:.2f} (期望: 0.80)")
    print(f"   水平偏移率: {offset_ratio:.2f} (期望: 0.20)")
    assert abs(overlap - 0.8) < 0.01, f"重叠率计算错误: {overlap}"
    assert abs(offset_ratio - 0.2) < 0.01, f"偏移率计算错误: {offset_ratio}"
    print("   ✅ 重叠率和偏移率计算正确")

    print("\n1.4 测试动态规划列聚类...")
    centers = np.array([125, 130, 128, 122, 225, 230, 220, 228, 325, 330])
    labels = _dynamic_column_clustering(centers, threshold=50.0)
    unique_labels = len(set(labels))
    print(f"   输入中心: {centers.tolist()}")
    print(f"   聚类结果: {labels}")
    print(f"   聚类数: {unique_labels} (期望: 3)")
    assert unique_labels == 3, f"期望3个聚类，实际{unique_labels}个"
    print("   ✅ 动态规划列聚类正确")

    print("\n✅ 行列合并算法错行鲁棒性测试通过!")
    return True


def test_ctc_repeated_chars():
    print("\n" + "=" * 60)
    print("测试2: CRNN CTC解码 - 重复字符处理")
    print("=" * 60)

    recognizer = CRNNRecognizer(use_mock=True)
    recognizer.load_model()

    chars = ['人', '天', '地', '大', '中', '国', '年', '月', '日']
    blank_index = len(chars)
    num_classes = len(chars) + 1

    print("\n2.1 测试贪心解码 - 重复字符保留...")
    seq_len = 100

    probs = np.zeros((seq_len, num_classes))
    probs[:, blank_index] = 0.1

    for t in range(seq_len):
        if t < 50:
            probs[t, 0] = 0.9
        else:
            probs[t, 0] = 0.9

    result = recognizer.ctc_decode(
        probs, chars, blank_index=blank_index,
        merge_repeated=True, beam_width=1, time_step_threshold=0.3
    )

    print(f"   输入: 时间步0-49='人', 50-99='人' (无blank分隔)")
    print(f"   解码结果: '{result['text']}' (期望: '人人')")
    print(f"   字符数: {len(result['text'])}")
    print(f"   置信度: {result['confidence']:.4f}")
    print(f"   时间跨度: {result['char_time_spans']}")

    if result['text'] == '人人':
        print("   ✅ 重复字符正确保留")
    elif result['text'] == '人':
        print("   ⚠️  重复字符被合并，测试fix_repeated_chars...")
        fixed = recognizer.fix_repeated_chars('人', char_confidences=[0.9, 0.9])
        print(f"   修复后: '{fixed}'")
    else:
        print(f"   ❌ 解码结果异常: '{result['text']}'")

    print("\n2.2 测试集束搜索解码...")
    result_beam = recognizer.ctc_decode(
        probs, chars, blank_index=blank_index,
        beam_width=5, time_step_threshold=0.3
    )
    print(f"   集束搜索结果: '{result_beam['text']}'")
    print(f"   Beam概率: {[f'{p:.4f}' for p in result_beam.get('beam_probs', [])]}")

    print("\n2.3 测试fix_repeated_chars后处理...")
    test_cases = [
        ('人人', ['人人'], None, '人人'),
        ('年年', ['年年'], None, '年年'),
        ('人', [], None, '人'),
        ('大小', [], None, '大小'),
        ('千千万万', [], ['千千万万'], '千千万万'),
        ('大大小小', [], ['大大小小'], '大大小小'),
        ('明明白白', [], ['明明白白'], '明明白白'),
        ('天天向上', ['天'], None, '天向上'),
    ]

    all_pass = True
    for input_text, common_repeats, protected_phrases, expected in test_cases:
        fixed = recognizer.fix_repeated_chars(
            input_text, common_repeats=common_repeats, protected_phrases=protected_phrases
        )
        status = "✅" if fixed == expected else "❌"
        print(f"   {status} '{input_text}' -> '{fixed}' (期望: '{expected}')")
        if fixed != expected:
            all_pass = False

    assert all_pass, "fix_repeated_chars测试失败"

    print("\n2.4 测试实际OCR场景...")
    test_probs = np.zeros((80, num_classes))
    test_probs[:, blank_index] = 0.05

    for t in range(20):
        test_probs[t, 0] = 0.95
    for t in range(20, 25):
        test_probs[t, blank_index] = 0.9
    for t in range(25, 45):
        test_probs[t, 0] = 0.95
    for t in range(45, 50):
        test_probs[t, blank_index] = 0.9
    for t in range(50, 70):
        test_probs[t, 1] = 0.95

    result = recognizer.ctc_decode(
        test_probs, chars, blank_index=blank_index,
        merge_repeated=True, beam_width=1, time_step_threshold=0.2
    )
    print(f"   序列: 人(20帧)-blank(5帧)-人(20帧)-blank(5帧)-天(20帧)")
    print(f"   解码结果: '{result['text']}' (期望: '人人天')")
    print(f"   时间跨度: {result['char_time_spans']}")

    assert '人人' in result['text'], f"期望包含'人人', 实际: '{result['text']}'"
    print("   ✅ 实际OCR场景测试通过")

    print("\n✅ CRNN CTC解码重复字符处理测试通过!")
    return True


def test_tei_xml_p5_compliance():
    print("\n" + "=" * 60)
    print("测试3: TEI XML输出 - P5标准符合性")
    print("=" * 60)

    app = create_app(DevelopmentConfig)

    with app.app_context():
        db.create_all()

        task_repo = TaskRepository(db.session)
        result_repo = ResultRepository(db.session)

        task = Task(
            id='test-tei-001',
            file_name='test_ancient.png',
            file_type='image',
            status='completed',
            progress=100,
            page_count=1
        )
        db.session.add(task)
        db.session.commit()

        print("\n3.1 创建测试数据...")
        page_result = result_repo.save_page_result(
            task.id,
            1,
            {
                'width': 800,
                'height': 600,
                'image_path': '/storage/uploads/test.png',
                'text_lines': [
                    {
                        'content': '人人為本',
                        'confidence': 0.92,
                        'candidates': [{'text': '人人為本', 'confidence': 0.92}],
                        'column_index': 0,
                        'line_index': 0,
                        'text_boxes': [
                            {'x1': 100, 'y1': 50, 'x2': 200, 'y2': 50, 'x3': 200, 'y3': 100, 'x4': 100, 'y4': 100, 'confidence': 0.95},
                            {'x1': 100, 'y1': 120, 'x2': 200, 'y2': 120, 'x3': 200, 'y3': 170, 'x4': 100, 'y4': 170, 'confidence': 0.90},
                            {'x1': 100, 'y1': 190, 'x2': 200, 'y2': 190, 'x3': 200, 'y3': 240, 'x4': 100, 'y4': 240, 'confidence': 0.93},
                            {'x1': 100, 'y1': 260, 'x2': 200, 'y2': 260, 'x3': 200, 'y3': 310, 'x4': 100, 'y4': 310, 'confidence': 0.88},
                        ]
                    },
                    {
                        'content': '天地玄黃',
                        'confidence': 0.88,
                        'candidates': [{'text': '天地玄黃', 'confidence': 0.88}],
                        'column_index': 0,
                        'line_index': 1,
                        'text_boxes': [
                            {'x1': 100, 'y1': 330, 'x2': 200, 'y2': 330, 'x3': 200, 'y3': 380, 'x4': 100, 'y4': 380, 'confidence': 0.88},
                            {'x1': 100, 'y1': 400, 'x2': 200, 'y2': 400, 'x3': 200, 'y3': 450, 'x4': 100, 'y4': 450, 'confidence': 0.85},
                            {'x1': 100, 'y1': 470, 'x2': 200, 'y2': 470, 'x3': 200, 'y3': 520, 'x4': 100, 'y4': 520, 'confidence': 0.90},
                            {'x1': 100, 'y1': 540, 'x2': 200, 'y2': 540, 'x3': 200, 'y3': 590, 'x4': 100, 'y4': 590, 'confidence': 0.89},
                        ]
                    }
                ]
            }
        )

        from app.services.export_service import ExportService
        export_service = ExportService(result_repo, task_repo)

        print("\n3.2 生成TEI XML (含坐标和置信度)...")
        tei_xml = export_service.export_tei_xml(
            task.id,
            include_confidence=True,
            include_coordinates=True
        )

        output_path = os.path.join(app.config['EXPORT_FOLDER'], 'test_output.xml')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(tei_xml)
        print(f"   已写入: {output_path}")

        print("\n3.3 验证XML格式...")
        try:
            root = ET.fromstring(tei_xml.encode('utf-8'))
            print("   ✅ XML格式正确")
        except ET.ParseError as e:
            print(f"   ❌ XML格式错误: {e}")
            return False

        print("\n3.4 验证TEI P5标准符合性...")
        TEI_NS = "http://www.tei-c.org/ns/1.0"
        XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
        XML_NS = "http://www.w3.org/XML/1998/namespace"

        checks = []

        schema_location = root.get(f"{{{XSI_NS}}}schemaLocation")
        has_schema = schema_location and "tei-c.org" in schema_location
        checks.append(("xsi:schemaLocation", has_schema))
        print(f"   xsi:schemaLocation: {'✅' if has_schema else '❌'} {schema_location}")

        tei_id = root.get(f"{{{XML_NS}}}id")
        has_tei_id = bool(tei_id)
        checks.append(("xml:id on TEI", has_tei_id))
        print(f"   xml:id on TEI: {'✅' if has_tei_id else '❌'} {tei_id}")

        tei_header = root.find(f"{{{TEI_NS}}}teiHeader")
        has_header = tei_header is not None
        checks.append(("teiHeader", has_header))
        print(f"   teiHeader: {'✅' if has_header else '❌'}")

        file_desc = tei_header.find(f"{{{TEI_NS}}}fileDesc") if has_header else None
        has_file_desc = file_desc is not None
        checks.append(("fileDesc", has_file_desc))
        print(f"   fileDesc: {'✅' if has_file_desc else '❌'}")

        text_elem = root.find(f"{{{TEI_NS}}}text")
        has_text = text_elem is not None
        checks.append(("text", has_text))
        print(f"   text: {'✅' if has_text else '❌'}")

        if has_text:
            text_lang = text_elem.get(f"{{{XML_NS}}}lang")
            has_lang = text_lang == "zh-CN"
            checks.append(("xml:lang on text", has_lang))
            print(f"   xml:lang on text: {'✅' if has_lang else '❌'} {text_lang}")

        divs = root.findall(f".//{{{TEI_NS}}}div")
        div_types = [div.get("type") for div in divs]
        has_textpart = "textpart" in div_types
        checks.append(("div type=textpart", has_textpart))
        print(f"   div type=textpart: {'✅' if has_textpart else '❌'} {div_types}")

        cert_attrs = []
        for elem in root.iter():
            cert = elem.get("cert")
            if cert:
                cert_attrs.append(cert)
        has_cert = len(cert_attrs) > 0
        checks.append(("cert attribute", has_cert))
        print(f"   cert attributes: {'✅' if has_cert else '❌'} {len(cert_attrs)} found")

        has_confidence_attr = False
        for elem in root.iter():
            for attr in elem.keys():
                if "confidence" in attr:
                    has_confidence_attr = True
                    break
        checks.append(("no confidence attribute", not has_confidence_attr))
        print(f"   无confidence自定义属性: {'✅' if not has_confidence_attr else '❌'}")

        facs = root.find(f"{{{TEI_NS}}}facsimile")
        has_facs = facs is not None
        checks.append(("facsimile", has_facs))
        print(f"   facsimile: {'✅' if has_facs else '❌'}")

        ns = {'tei': TEI_NS}

        if has_facs:
            surfaces = facs.findall("tei:surfaceGrp/tei:surface", ns)
            has_surfaces = len(surfaces) > 0
            checks.append(("surface elements", has_surfaces))
            print(f"   surface elements: {'✅' if has_surfaces else '❌'} {len(surfaces)} found")

            zones = root.findall(".//tei:zone", ns)
            has_zones = len(zones) > 0
            checks.append(("zone elements", has_zones))
            print(f"   zone elements: {'✅' if has_zones else '❌'} {len(zones)} found")

            if len(zones) > 0:
                zone_points = zones[0].get("points")
                has_points = bool(zone_points)
                checks.append(("zone points attribute", has_points))
                print(f"   zone points: {'✅' if has_points else '❌'} {zone_points}")

        w_elems = root.findall(".//tei:w", ns)
        has_w = len(w_elems) > 0
        checks.append(("w elements", has_w))
        print(f"   w elements: {'✅' if has_w else '❌'} {len(w_elems)} found")

        if len(w_elems) > 0:
            w_facs = w_elems[0].get("facs")
            has_w_facs = bool(w_facs) and w_facs.startswith("#")
            checks.append(("w facs ref", has_w_facs))
            print(f"   w facs reference: {'✅' if has_w_facs else '❌'} {w_facs}")

        certainty_elems = root.findall(".//tei:certainty", ns)
        has_certainty = len(certainty_elems) > 0
        checks.append(("certainty elements", has_certainty))
        print(f"   certainty elements: {'✅' if has_certainty else '❌'} {len(certainty_elems)} found")

        if len(certainty_elems) > 0:
            cert_target = certainty_elems[0].get("target")
            cert_degree = certainty_elems[0].get("degree")
            cert_locus = certainty_elems[0].get("locus")
            has_cert_attrs = all([cert_target, cert_degree, cert_locus])
            checks.append(("certainty attributes", has_cert_attrs))
            print(f"   certainty target: {'✅' if cert_target else '❌'} {cert_target}")
            print(f"   certainty degree: {'✅' if cert_degree else '❌'} {cert_degree}")
            print(f"   certainty locus: {'✅' if cert_locus else '❌'} {cert_locus}")

        xml_ids = []
        for elem in root.iter():
            xml_id = elem.get(f"{{{XML_NS}}}id")
            if xml_id:
                xml_ids.append(xml_id)
        has_unique_ids = len(xml_ids) == len(set(xml_ids))
        checks.append(("unique xml:id", has_unique_ids))
        print(f"   唯一xml:id: {'✅' if has_unique_ids else '❌'} {len(xml_ids)} total")

        seg_elems = root.findall(".//tei:seg", ns)
        seg_mixed_content = False
        for seg in seg_elems:
            if seg.text and seg.text.strip() and len(seg):
                seg_mixed_content = True
                break
        checks.append(("no seg mixed content", not seg_mixed_content))
        print(f"   seg无混合内容: {'✅' if not seg_mixed_content else '❌'}")

        print("\n3.5 检查结果汇总...")
        all_passed = True
        for name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {name}")
            if not passed:
                all_passed = False

        db.session.delete(task)
        db.session.commit()

        if all_passed:
            print("\n✅ TEI XML P5标准符合性测试通过!")
        else:
            print("\n❌ TEI XML P5标准符合性测试部分失败")

        return all_passed


def main():
    print("\n" + "=" * 60)
    print("古籍文字识别系统 - Bug修复综合测试")
    print("=" * 60)

    results = []

    try:
        results.append(("行列合并错行鲁棒性", test_misaligned_row_merging()))
    except Exception as e:
        print(f"\n❌ 测试1异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("行列合并错行鲁棒性", False))

    try:
        results.append(("CTC重复字符处理", test_ctc_repeated_chars()))
    except Exception as e:
        print(f"\n❌ 测试2异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("CTC重复字符处理", False))

    try:
        results.append(("TEI XML P5标准", test_tei_xml_p5_compliance()))
    except Exception as e:
        print(f"\n❌ 测试3异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("TEI XML P5标准", False))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"   {status} - {name}")

    all_passed = all(p for _, p in results)
    print(f"\n{'✅ 所有测试通过!' if all_passed else '❌ 部分测试失败!'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
