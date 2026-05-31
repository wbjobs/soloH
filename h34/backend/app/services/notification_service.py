import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import httpx
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import (
    Alert,
    NotificationLog,
    UserConfig,
    NotificationChannel,
    AlertType,
    RiskGrid,
    GridCell,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """通知服务

    负责邮件通知、Webhook通知、预警通知的发送和管理。
    支持异步发送、失败重试、状态记录等功能。
    """

    def __init__(
        self,
        db: AsyncSession,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_tls: Optional[bool] = None,
        emails_from_email: Optional[str] = None,
        emails_from_name: Optional[str] = None,
    ):
        self.db = db

        self.smtp_host = smtp_host or settings.SMTP_HOST
        self.smtp_port = smtp_port or settings.SMTP_PORT
        self.smtp_user = smtp_user or settings.SMTP_USER
        self.smtp_password = smtp_password or settings.SMTP_PASSWORD
        self.smtp_tls = smtp_tls if smtp_tls is not None else settings.SMTP_TLS
        self.emails_from_email = emails_from_email or settings.EMAILS_FROM_EMAIL
        self.emails_from_name = emails_from_name or settings.EMAILS_FROM_NAME

        self.frontend_base_url = "http://localhost:3000"

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
        alert_id: Optional[int] = None,
    ) -> bool:
        """异步发送邮件

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            html_content: HTML格式邮件内容
            plain_content: 纯文本格式邮件内容（可选）
            alert_id: 关联的预警ID（可选）

        Returns:
            bool: 发送是否成功
        """
        if not self.smtp_host or not self.smtp_user:
            logger.warning("SMTP配置不完整，跳过邮件发送")
            await self._create_notification_log(
                alert_id=alert_id,
                channel=NotificationChannel.EMAIL,
                recipient=to_email,
                status="failed",
                error_message="SMTP配置不完整",
            )
            return False

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{self.emails_from_name} <{self.emails_from_email}>" if self.emails_from_name else self.emails_from_email
        message["To"] = to_email

        if plain_content:
            message.attach(MIMEText(plain_content, "plain", "utf-8"))
        message.attach(MIMEText(html_content, "html", "utf-8"))

        max_retries = 3
        for attempt in range(max_retries):
            try:
                await aiosmtplib.send(
                    message,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_user,
                    password=self.smtp_password,
                    use_tls=self.smtp_tls,
                    start_tls=self.smtp_tls,
                    timeout=30,
                )
                logger.info(f"邮件发送成功: {to_email}")
                await self._create_notification_log(
                    alert_id=alert_id,
                    channel=NotificationChannel.EMAIL,
                    recipient=to_email,
                    status="success",
                )
                return True
            except Exception as e:
                wait_time = 2 ** attempt
                error_msg = f"邮件发送失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}"
                logger.error(error_msg)

                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                else:
                    await self._create_notification_log(
                        alert_id=alert_id,
                        channel=NotificationChannel.EMAIL,
                        recipient=to_email,
                        status="failed",
                        error_message=str(e),
                    )
                    return False

        return False

    async def send_webhook(
        self,
        webhook_url: str,
        payload: Dict[str, Any],
        retries: int = 3,
        alert_id: Optional[int] = None,
    ) -> bool:
        """异步发送Webhook通知

        Args:
            webhook_url: Webhook URL
            payload: 请求payload
            retries: 重试次数（默认3次）
            alert_id: 关联的预警ID（可选）

        Returns:
            bool: 发送是否成功
        """
        timeout = httpx.Timeout(10.0)

        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    response.raise_for_status()

                    logger.info(f"Webhook发送成功: {webhook_url}")
                    await self._create_notification_log(
                        alert_id=alert_id,
                        channel=NotificationChannel.WEBHOOK,
                        recipient=webhook_url,
                        status="success",
                    )
                    return True
            except httpx.HTTPStatusError as e:
                error_msg = f"Webhook HTTP错误 (尝试 {attempt + 1}/{retries}): {e.response.status_code} - {str(e)}"
                logger.error(error_msg)

                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    await self._create_notification_log(
                        alert_id=alert_id,
                        channel=NotificationChannel.WEBHOOK,
                        recipient=webhook_url,
                        status="failed",
                        error_message=str(e),
                    )
                    return False
            except Exception as e:
                error_msg = f"Webhook发送失败 (尝试 {attempt + 1}/{retries}): {str(e)}"
                logger.error(error_msg)

                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    await self._create_notification_log(
                        alert_id=alert_id,
                        channel=NotificationChannel.WEBHOOK,
                        recipient=webhook_url,
                        status="failed",
                        error_message=str(e),
                    )
                    return False

        return False

    async def test_webhook(self, webhook_url: str) -> bool:
        """测试Webhook连接

        Args:
            webhook_url: Webhook URL

        Returns:
            bool: 测试是否成功
        """
        test_payload = {
            "event": "test",
            "message": "这是一条测试消息",
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                response = await client.post(
                    webhook_url,
                    json=test_payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                logger.info(f"Webhook测试成功: {webhook_url}")
                return True
        except Exception as e:
            logger.error(f"Webhook测试失败: {str(e)}")
            return False

    async def send_alert_notification(
        self,
        alert: Alert,
        user_config: UserConfig,
    ) -> None:
        """发送预警通知

        根据用户配置选择通知渠道，同时发送邮件和Webhook（如果配置了）。

        Args:
            alert: 预警记录
            user_config: 用户配置
        """
        risk_data = await self._get_risk_data_for_alert(alert)
        tasks = []

        if user_config.notification_email:
            email_html = self._generate_alert_email_html(alert, risk_data, user_config)
            email_plain = self._generate_alert_email_plain(alert, risk_data, user_config)
            subject = f"【病害预警】{user_config.crop_type.value} - 风险指数: {risk_data.risk_index:.1f}"

            email_task = self.send_email(
                to_email=user_config.notification_email,
                subject=subject,
                html_content=email_html,
                plain_content=email_plain,
                alert_id=alert.id,
            )
            tasks.append(email_task)

        if user_config.webhook_url:
            webhook_payload = self._generate_alert_webhook_payload(alert, risk_data, user_config)
            webhook_task = self.send_webhook(
                webhook_url=user_config.webhook_url,
                payload=webhook_payload,
                alert_id=alert.id,
            )
            tasks.append(webhook_task)

        if tasks:
            await asyncio.gather(*tasks)

        alert.notified_at = datetime.utcnow()
        await self.db.commit()

    async def check_and_trigger_alerts(
        self,
        crop_type: str,
        forecast_date: datetime,
    ) -> int:
        """检查并触发预警

        查询所有用户配置，对比风险指数和用户阈值，
        对超过阈值的格点创建Alert记录并发送通知。

        Args:
            crop_type: 作物类型
            forecast_date: 预报日期

        Returns:
            int: 触发的预警数量
        """
        triggered_count = 0

        user_configs = await self._get_user_configs_by_crop_type(crop_type)
        if not user_configs:
            logger.info(f"没有找到 {crop_type} 的用户配置")
            return 0

        risk_data_list = await self._get_risk_data(crop_type, forecast_date)
        if not risk_data_list:
            logger.info(f"没有找到 {crop_type} 在 {forecast_date.date()} 的风险数据")
            return 0

        risk_map = {rg.grid_id: rg for rg in risk_data_list}

        for user_config in user_configs:
            for grid_id, risk_data in risk_map.items():
                if risk_data.risk_index < user_config.risk_threshold:
                    continue

                recent_alert = await self._get_recent_alert(
                    user_id=user_config.user_id,
                    grid_id=grid_id,
                    hours=24,
                )
                if recent_alert:
                    continue

                alert = await self._create_alert(
                    user_config=user_config,
                    risk_data=risk_data,
                    grid_id=grid_id,
                )

                if alert:
                    await self.send_alert_notification(alert, user_config)
                    triggered_count += 1

        logger.info(f"触发了 {triggered_count} 条 {crop_type} 预警")
        return triggered_count

    def _generate_alert_email_html(
        self,
        alert: Alert,
        risk_data: RiskGrid,
        user_config: UserConfig,
    ) -> str:
        """生成预警邮件HTML模板

        Args:
            alert: 预警记录
            risk_data: 风险数据
            user_config: 用户配置

        Returns:
            str: HTML邮件内容
        """
        risk_level = self._get_risk_level(risk_data.risk_index)
        risk_color = self._get_risk_color(risk_data.risk_index)
        map_url = self._generate_risk_map_url(risk_data, user_config)

        crop_name = self._get_crop_name(user_config.crop_type.value)
        prevention_advice = self._get_prevention_advice(
            risk_data.risk_index,
            user_config.crop_type.value,
        )

        grid_cell = risk_data.grid_cell
        location_str = f"经度: {grid_cell.lon:.4f}, 纬度: {grid_cell.lat:.4f}" if grid_cell else "位置未知"

        html = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>病害预警通知</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 24px;
                    border-radius: 8px 8px 0 0;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                    font-weight: 600;
                }}
                .content {{
                    background: white;
                    padding: 24px;
                    border-radius: 0 0 8px 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }}
                .risk-badge {{
                    display: inline-block;
                    padding: 8px 20px;
                    border-radius: 20px;
                    font-size: 18px;
                    font-weight: 600;
                    color: white;
                    margin: 16px 0;
                }}
                .info-card {{
                    background: #f8f9fa;
                    border-left: 4px solid {risk_color};
                    padding: 16px;
                    margin: 16px 0;
                    border-radius: 4px;
                }}
                .info-row {{
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 0;
                    border-bottom: 1px solid #eee;
                }}
                .info-row:last-child {{
                    border-bottom: none;
                }}
                .info-label {{
                    color: #666;
                    font-weight: 500;
                }}
                .info-value {{
                    font-weight: 600;
                    color: #333;
                }}
                .advice-section {{
                    background: #fff8e1;
                    border-left: 4px solid #ffc107;
                    padding: 16px;
                    margin: 16px 0;
                    border-radius: 4px;
                }}
                .advice-title {{
                    font-weight: 600;
                    color: #856404;
                    margin-bottom: 8px;
                }}
                .map-button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 12px 32px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 600;
                    text-align: center;
                    margin: 16px 0;
                }}
                .map-button:hover {{
                    opacity: 0.9;
                }}
                .footer {{
                    text-align: center;
                    color: #999;
                    font-size: 12px;
                    margin-top: 24px;
                    padding-top: 16px;
                    border-top: 1px solid #eee;
                }}
                .severity-high {{ background-color: #dc3545; }}
                .severity-medium-high {{ background-color: #fd7e14; }}
                .severity-medium {{ background-color: #ffc107; }}
                .severity-medium-low {{ background-color: #20c997; }}
                .severity-low {{ background-color: #28a745; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🌾 农业病害预警系统</h1>
                <p style="margin: 8px 0 0 0; opacity: 0.9;">您关注的作物区域发现病害风险</p>
            </div>
            <div class="content">
                <div style="text-align: center;">
                    <div class="risk-badge severity-{self._get_risk_severity_class(risk_data.risk_index)}">
                        风险等级: {risk_level}
                    </div>
                    <div style="font-size: 36px; font-weight: 700; color: {risk_color}; margin: 8px 0;">
                        {risk_data.risk_index:.1f}
                    </div>
                    <div style="color: #666;">风险指数 (0-100)</div>
                </div>

                <div class="info-card">
                    <h3 style="margin-top: 0;">📋 风险详情</h3>
                    <div class="info-row">
                        <span class="info-label">作物类型</span>
                        <span class="info-value">{crop_name}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">作物品种</span>
                        <span class="info-value">{user_config.variety_name}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">抗病等级</span>
                        <span class="info-value">{user_config.resistance_level}/5</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">预警阈值</span>
                        <span class="info-value">{user_config.risk_threshold:.1f}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">超出阈值</span>
                        <span class="info-value" style="color: #dc3545;">+{alert.threshold_exceeded:.1f}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">位置</span>
                        <span class="info-value">{location_str}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">预报日期</span>
                        <span class="info-value">{risk_data.forecast_date.strftime('%Y-%m-%d')}</span>
                    </div>
                    {'<div class="info-row"><span class="info-label">感染概率</span><span class="info-value">{risk_data.infection_probability:.1%}</span></div>' if risk_data.infection_probability is not None else ''}
                </div>

                <div style="text-align: center;">
                    <a href="{map_url}" class="map-button" target="_blank">
                        🗺️ 查看风险地图
                    </a>
                </div>

                <div class="advice-section">
                    <div class="advice-title">💡 防治建议</div>
                    <ul style="margin: 0; padding-left: 20px;">
                        {''.join(f'<li style="padding: 4px 0;">{advice}</li>' for advice in prevention_advice)}
                    </ul>
                </div>

                <div style="color: #666; font-size: 14px; margin-top: 16px;">
                    <p style="margin: 0;">{alert.message}</p>
                </div>
            </div>
            <div class="footer">
                <p>此邮件由农业病害预警系统自动发送，请勿直接回复。</p>
                <p>预警时间: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
            </div>
        </body>
        </html>
        """
        return html

    def _generate_alert_email_plain(
        self,
        alert: Alert,
        risk_data: RiskGrid,
        user_config: UserConfig,
    ) -> str:
        """生成预警邮件纯文本内容

        Args:
            alert: 预警记录
            risk_data: 风险数据
            user_config: 用户配置

        Returns:
            str: 纯文本邮件内容
        """
        risk_level = self._get_risk_level(risk_data.risk_index)
        crop_name = self._get_crop_name(user_config.crop_type.value)
        map_url = self._generate_risk_map_url(risk_data, user_config)
        prevention_advice = self._get_prevention_advice(
            risk_data.risk_index,
            user_config.crop_type.value,
        )

        grid_cell = risk_data.grid_cell
        location_str = f"经度: {grid_cell.lon:.4f}, 纬度: {grid_cell.lat:.4f}" if grid_cell else "位置未知"

        plain = f"""
【农业病害预警系统】预警通知

════════════════════════════════

风险等级: {risk_level}
风险指数: {risk_data.risk_index:.1f}/100

📋 风险详情
────────────────────────────────
作物类型: {crop_name}
作物品种: {user_config.variety_name}
抗病等级: {user_config.resistance_level}/5
预警阈值: {user_config.risk_threshold:.1f}
超出阈值: +{alert.threshold_exceeded:.1f}
位置: {location_str}
预报日期: {risk_data.forecast_date.strftime('%Y-%m-%d')}
{f"感染概率: {risk_data.infection_probability:.1%}" if risk_data.infection_probability is not None else ""}

🗺️ 查看风险地图
────────────────────────────────
{map_url}

💡 防治建议
────────────────────────────────
{chr(10).join(f'• {advice}' for advice in prevention_advice)}

📝 预警说明
────────────────────────────────
{alert.message}

════════════════════════════════
预警时间: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')} UTC

此邮件由农业病害预警系统自动发送，请勿直接回复。
        """
        return plain.strip()

    def _generate_alert_webhook_payload(
        self,
        alert: Alert,
        risk_data: RiskGrid,
        user_config: UserConfig,
    ) -> Dict[str, Any]:
        """生成Webhook payload

        Args:
            alert: 预警记录
            risk_data: 风险数据
            user_config: 用户配置

        Returns:
            Dict[str, Any]: Webhook JSON payload
        """
        risk_level = self._get_risk_level(risk_data.risk_index)
        crop_name = self._get_crop_name(user_config.crop_type.value)
        map_url = self._generate_risk_map_url(risk_data, user_config)
        prevention_advice = self._get_prevention_advice(
            risk_data.risk_index,
            user_config.crop_type.value,
        )

        grid_cell = risk_data.grid_cell

        payload = {
            "event": "alert_triggered",
            "alert_id": alert.id,
            "alert_type": alert.alert_type.value,
            "severity": alert.severity,
            "timestamp": alert.triggered_at.isoformat(),
            "risk_data": {
                "risk_index": risk_data.risk_index,
                "risk_level": risk_level,
                "infection_probability": risk_data.infection_probability,
                "forecast_date": risk_data.forecast_date.isoformat(),
                "model_version": risk_data.model_version,
            },
            "crop_info": {
                "crop_type": user_config.crop_type.value,
                "crop_name": crop_name,
                "variety_name": user_config.variety_name,
                "resistance_level": user_config.resistance_level,
            },
            "location": {
                "grid_id": risk_data.grid_id,
                "longitude": grid_cell.lon if grid_cell else None,
                "latitude": grid_cell.lat if grid_cell else None,
                "grid_x": grid_cell.grid_x if grid_cell else None,
                "grid_y": grid_cell.grid_y if grid_cell else None,
            },
            "threshold": {
                "user_threshold": user_config.risk_threshold,
                "threshold_exceeded": alert.threshold_exceeded,
            },
            "prevention_advice": prevention_advice,
            "map_url": map_url,
            "message": alert.message,
            "user_config_id": user_config.id,
            "user_id": user_config.user_id,
        }

        return payload

    async def _create_notification_log(
        self,
        alert_id: Optional[int],
        channel: NotificationChannel,
        recipient: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """创建通知日志记录

        Args:
            alert_id: 预警ID
            channel: 通知渠道
            recipient: 接收者
            status: 状态
            error_message: 错误信息（可选）
        """
        try:
            log = NotificationLog(
                alert_id=alert_id,
                channel=channel,
                recipient=recipient,
                status=status,
                error_message=error_message,
                sent_at=datetime.utcnow(),
            )
            self.db.add(log)
            await self.db.commit()
        except Exception as e:
            logger.error(f"创建通知日志失败: {str(e)}")
            await self.db.rollback()

    async def _get_user_configs_by_crop_type(
        self,
        crop_type: str,
    ) -> List[UserConfig]:
        """根据作物类型获取用户配置列表

        Args:
            crop_type: 作物类型

        Returns:
            List[UserConfig]: 用户配置列表
        """
        query = select(UserConfig).where(UserConfig.crop_type == crop_type)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_risk_data(
        self,
        crop_type: str,
        forecast_date: datetime,
    ) -> List[RiskGrid]:
        """获取指定作物类型和日期的风险数据

        Args:
            crop_type: 作物类型
            forecast_date: 预报日期

        Returns:
            List[RiskGrid]: 风险数据列表
        """
        query = (
            select(RiskGrid)
            .join(GridCell, RiskGrid.grid_id == GridCell.id)
            .where(
                and_(
                    RiskGrid.crop_type == crop_type,
                    func.date(RiskGrid.forecast_date) == func.date(forecast_date),
                )
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_risk_data_for_alert(
        self,
        alert: Alert,
    ) -> Optional[RiskGrid]:
        """获取预警关联的风险数据

        Args:
            alert: 预警记录

        Returns:
            Optional[RiskGrid]: 风险数据
        """
        query = (
            select(RiskGrid)
            .join(GridCell, RiskGrid.grid_id == GridCell.id)
            .where(
                and_(
                    RiskGrid.grid_id == alert.grid_id,
                    func.date(RiskGrid.forecast_date) == func.date(alert.triggered_at),
                )
            )
            .order_by(RiskGrid.calculated_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def _get_recent_alert(
        self,
        user_id: int,
        grid_id: int,
        hours: int = 24,
    ) -> Optional[Alert]:
        """检查指定用户在指定格点是否有近期预警

        Args:
            user_id: 用户ID
            grid_id: 格点ID
            hours: 时间窗口（小时）

        Returns:
            Optional[Alert]: 近期预警记录（如果存在）
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        query = select(Alert).where(
            and_(
                Alert.user_id == user_id,
                Alert.grid_id == grid_id,
                Alert.triggered_at >= cutoff_time,
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def _create_alert(
        self,
        user_config: UserConfig,
        risk_data: RiskGrid,
        grid_id: int,
    ) -> Optional[Alert]:
        """创建预警记录

        Args:
            user_config: 用户配置
            risk_data: 风险数据
            grid_id: 格点ID

        Returns:
            Optional[Alert]: 创建的预警记录
        """
        try:
            threshold_exceeded = risk_data.risk_index - user_config.risk_threshold
            severity = self._get_severity(risk_data.risk_index)
            alert_type = self._get_alert_type(risk_data.risk_index)
            risk_level = self._get_risk_level(risk_data.risk_index)
            crop_name = self._get_crop_name(user_config.crop_type.value)

            message = (
                f"您关注的{crop_name}区域（{user_config.variety_name}）"
                f"检测到{risk_level}级病害风险，风险指数{risk_data.risk_index:.1f}，"
                f"超出您设置的阈值{threshold_exceeded:.1f}。请及时采取防治措施。"
            )

            alert = Alert(
                user_id=user_config.user_id,
                grid_id=grid_id,
                alert_type=alert_type,
                severity=severity,
                threshold_exceeded=threshold_exceeded,
                message=message,
                triggered_at=datetime.utcnow(),
            )

            self.db.add(alert)
            await self.db.commit()
            await self.db.refresh(alert)

            logger.info(
                f"创建预警: user={user_config.user_id}, "
                f"grid={grid_id}, risk={risk_data.risk_index:.1f}"
            )
            return alert
        except Exception as e:
            logger.error(f"创建预警失败: {str(e)}")
            await self.db.rollback()
            return None

    @staticmethod
    def _get_risk_level(risk_index: float) -> str:
        """获取风险等级描述（中文，使用统一阈值）

        与前端地图颜色图例阈值完全一致，确保跨日期显示一致性。

        Args:
            risk_index: 风险指数 (0-100)

        Returns:
            str: 风险等级
        """
        from app.core.constants import get_risk_level
        return get_risk_level(risk_index, use_chinese=True)

    @staticmethod
    def _get_risk_color(risk_index: float) -> str:
        """获取风险等级对应的颜色（使用统一配色方案）

        与前端地图颜色图例完全一致，确保跨日期显示一致性。

        Args:
            risk_index: 风险指数 (0-100)

        Returns:
            str: 十六进制颜色值
        """
        from app.core.constants import get_risk_color
        return get_risk_color(risk_index)

    @staticmethod
    def _get_risk_severity_class(risk_index: float) -> str:
        """获取风险等级对应的CSS类名（使用统一阈值）

        Args:
            risk_index: 风险指数 (0-100)

        Returns:
            str: CSS类名
        """
        from app.core.constants import get_risk_level_en
        return get_risk_level_en(risk_index)

    @staticmethod
    def _get_severity(risk_index: float) -> str:
        """获取严重程度（使用统一阈值）

        Args:
            risk_index: 风险指数 (0-100)

        Returns:
            str: 严重程度
        """
        if risk_index < 40:
            return "mild"
        elif risk_index < 70:
            return "moderate"
        else:
            return "severe"

    @staticmethod
    def _get_alert_type(risk_index: float) -> AlertType:
        """获取预警类型（使用统一阈值）

        Args:
            risk_index: 风险指数 (0-100)

        Returns:
            AlertType: 预警类型
        """
        from app.core.constants import RISK_THRESHOLDS
        if risk_index >= RISK_THRESHOLDS["high"]:
            return AlertType.WARNING
        else:
            return AlertType.RISK

    @staticmethod
    def _get_crop_name(crop_type: str) -> str:
        """获取作物名称

        Args:
            crop_type: 作物类型枚举值

        Returns:
            str: 作物中文名称
        """
        crop_names = {
            "wheat": "小麦",
            "potato": "马铃薯",
            "corn": "玉米",
            "rice": "水稻",
        }
        return crop_names.get(crop_type, crop_type)

    def _generate_risk_map_url(
        self,
        risk_data: RiskGrid,
        user_config: UserConfig,
    ) -> str:
        """生成风险地图链接

        Args:
            risk_data: 风险数据
            user_config: 用户配置

        Returns:
            str: 风险地图URL
        """
        grid_cell = risk_data.grid_cell
        params = {
            "crop_type": user_config.crop_type.value,
            "date": risk_data.forecast_date.strftime("%Y-%m-%d"),
        }
        if grid_cell:
            params["lat"] = f"{grid_cell.lat:.4f}"
            params["lon"] = f"{grid_cell.lon:.4f}"

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.frontend_base_url}/risk-map?{query_string}"

    @staticmethod
    def _get_prevention_advice(risk_index: float, crop_type: str) -> List[str]:
        """根据风险指数和作物类型获取防治建议（使用统一阈值）

        阈值与前端地图颜色图例完全一致，确保跨模块一致性。

        Args:
            risk_index: 风险指数
            crop_type: 作物类型

        Returns:
            List[str]: 防治建议列表
        """
        from app.core.constants import RISK_THRESHOLDS
        base_advice = []

        if risk_index >= RISK_THRESHOLDS["high"]:
            base_advice.extend([
                "立即喷施保护性杀菌剂，建议选用内吸性强的药剂",
                "增加巡查频率，每日观察病害发展情况",
                "及时清除病叶、病株，减少侵染源",
                "避免在露水未干时进行农事操作，防止人为传播",
            ])
        elif risk_index >= RISK_THRESHOLDS["medium"]:
            base_advice.extend([
                "建议喷施预防性杀菌剂，注意轮换用药避免抗药性",
                "加强田间巡查，每2-3天观察一次",
                "保持田间通风透光，降低湿度",
            ])
        elif risk_index >= RISK_THRESHOLDS["low"]:
            base_advice.extend([
                "注意田间观察，重点关注易感病区域",
                "及时排除田间积水，降低土壤湿度",
                "合理施肥，避免偏施氮肥，增施磷钾肥",
            ])
        else:
            base_advice.extend([
                "继续保持正常田间管理",
                "定期巡查田间，关注天气变化",
                "关注后续预报信息",
            ])

        crop_specific = {
            "wheat": [
                "注意防治条锈病、叶锈病、白粉病",
                "小麦抽穗期重点预防赤霉病",
            ],
            "potato": [
                "注意防治晚疫病，重点关注叶片背面",
                "块茎形成期加强晚疫病监测",
            ],
            "corn": [
                "注意防治大斑病、小斑病",
                "玉米抽雄期重点预防灰斑病",
            ],
            "rice": [
                "注意防治稻瘟病、纹枯病",
                "水稻分蘖期和抽穗期是关键防治时期",
            ],
        }

        base_advice.extend(crop_specific.get(crop_type, []))
        return base_advice
