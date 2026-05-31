import numpy as np
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLabel, QLineEdit, QPushButton, QComboBox,
                             QCheckBox, QDialogButtonBox, QSpinBox,
                             QDoubleSpinBox, QGroupBox, QFileDialog, QTextEdit)
from PyQt5.QtCore import Qt
from typing import Optional
from app.models import InversionConfig


class InversionParamsDialog(QDialog):
    def __init__(self, config: Optional[InversionConfig] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("反演参数设置")
        self.setMinimumWidth(400)
        
        self.config = config if config else InversionConfig()
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        main_group = QGroupBox("基本反演参数")
        form = QFormLayout(main_group)
        
        self.max_iter_spin = QSpinBox()
        self.max_iter_spin.setRange(1, 100)
        self.max_iter_spin.setValue(self.config.max_iterations)
        form.addRow("最大迭代次数:", self.max_iter_spin)
        
        self.tol_spin = QDoubleSpinBox()
        self.tol_spin.setRange(1e-10, 1e-1)
        self.tol_spin.setDecimals(10)
        self.tol_spin.setScientificNotation(True)
        self.tol_spin.setValue(self.config.lsqr_tol)
        form.addRow("LSQR收敛阈值:", self.tol_spin)
        
        self.reg_spin = QDoubleSpinBox()
        self.reg_spin.setRange(0.0, 10.0)
        self.reg_spin.setDecimals(4)
        self.reg_spin.setSingleStep(0.01)
        self.reg_spin.setValue(self.config.regularization)
        form.addRow("正则化系数(初始):", self.reg_spin)
        
        self.damp_spin = QDoubleSpinBox()
        self.damp_spin.setRange(0.0, 1.0)
        self.damp_spin.setDecimals(4)
        self.damp_spin.setSingleStep(0.01)
        self.damp_spin.setValue(self.config.damping)
        form.addRow("阻尼系数(初始):", self.damp_spin)
        
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.01, 2.0)
        self.scale_spin.setDecimals(3)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setValue(self.config.update_scale)
        form.addRow("更新步长因子:", self.scale_spin)
        
        self.vmin_spin = QDoubleSpinBox()
        self.vmin_spin.setRange(100.0, 10000.0)
        self.vmin_spin.setValue(self.config.min_velocity)
        form.addRow("最小速度 (m/s):", self.vmin_spin)
        
        self.vmax_spin = QDoubleSpinBox()
        self.vmax_spin.setRange(100.0, 10000.0)
        self.vmax_spin.setValue(self.config.max_velocity)
        form.addRow("最大速度 (m/s):", self.vmax_spin)
        
        layout.addWidget(main_group)
        
        adaptive_group = QGroupBox("自适应正则化")
        adaptive_layout = QVBoxLayout(adaptive_group)
        
        self.adaptive_reg_check = QCheckBox("启用自适应正则化（自动选择参数）")
        self.adaptive_reg_check.setChecked(self.config.adaptive_regularization)
        self.adaptive_reg_check.toggled.connect(self._on_adaptive_toggled)
        adaptive_layout.addWidget(self.adaptive_reg_check)
        
        adaptive_form = QFormLayout()
        self.reg_min_spin = QDoubleSpinBox()
        self.reg_min_spin.setRange(0.001, 1.0)
        self.reg_min_spin.setDecimals(4)
        self.reg_min_spin.setValue(self.config.reg_min)
        adaptive_form.addRow("正则化最小值:", self.reg_min_spin)
        
        self.reg_max_spin = QDoubleSpinBox()
        self.reg_max_spin.setRange(0.01, 10.0)
        self.reg_max_spin.setDecimals(4)
        self.reg_max_spin.setValue(self.config.reg_max)
        adaptive_form.addRow("正则化最大值:", self.reg_max_spin)
        
        self.damp_min_spin = QDoubleSpinBox()
        self.damp_min_spin.setRange(0.0001, 0.1)
        self.damp_min_spin.setDecimals(5)
        self.damp_min_spin.setValue(self.config.damping_min)
        adaptive_form.addRow("阻尼最小值:", self.damp_min_spin)
        
        self.damp_max_spin = QDoubleSpinBox()
        self.damp_max_spin.setRange(0.001, 1.0)
        self.damp_max_spin.setDecimals(4)
        self.damp_max_spin.setValue(self.config.damping_max)
        adaptive_form.addRow("阻尼最大值:", self.damp_max_spin)
        
        adaptive_layout.addLayout(adaptive_form)
        
        self.ray_weight_check = QCheckBox("射线密度加权正则化（覆盖低的区域更强平滑）")
        self.ray_weight_check.setChecked(self.config.use_ray_weighted_reg)
        adaptive_layout.addWidget(self.ray_weight_check)
        
        self.curvature_check = QCheckBox("曲率正则化（二阶导数平滑）")
        self.curvature_check.setChecked(self.config.curvature_regularization)
        self.curvature_check.toggled.connect(self._on_curvature_toggled)
        adaptive_layout.addWidget(self.curvature_check)
        
        self.second_deriv_spin = QDoubleSpinBox()
        self.second_deriv_spin.setRange(0.0, 2.0)
        self.second_deriv_spin.setDecimals(3)
        self.second_deriv_spin.setValue(self.config.second_derivative_weight)
        adaptive_form2 = QFormLayout()
        adaptive_form2.addRow("二阶导数权重:", self.second_deriv_spin)
        adaptive_layout.addLayout(adaptive_form2)
        
        layout.addWidget(adaptive_group)
        
        self._on_adaptive_toggled(self.adaptive_reg_check.isChecked())
        self._on_curvature_toggled(self.curvature_check.isChecked())
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _on_adaptive_toggled(self, checked):
        self.reg_min_spin.setEnabled(checked)
        self.reg_max_spin.setEnabled(checked)
        self.damp_min_spin.setEnabled(checked)
        self.damp_max_spin.setEnabled(checked)
    
    def _on_curvature_toggled(self, checked):
        self.second_deriv_spin.setEnabled(checked)
    
    def get_config(self) -> InversionConfig:
        return InversionConfig(
            max_iterations=self.max_iter_spin.value(),
            lsqr_tol=self.tol_spin.value(),
            regularization=self.reg_spin.value(),
            damping=self.damp_spin.value(),
            update_scale=self.scale_spin.value(),
            min_velocity=self.vmin_spin.value(),
            max_velocity=self.vmax_spin.value(),
            adaptive_regularization=self.adaptive_reg_check.isChecked(),
            reg_min=self.reg_min_spin.value(),
            reg_max=self.reg_max_spin.value(),
            damping_min=self.damp_min_spin.value(),
            damping_max=self.damp_max_spin.value(),
            use_ray_weighted_reg=self.ray_weight_check.isChecked(),
            curvature_regularization=self.curvature_check.isChecked(),
            second_derivative_weight=self.second_deriv_spin.value()
        )


class SyntheticDataDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("生成合成测试数据")
        self.setMinimumWidth(400)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        grid_group = QGroupBox("网格参数")
        grid_form = QFormLayout(grid_group)
        
        self.nx_spin = QSpinBox()
        self.nx_spin.setRange(10, 200)
        self.nx_spin.setValue(40)
        grid_form.addRow("X方向网格数:", self.nx_spin)
        
        self.nz_spin = QSpinBox()
        self.nz_spin.setRange(10, 200)
        self.nz_spin.setValue(40)
        grid_form.addRow("Z方向网格数:", self.nz_spin)
        
        self.dx_spin = QDoubleSpinBox()
        self.dx_spin.setRange(0.5, 50.0)
        self.dx_spin.setValue(5.0)
        self.dx_spin.setSuffix(" m")
        grid_form.addRow("X方向网格间距:", self.dx_spin)
        
        self.dz_spin = QDoubleSpinBox()
        self.dz_spin.setRange(0.5, 50.0)
        self.dz_spin.setValue(5.0)
        self.dz_spin.setSuffix(" m")
        grid_form.addRow("Z方向网格间距:", self.dz_spin)
        
        layout.addWidget(grid_group)
        
        model_group = QGroupBox("速度模型类型")
        model_layout = QVBoxLayout(model_group)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(['anomaly (异常体)', 'gradient (梯度)', 
                                   'two_layer (两层)', 'complex (复杂)'])
        model_layout.addWidget(self.model_combo)
        
        layout.addWidget(model_group)
        
        geometry_group = QGroupBox("观测系统")
        geom_form = QFormLayout(geometry_group)
        
        self.nshots_spin = QSpinBox()
        self.nshots_spin.setRange(2, 100)
        self.nshots_spin.setValue(10)
        geom_form.addRow("炮点数量:", self.nshots_spin)
        
        self.nrecv_spin = QSpinBox()
        self.nrecv_spin.setRange(2, 200)
        self.nrecv_spin.setValue(40)
        geom_form.addRow("检波点数量:", self.nrecv_spin)
        
        self.noise_spin = QDoubleSpinBox()
        self.noise_spin.setRange(0.0, 0.1)
        self.noise_spin.setDecimals(4)
        self.noise_spin.setSingleStep(0.001)
        self.noise_spin.setValue(0.01)
        self.noise_spin.setSuffix(" (%)")
        geom_form.addRow("噪声水平:", self.noise_spin)
        
        layout.addWidget(geometry_group)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_params(self) -> dict:
        model_type = self.model_combo.currentText().split(' ')[0]
        return {
            'nx': self.nx_spin.value(),
            'nz': self.nz_spin.value(),
            'dx': self.dx_spin.value(),
            'dz': self.dz_spin.value(),
            'n_shots': self.nshots_spin.value(),
            'n_receivers': self.nrecv_spin.value(),
            'noise_level': self.noise_spin.value(),
            'model_type': model_type
        }


class LogDisplayDialog(QDialog):
    def __init__(self, title: str = "日志", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 400)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.Save).clicked.connect(self.save_log)
        layout.addWidget(buttons)
    
    def append_text(self, text: str):
        self.text_edit.append(text)
    
    def clear(self):
        self.text_edit.clear()
    
    def save_log(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存日志", "", "Text Files (*.txt);;All Files (*)"
        )
        if filename:
            with open(filename, 'w') as f:
                f.write(self.text_edit.toPlainText())
