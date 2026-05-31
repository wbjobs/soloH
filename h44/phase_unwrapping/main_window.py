"""
PyQt5主界面模块
整合所有功能的图形用户界面
"""

import sys
import os
import numpy as np
from typing import Optional, Dict, Any
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QPushButton, QLabel, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QFileDialog, QMessageBox,
    QProgressDialog, QStatusBar, QDockWidget, QListWidget, QListWidgetItem,
    QGridLayout, QFormLayout, QPlainTextEdit, QSlider, QLineEdit, QInputDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon

from .data_io import read_interferogram, write_envi, write_geotiff
from .unwrapping_algorithms import PhaseUnwrapper, detect_residues
from .quality_and_snaphu import QualityMapGenerator, get_snaphu_unwrapper
from .mask_processing import MaskProcessor, AutoMaskGenerator
from .advanced_processing import DLPhaseUnwrapper, MultiBaselineUnwrapper, SBASInverter
from .visualization import (
    ImageCanvas, ProfilePlotCanvas, Surface3DCanvas,
    ResiduePlotCanvas, create_navigation_toolbar, PhaseColormap
)


class UnwrappingWorker(QThread):
    """
    相位解缠工作线程
    用于在后台执行耗时的解缠计算
    """

    progress_signal = pyqtSignal(str, int)
    finished_signal = pyqtSignal(np.ndarray, dict)
    error_signal = pyqtSignal(str)

    def __init__(self, algorithm: str, wrapped_phase: np.ndarray,
                 mask: Optional[np.ndarray] = None,
                 quality_map: Optional[np.ndarray] = None,
                 snaphu_params: Optional[dict] = None,
                 remove_flat: bool = True,
                 flat_phase_degree: int = 1,
                 use_region_growing: bool = False,
                 weight_power: float = 3.0,
                 **kwargs):
        super().__init__()
        self.algorithm = algorithm
        self.wrapped_phase = wrapped_phase
        self.mask = mask
        self.quality_map = quality_map
        self.snaphu_params = snaphu_params or {}
        self.remove_flat = remove_flat
        self.flat_phase_degree = flat_phase_degree
        self.use_region_growing = use_region_growing
        self.weight_power = weight_power
        self.kwargs = kwargs

    def run(self):
        try:
            self.progress_signal.emit('开始相位解缠...', 10)

            if self.algorithm == 'snaphu':
                self.progress_signal.emit('调用SNAPHU...', 30)
                snaphu = get_snaphu_unwrapper()
                unwrapped, info = snaphu.unwrap(
                    self.wrapped_phase,
                    mask=self.mask,
                    quality_map=self.quality_map,
                    remove_flat=self.remove_flat,
                    flat_phase_degree=self.flat_phase_degree,
                    use_region_growing=self.use_region_growing,
                    weight_power=self.weight_power,
                    **self.snaphu_params
                )
            else:
                self.progress_signal.emit(f'执行{self.algorithm}算法...', 30)
                unwrapper = PhaseUnwrapper(
                    self.algorithm,
                    remove_flat=self.remove_flat,
                    flat_phase_degree=self.flat_phase_degree,
                    use_region_growing=self.use_region_growing,
                    weight_power=self.weight_power,
                    **self.kwargs
                )
                unwrapped, info = unwrapper.unwrap(
                    self.wrapped_phase,
                    mask=self.mask,
                    quality_map=self.quality_map
                )

            self.progress_signal.emit('解缠完成', 100)
            self.finished_signal.emit(unwrapped, info)

        except Exception as e:
            self.error_signal.emit(str(e))


class AdvancedProcessingWorker(QThread):
    """
    高级处理工作线程
    用于深度学习分阶段解缠、多基线联合解缠、SBAS时序反演
    """

    progress_signal = pyqtSignal(str, int)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, task_type: str, **kwargs):
        super().__init__()
        self.task_type = task_type
        self.kwargs = kwargs

    def run(self):
        try:
            if self.task_type == 'dl_unwrap':
                self._run_dl_unwrap()
            elif self.task_type == 'multi_baseline':
                self._run_multi_baseline()
            elif self.task_type == 'sbas':
                self._run_sbas()
            else:
                self.error_signal.emit(f'未知任务类型: {self.task_type}')
        except Exception as e:
            self.error_signal.emit(str(e))

    def _run_dl_unwrap(self):
        self.progress_signal.emit('开始分阶段解缠...', 10)

        unwrapper = DLPhaseUnwrapper(
            high_threshold=self.kwargs.get('high_threshold', 0.7),
            mid_threshold=self.kwargs.get('mid_threshold', 0.4),
            low_threshold=self.kwargs.get('low_threshold', 0.15),
            num_stages=self.kwargs.get('num_stages', 4),
            use_multiscale=self.kwargs.get('use_multiscale', True)
        )

        unwrapped, info = unwrapper.unwrap(
            self.kwargs['wrapped_phase'],
            mask=self.kwargs.get('mask'),
            quality_map=self.kwargs.get('quality_map')
        )

        self.progress_signal.emit('分阶段解缠完成', 100)
        self.finished_signal.emit({
            'unwrapped': unwrapped,
            'info': info,
            'task': 'dl_unwrap'
        })

    def _run_multi_baseline(self):
        self.progress_signal.emit('开始多基线联合解缠...', 10)

        unwrapper = MultiBaselineUnwrapper(
            use_baseline_weighting=self.kwargs.get('use_baseline_weighting', True),
            combine_method=self.kwargs.get('combine_method', 'weighted_average')
        )

        unwrapped, info = unwrapper.unwrap(
            self.kwargs['wrapped_phases'],
            self.kwargs['perpendicular_baselines'],
            masks=self.kwargs.get('masks'),
            quality_maps=self.kwargs.get('quality_maps')
        )

        self.progress_signal.emit('多基线联合解缠完成', 100)
        self.finished_signal.emit({
            'unwrapped': unwrapped,
            'info': info,
            'task': 'multi_baseline'
        })

    def _run_sbas(self):
        self.progress_signal.emit('开始SBAS时序反演...', 10)

        inverter = SBASInverter(
            wavelength=self.kwargs.get('wavelength', 0.056),
            max_temporal_baseline=self.kwargs.get('max_temporal_baseline'),
            max_perpendicular_baseline=self.kwargs.get('max_perpendicular_baseline'),
            ref_pixel=self.kwargs.get('ref_pixel')
        )

        results = inverter.invert(
            self.kwargs['unwrapped_phases'],
            self.kwargs['acquisition_dates'],
            self.kwargs['perpendicular_baselines'],
            masks=self.kwargs.get('masks'),
            quality_maps=self.kwargs.get('quality_maps')
        )

        self.progress_signal.emit('SBAS时序反演完成', 100)
        results['task'] = 'sbas'
        self.finished_signal.emit(results)


