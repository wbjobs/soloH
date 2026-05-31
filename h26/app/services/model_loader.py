import torch
import hashlib
from pathlib import Path
from typing import Optional, Dict, List
import logging

from app.config import settings
from app.models.resnet import ResNetContact, create_model, get_available_models, MODEL_REGISTRY

logger = logging.getLogger(__name__)


class ModelLoader:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or settings.MODEL_CACHE_PATH
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._models: Dict[str, ResNetContact] = {}
        self._model_hashes: Dict[str, str] = {}

    def _get_model_path(self, model_name: str) -> Path:
        return self.cache_dir / f"{model_name}.pt"

    def _compute_model_hash(self, model: ResNetContact) -> str:
        state_dict = model.state_dict()
        hash_obj = hashlib.md5()
        for key in sorted(state_dict.keys()):
            tensor = state_dict[key]
            hash_obj.update(key.encode())
            hash_obj.update(tensor.numpy().tobytes())
        return hash_obj.hexdigest()

    def load_model(self, model_name: str, force_reload: bool = False) -> ResNetContact:
        if model_name in self._models and not force_reload:
            logger.info(f"Using cached model: {model_name}")
            return self._models[model_name]

        if model_name not in MODEL_REGISTRY:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(MODEL_REGISTRY.keys())}")

        model_path = self._get_model_path(model_name)
        pretrained = model_path.exists()

        logger.info(f"Loading model {model_name} (pretrained={pretrained})")

        model = create_model(
            model_name=model_name,
            pretrained=pretrained,
            model_path=str(model_path) if pretrained else None
        )

        if not pretrained:
            logger.warning(f"No pretrained weights found for {model_name}, using initialized weights")

        self._models[model_name] = model
        self._model_hashes[model_name] = self._compute_model_hash(model)

        return model

    def unload_model(self, model_name: str) -> bool:
        if model_name in self._models:
            del self._models[model_name]
            if model_name in self._model_hashes:
                del self._model_hashes[model_name]
            logger.info(f"Unloaded model: {model_name}")
            return True
        return False

    def get_available_models(self) -> dict:
        models = get_available_models()
        for name in models:
            model_path = self._get_model_path(name)
            models[name]["pretrained_available"] = model_path.exists()
            models[name]["loaded"] = name in self._models
        return models

    def list_loaded_models(self) -> List[str]:
        return list(self._models.keys())

    def get_model_hash(self, model_name: str) -> Optional[str]:
        return self._model_hashes.get(model_name)

    def predict(
        self,
        model_name: str,
        input_tensor: torch.Tensor,
        device: Optional[str] = None
    ) -> torch.Tensor:
        model = self.load_model(model_name)

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        model = model.to(device)
        input_tensor = input_tensor.to(device)

        with torch.no_grad():
            with torch.amp.autocast(device_type='cuda' if device == 'cuda' else 'cpu', enabled=device == 'cuda'):
                output = model(input_tensor)

        contact_map = output.squeeze(0).cpu().numpy()
        contact_map = (contact_map + contact_map.T) / 2

        return torch.from_numpy(contact_map)


_model_loader_instance: Optional[ModelLoader] = None


def get_model_loader() -> ModelLoader:
    global _model_loader_instance
    if _model_loader_instance is None:
        _model_loader_instance = ModelLoader()
    return _model_loader_instance
