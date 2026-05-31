import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xml.etree import ElementTree as ET
from app import create_app, db
from app.repositories.task_repository import TaskRepository
from app.repositories.result_repository import ResultRepository
from app.models.task import Task
from config import DevelopmentConfig
import uuid

app = create_app(DevelopmentConfig)

with app.app_context():
    db.create_all()

    task_repo = TaskRepository(db.session)
    result_repo = ResultRepository(db.session)

    task_id = f'test-tei-{uuid.uuid4().hex[:8]}'
    task = Task(
        id=task_id,
        file_name='test_ancient.png',
        file_type='image',
        status='completed',
        progress=100,
        page_count=1
    )
    db.session.add(task)
    db.session.commit()

    print('3.1 创建测试数据...')
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
                }
            ]
        }
    )

    from app.services.export_service import ExportService
    export_service = ExportService(result_repo, task_repo)

    print('3.2 生成TEI XML (含坐标和置信度)...')
    tei_xml = export_service.export_tei_xml(
        task.id,
        include_confidence=True,
        include_coordinates=True
    )

    output_path = os.path.join(app.config['EXPORT_FOLDER'], 'test_output_final.xml')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(tei_xml)
    print(f'   已写入: {output_path}')

    print('\n3.3 验证XML格式...')
    try:
        root = ET.fromstring(tei_xml.encode('utf-8'))
        print('   ✅ XML格式正确')
    except ET.ParseError as e:
        print(f'   ❌ XML格式错误: {e}')
        sys.exit(1)

    print('\n3.4 验证TEI P5标准符合性...')
    TEI_NS = 'http://www.tei-c.org/ns/1.0'
    XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
    XML_NS = 'http://www.w3.org/XML/1998/namespace'
    ns = {'tei': TEI_NS}

    checks = []

    schema_location = root.get(f'{{{XSI_NS}}}schemaLocation')
    has_schema = schema_location and 'tei-c.org' in schema_location
    checks.append(('xsi:schemaLocation', has_schema))
    status = '✅' if has_schema else '❌'
    print(f'   {status} xsi:schemaLocation: {schema_location}')

    tei_id = root.get(f'{{{XML_NS}}}id')
    has_tei_id = bool(tei_id)
    checks.append(('xml:id on TEI', has_tei_id))
    status = '✅' if has_tei_id else '❌'
    print(f'   {status} xml:id on TEI: {tei_id}')

    tei_header = root.find(f'tei:teiHeader', ns)
    has_header = tei_header is not None
    checks.append(('teiHeader', has_header))
    status = '✅' if has_header else '❌'
    print(f'   {status} teiHeader')

    file_desc = tei_header.find(f'tei:fileDesc', ns) if has_header else None
    has_file_desc = file_desc is not None
    checks.append(('fileDesc', has_file_desc))
    status = '✅' if has_file_desc else '❌'
    print(f'   {status} fileDesc')

    text_elem = root.find(f'tei:text', ns)
    has_text = text_elem is not None
    checks.append(('text', has_text))
    status = '✅' if has_text else '❌'
    print(f'   {status} text')

    if has_text:
        text_lang = text_elem.get(f'{{{XML_NS}}}lang')
        has_lang = text_lang == 'zh-CN'
        checks.append(('xml:lang on text', has_lang))
        status = '✅' if has_lang else '❌'
        print(f'   {status} xml:lang on text: {text_lang}')

    divs = root.findall('.//tei:div', ns)
    div_types = [div.get('type') for div in divs]
    has_textpart = 'textpart' in div_types
    checks.append(('div type=textpart', has_textpart))
    status = '✅' if has_textpart else '❌'
    print(f'   {status} div type=textpart: {div_types}')

    cert_attrs = []
    for elem in root.iter():
        cert = elem.get('cert')
        if cert:
            cert_attrs.append(cert)
    has_cert = len(cert_attrs) > 0
    checks.append(('cert attribute', has_cert))
    status = '✅' if has_cert else '❌'
    print(f'   {status} cert attributes: {len(cert_attrs)} found')

    has_confidence_attr = False
    for elem in root.iter():
        for attr in elem.keys():
            if 'confidence' in attr:
                has_confidence_attr = True
                break
    checks.append(('no confidence attribute', not has_confidence_attr))
    status = '✅' if not has_confidence_attr else '❌'
    print(f'   {status} 无confidence自定义属性')

    facs = root.find(f'tei:facsimile', ns)
    has_facs = facs is not None
    checks.append(('facsimile', has_facs))
    status = '✅' if has_facs else '❌'
    print(f'   {status} facsimile')

    if has_facs:
        surfaces = facs.findall('tei:surfaceGrp/tei:surface', ns)
        has_surfaces = len(surfaces) > 0
        checks.append(('surface elements', has_surfaces))
        status = '✅' if has_surfaces else '❌'
        print(f'   {status} surface elements: {len(surfaces)} found')

        zones = root.findall('.//tei:zone', ns)
        has_zones = len(zones) > 0
        checks.append(('zone elements', has_zones))
        status = '✅' if has_zones else '❌'
        print(f'   {status} zone elements: {len(zones)} found')

        if len(zones) > 0:
            zone_points = zones[0].get('points')
            has_points = bool(zone_points)
            checks.append(('zone points attribute', has_points))
            status = '✅' if has_points else '❌'
            print(f'   {status} zone points: {zone_points}')

    w_elems = root.findall('.//tei:w', ns)
    has_w = len(w_elems) > 0
    checks.append(('w elements', has_w))
    status = '✅' if has_w else '❌'
    print(f'   {status} w elements: {len(w_elems)} found')

    if len(w_elems) > 0:
        w_facs = w_elems[0].get('facs')
        has_w_facs = bool(w_facs) and w_facs.startswith('#')
        checks.append(('w facs ref', has_w_facs))
        status = '✅' if has_w_facs else '❌'
        print(f'   {status} w facs reference: {w_facs}')

    certainty_elems = root.findall('.//tei:certainty', ns)
    has_certainty = len(certainty_elems) > 0
    checks.append(('certainty elements', has_certainty))
    status = '✅' if has_certainty else '❌'
    print(f'   {status} certainty elements: {len(certainty_elems)} found')

    if len(certainty_elems) > 0:
        cert_target = certainty_elems[0].get('target')
        cert_degree = certainty_elems[0].get('degree')
        cert_locus = certainty_elems[0].get('locus')
        has_cert_attrs = all([cert_target, cert_degree, cert_locus])
        checks.append(('certainty attributes', has_cert_attrs))
        s1 = '✅' if cert_target else '❌'
        s2 = '✅' if cert_degree else '❌'
        s3 = '✅' if cert_locus else '❌'
        print(f'   {s1} certainty target: {cert_target}')
        print(f'   {s2} certainty degree: {cert_degree}')
        print(f'   {s3} certainty locus: {cert_locus}')

    xml_ids = []
    for elem in root.iter():
        xml_id = elem.get(f'{{{XML_NS}}}id')
        if xml_id:
            xml_ids.append(xml_id)
    has_unique_ids = len(xml_ids) == len(set(xml_ids))
    checks.append(('unique xml:id', has_unique_ids))
    status = '✅' if has_unique_ids else '❌'
    print(f'   {status} 唯一xml:id: {len(xml_ids)} total')

    seg_elems = root.findall('.//tei:seg', ns)
    seg_mixed_content = False
    for seg in seg_elems:
        if seg.text and seg.text.strip() and len(seg):
            seg_mixed_content = True
            break
    checks.append(('no seg mixed content', not seg_mixed_content))
    status = '✅' if not seg_mixed_content else '❌'
    print(f'   {status} seg无混合内容')

    print('\n3.5 检查结果汇总...')
    all_passed = True
    for name, passed in checks:
        status = '✅' if passed else '❌'
        print(f'   {status} {name}')
        if not passed:
            all_passed = False

    db.session.delete(task)
    db.session.commit()

    if all_passed:
        print('\n✅ TEI XML P5标准符合性测试通过!')
    else:
        print('\n❌ TEI XML P5标准符合性测试部分失败')
        sys.exit(1)

    print('\n✅ 所有测试通过!')
