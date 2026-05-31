import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import librosa
from typing import Tuple, Dict, Any, Optional, List
from . import utils


class ResidualBlock(nn.Module):
    def __init__(self, channels: int, kernel_size: int = 3):
        super().__init__()
        padding = kernel_size // 2
        self.conv1 = nn.Conv2d(channels, channels, kernel_size, padding=padding)
        self.bn1 = nn.BatchNorm2d(channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size, padding=padding)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        return out + residual


class UNetDown(nn.Module):
    def __init__(self, in_channels: int, out_channels: int,
                 kernel_size: int = 4, stride: int = 2):
        super().__init__()
        padding = kernel_size // 2 - 1 if kernel_size % 2 == 0 else kernel_size // 2
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, stride=stride, padding=padding)
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.LeakyReLU(0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.bn(self.conv(x)))


class UNetUp(nn.Module):
    def __init__(self, in_channels: int, out_channels: int,
                 kernel_size: int = 4, stride: int = 2, dropout: float = 0.0):
        super().__init__()
        padding = kernel_size // 2 - 1 if kernel_size % 2 == 0 else kernel_size // 2
        self.deconv = nn.ConvTranspose2d(in_channels, out_channels, kernel_size, stride=stride, padding=padding)
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.dropout = nn.Dropout2d(dropout) if dropout > 0 else None

    def forward(self, x: torch.Tensor, skip_connection: Optional[torch.Tensor] = None) -> torch.Tensor:
        out = self.relu(self.bn(self.deconv(x)))
        if self.dropout is not None:
            out = self.dropout(out)
        if skip_connection is not None:
            if out.shape[2] != skip_connection.shape[2] or out.shape[3] != skip_connection.shape[3]:
                skip_connection = F.interpolate(skip_connection, size=(out.shape[2], out.shape[3]))
            out = torch.cat([out, skip_connection], dim=1)
        return out


