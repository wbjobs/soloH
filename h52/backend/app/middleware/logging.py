import time
from fastapi import Request
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def logging_middleware(request: Request, call_next):
    start_time = time.time()
    method = request.method
    path = request.url.path
    client_ip = request.client.host if request.client else "unknown"

    logger.info(f"Request started: {method} {path} from {client_ip}")

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    status_code = response.status_code

    logger.info(
        f"Request completed: {method} {path} "
        f"Status: {status_code} "
        f"Duration: {process_time:.2f}ms"
    )

    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    return response
