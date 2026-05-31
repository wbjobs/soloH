import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Optional


class ResidualBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, dilation: int = 1, dropout: float = 0.2):
        super(ResidualBlock, self).__init__()

        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3,
                               padding=dilation, dilation=dilation, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3,
                               padding=dilation, dilation=dilation, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)
        self.dropout = nn.Dropout2d(dropout)

        self.shortcut = nn.Sequential()
        if in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, bias=False),
                nn.BatchNorm2d(out_channels)
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x

        out = F.relu(self.bn1(self.conv1(x)))
        out = self.dropout(out)
        out = self.bn2(self.conv2(out))
        out += self.shortcut(residual)
        out = F.relu(out)

        return out


class ResNetContact(nn.Module):
    def __init__(
        self,
        in_channels: int = 80,
        num_blocks: List[int] = [3, 4, 6, 3],
        base_channels: int = 64,
        dropout: float = 0.2
    ):
        super(ResNetContact, self).__init__()

        self.in_channels = in_channels

        self.conv1 = nn.Conv2d(in_channels, base_channels, kernel_size=7, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(base_channels)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=1, padding=1)

        self.layers = nn.ModuleList()
        current_channels = base_channels

        for i, num_block in enumerate(num_blocks):
            layer = self._make_layer(current_channels, current_channels * 2, num_block, dropout)
            self.layers.append(layer)
            current_channels = current_channels * 2

        self.conv_final = nn.Conv2d(current_channels, 1, kernel_size=1)
        self.sigmoid = nn.Sigmoid()

        self._init_weights()

    def _make_layer(self, in_channels: int, out_channels: int, num_blocks: int, dropout: float) -> nn.Sequential:
        layers = []
        layers.append(ResidualBlock(in_channels, out_channels, dropout=dropout))
        for _ in range(1, num_blocks):
            layers.append(ResidualBlock(out_channels, out_channels, dropout=dropout))
        return nn.Sequential(*layers)

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.maxpool(x)

        for layer in self.layers:
            x = layer(x)

        x = self.conv_final(x)
        x = self.sigmoid(x)
        x = (x + x.transpose(2, 3)) / 2
        x = torch.clamp(x, min=0.0, max=1.0)

        return x.squeeze(1)


def resnet18_contact(in_channels: int = 80, **kwargs) -> ResNetContact:
    return ResNetContact(in_channels=in_channels, num_blocks=[2, 2, 2, 2], base_channels=32, **kwargs)


def resnet34_contact(in_channels: int = 80, **kwargs) -> ResNetContact:
    return ResNetContact(in_channels=in_channels, num_blocks=[3, 4, 6, 3], base_channels=32, **kwargs)


def resnet50_contact(in_channels: int = 80, **kwargs) -> ResNetContact:
    return ResNetContact(in_channels=in_channels, num_blocks=[3, 4, 6, 3], base_channels=64, **kwargs)


def resnet101_contact(in_channels: int = 80, **kwargs) -> ResNetContact:
    return ResNetContact(in_channels=in_channels, num_blocks=[3, 4, 23, 3], base_channels=64, **kwargs)


MODEL_REGISTRY = {
    "resnet18_pdb": {
        "builder": resnet18_contact,
        "description": "ResNet-18 trained on PDB dataset",
        "in_channels": 80,
        "threshold": 8.0
    },
    "resnet34_pdb": {
        "builder": resnet34_contact,
        "description": "ResNet-34 trained on PDB dataset",
        "in_channels": 80,
        "threshold": 8.0
    },
    "resnet50_pdb": {
        "builder": resnet50_contact,
        "description": "ResNet-50 trained on PDB dataset (CASP model)",
        "in_channels": 80,
        "threshold": 8.0
    },
    "resnet101_pdb": {
        "builder": resnet101_contact,
        "description": "ResNet-101 trained on PDB dataset",
        "in_channels": 80,
        "threshold": 8.0
    },
    "resnet50_casp14": {
        "builder": resnet50_contact,
        "description": "CASP14 champion model - ResNet-50",
        "in_channels": 80,
        "threshold": 8.0
    },
    "resnet50_casp15": {
        "builder": resnet50_contact,
        "description": "CASP15 champion model - ResNet-50 with enhanced training",
        "in_channels": 80,
        "threshold": 8.0
    }
}


def create_model(model_name: str, pretrained: bool = False, model_path: Optional[str] = None) -> ResNetContact:
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model_name}. Available models: {list(MODEL_REGISTRY.keys())}")

    model_config = MODEL_REGISTRY[model_name]
    model = model_config["builder"](in_channels=model_config["in_channels"])

    if pretrained and model_path:
        state_dict = torch.load(model_path, map_location='cpu')
        model.load_state_dict(state_dict)

    model.eval()
    return model


def get_available_models() -> dict:
    return {
        name: {
            "description": config["description"],
            "in_channels": config["in_channels"],
            "threshold": config["threshold"]
        }
        for name, config in MODEL_REGISTRY.items()
    }
