import os
import sys
import importlib
import importlib.util
import hashlib
from typing import Dict, Optional, Any, Type
from pathlib import Path

from app.core.config import settings
from app.strategies.base_strategy import BaseStrategy, STRATEGY_REGISTRY
from app.auction.bidder import BidderState, AuctionState


class StrategyManager:
    def __init__(self, upload_dir: Optional[str] = None):
        self.upload_dir = Path(upload_dir or settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.custom_strategies: Dict[str, Type[BaseStrategy]] = {}
        self._load_builtin_strategies()
        self._load_uploaded_strategies()

    def _load_builtin_strategies(self):
        for name, strategy_class in STRATEGY_REGISTRY.items():
            self.custom_strategies[name] = strategy_class

    def _load_uploaded_strategies(self):
        for file in self.upload_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue
            try:
                strategy_name = file.stem
                self._load_strategy_from_file(strategy_name, file)
            except Exception as e:
                print(f"Warning: Failed to load strategy {file.name}: {e}")

    def _load_strategy_from_file(self, strategy_name: str, file_path: Path) -> Type[BaseStrategy]:
        module_name = f"uploaded_strategy_{strategy_name}"

        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        strategy_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseStrategy)
                and attr is not BaseStrategy
            ):
                strategy_class = attr
                break

        if strategy_class is None:
            raise ValueError(f"No valid strategy class found in {file_path}")

        strategy_class.name = strategy_name
        self.custom_strategies[strategy_name] = strategy_class
        return strategy_class

    def upload_strategy(
        self,
        strategy_name: str,
        code: str,
        author: Optional[str] = None,
        description: Optional[str] = None,
        is_public: bool = True
    ) -> Dict[str, Any]:
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in strategy_name)
        safe_name = safe_name[:50]

        if safe_name in self.custom_strategies and safe_name in STRATEGY_REGISTRY:
            raise ValueError(f"Strategy name '{safe_name}' conflicts with built-in strategy")

        file_path = self.upload_dir / f"{safe_name}.py"

        code_hash = hashlib.sha256(code.encode()).hexdigest()

        temp_file = self.upload_dir / f"temp_{safe_name}.py"
        temp_file.write_text(code, encoding="utf-8")

        try:
            self._validate_strategy_code(temp_file)
            temp_file.rename(file_path)
            strategy_class = self._load_strategy_from_file(safe_name, file_path)

            return {
                "strategy_name": safe_name,
                "original_name": strategy_name,
                "filename": file_path.name,
                "code_hash": code_hash,
                "author": author,
                "description": description,
                "is_public": is_public,
                "class_name": strategy_class.__name__
            }
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise e

    def _validate_strategy_code(self, file_path: Path):
        try:
            strategy_class = self._load_strategy_from_file("_temp_validate", file_path)
            instance = strategy_class()

            if not hasattr(instance, "decide_bid"):
                raise ValueError("Strategy must implement decide_bid method")

            import inspect
            sig = inspect.signature(instance.decide_bid)
            params = list(sig.parameters.keys())
            required_params = ["bidder", "auction_state", "round_number"]
            for param in required_params:
                if param not in params:
                    raise ValueError(f"Strategy decide_bid missing required parameter: {param}")

        finally:
            if file_path.exists():
                file_path.unlink()

    def get_strategy(self, strategy_name: str, params: Optional[Dict[str, Any]] = None) -> BaseStrategy:
        if strategy_name not in self.custom_strategies:
            file_path = self.upload_dir / f"{strategy_name}.py"
            if file_path.exists():
                self._load_strategy_from_file(strategy_name, file_path)
            else:
                raise ValueError(f"Strategy '{strategy_name}' not found")

        strategy_class = self.custom_strategies[strategy_name]
        return strategy_class(params)

    def list_strategies(self, include_builtin: bool = True) -> list:
        strategies = []
        for name, strategy_class in self.custom_strategies.items():
            is_builtin = name in STRATEGY_REGISTRY
            if not include_builtin and is_builtin:
                continue

            file_path = self.upload_dir / f"{name}.py"
            code_hash = None
            if file_path.exists():
                code_hash = hashlib.sha256(file_path.read_text(encoding="utf-8").encode()).hexdigest()

            strategies.append({
                "name": name,
                "description": getattr(strategy_class, "description", ""),
                "is_builtin": is_builtin,
                "code_hash": code_hash,
                "class_name": strategy_class.__name__
            })
        return strategies

    def get_strategy_code(self, strategy_name: str) -> Optional[str]:
        file_path = self.upload_dir / f"{strategy_name}.py"
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return None

    def delete_strategy(self, strategy_name: str) -> bool:
        if strategy_name in STRATEGY_REGISTRY:
            raise ValueError(f"Cannot delete built-in strategy '{strategy_name}'")

        file_path = self.upload_dir / f"{strategy_name}.py"
        if file_path.exists():
            file_path.unlink()
            if strategy_name in self.custom_strategies:
                del self.custom_strategies[strategy_name]
            return True
        return False

    def execute_strategy(
        self,
        strategy_name: str,
        bidder: BidderState,
        auction_state: AuctionState,
        round_number: int,
        strategy_params: Optional[Dict[str, Any]] = None
    ) -> list:
        strategy = self.get_strategy(strategy_name, strategy_params)
        return strategy.decide_bid(bidder, auction_state, round_number)


strategy_manager = StrategyManager()
