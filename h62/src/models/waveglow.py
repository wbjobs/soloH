import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
import numpy as np


def fused_add_tanh_sigmoid_multiply(input_a: torch.Tensor, input_b: torch.Tensor, n_channels: int):
    n_channels_int = n_channels[0]
    in_act = input_a + input_b
    t_act = torch.tanh(in_act[:, :n_channels_int, :])
    s_act = torch.sigmoid(in_act[:, n_channels_int:, :])
    acts = t_act * s_act
    return acts


class WN(nn.Module):
    def __init__(self, n_in_channels: int, n_layers: int, n_channels: int, kernel_size: int):
        super().__init__()
        self.n_layers = n_layers
        self.n_channels = n_channels
        self.in_layers = nn.ModuleList()
        self.res_skip_layers = nn.ModuleList()
        
        self.cond_layer = nn.Conv1d(n_channels, 2 * n_channels * n_layers, 1)
        
        for i in range(n_layers):
            dilation = 2 ** i
            padding = int((kernel_size * dilation - dilation) / 2)
            
            in_layer = nn.Conv1d(
                n_in_channels,
                2 * n_channels,
                kernel_size,
                dilation=dilation,
                padding=padding,
            )
            self.in_layers.append(in_layer)
            
            if i < n_layers - 1:
                res_skip_channels = 2 * n_channels
            else:
                res_skip_channels = n_channels
            
            res_skip_layer = nn.Conv1d(n_channels, res_skip_channels, 1)
            self.res_skip_layers.append(res_skip_layer)

    def forward(self, forward_input: Tuple[torch.Tensor, torch.Tensor]) -> torch.Tensor:
        audio, spect = forward_input
        audio = audio.float()
        
        spect = self.cond_layer(spect)
        
        audio_output = torch.zeros_like(audio)
        
        for i in range(self.n_layers):
            spect_offset = i * 2 * self.n_channels
            
            acts = fused_add_tanh_sigmoid_multiply(
                self.in_layers[i](audio),
                spect[:, spect_offset:spect_offset + 2 * self.n_channels, :],
                [self.n_channels],
            )
            
            res_skip_acts = self.res_skip_layers[i](acts)
            if i < self.n_layers - 1:
                audio = audio + res_skip_acts[:, :self.n_channels, :]
                audio_output = audio_output + res_skip_acts[:, self.n_channels:, :]
            else:
                audio_output = audio_output + res_skip_acts
        
        return audio_output


