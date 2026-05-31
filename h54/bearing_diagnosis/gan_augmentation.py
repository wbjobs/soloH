import numpy as np
from typing import Optional, Tuple, List, Dict, Union
import warnings

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    warnings.warn("PyTorch not available. GAN augmentation will use NumPy fallback.")

from .data_generator import generate_bearing_signal
from .preprocessing import Preprocessor
from .feature_extraction import FeatureExtractor


class Generator(nn.Module):
    """GAN生成器 - 生成合成振动信号或特征"""
    
    def __init__(self, latent_dim: int = 100, output_dim: int = 128, n_channels: int = 1):
        super(Generator, self).__init__()
        self.n_channels = n_channels
        self.output_dim = output_dim
        
        self.model = nn.Sequential(
            nn.Linear(latent_dim, 256),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(256),
            
            nn.Linear(256, 512),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(512),
            
            nn.Linear(512, 1024),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(1024),
            
            nn.Linear(1024, output_dim * n_channels),
            nn.Tanh()
        )
    
    def forward(self, z: torch.Tensor) -> torch.Tensor:
        output = self.model(z)
        return output.view(output.size(0), self.output_dim, self.n_channels)


class Discriminator(nn.Module):
    """GAN判别器 - 判断信号是真实还是生成"""
    
    def __init__(self, input_dim: int = 128, n_channels: int = 1):
        super(Discriminator, self).__init__()
        
        self.model = nn.Sequential(
            nn.Flatten(),
            nn.Linear(input_dim * n_channels, 512),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            
            nn.Linear(512, 256),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            
            nn.Linear(256, 128),
            nn.LeakyReLU(0.2),
            
            nn.Linear(128, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)


class GANDataAugmenter:
    """
    基于GAN的故障数据增强器
    
    用于缓解样本不平衡问题，为少数类故障生成合成样本。
    支持两种模式：
    1. 信号级增强：直接生成合成振动信号
    2. 特征级增强：生成合成特征向量
    """
    
    def __init__(self, fs: float = 25600.0,
                 latent_dim: int = 100,
                 n_channels: int = 1,
                 use_feature_space: bool = True,
                 device: str = 'auto'):
        """
        Args:
            fs: 采样频率 (Hz)
            latent_dim: 潜在空间维度
            n_channels: 通道数
            use_feature_space: 是否在特征空间进行增强（更稳定）
            device: 计算设备 ('auto', 'cpu', 'cuda')
        """
        self.fs = fs
        self.latent_dim = latent_dim
        self.n_channels = n_channels
        self.use_feature_space = use_feature_space
        self.is_trained = False
        
        if TORCH_AVAILABLE:
            if device == 'auto':
                self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            else:
                self.device = torch.device(device)
        else:
            self.device = 'cpu'
        
        self.generator = None
        self.discriminator = None
        self.optimizer_g = None
        self.optimizer_d = None
        self.criterion = None
        
        self.fault_type_map = {
            'normal': 0,
            'inner_race': 1,
            'outer_race': 2,
            'rolling_element': 3,
            'cage': 4
        }
    
    def _init_models(self, input_dim: int):
        """初始化GAN模型"""
        if not TORCH_AVAILABLE:
            return
        
        self.generator = Generator(
            latent_dim=self.latent_dim,
            output_dim=input_dim,
            n_channels=self.n_channels
        ).to(self.device)
        
        self.discriminator = Discriminator(
            input_dim=input_dim,
            n_channels=self.n_channels
        ).to(self.device)
        
        self.optimizer_g = optim.Adam(self.generator.parameters(), lr=0.0002, betas=(0.5, 0.999))
        self.optimizer_d = optim.Adam(self.discriminator.parameters(), lr=0.0002, betas=(0.5, 0.999))
        self.criterion = nn.BCELoss()
    
    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None,
            fault_type: Optional[str] = None,
            epochs: int = 500,
            batch_size: int = 32,
            verbose: bool = True) -> 'GANDataAugmenter':
        """
        训练GAN模型
        
        Args:
            X: 输入数据 (n_samples, n_features) 或 (n_samples, n_timesteps, n_channels)
            y: 标签 (可选)
            fault_type: 针对特定故障类型训练
            epochs: 训练轮数
            batch_size: 批次大小
            verbose: 是否显示训练进度
        
        Returns:
            self
        """
        if y is not None and fault_type is not None:
            mask = np.array([label == fault_type for label in y])
            X_train = X[mask]
            if verbose:
                print(f"训练 {fault_type} 的GAN模型，样本数: {len(X_train)}")
        else:
            X_train = X
        
        if len(X_train) < 10:
            warnings.warn(f"样本数太少 ({len(X_train)})，GAN训练可能不稳定。使用传统增强方法。")
            self.is_trained = False
            return self
        
        if X_train.ndim == 2:
            input_dim = X_train.shape[1]
            X_tensor = torch.FloatTensor(X_train).unsqueeze(-1).to(self.device)
        else:
            input_dim = X_train.shape[1]
            X_tensor = torch.FloatTensor(X_train).to(self.device)
        
        if TORCH_AVAILABLE:
            self._init_models(input_dim)
            
            dataset = TensorDataset(X_tensor)
            dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
            
            for epoch in range(epochs):
                for batch in dataloader:
                    real_data = batch[0]
                    batch_size_real = real_data.size(0)
                    
                    real_labels = torch.ones(batch_size_real, 1).to(self.device) * 0.9
                    fake_labels = torch.zeros(batch_size_real, 1).to(self.device)
                    
                    self.optimizer_d.zero_grad()
                    
                    real_output = self.discriminator(real_data)
                    d_loss_real = self.criterion(real_output, real_labels)
                    
                    z = torch.randn(batch_size_real, self.latent_dim).to(self.device)
                    fake_data = self.generator(z)
                    fake_output = self.discriminator(fake_data.detach())
                    d_loss_fake = self.criterion(fake_output, fake_labels)
                    
                    d_loss = d_loss_real + d_loss_fake
                    d_loss.backward()
                    self.optimizer_d.step()
                    
                    self.optimizer_g.zero_grad()
                    
                    fake_output = self.discriminator(fake_data)
                    g_loss = self.criterion(fake_output, real_labels)
                    g_loss.backward()
                    self.optimizer_g.step()
                
                if verbose and (epoch + 1) % 100 == 0:
                    print(f"Epoch [{epoch+1}/{epochs}], D_loss: {d_loss.item():.4f}, G_loss: {g_loss.item():.4f}")
            
            self.is_trained = True
        else:
            self.is_trained = False
        
        return self
    
    def generate(self, n_samples: int,
                 fault_type: Optional[str] = None,
                 severity: str = 'medium',
                 rotational_speed: float = 50.0,
                 n_rolling_elements: int = 9,
                 pitch_diameter: float = 39.04,
                 rolling_element_diameter: float = 7.94,
                 contact_angle: float = 0.0,
                 duration: float = 0.5) -> np.ndarray:
        """
        生成合成样本
        
        Args:
            n_samples: 生成样本数量
            fault_type: 故障类型（生成信号级样本时需要）
            severity: 严重程度
            rotational_speed: 转速 (Hz)
            n_rolling_elements: 滚动体数量
            pitch_diameter: 节径 (mm)
            rolling_element_diameter: 滚动体直径 (mm)
            contact_angle: 接触角 (度)
            duration: 信号时长 (秒)
        
        Returns:
            合成样本数组
        """
        if self.is_trained and TORCH_AVAILABLE and self.generator is not None:
            self.generator.eval()
            with torch.no_grad():
                z = torch.randn(n_samples, self.latent_dim).to(self.device)
                generated = self.generator(z).cpu().numpy()
                
                if generated.shape[-1] == 1:
                    generated = generated.squeeze(-1)
                
                return generated
        else:
            return self._traditional_augmentation(
                n_samples=n_samples,
                fault_type=fault_type,
                severity=severity,
                rotational_speed=rotational_speed,
                n_rolling_elements=n_rolling_elements,
                pitch_diameter=pitch_diameter,
                rolling_element_diameter=rolling_element_diameter,
                contact_angle=contact_angle,
                duration=duration
            )
    
    def _traditional_augmentation(self, n_samples: int,
                                  fault_type: Optional[str] = None,
                                  severity: str = 'medium',
                                  rotational_speed: float = 50.0,
                                  n_rolling_elements: int = 9,
                                  pitch_diameter: float = 39.04,
                                  rolling_element_diameter: float = 7.94,
                                  contact_angle: float = 0.0,
                                  duration: float = 0.5) -> np.ndarray:
        """
        传统数据增强方法（GAN不可用时的备选方案）
        包含：随机噪声注入、幅值缩放、时间偏移、相位随机化
        """
        generated_samples = []
        
        for i in range(n_samples):
            if fault_type is None:
                ft = np.random.choice(['inner_race', 'outer_race', 'rolling_element', 'cage'])
            else:
                ft = fault_type
            
            noise_variation = np.random.uniform(0.8, 1.2)
            amplitude_scale = np.random.uniform(0.8, 1.2)
            speed_variation = rotational_speed * np.random.uniform(0.95, 1.05)
            
            signal = generate_bearing_signal(
                fs=self.fs,
                duration=duration,
                fault_type=ft,
                severity=severity,
                n_channels=self.n_channels,
                rotational_speed=speed_variation,
                n_rolling_elements=n_rolling_elements,
                pitch_diameter=pitch_diameter,
                rolling_element_diameter=rolling_element_diameter,
                contact_angle=contact_angle,
                noise_level=0.5 * noise_variation,
                random_state=None
            )
            
            signal = signal * amplitude_scale
            
            if self.use_feature_space:
                preprocessor = Preprocessor(fs=self.fs)
                feature_extractor = FeatureExtractor(fs=self.fs)
                
                processed = preprocessor.preprocess(signal)
                features, _ = feature_extractor.extract(processed)
                generated_samples.append(features.flatten())
            else:
                generated_samples.append(signal)
        
        return np.array(generated_samples)
    
    def balance_dataset(self, X: np.ndarray, y: np.ndarray,
                        target_count: Optional[int] = None,
                        epochs_per_class: int = 300,
                        verbose: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        平衡数据集 - 为少数类生成合成样本
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
            y: 标签数组
            target_count: 目标样本数（None则使用最多类的数量）
            epochs_per_class: 每个类的训练轮数
            verbose: 是否显示进度
        
        Returns:
            (X_balanced, y_balanced) 平衡后的数据集
        """
        unique_labels, counts = np.unique(y, return_counts=True)
        
        if target_count is None:
            target_count = max(counts)
        
        if verbose:
            print(f"原始样本分布:")
            for label, count in zip(unique_labels, counts):
                print(f"  {label}: {count}")
            print(f"目标样本数: {target_count}")
        
        X_balanced = [X.copy()]
        y_balanced = [y.copy()]
        n_features = X.shape[1]
        
        for label, count in zip(unique_labels, counts):
            if count >= target_count:
                continue
            
            n_to_generate = target_count - count
            
            if verbose:
                print(f"\n为 {label} 生成 {n_to_generate} 个合成样本...")
            
            try:
                gan_generated = False
                
                if TORCH_AVAILABLE and len(X[y == label]) >= 10:
                    try:
                        self.fit(X, y, fault_type=label, epochs=epochs_per_class, verbose=verbose)
                        
                        generated = self.generate(
                            n_samples=n_to_generate,
                            fault_type=label
                        )
                        
                        if generated.shape[1] == n_features:
                            gan_generated = True
                        elif generated.ndim == 3:
                            preprocessor = Preprocessor(fs=self.fs)
                            feature_extractor = FeatureExtractor(fs=self.fs, n_channels=self.n_channels)
                            
                            gen_features = []
                            for i in range(len(generated)):
                                sig = generated[i]
                                if sig.ndim == 1:
                                    sig = sig.reshape(-1, self.n_channels)
                                elif sig.shape[1] != self.n_channels and self.n_channels > 1:
                                    sig = np.tile(sig.reshape(-1, 1), (1, self.n_channels))
                                processed = preprocessor.preprocess(sig)
                                feats, _ = feature_extractor.extract(processed)
                                gen_features.append(feats.flatten())
                            generated = np.array(gen_features)
                            if generated.shape[1] == n_features:
                                gan_generated = True
                    except Exception as e:
                        if verbose:
                            print(f"  GAN训练失败: {e}，使用SMOTE风格增强")
                
                if not gan_generated:
                    mask = np.array([lbl == label for lbl in y])
                    X_class = X[mask]
                    
                    if len(X_class) < 2:
                        mean = X_class.mean(axis=0)
                        std = X_class.std(axis=0) + 1e-8
                        generated = mean + np.random.randn(n_to_generate, n_features) * std * 0.3
                    else:
                        generated = np.zeros((n_to_generate, n_features))
                        for i in range(n_to_generate):
                            idx1, idx2 = np.random.choice(len(X_class), 2, replace=False)
                            lam = np.random.random()
                            generated[i] = X_class[idx1] + lam * (X_class[idx2] - X_class[idx1])
                        
                        noise = np.random.randn(n_to_generate, n_features) * X_class.std(axis=0) * 0.1
                        generated += noise
                
                X_balanced.append(generated)
                y_balanced.append(np.array([label] * n_to_generate))
                
                if verbose:
                    print(f"✓ 成功生成 {n_to_generate} 个 {label} 样本")
                    
            except Exception as e:
                warnings.warn(f"为 {label} 生成样本失败: {e}。使用高斯噪声增强...")
                mask = np.array([lbl == label for lbl in y])
                if mask.sum() > 0:
                    mean = X[mask].mean(axis=0)
                    std = X[mask].std(axis=0) + 1e-8
                    generated = mean + np.random.randn(n_to_generate, n_features) * std * 0.5
                else:
                    generated = np.random.randn(n_to_generate, n_features) * 0.1
                
                X_balanced.append(generated)
                y_balanced.append(np.array([label] * n_to_generate))
        
        X_balanced = np.vstack(X_balanced)
        y_balanced = np.concatenate(y_balanced)
        
        if verbose:
            unique_bal, counts_bal = np.unique(y_balanced, return_counts=True)
            print(f"\n平衡后样本分布:")
            for label, count in zip(unique_bal, counts_bal):
                print(f"  {label}: {count}")
        
        return X_balanced, y_balanced
    
    def save(self, path: str) -> None:
        """保存GAN模型"""
        if TORCH_AVAILABLE and self.generator is not None:
            torch.save({
                'generator_state_dict': self.generator.state_dict(),
                'discriminator_state_dict': self.discriminator.state_dict(),
                'latent_dim': self.latent_dim,
                'n_channels': self.n_channels,
                'is_trained': self.is_trained
            }, path)
    
    def load(self, path: str) -> 'GANDataAugmenter':
        """加载GAN模型"""
        if TORCH_AVAILABLE:
            checkpoint = torch.load(path, map_location=self.device)
            self.latent_dim = checkpoint['latent_dim']
            self.n_channels = checkpoint['n_channels']
            self.is_trained = checkpoint['is_trained']
            
            if self.is_trained:
                self._init_models(128)
                self.generator.load_state_dict(checkpoint['generator_state_dict'])
                self.discriminator.load_state_dict(checkpoint['discriminator_state_dict'])
        
        return self
