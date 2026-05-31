from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.db.models import CropType, UserConfig
from app.schemas.auth import CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.config import UserConfigCreate, UserConfigResponse, UserConfigUpdate

router = APIRouter()


@router.get(
    "/list",
    response_model=ApiResponse[List[UserConfigResponse]],
    summary="用户配置列表",
)
async def get_configs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[List[UserConfigResponse]]:
    query = select(UserConfig).where(UserConfig.user_id == current_user.id)
    result = await db.execute(query)
    configs = result.scalars().all()

    items = [UserConfigResponse.model_validate(c) for c in configs]

    return ApiResponse(data=items)


@router.post(
    "/",
    response_model=ApiResponse[UserConfigResponse],
    summary="创建配置",
)
async def create_config(
    config_in: UserConfigCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[UserConfigResponse]:
    query = select(UserConfig).where(
        and_(
            UserConfig.user_id == current_user.id,
            UserConfig.crop_type == config_in.crop_type,
        )
    )
    result = await db.execute(query)
    existing_config = result.scalar_one_or_none()

    if existing_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该作物类型的配置已存在",
        )

    webhook_url_str = str(config_in.webhook_url) if config_in.webhook_url else None

    config = UserConfig(
        user_id=current_user.id,
        crop_type=config_in.crop_type,
        variety_name=config_in.variety_name,
        resistance_level=config_in.resistance_level,
        risk_threshold=config_in.risk_threshold,
        notification_email=config_in.notification_email,
        webhook_url=webhook_url_str,
    )

    db.add(config)
    await db.commit()
    await db.refresh(config)

    return ApiResponse(data=UserConfigResponse.model_validate(config))


@router.get(
    "/{config_id}",
    response_model=ApiResponse[UserConfigResponse],
    summary="配置详情",
)
async def get_config_detail(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[UserConfigResponse]:
    query = select(UserConfig).where(
        and_(
            UserConfig.id == config_id,
            UserConfig.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在或无权限访问",
        )

    return ApiResponse(data=UserConfigResponse.model_validate(config))


@router.put(
    "/{config_id}",
    response_model=ApiResponse[UserConfigResponse],
    summary="更新配置",
)
async def update_config(
    config_id: int,
    config_in: UserConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[UserConfigResponse]:
    query = select(UserConfig).where(
        and_(
            UserConfig.id == config_id,
            UserConfig.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在或无权限访问",
        )

    update_data = config_in.model_dump(exclude_unset=True)

    if "webhook_url" in update_data and update_data["webhook_url"] is not None:
        update_data["webhook_url"] = str(update_data["webhook_url"])

    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)

    return ApiResponse(data=UserConfigResponse.model_validate(config))


@router.delete(
    "/{config_id}",
    response_model=ApiResponse[dict],
    summary="删除配置",
)
async def delete_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[dict]:
    query = select(UserConfig).where(
        and_(
            UserConfig.id == config_id,
            UserConfig.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在或无权限访问",
        )

    await db.delete(config)
    await db.commit()

    return ApiResponse(data={"message": "配置删除成功"})


@router.get(
    "/by-crop/{crop_type}",
    response_model=ApiResponse[UserConfigResponse],
    summary="按作物类型获取配置",
)
async def get_config_by_crop(
    crop_type: CropType,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> ApiResponse[UserConfigResponse]:
    query = select(UserConfig).where(
        and_(
            UserConfig.user_id == current_user.id,
            UserConfig.crop_type == crop_type,
        )
    )
    result = await db.execute(query)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到 {crop_type.value} 类型的配置",
        )

    return ApiResponse(data=UserConfigResponse.model_validate(config))