class Invertible1x1Conv(nn.Module):
    def __init__(self, n_channels: int):
        super().__init__()
        
        W = torch.linalg.qr(torch.FloatTensor(n_channels, n_channels).normal_())[0]
        
        if torch.det(W) < 0:
            W[:, 0] = -W[:, 0]
        
        self.W = nn.Parameter(W)
        self.W_inverse = None

    def forward(self, forward_input: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size, n_channels, n_of_groups = forward_input.size()
        
        log_det_W = torch.log(torch.abs(torch.det(self.W))) * n_of_groups
        W = self.W.view(n_channels, n_channels, 1)
        output = F.conv1d(forward_input, W)
        return output, log_det_W

    def infer(self, forward_input: torch.Tensor) -> torch.Tensor:
        if self.W_inverse is None:
            self.W_inverse = torch.inverse(self.W)
        W_inverse = self.W_inverse.view(self.W.size(0), self.W.size(1), 1)
        output = F.conv1d(forward_input, W_inverse)
        return output


class WaveGlow(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        vocoder_config = config["vocoder"]
        
        self.n_mel_channels = vocoder_config["n_mel_channels"]
        self.n_flows = vocoder_config["n_flows"]
        self.n_group = vocoder_config["n_group"]
        self.n_early_every = vocoder_config["n_early_every"]
        self.n_early_size = vocoder_config["n_early_size"]
        
        self.WN_config = vocoder_config["WN_config"]
        self.sigma = 1.0
        
        self.upsample = nn.ConvTranspose1d(
            self.n_mel_channels,
            self.n_mel_channels,
            1024,
            stride=256,
        )
        
        self.WN = nn.ModuleList()
        self.convinv = nn.ModuleList()
        
        n_half = int(self.n_group / 2)
        n_remaining_channels = self.n_group
        
        for k in range(self.n_flows):
            if k % self.n_early_every == 0 and k > 0:
                n_half = n_half - int(self.n_early_size / 2)
                n_remaining_channels = n_remaining_channels - self.n_early_size
            
            self.convinv.append(Invertible1x1Conv(n_remaining_channels))
            
            self.WN.append(
                WN(
                    n_half,
                    self.WN_config["n_layers"],
                    self.WN_config["n_channels"],
                    self.WN_config["kernel_size"],
                )
            )
        
        self.n_remaining_channels = n_remaining_channels

    def forward(
        self,
        forward_input: Tuple[torch.Tensor, torch.Tensor],
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        audio, spect = forward_input
        spect = self.upsample(spect)
        
        n_group = self.n_group
        
        audio = audio.unfold(1, n_group, n_group).permute(0, 2, 1)
        
        spect = spect.unfold(2, n_group, n_group).permute(0, 2, 1, 3)
        spect = spect.contiguous().view(spect.size(0), spect.size(1), -1).permute(0, 2, 1)
        
        output_audio = []
        log_s_list = []
        log_det_W_list = []
        
        n_remaining_channels = self.n_group
        
        for k in range(self.n_flows):
            if k % self.n_early_every == 0 and k > 0:
                output_audio.append(audio[:, :self.n_early_size, :])
                audio = audio[:, self.n_early_size:, :]
                n_remaining_channels = n_remaining_channels - self.n_early_size
            
            audio, log_det_W = self.convinv[k](audio)
            log_det_W_list.append(log_det_W)
            
            n_half = int(n_remaining_channels / 2)
            audio_0 = audio[:, :n_half, :]
            audio_1 = audio[:, n_half:, :]
            
            n_channels = self.WN_config["n_channels"]
            output = self.WN[k]((audio_0, spect))
            log_s = output[:, n_channels:, :]
            b = output[:, :n_channels, :]
            audio_1 = torch.exp(log_s) * audio_1 + b
            log_s_list.append(log_s)
            
            audio = torch.cat([audio_0, audio_1], 1)
        
        output_audio.append(audio)
        z = torch.cat(output_audio, 1)
        
        log_s_sum = torch.stack(log_s_list).sum()
        log_det_W_sum = torch.stack(log_det_W_list).sum()
        
        log_s = log_s_sum
        log_det_W = log_det_W_sum
        
        return z, log_s + log_det_W

    def infer(self, spect: torch.Tensor, sigma: float = 1.0) -> torch.Tensor:
        spect = self.upsample(spect)
        
        trim = spect.size(2) % self.n_group
        if trim != 0:
            spect = spect[:, :, :-trim]
        
        n_group = self.n_group
        spect = spect.unfold(2, n_group, n_group).permute(0, 2, 1, 3)
        spect = spect.contiguous().view(spect.size(0), spect.size(1), -1).permute(0, 2, 1)
        
        n_remaining_channels = self.n_remaining_channels
        audio = torch.randn(
            spect.size(0),
            n_remaining_channels,
            spect.size(2),
            device=spect.device,
            dtype=spect.dtype,
        ) * sigma
        
        for k in reversed(range(self.n_flows)):
            n_half = int(n_remaining_channels / 2)
            audio_0 = audio[:, :n_half, :]
            audio_1 = audio[:, n_half:, :]
            
            n_channels = self.WN_config["n_channels"]
            output = self.WN[k]((audio_0, spect))
            s = output[:, n_channels:, :]
            b = output[:, :n_channels, :]
            audio_1 = (audio_1 - b) / torch.exp(s)
            audio = torch.cat([audio_0, audio_1], 1)
            
            audio = self.convinv[k].infer(audio)
            
            if k % self.n_early_every == 0 and k > 0:
                n_remaining_channels = n_remaining_channels + self.n_early_size
                z = torch.randn(
                    spect.size(0),
                    self.n_early_size,
                    spect.size(2),
                    device=spect.device,
                    dtype=spect.dtype,
                ) * sigma
                audio = torch.cat([z, audio], 1)
        
        audio = audio.permute(0, 2, 1).contiguous().view(audio.size(0), -1).data
        return audio

    def remove_weightnorm(self):
        for WN in self.WN:
            WN.start = nn.utils.remove_weight_norm(WN.start)
            WN.end = nn.utils.remove_weight_norm(WN.end)
            WN.cond_layer = nn.utils.remove_weight_norm(WN.cond_layer)
            for i in range(WN.n_layers):
                WN.in_layers[i] = nn.utils.remove_weight_norm(WN.in_layers[i])
                WN.res_skip_layers[i] = nn.utils.remove_weight_norm(WN.res_skip_layers[i])


class WaveGlowLoss(nn.Module):
    def __init__(self, sigma: float = 1.0):
        super().__init__()
        self.sigma = sigma

    def forward(self, model_output: Tuple[torch.Tensor, torch.Tensor]) -> torch.Tensor:
        z, log_s_list, log_det_W_list = model_output
        
        for i, log_s in enumerate(log_s_list):
            if i == 0:
                log_s_total = torch.sum(log_s)
                log_det_W_total = log_det_W_list[i]
            else:
                log_s_total = log_s_total + torch.sum(log_s)
                log_det_W_total = log_det_W_total + log_det_W_list[i]
        
        loss = torch.sum(z * z) / (2 * self.sigma * self.sigma) - log_s_total - log_det_W_total
        return loss / (z.size(0) * z.size(1) * z.size(2))
