from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.analysis.market_power import MarketPowerAnalyzer
from app.auction.auction_service import AuctionService
from app.schemas.schemas import (
    MarketPowerAnalysisSchema,
    MarketPowerReportSchema,
    CollusionRiskSchema
)
from app.models import models

router = APIRouter(prefix="/api/market-power", tags=["市场势力分析"])


@router.get("/auction/{auction_id}", response_model=MarketPowerAnalysisSchema)
async def analyze_auction_market_power(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(models.Auction).filter(models.Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail=f"Auction {auction_id} not found")

    if auction.current_round < 3:
        raise HTTPException(
            status_code=400,
            detail="Need at least 3 rounds of data for market power analysis"
        )

    service = AuctionService(db)
    auction_state = service._build_auction_state(auction)

    analyzer = MarketPowerAnalyzer(auction_state)
    analysis = analyzer.analyze()

    report = models.MarketPowerReport(
        auction_id=auction_id,
        hhi_index=analysis.hhi_index,
        concentration_level=analysis.concentration_level,
        overall_risk_level=analysis.overall_risk_level,
        market_power_scores=analysis.market_power_scores,
        winning_shares=analysis.winning_bidder_shares,
        collusion_risks=[{
            "bidder_pair": list(r.bidder_pair),
            "risk_score": r.risk_score,
            "risk_level": r.risk_level,
            "evidence": r.evidence
        } for r in analysis.collusion_risks],
        suspicious_patterns=analysis.suspicious_patterns
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "hhi_index": analysis.hhi_index,
        "concentration_level": analysis.concentration_level,
        "collusion_risks": [{
            "bidder_pair": list(r.bidder_pair),
            "risk_score": r.risk_score,
            "risk_level": r.risk_level,
            "evidence": r.evidence
        } for r in analysis.collusion_risks],
        "market_power_scores": analysis.market_power_scores,
        "winning_bidder_shares": analysis.winning_bidder_shares,
        "suspicious_patterns": analysis.suspicious_patterns,
        "overall_risk_level": analysis.overall_risk_level
    }


@router.get("/auction/{auction_id}/reports", response_model=List[MarketPowerReportSchema])
async def get_auction_market_power_reports(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(models.Auction).filter(models.Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail=f"Auction {auction_id} not found")

    reports = db.query(models.MarketPowerReport).filter(
        models.MarketPowerReport.auction_id == auction_id
    ).order_by(models.MarketPowerReport.created_at.desc()).all()

    return reports


@router.get("/report/{report_id}", response_model=MarketPowerReportSchema)
async def get_market_power_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(models.MarketPowerReport).filter(models.MarketPowerReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail=f"Market power report {report_id} not found")
    return report


@router.get("/auction/{auction_id}/hhi")
async def get_hhi_index(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(models.Auction).filter(models.Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail=f"Auction {auction_id} not found")

    service = AuctionService(db)
    auction_state = service._build_auction_state(auction)
    analyzer = MarketPowerAnalyzer(auction_state)

    hhi = analyzer._compute_hhi()
    concentration = analyzer._get_concentration_level(hhi)
    shares = analyzer._compute_winning_shares()

    return {
        "auction_id": auction_id,
        "hhi_index": round(hhi, 2),
        "concentration_level": concentration,
        "winning_shares": {k: round(v, 4) for k, v in shares.items()},
        "interpretation": {
            "unconcentrated": "HHI < 1500: 市场竞争充分",
            "moderately_concentrated": "1500 ≤ HHI < 2500: 市场中度集中",
            "highly_concentrated": "HHI ≥ 2500: 市场高度集中，存在垄断风险"
        }.get(concentration, "")
    }


@router.get("/auction/{auction_id}/collusion-risks")
async def get_collusion_risks(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(models.Auction).filter(models.Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail=f"Auction {auction_id} not found")

    if auction.current_round < 3:
        raise HTTPException(
            status_code=400,
            detail="Need at least 3 rounds of data for collusion detection"
        )

    service = AuctionService(db)
    auction_state = service._build_auction_state(auction)
    analyzer = MarketPowerAnalyzer(auction_state)
    risks = analyzer._detect_collusion()

    return {
        "auction_id": auction_id,
        "total_pairs_analyzed": len(auction_state.bidders) * (len(auction_state.bidders) - 1) // 2,
        "high_risk_pairs": sum(1 for r in risks if r.risk_level == "high"),
        "medium_risk_pairs": sum(1 for r in risks if r.risk_level == "medium"),
        "low_risk_pairs": sum(1 for r in risks if r.risk_level == "low"),
        "risks": [{
            "bidder_pair": list(r.bidder_pair),
            "risk_score": r.risk_score,
            "risk_level": r.risk_level,
            "evidence": r.evidence
        } for r in risks]
    }


@router.get("/auction/{auction_id}/market-power-scores")
async def get_market_power_scores(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(models.Auction).filter(models.Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail=f"Auction {auction_id} not found")

    service = AuctionService(db)
    auction_state = service._build_auction_state(auction)
    analyzer = MarketPowerAnalyzer(auction_state)
    scores = analyzer._compute_market_power_scores()

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return {
        "auction_id": auction_id,
        "market_power_scores": [
            {"bidder_id": bidder_id, "score": round(score, 4),
             "dominance_level": "high" if score > 0.7 else "medium" if score > 0.4 else "low"}
            for bidder_id, score in sorted_scores
        ],
        "dominant_bidder": sorted_scores[0] if sorted_scores else None
    }
