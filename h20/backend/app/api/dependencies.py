from typing import Generator, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.core.config import settings
from app.core.database import async_session_factory
from app.repositories import (
    TransactionRepository,
    AddressRepository,
    GraphRepository,
    ClusterRepository,
    PatternRepository,
    TaskRepository,
)
from app.services import (
    TransactionService,
    AddressService,
    GraphService,
    ClusteringService,
    PatternService,
    TaskService,
    GNNAnomalyService,
    PrivacyCoinAnalysisService,
    ComplianceReportService,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


async def get_db_session() -> Generator[AsyncSession, None, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> dict | None:
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def get_transaction_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransactionRepository:
    return TransactionRepository(db)


def get_address_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AddressRepository:
    return AddressRepository(db)


def get_graph_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GraphRepository:
    return GraphRepository(db)


def get_cluster_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ClusterRepository:
    return ClusterRepository(db)


def get_pattern_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PatternRepository:
    return PatternRepository(db)


def get_task_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskRepository:
    return TaskRepository(db)


def get_transaction_service(
    repo: Annotated[TransactionRepository, Depends(get_transaction_repository)],
) -> TransactionService:
    return TransactionService(repo)


def get_address_service(
    address_repo: Annotated[AddressRepository, Depends(get_address_repository)],
    transaction_repo: Annotated[TransactionRepository, Depends(get_transaction_repository)],
) -> AddressService:
    return AddressService(address_repo, transaction_repo)


def get_graph_service(
    repo: Annotated[GraphRepository, Depends(get_graph_repository)],
) -> GraphService:
    return GraphService(repo)


def get_clustering_service(
    cluster_repo: Annotated[ClusterRepository, Depends(get_cluster_repository)],
    transaction_repo: Annotated[TransactionRepository, Depends(get_transaction_repository)],
) -> ClusteringService:
    return ClusteringService(cluster_repo, transaction_repo)


def get_pattern_service(
    pattern_repo: Annotated[PatternRepository, Depends(get_pattern_repository)],
    address_repo: Annotated[AddressRepository, Depends(get_address_repository)],
) -> PatternService:
    return PatternService(pattern_repo, address_repo)


def get_task_service(
    repo: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(repo)


def get_gnn_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GNNAnomalyService:
    return GNNAnomalyService(db)


def get_privacy_coin_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PrivacyCoinAnalysisService:
    return PrivacyCoinAnalysisService(db)


def get_compliance_report_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComplianceReportService:
    return ComplianceReportService(db)
