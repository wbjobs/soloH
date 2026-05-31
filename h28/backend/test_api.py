from app import create_app, db
from config import DevelopmentConfig
import json
import io

app = create_app(DevelopmentConfig)

with app.app_context():
    db.create_all()
    print('Database initialized')

with app.test_client() as client:
    # Test health endpoint
    response = client.get('/api/health')
    print(f'\n1. Health check: {response.status_code}')
    print(json.dumps(response.get_json(), ensure_ascii=False, indent=2))
    
    # Test create task
    response = client.post('/api/tasks', json={
        'fileName': 'test.png',
        'fileType': 'image'
    })
    print(f'\n2. Create task: {response.status_code}')
    result = response.get_json()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    task_id = result.get('id') or result.get('taskId')
    
    if task_id:
        # Test get task
        response = client.get(f'/api/tasks/{task_id}')
        print(f'\n3. Get task {task_id}: {response.status_code}')
        print(json.dumps(response.get_json(), ensure_ascii=False, indent=2))
        
        # Test update task result
        response = client.put(f'/api/tasks/{task_id}/result', json={
            'textLineId': 1,
            'content': '修改后的内容'
        })
        print(f'\n4. Update text line: {response.status_code}')
        
        # Test get task result
        response = client.get(f'/api/tasks/{task_id}/result')
        print(f'\n5. Get task result: {response.status_code}')
        print(f'Response keys: {list(response.get_json().keys())}')
        
        # Test export
        for fmt in ['markdown', 'tei', 'txt', 'json']:
            response = client.get(f'/api/tasks/{task_id}/export?format={fmt}&download=false')
            print(f'\n6. Export {fmt}: {response.status_code}')
            if response.status_code == 200:
                result = response.get_json()
                filename = result.get('filename', '')
                content = result.get('content', '')
                print(f'   Filename: {filename}')
                print(f'   Content length: {len(content)} chars')
    
    # Test get tasks list
    response = client.get('/api/tasks?page=1&perPage=10')
    print(f'\n7. Get tasks list: {response.status_code}')
    result = response.get_json()
    total = result.get('total')
    page = result.get('page')
    per_page = result.get('perPage')
    print(f'   Total: {total}, Page: {page}, PerPage: {per_page}')
    
    # Test file upload with a dummy image
    dummy_image = io.BytesIO(b'fake_image_data')
    dummy_image.name = 'test.png'
    response = client.post('/api/files/upload', data={
        'file': (dummy_image, 'test.png')
    }, content_type='multipart/form-data')
    print(f'\n8. File upload: {response.status_code}')
    if response.status_code == 201:
        print(json.dumps(response.get_json(), ensure_ascii=False, indent=2))
    
    if task_id:
        # Test delete task
        response = client.delete(f'/api/tasks/{task_id}')
        print(f'\n9. Delete task: {response.status_code}')
    
    print('\n✅ All API tests completed successfully!')