class Generator(nn.Module):
    def __init__(self, in_channels: int = 1, out_channels: int = 1,
                 n_filters: int = 64, n_residual_blocks: int = 6):
        super().__init__()

        self.down1 = UNetDown(in_channels, n_filters)
        self.down2 = UNetDown(n_filters, n_filters * 2)
        self.down3 = UNetDown(n_filters * 2, n_filters * 4)
        self.down4 = UNetDown(n_filters * 4, n_filters * 8)

        self.residual_blocks = nn.Sequential(
            *[ResidualBlock(n_filters * 8) for _ in range(n_residual_blocks)]
        )

        self.up1 = UNetUp(n_filters * 8, n_filters * 4)
        self.up2 = UNetUp(n_filters * 8, n_filters * 2)
        self.up3 = UNetUp(n_filters * 4, n_filters)
        self.up4 = UNetUp(n_filters * 2, n_filters)

        self.final = nn.Sequential(
            nn.Conv2d(n_filters, out_channels, kernel_size=3, padding=1),
            nn.Tanh()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        d1 = self.down1(x)
        d2 = self.down2(d1)
        d3 = self.down3(d2)
        d4 = self.down4(d3)

        r = self.residual_blocks(d4)

        u1 = self.up1(r, d3)
        u2 = self.up2(u1, d2)
        u3 = self.up3(u2, d1)
        u4 = self.up4(u3)

        return self.final(u4)


class Discriminator(nn.Module):
    def __init__(self, in_channels: int = 1, n_filters: int = 64):
        super().__init__()

        self.model = nn.Sequential(
            nn.Conv2d(in_channels * 2, n_filters, kernel_size=4, stride=2, padding=1),
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(n_filters, n_filters * 2, kernel_size=4, stride=2, padding=1),
            nn.BatchNorm2d(n_filters * 2),
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(n_filters * 2, n_filters * 4, kernel_size=4, stride=2, padding=1),
            nn.BatchNorm2d(n_filters * 4),
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(n_filters * 4, n_filters * 8, kernel_size=4, stride=1, padding=1),
            nn.BatchNorm2d(n_filters * 8),
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(n_filters * 8, 1, kernel_size=4, stride=1, padding=1),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        return self.model(torch.cat([x, y], dim=1))


class CycleGANGenerator(nn.Module):
    def __init__(self, in_channels: int = 1, out_channels: int = 1, n_filters: int = 64):
        super().__init__()

        self.downsampling = nn.Sequential(
            nn.ReflectionPad2d(3),
            nn.Conv2d(in_channels, n_filters, kernel_size=7, padding=0),
            nn.BatchNorm2d(n_filters),
            nn.ReLU(inplace=True),

            nn.Conv2d(n_filters, n_filters * 2, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(n_filters * 2),
            nn.ReLU(inplace=True),

            nn.Conv2d(n_filters * 2, n_filters * 4, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(n_filters * 4),
            nn.ReLU(inplace=True)
        )

        self.residual_blocks = nn.Sequential(
            *[ResidualBlock(n_filters * 4) for _ in range(9)]
        )

        self.upsampling = nn.Sequential(
            nn.ConvTranspose2d(n_filters * 4, n_filters * 2, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.BatchNorm2d(n_filters * 2),
            nn.ReLU(inplace=True),

            nn.ConvTranspose2d(n_filters * 2, n_filters, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.BatchNorm2d(n_filters),
            nn.ReLU(inplace=True),

            nn.ReflectionPad2d(3),
            nn.Conv2d(n_filters, out_channels, kernel_size=7, padding=0),
            nn.Tanh()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.downsampling(x)
        x = self.residual_blocks(x)
        return self.upsampling(x)


class GANLoss(nn.Module):
    def __init__(self, target_real_label: float = 1.0, target_fake_label: float = 0.0):
        super().__init__()
        self.register_buffer('real_label', torch.tensor(target_real_label))
        self.register_buffer('fake_label', torch.tensor(target_fake_label))
        self.loss = nn.BCELoss()

    def __call__(self, prediction: torch.Tensor, is_real: bool) -> torch.Tensor:
        target = self.real_label if is_real else self.fake_label
        target = target.expand_as(prediction)
        return self.loss(prediction, target)


class GANVoiceRepair:
    def __init__(self, sample_rate: int = 16000, n_fft: int = 512,
                 hop_length: int = 160, n_mels: int = 80,
                 device: str = 'cpu', model_type: str = 'gan'):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.device = device
        self.model_type = model_type

        if model_type == 'cyclegan':
            self.generator_A2B = CycleGANGenerator().to(device)
            self.generator_B2A = CycleGANGenerator().to(device)
            self.discriminator_A = Discriminator().to(device)
            self.discriminator_B = Discriminator().to(device)
        else:
            self.generator = Generator().to(device)
            self.discriminator = Discriminator().to(device)

        self.criterion_GAN = GANLoss().to(device)
        self.criterion_cycle = nn.L1Loss()
        self.criterion_identity = nn.L1Loss()

        self.is_trained = False

    def _preprocess_audio(self, audio: np.ndarray) -> Tuple[torch.Tensor, np.ndarray, np.ndarray]:
        audio = utils.normalize_audio(audio)

        D = librosa.stft(audio, n_fft=self.n_fft, hop_length=self.hop_length)
        mag = np.abs(D)
        phase = np.angle(D)

        mag_db = librosa.amplitude_to_db(mag, ref=np.max)
        mag_norm = (mag_db + 80) / 80
        mag_norm = np.clip(mag_norm, 0, 1)

        mag_tensor = torch.tensor(mag_norm, dtype=torch.float32, device=self.device)
        mag_tensor = mag_tensor.unsqueeze(0).unsqueeze(0)

        return mag_tensor, mag, phase

    def _postprocess_audio(self, output_tensor: torch.Tensor,
                           phase: np.ndarray) -> np.ndarray:
        output_np = output_tensor.squeeze().detach().cpu().numpy()
        output_np = output_np * 80 - 80
        mag_reconstructed = librosa.db_to_amplitude(output_np, ref=1.0)

        if mag_reconstructed.shape != phase.shape:
            from scipy.interpolate import interp2d

            if mag_reconstructed.shape[0] != phase.shape[0]:
                old_freq = np.linspace(0, 1, mag_reconstructed.shape[0])
                new_freq = np.linspace(0, 1, phase.shape[0])
                f = interp2d(np.arange(mag_reconstructed.shape[1]), old_freq, mag_reconstructed, kind='linear')
                mag_reconstructed = f(np.arange(mag_reconstructed.shape[1]), new_freq)

            if mag_reconstructed.shape[1] != phase.shape[1]:
                old_time = np.linspace(0, 1, mag_reconstructed.shape[1])
                new_time = np.linspace(0, 1, phase.shape[1])
                f = interp2d(old_time, np.arange(mag_reconstructed.shape[0]), mag_reconstructed, kind='linear')
                mag_reconstructed = f(new_time, np.arange(mag_reconstructed.shape[0]))

        D_reconstructed = mag_reconstructed * np.exp(1j * phase)
        audio_reconstructed = librosa.istft(
            D_reconstructed, hop_length=self.hop_length, length=None
        )

        max_val = np.max(np.abs(audio_reconstructed))
        if max_val > 0:
            audio_reconstructed = audio_reconstructed / max_val * 0.9

        return audio_reconstructed

    def repair_audio(self, spoofed_audio: np.ndarray,
                     reference_audio: Optional[np.ndarray] = None,
                     lambda_cycle: float = 10.0,
                     lambda_identity: float = 0.5) -> Tuple[np.ndarray, Dict[str, Any]]:
        self.generator.eval() if hasattr(self, 'generator') else self.generator_A2B.eval()

        with torch.no_grad():
            input_tensor, mag_orig, phase_orig = self._preprocess_audio(spoofed_audio)

            if self.model_type == 'cyclegan' and reference_audio is not None:
                ref_tensor, _, _ = self._preprocess_audio(reference_audio)

                fake_B = self.generator_A2B(input_tensor)
                recovered_A = self.generator_B2A(fake_B)

                fake_A = self.generator_B2A(ref_tensor)
                recovered_B = self.generator_A2B(fake_A)

                output_tensor = fake_B

                if output_tensor.shape != input_tensor.shape:
                    output_tensor = F.interpolate(output_tensor, size=input_tensor.shape[2:], mode='bilinear', align_corners=False)
                if recovered_A.shape != input_tensor.shape:
                    recovered_A = F.interpolate(recovered_A, size=input_tensor.shape[2:], mode='bilinear', align_corners=False)
                if recovered_B.shape != ref_tensor.shape:
                    recovered_B = F.interpolate(recovered_B, size=ref_tensor.shape[2:], mode='bilinear', align_corners=False)

                loss_cycle_A = self.criterion_cycle(recovered_A, input_tensor).item()
                loss_cycle_B = self.criterion_cycle(recovered_B, ref_tensor).item()

                info = {
                    'model_type': 'CycleGAN',
                    'loss_cycle_A': float(loss_cycle_A),
                    'loss_cycle_B': float(loss_cycle_B),
                    'lambda_cycle': lambda_cycle
                }
            else:
                output_tensor = self.generator(input_tensor)

                if output_tensor.shape != input_tensor.shape:
                    output_tensor = F.interpolate(output_tensor, size=input_tensor.shape[2:], mode='bilinear', align_corners=False)

                info = {
                    'model_type': 'GAN',
                    'input_shape': list(input_tensor.shape),
                    'output_shape': list(output_tensor.shape)
                }

        repaired_audio = self._postprocess_audio(output_tensor, phase_orig)

        if len(repaired_audio) < len(spoofed_audio):
            repaired_audio = np.pad(
                repaired_audio,
                (0, len(spoofed_audio) - len(repaired_audio)),
                mode='constant'
            )
        elif len(repaired_audio) > len(spoofed_audio):
            repaired_audio = repaired_audio[:len(spoofed_audio)]

        snr_improvement = self._estimate_snr_improvement(spoofed_audio, repaired_audio)
        info['snr_improvement'] = float(snr_improvement)

        return repaired_audio, info

    def _estimate_snr_improvement(self, original: np.ndarray,
                                  restored: np.ndarray) -> float:
        noise_original = np.std(original)
        noise_restored = np.std(restored)

        if noise_restored > 0:
            improvement = 20 * np.log10(noise_original / noise_restored)
            return float(improvement)
        return 0.0

    def train_step(self, real_audio: np.ndarray, spoofed_audio: np.ndarray,
                   optimizer_G: torch.optim.Optimizer,
                   optimizer_D: torch.optim.Optimizer,
                   lambda_l1: float = 100.0) -> Dict[str, float]:
        import librosa

        self.generator.train()
        self.discriminator.train()

        real_tensor, _, _ = self._preprocess_audio(real_audio)
        spoofed_tensor, _, phase = self._preprocess_audio(spoofed_audio)

        optimizer_G.zero_grad()

        fake_real = self.generator(spoofed_tensor)

        pred_fake = self.discriminator(spoofed_tensor, fake_real)
        loss_GAN = self.criterion_GAN(pred_fake, True)

        loss_L1 = self.criterion_cycle(fake_real, real_tensor) * lambda_l1

        loss_G = loss_GAN + loss_L1
        loss_G.backward()
        optimizer_G.step()

        optimizer_D.zero_grad()

        pred_real = self.discriminator(spoofed_tensor, real_tensor)
        loss_D_real = self.criterion_GAN(pred_real, True)

        pred_fake = self.discriminator(spoofed_tensor, fake_real.detach())
        loss_D_fake = self.criterion_GAN(pred_fake, False)

        loss_D = (loss_D_real + loss_D_fake) * 0.5
        loss_D.backward()
        optimizer_D.step()

        return {
            'loss_G': float(loss_G.item()),
            'loss_GAN': float(loss_GAN.item()),
            'loss_L1': float(loss_L1.item()),
            'loss_D': float(loss_D.item()),
            'loss_D_real': float(loss_D_real.item()),
            'loss_D_fake': float(loss_D_fake.item())
        }

    def save_model(self, path: str) -> None:
        import os
        dirname = os.path.dirname(path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)

        state = {
            'model_type': self.model_type,
            'is_trained': self.is_trained
        }

        if self.model_type == 'cyclegan':
            state['generator_A2B'] = self.generator_A2B.state_dict()
            state['generator_B2A'] = self.generator_B2A.state_dict()
            state['discriminator_A'] = self.discriminator_A.state_dict()
            state['discriminator_B'] = self.discriminator_B.state_dict()
        else:
            state['generator'] = self.generator.state_dict()
            state['discriminator'] = self.discriminator.state_dict()

        torch.save(state, path)

    def load_model(self, path: str) -> None:
        state = torch.load(path, map_location=self.device)
        self.model_type = state['model_type']
        self.is_trained = state['is_trained']

        if self.model_type == 'cyclegan':
            self.generator_A2B.load_state_dict(state['generator_A2B'])
            self.generator_B2A.load_state_dict(state['generator_B2A'])
            self.discriminator_A.load_state_dict(state['discriminator_A'])
            self.discriminator_B.load_state_dict(state['discriminator_B'])
        else:
            self.generator.load_state_dict(state['generator'])
            self.discriminator.load_state_dict(state['discriminator'])


class MultiScaleGANRepair:
    def __init__(self, sample_rate: int = 16000, device: str = 'cpu'):
        self.sample_rate = sample_rate
        self.device = device

        self.gan_repair = GANVoiceRepair(
            sample_rate=sample_rate,
            n_fft=512,
            hop_length=160,
            n_mels=80,
            device=device,
            model_type='gan'
        )

        self.cyclegan_repair = GANVoiceRepair(
            sample_rate=sample_rate,
            n_fft=512,
            hop_length=160,
            n_mels=80,
            device=device,
            model_type='cyclegan'
        )

    def repair(self, spoofed_audio: np.ndarray,
               reference_audio: Optional[np.ndarray] = None,
               use_cyclegan: bool = False) -> Tuple[np.ndarray, Dict[str, Any]]:
        if use_cyclegan and reference_audio is not None:
            return self.cyclegan_repair.repair_audio(spoofed_audio, reference_audio)
        else:
            return self.gan_repair.repair_audio(spoofed_audio)

    def hybrid_repair(self, spoofed_audio: np.ndarray,
                      reference_audio: Optional[np.ndarray] = None,
                      estimated_pitch_factor: float = 1.0) -> Tuple[np.ndarray, Dict[str, Any]]:
        from .pitch_recovery import AudioRestoration

        pitch_restorer = AudioRestoration(sample_rate=self.sample_rate)

        pitch_repaired, pitch_info = pitch_restorer.restore_audio(
            spoofed_audio,
            estimated_pitch_factor=estimated_pitch_factor,
            reference_audio=reference_audio
        )

        gan_repaired, gan_info = self.gan_repair.repair_audio(
            pitch_repaired, reference_audio
        )

        info = {
            'pitch_recovery': pitch_info,
            'gan_repair': gan_info,
            'method': 'hybrid_pitch_gan'
        }

        return gan_repaired, info
