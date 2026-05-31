import requests
import json
import time

BASE_URL = "http://localhost:8000"


def test_health_check():
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("  PASSED\n")


def test_get_models():
    print("Testing get models...")
    response = requests.get(f"{BASE_URL}/models")
    print(f"  Status: {response.status_code}")
    models = response.json()
    print(f"  Available models: {[m['name'] for m in models]}")
    assert response.status_code == 200
    assert len(models) > 0
    print("  PASSED\n")
    return models


def test_async_prediction():
    print("Testing async prediction...")

    fasta_content = """>test_protein
MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKA"""

    payload = {
        "fasta": fasta_content,
        "model_name": "resnet50_pdb"
    }

    response = requests.post(
        f"{BASE_URL}/predict",
        json=payload
    )
    print(f"  Status: {response.status_code}")
    result = response.json()
    print(f"  Task ID: {result.get('task_id')}")
    print(f"  Status: {result.get('status')}")
    assert response.status_code == 202
    assert "task_id" in result
    print("  PASSED\n")
    return result["task_id"]


def test_get_task_status(task_id):
    print(f"Testing get task status for {task_id}...")
    response = requests.get(f"{BASE_URL}/predict/{task_id}")
    print(f"  Status: {response.status_code}")
    result = response.json()
    print(f"  Task status: {result.get('status')}")
    assert response.status_code == 200
    print("  PASSED\n")


def test_sync_prediction():
    print("Testing sync prediction...")

    fasta_content = """>test_protein_short
MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKA"""

    payload = {
        "fasta": fasta_content,
        "model_name": "resnet18_pdb"
    }

    print("  This may take a few seconds...")
    response = requests.post(
        f"{BASE_URL}/predict/sync",
        json=payload,
        timeout=120
    )
    print(f"  Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"  Sequence length: {result.get('sequence_length')}")
        print(f"  Num contacts: {result.get('num_contacts')}")
        print(f"  Threshold: {result.get('threshold_angstrom')}Å")
        print(f"  Inference time: {result.get('inference_time_ms'):.2f}ms")
        print(f"  Precision metrics: {json.dumps(result.get('precision_metrics'), indent=4)}")
        print(f"  First 5 contacts: {json.dumps(result.get('contact_list')[:5], indent=4)}")
        print(f"  3D coordinates shape: ({len(result.get('coordinates_3d'))}, {len(result.get('coordinates_3d')[0]) if result.get('coordinates_3d') else 0})")
        print("  PASSED\n")
    else:
        print(f"  Error: {response.text}")
        print("  FAILED\n")


def test_list_tasks():
    print("Testing list tasks...")
    response = requests.get(f"{BASE_URL}/tasks?limit=10")
    print(f"  Status: {response.status_code}")
    result = response.json()
    print(f"  Total tasks: {result.get('total')}")
    print(f"  Returned tasks: {len(result.get('tasks'))}")
    assert response.status_code == 200
    print("  PASSED\n")


def main():
    print("=" * 60)
    print("Protein Contact Map Prediction API - Test Suite")
    print("=" * 60 + "\n")

    try:
        test_health_check()
        test_get_models()

        task_id = test_async_prediction()

        time.sleep(2)
        test_get_task_status(task_id)

        test_sync_prediction()
        test_list_tasks()

        print("=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to server.")
        print("Please make sure the server is running on http://localhost:8000")
        print("You can start it with: python -m uvicorn app.main:app --reload")
    except AssertionError as e:
        print(f"\nTest failed: {e}")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
