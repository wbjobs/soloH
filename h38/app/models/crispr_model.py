import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
from app.constants import TOTAL_SEQUENCE_LENGTH, BASE_TO_INDEX


class CRISPRModel(nn.Module):
    def __init__(
        self,
        input_channels: int = 12,
        seq_length: int = TOTAL_SEQUENCE_LENGTH,
        num_filters: int = 64,
        kernel_sizes: Tuple[int, ...] = (3, 5, 7),
        lstm_hidden: int = 64,
        lstm_layers: int = 2,
        dropout: float = 0.3,
        fc_hidden: int = 128,
    ):
        super().__init__()

        self.seq_length = seq_length
        self.num_filters = num_filters
        self.kernel_sizes = kernel_sizes

        self.convs = nn.ModuleList()
        self.batch_norms = nn.ModuleList()
        self.pools = nn.ModuleList()

        for kernel_size in kernel_sizes:
            self.convs.append(
                nn.Conv1d(
                    in_channels=input_channels,
                    out_channels=num_filters,
                    kernel_size=kernel_size,
                    padding=kernel_size // 2,
                )
            )
            self.batch_norms.append(nn.BatchNorm1d(num_filters))
            self.pools.append(nn.MaxPool1d(kernel_size=2, stride=2))

        total_filters = num_filters * len(kernel_sizes)
        reduced_length = seq_length // 2

        self.dropout = nn.Dropout(dropout)

        self.lstm = nn.LSTM(
            input_size=total_filters,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if lstm_layers > 1 else 0.0,
        )

        lstm_output_size = lstm_hidden * 2

        self.attention = nn.Sequential(
            nn.Linear(lstm_output_size, lstm_output_size),
            nn.Tanh(),
            nn.Linear(lstm_output_size, 1),
        )

        self.fc_layers = nn.Sequential(
            nn.Linear(lstm_output_size + total_filters, fc_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fc_hidden, fc_hidden // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fc_hidden // 2, 1),
        )

        self._init_weights()

    def _init_weights(self):
        for conv in self.convs:
            nn.init.kaiming_normal_(conv.weight, mode="fan_out", nonlinearity="relu")
            nn.init.constant_(conv.bias, 0)

        for fc in self.fc_layers:
            if isinstance(fc, nn.Linear):
                nn.init.kaiming_normal_(fc.weight, mode="fan_out", nonlinearity="relu")
                nn.init.constant_(fc.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size = x.size(0)

        conv_outputs = []
        for conv, bn, pool in zip(self.convs, self.batch_norms, self.pools):
            conv_out = F.relu(bn(conv(x)))
            conv_out = pool(conv_out)
            conv_out = self.dropout(conv_out)
            conv_outputs.append(conv_out)

        concat_conv = torch.cat(conv_outputs, dim=1)

        cnn_features = F.adaptive_max_pool1d(concat_conv, 1).squeeze(-1)

        lstm_input = concat_conv.transpose(1, 2)
        lstm_output, _ = self.lstm(lstm_input)

        attention_weights = self.attention(lstm_output).squeeze(-1)
        attention_weights = F.softmax(attention_weights, dim=1)

        weighted_lstm = torch.sum(
            lstm_output * attention_weights.unsqueeze(-1), dim=1
        )

        combined = torch.cat([cnn_features, weighted_lstm], dim=1)

        output = self.fc_layers(combined)

        return output.squeeze(-1)


class CRISPRPredictor:
    def __init__(
        self,
        model: Optional[CRISPRModel] = None,
        model_path: Optional[str] = None,
        device: str = "cpu",
    ):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")

        if model is None:
            model = CRISPRModel()

        self.model = model.to(self.device)
        self.model.eval()

        if model_path is not None:
            self.load_weights(model_path)

    def load_weights(self, model_path: str):
        try:
            state_dict = torch.load(model_path, map_location=self.device)
            if "model_state_dict" in state_dict:
                state_dict = state_dict["model_state_dict"]
            self.model.load_state_dict(state_dict)
        except Exception as e:
            print(f"Warning: Could not load model weights from {model_path}: {e}")
            print("Using initialized model weights instead.")

    def predict(self, encoded_input: torch.Tensor) -> torch.Tensor:
        self.model.eval()
        with torch.no_grad():
            encoded_input = encoded_input.to(self.device)
            outputs = self.model(encoded_input)
            scores = torch.sigmoid(outputs)
        return scores

    def predict_numpy(self, encoded_input: torch.Tensor) -> float:
        scores = self.predict(encoded_input)
        return scores.cpu().numpy()

    def get_embeddings(self, encoded_input: torch.Tensor) -> torch.Tensor:
        self.model.eval()
        with torch.no_grad():
            encoded_input = encoded_input.to(self.device)

            conv_outputs = []
            for conv, bn, pool in zip(
                self.model.convs, self.model.batch_norms, self.model.pools
            ):
                conv_out = F.relu(bn(conv(encoded_input)))
                conv_out = pool(conv_out)
                conv_outputs.append(conv_out)

            concat_conv = torch.cat(conv_outputs, dim=1)
            cnn_features = F.adaptive_max_pool1d(concat_conv, 1).squeeze(-1)

            lstm_input = concat_conv.transpose(1, 2)
            lstm_output, _ = self.model.lstm(lstm_input)

            attention_weights = self.model.attention(lstm_output).squeeze(-1)
            attention_weights = F.softmax(attention_weights, dim=1)
            weighted_lstm = torch.sum(
                lstm_output * attention_weights.unsqueeze(-1), dim=1
            )

            embeddings = torch.cat([cnn_features, weighted_lstm], dim=1)

        return embeddings
