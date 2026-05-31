import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional


class ResBlock1(nn.Module):
    def __init__(self, channels: int, kernel_size: int = 3, dilation: Tuple[int, ...] = (1, 3, 5)):
        super().__init__()
        self.convs1 = nn.ModuleList()
        self.convs2 = nn.ModuleList()
        
        for d in dilation:
            padding = int((kernel_size * d - d) / 2)
            self.convs1.append(
                nn.Sequential(
                    nn.LeakyReLU(0.1),
                    nn.Conv1d(channels, channels, kernel_size, padding=padding, dilation=d),
                )
            )
            self.convs2.append(
                nn.Sequential(
                    nn.LeakyReLU(0.1),
                    nn.Conv1d(channels, channels, kernel_size, padding=1, dilation=1),
                )
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for c1, c2 in zip(self.convs1, self.convs2):
            xt = c1(x)
            xt = c2(xt)
            x = xt + x
        return x


class ResBlock2(nn.Module):
    def __init__(self, channels: int, kernel_size: int = 3, dilation: Tuple[int, ...] = (1, 3)):
        super().__init__()
        self.convs = nn.ModuleList()
        
        for d in dilation:
            padding = int((kernel_size * d - d) / 2)
            self.convs.append(
                nn.Sequential(
                    nn.LeakyReLU(0.1),
                    nn.Conv1d(channels, channels, kernel_size, padding=padding, dilation=d),
                )
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for c in self.convs:
            xt = c(x)
            x = xt + x
        return x


class HiFiGANGenerator(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        vocoder_config = config["vocoder"]
        
        self.num_mels = config["audio"]["n_mel_channels"]
        self.upsample_rates = (8, 8, 2, 2)
        self.upsample_kernel_sizes = (16, 16, 4, 4)
        self.upsample_initial_channel = 512
        self.resblock_kernel_sizes = (3, 7, 11)
        self.resblock_dilations = ((1, 3, 5), (1, 3, 5), (1, 3, 5))
        
        self.num_upsamples = len(self.upsample_rates)
        self.num_kernels = len(self.resblock_kernel_sizes)
        
        self.conv_pre = nn.Conv1d(
            self.num_mels,
            self.upsample_initial_channel,
            7,
            padding=3,
        )
        
        resblock = ResBlock1
        
        self.ups = nn.ModuleList()
        for i, (u, k) in enumerate(zip(self.upsample_rates, self.upsample_kernel_sizes)):
            self.ups.append(
                nn.Sequential(
                    nn.LeakyReLU(0.1),
                    nn.ConvTranspose1d(
                        self.upsample_initial_channel // (2 ** i),
                        self.upsample_initial_channel // (2 ** (i + 1)),
                        k,
                        stride=u,
                        padding=(k - u) // 2,
                    ),
                )
            )
        
        self.resblocks = nn.ModuleList()
        for i in range(len(self.ups)):
            ch = self.upsample_initial_channel // (2 ** (i + 1))
            for j, (k, d) in enumerate(zip(self.resblock_kernel_sizes, self.resblock_dilations)):
                self.resblocks.append(resblock(ch, k, d))
        
        self.conv_post = nn.Sequential(
            nn.LeakyReLU(0.1),
            nn.Conv1d(ch, 1, 7, padding=3),
            nn.Tanh(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv_pre(x)
        
        for i in range(self.num_upsamples):
            x = self.ups[i](x)
            xs = None
            for j in range(self.num_kernels):
                if xs is None:
                    xs = self.resblocks[i * self.num_kernels + j](x)
                else:
                    xs += self.resblocks[i * self.num_kernels + j](x)
            x = xs / self.num_kernels
        
        x = self.conv_post(x)
        
        return x


class DiscriminatorP(nn.Module):
    def __init__(self, period: int, kernel_size: int = 5, stride: int = 3, use_spectral_norm: bool = False):
        super().__init__()
        self.period = period
        norm_f = nn.utils.spectral_norm if use_spectral_norm else nn.utils.weight_norm
        
        self.convs = nn.ModuleList([
            norm_f(nn.Conv2d(1, 32, (kernel_size, 1), (stride, 1), padding=(int((kernel_size - 1) / 2), 0))),
            norm_f(nn.Conv2d(32, 128, (kernel_size, 1), (stride, 1), padding=(int((kernel_size - 1) / 2), 0))),
            norm_f(nn.Conv2d(128, 512, (kernel_size, 1), (stride, 1), padding=(int((kernel_size - 1) / 2), 0))),
            norm_f(nn.Conv2d(512, 1024, (kernel_size, 1), (stride, 1), padding=(int((kernel_size - 1) / 2), 0))),
            norm_f(nn.Conv2d(1024, 1024, (kernel_size, 1), 1, padding=(int((kernel_size - 1) / 2), 0))),
        ])
        
        self.conv_post = norm_f(nn.Conv2d(1024, 1, (3, 1), 1, padding=(1, 0)))

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, list]:
        fmap = []
        
        b, c, t = x.shape
        if t % self.period != 0:
            n_pad = self.period - (t % self.period)
            x = F.pad(x, (0, n_pad), "reflect")
            t = t + n_pad
        x = x.view(b, c, t // self.period, self.period)
        
        for l in self.convs:
            x = l(x)
            x = F.leaky_relu(x, 0.1)
            fmap.append(x)
        
        x = self.conv_post(x)
        fmap.append(x)
        x = torch.flatten(x, 1, -1)
        
        return x, fmap


class DiscriminatorS(nn.Module):
    def __init__(self, use_spectral_norm: bool = False):
        super().__init__()
        norm_f = nn.utils.spectral_norm if use_spectral_norm else nn.utils.weight_norm
        
        self.convs = nn.ModuleList([
            norm_f(nn.Conv1d(1, 128, 15, 1, padding=7)),
            norm_f(nn.Conv1d(128, 128, 41, 2, groups=4, padding=20)),
            norm_f(nn.Conv1d(128, 256, 41, 2, groups=16, padding=20)),
            norm_f(nn.Conv1d(256, 512, 41, 4, groups=16, padding=20)),
            norm_f(nn.Conv1d(512, 1024, 41, 4, groups=16, padding=20)),
            norm_f(nn.Conv1d(1024, 1024, 41, 1, groups=16, padding=20)),
            norm_f(nn.Conv1d(1024, 1024, 5, 1, padding=2)),
        ])
        
        self.conv_post = norm_f(nn.Conv1d(1024, 1, 3, 1, padding=1))

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, list]:
        fmap = []
        
        for l in self.convs:
            x = l(x)
            x = F.leaky_relu(x, 0.1)
            fmap.append(x)
        
        x = self.conv_post(x)
        fmap.append(x)
        x = torch.flatten(x, 1, -1)
        
        return x, fmap


class HiFiGANDiscriminator(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        
        self.discriminators = nn.ModuleList([
            DiscriminatorS(use_spectral_norm=True),
            DiscriminatorP(2),
            DiscriminatorP(3),
            DiscriminatorP(5),
            DiscriminatorP(7),
            DiscriminatorP(11),
        ])

    def forward(self, y: torch.Tensor, y_hat: torch.Tensor) -> Tuple[list, list, list, list]:
        y_d_rs = []
        y_d_gs = []
        fmap_rs = []
        fmap_gs = []
        
        for d in self.discriminators:
            y_d_r, fmap_r = d(y)
            y_d_g, fmap_g = d(y_hat)
            
            y_d_rs.append(y_d_r)
            fmap_rs.append(fmap_r)
            y_d_gs.append(y_d_g)
            fmap_gs.append(fmap_g)
        
        return y_d_rs, y_d_gs, fmap_rs, fmap_gs


class HiFiGAN(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        self.generator = HiFiGANGenerator(config)
        self.discriminator = HiFiGANDiscriminator(config)

    def forward(self, mel: torch.Tensor) -> torch.Tensor:
        return self.generator(mel)

    def infer(self, mel: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            audio = self.generator(mel)
        return audio.squeeze(1)

    def remove_weightnorm(self):
        def _remove_weight_norm(m):
            try:
                nn.utils.remove_weight_norm(m)
            except ValueError:
                return
        
        self.apply(_remove_weight_norm)


def feature_loss(fmap_r: list, fmap_g: list) -> torch.Tensor:
    loss = 0
    for dr, dg in zip(fmap_r, fmap_g):
        for rl, gl in zip(dr, dg):
            loss += torch.mean(torch.abs(rl - gl))
    return loss * 2


def discriminator_loss(disc_real_outputs: list, disc_generated_outputs: list) -> Tuple[torch.Tensor, list, list]:
    loss = 0
    r_losses = []
    g_losses = []
    
    for dr, dg in zip(disc_real_outputs, disc_generated_outputs):
        r_loss = torch.mean((1 - dr) ** 2)
        g_loss = torch.mean(dg ** 2)
        loss += (r_loss + g_loss)
        r_losses.append(r_loss.item())
        g_losses.append(g_loss.item())
    
    return loss, r_losses, g_losses


def generator_loss(disc_outputs: list) -> Tuple[torch.Tensor, list]:
    loss = 0
    gen_losses = []
    
    for dg in disc_outputs:
        l = torch.mean((1 - dg) ** 2)
        gen_losses.append(l)
        loss += l
    
    return loss, gen_losses
