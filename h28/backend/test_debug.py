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
    
    task_obj = task_repo.get_by_id(task.id)
    all_results = result_repo.get_by_task_id(task.id)
    
    print(f'  任务: {task_obj.id}')
    print(f'  结果数: {len(all_results)}')
    for r in all_results:
        print(f'  页面: {r.page_number}, text_lines: {len(r.text_lines)}')
        for tl in r.text_lines:
            print(f'    行: {tl.content}, confidence={tl.confidence}, is None={tl.confidence is None}')
            print(f'    text_boxes: {len(tl.text_boxes)}')
            for tb in tl.text_boxes:
                print(f'      tb confidence={tb.confidence}')
    
    tei_xml = export_service.export_tei_xml(
        task.id,
        include_confidence=True,
        include_coordinates=True
    )

    output_path = os.path.join(app.config['EXPORT_FOLDER'], 'test_output_debug.xml')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(tei_xml)
    print(f'   已写入: {output_path}')

    root = ET.fromstring(tei_xml.encode('utf-8'))
    TEI_NS = 'http://www.tei-c.org/ns/1.0'
    ns = {'tei': TEI_NS}
    
    certainty_elems = root.findall('.//tei:certainty', ns)
    print(f'  certainty元素数: {len(certainty_elems)}')
    
    seg_elems = root.findall('.//tei:seg', ns)
    for seg in seg_elems:
        print(f'  seg子元素: {[child.tag.split("}")[-1] for child in seg]}')

    db.session.delete(task)
    db.session.commit()
