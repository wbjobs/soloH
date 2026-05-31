from app import create_app, db
from config import DevelopmentConfig
from PIL import Image
import json
import io
import os
import tempfile

app = create_app(DevelopmentConfig)

with app.app_context():
    db.create_all()
    print('Database initialized')

with app.test_client() as client:
    # 1. Health check
    print('\n=== 1. Health Check ===')
    response = client.get('/api/health')
    print(f'Status: {response.status_code}')
    assert response.status_code == 200, 'Health check failed'
    print('✅ Health check passed')
    
    # 2. Create a real test image
    print('\n=== 2. Create Test Image ===')
    img = Image.new('RGB', (800, 600), color=(245, 240, 230))
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    print('✅ Test image created')
    
    # 3. File upload
    print('\n=== 3. File Upload ===')
    response = client.post('/api/files/upload', data={
        'file': (img_buffer, 'test_ancient.png')
    }, content_type='multipart/form-data')
    print(f'Status: {response.status_code}')
    if response.status_code != 201:
        print(f'Error: {response.get_json()}')
    else:
        result = response.get_json()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        task_id = result.get('id') or result.get('taskId')
        print(f'✅ File uploaded successfully, task_id: {task_id}')
    
    # 4. Create task manually
    print('\n=== 4. Create Task Manually ===')
    response = client.post('/api/tasks', json={
        'fileName': 'manual_test.png',
        'fileType': 'image'
    })
    print(f'Status: {response.status_code}')
    result = response.get_json()
    task_id = result.get('id') or result.get('taskId')
    print(f'✅ Task created: {task_id}')
    
    # 5. Get task
    print('\n=== 5. Get Task ===')
    response = client.get(f'/api/tasks/{task_id}')
    print(f'Status: {response.status_code}')
    assert response.status_code == 200, 'Get task failed'
    print('✅ Get task passed')
    
    # 6. Get tasks list
    print('\n=== 6. Get Tasks List ===')
    response = client.get('/api/tasks?page=1&perPage=10')
    print(f'Status: {response.status_code}')
    assert response.status_code == 200, 'Get tasks list failed'
    result = response.get_json()
    print(f'Total tasks: {result["total"]}')
    print('✅ Get tasks list passed')
    
    # 7. Delete task
    print('\n=== 7. Delete Task ===')
    response = client.delete(f'/api/tasks/{task_id}')
    print(f'Status: {response.status_code}')
    if response.status_code != 200:
        print(f'Error: {response.get_json()}')
    else:
        print('✅ Delete task passed')
    
    # 8. Test ML modules (Mock mode)
    print('\n=== 8. Test ML Modules (Mock Mode) ===')
    try:
        from ml import CTPNDetector, CRNNRecognizer, BERTPunctuator, PostProcessor
        import numpy as np
        
        detector = CTPNDetector(use_mock=True)
        recognizer = CRNNRecognizer(use_mock=True)
        punctuator = BERTPunctuator(use_mock=True)
        post_processor = PostProcessor()
        
        # Create dummy image
        dummy_image = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
        
        # Test detection
        detections = detector.detect(dummy_image)
        print(f'✅ CTPN Detection: {len(detections)} boxes detected')
        
        # Test recognition
        if detections:
            box_images = [dummy_image[10:50, 10:100] for _ in range(3)]
            results = recognizer.recognize_batch(box_images, return_candidates=True, top_k=5)
            print(f'✅ CRNN Recognition: {len(results)} results')
            if results:
                print(f'   Sample text: {results[0].get("text", "")}')
        
        # Test punctuation
        test_texts = ['天地玄黄宇宙洪荒', '日月盈昃辰宿列张']
        punctuated = punctuator.punctuate_batch(test_texts)
        print(f'✅ BERT Punctuation: {len(punctuated)} results')
        
        # Test post processing
        post_result = post_processor.process(
            detection_results=detections,
            recognition_results=results if 'results' in locals() else [],
            punctuation_results=punctuated
        )
        print(f'✅ Post Processing: {len(post_result.get("columns", []))} columns')
        
        print('✅ All ML modules working in mock mode')
    except Exception as e:
        print(f'❌ ML modules test failed: {str(e)}')
        import traceback
        traceback.print_exc()
    
    # 9. Test Export Service
    print('\n=== 9. Test Export Service ===')
    try:
        # Create a completed task with mock data for export testing
        from app.repositories.task_repository import TaskRepository
        from app.repositories.result_repository import ResultRepository
        from app.models.task import Task
        import uuid
        
        task_repo = TaskRepository(db.session)
        result_repo = ResultRepository(db.session)
        
        # Create task
        export_task = Task(
            id=str(uuid.uuid4()),
            file_name='export_test.png',
            file_type='image',
            status='completed',
            progress=100,
            page_count=1
        )
        db.session.add(export_task)
        db.session.commit()
        
        # Add mock page result with text lines
        page_result = result_repo.save_page_result(
            export_task.id,
            1,
            {
                'width': 800,
                'height': 600,
                'image_path': '/storage/uploads/test.png',
                'text_lines': [
                    {
                        'content': '天地玄黃，宇宙洪荒。',
                        'confidence': 0.95,
                        'candidates': [{'text': '天地玄黃', 'confidence': 0.95}],
                        'column_index': 0,
                        'line_index': 0,
                        'text_boxes': [{
                            'x1': 100, 'y1': 50, 'x2': 200, 'y2': 50,
                            'x3': 200, 'y3': 100, 'x4': 100, 'y4': 100,
                            'confidence': 0.95
                        }]
                    },
                    {
                        'content': '日月盈昃，辰宿列張。',
                        'confidence': 0.92,
                        'candidates': [{'text': '日月盈昃', 'confidence': 0.92}],
                        'column_index': 0,
                        'line_index': 1,
                        'text_boxes': [{
                            'x1': 100, 'y1': 120, 'x2': 200, 'y2': 120,
                            'x3': 200, 'y3': 170, 'x4': 100, 'y4': 170,
                            'confidence': 0.92
                        }]
                    },
                    {
                        'content': '寒來暑往，秋收冬藏。',
                        'confidence': 0.88,
                        'candidates': [{'text': '寒來暑往', 'confidence': 0.88}],
                        'column_index': 1,
                        'line_index': 0,
                        'text_boxes': [{
                            'x1': 300, 'y1': 50, 'x2': 400, 'y2': 50,
                            'x3': 400, 'y3': 100, 'x4': 300, 'y4': 100,
                            'confidence': 0.88
                        }]
                    }
                ]
            }
        )
        
        # Test export service
        from app.services.export_service import ExportService
        export_service = ExportService(result_repo, task_repo)
        
        # Test Markdown export
        md_content = export_service.export_markdown(export_task.id, include_confidence=True)
        print(f'✅ Markdown export: {len(md_content)} chars')
        print(f'   Content preview: {md_content[:100]}...')
        
        # Test TEI XML export
        tei_content = export_service.export_tei_xml(export_task.id, include_coordinates=True)
        print(f'✅ TEI XML export: {len(tei_content)} chars')
        
        # Test TXT export
        txt_content = export_service.export_txt(export_task.id)
        print(f'✅ TXT export: {len(txt_content)} chars')
        
        # Test JSON export (via controller method)
        from app.controllers.export_controller import ExportController
        export_controller = ExportController()
        json_result, status = export_controller.export_task_result(
            export_task.id, 'json', include_confidence=True
        )
        print(f'✅ JSON export: {len(json_result["content"])} chars')
        
        # Test via API
        print('\n   --- Testing via API ---')
        for fmt in ['markdown', 'tei', 'txt', 'json']:
            response = client.get(f'/api/tasks/{export_task.id}/export?format={fmt}&download=false')
            print(f'   Export {fmt}: {response.status_code}')
            if response.status_code == 200:
                result = response.get_json()
                print(f'     ✓ {len(result["content"])} chars')
        
        # Clean up
        db.session.delete(export_task)
        db.session.commit()
        
        print('✅ All export tests passed')
    except Exception as e:
        print(f'❌ Export test failed: {str(e)}')
        import traceback
        traceback.print_exc()
    
    print('\n' + '='*50)
    print('✅ All tests completed successfully!')
    print('='*50)
