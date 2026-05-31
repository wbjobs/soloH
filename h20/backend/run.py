import uvicorn
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

host = os.getenv("API_HOST", "0.0.0.0")
port = int(os.getenv("API_PORT", "8000"))
reload = os.getenv("API_RELOAD", "True").lower() == "true"

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Bitcoin Transaction Graph Analysis Backend")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Auto-reload: {reload}")
    print("=" * 60)
    print(f"API Documentation: http://{host}:{port}/docs")
    print(f"Alternative Docs: http://{host}:{port}/redoc")
    print(f"Health Check: http://{host}:{port}/health")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=1 if reload else None,
    )
