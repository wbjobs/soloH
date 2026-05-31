from app import create_app, db
from config import DevelopmentConfig
import json
import io
import traceback

app = create_app(DevelopmentConfig)

with app.app_context():
    db.create_all()
    print('Database initialized')

with app.test_client() as client:
    # Test health endpoint
    print('\n=== 1. Health Check ===')
    response = client.get('/api/health')
    print(f'Status: {response.status_code}')
    print(f'Response: {json.dumps(response.get_json(), ensure_ascii=False, indent=2)}')
    
    # Test create task
    print('\n=== 2. Create Task ===')
    response = client.post('/api/tasks', json={
        'fileName': 'test.png',
        'fileType': 'image'
    })
    print(f'Status: {response.status_code}')
    result = response.get_json()
    print(f'Response: {json.dumps(result, ensure_ascii=False, indent=2)}')
    task_id = result.get('id') or result.get('taskId')
    print(f'Task ID: {task_id}')
    
    # Test delete task
    if task_id:
        print(f'\n=== 3. Delete Task {task_id} ===')
        response = client.delete(f'/api/tasks/{task_id}')
        print(f'Status: {response.status_code}')
        print(f'Response: {json.dumps(response.get_json(), ensure_ascii=False, indent=2)}')
    
    # Test file upload
    print('\n=== 4. File Upload ===')
    try:
        dummy_image = io.BytesIO(b'fake_image_data')
        dummy_image.name = 'test.png'
        response = client.post('/api/files/upload', data={
            'file': (dummy_image, 'test.png')
        }, content_type='multipart/form-data')
        print(f'Status: {response.status_code}')
        print(f'Response: {json.dumps(response.get_json(), ensure_ascii=False, indent=2)}')
    except Exception as e:
        print(f'Exception: {str(e)}')
        traceback.print_exc()
    
    # Test get tasks list
    print('\n=== 5. Get Tasks List ===')
    response = client.get('/api/tasks?page=1&perPage=10')
    print(f'Status: {response.status_code}')
    result = response.get_json()
    print(f'Response: {json.dumps(result, ensure_ascii=False, indent=2)}')
    
    print('\n=== Tests Complete ===')
