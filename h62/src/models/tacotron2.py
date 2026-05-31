import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
import numpy as np


class Prenet(nn.Module):
    def __init__(self, in_dim: int, sizes: Tuple[int, ...]):
        super().__init__()
        in_sizes = [in_dim] + list(sizes[:-1])
        self.layers = nn.ModuleList([
            nn.Linear(in_size, out_size)
            for (in_size, out_size) in zip(in_sizes, sizes)
        ])
        self.dropout = nn.Dropout(0.5)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for linear in self.layers:
            x = self.dropout(F.relu(linear(x)))
        return x


class Postnet(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        model_config = config["model"]
        n_mel_channels = config["audio"]["n_mel_channels"]
        self.convolutions = nn.ModuleList()
        
        self.convolutions.append(
            nn.Sequential(
                nn.Conv1d(
                    n_mel_channels,
                    model_config["postnet_embedding_dim"],
                    kernel_size=model_config["postnet_kernel_size"],
                    padding=int((model_config["postnet_kernel_size"] - 1) / 2),
                    dilation=1,
                ),
                nn.BatchNorm1d(model_config["postnet_embedding_dim"]),
            )
        )
        
        for _ in range(1, model_config["postnet_n_convolutions"] - 1):
            self.convolutions.append(
                nn.Sequential(
                    nn.Conv1d(
                        model_config["postnet_embedding_dim"],
                        model_config["postnet_embedding_dim"],
                        kernel_size=model_config["postnet_kernel_size"],
                        padding=int((model_config["postnet_kernel_size"] - 1) / 2),
                        dilation=1,
                    ),
                    nn.BatchNorm1d(model_config["postnet_embedding_dim"]),
                )
            )
        
        self.convolutions.append(
            nn.Sequential(
                nn.Conv1d(
                    model_config["postnet_embedding_dim"],
                    n_mel_channels,
                    kernel_size=model_config["postnet_kernel_size"],
                    padding=int((model_config["postnet_kernel_size"] - 1) / 2),
                    dilation=1,
                ),
                nn.BatchNorm1d(n_mel_channels),
            )
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for i, conv in enumerate(self.convolutions):
            x = conv(x)
            if i < len(self.convolutions) - 1:
                x = torch.tanh(x)
            x = F.dropout(x, 0.5, self.training)
        return x


class Encoder(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        model_config = config["model"]
        self.encoder_embedding_dim = model_config["encoder_embedding_dim"]
        
        convolutions = []
        for _ in range(model_config["encoder_n_convolutions"]):
            conv_layer = nn.Sequential(
                nn.Conv1d(
                    model_config["encoder_embedding_dim"],
                    model_config["encoder_embedding_dim"],
                    kernel_size=model_config["encoder_kernel_size"],
                    padding=int((model_config["encoder_kernel_size"] - 1) / 2),
                ),
                nn.BatchNorm1d(model_config["encoder_embedding_dim"]),
            )
            convolutions.append(conv_layer)
        self.convolutions = nn.ModuleList(convolutions)
        
        self.lstm = nn.LSTM(
            model_config["encoder_embedding_dim"],
            int(model_config["encoder_embedding_dim"] / 2),
            num_layers=1,
            batch_first=True,
            bidirectional=True,
        )

    def forward(self, x: torch.Tensor, input_lengths: torch.Tensor) -> torch.Tensor:
        for conv in self.convolutions:
            x = F.dropout(F.relu(conv(x)), 0.5, self.training)
        
        x = x.transpose(1, 2)
        
        input_lengths = input_lengths.cpu().numpy()
        x = nn.utils.rnn.pack_padded_sequence(x, input_lengths, batch_first=True, enforce_sorted=False)
        
        self.lstm.flatten_parameters()
        outputs, _ = self.lstm(x)
        
        outputs, _ = nn.utils.rnn.pad_packed_sequence(outputs, batch_first=True)
        
        return outputs


class LocationLayer(nn.Module):
    def __init__(self, attention_n_filters: int, attention_kernel_size: int, attention_dim: int):
        super().__init__()
        padding = int((attention_kernel_size - 1) / 2)
        self.location_conv = nn.Conv1d(
            2,
            attention_n_filters,
            kernel_size=attention_kernel_size,
            padding=padding,
            bias=False,
            stride=1,
            dilation=1,
        )
        self.location_dense = nn.Linear(attention_n_filters, attention_dim, bias=False)

    def forward(self, attention_weights_cat: torch.Tensor) -> torch.Tensor:
        processed_attention = self.location_conv(attention_weights_cat)
        processed_attention = processed_attention.transpose(1, 2)
        processed_attention = self.location_dense(processed_attention)
        return processed_attention


class Attention(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        model_config = config["model"]
        
        self.attention_rnn_dim = model_config["attention_rnn_dim"]
        self.encoder_embedding_dim = model_config["encoder_embedding_dim"]
        self.attention_dim = model_config["attention_dim"]
        self.attention_location_n_filters = model_config["attention_location_n_filters"]
        self.attention_location_kernel_size = model_config["attention_location_kernel_size"]
        
        self.query_layer = nn.Linear(self.attention_rnn_dim, self.attention_dim, bias=False)
        self.memory_layer = nn.Linear(self.encoder_embedding_dim, self.attention_dim, bias=False)
        self.v = nn.Linear(self.attention_dim, 1, bias=False)
        self.location_layer = LocationLayer(
            self.attention_location_n_filters,
            self.attention_location_kernel_size,
            self.attention_dim,
        )
        self.score_mask_value = -float("inf")

    def get_alignment_energies(
        self,
        query: torch.Tensor,
        processed_memory: torch.Tensor,
        attention_weights_cat: torch.Tensor,
    ) -> torch.Tensor:
        processed_query = self.query_layer(query.unsqueeze(1))
        processed_attention_weights = self.location_layer(attention_weights_cat)
        energies = self.v(torch.tanh(processed_query + processed_attention_weights + processed_memory))
        energies = energies.squeeze(-1)
        return energies

    def forward(
        self,
        attention_hidden_state: torch.Tensor,
        memory: torch.Tensor,
        processed_memory: torch.Tensor,
        attention_weights_cat: torch.Tensor,
        mask: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        alignment = self.get_alignment_energies(
            attention_hidden_state, processed_memory, attention_weights_cat
        )
        
        if mask is not None:
            alignment = alignment.masked_fill(mask == 0, self.score_mask_value)
        
        attention_weights = F.softmax(alignment, dim=1)
        attention_context = torch.bmm(attention_weights.unsqueeze(1), memory)
        attention_context = attention_context.squeeze(1)
        
        return attention_context, attention_weights


class Decoder(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        model_config = config["model"]
        
        self.n_mel_channels = config["audio"]["n_mel_channels"]
        self.n_frames_per_step = model_config["n_frames_per_step"]
        self.encoder_embedding_dim = model_config["encoder_embedding_dim"]
        self.attention_rnn_dim = model_config["attention_rnn_dim"]
        self.decoder_rnn_dim = model_config["decoder_rnn_dim"]
        self.prenet_dim = model_config["prenet_dim"]
        self.max_decoder_steps = model_config["max_decoder_steps"]
        self.gate_threshold = model_config["gate_threshold"]
        self.p_attention_dropout = model_config["p_attention_dropout"]
        self.p_decoder_dropout = model_config["p_decoder_dropout"]
        
        self.prenet = Prenet(
            self.n_mel_channels * self.n_frames_per_step,
            [self.prenet_dim, self.prenet_dim],
        )
        
        self.attention_rnn = nn.LSTMCell(
            self.prenet_dim + self.encoder_embedding_dim,
            self.attention_rnn_dim,
        )
        
        self.attention_layer = Attention(config)
        
        self.decoder_rnn = nn.LSTMCell(
            self.attention_rnn_dim + self.encoder_embedding_dim,
            self.decoder_rnn_dim,
        )
        
        self.linear_projection = nn.Linear(
            self.decoder_rnn_dim + self.encoder_embedding_dim,
            self.n_mel_channels * self.n_frames_per_step,
        )
        
        self.gate_layer = nn.Linear(
            self.decoder_rnn_dim + self.encoder_embedding_dim,
            1,
        )

    def get_go_frame(self, memory: torch.Tensor) -> torch.Tensor:
        B = memory.size(0)
        decoder_input = torch.zeros(
            B, self.n_mel_channels * self.n_frames_per_step,
            dtype=memory.dtype, device=memory.device,
        )
        return decoder_input

    def initialize_decoder_states(
        self, memory: torch.Tensor, mask: torch.Tensor
    ) -> Tuple[torch.Tensor, ...]:
        B = memory.size(0)
        MAX_TIME = memory.size(1)
        
        device = memory.device
        dtype = memory.dtype
        
        attention_hidden = torch.zeros(B, self.attention_rnn_dim, dtype=dtype, device=device)
        attention_cell = torch.zeros(B, self.attention_rnn_dim, dtype=dtype, device=device)
        
        decoder_hidden = torch.zeros(B, self.decoder_rnn_dim, dtype=dtype, device=device)
        decoder_cell = torch.zeros(B, self.decoder_rnn_dim, dtype=dtype, device=device)
        
        attention_weights = torch.zeros(B, MAX_TIME, dtype=dtype, device=device)
        attention_weights_cum = torch.zeros(B, MAX_TIME, dtype=dtype, device=device)
        attention_context = torch.zeros(B, self.encoder_embedding_dim, dtype=dtype, device=device)
        
        processed_memory = self.attention_layer.memory_layer(memory)
        
        return (
            attention_hidden, attention_cell, decoder_hidden, decoder_cell,
            attention_weights, attention_weights_cum, attention_context, processed_memory,
        )

    def parse_decoder_inputs(self, decoder_inputs: torch.Tensor) -> torch.Tensor:
        decoder_inputs = decoder_inputs.transpose(1, 2)
        decoder_inputs = decoder_inputs.view(
            decoder_inputs.size(0),
            int(decoder_inputs.size(1) / self.n_frames_per_step),
            -1,
        )
        decoder_inputs = decoder_inputs.transpose(0, 1)
        return decoder_inputs

    def parse_decoder_outputs(
        self,
        mel_outputs: torch.Tensor,
        gate_outputs: torch.Tensor,
        alignments: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        alignments = torch.stack(alignments).transpose(0, 1)
        gate_outputs = torch.stack(gate_outputs).transpose(0, 1).contiguous()
        gate_outputs = gate_outputs.view(gate_outputs.size(0), -1)
        
        mel_outputs = torch.stack(mel_outputs).transpose(0, 1).contiguous()
        mel_outputs = mel_outputs.view(
            mel_outputs.size(0),
            -1,
            self.n_mel_channels,
        )
        mel_outputs = mel_outputs.transpose(1, 2)
        
        return mel_outputs, gate_outputs, alignments

    def decode(
        self,
        decoder_input: torch.Tensor,
        attention_hidden: torch.Tensor,
        attention_cell: torch.Tensor,
        decoder_hidden: torch.Tensor,
        decoder_cell: torch.Tensor,
        attention_weights: torch.Tensor,
        attention_weights_cum: torch.Tensor,
        attention_context: torch.Tensor,
        memory: torch.Tensor,
        processed_memory: torch.Tensor,
        mask: torch.Tensor,
    ) -> Tuple[torch.Tensor, ...]:
        cell_input = torch.cat((decoder_input, attention_context), -1)
        attention_hidden, attention_cell = self.attention_rnn(cell_input, (attention_hidden, attention_cell))
        attention_hidden = F.dropout(attention_hidden, self.p_attention_dropout, self.training)
        
        attention_weights_cat = torch.cat(
            (attention_weights.unsqueeze(1), attention_weights_cum.unsqueeze(1)), dim=1,
        )
        attention_context, attention_weights = self.attention_layer(
            attention_hidden, memory, processed_memory, attention_weights_cat, mask,
        )
        
        attention_weights_cum += attention_weights
        
        decoder_input = torch.cat((attention_hidden, attention_context), -1)
        decoder_hidden, decoder_cell = self.decoder_rnn(decoder_input, (decoder_hidden, decoder_cell))
        decoder_hidden = F.dropout(decoder_hidden, self.p_decoder_dropout, self.training)
        
        decoder_hidden_attention_context = torch.cat((decoder_hidden, attention_context), dim=1)
        decoder_output = self.linear_projection(decoder_hidden_attention_context)
        gate_prediction = self.gate_layer(decoder_hidden_attention_context)
        
        return (
            decoder_output, gate_prediction, attention_hidden, attention_cell,
            decoder_hidden, decoder_cell, attention_weights, attention_weights_cum, attention_context,
        )

    def forward(
        self,
        memory: torch.Tensor,
        decoder_inputs: torch.Tensor,
        memory_lengths: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        decoder_inputs = self.parse_decoder_inputs(decoder_inputs)
        MAX_TIME = decoder_inputs.size(0)
        
        mask = ~get_mask_from_lengths(memory_lengths)
        (
            attention_hidden, attention_cell, decoder_hidden, decoder_cell,
            attention_weights, attention_weights_cum, attention_context, processed_memory,
        ) = self.initialize_decoder_states(memory, mask)
        
        mel_outputs, gate_outputs, alignments = [], [], []
        decoder_input = self.get_go_frame(memory)
        
        for t in range(MAX_TIME):
            decoder_input = self.prenet(decoder_input)
            (
                mel_output, gate_output, attention_hidden, attention_cell,
                decoder_hidden, decoder_cell, attention_weights, attention_weights_cum, attention_context,
            ) = self.decode(
                decoder_input, attention_hidden, attention_cell, decoder_hidden, decoder_cell,
                attention_weights, attention_weights_cum, attention_context, memory,
                processed_memory, mask,
            )
            
            mel_outputs += [mel_output]
            gate_outputs += [gate_output]
            alignments += [attention_weights]
            
            decoder_input = decoder_inputs[t]
        
        return self.parse_decoder_outputs(mel_outputs, gate_outputs, alignments)

    def inference(
        self,
        memory: torch.Tensor,
        memory_lengths: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        mask = ~get_mask_from_lengths(memory_lengths)
        (
            attention_hidden, attention_cell, decoder_hidden, decoder_cell,
            attention_weights, attention_weights_cum, attention_context, processed_memory,
        ) = self.initialize_decoder_states(memory, mask)
        
        mel_outputs, gate_outputs, alignments = [], [], []
        decoder_input = self.get_go_frame(memory)
        
        while True:
            decoder_input = self.prenet(decoder_input)
            (
                mel_output, gate_output, attention_hidden, attention_cell,
                decoder_hidden, decoder_cell, attention_weights, attention_weights_cum, attention_context,
            ) = self.decode(
                decoder_input, attention_hidden, attention_cell, decoder_hidden, decoder_cell,
                attention_weights, attention_weights_cum, attention_context, memory,
                processed_memory, mask,
            )
            
            mel_outputs += [mel_output]
            gate_outputs += [gate_output]
            alignments += [attention_weights]
            
            if torch.sigmoid(gate_output.data) > self.gate_threshold:
                break
            elif len(mel_outputs) == self.max_decoder_steps:
                print("Warning! Reached max decoder steps")
                break
            
            decoder_input = mel_output
        
        return self.parse_decoder_outputs(mel_outputs, gate_outputs, alignments)


def get_mask_from_lengths(lengths: torch.Tensor) -> torch.Tensor:
    max_len = torch.max(lengths).item()
    ids = torch.arange(0, max_len, device=lengths.device)
    mask = (ids < lengths.unsqueeze(1)).bool()
    return mask


class Tacotron2(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        model_config = config["model"]
        
        self.mask_padding = True
        self.n_mel_channels = config["audio"]["n_mel_channels"]
        self.n_frames_per_step = model_config["n_frames_per_step"]
        
        self.embedding = nn.Embedding(
            model_config["n_symbols"],
            model_config["symbols_embedding_dim"],
        )
        std = np.sqrt(2.0 / (model_config["n_symbols"] + model_config["symbols_embedding_dim"]))
        self.embedding.weight.data.normal_(0, std)
        
        self.encoder = Encoder(config)
        self.decoder = Decoder(config)
        self.postnet = Postnet(config)
        
        self.style_embedding_dim = config["reference_encoder"]["style_embedding_dim"]
        self.emotion_embedding_dim = config["emotion"]["emotion_embedding_dim"]
        self.encoder_embedding_dim = model_config["encoder_embedding_dim"]
        
        self.style_proj = nn.Linear(
            self.style_embedding_dim + self.emotion_embedding_dim,
            self.encoder_embedding_dim,
        )
        
        self.prosody_dim = config["emotion"]["prosody_dim"]
        self.prosody_proj = nn.Linear(self.prosody_dim, self.encoder_embedding_dim)

    def parse_batch(self, batch: Tuple[torch.Tensor, ...]) -> Tuple[torch.Tensor, ...]:
        (
            text_padded,
            input_lengths,
            mel_padded,
            gate_padded,
            output_lengths,
            style_embedding,
            emotion_embedding,
            prosody_features,
        ) = batch
        
        return (
            (text_padded, input_lengths, mel_padded, max_len, output_lengths, style_embedding, emotion_embedding, prosody_features),
            (mel_padded, gate_padded),
        )

    def parse_output(
        self,
        outputs: Tuple[torch.Tensor, ...],
        output_lengths: torch.Tensor,
    ) -> Tuple[torch.Tensor, ...]:
        mel_outputs, mel_outputs_postnet, gate_outputs, alignments = outputs
        
        if self.mask_padding and output_lengths is not None:
            mask = ~get_mask_from_lengths(output_lengths)
            mask = mask.expand(self.n_mel_channels, mask.size(0), mask.size(1))
            mask = mask.permute(1, 0, 2)
            
            mel_outputs.data.masked_fill_(mask, 0.0)
            mel_outputs_postnet.data.masked_fill_(mask, 0.0)
            gate_outputs.data.masked_fill_(mask[:, 0, :], 1e3)
        
        return mel_outputs, mel_outputs_postnet, gate_outputs, alignments

    def forward(
        self,
        inputs: Tuple[torch.Tensor, ...],
    ) -> Tuple[torch.Tensor, ...]:
        (
            inputs_padded,
            input_lengths,
            mels,
            max_len,
            output_lengths,
            style_embedding,
            emotion_embedding,
            prosody_features,
        ) = inputs
        
        embedded_inputs = self.embedding(inputs_padded).transpose(1, 2)
        encoder_outputs = self.encoder(embedded_inputs, input_lengths)
        
        combined_style = torch.cat([style_embedding, emotion_embedding], dim=-1)
        style_proj = self.style_proj(combined_style).unsqueeze(1)
        prosody_proj = self.prosody_proj(prosody_features).unsqueeze(1)
        
        encoder_outputs = encoder_outputs + style_proj + prosody_proj
        
        mel_outputs, gate_outputs, alignments = self.decoder(
            encoder_outputs, mels, memory_lengths=input_lengths,
        )
        
        mel_outputs_postnet = self.postnet(mel_outputs)
        mel_outputs_postnet = mel_outputs + mel_outputs_postnet
        
        return self.parse_output(
            [mel_outputs, mel_outputs_postnet, gate_outputs, alignments], output_lengths,
        )

    def inference(
        self,
        inputs_padded: torch.Tensor,
        input_lengths: torch.Tensor,
        style_embedding: torch.Tensor,
        emotion_embedding: torch.Tensor,
        prosody_features: torch.Tensor,
    ) -> Tuple[torch.Tensor, ...]:
        embedded_inputs = self.embedding(inputs_padded).transpose(1, 2)
        encoder_outputs = self.encoder(embedded_inputs, input_lengths)
        
        combined_style = torch.cat([style_embedding, emotion_embedding], dim=-1)
        style_proj = self.style_proj(combined_style).unsqueeze(1)
        prosody_proj = self.prosody_proj(prosody_features).unsqueeze(1)
        
        encoder_outputs = encoder_outputs + style_proj + prosody_proj
        
        mel_outputs, gate_outputs, alignments = self.decoder.inference(
            encoder_outputs, memory_lengths=input_lengths,
        )
        
        mel_outputs_postnet = self.postnet(mel_outputs)
        mel_outputs_postnet = mel_outputs + mel_outputs_postnet
        
        return mel_outputs, mel_outputs_postnet, gate_outputs, alignments