class MainWindow(QMainWindow):
    """
    相位解缠应用主窗口
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle('InSAR相位解缠处理系统')
        self.setGeometry(100, 100, 1400, 900)

        self.wrapped_phase: Optional[np.ndarray] = None
        self.unwrapped_phase: Optional[np.ndarray] = None
        self.quality_map: Optional[np.ndarray] = None
        self.mask: Optional[np.ndarray] = None
        self.mask_results: Optional[Dict[str, Any]] = None
        self.unwrap_info: Optional[Dict[str, Any]] = None
        self.metadata: Optional[Dict[str, Any]] = None
        self.current_file_path: Optional[str] = None

        self.worker: Optional[UnwrappingWorker] = None
        self.advanced_worker: Optional[AdvancedProcessingWorker] = None

        self.velocity: Optional[np.ndarray] = None
        self.velocity_std: Optional[np.ndarray] = None
        self.time_series: Optional[np.ndarray] = None
        self.sbas_results: Optional[Dict[str, Any]] = None

        self.wrapped_phases: List[np.ndarray] = []
        self.perpendicular_baselines: Optional[np.ndarray] = None
        self.acquisition_dates: Optional[np.ndarray] = None

        self._init_ui()
        self._init_menu()
        self._init_toolbar()

    def _init_ui(self):
        """初始化用户界面"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage('就绪')

    def _create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        file_group = self._create_file_group()
        layout.addWidget(file_group)

        algo_group = self._create_algorithm_group()
        layout.addWidget(algo_group)

        advanced_group = self._create_advanced_group()
        layout.addWidget(advanced_group)

        mask_group = self._create_mask_group()
        layout.addWidget(mask_group)

        quality_group = self._create_quality_group()
        layout.addWidget(quality_group)

        export_group = self._create_export_group()
        layout.addWidget(export_group)

        layout.addStretch(1)

        return panel

    def _create_file_group(self) -> QGroupBox:
        """创建文件操作组"""
        group = QGroupBox('文件操作')
        layout = QVBoxLayout(group)

        btn_load = QPushButton('加载干涉图 (GeoTIFF)')
        btn_load.clicked.connect(self._load_interferogram)
        layout.addWidget(btn_load)

        self.lbl_file_info = QLabel('未加载文件')
        self.lbl_file_info.setWordWrap(True)
        layout.addWidget(self.lbl_file_info)

        return group

    def _create_algorithm_group(self) -> QGroupBox:
        """创建算法选择组"""
        group = QGroupBox('相位解缠算法')
        layout = QFormLayout(group)

        self.cmb_algorithm = QComboBox()
        self.cmb_algorithm.addItems([
            '分支切割法',
            '最小二乘法(无权重)',
            '最小二乘法(加权)',
            'SNAPHU (统计耗费网络流)',
            'DL分阶段解缠(高噪声)',
            '多基线联合解缠'
        ])
        layout.addRow('选择算法:', self.cmb_algorithm)

        self.spin_branch_length = QSpinBox()
        self.spin_branch_length.setRange(10, 1000)
        self.spin_branch_length.setValue(100)
        layout.addRow('最大分支长度:', self.spin_branch_length)

        self.cmb_snaphu_mode = QComboBox()
        self.cmb_snaphu_mode.addItems(['DEFO', 'TOPO', 'SMOOTH', 'NOSTATCOSTS'])
        layout.addRow('SNAPHU模式:', self.cmb_snaphu_mode)

        self.chk_use_quality = QCheckBox('使用质量图加权')
        self.chk_use_quality.setChecked(True)
        layout.addRow(self.chk_use_quality)

        self.chk_remove_flat = QCheckBox('去除平地相位')
        self.chk_remove_flat.setChecked(True)
        layout.addRow(self.chk_remove_flat)

        self.cmb_flat_degree = QComboBox()
        self.cmb_flat_degree.addItems(['1阶(线性)', '2阶(二次)'])
        self.cmb_flat_degree.setCurrentIndex(0)
        layout.addRow('平地相位阶数:', self.cmb_flat_degree)

        self.chk_region_growing = QCheckBox('质量引导区域增长(防错误扩散)')
        self.chk_region_growing.setChecked(False)
        layout.addRow(self.chk_region_growing)

        layout.addRow(QLabel('<b>权重设置:</b>'))

        self.spin_weight_power = QDoubleSpinBox()
        self.spin_weight_power.setRange(1.0, 6.0)
        self.spin_weight_power.setSingleStep(0.5)
        self.spin_weight_power.setValue(3.0)
        layout.addRow('权重幂指数:', self.spin_weight_power)

        btn_unwrap = QPushButton('执行相位解缠')
        btn_unwrap.clicked.connect(self._run_unwrapping)
        layout.addRow(btn_unwrap)

        return group

    def _create_advanced_group(self) -> QGroupBox:
        """创建高级处理组"""
        group = QGroupBox('高级处理')
        layout = QFormLayout(group)

        layout.addRow(QLabel('<b>分阶段解缠设置:</b>'))

        self.spin_high_threshold = QDoubleSpinBox()
        self.spin_high_threshold.setRange(0.5, 0.95)
        self.spin_high_threshold.setSingleStep(0.05)
        self.spin_high_threshold.setValue(0.7)
        layout.addRow('高质量阈值:', self.spin_high_threshold)

        self.spin_mid_threshold = QDoubleSpinBox()
        self.spin_mid_threshold.setRange(0.2, 0.6)
        self.spin_mid_threshold.setSingleStep(0.05)
        self.spin_mid_threshold.setValue(0.4)
        layout.addRow('中等质量阈值:', self.spin_mid_threshold)

        self.spin_low_threshold = QDoubleSpinBox()
        self.spin_low_threshold.setRange(0.05, 0.3)
        self.spin_low_threshold.setSingleStep(0.05)
        self.spin_low_threshold.setValue(0.15)
        layout.addRow('低质量阈值:', self.spin_low_threshold)

        self.chk_use_multiscale = QCheckBox('多尺度策略')
        self.chk_use_multiscale.setChecked(True)
        layout.addRow(self.chk_use_multiscale)

        layout.addRow(QLabel('<b>多基线设置:</b>'))

        self.cmb_combine_method = QComboBox()
        self.cmb_combine_method.addItems([
            '加权平均',
            '质量最优',
            '顺序解缠'
        ])
        layout.addRow('组合方法:', self.cmb_combine_method)

        self.chk_baseline_weighting = QCheckBox('基线长度加权')
        self.chk_baseline_weighting.setChecked(True)
        layout.addRow(self.chk_baseline_weighting)

        btn_load_multi = QPushButton('加载多基线数据...')
        btn_load_multi.clicked.connect(self._load_multi_baseline_data)
        layout.addRow(btn_load_multi)

        layout.addRow(QLabel('<b>SBAS时序反演:</b>'))

        self.spin_wavelength = QDoubleSpinBox()
        self.spin_wavelength.setRange(0.01, 1.0)
        self.spin_wavelength.setSingleStep(0.001)
        self.spin_wavelength.setValue(0.056)
        layout.addRow('雷达波长(米):', self.spin_wavelength)

        self.spin_max_temp_baseline = QSpinBox()
        self.spin_max_temp_baseline.setRange(0, 365)
        self.spin_max_temp_baseline.setValue(0)
        self.spin_max_temp_baseline.setSpecialValueText('不限制')
        layout.addRow('最大时间基线(天):', self.spin_max_temp_baseline)

        self.spin_max_perp_baseline = QSpinBox()
        self.spin_max_perp_baseline.setRange(0, 500)
        self.spin_max_perp_baseline.setValue(0)
        self.spin_max_perp_baseline.setSpecialValueText('不限制')
        layout.addRow('最大垂直基线(米):', self.spin_max_perp_baseline)

        btn_load_sbas = QPushButton('加载SBAS数据...')
        btn_load_sbas.clicked.connect(self._load_sbas_data)
        layout.addRow(btn_load_sbas)

        btn_run_sbas = QPushButton('执行SBAS时序反演')
        btn_run_sbas.clicked.connect(self._run_sbas_inversion)
        layout.addRow(btn_run_sbas)

        self.lbl_advanced_info = QLabel('')
        self.lbl_advanced_info.setWordWrap(True)
        layout.addRow(self.lbl_advanced_info)

        return group

    def _create_mask_group(self) -> QGroupBox:
        """创建掩膜处理组"""
        group = QGroupBox('掩膜处理')
        layout = QFormLayout(group)

        self.chk_enable_water = QCheckBox('水体检测')
        self.chk_enable_water.setChecked(True)
        layout.addRow(self.chk_enable_water)

        self.chk_enable_shadow = QCheckBox('阴影检测')
        self.chk_enable_shadow.setChecked(True)
        layout.addRow(self.chk_enable_shadow)

        self.chk_enable_lowcoh = QCheckBox('低相干检测')
        self.chk_enable_lowcoh.setChecked(True)
        layout.addRow(self.chk_enable_lowcoh)

        self.spin_coh_threshold = QDoubleSpinBox()
        self.spin_coh_threshold.setRange(0, 1)
        self.spin_coh_threshold.setSingleStep(0.05)
        self.spin_coh_threshold.setValue(0.3)
        layout.addRow('相干阈值:', self.spin_coh_threshold)

        self.spin_dilation = QSpinBox()
        self.spin_dilation.setRange(0, 20)
        self.spin_dilation.setValue(2)
        layout.addRow('膨胀半径:', self.spin_dilation)

        btn_generate_mask = QPushButton('自动生成掩膜')
        btn_generate_mask.clicked.connect(self._generate_mask)
        layout.addRow(btn_generate_mask)

        btn_load_mask = QPushButton('加载外部掩膜')
        btn_load_mask.clicked.connect(self._load_mask)
        layout.addRow(btn_load_mask)

        self.chk_apply_mask = QCheckBox('应用掩膜到解缠')
        self.chk_apply_mask.setChecked(True)
        layout.addRow(self.chk_apply_mask)

        self.lbl_mask_stats = QLabel('')
        self.lbl_mask_stats.setWordWrap(True)
        layout.addRow(self.lbl_mask_stats)

        return group

    def _create_quality_group(self) -> QGroupBox:
        """创建质量图生成组"""
        group = QGroupBox('质量图生成')
        layout = QFormLayout(group)

        self.cmb_quality_method = QComboBox()
        self.cmb_quality_method.addItems([
            '伪相关系数',
            '相位导数方差',
            '最大相位梯度'
        ])
        layout.addRow('质量图方法:', self.cmb_quality_method)

        self.spin_window_size = QSpinBox()
        self.spin_window_size.setRange(3, 21)
        self.spin_window_size.setSingleStep(2)
        self.spin_window_size.setValue(5)
        layout.addRow('窗口大小:', self.spin_window_size)

        btn_generate_quality = QPushButton('生成质量图')
        btn_generate_quality.clicked.connect(self._generate_quality_map)
        layout.addRow(btn_generate_quality)

        return group

    def _create_export_group(self) -> QGroupBox:
        """创建导出组"""
        group = QGroupBox('结果导出')
        layout = QFormLayout(group)

        self.cmb_export_format = QComboBox()
        self.cmb_export_format.addItems(['ENVI格式', 'GeoTIFF格式'])
        layout.addRow('导出格式:', self.cmb_export_format)

        self.chk_export_unwrapped = QCheckBox('解缠相位')
        self.chk_export_unwrapped.setChecked(True)
        layout.addRow(self.chk_export_unwrapped)

        self.chk_export_wrapped = QCheckBox('包裹相位')
        self.chk_export_wrapped.setChecked(False)
        layout.addRow(self.chk_export_wrapped)

        self.chk_export_quality = QCheckBox('质量图')
        self.chk_export_quality.setChecked(True)
        layout.addRow(self.chk_export_quality)

        self.chk_export_mask = QCheckBox('掩膜')
        self.chk_export_mask.setChecked(True)
        layout.addRow(self.chk_export_mask)

        self.chk_export_error = QCheckBox('误差估计')
        self.chk_export_error.setChecked(True)
        layout.addRow(self.chk_export_error)

        self.chk_export_flat = QCheckBox('平地相位')
        self.chk_export_flat.setChecked(True)
        layout.addRow(self.chk_export_flat)

        btn_export = QPushButton('导出结果')
        btn_export.clicked.connect(self._export_results)
        layout.addRow(btn_export)

        return group

    def _create_right_panel(self) -> QWidget:
        """创建右侧显示面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.tab_widget = QTabWidget()

        self.tab_image = self._create_image_tab()
        self.tab_profile = self._create_profile_tab()
        self.tab_3d = self._create_3d_tab()
        self.tab_stats = self._create_stats_tab()
        self.tab_info = self._create_info_tab()

        self.tab_widget.addTab(self.tab_image, '图像显示')
        self.tab_widget.addTab(self.tab_profile, '相位剖面')
        self.tab_widget.addTab(self.tab_3d, '3D表面')
        self.tab_widget.addTab(self.tab_stats, '统计分析')
        self.tab_widget.addTab(self.tab_info, '信息日志')

        layout.addWidget(self.tab_widget)

        return panel

    def _create_image_tab(self) -> QWidget:
        """创建图像显示标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        control_layout = QHBoxLayout()

        control_layout.addWidget(QLabel('显示图层:'))
        self.cmb_display_layer = QComboBox()
        self.cmb_display_layer.addItems([
            '包裹相位',
            '解缠相位',
            '质量图',
            '掩膜',
            '误差估计',
            '估计的平地相位',
            '形变速率(mm/年)',
            '形变速率标准差'
        ])
        self.cmb_display_layer.currentIndexChanged.connect(self._update_display)
        control_layout.addWidget(self.cmb_display_layer)

        self.chk_show_residues = QCheckBox('显示残差点')
        self.chk_show_residues.stateChanged.connect(self._update_display)
        control_layout.addWidget(self.chk_show_residues)

        self.chk_show_mask = QCheckBox('显示掩膜叠加')
        self.chk_show_mask.stateChanged.connect(self._update_display)
        control_layout.addWidget(self.chk_show_mask)

        btn_draw_profile = QPushButton('绘制剖面线')
        btn_draw_profile.setCheckable(True)
        btn_draw_profile.toggled.connect(self._toggle_profile_drawing)
        control_layout.addWidget(btn_draw_profile)

        btn_refresh = QPushButton('刷新显示')
        btn_refresh.clicked.connect(self._update_display)
        control_layout.addWidget(btn_refresh)

        control_layout.addStretch(1)
        layout.addLayout(control_layout)

        self.image_canvas = ImageCanvas()
        self.image_canvas.data_changed_callback = self._on_canvas_event
        toolbar = create_navigation_toolbar(self.image_canvas, widget)
        layout.addWidget(toolbar)
        layout.addWidget(self.image_canvas)

        return widget

    def _create_profile_tab(self) -> QWidget:
        """创建剖面线标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        control_layout = QHBoxLayout()

        self.chk_compare_profile = QCheckBox('比较包裹/解缠相位')
        self.chk_compare_profile.setChecked(True)
        control_layout.addWidget(self.chk_compare_profile)

        btn_clear_profile = QPushButton('清除剖面')
        btn_clear_profile.clicked.connect(self._clear_profile)
        control_layout.addWidget(btn_clear_profile)

        control_layout.addStretch(1)
        layout.addLayout(control_layout)

        self.profile_canvas = ProfilePlotCanvas()
        layout.addWidget(self.profile_canvas)

        return widget

    def _create_3d_tab(self) -> QWidget:
        """创建3D表面标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        control_layout = QHBoxLayout()

        control_layout.addWidget(QLabel('显示数据:'))
        self.cmb_3d_data = QComboBox()
        self.cmb_3d_data.addItems(['解缠相位', '包裹相位', '质量图'])
        control_layout.addWidget(self.cmb_3d_data)

        control_layout.addWidget(QLabel('下采样:'))
        self.spin_downsample = QSpinBox()
        self.spin_downsample.setRange(1, 10)
        self.spin_downsample.setValue(2)
        control_layout.addWidget(self.spin_downsample)

        self.chk_wireframe = QCheckBox('网格模式')
        control_layout.addWidget(self.chk_wireframe)

        btn_plot_3d = QPushButton('绘制3D表面')
        btn_plot_3d.clicked.connect(self._plot_3d_surface)
        control_layout.addWidget(btn_plot_3d)

        btn_clear_3d = QPushButton('清除3D图')
        btn_clear_3d.clicked.connect(lambda: self.surface_canvas.clear())
        control_layout.addWidget(btn_clear_3d)

        control_layout.addStretch(1)
        layout.addLayout(control_layout)

        self.surface_canvas = Surface3DCanvas()
        layout.addWidget(self.surface_canvas)

        return widget

    def _create_stats_tab(self) -> QWidget:
        """创建统计分析标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        control_layout = QHBoxLayout()

        btn_plot_residues = QPushButton('残差点统计')
        btn_plot_residues.clicked.connect(self._plot_residue_stats)
        control_layout.addWidget(btn_plot_residues)

        btn_plot_error = QPushButton('误差分布')
        btn_plot_error.clicked.connect(self._plot_error_distribution)
        control_layout.addWidget(btn_plot_error)

        control_layout.addStretch(1)
        layout.addLayout(control_layout)

        self.stats_canvas = ResiduePlotCanvas()
        layout.addWidget(self.stats_canvas)

        return widget

    def _create_info_tab(self) -> QWidget:
        """创建信息日志标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.txt_info = QPlainTextEdit()
        self.txt_info.setReadOnly(True)
        layout.addWidget(self.txt_info)

        return widget

    def _init_menu(self):
        """初始化菜单栏"""
        menubar = self.menuBar()

        file_menu = menubar.addMenu('文件')

        load_action = file_menu.addAction('加载干涉图')
        load_action.triggered.connect(self._load_interferogram)

        load_mask_action = file_menu.addAction('加载掩膜')
        load_mask_action.triggered.connect(self._load_mask)

        file_menu.addSeparator()

        export_action = file_menu.addAction('导出结果')
        export_action.triggered.connect(self._export_results)

        file_menu.addSeparator()

        exit_action = file_menu.addAction('退出')
        exit_action.triggered.connect(self.close)

        view_menu = menubar.addMenu('视图')

        refresh_action = view_menu.addAction('刷新显示')
        refresh_action.triggered.connect(self._update_display)

        help_menu = menubar.addMenu('帮助')

        about_action = help_menu.addAction('关于')
        about_action.triggered.connect(self._show_about)

    def _init_toolbar(self):
        """初始化工具栏"""
        toolbar = self.addToolBar('主工具栏')

        load_icon = QIcon.fromTheme('document-open')
        load_action = toolbar.addAction(load_icon, '加载')
        load_action.triggered.connect(self._load_interferogram)

        process_icon = QIcon.fromTheme('system-run')
        process_action = toolbar.addAction(process_icon, '解缠')
        process_action.triggered.connect(self._run_unwrapping)

        save_icon = QIcon.fromTheme('document-save')
        save_action = toolbar.addAction(save_icon, '导出')
        save_action.triggered.connect(self._export_results)

    def _append_log(self, message: str):
        """添加日志信息"""
        self.txt_info.appendPlainText(message)
        self.txt_info.verticalScrollBar().setValue(
            self.txt_info.verticalScrollBar().maximum()
        )

    def _load_interferogram(self):
        """加载干涉图文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            '选择干涉图文件',
            '',
            'GeoTIFF文件 (*.tif *.tiff *.gtif);;ENVI文件 (*.dat *.img);;所有文件 (*.*)'
        )

        if not file_path:
            return

        try:
            self.statusBar().showMessage(f'正在加载: {file_path}')
            QApplication.processEvents()

            data, metadata = read_interferogram(file_path)

            self.wrapped_phase = data
            self.metadata = metadata
            self.current_file_path = file_path

            min_val = np.nanmin(data)
            max_val = np.nanmax(data)
            self._append_log(f'成功加载: {file_path}')
            self._append_log(f'数据尺寸: {data.shape[0]} x {data.shape[1]}')
            self._append_log(f'数值范围: [{min_val:.4f}, {max_val:.4f}]')

            if abs(min_val) <= np.pi and abs(max_val) <= np.pi:
                self._append_log('检测到相位范围在[-π, π]，确认是包裹相位')
            else:
                self._append_log('警告: 相位范围超出[-π, π]，可能不是包裹相位')

            self.lbl_file_info.setText(
                f'文件: {os.path.basename(file_path)}\n'
                f'尺寸: {data.shape[0]}x{data.shape[1]}'
            )

            self.mask = MaskProcessor.create_valid_mask(data, metadata.get('nodata', None))

            self._generate_quality_map()
            self._update_display()

            self.statusBar().showMessage('加载完成')

        except Exception as e:
            QMessageBox.critical(self, '错误', f'加载失败: {str(e)}')
            self._append_log(f'错误: {str(e)}')
            self.statusBar().showMessage('加载失败')

    def _load_mask(self):
        """加载外部掩膜文件"""
        if self.wrapped_phase is None:
            QMessageBox.warning(self, '警告', '请先加载干涉图')
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            '选择掩膜文件',
            '',
            '所有支持格式 (*.tif *.tiff *.dat *.img)'
        )

        if not file_path:
            return

        try:
            data, _ = read_interferogram(file_path)

            if data.shape != self.wrapped_phase.shape:
                QMessageBox.warning(
                    self, '警告',
                    f'掩膜尺寸 {data.shape} 与干涉图尺寸 {self.wrapped_phase.shape} 不匹配'
                )
                return

            self.mask = data.astype(bool)
            self._append_log(f'成功加载掩膜: {file_path}')

            stats = MaskProcessor.get_mask_stats(self.mask)
            self.lbl_mask_stats.setText(
                f'有效像素: {stats["valid_pixels"]}\n'
                f'掩膜比例: {stats["masked_ratio"]*100:.1f}%'
            )

            self._update_display()

        except Exception as e:
            QMessageBox.critical(self, '错误', f'加载掩膜失败: {str(e)}')

    def _generate_mask(self):
        """自动生成掩膜"""
        if self.wrapped_phase is None:
            QMessageBox.warning(self, '警告', '请先加载干涉图')
            return

        try:
            self.statusBar().showMessage('正在生成掩膜...')
            QApplication.processEvents()

            auto_mask = AutoMaskGenerator()
            valid_mask, results = auto_mask.generate(
                self.wrapped_phase,
                coherence_map=self.quality_map,
                enable_water=self.chk_enable_water.isChecked(),
                enable_shadow=self.chk_enable_shadow.isChecked(),
                enable_low_coherence=self.chk_enable_lowcoh.isChecked(),
                coherence_threshold=self.spin_coh_threshold.value(),
                dilation_radius=self.spin_dilation.value()
            )

            self.mask = valid_mask
            self.mask_results = results

            stats = MaskProcessor.get_mask_stats(self.mask)
            self.lbl_mask_stats.setText(
                f'有效像素: {stats["valid_pixels"]}\n'
                f'掩膜比例: {stats["masked_ratio"]*100:.1f}%'
            )

            self._append_log('自动掩膜生成完成')
            self._append_log(f'  水体区域: {np.sum(results["water"])} 像素')
            self._append_log(f'  阴影区域: {np.sum(results["shadow"])} 像素')
            self._append_log(f'  低相干区域: {np.sum(results["low_coherence"])} 像素')

            self._update_display()
            self.statusBar().showMessage('掩膜生成完成')

        except Exception as e:
            QMessageBox.critical(self, '错误', f'生成掩膜失败: {str(e)}')

    def _generate_quality_map(self):
        """生成质量图"""
        if self.wrapped_phase is None:
            QMessageBox.warning(self, '警告', '请先加载干涉图')
            return

        try:
            self.statusBar().showMessage('正在生成质量图...')
            QApplication.processEvents()

            method_idx = self.cmb_quality_method.currentIndex()
            window_size = self.spin_window_size.value()

            methods = [
                'pseudo_coherence',
                'phase_derivative_variance',
                'max_phase_gradient'
            ]

            self.quality_map = QualityMapGenerator.generate(
                self.wrapped_phase,
                method=methods[method_idx],
                window_size=window_size
            )

            mean_quality = np.nanmean(self.quality_map)
            self._append_log(
                f'质量图生成完成 ({self.cmb_quality_method.currentText()}), '
                f'平均质量: {mean_quality:.4f}'
            )

            self._update_display()
            self.statusBar().showMessage('质量图生成完成')

        except Exception as e:
            QMessageBox.critical(self, '错误', f'生成质量图失败: {str(e)}')

    def _run_unwrapping(self):
        """执行相位解缠"""
        if self.wrapped_phase is None:
            QMessageBox.warning(self, '警告', '请先加载干涉图')
            return

        if self.chk_use_quality.isChecked() and self.quality_map is None:
            self._generate_quality_map()

        algo_idx = self.cmb_algorithm.currentIndex()
        algorithms = [
            'branch_cut',
            'least_squares',
            'weighted_least_squares',
            'snaphu',
            'dl_stage',
            'multi_baseline'
        ]
        algorithm = algorithms[algo_idx]

        mask = None
        if self.chk_apply_mask.isChecked() and self.mask is not None:
            mask = self.mask

        quality_map = None
        if self.chk_use_quality.isChecked():
            quality_map = self.quality_map

        if algorithm == 'dl_stage':
            self._run_dl_unwrap(mask, quality_map)
            return
        elif algorithm == 'multi_baseline':
            if not self.wrapped_phases or self.perpendicular_baselines is None:
                QMessageBox.warning(self, '警告', '请先加载多基线数据')
                return
            self._run_multi_baseline_unwrap()
            return

        kwargs = {}
        if algorithm == 'branch_cut':
            kwargs['max_branch_length'] = self.spin_branch_length.value()

        snaphu_params = {}
        if algorithm == 'snaphu':
            snaphu_params['cost_mode'] = self.cmb_snaphu_mode.currentText()

        remove_flat = self.chk_remove_flat.isChecked()
        flat_degree = self.cmb_flat_degree.currentIndex() + 1
        use_region_growing = self.chk_region_growing.isChecked()
        weight_power = self.spin_weight_power.value()

        self.progress_dialog = QProgressDialog('正在执行相位解缠...', '取消', 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)

        self.worker = UnwrappingWorker(
            algorithm,
            self.wrapped_phase,
            mask=mask,
            quality_map=quality_map,
            snaphu_params=snaphu_params,
            remove_flat=remove_flat,
            flat_phase_degree=flat_degree,
            use_region_growing=use_region_growing,
            weight_power=weight_power,
            **kwargs
        )

        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_unwrap_finished)
        self.worker.error_signal.connect(self._on_unwrap_error)

        self.worker.start()
        self.progress_dialog.show()

    def _run_dl_unwrap(self, mask, quality_map):
        """运行分阶段解缠"""
        self.progress_dialog = QProgressDialog('正在执行分阶段解缠...', '取消', 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)

        self.advanced_worker = AdvancedProcessingWorker(
            'dl_unwrap',
            wrapped_phase=self.wrapped_phase,
            mask=mask,
            quality_map=quality_map,
            high_threshold=self.spin_high_threshold.value(),
            mid_threshold=self.spin_mid_threshold.value(),
            low_threshold=self.spin_low_threshold.value(),
            num_stages=4,
            use_multiscale=self.chk_use_multiscale.isChecked()
        )

        self.advanced_worker.progress_signal.connect(self._on_progress)
        self.advanced_worker.finished_signal.connect(self._on_advanced_finished)
        self.advanced_worker.error_signal.connect(self._on_advanced_error)

        self.advanced_worker.start()
        self.progress_dialog.show()

    def _run_multi_baseline_unwrap(self):
        """运行多基线联合解缠"""
        if not self.wrapped_phases:
            QMessageBox.warning(self, '警告', '请先加载多基线数据')
            return

        self.progress_dialog = QProgressDialog('正在执行多基线联合解缠...', '取消', 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)

        methods = ['weighted_average', 'quality_best', 'sequential']
        combine_method = methods[self.cmb_combine_method.currentIndex()]

        quality_maps = []
        for wp in self.wrapped_phases:
            qm = QualityMapGenerator.pseudo_coherence(wp)
            quality_maps.append(qm)

        masks = [self.mask if self.mask is not None else np.ones_like(wp, dtype=bool) for wp in self.wrapped_phases]

        self.advanced_worker = AdvancedProcessingWorker(
            'multi_baseline',
            wrapped_phases=self.wrapped_phases,
            perpendicular_baselines=self.perpendicular_baselines,
            masks=masks,
            quality_maps=quality_maps,
            use_baseline_weighting=self.chk_baseline_weighting.isChecked(),
            combine_method=combine_method
        )

        self.advanced_worker.progress_signal.connect(self._on_progress)
        self.advanced_worker.finished_signal.connect(self._on_advanced_finished)
        self.advanced_worker.error_signal.connect(self._on_advanced_error)

        self.advanced_worker.start()
        self.progress_dialog.show()

    def _run_sbas_inversion(self):
        """运行SBAS时序反演"""
        if not self.wrapped_phases or self.acquisition_dates is None or self.perpendicular_baselines is None:
            QMessageBox.warning(self, '警告', '请先加载SBAS数据')
            return

        self.progress_dialog = QProgressDialog('正在执行SBAS时序反演...', '取消', 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)

        unwrapped_phases = []
        quality_maps = []
        masks = []

        for i, wp in enumerate(self.wrapped_phases):
            qm = QualityMapGenerator.pseudo_coherence(wp)
            unwrapper = PhaseUnwrapper('weighted_least_squares', remove_flat=True, weight_power=3.0)
            unw, info = unwrapper.unwrap(wp, quality_map=qm)
            unwrapped_phases.append(unw)
            quality_maps.append(qm)
            masks.append(np.ones_like(wp, dtype=bool))

            self._on_progress(f'解缠干涉图 {i+1}/{len(self.wrapped_phases)}...', 20 + i * 60 // len(self.wrapped_phases))

        max_temp_baseline = self.spin_max_temp_baseline.value()
        if max_temp_baseline == 0:
            max_temp_baseline = None

        max_perp_baseline = self.spin_max_perp_baseline.value()
        if max_perp_baseline == 0:
            max_perp_baseline = None

        self.advanced_worker = AdvancedProcessingWorker(
            'sbas',
            unwrapped_phases=unwrapped_phases,
            acquisition_dates=self.acquisition_dates,
            perpendicular_baselines=self.perpendicular_baselines,
            masks=masks,
            quality_maps=quality_maps,
            wavelength=self.spin_wavelength.value(),
            max_temporal_baseline=max_temp_baseline,
            max_perpendicular_baseline=max_perp_baseline,
            ref_pixel=None
        )

        self.advanced_worker.progress_signal.connect(self._on_progress)
        self.advanced_worker.finished_signal.connect(self._on_advanced_finished)
        self.advanced_worker.error_signal.connect(self._on_advanced_error)

        self.advanced_worker.start()
        self.progress_dialog.show()

    def _load_multi_baseline_data(self):
        """加载多基线数据"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, '选择多基线干涉图文件', '', 'GeoTIFF文件 (*.tif *.tiff)'
        )
        if not file_paths:
            return

        try:
            self.wrapped_phases = []
            baselines = []

            for i, file_path in enumerate(file_paths):
                data, metadata = read_interferogram(file_path)
                self.wrapped_phases.append(data)

                baseline, ok = QInputDialog.getDouble(
                    self, f'输入垂直基线 - 文件{i+1}',
                    f'请输入第{i+1}个干涉图的垂直基线(米):',
                    0.0, -1000.0, 1000.0, 1
                )
                if not ok:
                    self.wrapped_phases = []
                    return
                baselines.append(baseline)

                if i == 0:
                    self.wrapped_phase = data
                    self.metadata = metadata
                    self.current_file_path = file_path

            self.perpendicular_baselines = np.array(baselines)

            self._append_log(f'已加载 {len(self.wrapped_phases)} 个多基线干涉图')
            self._append_log(f'垂直基线范围: {min(baselines):.1f} ~ {max(baselines):.1f} 米')
            self.lbl_file_info.setText(f'多基线数据: {len(self.wrapped_phases)} 个干涉图')
            self.lbl_advanced_info.setText(f'多基线: {len(self.wrapped_phases)} IFGs')

            self._update_display()
            self.statusBar().showMessage('多基线数据加载完成')

        except Exception as e:
            QMessageBox.critical(self, '错误', f'加载多基线数据失败: {str(e)}')

    def _load_sbas_data(self):
        """加载SBAS数据"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, '选择SBAS时序干涉图文件', '', 'GeoTIFF文件 (*.tif *.tiff)'
        )
        if not file_paths:
            return

        try:
            self.wrapped_phases = []
            baselines = []
            dates = []

            for i, file_path in enumerate(file_paths):
                data, metadata = read_interferogram(file_path)
                self.wrapped_phases.append(data)

                baseline, ok = QInputDialog.getDouble(
                    self, f'输入垂直基线 - 文件{i+1}',
                    f'请输入第{i+1}个干涉图的垂直基线(米):',
                    0.0, -1000.0, 1000.0, 1
                )
                if not ok:
                    self.wrapped_phases = []
                    return
                baselines.append(baseline)

                date_str, ok = QInputDialog.getText(
                    self, f'输入获取日期 - 文件{i+1}',
                    f'请输入第{i+1}个干涉图的获取日期 (YYYY-MM-DD):',
                    text='2023-01-01'
                )
                if not ok or not date_str:
                    self.wrapped_phases = []
                    return
                dates.append(np.datetime64(date_str))

                if i == 0:
                    self.wrapped_phase = data
                    self.metadata = metadata
                    self.current_file_path = file_path

            self.perpendicular_baselines = np.array(baselines)
            self.acquisition_dates = np.array(dates)

            self._append_log(f'已加载 {len(self.wrapped_phases)} 个SBAS干涉图')
            self._append_log(f'时间范围: {min(dates)} ~ {max(dates)}')
            self._append_log(f'垂直基线范围: {min(baselines):.1f} ~ {max(baselines):.1f} 米')
            self.lbl_file_info.setText(f'SBAS数据: {len(self.wrapped_phases)} 个干涉图')
            self.lbl_advanced_info.setText(f'SBAS: {len(self.wrapped_phases)} IFGs')

            self._update_display()
            self.statusBar().showMessage('SBAS数据加载完成')

        except Exception as e:
            QMessageBox.critical(self, '错误', f'加载SBAS数据失败: {str(e)}')

    def _on_advanced_finished(self, results: dict):
        """高级处理完成处理"""
        task = results.get('task', '')

        if task == 'dl_unwrap' or task == 'multi_baseline':
            self.unwrapped_phase = results['unwrapped']
            self.unwrap_info = results['info']

            self._append_log(f'{results["info"]["algorithm_name"]}完成')
            self._append_log(f'  正残差点: {results["info"]["num_positive_residues"]}')
            self._append_log(f'  负残差点: {results["info"]["num_negative_residues"]}')
            self._append_log(f'  平均误差: {results["info"]["mean_error"]:.6f} 弧度')

            if task == 'dl_unwrap' and 'stage_details' in results['info']:
                for stage in results['info']['stage_details']:
                    self._append_log(f'  阶段{stage["stage"]}: {stage["pixels"]}像素, 平均误差 {stage["mean_error"]:.4f}')

        elif task == 'sbas':
            self.sbas_results = results
            self.velocity = results.get('velocity')
            self.velocity_std = results.get('velocity_std')
            self.time_series = results.get('time_series')

            self._append_log(f'SBAS时序反演完成')
            if results.get('inversion_success'):
                self._append_log(f'  平均速率: {results.get("mean_velocity", 0):.3f} mm/年')
                self._append_log(f'  速率范围: {results.get("min_velocity", 0):.3f} ~ {results.get("max_velocity", 0):.3f} mm/年')
                self._append_log(f'  参考像素: {results.get("ref_pixel")}')
            else:
                self._append_log(f'  反演失败: {results.get("error_message", "未知错误")}')

        self._update_display()
        self.progress_dialog.close()
        self.statusBar().showMessage(f'{task} 完成')

    def _on_advanced_error(self, error_msg: str):
        """高级处理错误处理"""
        self.progress_dialog.close()
        QMessageBox.critical(self, '错误', f'处理失败: {error_msg}')
        self._append_log(f'错误: {error_msg}')
        self.statusBar().showMessage('处理失败')

    def _on_progress(self, message: str, value: int):
        """处理进度更新"""
        self.progress_dialog.setLabelText(message)
        self.progress_dialog.setValue(value)
        self.statusBar().showMessage(message)

    def _on_unwrap_finished(self, unwrapped: np.ndarray, info: dict):
        """解缠完成处理"""
        self.unwrapped_phase = unwrapped
        self.unwrap_info = info

        self._append_log(f'相位解缠完成 ({info["algorithm_name"]})')
        self._append_log(f'  正残差点: {info["num_positive_residues"]}')
        self._append_log(f'  负残差点: {info["num_negative_residues"]}')
        self._append_log(f'  平均误差: {info["mean_error"]:.6f} 弧度')
        self._append_log(f'  最大误差: {info["max_error"]:.6f} 弧度')

        if info.get('flat_phase_removed', False):
            self._append_log(f'  已去除平地相位')
        if 'note' in info:
            self._append_log(f'  提示: {info["note"]}')

        self._update_display()
        self.progress_dialog.close()
        self.statusBar().showMessage('解缠完成')

    def _on_unwrap_error(self, error_msg: str):
        """解缠错误处理"""
        self.progress_dialog.close()
        QMessageBox.critical(self, '错误', f'解缠失败: {error_msg}')
        self._append_log(f'错误: {error_msg}')
        self.statusBar().showMessage('解缠失败')

    def _update_display(self):
        """更新显示"""
        if self.wrapped_phase is None:
            return

        layer_idx = self.cmb_display_layer.currentIndex()
        layers = ['wrapped', 'unwrapped', 'quality', 'mask', 'error', 'flat_phase', 'velocity', 'velocity_std']
        layer = layers[layer_idx]

        data = None
        title = ''
        is_wrapped = False

        if layer == 'wrapped':
            data = self.wrapped_phase
            title = '包裹相位'
            is_wrapped = True
        elif layer == 'unwrapped':
            if self.unwrapped_phase is not None:
                data = self.unwrapped_phase
                title = '解缠相位'
            else:
                data = self.wrapped_phase
                title = '包裹相位 (请先执行解缠)'
                is_wrapped = True
        elif layer == 'quality':
            if self.quality_map is not None:
                data = self.quality_map
                title = '质量图'
            else:
                data = self.wrapped_phase
                title = '包裹相位 (请先生成质量图)'
                is_wrapped = True
        elif layer == 'mask':
            if self.mask is not None:
                data = self.mask.astype(float)
                title = '掩膜 (白色=有效, 黑色=掩膜)'
            else:
                data = self.wrapped_phase
                title = '包裹相位 (请先生成或加载掩膜)'
                is_wrapped = True
        elif layer == 'error':
            if self.unwrap_info is not None and 'error_estimate' in self.unwrap_info:
                data = self.unwrap_info['error_estimate']
                title = '解缠误差估计'
            else:
                data = self.wrapped_phase
                title = '包裹相位 (请先执行解缠)'
                is_wrapped = True
        elif layer == 'flat_phase':
            if self.unwrap_info is not None and self.unwrap_info.get('flat_phase_removed', False):
                data = self.unwrap_info.get('estimated_flat_phase')
                title = '估计的平地相位'
                is_wrapped = True
            else:
                data = self.wrapped_phase
                title = '包裹相位 (请先执行含平地相位去除的解缠)'
                is_wrapped = True
        elif layer == 'velocity':
            if self.velocity is not None:
                data = self.velocity
                title = '形变速率 (mm/年)'
            else:
                data = self.wrapped_phase
                title = '包裹相位 (请先执行SBAS时序反演)'
                is_wrapped = True
        elif layer == 'velocity_std':
            if self.velocity_std is not None:
                data = self.velocity_std
                title = '形变速率标准差 (mm/年)'
            else:
                data = self.wrapped_phase
                title = '包裹相位 (请先执行SBAS时序反演)'
                is_wrapped = True

        if data is not None:
            self.image_canvas.display_image(data, title, is_wrapped_phase=is_wrapped)

            if self.chk_show_mask.isChecked() and self.mask is not None:
                invalid_mask = ~self.mask
                self.image_canvas.overlay_mask(invalid_mask, color='red', alpha=0.3)

            if self.chk_show_residues.isChecked() and self.unwrap_info is not None:
                pos_res = self.unwrap_info.get('positive_residues', np.array([]))
                neg_res = self.unwrap_info.get('negative_residues', np.array([]))
                if len(pos_res) > 0 or len(neg_res) > 0:
                    self.image_canvas.overlay_residues(pos_res, neg_res)

    def _toggle_profile_drawing(self, enabled: bool):
        """切换剖面线绘制模式"""
        if enabled:
            self.image_canvas.enable_profile_drawing()
            self.statusBar().showMessage('在图像上拖动鼠标绘制剖面线')
        else:
            self.image_canvas.disable_profile_drawing()
            self.statusBar().showMessage('就绪')

    def _on_canvas_event(self, event_type: str, data: any):
        """处理画布事件"""
        if event_type == 'profile_done' and len(data) == 2:
            start, end = data
            self._draw_profile(start, end)

    def _draw_profile(self, start: tuple, end: tuple):
        """绘制相位剖面"""
        dist, values = self.image_canvas.get_profile_data(start, end)

        if self.chk_compare_profile.isChecked() and self.unwrapped_phase is not None:
            orig_data = self.image_canvas.current_data
            self.image_canvas.current_data = self.wrapped_phase
            _, wrapped_vals = self.image_canvas.get_profile_data(start, end)
            self.image_canvas.current_data = self.unwrapped_phase
            _, unwrapped_vals = self.image_canvas.get_profile_data(start, end)
            self.image_canvas.current_data = orig_data

            self.profile_canvas.plot_comparison(dist, wrapped_vals, unwrapped_vals)
        else:
            is_wrapped = (self.cmb_display_layer.currentIndex() == 0)
            self.profile_canvas.plot_profile(
                dist, values,
                label=self.cmb_display_layer.currentText(),
                is_wrapped=is_wrapped
            )

        self.tab_widget.setCurrentIndex(1)

    def _clear_profile(self):
        """清除剖面线"""
        self.image_canvas.clear_profile()
        self.profile_canvas.clear()

    def _plot_3d_surface(self):
        """绘制3D表面"""
        data_idx = self.cmb_3d_data.currentIndex()
        data = None
        title = ''

        if data_idx == 0:
            if self.unwrapped_phase is None:
                QMessageBox.warning(self, '警告', '请先执行相位解缠')
                return
            data = self.unwrapped_phase
            title = '解缠相位3D表面'
        elif data_idx == 1:
            data = self.wrapped_phase
            title = '包裹相位3D表面'
        elif data_idx == 2:
            if self.quality_map is None:
                QMessageBox.warning(self, '警告', '请先生成质量图')
                return
            data = self.quality_map
            title = '质量图3D表面'

        downsample = self.spin_downsample.value()

        if self.chk_wireframe.isChecked():
            self.surface_canvas.plot_wireframe(data, title, downsample)
        else:
            self.surface_canvas.plot_surface(data, title, downsample)

    def _plot_residue_stats(self):
        """绘制残差点统计"""
        if self.unwrap_info is None:
            if self.wrapped_phase is not None:
                pos, neg, charge_map = detect_residues(self.wrapped_phase, self.mask)
                self.stats_canvas.plot_residue_histogram(charge_map)
            else:
                QMessageBox.warning(self, '警告', '请先加载干涉图')
        else:
            charge_map = self.unwrap_info.get('charge_map')
            if charge_map is not None:
                self.stats_canvas.plot_residue_histogram(charge_map)

    def _plot_error_distribution(self):
        """绘制误差分布"""
        if self.unwrap_info is None or 'error_estimate' not in self.unwrap_info:
            QMessageBox.warning(self, '警告', '请先执行相位解缠')
            return

        error_map = self.unwrap_info['error_estimate']
        self.stats_canvas.plot_error_distribution(error_map)

    def _export_results(self):
        """导出处理结果"""
        if self.wrapped_phase is None:
            QMessageBox.warning(self, '警告', '没有可导出的数据')
            return

        export_dir = QFileDialog.getExistingDirectory(
            self,
            '选择导出目录',
            os.path.dirname(self.current_file_path) if self.current_file_path else ''
        )

        if not export_dir:
            return

        try:
            base_name = os.path.basename(self.current_file_path) if self.current_file_path else 'result'
            base_name = os.path.splitext(base_name)[0]

            export_format = self.cmb_export_format.currentIndex()

            export_list = []

            if self.chk_export_unwrapped.isChecked() and self.unwrapped_phase is not None:
                export_list.append(('unwrapped', self.unwrapped_phase, '解缠相位'))

            if self.chk_export_wrapped.isChecked():
                export_list.append(('wrapped', self.wrapped_phase, '包裹相位'))

            if self.chk_export_quality.isChecked() and self.quality_map is not None:
                export_list.append(('quality', self.quality_map, '质量图'))

            if self.chk_export_mask.isChecked() and self.mask is not None:
                export_list.append(('mask', self.mask.astype(np.float32), '掩膜'))

            if self.chk_export_error.isChecked() and self.unwrap_info is not None:
                error = self.unwrap_info.get('error_estimate')
                if error is not None:
                    export_list.append(('error', error, '解缠误差'))

            if self.chk_export_flat.isChecked() and self.unwrap_info is not None:
                flat_phase = self.unwrap_info.get('estimated_flat_phase')
                if flat_phase is not None:
                    export_list.append(('flat_phase', flat_phase, '估计的平地相位'))

            for suffix, data, desc in export_list:
                filename = f'{base_name}_{suffix}'

                if export_format == 0:
                    filepath = os.path.join(export_dir, filename + '.dat')
                    write_envi(data, filepath, self.metadata, band_names=[desc])
                else:
                    filepath = os.path.join(export_dir, filename + '.tif')
                    write_geotiff(data, filepath, self.metadata)

                self._append_log(f'已导出 {desc}: {filepath}')

            QMessageBox.information(self, '成功', f'成功导出 {len(export_list)} 个文件')
            self.statusBar().showMessage('导出完成')

        except Exception as e:
            QMessageBox.critical(self, '错误', f'导出失败: {str(e)}')
            self._append_log(f'导出错误: {str(e)}')

    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            '关于',
            'InSAR相位解缠处理系统 v1.1\n\n'
            '功能:\n'
            '- 读取GeoTIFF格式干涉图\n'
            '- 多种相位解缠算法 (分支切割、最小二乘、SNAPHU)\n'
            '- 质量图生成 (相干系数、伪相关系数)\n'
            '- 掩膜处理 (水体、阴影、低相干区域)\n'
            '- 相位剖面线和3D表面可视化\n'
            '- ENVI/GeoTIFF格式导出\n\n'
            'v1.1修复内容:\n'
            '- 低质量区域错误传播 (质量引导区域增长)\n'
            '- 加权最小二乘权重归一化错误 (非线性权重映射)\n'
            '- 平地相位去除不干净 (多项式拟合去平地相位)\n'
        )
