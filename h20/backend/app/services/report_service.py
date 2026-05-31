from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.piecharts import Pie

from app.services.base import BaseService
from app.services.gnn_service import GNNAnomalyService
from app.services.privacy_coin_service import PrivacyCoinAnalysisService
from app.repositories import (
    TransactionRepository, AddressRepository, PatternRepository
)


RISK_COLORS = {
    "critical": colors.HexColor("#7c3aed"),
    "high": colors.HexColor("#ef4444"),
    "medium": colors.HexColor("#f59e0b"),
    "low": colors.HexColor("#10b981"),
    "info": colors.HexColor("#3b82f6")
}


class ComplianceReportService(BaseService[TransactionRepository]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, TransactionRepository)
        self.addr_repo = AddressRepository(db)
        self.pattern_repo = PatternRepository(db)
        self.gnn_service = GNNAnomalyService(db)
        self.privacy_service = PrivacyCoinAnalysisService(db)

    async def generate_address_compliance_report(
        self,
        address: str,
        report_format: str = "pdf",
        include_visualizations: bool = True
    ) -> Dict[str, Any]:
        report_data = await self._collect_report_data(address)

        if report_format == "pdf":
            pdf_bytes = self._generate_pdf_report(address, report_data, include_visualizations)
            return {
                "address": address,
                "report_type": "address_compliance",
                "format": "pdf",
                "generated_at": datetime.utcnow().isoformat(),
                "file_size": len(pdf_bytes),
                "content": pdf_bytes,
                "filename": f"compliance_report_{address}.pdf",
                "summary": report_data["summary"]
            }
        else:
            return {
                "address": address,
                "report_type": "address_compliance",
                "format": "json",
                "generated_at": datetime.utcnow().isoformat(),
                "data": report_data
            }

    async def _collect_report_data(self, address: str) -> Dict[str, Any]:
        gnn_result = await self.gnn_service.calculate_gnn_anomaly_score(address, depth=3)
        privacy_result = await self.privacy_service.analyze_privacy_coin_associations(address, depth=2)
        threat_intel = await self.privacy_service.generate_privacy_threat_intel(privacy_result)
        gnn_explanations = await self.gnn_service.explain_anomaly_score(address, gnn_result)

        patterns = await self.pattern_repo.get_address_patterns(address)
        suspicious_patterns = []
        for p in patterns:
            suspicious_patterns.append({
                "id": p.id,
                "type": p.pattern_type,
                "severity": p.severity,
                "confidence": p.confidence,
                "description": p.description,
                "detected_at": p.detected_at.isoformat() if p.detected_at else None
            })

        overall_risk_score = max(
            gnn_result.get("anomaly_score", 0),
            privacy_result.get("overall_risk_score", 0)
        )

        risk_level = self._get_risk_level(overall_risk_score)

        summary = {
            "overall_risk_score": overall_risk_score,
            "risk_level": risk_level,
            "gnn_anomaly_score": gnn_result.get("anomaly_score", 0),
            "privacy_risk_score": privacy_result.get("overall_risk_score", 0),
            "suspicious_pattern_count": len(suspicious_patterns),
            "privacy_coin_associations": privacy_result.get("privacy_coin_count", 0),
            "report_date": datetime.utcnow().isoformat(),
            "analysis_period": "Last 90 days"
        }

        return {
            "summary": summary,
            "gnn_analysis": gnn_result,
            "gnn_explanations": gnn_explanations,
            "privacy_analysis": privacy_result,
            "threat_intelligence": threat_intel,
            "suspicious_patterns": suspicious_patterns
        }

    def _generate_pdf_report(
        self,
        address: str,
        report_data: Dict[str, Any],
        include_visualizations: bool = True
    ) -> bytes:
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        styles = getSampleStyleSheet()
        self._setup_styles(styles)

        story = []

        self._add_cover_page(story, address, report_data, styles)
        story.append(PageBreak())

        self._add_executive_summary(story, report_data, styles)
        story.append(PageBreak())

        self._add_risk_assessment_section(story, report_data, styles, include_visualizations)
        story.append(PageBreak())

        self._add_gnn_analysis_section(story, report_data, styles, include_visualizations)
        story.append(PageBreak())

        self._add_privacy_analysis_section(story, report_data, styles)
        story.append(PageBreak())

        self._add_suspicious_patterns_section(story, report_data, styles)

        self._add_footer(story, styles)

        doc.build(story)

        return buffer.getvalue()

    def _setup_styles(self, styles):
        styles.add(ParagraphStyle(
            name='CoverTitle',
            parent=styles['Title'],
            fontSize=28,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=20,
            alignment=TA_CENTER
        ))

        styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor("#1e40af"),
            spaceBefore=20,
            spaceAfter=12,
            borderWidth=1,
            borderColor=colors.HexColor("#3b82f6"),
            borderPadding=5
        ))

        styles.add(ParagraphStyle(
            name='SubSectionTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=15,
            spaceAfter=8
        ))

        styles.add(ParagraphStyle(
            name='RiskText',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor("#334155"),
            spaceAfter=6,
            leading=14
        ))

        styles.add(ParagraphStyle(
            name='FooterText',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_CENTER
        ))

    def _add_cover_page(self, story, address: str, report_data: Dict[str, Any], styles):
        story.append(Spacer(1, 3*cm))

        risk_level = report_data["summary"]["risk_level"]
        risk_score = report_data["summary"]["overall_risk_score"]

        logo_drawing = Drawing(400, 80)
        logo_drawing.add(Rect(0, 0, 400, 80,
                        fillColor=colors.HexColor("#eff6ff"),
                        strokeColor=colors.HexColor("#3b82f6"),
                        strokeWidth=2))
        logo_drawing.add(String(200, 50, "Bitcoin Transaction Graph Analysis",
                             textAnchor="middle", fontSize=16,
                             fillColor=colors.HexColor("#1e40af")))
        story.append(logo_drawing)

        story.append(Spacer(1, 2*cm))
        story.append(Paragraph("合规调查报告", styles['CoverTitle']))
        story.append(Spacer(1, 1*cm))

        story.append(Paragraph(
            f"地址: <code>{address}</code>",
            styles['Normal']))
        story.append(Spacer(1, 0.5*cm))

        risk_color = RISK_COLORS.get(risk_level, colors.HexColor("#10b981"))
        risk_label = self._get_risk_label(risk_level)

        risk_drawing = Drawing(300, 100)
        risk_drawing.add(Rect(50, 0, 200, 80,
                        fillColor=risk_color,
                        strokeColor=risk_color,
                        strokeWidth=2))
        risk_drawing.add(String(150, 45, f"风险等级: {risk_label}",
                             textAnchor="middle", fontSize=18,
                             fillColor=colors.white))
        risk_drawing.add(String(150, 20, f"风险评分: {risk_score:.1f}/100",
                             textAnchor="middle", fontSize=12,
                             fillColor=colors.white))
        story.append(risk_drawing)

        story.append(Spacer(1, 3*cm))

        report_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        story.append(Paragraph(f"报告生成时间: {report_date}", styles['Normal']))
        story.append(Paragraph("报告类型: 地址合规调查", styles['Normal']))
        story.append(Paragraph("分析深度: 3层关联", styles['Normal']))

    def _add_executive_summary(self, story, report_data: Dict[str, Any], styles):
        story.append(Paragraph("执行摘要", styles['SectionTitle']))

        summary = report_data["summary"]
        threat_intel = report_data["threat_intelligence"]

        story.append(Paragraph(
            "本报告对指定比特币地址进行了全面的合规分析，"
            "包括图神经网络异常检测、隐私币关联分析、以及可疑模式识别。",
            styles['RiskText']
        ))
        story.append(Spacer(1, 0.5*cm))

        summary_data = [
            ["指标", "数值", "风险等级"],
            ["整体风险评分", f"{summary['overall_risk_score']:.1f}/100", self._get_risk_label(summary['risk_level'])],
            ["GNN异常评分", f"{summary['gnn_anomaly_score']:.1f}/100", self._get_risk_label(self._get_risk_level(summary['gnn_anomaly_score']))],
            ["隐私风险评分", f"{summary['privacy_risk_score']:.1f}/100", self._get_risk_label(self._get_risk_level(summary['privacy_risk_score']))],
            ["可疑模式数量", str(summary['suspicious_pattern_count']), "高" if summary['suspicious_pattern_count'] > 0 else "低"],
            ["隐私币关联数", str(summary['privacy_coin_associations']), "高" if summary['privacy_coin_associations'] > 0 else "低"]
        ]

        t = Table(summary_data, colWidths=[5*cm, 4*cm, 3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#334155")),
        ]))
        story.append(t)

        story.append(Spacer(1, 1*cm))
        story.append(Paragraph("威胁情报摘要", styles['SubSectionTitle']))

        indicator_data = [["类型", "描述", "严重程度"]]
        for indicator in threat_intel.get("threat_indicators", []):
            indicator_data.append([
                indicator.get("type", ""),
                indicator.get("description", ""),
                indicator.get("severity", "")
            ])

        if len(indicator_data) > 1:
            t2 = Table(indicator_data, colWidths=[4*cm, 7*cm, 3*cm])
            t2.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#334155")),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(t2)

        if threat_intel.get("recommended_actions"):
            story.append(Spacer(1, 0.5*cm))
            story.append(Paragraph("建议措施", styles['SubSectionTitle']))
            for action in threat_intel["recommended_actions"]:
                story.append(Paragraph(f"• {action}", styles['RiskText']))

        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(
            f"<b>总结:</b> {threat_intel.get('summary', '')}",
            styles['RiskText']
        ))

    def _add_risk_assessment_section(self, story, report_data: Dict[str, Any], styles, include_vis: bool):
        story.append(Paragraph("风险评估详情", styles['SectionTitle']))

        summary = report_data["summary"]

        story.append(Paragraph(
            "本章节详细展示该地址的各项风险指标，包括基础风险特征、"
            "交易模式分析、以及风险趋势。",
            styles['RiskText']
        ))

        if include_vis:
            story.append(Spacer(1, 0.5*cm))
            self._add_risk_score_chart(story, summary)

        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("风险评估维度", styles['SubSectionTitle']))

        features = report_data["gnn_analysis"].get("features", {})
        risk_dimensions = [
            ["评估维度", "数值", "说明"],
            ["交易金额分布熵", f"{features.get('value_entropy', 0):.4f}", "数值越低越可疑"],
            ["异常模式评分", f"{features.get('anomaly_pattern_score', 0):.4f}", ">0.5 表示可疑"],
            ["资金流动比率", f"{features.get('flow_ratio', 0):.4f}", "接近1表示中转特征"],
            ["输入金额标准差", f"{features.get('std_in_value', 0):.4f}", "波动越大越可疑"],
            ["聚类系数", f"{features.get('clustering_coefficient', 0):.4f}", ">0.4 表示密集关联"],
            ["PageRank 分数", f"{features.get('page_rank', 0):.2f}", "越高越重要"],
            ["入度", f"{features.get('in_degree', 0):.0f}", "输入交易数量"],
            ["出度", f"{features.get('out_degree', 0):.0f}", "输出交易数量"]
        ]

        t = Table(risk_dimensions, colWidths=[4*cm, 3*cm, 5*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#334155")),
        ]))
        story.append(t)

    def _add_risk_score_chart(self, story, summary: Dict[str, Any]):
        d = Drawing(400, 200)

        pie = Pie()
        pie.x = 50
        pie.y = 20
        pie.height = 150
        pie.data = [
            summary['gnn_anomaly_score'],
            100 - summary['gnn_anomaly_score']
        ]
        pie.labels = ['风险分数', '剩余']
        pie.slices.strokeWidth = 1

        risk_level = summary['risk_level']
        pie.slices[0].fillColor = RISK_COLORS.get(risk_level, colors.HexColor("#10b981"))
        pie.slices[1].fillColor = colors.HexColor("#e2e8f0")

        d.add(pie)

        d.add(String(200, 180, "GNN 异常风险评分分布",
                     textAnchor="middle", fontSize=12,
                     fillColor=colors.HexColor("#1e293b")))

        story.append(d)

    def _add_gnn_analysis_section(self, story, report_data: Dict[str, Any], styles, include_vis: bool):
        story.append(Paragraph("图神经网络异常分析", styles['SectionTitle']))

        gnn_result = report_data["gnn_analysis"]
        explanations = report_data["gnn_explanations"]

        story.append(Paragraph(
            "使用图神经网络(GNN)技术对地址的交易图进行分析，"
            "从多个维度提取特征并计算异常评分。",
            styles['RiskText']
        ))
        story.append(Spacer(1, 0.5*cm))

        gnn_data = [
            ["项目", "详情"],
            ["GNN 异常评分", f"{gnn_result.get('anomaly_score', 0):.2f}/100"],
            ["风险等级", self._get_risk_label(gnn_result.get('risk_level', 'low'))],
            ["分析深度", f"{gnn_result.get('analysis_depth', 3)} 层"],
            ["子图节点数", str(gnn_result.get('subgraph_size', {}).get('nodes', 0))],
            ["子图边数", str(gnn_result.get('subgraph_size', {}).get('edges', 0))]
        ]

        t = Table(gnn_data, colWidths=[5*cm, 8*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#334155")),
        ]))
        story.append(t)

        if explanations:
            story.append(Spacer(1, 1*cm))
            story.append(Paragraph("异常解释", styles['SubSectionTitle']))

            for exp in explanations:
                sev_color = RISK_COLORS.get(exp.get("severity", "low"),
                                             colors.HexColor("#10b981"))
                exp_text = (
                    f"<font color='{sev_color.hexval()}'><b>[{exp.get('type', '')}]</b></font> "
                    f"{exp.get('description', '')} "
                    f"(贡献度: {exp.get('contribution', 0):.1f}%)"
                )
                story.append(Paragraph(exp_text, styles['RiskText']))
                story.append(Spacer(1, 0.2*cm))

        if include_vis:
            story.append(Spacer(1, 0.5*cm))
            self._add_feature_importance_chart(story, gnn_result)

    def _add_feature_importance_chart(self, story, gnn_result: Dict[str, Any]):
        importance = gnn_result.get("feature_importance", {})
        if not importance:
            return

        d = Drawing(400, 200)

        bar = HorizontalBarChart()
        bar.x = 100
        bar.y = 30
        bar.height = 140
        bar.width = 250

        features = list(importance.keys())[:6]
        values = [[v * 100 for v in list(importance.values())[:6]]]

        bar.data = values
        bar.categoryAxis.categoryNames = features
        bar.valueAxis.valueMin = 0
        bar.valueAxis.valueMax = 100

        bar.bars[0].fillColor = colors.HexColor("#3b82f6")

        d.add(bar)
        d.add(String(225, 185, "特征重要性 (%)",
                     textAnchor="middle", fontSize=12,
                     fillColor=colors.HexColor("#1e293b")))

        story.append(d)

    def _add_privacy_analysis_section(self, story, report_data: Dict[str, Any], styles):
        story.append(Paragraph("隐私币关联分析", styles['SectionTitle']))

        privacy_result = report_data["privacy_analysis"]

        story.append(Paragraph(
            "分析该地址与隐私币（如Monero、Zcash等）的关联，"
            "检测混币模式和跨链交易特征。",
            styles['RiskText']
        ))
        story.append(Spacer(1, 0.5*cm))

        privacy_data = [
            ["项目", "数值", "风险等级"],
            ["隐私风险评分", f"{privacy_result.get('overall_risk_score', 0):.1f}/100",
             self._get_risk_label(privacy_result.get('risk_level', 'low'))],
            ["检测到隐私币类型", str(privacy_result.get('privacy_coin_count', 0)), "高" if privacy_result.get('privacy_coin_count', 0) > 0 else "低"],
            ["关联地址数量", str(privacy_result.get('associated_address_count', 0)), "-"],
            ["可疑交易数量", str(len(privacy_result.get('suspicious_transactions', []))), "高" if len(privacy_result.get('suspicious_transactions', [])) > 0 else "低"],
            ["隐私相关总金额", f"{privacy_result.get('total_privacy_related_value', 0):.4f} BTC", "-"]
        ]

        t = Table(privacy_data, colWidths=[5*cm, 4*cm, 3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#334155")),
        ]))
        story.append(t)

        detected_coins = privacy_result.get("detected_privacy_coins", {})
        if detected_coins:
            story.append(Spacer(1, 0.8*cm))
            story.append(Paragraph("检测到的隐私币类型", styles['SubSectionTitle']))

            for coin_type, matches in detected_coins.items():
                for match in matches:
                    coin_text = (
                        f"<b>{match.get('coin_name', coin_type)}:</b> "
                        f"{match.get('address', '')[:12]}... "
                        f"({match.get('description', '')})"
                    )
                    story.append(Paragraph(coin_text, styles['RiskText']))

        mixing_patterns = privacy_result.get("mixing_patterns", [])
        if mixing_patterns:
            story.append(Spacer(1, 0.8*cm))
            story.append(Paragraph("检测到的混币模式", styles['SubSectionTitle']))

            for pattern in mixing_patterns:
                text = (
                    f"• <b>{pattern.get('type', '')}:</b> "
                    f"{pattern.get('description', '')} "
                    f"(置信度: {pattern.get('confidence', 0):.0%})"
                )
                story.append(Paragraph(text, styles['RiskText']))

        cross_chain = privacy_result.get("cross_chain_links", [])
        if cross_chain:
            story.append(Spacer(1, 0.8*cm))
            story.append(Paragraph("跨链关联", styles['SubSectionTitle']))

            for link in cross_chain:
                if link.get('type') == 'privacy_coin':
                    link_text = (
                        f"• <b>{link.get('coin_name', '')}:</b> "
                        f"{link.get('address', '')[:12]}... "
                        f"{link.get('transaction_count', 0)} 笔交易, "
                        f"总金额 {link.get('total_value', 0):.4f} BTC"
                    )
                else:
                    link_text = (
                        f"• <b>网关 {link.get('gateway_name', '')}:</b> "
                        f"{link.get('gateway_type', '')} "
                        f"风险等级: {link.get('risk_level', '')}"
                    )
                story.append(Paragraph(link_text, styles['RiskText']))

    def _add_suspicious_patterns_section(self, story, report_data: Dict[str, Any], styles):
        story.append(Paragraph("可疑交易模式", styles['SectionTitle']))

        patterns = report_data["suspicious_patterns"]

        if not patterns:
            story.append(Paragraph(
                "未检测到明确的可疑交易模式。",
                styles['RiskText']
            ))
            return

        story.append(Paragraph(
            f"共检测到 {len(patterns)} 个可疑交易模式，详情如下：",
            styles['RiskText']
        ))
        story.append(Spacer(1, 0.5*cm))

        pattern_data = [
            ["模式类型", "严重程度", "置信度", "描述", "检测时间"]
        ]
        for p in patterns:
            pattern_data.append([
                p.get('type', ''),
                p.get('severity', ''),
                f"{p.get('confidence', 0):.0%}",
                p.get('description', ''),
                p.get('detected_at', '')[:10] if p.get('detected_at') else ''
            ])

        t = Table(pattern_data, colWidths=[2.5*cm, 2*cm, 1.5*cm, 5.5*cm, 2.5*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#334155")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('WORDWRAP', (0, 0), (-1, -1), True),
        ]))
        story.append(t)

        story.append(Spacer(1, 1*cm))
        story.append(Paragraph("可疑交易明细", styles['SubSectionTitle']))

        suspicious_txs = report_data["privacy_analysis"].get("suspicious_transactions", [])
        if suspicious_txs:
            tx_data = [
                ["交易ID", "方向", "金额 (BTC)", "类型", "时间戳"]
            ]
            for tx in suspicious_txs[:15]:
                direction = "转入" if tx.get('direction') == 'incoming' else "转出"
                priv_type = tx.get('privacy_type') or tx.get('gateway_info', {}).get('name', '')
                tx_data.append([
                    tx.get('txid', '')[:16] + "...",
                    direction,
                    f"{tx.get('value', 0):.4f}",
                    priv_type,
                    datetime.fromtimestamp(tx.get('timestamp', 0)).strftime("%Y-%m-%d")
                ])

            if len(tx_data) > 1:
                t2 = Table(tx_data, colWidths=[3.5*cm, 1.5*cm, 2.5*cm, 3*cm, 2.5*cm])
                t2.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#dc2626")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#fef2f2")),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#fecaca")),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#334155")),
                ]))
                story.append(t2)
        else:
            story.append(Paragraph("暂无可疑交易明细。", styles['RiskText']))

    def _add_footer(self, story, styles):
        story.append(Spacer(1, 2*cm))
        story.append(Paragraph("-" * 80, styles['FooterText']))
        story.append(Paragraph(
            "本报告由比特币交易图分析系统自动生成，仅供合规调查参考。",
            styles['FooterText']
        ))
        story.append(Paragraph(
            f"报告生成时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            styles['FooterText']
        ))

    def _get_risk_level(self, score: float) -> str:
        if score >= 75:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 25:
            return "medium"
        else:
            return "low"

    def _get_risk_label(self, level: str) -> str:
        labels = {
            "critical": "极高风险",
            "high": "高风险",
            "medium": "中风险",
            "low": "低风险"
        }
        return labels.get(level, "未知")

    async def generate_batch_compliance_report(
        self,
        addresses: List[str],
        report_format: str = "pdf"
    ) -> Dict[str, Any]:
        reports = []
        for address in addresses:
            report = await self.generate_address_compliance_report(address, report_format, False)
            reports.append(report)

        return {
            "report_count": len(reports),
            "reports": reports,
            "generated_at": datetime.utcnow().isoformat()
        }
