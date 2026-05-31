import numpy as np
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QSizePolicy)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=10, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()
    
    def get_figure(self):
        return self.fig
    
    def clear(self):
        self.fig.clear()
        self.draw()


class MplWidget(QWidget):
    def __init__(self, parent=None, with_toolbar: bool = True):
        super().__init__(parent)
        self._build_ui(with_toolbar)
    
    def _build_ui(self, with_toolbar: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.canvas = MplCanvas()
        layout.addWidget(self.canvas)
        
        if with_toolbar:
            self.toolbar = NavigationToolbar(self.canvas, self)
            layout.addWidget(self.toolbar)
    
    def get_canvas(self) -> MplCanvas:
        return self.canvas
    
    def get_figure(self) -> Figure:
        return self.canvas.get_figure()
    
    def clear(self):
        self.canvas.clear()


class StatusBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
    
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        
        self.data_label = QLabel("数据: 未加载")
        self.model_label = QLabel("模型: 未加载")
        self.status_label = QLabel("就绪")
        
        layout.addWidget(self.data_label)
        layout.addSpacing(20)
        layout.addWidget(self.model_label)
        layout.addStretch()
        layout.addWidget(self.status_label)
    
    def update_data_info(self, n_shots: int, n_receivers: int, n_data: int):
        self.data_label.setText(f"数据: {n_shots}炮, {n_receivers}检波点, {n_data}条记录")
    
    def update_model_info(self, nx: int, nz: int, dx: float, dz: float):
        self.model_label.setText(f"模型: {nx}x{nz}网格, {dx}x{dz}m")
    
    def update_status(self, text: str):
        self.status_label.setText(text)
