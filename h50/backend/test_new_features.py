import requests
import json
import numpy as np
from PIL import Image
import io

BASE_URL = "http://localhost:5000/api"

def test_styles_api():
    print("=" * 60)
    print("测试流派风格API")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/styles")
        print(f"GET /api/styles 状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"获取到 {len(data.get('styles', []))} 个流派")
            for style in data.get('styles', []):
                print(f"  - {style['id']}: {style['name']}")
            return True
        else:
            print(f"错误: {response.text}")
            return False
    except Exception as e:
        print(f"异常: {e}")
        return False

def test_style_detail_api():
    print("\n" + "=" * 60)
    print("测试流派详情API")
    print("=" * 60)
    
    try:
        style_id = "guangling"
        response = requests.get(f"{BASE_URL}/styles/{style_id}")
        print(f"GET /api/styles/{style_id} 状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            style = data.get('style', {})
            print(f"流派名称: {style.get('name')}")
            print(f"流派描述: {style.get('description')[:50]}...")
            if 'params' in style:
                print(f"包含 {len(style['params'])} 个风格参数")
            return True
        else:
            print(f"错误: {response.text}")
            return False
    except Exception as e:
        print(f"异常: {e}")
        return False

def test_score_list_api():
    print("\n" + "=" * 60)
    print("测试曲谱列表API")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/score/list")
        print(f"GET /api/score/list 状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"获取到 {len(data.get('scores', []))} 个曲谱")
            return True
        else:
            print(f"错误: {response.text}")
            return False
    except Exception as e:
        print(f"异常: {e}")
        return False

def test_stitch_preview_api():
    print("\n" + "=" * 60)
    print("测试谱页拼接预览API")
    print("=" * 60)
    
    try:
        test_image1 = Image.new('RGB', (800, 600), color=(245, 240, 230))
        test_image2 = Image.new('RGB', (800, 600), color=(240, 235, 225))
        
        buf1 = io.BytesIO()
        test_image1.save(buf1, format='PNG')
        buf1.seek(0)
        
        buf2 = io.BytesIO()
        test_image2.save(buf2, format='PNG')
        buf2.seek(0)
        
        files = [
            ('pages', ('page1.png', buf1, 'image/png')),
            ('pages', ('page2.png', buf2, 'image/png'))
        ]
        
        response = requests.post(f"{BASE_URL}/score/stitch", files=files)
        print(f"POST /api/score/stitch 状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"拼接成功: {data.get('success')}")
            print(f"检测到 {data.get('column_count', 0)} 个列")
            return True
        else:
            print(f"错误: {response.text}")
            return False
    except Exception as e:
        print(f"异常: {e}")
        return False

def test_create_score_api():
    print("\n" + "=" * 60)
    print("测试创建曲谱API")
    print("=" * 60)
    
    try:
        test_image = Image.new('RGB', (800, 600), color=(245, 240, 230))
        buf = io.BytesIO()
        test_image.save(buf, format='PNG')
        buf.seek(0)
        
        files = [('pages', ('test_page.png', buf, 'image/png'))]
        data = {
            'title': '测试曲目',
            'metadata': json.dumps({
                'composer': '测试',
                'dynasty': '现代',
                'description': '测试曲目描述'
            })
        }
        
        response = requests.post(f"{BASE_URL}/score/create", files=files, data=data)
        print(f"POST /api/score/create 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"创建成功: {result.get('success')}")
            print(f"曲谱ID: {result.get('score_id')}")
            return result.get('score_id')
        else:
            print(f"错误: {response.text}")
            return None
    except Exception as e:
        print(f"异常: {e}")
        return None

def test_score_detail_api(score_id):
    print("\n" + "=" * 60)
    print("测试曲谱详情API")
    print("=" * 60)
    
    if not score_id:
        print("跳过: 没有有效的score_id")
        return False
    
    try:
        response = requests.get(f"{BASE_URL}/score/{score_id}")
        print(f"GET /api/score/{score_id} 状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            score = data.get('score', {})
            print(f"曲谱标题: {score.get('metadata', {}).get('title')}")
            print(f"总页数: {score.get('metadata', {}).get('total_pages')}")
            print(f"减字数量: {len(score.get('jianzi_sequence', []))}")
            return True
        else:
            print(f"错误: {response.text}")
            return False
    except Exception as e:
        print(f"异常: {e}")
        return False

def test_difficulty_evaluate_api(score_id):
    print("\n" + "=" * 60)
    print("测试难度评估API")
    print("=" * 60)
    
    if not score_id:
        print("跳过: 没有有效的score_id")
        return False
    
    try:
        response = requests.get(f"{BASE_URL}/difficulty/evaluate/{score_id}")
        print(f"GET /api/difficulty/evaluate/{score_id} 状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"评估成功: {data.get('success')}")
            report = data.get('report', {})
            overall = report.get('overall', {})
            print(f"综合难度分: {overall.get('score'):.1f}")
            print(f"难度等级: {overall.get('level')}")
            print(f"建议数量: {len(report.get('recommendations', []))}")
            return True
        else:
            print(f"错误: {response.text}")
            return False
    except Exception as e:
        print(f"异常: {e}")
        return False

def test_synthesize_score_api(score_id):
    print("\n" + "=" * 60)
    print("测试曲谱合成API")
    print("=" * 60)
    
    if not score_id:
        print("跳过: 没有有效的score_id")
        return False
    
    try:
        data = {
            'style': 'guangling',
            'tempo': 60
        }
        response = requests.post(f"{BASE_URL}/score/{score_id}/synthesize", json=data)
        print(f"POST /api/score/{score_id}/synthesize 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"合成成功: {result.get('success')}")
            print(f"使用风格: {result.get('style')}")
            print(f"音频时长: {result.get('duration'):.2f}秒")
            return True
        else:
            print(f"错误: {response.text}")
            return False
    except Exception as e:
        print(f"异常: {e}")
        return False

def test_style_compare_api():
    print("\n" + "=" * 60)
    print("测试流派对比API")
    print("=" * 60)
    
    try:
        data = {
            'jianzi_list': [
                {'id': '1', 'technique': '勾', 'string': '1', 'hui': '7'},
                {'id': '2', 'technique': '挑', 'string': '2', 'hui': '9'}
            ],
            'style_ids': ['guangling', 'yushan', 'meian'],
            'tempo': 60
        }
        response = requests.post(f"{BASE_URL}/styles/compare", json=data)
        print(f"POST /api/styles/compare 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"对比成功，获得 {len(result.get('results', []))} 个结果")
            for r in result.get('results', []):
                print(f"  - {r['style_name']}: {r.get('level', 'N/A')}")
            return True
        else:
            print(f"错误: {response.text}")
            return False
    except Exception as e:
        print(f"异常: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "#" * 60)
    print("# 古琴减字谱系统 - 新功能测试")
    print("#" * 60)
    
    results = []
    
    results.append(('流派列表API', test_styles_api()))
    results.append(('流派详情API', test_style_detail_api()))
    results.append(('曲谱列表API', test_score_list_api()))
    results.append(('谱页拼接API', test_stitch_preview_api()))
    
    score_id = test_create_score_api()
    results.append(('创建曲谱API', score_id is not None))
    
    if score_id:
        results.append(('曲谱详情API', test_score_detail_api(score_id)))
        results.append(('难度评估API', test_difficulty_evaluate_api(score_id)))
        results.append(('曲谱合成API', test_synthesize_score_api(score_id)))
    
    results.append(('流派对比API', test_style_compare_api()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")
    
    print("\n" + "=" * 60)
    if passed == total:
        print("🎉 所有测试通过！")
    else:
        print(f"⚠️  有 {total - passed} 个测试失败")
    print("=" * 60)
