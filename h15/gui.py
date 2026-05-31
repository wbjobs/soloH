import sys
import numpy as np
from typing import Optional, Dict, List

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QGroupBox, QCheckBox, QProgressBar, QTextEdit,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QFont

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from phantom import shepp_logan_phantom, generate_sensitivity_maps, add_noise
from kspace import compute_kspace, apply_mask, ifft2c
from undersampling import generate_mask, get_sampling_patterns
from reconstruction import (
    reconstruct, get_reconstruction_methods,
    zero_filled_reconstruction,
)
from wavelet import get_available_wavelets, get_wavelet_families
from metrics import compute_metrics, error_map


plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class ImageCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.im = None
        self.ax.set_xticks([])
        self.ax.set_yticks([])
    
    def update_image(self, img: np.ndarray, title: str = "", 
                     cmap: str = 'gray', vmin: float = None, vmax: float = None):
        self.ax.clear()
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        
        if img is not None:
            self.im = self.ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax)
            self.fig.colorbar(self.im, ax=self.ax, fraction=0.046, pad=0.04)
        
        if title:
            self.ax.set_title(title, fontsize=10)
        
        self.fig.tight_layout()
        self.draw()


class ReconstructionWorker(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    
    def __init__(self, params: Dict):
        super().__init__()
        self.params = params
    
    def run(self):
        try:
            size = self.params['size']
            pattern = self.params['pattern']
            method = self.params['method']
            acceleration = self.params['acceleration']
            wavelet = self.params.get('wavelet', 'db4')
            wavelet_level = self.params.get('wavelet_level', 3)
            snr_db = self.params.get('snr_db', 30)
            use_sense = self.params.get('use_sense', False)
            dynamic_mode = self.params.get('dynamic_mode', False)
            num_frames = self.params.get('num_frames', 20)
            motion_type = self.params.get('motion_type', 'rotation')
            
            dynamic_methods = ['kt_slr', 'kt_focuss', 'temporal_low_rank']
            if method in dynamic_methods:
                dynamic_mode = True
            
            if dynamic_mode:
                self.message.emit(f"正在生成动态 Phantom ({num_frames}帧)...")
                self.progress.emit(5)
                from kt_slr import generate_dynamic_phantom, generate_dynamic_kspace
                phantom_dynamic = generate_dynamic_phantom(size, num_frames, motion_type)
                phantom = phantom_dynamic[0]
                
                self.message.emit("正在生成动态k空间...")
                self.progress.emit(20)
                
                mask = generate_mask(pattern, size, acceleration=acceleration, random_t=True, num_frames=num_frames)
                kspace_und, mask = generate_dynamic_kspace(phantom_dynamic, mask, snr_db)
                kspace_full = kspace_und.copy()
                
                recon_params = {
                    'wavelet': wavelet,
                    'wavelet_level': wavelet_level,
                    'num_iter': self.params.get('num_iter', 30),
                    'lambda_lr': self.params.get('lambda_lr', 0.1),
                    'lambda_sp': self.params.get('lambda_sp', 0.01),
                }
                
                self.message.emit(f"正在使用 {method} 方法重建动态图像...")
                self.progress.emit(50)
                
                recon_dynamic = reconstruct(method, kspace_und, mask, **recon_params)
                recon_img = recon_dynamic[0]
                
                self.message.emit("正在计算图像质量指标...")
                self.progress.emit(85)
                
                from kt_slr import compute_dynamic_metrics
                dynamic_metrics = compute_dynamic_metrics(phantom_dynamic, recon_dynamic)
                metrics = {
                    'PSNR': dynamic_metrics['avg_PSNR'],
                    'SSIM': dynamic_metrics['avg_SSIM'],
                    'NMSE': dynamic_metrics['avg_NMSE'],
                }
                
                zf_img = np.abs(ifft2c(kspace_und[0]))
                err_map = error_map(phantom, recon_img, align=self.params.get('auto_align', True))
                
                result = {
                    'phantom': phantom,
                    'mask': mask[0] if mask.ndim == 3 else mask,
                    'kspace_full': kspace_full[0],
                    'kspace_und': kspace_und[0],
                    'zf_recon': zf_img,
                    'recon': recon_img,
                    'error_map': err_map,
                    'metrics': metrics,
                    'dynamic_phantom': phantom_dynamic,
                    'dynamic_recon': recon_dynamic,
                    'dynamic_metrics': dynamic_metrics,
                    'sampling_rate': mask.sum() / mask.size,
                }
            else:
                self.message.emit("正在生成 Shepp-Logan Phantom...")
                self.progress.emit(5)
                phantom = shepp_logan_phantom(size)
                
                self.message.emit("正在计算全采样k空间...")
                self.progress.emit(15)
                
                if use_sense:
                    num_channels = 8
                    sense_maps = generate_sensitivity_maps(size, num_channels)
                    phantom_multi = phantom[np.newaxis, :, :] * sense_maps
                    kspace_full = compute_kspace(phantom_multi)
                else:
                    kspace_full = compute_kspace(phantom)
                
                if snr_db > 0:
                    kspace_full = add_noise(kspace_full, snr_db)
                
                self.message.emit(f"正在生成 {pattern} 采样模式...")
                self.progress.emit(30)
                
                mask_params = {'acceleration': acceleration} if pattern in ['cartesian', 'random'] else {}
                if pattern == 'radial':
                    mask_params = {'num_spokes': max(16, int(256 / acceleration))}
                elif pattern == 'spiral':
                    mask_params = {'num_arms': max(8, int(128 / acceleration)),
                                  'use_density_compensation': self.params.get('use_density_compensation', True)}
                
                mask = generate_mask(pattern, size, **mask_params)
                
                self.message.emit("正在应用欠采样...")
                self.progress.emit(45)
                kspace_und = apply_mask(kspace_full, mask)
                
                recon_params = {}
                if method == 'tv':
                    recon_params = {
                        'lambda_tv': self.params.get('lambda_tv', 0.05),
                        'num_iter': self.params.get('num_iter', 30),
                    }
                elif method == 'sense':
                    recon_params = {
                        'sense_maps': sense_maps,
                        'mask': mask,
                        'num_iter': self.params.get('num_iter', 20),
                    }
                elif method in ['cs_mri_ist', 'cs_mri_fista']:
                    recon_params = {
                        'wavelet': wavelet,
                        'wavelet_level': wavelet_level,
                        'lambda_csmri': self.params.get('lambda_csmri', 0.01),
                        'num_iter': self.params.get('num_iter', 50),
                        'use_cycle_spinning': self.params.get('use_cycle_spinning', True),
                        'num_cycle_shifts': self.params.get('num_cycle_shifts', 2),
                        'use_density_compensation': self.params.get('use_density_compensation', True),
                    }
                elif method == 'pnp_dncnn':
                    recon_params = {
                        'denoiser_type': self.params.get('denoiser_type', 'auto'),
                        'num_iter': self.params.get('num_iter', 30),
                        'rho': self.params.get('rho', 1.0),
                        'sigma_denoise': self.params.get('sigma_denoise', 0.05),
                    }
                elif method == 'gridding':
                    from nufft_recon import generate_radial_trajectory, generate_spiral_trajectory
                    if pattern == 'radial':
                        kx, ky = generate_radial_trajectory(num_spokes=mask_params.get('num_spokes', 64), num_samples=size)
                    elif pattern == 'spiral':
                        kx, ky = generate_spiral_trajectory(num_arms=mask_params.get('num_arms', 16), num_samples=size*2)
                    else:
                        kx, ky = generate_radial_trajectory(num_spokes=64, num_samples=size)
                    kspace_data = kspace_und.flatten() if kspace_und.ndim == 2 else kspace_und
                    recon_params = {
                        'kx': kx,
                        'ky': ky,
                        'grid_size': size,
                        'num_iter': self.params.get('num_iter', 20),
                    }
                
                self.message.emit(f"正在使用 {method} 方法重建...")
                self.progress.emit(60)
                
                if method == 'sense' and not use_sense:
                    recon_img = zero_filled_reconstruction(kspace_und)
                else:
                    recon_img = reconstruct(method, kspace_und, mask, **recon_params)
                
                self.message.emit("正在计算图像质量指标...")
                self.progress.emit(85)
                
                ref_img = phantom
                auto_align = self.params.get('auto_align', True)
                metrics = compute_metrics(ref_img, recon_img, align=auto_align)
                err_map = error_map(ref_img, recon_img, align=auto_align)
                
                zf_img = zero_filled_reconstruction(
                    kspace_und if kspace_und.ndim == 2 else np.sum(kspace_und, axis=0)
                )
                
                result = {
                    'phantom': phantom,
                    'mask': mask,
                    'kspace_full': kspace_full,
                    'kspace_und': kspace_und,
                    'zf_recon': zf_img,
                    'recon': recon_img,
                    'error_map': err_map,
                    'metrics': metrics,
                    'sampling_rate': mask.sum() / mask.size,
                }
            
            self.message.emit("完成！")
            self.progress.emit(100)
            self.finished.emit(result)
            
        except Exception as e:
            import traceback
            error_msg = f"错误: {str(e)}\n{traceback.format_exc()}"
            self.message.emit(error_msg)
            self.finished.emit({'error': str(e)})


class BatchWorker(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    
    def __init__(self, params: Dict):
        super().__init__()
        self.params = params
    
    def run(self):
        try:
            size = self.params['size']
            patterns = self.params['patterns']
            methods = self.params['methods']
            acceleration = self.params['acceleration']
            wavelet = self.params.get('wavelet', 'db4')
            wavelet_level = self.params.get('wavelet_level', 3)
            snr_db = self.params.get('snr_db', 30)
            use_cycle_spinning = self.params.get('use_cycle_spinning', True)
            num_cycle_shifts = self.params.get('num_cycle_shifts', 2)
            use_density_compensation = self.params.get('use_density_compensation', True)
            auto_align = self.params.get('auto_align', True)
            denoiser_type = self.params.get('denoiser_type', 'auto')
            rho = self.params.get('rho', 1.0)
            
            self.message.emit("正在生成 Shepp-Logan Phantom...")
            phantom = shepp_logan_phantom(size)
            kspace_full = compute_kspace(phantom)
            if snr_db > 0:
                kspace_full = add_noise(kspace_full, snr_db)
            
            batch_results = []
            total_tasks = len(patterns) * len(methods)
            current_task = 0
            
            for pattern in patterns:
                self.message.emit(f"处理采样模式: {pattern}...")
                
                mask_params = {'acceleration': acceleration} if pattern in ['cartesian', 'random'] else {}
                if pattern == 'radial':
                    mask_params = {'num_spokes': max(16, int(256 / acceleration))}
                elif pattern == 'spiral':
                    mask_params = {'num_arms': max(8, int(128 / acceleration)),
                                  'use_density_compensation': use_density_compensation}
                
                mask = generate_mask(pattern, size, **mask_params)
                kspace_und = apply_mask(kspace_full, mask)
                
                for method in methods:
                    current_task += 1
                    self.progress.emit(int(current_task / total_tasks * 80))
                    self.message.emit(f"重建: {pattern} + {method}...")
                    
                    recon_params = {}
                    if method == 'tv':
                        recon_params = {'lambda_tv': 0.05, 'num_iter': 30}
                    elif method in ['cs_mri_ist', 'cs_mri_fista']:
                        recon_params = {
                            'wavelet': wavelet,
                            'wavelet_level': wavelet_level,
                            'lambda_csmri': 0.01,
                            'num_iter': 50,
                            'use_cycle_spinning': use_cycle_spinning,
                            'num_cycle_shifts': num_cycle_shifts,
                            'use_density_compensation': use_density_compensation,
                        }
                    elif method == 'pnp_dncnn':
                        recon_params = {
                            'denoiser_type': denoiser_type,
                            'num_iter': 30,
                            'rho': rho,
                            'sigma_denoise': 0.05,
                        }
                    elif method == 'gridding':
                        from nufft_recon import generate_radial_trajectory, generate_spiral_trajectory
                        if pattern == 'radial':
                            kx, ky = generate_radial_trajectory(num_spokes=mask_params.get('num_spokes', 64), num_samples=size)
                        elif pattern == 'spiral':
                            kx, ky = generate_spiral_trajectory(num_arms=mask_params.get('num_arms', 16), num_samples=size*2)
                        else:
                            kx, ky = generate_radial_trajectory(num_spokes=64, num_samples=size)
                        recon_params = {
                            'kx': kx,
                            'ky': ky,
                            'grid_size': size,
                            'num_iter': 20,
                        }
                    elif method in ['kt_slr', 'kt_focuss', 'temporal_low_rank']:
                        continue
                    
                    recon_img = reconstruct(method, kspace_und, mask, **recon_params)
                    metrics = compute_metrics(phantom, recon_img, align=auto_align)
                    
                    batch_results.append({
                        'pattern': pattern,
                        'method': method,
                        'recon': recon_img,
                        'metrics': metrics,
                        'sampling_rate': mask.sum() / mask.size,
                    })
            
            self.progress.emit(100)
            self.message.emit("批量处理完成！")
            
            self.finished.emit({
                'phantom': phantom,
                'results': batch_results,
            })
            
        except Exception as e:
            import traceback
            error_msg = f"错误: {str(e)}\n{traceback.format_exc()}"
            self.message.emit(error_msg)
            self.finished.emit({'error': str(e)})


class MRISimGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MRI 采集与重建模拟系统")
        self.resize(1400, 900)
        
        self.worker = None
        self.batch_worker = None
        self.current_result = None
        
        self.init_ui()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        control_panel = self.create_control_panel()
        splitter.addWidget(control_panel)
        
        display_panel = self.create_display_panel()
        splitter.addWidget(display_panel)
        
        splitter.setSizes([350, 1050])
        
        self.statusBar().showMessage("准备就绪")
    
    def create_control_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        
        phantom_group = QGroupBox("数据生成")
        phantom_layout = QGridLayout()
        
        phantom_layout.addWidget(QLabel("图像大小:"), 0, 0)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(64, 512)
        self.size_spin.setValue(256)
        self.size_spin.setSingleStep(64)
        phantom_layout.addWidget(self.size_spin, 0, 1)
        
        phantom_layout.addWidget(QLabel("SNR (dB):"), 1, 0)
        self.snr_spin = QDoubleSpinBox()
        self.snr_spin.setRange(0, 100)
        self.snr_spin.setValue(30)
        self.snr_spin.setSingleStep(5)
        phantom_layout.addWidget(self.snr_spin, 1, 1)
        
        self.sense_check = QCheckBox("使用SENSE多通道")
        phantom_layout.addWidget(self.sense_check, 2, 0, 1, 2)
        
        phantom_group.setLayout(phantom_layout)
        layout.addWidget(phantom_group)
        
        sampling_group = QGroupBox("欠采样模式")
        sampling_layout = QGridLayout()
        
        sampling_layout.addWidget(QLabel("采样模式:"), 0, 0)
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems(get_sampling_patterns().keys())
        sampling_layout.addWidget(self.pattern_combo, 0, 1)
        
        sampling_layout.addWidget(QLabel("加速因子:"), 1, 0)
        self.accel_spin = QDoubleSpinBox()
        self.accel_spin.setRange(1, 16)
        self.accel_spin.setValue(4)
        self.accel_spin.setSingleStep(0.5)
        sampling_layout.addWidget(self.accel_spin, 1, 1)
        
        sampling_group.setLayout(sampling_layout)
        layout.addWidget(sampling_group)
        
        recon_group = QGroupBox("重建算法")
        recon_layout = QGridLayout()
        
        recon_layout.addWidget(QLabel("重建方法:"), 0, 0)
        self.method_combo = QComboBox()
        recon_methods = get_reconstruction_methods()
        self.method_combo.addItems(recon_methods.keys())
        self.method_combo.setCurrentText('cs_mri_fista')
        recon_layout.addWidget(self.method_combo, 0, 1)
        
        recon_layout.addWidget(QLabel("迭代次数:"), 1, 0)
        self.iter_spin = QSpinBox()
        self.iter_spin.setRange(1, 500)
        self.iter_spin.setValue(50)
        recon_layout.addWidget(self.iter_spin, 1, 1)
        
        recon_layout.addWidget(QLabel("正则化参数:"), 2, 0)
        self.lambda_spin = QDoubleSpinBox()
        self.lambda_spin.setRange(0.0001, 1)
        self.lambda_spin.setValue(0.01)
        self.lambda_spin.setDecimals(4)
        self.lambda_spin.setSingleStep(0.001)
        recon_layout.addWidget(self.lambda_spin, 2, 1)
        
        wavelet_group = QGroupBox("小波基")
        wavelet_layout = QGridLayout()
        
        wavelet_layout.addWidget(QLabel("小波族:"), 0, 0)
        self.wavelet_family_combo = QComboBox()
        self.wavelet_family_combo.addItems(get_wavelet_families().keys())
        self.wavelet_family_combo.currentTextChanged.connect(self.update_wavelet_combo)
        wavelet_layout.addWidget(self.wavelet_family_combo, 0, 1)
        
        wavelet_layout.addWidget(QLabel("小波基:"), 1, 0)
        self.wavelet_combo = QComboBox()
        self.update_wavelet_combo()
        wavelet_layout.addWidget(self.wavelet_combo, 1, 1)
        
        wavelet_layout.addWidget(QLabel("分解层数:"), 2, 0)
        self.wavelet_level_spin = QSpinBox()
        self.wavelet_level_spin.setRange(1, 5)
        self.wavelet_level_spin.setValue(3)
        wavelet_layout.addWidget(self.wavelet_level_spin, 2, 1)
        
        wavelet_group.setLayout(wavelet_layout)
        recon_layout.addWidget(wavelet_group, 3, 0, 1, 2)
        
        advanced_group = QGroupBox("高级选项")
        advanced_layout = QGridLayout()
        
        self.cycle_spin_check = QCheckBox("Cycle Spinning (减少块效应)")
        self.cycle_spin_check.setChecked(True)
        advanced_layout.addWidget(self.cycle_spin_check, 0, 0, 1, 2)
        
        advanced_layout.addWidget(QLabel("循环平移次数:"), 1, 0)
        self.cycle_shifts_spin = QSpinBox()
        self.cycle_shifts_spin.setRange(1, 8)
        self.cycle_shifts_spin.setValue(2)
        advanced_layout.addWidget(self.cycle_shifts_spin, 1, 1)
        
        self.density_comp_check = QCheckBox("轨迹密度补偿 (螺旋/径向)")
        self.density_comp_check.setChecked(True)
        advanced_layout.addWidget(self.density_comp_check, 2, 0, 1, 2)
        
        self.align_check = QCheckBox("自动尺寸对齐 (PSNR)")
        self.align_check.setChecked(True)
        advanced_layout.addWidget(self.align_check, 3, 0, 1, 2)
        
        advanced_layout.addWidget(QLabel("DnCNN去噪器类型:"), 4, 0)
        self.denoiser_combo = QComboBox()
        self.denoiser_combo.addItems(['auto', 'bilateral'])
        self.denoiser_combo.setCurrentText('auto')
        advanced_layout.addWidget(self.denoiser_combo, 4, 1)
        
        advanced_layout.addWidget(QLabel("PnP ADMM rho:"), 5, 0)
        self.rho_spin = QDoubleSpinBox()
        self.rho_spin.setRange(0.01, 10.0)
        self.rho_spin.setValue(1.0)
        self.rho_spin.setDecimals(2)
        self.rho_spin.setSingleStep(0.1)
        advanced_layout.addWidget(self.rho_spin, 5, 1)
        
        advanced_group.setLayout(advanced_layout)
        recon_layout.addWidget(advanced_group, 4, 0, 1, 2)
        
        dynamic_group = QGroupBox("动态MRI设置")
        dynamic_layout = QGridLayout()
        
        self.dynamic_check = QCheckBox("启用动态MRI模式")
        self.dynamic_check.setChecked(False)
        self.dynamic_check.stateChanged.connect(self._toggle_dynamic)
        dynamic_layout.addWidget(self.dynamic_check, 0, 0, 1, 2)
        
        dynamic_layout.addWidget(QLabel("时间帧数:"), 1, 0)
        self.num_frames_spin = QSpinBox()
        self.num_frames_spin.setRange(5, 100)
        self.num_frames_spin.setValue(20)
        self.num_frames_spin.setEnabled(False)
        dynamic_layout.addWidget(self.num_frames_spin, 1, 1)
        
        dynamic_layout.addWidget(QLabel("运动类型:"), 2, 0)
        self.motion_combo = QComboBox()
        self.motion_combo.addItems(['rotation', 'translation', 'expansion'])
        self.motion_combo.setEnabled(False)
        dynamic_layout.addWidget(self.motion_combo, 2, 1)
        
        dynamic_layout.addWidget(QLabel("低秩权重 λ_LR:"), 3, 0)
        self.lambda_lr_spin = QDoubleSpinBox()
        self.lambda_lr_spin.setRange(0.001, 1.0)
        self.lambda_lr_spin.setValue(0.1)
        self.lambda_lr_spin.setDecimals(3)
        self.lambda_lr_spin.setSingleStep(0.01)
        self.lambda_lr_spin.setEnabled(False)
        dynamic_layout.addWidget(self.lambda_lr_spin, 3, 1)
        
        dynamic_layout.addWidget(QLabel("稀疏权重 λ_SP:"), 4, 0)
        self.lambda_sp_spin = QDoubleSpinBox()
        self.lambda_sp_spin.setRange(0.001, 1.0)
        self.lambda_sp_spin.setValue(0.01)
        self.lambda_sp_spin.setDecimals(3)
        self.lambda_sp_spin.setSingleStep(0.01)
        self.lambda_sp_spin.setEnabled(False)
        dynamic_layout.addWidget(self.lambda_sp_spin, 4, 1)
        
        dynamic_group.setLayout(dynamic_layout)
        layout.addWidget(dynamic_group)
        
        recon_group.setLayout(recon_layout)
        layout.addWidget(recon_group)
        
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout()
        
        self.run_button = QPushButton("运行模拟与重建")
        self.run_button.clicked.connect(self.run_reconstruction)
        self.run_button.setMinimumHeight(40)
        action_layout.addWidget(self.run_button)
        
        self.batch_button = QPushButton("批量对比处理")
        self.batch_button.clicked.connect(self.run_batch)
        self.batch_button.setMinimumHeight(35)
        action_layout.addWidget(self.batch_button)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar)
        
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)
        
        batch_config_group = QGroupBox("批量处理配置")
        batch_config_layout = QGridLayout()
        
        batch_config_layout.addWidget(QLabel("采样模式:"), 0, 0)
        self.batch_patterns = {}
        patterns = get_sampling_patterns()
        for i, pattern in enumerate(patterns.keys()):
            cb = QCheckBox(pattern)
            cb.setChecked(i < 2)
            self.batch_patterns[pattern] = cb
            batch_config_layout.addWidget(cb, i // 2, i % 2 + 1)
        
        batch_config_layout.addWidget(QLabel("重建方法:"), 2, 0)
        self.batch_methods = {}
        methods = get_reconstruction_methods()
        for i, method in enumerate(['zero_filled', 'tv', 'cs_mri_fista']):
            cb = QCheckBox(method)
            cb.setChecked(True)
            self.batch_methods[method] = cb
            batch_config_layout.addWidget(cb, 3 + i // 2, i % 2 + 1)
        
        batch_config_group.setLayout(batch_config_layout)
        layout.addWidget(batch_config_group)
        
        layout.addStretch(1)
        
        return panel
    
    def update_wavelet_combo(self):
        family = self.wavelet_family_combo.currentText()
        families = get_wavelet_families()
        self.wavelet_combo.clear()
        if family in families:
            self.wavelet_combo.addItems(families[family])
            if family == 'Daubechies':
                self.wavelet_combo.setCurrentText('db4')
            else:
                self.wavelet_combo.setCurrentText('sym4')
    
    def create_display_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        self.phantom_canvas = ImageCanvas(width=3, height=3)
        self.mask_canvas = ImageCanvas(width=3, height=3)
        self.recon_canvas = ImageCanvas(width=3, height=3)
        self.error_canvas = ImageCanvas(width=3, height=3)
        
        self.kspace_canvas = ImageCanvas(width=3, height=3)
        self.zf_canvas = ImageCanvas(width=3, height=3)
        
        display_layout = QGridLayout()
        display_layout.addWidget(self.phantom_canvas, 0, 0)
        display_layout.addWidget(self.mask_canvas, 0, 1)
        display_layout.addWidget(self.kspace_canvas, 0, 2)
        
        display_layout.addWidget(self.zf_canvas, 1, 0)
        display_layout.addWidget(self.recon_canvas, 1, 1)
        display_layout.addWidget(self.error_canvas, 1, 2)
        
        layout.addLayout(display_layout)
        
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(4)
        self.metrics_table.setHorizontalHeaderLabels(['指标', '值', '单位', '说明'])
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.metrics_table.setMinimumHeight(150)
        layout.addWidget(self.metrics_table)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        return panel
    
    def run_reconstruction(self):
        if self.worker is not None and self.worker.isRunning():
            return
        
        params = {
            'size': self.size_spin.value(),
            'pattern': self.pattern_combo.currentText(),
            'method': self.method_combo.currentText(),
            'acceleration': self.accel_spin.value(),
            'wavelet': self.wavelet_combo.currentText(),
            'wavelet_level': self.wavelet_level_spin.value(),
            'snr_db': self.snr_spin.value(),
            'use_sense': self.sense_check.isChecked(),
            'num_iter': self.iter_spin.value(),
            'use_cycle_spinning': self.cycle_spin_check.isChecked(),
            'num_cycle_shifts': self.cycle_shifts_spin.value(),
            'use_density_compensation': self.density_comp_check.isChecked(),
            'auto_align': self.align_check.isChecked(),
            'denoiser_type': self.denoiser_combo.currentText(),
            'rho': self.rho_spin.value(),
            'dynamic_mode': self.dynamic_check.isChecked(),
            'num_frames': self.num_frames_spin.value(),
            'motion_type': self.motion_combo.currentText(),
            'lambda_lr': self.lambda_lr_spin.value(),
            'lambda_sp': self.lambda_sp_spin.value(),
        }
        
        if params['method'] == 'tv':
            params['lambda_tv'] = self.lambda_spin.value()
        elif params['method'] in ['cs_mri_ist', 'cs_mri_fista']:
            params['lambda_csmri'] = self.lambda_spin.value()
        elif params['method'] == 'pnp_dncnn':
            params['sigma_denoise'] = self.lambda_spin.value()
        elif params['method'] in ['kt_slr', 'kt_focuss', 'temporal_low_rank']:
            params['dynamic_mode'] = True
            if params['method'] == 'kt_slr':
                params['lambda_lr'] = self.lambda_lr_spin.value()
                params['lambda_sp'] = self.lambda_sp_spin.value()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.run_button.setEnabled(False)
        self.batch_button.setEnabled(False)
        
        self.worker = ReconstructionWorker(params)
        self.worker.progress.connect(self.update_progress)
        self.worker.message.connect(self.update_log)
        self.worker.finished.connect(self.reconstruction_finished)
        self.worker.start()
    
    def run_batch(self):
        if self.batch_worker is not None and self.batch_worker.isRunning():
            return
        
        patterns = [p for p, cb in self.batch_patterns.items() if cb.isChecked()]
        methods = [m for m, cb in self.batch_methods.items() if cb.isChecked()]
        
        if not patterns or not methods:
            self.update_log("请至少选择一种采样模式和一种重建方法！")
            return
        
        params = {
            'size': self.size_spin.value(),
            'patterns': patterns,
            'methods': methods,
            'acceleration': self.accel_spin.value(),
            'wavelet': self.wavelet_combo.currentText(),
            'wavelet_level': self.wavelet_level_spin.value(),
            'snr_db': self.snr_spin.value(),
            'use_cycle_spinning': self.cycle_spin_check.isChecked(),
            'num_cycle_shifts': self.cycle_shifts_spin.value(),
            'use_density_compensation': self.density_comp_check.isChecked(),
            'auto_align': self.align_check.isChecked(),
        }
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.run_button.setEnabled(False)
        self.batch_button.setEnabled(False)
        
        self.batch_worker = BatchWorker(params)
        self.batch_worker.progress.connect(self.update_progress)
        self.batch_worker.message.connect(self.update_log)
        self.batch_worker.finished.connect(self.batch_finished)
        self.batch_worker.start()
    
    def update_progress(self, value: int):
        self.progress_bar.setValue(value)
        self.statusBar().showMessage(f"处理中... {value}%")
    
    def _toggle_dynamic(self, state: int):
        """Toggle dynamic MRI mode controls."""
        enabled = state == Qt.Checked
        self.num_frames_spin.setEnabled(enabled)
        self.motion_combo.setEnabled(enabled)
        self.lambda_lr_spin.setEnabled(enabled)
        self.lambda_sp_spin.setEnabled(enabled)
    
    def update_log(self, message: str):
        self.log_text.append(message)
        self.statusBar().showMessage(message)
    
    def reconstruction_finished(self, result: Dict):
        self.run_button.setEnabled(True)
        self.batch_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if 'error' in result:
            self.update_log(f"错误: {result['error']}")
            return
        
        self.current_result = result
        
        phantom = result['phantom']
        mask = result['mask']
        kspace_und = result['kspace_und']
        zf_recon = result['zf_recon']
        recon = result['recon']
        err_map = result['error_map']
        metrics = result['metrics']
        
        kspace_display = kspace_und if kspace_und.ndim == 2 else np.log(np.abs(kspace_und[0]) + 1)
        if kspace_und.ndim == 2:
            kspace_display = np.log(np.abs(kspace_display) + 1)
        
        self.phantom_canvas.update_image(phantom, "Shepp-Logan Phantom", vmin=0, vmax=1)
        self.mask_canvas.update_image(mask, f"采样模式 ({result['sampling_rate']*100:.1f}%)", cmap='binary')
        self.kspace_canvas.update_image(kspace_display, "欠采样k空间 (log)", cmap='viridis')
        
        self.zf_canvas.update_image(zf_recon, "零填充重建", vmin=0, vmax=1)
        self.recon_canvas.update_image(recon, f"{self.method_combo.currentText()} 重建", vmin=0, vmax=1)
        self.error_canvas.update_image(err_map, "误差图", cmap='hot', vmin=0, vmax=1)
        
        self.update_metrics_table(metrics, result['sampling_rate'])
    
    def update_metrics_table(self, metrics: Dict, sampling_rate: float):
        self.metrics_table.setRowCount(0)
        
        metric_info = [
            ('PSNR', metrics['PSNR'], 'dB', '峰值信噪比'),
            ('SSIM', metrics['SSIM'], '', '结构相似性指数'),
            ('NMSE', metrics['NMSE'], '', '归一化均方误差'),
            ('采样率', sampling_rate * 100, '%', '实际采样比例'),
        ]
        
        for i, (name, value, unit, desc) in enumerate(metric_info):
            self.metrics_table.insertRow(i)
            self.metrics_table.setItem(i, 0, QTableWidgetItem(name))
            self.metrics_table.setItem(i, 1, QTableWidgetItem(f"{value:.4f}" if isinstance(value, float) else str(value)))
            self.metrics_table.setItem(i, 2, QTableWidgetItem(unit))
            self.metrics_table.setItem(i, 3, QTableWidgetItem(desc))
    
    def batch_finished(self, result: Dict):
        self.run_button.setEnabled(True)
        self.batch_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if 'error' in result:
            self.update_log(f"错误: {result['error']}")
            return
        
        self.show_batch_results(result)
    
    def show_batch_results(self, result: Dict):
        phantom = result['phantom']
        batch_results = result['results']
        
        dialog = QWidget()
        dialog.setWindowTitle("批量处理结果对比")
        dialog.resize(1200, 800)
        
        layout = QVBoxLayout(dialog)
        
        comparison_table = QTableWidget()
        comparison_table.setColumnCount(5)
        comparison_table.setHorizontalHeaderLabels(['采样模式', '重建方法', 'PSNR (dB)', 'SSIM', '采样率'])
        comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        for i, res in enumerate(batch_results):
            comparison_table.insertRow(i)
            comparison_table.setItem(i, 0, QTableWidgetItem(res['pattern']))
            comparison_table.setItem(i, 1, QTableWidgetItem(res['method']))
            comparison_table.setItem(i, 2, QTableWidgetItem(f"{res['metrics']['PSNR']:.2f}"))
            comparison_table.setItem(i, 3, QTableWidgetItem(f"{res['metrics']['SSIM']:.4f}"))
            comparison_table.setItem(i, 4, QTableWidgetItem(f"{res['sampling_rate']*100:.1f}%"))
        
        comparison_table.setMinimumHeight(200)
        layout.addWidget(comparison_table)
        
        num_results = len(batch_results)
        ncols = min(4, num_results)
        nrows = (num_results + ncols - 1) // ncols + 1
        
        fig = Figure(figsize=(12, 3 * nrows))
        
        ax = fig.add_subplot(nrows, ncols, 1)
        ax.imshow(phantom, cmap='gray', vmin=0, vmax=1)
        ax.set_title("参考 Phantom", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
        
        for i, res in enumerate(batch_results):
            ax = fig.add_subplot(nrows, ncols, i + ncols + 1)
            ax.imshow(res['recon'], cmap='gray', vmin=0, vmax=1)
            psnr = res['metrics']['PSNR']
            ssim = res['metrics']['SSIM']
            ax.set_title(f"{res['pattern']}+{res['method']}\nPSNR:{psnr:.1f} SSIM:{ssim:.3f}", fontsize=8)
            ax.set_xticks([])
            ax.set_yticks([])
        
        fig.tight_layout()
        
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)
        
        dialog.setLayout(layout)
        dialog.show()
        self.batch_dialog = dialog
    
    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.terminate()
        if self.batch_worker is not None:
            self.batch_worker.terminate()
        event.accept()


def main():
    app = QApplication(sys.argv)
    
    app.setStyle('Fusion')
    
    window = MRISimGUI()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
