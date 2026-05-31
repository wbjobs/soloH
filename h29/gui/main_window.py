import sys
import os
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QListWidget, QListWidgetItem,
                             QFileDialog, QMessageBox, QStatusBar,
                             QToolBar, QAction, QProgressDialog,
                             QApplication)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon

from app.models import (VelocityModel, Shot, Receiver, TravelTimeData,
                        InversionConfig)
from app.ray_tracing import ShortestPathRayTracer
from app.inversion import TomographicInversion
from app.io_handler import (load_velocity_model_ascii, save_velocity_model_ascii,
                            load_geometry, save_geometry, load_travel_times,
                            save_travel_times)
from app.synthetic import create_synthetic_test
from app.visualization import (plot_all_results, plot_geometry_only,
                               plot_velocity_model, plot_ray_density,
                               plot_residual_histogram, plot_convergence)
from .widgets import MplWidget, StatusBarWidget
from .dialogs import (InversionParamsDialog, SyntheticDataDialog,
                      LogDisplayDialog)


class InversionThread(QThread):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, model, shots, receivers, data, config):
        super().__init__()
        self.model = model
        self.shots = shots
        self.receivers = receivers
        self.data = data
        self.config = config
        self.inversion = None
    
    def run(self):
        try:
            self.inversion = TomographicInversion(self.model, self.config)
            
            def callback(info):
                self.progress.emit(info)
            
            history = self.inversion.run_full_inversion(
                self.shots, self.receivers, self.data,
                progress_callback=callback
            )
            
            self.finished.emit({
                'history': history,
                'inverted_model': self.inversion.model,
                'initial_model': self.inversion.initial_model
            })
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("井间地震走时层析成像系统")
        self.resize(1400, 900)
        
        self.velocity_model: VelocityModel = None
        self.true_model: VelocityModel = None
        self.shots: list[Shot] = []
        self.receivers: list[Receiver] = []
        self.travel_time_data: list[TravelTimeData] = []
        self.inversion_config = InversionConfig()
        self.inversion_history: list[dict] = []
        self.inverted_model: VelocityModel = None
        self.inversion_thread: InversionThread = None
        
        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
    
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.view_list = QListWidget()
        self.view_list.addItem("📊 综合结果显示")
        self.view_list.addItem("🗺️  初始速度模型")
        self.view_list.addItem("🎯 反演结果模型")
        self.view_list.addItem("📡 射线覆盖密度")
        self.view_list.addItem("📈 走时残差直方图")
        self.view_list.addItem("📉 收敛曲线")
        self.view_list.addItem("📍 观测系统")
        self.view_list.currentRowChanged.connect(self.on_view_changed)
        self.view_list.setCurrentRow(0)
        left_layout.addWidget(self.view_list)
        
        splitter.addWidget(left_panel)
        
        self.plot_widget = MplWidget()
        splitter.addWidget(self.plot_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([200, 1200])
        
        main_layout.addWidget(splitter)
    
    def _build_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("文件(&F)")
        
        load_model_action = QAction("导入速度模型...", self)
        load_model_action.setShortcut("Ctrl+O")
        load_model_action.triggered.connect(self.load_velocity_model)
        file_menu.addAction(load_model_action)
        
        save_model_action = QAction("导出速度模型...", self)
        save_model_action.setShortcut("Ctrl+S")
        save_model_action.triggered.connect(self.save_velocity_model)
        file_menu.addAction(save_model_action)
        
        file_menu.addSeparator()
        
        load_geom_action = QAction("导入观测系统...", self)
        load_geom_action.triggered.connect(self.load_geometry_data)
        file_menu.addAction(load_geom_action)
        
        save_geom_action = QAction("导出观测系统...", self)
        save_geom_action.triggered.connect(self.save_geometry_data)
        file_menu.addAction(save_geom_action)
        
        file_menu.addSeparator()
        
        load_tt_action = QAction("导入走时数据...", self)
        load_tt_action.triggered.connect(self.load_travel_time_data)
        file_menu.addAction(load_tt_action)
        
        save_tt_action = QAction("导出走时数据...", self)
        save_tt_action.triggered.connect(self.save_travel_time_data)
        file_menu.addAction(save_tt_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        tools_menu = menubar.addMenu("工具(&T)")
        
        synthetic_action = QAction("生成合成测试数据...", self)
        synthetic_action.triggered.connect(self.generate_synthetic_data)
        tools_menu.addAction(synthetic_action)
        
        forward_action = QAction("正演计算走时...", self)
        forward_action.triggered.connect(self.run_forward_modeling)
        tools_menu.addAction(forward_action)
        
        tools_menu.addSeparator()
        
        params_action = QAction("反演参数设置...", self)
        params_action.triggered.connect(self.configure_inversion_params)
        tools_menu.addAction(params_action)
        
        invert_action = QAction("执行层析反演", self)
        invert_action.setShortcut("Ctrl+R")
        invert_action.triggered.connect(self.run_inversion)
        tools_menu.addAction(invert_action)
        
        view_menu = menubar.addMenu("视图(&V)")
        
        refresh_action = QAction("刷新显示", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_plot)
        view_menu.addAction(refresh_action)
        
        view_menu.addSeparator()
        
        log_action = QAction("显示反演日志...", self)
        log_action.triggered.connect(self.show_log)
        view_menu.addAction(log_action)
        
        help_menu = menubar.addMenu("帮助(&H)")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def _build_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        load_model_action = QAction("导入模型", self)
        load_model_action.triggered.connect(self.load_velocity_model)
        toolbar.addAction(load_model_action)
        
        save_model_action = QAction("导出模型", self)
        save_model_action.triggered.connect(self.save_velocity_model)
        toolbar.addAction(save_model_action)
        
        toolbar.addSeparator()
        
        synthetic_action = QAction("合成数据", self)
        synthetic_action.triggered.connect(self.generate_synthetic_data)
        toolbar.addAction(synthetic_action)
        
        forward_action = QAction("正演计算", self)
        forward_action.triggered.connect(self.run_forward_modeling)
        toolbar.addAction(forward_action)
        
        toolbar.addSeparator()
        
        params_action = QAction("参数设置", self)
        params_action.triggered.connect(self.configure_inversion_params)
        toolbar.addAction(params_action)
        
        invert_action = QAction("开始反演", self)
        invert_action.triggered.connect(self.run_inversion)
        toolbar.addAction(invert_action)
    
    def _build_statusbar(self):
        self.status_widget = StatusBarWidget()
        status_bar = QStatusBar()
        status_bar.addWidget(self.status_widget, 1)
        self.setStatusBar(status_bar)
    
    def load_velocity_model(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择速度模型文件", "",
            "ASCII Files (*.txt *.dat *.vel);;All Files (*)"
        )
        if filename:
            try:
                self.velocity_model = load_velocity_model_ascii(filename)
                self.inverted_model = None
                self.inversion_history = []
                self.status_widget.update_model_info(
                    self.velocity_model.nx, self.velocity_model.nz,
                    self.velocity_model.dx, self.velocity_model.dz
                )
                self.status_widget.update_status(f"已加载速度模型: {os.path.basename(filename)}")
                self.refresh_plot()
                QMessageBox.information(self, "成功", "速度模型加载成功！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载速度模型失败: {str(e)}")
    
    def save_velocity_model(self):
        if self.inverted_model is None and self.velocity_model is None:
            QMessageBox.warning(self, "警告", "没有可导出的速度模型！")
            return
        
        model_to_save = self.inverted_model if self.inverted_model else self.velocity_model
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存速度模型", "",
            "ASCII Files (*.txt *.dat *.vel);;All Files (*)"
        )
        if filename:
            try:
                save_velocity_model_ascii(model_to_save, filename)
                self.status_widget.update_status(f"已保存速度模型: {os.path.basename(filename)}")
                QMessageBox.information(self, "成功", "速度模型保存成功！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存速度模型失败: {str(e)}")
    
    def load_geometry_data(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择观测系统文件", "",
            "ASCII Files (*.txt *.dat *.geo);;All Files (*)"
        )
        if filename:
            try:
                self.shots, self.receivers = load_geometry(filename)
                self.status_widget.update_data_info(
                    len(self.shots), len(self.receivers), len(self.travel_time_data)
                )
                self.status_widget.update_status(f"已加载观测系统: {os.path.basename(filename)}")
                self.refresh_plot()
                QMessageBox.information(self, "成功", "观测系统加载成功！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载观测系统失败: {str(e)}")
    
    def save_geometry_data(self):
        if not self.shots or not self.receivers:
            QMessageBox.warning(self, "警告", "没有可导出的观测系统数据！")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存观测系统", "",
            "ASCII Files (*.txt *.dat *.geo);;All Files (*)"
        )
        if filename:
            try:
                save_geometry(self.shots, self.receivers, filename)
                self.status_widget.update_status(f"已保存观测系统: {os.path.basename(filename)}")
                QMessageBox.information(self, "成功", "观测系统保存成功！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存观测系统失败: {str(e)}")
    
    def load_travel_time_data(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择走时数据文件", "",
            "ASCII Files (*.txt *.dat *.tt);;All Files (*)"
        )
        if filename:
            try:
                self.travel_time_data = load_travel_times(filename)
                
                shot_dict = {s.id: s for s in self.shots}
                rec_dict = {r.id: r for r in self.receivers}
                for d in self.travel_time_data:
                    d.shot = shot_dict.get(d.shot_id)
                    d.receiver = rec_dict.get(d.receiver_id)
                
                self.status_widget.update_data_info(
                    len(self.shots), len(self.receivers), len(self.travel_time_data)
                )
                self.status_widget.update_status(f"已加载走时数据: {os.path.basename(filename)}")
                self.refresh_plot()
                QMessageBox.information(self, "成功", f"加载成功！共{len(self.travel_time_data)}条走时记录。")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载走时数据失败: {str(e)}")
    
    def save_travel_time_data(self):
        if not self.travel_time_data:
            QMessageBox.warning(self, "警告", "没有可导出的走时数据！")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存走时数据", "",
            "ASCII Files (*.txt *.dat *.tt);;All Files (*)"
        )
        if filename:
            try:
                include_calc = any(abs(d.calculated_time) > 0 for d in self.travel_time_data)
                save_travel_times(self.travel_time_data, filename, include_calc)
                self.status_widget.update_status(f"已保存走时数据: {os.path.basename(filename)}")
                QMessageBox.information(self, "成功", "走时数据保存成功！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存走时数据失败: {str(e)}")
    
    def generate_synthetic_data(self):
        dialog = SyntheticDataDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_params()
            
            progress = QProgressDialog("正在生成合成数据...", None, 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            try:
                progress.setValue(10)
                QApplication.processEvents()
                
                self.true_model, self.velocity_model, self.shots, self.receivers, self.travel_time_data = \
                    create_synthetic_test(**params)
                
                progress.setValue(50)
                QApplication.processEvents()
                
                shot_dict = {s.id: s for s in self.shots}
                rec_dict = {r.id: r for r in self.receivers}
                for d in self.travel_time_data:
                    d.shot = shot_dict.get(d.shot_id)
                    d.receiver = rec_dict.get(d.receiver_id)
                
                progress.setValue(100)
                
                self.inverted_model = None
                self.inversion_history = []
                
                self.status_widget.update_model_info(
                    self.velocity_model.nx, self.velocity_model.nz,
                    self.velocity_model.dx, self.velocity_model.dz
                )
                self.status_widget.update_data_info(
                    len(self.shots), len(self.receivers), len(self.travel_time_data)
                )
                self.status_widget.update_status("合成数据生成完成")
                self.refresh_plot()
                
                QMessageBox.information(
                    self, "成功",
                    f"合成数据生成成功！\n"
                    f"模型: {params['model_type']}\n"
                    f"网格: {params['nx']}x{params['nz']}\n"
                    f"炮点: {params['n_shots']}, 检波点: {params['n_receivers']}\n"
                    f"走时记录: {len(self.travel_time_data)}条"
                )
            except Exception as e:
                QMessageBox.critical(self, "错误", f"生成合成数据失败: {str(e)}")
            finally:
                progress.close()
    
    def run_forward_modeling(self):
        if self.velocity_model is None:
            QMessageBox.warning(self, "警告", "请先加载速度模型！")
            return
        if not self.shots or not self.receivers:
            QMessageBox.warning(self, "警告", "请先加载观测系统！")
            return
        if not self.travel_time_data:
            QMessageBox.warning(self, "警告", "请先加载走时数据或生成合成数据！")
            return
        
        progress = QProgressDialog("正在正演计算走时...", None, 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        try:
            progress.setValue(10)
            QApplication.processEvents()
            
            ray_tracer = ShortestPathRayTracer(self.velocity_model)
            self.travel_time_data, _ = ray_tracer.forward_modeling(
                self.shots, self.receivers, self.travel_time_data,
                compute_rays=True, update_density=True
            )
            
            progress.setValue(100)
            
            residuals = np.array([d.residual for d in self.travel_time_data if np.isfinite(d.residual)])
            rms = np.sqrt(np.mean(residuals ** 2)) * 1000 if len(residuals) > 0 else 0
            
            self.status_widget.update_status(f"正演完成, RMS={rms:.2f} ms")
            self.refresh_plot()
            
            QMessageBox.information(
                self, "正演完成",
                f"正演计算完成！\n"
                f"有效数据: {len(residuals)}条\n"
                f"RMS残差: {rms:.2f} ms\n"
                f"平均残差: {np.mean(residuals)*1000:.2f} ms\n"
                f"残差标准差: {np.std(residuals)*1000:.2f} ms"
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"正演计算失败: {str(e)}")
        finally:
            progress.close()
    
    def configure_inversion_params(self):
        dialog = InversionParamsDialog(self.inversion_config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.inversion_config = dialog.get_config()
            self.status_widget.update_status("反演参数已更新")
    
    def run_inversion(self):
        if self.velocity_model is None:
            QMessageBox.warning(self, "警告", "请先加载速度模型！")
            return
        if not self.shots or not self.receivers:
            QMessageBox.warning(self, "警告", "请先加载观测系统！")
            return
        if not self.travel_time_data:
            QMessageBox.warning(self, "警告", "请先加载走时数据！")
            return
        
        reply = QMessageBox.question(
            self, "确认反演",
            f"准备开始层析反演，参数如下：\n"
            f"最大迭代: {self.inversion_config.max_iterations}\n"
            f"正则化系数: {self.inversion_config.regularization}\n"
            f"阻尼系数: {self.inversion_config.damping}\n\n"
            f"确定开始反演吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.log_dialog = LogDisplayDialog("反演日志", self)
        self.log_dialog.show()
        self.log_dialog.append_text(f"=== 反演开始于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        self.log_dialog.append_text(f"配置: 最大迭代={self.inversion_config.max_iterations}, "
                                    f"正则化={self.inversion_config.regularization}, "
                                    f"阻尼={self.inversion_config.damping}")
        self.log_dialog.append_text("")
        
        self.inversion_thread = InversionThread(
            self.velocity_model.copy(),
            self.shots, self.receivers,
            self.travel_time_data.copy(),
            self.inversion_config
        )
        
        self.inversion_thread.progress.connect(self.on_inversion_progress)
        self.inversion_thread.finished.connect(self.on_inversion_finished)
        self.inversion_thread.error.connect(self.on_inversion_error)
        self.inversion_thread.start()
        
        self.status_widget.update_status("反演进行中...")
    
    def on_inversion_progress(self, info):
        if 'error' in info:
            msg = f"迭代 {info['iteration']}: 错误 - {info['error']}"
        else:
            msg = (f"迭代 {info['iteration']}: "
                   f"RMS前={info['rms_before']*1000:.2f} ms, "
                   f"RMS后={info['rms_after']*1000:.2f} ms, "
                   f"下降={info['rms_reduction']:.2f}%")
        
        if self.log_dialog:
            self.log_dialog.append_text(msg)
        
        self.status_widget.update_status(f"反演迭代 {info['iteration']}...")
    
    def on_inversion_finished(self, result):
        self.inversion_history = result['history']
        self.inverted_model = result['inverted_model']
        
        if self.log_dialog:
            self.log_dialog.append_text("")
            self.log_dialog.append_text(f"=== 反演完成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            if self.inversion_history:
                final = self.inversion_history[-1]
                self.log_dialog.append_text(f"最终RMS: {final['rms_after']*1000:.2f} ms")
                self.log_dialog.append_text(f"总迭代次数: {final['iteration']}")
        
        self.status_widget.update_status("反演完成")
        self.refresh_plot()
        
        QMessageBox.information(
            self, "反演完成",
            "层析反演已完成！\n"
            "请查看右侧显示的反演结果。"
        )
    
    def on_inversion_error(self, error_msg):
        if self.log_dialog:
            self.log_dialog.append_text(f"错误: {error_msg}")
        
        self.status_widget.update_status("反演出错")
        QMessageBox.critical(self, "反演错误", f"反演过程中发生错误:\n{error_msg}")
    
    def show_log(self):
        if not hasattr(self, 'log_dialog') or self.log_dialog is None:
            self.log_dialog = LogDisplayDialog("反演日志", self)
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()
    
    def show_about(self):
        QMessageBox.about(
            self, "关于",
            "井间地震走时层析成像系统 v1.0\n\n"
            "功能特性:\n"
            "• 最短路径法弯曲射线追踪\n"
            "• LSQR算法求解层析反演\n"
            "• 速度模型导入/导出 (ASCII格式)\n"
            "• 合成数据测试功能\n"
            "• 多视图结果可视化\n\n"
            "开发: Python + PyQt5 + NumPy + Matplotlib"
        )
    
    def on_view_changed(self, index):
        self.refresh_plot()
    
    def refresh_plot(self):
        canvas = self.plot_widget.get_canvas()
        view_index = self.view_list.currentRow()
        
        if view_index == 0:
            self._plot_combined_results(canvas)
        elif view_index == 1:
            self._plot_initial_model(canvas)
        elif view_index == 2:
            self._plot_inverted_model(canvas)
        elif view_index == 3:
            self._plot_ray_density(canvas)
        elif view_index == 4:
            self._plot_residual_histogram(canvas)
        elif view_index == 5:
            self._plot_convergence(canvas)
        elif view_index == 6:
            self._plot_geometry(canvas)
    
    def _plot_combined_results(self, canvas):
        if self.velocity_model is None:
            self._plot_empty(canvas, "请先加载数据")
            return
        
        data = []
        if self.travel_time_data:
            data = self.travel_time_data
        
        if self.inverted_model is None:
            if data:
                ray_tracer = ShortestPathRayTracer(self.velocity_model)
                ray_tracer.forward_modeling(
                    self.shots, self.receivers, data,
                    compute_rays=True, update_density=True
                )
            
            fig = canvas.get_figure()
            fig.clear()
            
            gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
            
            ax1 = fig.add_subplot(gs[0, 0])
            plot_velocity_model(ax1, self.velocity_model, '初始速度模型')
            
            ax2 = fig.add_subplot(gs[0, 1])
            plot_ray_density(ax2, self.velocity_model, '射线覆盖密度')
            
            ax3 = fig.add_subplot(gs[1, 0])
            plot_geometry_only_view(ax3, self.shots, self.receivers, self.velocity_model)
            
            ax4 = fig.add_subplot(gs[1, 1])
            if data and any(abs(d.residual) > 0 for d in data):
                plot_residual_histogram(ax4, data, '走时残差直方图')
            else:
                ax4.text(0.5, 0.5, '请先进行正演或反演\n以计算残差',
                        ha='center', va='center', fontsize=12)
                ax4.set_axis_off()
            
            canvas.draw()
        else:
            final_data = self.travel_time_data
            if self.inversion_history and 'final_data' in self.inversion_history[-1]:
                final_data = self.inversion_history[-1]['final_data']
            
            plot_all_results(
                canvas,
                initial_model=self.velocity_model,
                inverted_model=self.inverted_model,
                true_model=self.true_model,
                data=final_data,
                history=self.inversion_history,
                shots=self.shots,
                receivers=self.receivers
            )
    
    def _plot_initial_model(self, canvas):
        if self.velocity_model is None:
            self._plot_empty(canvas, "请先加载速度模型")
            return
        
        fig = canvas.get_figure()
        fig.clear()
        ax = fig.add_subplot(111)
        plot_velocity_model(ax, self.velocity_model, '初始速度模型')
        canvas.draw()
    
    def _plot_inverted_model(self, canvas):
        if self.inverted_model is None:
            self._plot_empty(canvas, "请先执行反演")
            return
        
        fig = canvas.get_figure()
        fig.clear()
        ax = fig.add_subplot(111)
        plot_velocity_model(ax, self.inverted_model, '反演结果速度模型')
        canvas.draw()
    
    def _plot_ray_density(self, canvas):
        model = self.inverted_model if self.inverted_model else self.velocity_model
        if model is None:
            self._plot_empty(canvas, "请先加载模型并正演")
            return
        
        fig = canvas.get_figure()
        fig.clear()
        ax = fig.add_subplot(111)
        plot_ray_density(ax, model, '射线覆盖密度')
        canvas.draw()
    
    def _plot_residual_histogram(self, canvas):
        if not self.travel_time_data:
            self._plot_empty(canvas, "请先加载走时数据")
            return
        
        data = self.travel_time_data
        if self.inversion_history and 'final_data' in self.inversion_history[-1]:
            data = self.inversion_history[-1]['final_data']
        
        if not any(abs(d.residual) > 0 for d in data):
            self._plot_empty(canvas, "请先进行正演或反演计算")
            return
        
        fig = canvas.get_figure()
        fig.clear()
        ax = fig.add_subplot(111)
        plot_residual_histogram(ax, data, '走时残差直方图')
        canvas.draw()
    
    def _plot_convergence(self, canvas):
        if not self.inversion_history:
            self._plot_empty(canvas, "请先执行反演")
            return
        
        fig = canvas.get_figure()
        fig.clear()
        ax = fig.add_subplot(111)
        plot_convergence(ax, self.inversion_history, '收敛曲线')
        canvas.draw()
    
    def _plot_geometry(self, canvas):
        if not self.shots or not self.receivers:
            self._plot_empty(canvas, "请先加载观测系统")
            return
        
        model = self.inverted_model if self.inverted_model else self.velocity_model
        if model is None:
            fig = canvas.get_figure()
            fig.clear()
            ax = fig.add_subplot(111)
            plot_geometry(ax, self.shots, self.receivers, '观测系统')
            canvas.draw()
        else:
            plot_geometry_only(canvas, self.shots, self.receivers, model)
    
    def _plot_empty(self, canvas, message):
        fig = canvas.get_figure()
        fig.clear()
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, message, ha='center', va='center',
                fontsize=16, color='gray')
        ax.set_axis_off()
        canvas.draw()


def plot_geometry_only_view(ax, shots, receivers, model):
    x_coords = model.x_coords()
    z_coords = model.z_coords()
    extent = [x_coords[0], x_coords[-1], z_coords[-1], z_coords[0]]
    
    ax.imshow(model.velocity, extent=extent, cmap='jet',
              aspect='auto', origin='upper', alpha=0.6)
    
    sx = [s.x for s in shots]
    sz = [s.z for s in shots]
    rx = [r.x for r in receivers]
    rz = [r.z for r in receivers]
    
    ax.scatter(sx, sz, c='red', marker='*', s=150, edgecolor='white',
               linewidth=1, label='Shots', zorder=10)
    ax.scatter(rx, rz, c='blue', marker='v', s=100, edgecolor='white',
               linewidth=1, label='Receivers', zorder=10)
    
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Z (m)')
    ax.set_title('观测系统')
    ax.legend()
    ax.grid(True, alpha=0.3)
