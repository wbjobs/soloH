from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import (
    StrategyCreate, StrategyResponse, CompetitionCreate, Competition,
    CompetitionResultResponse, StrategyUploadResponse
)
from app.auction.competition_service import CompetitionService

router = APIRouter(tags=["strategies"])


@router.get("/strategies")
def list_strategies(
    include_builtin: bool = Query(True, description="Include built-in strategies"),
    db: Session = Depends(get_db)
):
    service = CompetitionService(db)
    return service.list_strategies(include_builtin=include_builtin)


@router.get("/strategies/example")
def get_strategy_example():
    example_code = '''from typing import List, Dict, Any
from app.strategies.base_strategy import BaseStrategy

class MyCustomStrategy(BaseStrategy):
    """
    Custom bidding strategy example.
    Extend BaseStrategy and implement decide_bid method.
    """
    name = "my_custom_strategy"
    description = "A custom bidding strategy"

    def decide_bid(
        self,
        bidder,
        auction_state,
        round_number
    ) -> List[Dict[str, Any]]:
        """
        Decide what bids to place in this round.

        Args:
            bidder: BidderState object with bidder info and valuations
            auction_state: AuctionState object with current auction state
            round_number: Current round number

        Returns:
            List of bid dictionaries, each with:
                - item_id: int (for single item bids)
                - bundle: Dict[int, int] (for package bids)
                - price: float
                - quantity: int (optional, default 1)
        """
        prices = auction_state.get_current_prices()
        bids = []

        # Get demand set based on current prices
        demand_bundle = bidder.get_demand_set(prices)

        for item_id in demand_bundle:
            value = bidder.get_individual_value(item_id)
            price = prices.get(item_id, 0.0)

            # Bid if value exceeds price by some margin
            if value > price * 1.1:
                bids.append({
                    "item_id": item_id,
                    "price": price + auction_state.bid_increment,
                    "quantity": 1
                })

        return bids

    def observe_history(
        self,
        bidder,
        auction_state,
        round_number
    ):
        """
        Optional: observe auction history to learn from competitors.
        Called before decide_bid each round.
        """
        if round_number > 0 and auction_state.round_history:
            last_round = auction_state.round_history[-1]
            # Analyze competitor bids from last round
            for bid in last_round.bids:
                if bid.get("bidder_id") != bidder.bidder_id:
                    # Track competitor behavior
                    pass
'''
    return {
        "example_code": example_code,
        "required_methods": ["decide_bid"],
        "optional_methods": ["observe_history"],
        "available_data": {
            "bidder": ["base_values", "complementary_values", "budget", "risk_aversion", "activity_score", "history_bids"],
            "auction_state": ["get_current_prices()", "get_excess_demand()", "round_history", "items", "bidders", "current_round"]
        }
    }


@router.post("/strategies", response_model=StrategyUploadResponse)
def upload_strategy(
    name: str = Form(..., description="Strategy name"),
    description: Optional[str] = Form(None, description="Strategy description"),
    author: Optional[str] = Form(None, description="Author name"),
    is_public: bool = Form(True, description="Make strategy public"),
    file: UploadFile = File(..., description="Python file with strategy class"),
    db: Session = Depends(get_db)
):
    try:
        contents = file.file.read()
        code = contents.decode("utf-8")

        if len(code) > 100000:
            raise HTTPException(status_code=400, detail="File too large (max 100KB)")

        service = CompetitionService(db)
        strategy = service.upload_strategy(
            name=name,
            code=code,
            author=author,
            description=description,
            is_public=is_public
        )

        return StrategyUploadResponse(
            strategy_id=strategy.id,
            name=strategy.name,
            message="Strategy uploaded successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        file.file.close()


@router.post("/strategies/text", response_model=StrategyUploadResponse)
def upload_strategy_text(
    strategy_data: StrategyCreate,
    db: Session = Depends(get_db)
):
    try:
        service = CompetitionService(db)
        strategy = service.upload_strategy(
            name=strategy_data.name,
            code=strategy_data.code,
            author=strategy_data.author,
            description=strategy_data.description,
            is_public=strategy_data.is_public
        )

        return StrategyUploadResponse(
            strategy_id=strategy.id,
            name=strategy.name,
            message="Strategy uploaded successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
def get_strategy(strategy_id: int, db: Session = Depends(get_db)):
    service = CompetitionService(db)
    strategy = service.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    service = CompetitionService(db)
    if not service.delete_strategy(strategy_id):
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"message": "Strategy deleted successfully"}


@router.get("/competitions", response_model=List[Competition])
def list_competitions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    service = CompetitionService(db)
    return service.list_competitions(skip=skip, limit=limit)


@router.post("/competitions", response_model=Competition, status_code=201)
def create_competition(
    competition_data: CompetitionCreate,
    db: Session = Depends(get_db)
):
    service = CompetitionService(db)
    try:
        competition = service.create_competition(
            name=competition_data.name,
            auction_type=competition_data.auction_type,
            strategy_ids=competition_data.strategy_ids,
            config=competition_data.config,
            description=competition_data.description
        )
        return competition
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/competitions/{competition_id}", response_model=Competition)
def get_competition(competition_id: int, db: Session = Depends(get_db)):
    service = CompetitionService(db)
    competition = service.get_competition(competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    return competition


@router.post("/competitions/{competition_id}/run", response_model=CompetitionResultResponse)
def run_competition(
    competition_id: int,
    num_rounds: int = Query(5, ge=1, le=100, description="Number of auction rounds"),
    verbose: bool = Query(False, description="Print progress to console"),
    db: Session = Depends(get_db)
):
    service = CompetitionService(db)
    try:
        result = service.run_competition(competition_id, num_rounds=num_rounds, verbose=verbose)
        return CompetitionResultResponse(
            competition_id=competition_id,
            status="completed",
            results=result,
            rankings=result["rankings"]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/competitions/{competition_id}")
def delete_competition(competition_id: int, db: Session = Depends(get_db)):
    service = CompetitionService(db)
    if not service.delete_competition(competition_id):
        raise HTTPException(status_code=404, detail="Competition not found")
    return {"message": "Competition deleted successfully"}
