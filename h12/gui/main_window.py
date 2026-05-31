import sys
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QMessageBox, 
                             QTabWidget, QGroupBox, QComboBox, QDoubleSpinBox,
                             QSpinBox, QProgressDialog, QTableWidget, QTableWidgetItem,
                             QHeaderView, QSplitter, QTextEdit, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from microstate import (EEGDataLoader, Preprocessor, GFPAnalyzer, 
                        MicrostateClustering, TemplateFitting, StatisticsAnalyzer,
                        Visualizer, Exporter, NonlinearDynamicsAnalyzer,
                        SourceReconstructor, CorticalMicrostateAnalyzer, GroupStatistics)


class AnalysisThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, filepath, params):
        super().__init__()
        self.filepath = filepath
        self.params = params

    def run(self):
        try:
            self.progress.emit(5, '正在加载EDF数据...')
            loader = EEGDataLoader()
            data, ch_names, sfreq, times = loader.load_edf(self.filepath)
            pos = loader.get_channel_positions()

            self.progress.emit(15, '正在进行预处理...')
            preprocessor = Preprocessor(
                low_freq=self.params['low_freq'],
                high_freq=self.params['high_freq'],
                sfreq=sfreq
            )
            processed_data = preprocessor.preprocess(
                data, reference_type=self.params['reference_type']
            )

            self.progress.emit(30, '正在计算GFP并提取峰值...')
            gfp_analyzer = GFPAnalyzer(sfreq=sfreq)
            gfp, peak_indices, peak_times, peak_data, peak_props = gfp_analyzer.analyze(
                processed_data, min_distance_ms=self.params['min_peak_distance']
            )

            self.progress.emit(45, '正在进行k-means聚类...')
            clustering = MicrostateClustering(
                n_clusters=self.params['n_clusters'],
                n_init=self.params['n_init'],
                max_iter=self.params['max_iter']
            )
            templates, labels = clustering.fit(peak_data)

            self.progress.emit(55, '正在进行模板拟合...')
            template_fitting = TemplateFitting(templates, sfreq=sfreq)
            microstate_sequence, correlation_values = template_fitting.fit(processed_data)

            self.progress.emit(65, '正在进行统计分析...')
            stats_analyzer = StatisticsAnalyzer(sfreq=sfreq, n_clusters=self.params['n_clusters'])
            stats = stats_analyzer.analyze(microstate_sequence)

            nonlinear_results = None
            if self.params.get('enable_nonlinear', True):
                self.progress.emit(72, '正在进行非线性动力学分析...')
                nonlinear_analyzer = NonlinearDynamicsAnalyzer(n_clusters=self.params['n_clusters'])
                nonlinear_results = nonlinear_analyzer.analyze(
                    microstate_sequence, 
                    transition_matrix=stats['transition_probabilities']
                )

            source_results = None
            if self.params.get('enable_source', False):
                self.progress.emit(82, '正在进行源重建和皮层微状态分析...')
                source_recon = SourceReconstructor(sfreq=sfreq, method=self.params.get('source_method', 'eloreta'))
                source_data, source_power, source_space = source_recon.reconstruct(
                    processed_data, pos, 
                    lambda_reg=self.params.get('lambda_reg', 0.1),
                    n_sources=self.params.get('n_sources', 200)
                )
                
                cortical_analyzer = CorticalMicrostateAnalyzer(
                    n_clusters=self.params['n_clusters'], sfreq=sfreq
                )
                source_results = cortical_analyzer.analyze(
                    source_power, source_space,
                    peak_min_distance_ms=self.params['min_peak_distance']
                )
                source_results['source_data'] = source_data
                source_results['source_power'] = source_power
                source_results['source_space'] = source_space

            self.progress.emit(95, '正在完成分析...')

            results = {
                'data': data,
                'processed_data': processed_data,
                'ch_names': ch_names,
                'sfreq': sfreq,
                'times': times,
                'pos': pos,
                'gfp': gfp,
                'peak_indices': peak_indices,
                'peak_times': peak_times,
                'peak_data': peak_data,
                'templates': templates,
                'cluster_labels': labels,
                'microstate_sequence': microstate_sequence,
                'correlation_values': correlation_values,
                'stats': stats,
                'explained_variance': clustering.explained_variance,
                'nonlinear_results': nonlinear_results,
                'source_results': source_results
            }

            self.progress.emit(100, '分析完成!')
            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('EEG微状态分析系统')
        self.setGeometry(100, 100, 1400, 900)
        
        self.results = None
        self.visualizer = Visualizer()
        self.exporter = Exporter()
        
        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        
        main_layout.addWidget(splitter)

    def _toggle_source_params(self, enabled):
        self.source_param_widget.setEnabled(enabled)

    def _create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        file_group = QGroupBox('数据加载')
        file_layout = QVBoxLayout(file_group)
        
        self.load_btn = QPushButton('加载EDF文件')
        self.load_btn.clicked.connect(self.load_file)
        self.load_btn.setFont(QFont('Arial', 10, QFont.Bold))
        self.load_btn.setMinimumHeight(40)
        file_layout.addWidget(self.load_btn)
        
        self.file_label = QLabel('未选择文件')
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet('color: gray;')
        file_layout.addWidget(self.file_label)
        
        layout.addWidget(file_group)
        
        preprocess_group = QGroupBox('预处理参数')
        preprocess_layout = QVBoxLayout(preprocess_group)
        
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel('低通频率(Hz):'))
        self.low_freq_spin = QDoubleSpinBox()
        self.low_freq_spin.setRange(0.1, 100)
        self.low_freq_spin.setValue(1.0)
        freq_layout.addWidget(self.low_freq_spin)
        preprocess_layout.addLayout(freq_layout)
        
        high_freq_layout = QHBoxLayout()
        high_freq_layout.addWidget(QLabel('高通频率(Hz):'))
        self.high_freq_spin = QDoubleSpinBox()
        self.high_freq_spin.setRange(1, 200)
        self.high_freq_spin.setValue(40.0)
        high_freq_layout.addWidget(self.high_freq_spin)
        preprocess_layout.addLayout(high_freq_layout)
        
        ref_layout = QHBoxLayout()
        ref_layout.addWidget(QLabel('参考类型:'))
        self.ref_combo = QComboBox()
        self.ref_combo.addItems(['平均参考', '中位数参考'])
        ref_layout.addWidget(self.ref_combo)
        preprocess_layout.addLayout(ref_layout)
        
        layout.addWidget(preprocess_group)
        
        gfp_group = QGroupBox('GFP峰值提取')
        gfp_layout = QVBoxLayout(gfp_group)
        
        peak_layout = QHBoxLayout()
        peak_layout.addWidget(QLabel('最小峰间距(ms):'))
        self.peak_distance_spin = QSpinBox()
        self.peak_distance_spin.setRange(10, 100)
        self.peak_distance_spin.setValue(20)
        peak_layout.addWidget(self.peak_distance_spin)
        gfp_layout.addLayout(peak_layout)
        
        layout.addWidget(gfp_group)
        
        cluster_group = QGroupBox('聚类参数')
        cluster_layout = QVBoxLayout(cluster_group)
        
        k_layout = QHBoxLayout()
        k_layout.addWidget(QLabel('聚类数(k):'))
        self.k_spin = QSpinBox()
        self.k_spin.setRange(2, 10)
        self.k_spin.setValue(4)
        k_layout.addWidget(self.k_spin)
        cluster_layout.addLayout(k_layout)
        
        n_init_layout = QHBoxLayout()
        n_init_layout.addWidget(QLabel('初始化次数:'))
        self.n_init_spin = QSpinBox()
        self.n_init_spin.setRange(10, 500)
        self.n_init_spin.setValue(100)
        n_init_layout.addWidget(self.n_init_spin)
        cluster_layout.addLayout(n_init_layout)
        
        layout.addWidget(cluster_group)
        
        advanced_group = QGroupBox('高级分析')
        advanced_layout = QVBoxLayout(advanced_group)
        
        self.enable_nonlinear_check = QCheckBox('启用非线性动力学分析')
        self.enable_nonlinear_check.setChecked(True)
        advanced_layout.addWidget(self.enable_nonlinear_check)
        
        self.enable_source_check = QCheckBox('启用皮层源重建分析')
        self.enable_source_check.setChecked(False)
        self.enable_source_check.toggled.connect(self._toggle_source_params)
        advanced_layout.addWidget(self.enable_source_check)
        
        source_param_layout = QVBoxLayout()
        source_param_layout.setContentsMargins(20, 0, 0, 0)
        
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel('源重建方法:'))
        self.source_method_combo = QComboBox()
        self.source_method_combo.addItems(['eLORETA', 'Minimum Norm', 'dSPM'])
        method_layout.addWidget(self.source_method_combo)
        source_param_layout.addLayout(method_layout)
        
        lambda_layout = QHBoxLayout()
        lambda_layout.addWidget(QLabel('正则化参数:'))
        self.lambda_spin = QDoubleSpinBox()
        self.lambda_spin.setRange(0.001, 1.0)
        self.lambda_spin.setValue(0.1)
        self.lambda_spin.setSingleStep(0.01)
        lambda_layout.addWidget(self.lambda_spin)
        source_param_layout.addLayout(lambda_layout)
        
        n_sources_layout = QHBoxLayout()
        n_sources_layout.addWidget(QLabel('源点数量:'))
        self.n_sources_spin = QSpinBox()
        self.n_sources_spin.setRange(100, 1000)
        self.n_sources_spin.setValue(200)
        n_sources_layout.addWidget(self.n_sources_spin)
        source_param_layout.addLayout(n_sources_layout)
        
        source_param_widget = QWidget()
        source_param_widget.setLayout(source_param_layout)
        source_param_widget.setEnabled(False)
        self.source_param_widget = source_param_widget
        advanced_layout.addWidget(source_param_widget)
        
        layout.addWidget(advanced_group)
        
        analysis_group = QGroupBox('分析控制')
        analysis_layout = QVBoxLayout(analysis_group)
        
        self.analyze_btn = QPushButton('开始分析')
        self.analyze_btn.clicked.connect(self.start_analysis)
        self.analyze_btn.setFont(QFont('Arial', 11, QFont.Bold))
        self.analyze_btn.setMinimumHeight(50)
        self.analyze_btn.setStyleSheet('''
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        ''')
        self.analyze_btn.setEnabled(False)
        analysis_layout.addWidget(self.analyze_btn)
        
        layout.addWidget(analysis_group)
        
        export_group = QGroupBox('导出结果')
        export_layout = QVBoxLayout(export_group)
        
        self.export_csv_btn = QPushButton('导出CSV统计结果')
        self.export_csv_btn.clicked.connect(self.export_csv)
        self.export_csv_btn.setEnabled(False)
        export_layout.addWidget(self.export_csv_btn)
        
        self.export_svg_btn = QPushButton('导出SVG地形图')
        self.export_svg_btn.clicked.connect(self.export_svg)
        self.export_svg_btn.setEnabled(False)
        export_layout.addWidget(self.export_svg_btn)
        
        self.export_all_btn = QPushButton('导出全部结果')
        self.export_all_btn.clicked.connect(self.export_all)
        self.export_all_btn.setEnabled(False)
        export_layout.addWidget(self.export_all_btn)
        
        layout.addWidget(export_group)
        
        layout.addStretch()
        
        return panel

    def _create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        self.tabs = QTabWidget()
        
        self.info_tab = self._create_info_tab()
        self.signal_tab = self._create_plot_tab('EEG信号')
        self.gfp_tab = self._create_plot_tab('GFP分析')
        self.topomap_tab = self._create_plot_tab('微状态地形图')
        self.sequence_tab = self._create_plot_tab('微状态序列')
        self.stats_tab = self._create_stats_tab()
        self.transition_tab = self._create_plot_tab('转换概率矩阵')
        self.nonlinear_tab = self._create_nonlinear_tab()
        self.source_tab = self._create_plot_tab('皮层源微状态')
        self.group_tab = self._create_group_stats_tab()
        
        self.tabs.addTab(self.info_tab, '数据信息')
        self.tabs.addTab(self.signal_tab, 'EEG信号')
        self.tabs.addTab(self.gfp_tab, 'GFP分析')
        self.tabs.addTab(self.topomap_tab, '地形图')
        self.tabs.addTab(self.sequence_tab, '状态序列')
        self.tabs.addTab(self.stats_tab, '统计结果')
        self.tabs.addTab(self.transition_tab, '转换矩阵')
        self.tabs.addTab(self.nonlinear_tab, '非线性动力学')
        self.tabs.addTab(self.source_tab, '皮层源分析')
        self.tabs.addTab(self.group_tab, '组水平统计')
        
        layout.addWidget(self.tabs)
        
        return panel

    def _create_nonlinear_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.nonlinear_table = QTableWidget()
        self.nonlinear_table.setColumnCount(2)
        self.nonlinear_table.setHorizontalHeaderLabels(['指标', '数值'])
        self.nonlinear_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.nonlinear_table.verticalHeader().setVisible(False)
        layout.addWidget(self.nonlinear_table)
        
        return widget

    def _create_group_stats_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group_control_layout = QHBoxLayout()
        
        self.load_group1_btn = QPushButton('加载组1数据')
        self.load_group1_btn.clicked.connect(lambda: self.load_group_data(1))
        group_control_layout.addWidget(self.load_group1_btn)
        
        self.load_group2_btn = QPushButton('加载组2数据')
        self.load_group2_btn.clicked.connect(lambda: self.load_group_data(2))
        group_control_layout.addWidget(self.load_group2_btn)
        
        self.run_group_stats_btn = QPushButton('执行组水平统计')
        self.run_group_stats_btn.clicked.connect(self.run_group_statistics)
        group_control_layout.addWidget(self.run_group_stats_btn)
        
        layout.addLayout(group_control_layout)
        
        self.group_stats_table = QTableWidget()
        self.group_stats_table.setColumnCount(6)
        self.group_stats_table.setHorizontalHeaderLabels(
            ['指标', '统计量', 'P值', '校正P值', '效应量', '显著性']
        )
        self.group_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.group_stats_table.verticalHeader().setVisible(False)
        layout.addWidget(self.group_stats_table)
        
        self.group1_data = None
        self.group2_data = None
        self.group1_files = []
        self.group2_files = []
        
        return widget

    def _create_info_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setFont(QFont('Consolas', 10))
        self.info_text.setPlaceholderText('加载数据后，此处将显示数据信息...')
        layout.addWidget(self.info_text)
        
        return widget

    def _create_plot_tab(self, title):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.figure = plt.figure(figsize=(10, 8))
        canvas = FigureCanvas(self.figure)
        toolbar = NavigationToolbar(canvas, self)
        
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        
        return widget

    def _create_stats_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(5)
        self.stats_table.setHorizontalHeaderLabels(['指标', '微状态1', '微状态2', '微状态3', '微状态4'])
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stats_table.verticalHeader().setVisible(False)
        layout.addWidget(self.stats_table)
        
        return widget

    def load_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, '选择EDF文件', '', 'EDF Files (*.edf);;All Files (*)'
        )
        
        if filepath:
            self.filepath = filepath
            self.file_label.setText(f'已选择: {filepath.split("/")[-1]}')
            self.file_label.setStyleSheet('color: black;')
            self.analyze_btn.setEnabled(True)
            
            try:
                loader = EEGDataLoader()
                data, ch_names, sfreq, times = loader.load_edf(filepath)
                info = loader.get_info()
                
                info_text = f"""
=== EEG数据信息 ===

文件路径: {filepath}

--- 基本信息 ---
通道数: {info['n_channels']}
采样率: {info['sfreq']} Hz
数据时长: {info['duration']:.2f} 秒
采样点数: {info['n_samples']}

--- 通道列表 ---
{', '.join(info['ch_names'][:16])}
{', '.join(info['ch_names'][16:])}
                """
                self.info_text.setText(info_text)
                
            except Exception as e:
                QMessageBox.critical(self, '错误', f'加载数据失败: {str(e)}')
                self.analyze_btn.setEnabled(False)

    def start_analysis(self):
        source_method_map = {'eLORETA': 'eloreta', 'Minimum Norm': 'minimum_norm', 'dSPM': 'dSPM'}
        params = {
            'low_freq': self.low_freq_spin.value(),
            'high_freq': self.high_freq_spin.value(),
            'reference_type': 'average' if self.ref_combo.currentIndex() == 0 else 'median',
            'min_peak_distance': self.peak_distance_spin.value(),
            'n_clusters': self.k_spin.value(),
            'n_init': self.n_init_spin.value(),
            'max_iter': 1000,
            'enable_nonlinear': self.enable_nonlinear_check.isChecked(),
            'enable_source': self.enable_source_check.isChecked(),
            'source_method': source_method_map[self.source_method_combo.currentText()],
            'lambda_reg': self.lambda_spin.value(),
            'n_sources': self.n_sources_spin.value()
        }
        
        self.progress_dialog = QProgressDialog('正在分析...', '取消', 0, 100, self)
        self.progress_dialog.setWindowTitle('分析进度')
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.show()
        
        self.analysis_thread = AnalysisThread(self.filepath, params)
        self.analysis_thread.progress.connect(self.update_progress)
        self.analysis_thread.finished.connect(self.analysis_finished)
        self.analysis_thread.error.connect(self.analysis_error)
        self.analysis_thread.start()

    def update_progress(self, value, message):
        self.progress_dialog.setValue(value)
        self.progress_dialog.setLabelText(message)

    def analysis_finished(self, results):
        self.results = results
        self.progress_dialog.close()
        
        self.export_csv_btn.setEnabled(True)
        self.export_svg_btn.setEnabled(True)
        self.export_all_btn.setEnabled(True)
        
        self._update_plots()
        self._update_stats_table()
        
        if results.get('nonlinear_results') is not None:
            self._update_nonlinear_table(results['nonlinear_results'])
        
        if results.get('source_results') is not None:
            self._plot_source_microstates(results['source_results'])
        
        self.info_text.append(f"\n=== 分析结果 ===\n")
        self.info_text.append(f"解释方差: {results['explained_variance']:.4f} ({results['explained_variance']*100:.2f}%)")
        self.info_text.append(f"GFP峰值数量: {len(results['peak_indices'])}")
        self.info_text.append(f"微状态序列长度: {len(results['microstate_sequence'])}")
        
        if results.get('nonlinear_results') is not None:
            self.info_text.append(f"\n--- 非线性动力学指标 ---")
            nl = results['nonlinear_results']
            self.info_text.append(f"Lempel-Ziv复杂度: {nl['lempel_ziv_complexity']:.4f}")
            self.info_text.append(f"样本熵: {nl['sample_entropy']:.4f}")
            self.info_text.append(f"香农熵: {nl['shannon_entropy']:.4f}")
            self.info_text.append(f"Hurst指数: {nl['hurst_exponent']:.4f}")
            self.info_text.append(f"DFA α: {nl['dfa_alpha']:.4f}")
            self.info_text.append(f"复杂度指数: {nl['complexity_index']:.4f}")
        
        QMessageBox.information(self, '完成', '微状态分析已完成!')

    def analysis_error(self, error_msg):
        self.progress_dialog.close()
        QMessageBox.critical(self, '错误', f'分析失败: {error_msg}')

    def _update_plots(self):
        self._plot_eeg_signal()
        self._plot_gfp()
        self._plot_topomaps()
        self._plot_sequence()
        self._plot_transition_matrix()

    def _plot_eeg_signal(self):
        self.tabs.setCurrentWidget(self.signal_tab)
        canvas = self.signal_tab.findChild(FigureCanvas)
        if canvas:
            fig = canvas.figure
            fig.clear()
            ax = fig.add_subplot(111)
            
            n_samples = len(self.results['times'])
            downsample = max(1, n_samples // 5000)
            
            self.visualizer.plot_eeg_signal(
                self.results['processed_data'][:, ::downsample],
                self.results['times'][::downsample],
                self.results['ch_names'],
                n_channels=5,
                ax=ax
            )
            fig.tight_layout()
            canvas.draw()

    def _plot_gfp(self):
        canvas = self.gfp_tab.findChild(FigureCanvas)
        if canvas:
            fig = canvas.figure
            fig.clear()
            ax = fig.add_subplot(111)
            
            n_samples = len(self.results['times'])
            downsample = max(1, n_samples // 5000)
            
            peak_indices_downsampled = []
            for peak_idx in self.results['peak_indices']:
                if peak_idx % downsample == 0:
                    peak_indices_downsampled.append(peak_idx // downsample)
            
            self.visualizer.plot_gfp_with_peaks(
                self.results['gfp'][::downsample],
                np.array(peak_indices_downsampled),
                self.results['times'][::downsample],
                ax=ax
            )
            fig.tight_layout()
            canvas.draw()

    def _plot_topomaps(self):
        canvas = self.topomap_tab.findChild(FigureCanvas)
        if canvas:
            fig = canvas.figure
            self.visualizer.plot_microstate_topomaps(
                self.results['templates'],
                self.results['pos'],
                fig=fig
            )
            canvas.draw()

    def _plot_sequence(self):
        canvas = self.sequence_tab.findChild(FigureCanvas)
        if canvas:
            fig = canvas.figure
            fig.clear()
            ax = fig.add_subplot(111)
            
            n_samples = len(self.results['times'])
            start_idx = int(0.1 * n_samples)
            end_idx = int(0.15 * n_samples)
            
            self.visualizer.plot_microstate_sequence(
                self.results['microstate_sequence'][start_idx:end_idx],
                self.results['times'][start_idx:end_idx],
                self.results['sfreq'],
                ax=ax,
                show_gfp=True,
                gfp=self.results['gfp'][start_idx:end_idx]
            )
            fig.tight_layout()
            canvas.draw()

    def _plot_transition_matrix(self):
        canvas = self.transition_tab.findChild(FigureCanvas)
        if canvas:
            fig = canvas.figure
            fig.clear()
            ax = fig.add_subplot(111)
            
            self.visualizer.plot_transition_matrix(
                self.results['stats']['transition_probabilities'],
                ax=ax
            )
            fig.tight_layout()
            canvas.draw()

    def _update_stats_table(self):
        stats = self.results['stats']
        self.stats_table.setRowCount(4)
        
        self.stats_table.setItem(0, 0, QTableWidgetItem('平均持续时间(ms)'))
        self.stats_table.setItem(1, 0, QTableWidgetItem('持续时间标准差(ms)'))
        self.stats_table.setItem(2, 0, QTableWidgetItem('出现频率(%)'))
        self.stats_table.setItem(3, 0, QTableWidgetItem('出现次数'))
        
        total_samples = len(self.results['microstate_sequence'])
        
        for i in range(4):
            self.stats_table.setItem(0, i + 1, QTableWidgetItem(f"{stats['mean_durations'][i]:.2f}"))
            self.stats_table.setItem(1, i + 1, QTableWidgetItem(f"{stats['std_durations'][i]:.2f}"))
            self.stats_table.setItem(2, i + 1, QTableWidgetItem(f"{stats['frequencies'][i] * 100:.2f}"))
            self.stats_table.setItem(3, i + 1, QTableWidgetItem(f"{int(stats['frequencies'][i] * total_samples)}"))

    def export_csv(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, '导出CSV统计结果', '', 'CSV Files (*.csv)'
        )
        if filepath:
            try:
                self.exporter.export_statistics_csv(self.results['stats'], filepath)
                QMessageBox.information(self, '成功', f'CSV文件已导出到:\n{filepath}')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'导出失败: {str(e)}')

    def export_svg(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, '导出SVG地形图', '', 'SVG Files (*.svg)'
        )
        if filepath:
            try:
                self.exporter.export_topomaps_svg(
                    self.results['templates'], 
                    self.results['pos'], 
                    filepath
                )
                QMessageBox.information(self, '成功', f'SVG文件已导出到:\n{filepath}')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'导出失败: {str(e)}')

    def export_all(self):
        dirpath = QFileDialog.getExistingDirectory(self, '选择导出目录')
        if dirpath:
            try:
                self.exporter.export_all_csv(self.results, dirpath)
                self.exporter.export_all_svg(self.results, dirpath)
                QMessageBox.information(self, '成功', f'所有结果已导出到:\n{dirpath}')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'导出失败: {str(e)}')

    def _update_nonlinear_table(self, nonlinear_results):
        metrics = [
            ('Lempel-Ziv复杂度', 'lempel_ziv_complexity', '{:.4f}'),
            ('样本熵', 'sample_entropy', '{:.4f}'),
            ('香农熵', 'shannon_entropy', '{:.4f}'),
            ('马尔可夫熵率', 'markov_entropy_rate', '{:.4f}'),
            ('Hurst指数', 'hurst_exponent', '{:.4f}'),
            ('DFA α指数', 'dfa_alpha', '{:.4f}'),
            ('复杂度指数', 'complexity_index', '{:.4f}')
        ]
        
        self.nonlinear_table.setRowCount(len(metrics))
        for row, (name, key, fmt) in enumerate(metrics):
            self.nonlinear_table.setItem(row, 0, QTableWidgetItem(name))
            value = nonlinear_results.get(key, None)
            if value is not None:
                self.nonlinear_table.setItem(row, 1, QTableWidgetItem(fmt.format(value)))
            else:
                self.nonlinear_table.setItem(row, 1, QTableWidgetItem('N/A'))

    def _plot_source_microstates(self, source_results):
        canvas = self.source_tab.findChild(FigureCanvas)
        if canvas:
            fig = canvas.figure
            fig.clear()
            
            templates = source_results['cortical_templates']
            source_space = source_results['source_space']
            
            n_clusters = templates.shape[1]
            for i in range(n_clusters):
                ax = fig.add_subplot(1, n_clusters, i + 1, projection='3d')
                
                template = templates[:, i]
                vmax = np.max(np.abs(template))
                
                sc = ax.scatter(
                    source_space[:, 0], source_space[:, 1], source_space[:, 2],
                    c=template, cmap='RdBu_r', vmin=-vmax, vmax=vmax, s=20
                )
                
                ax.set_xlabel('X')
                ax.set_ylabel('Y')
                ax.set_zlabel('Z')
                ax.set_title(f'皮层微状态 {i+1}', fontsize=10)
                ax.set_box_aspect([1, 1, 0.6])
            
            fig.colorbar(sc, ax=fig.get_axes(), shrink=0.5, pad=0.05)
            fig.tight_layout()
            canvas.draw()

    def load_group_data(self, group_num):
        filepaths, _ = QFileDialog.getOpenFileNames(
            self, f'选择组{group_num}的EDF文件', '', 'EDF Files (*.edf)'
        )
        
        if not filepaths:
            return
        
        if group_num == 1:
            self.group1_files = filepaths
            self.load_group1_btn.setText(f'组1: {len(filepaths)}个文件')
        else:
            self.group2_files = filepaths
            self.load_group2_btn.setText(f'组2: {len(filepaths)}个文件')
        
        if self.group1_files and self.group2_files:
            self.run_group_stats_btn.setEnabled(True)
        else:
            self.run_group_stats_btn.setEnabled(False)

    def run_group_statistics(self):
        if not self.group1_files or not self.group2_files:
            QMessageBox.warning(self, '提示', '请先加载两组数据!')
            return
        
        progress = QProgressDialog('正在执行组水平统计...', '取消', 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        try:
            group1_features = self._extract_group_features(self.group1_files, progress, 0, 50)
            group2_features = self._extract_group_features(self.group2_files, progress, 50, 50)
            
            progress.setValue(70)
            progress.setLabelText('正在进行统计检验...')
            
            group_stats = GroupStatistics(n_permutations=1000, alpha=0.05)
            results = group_stats.compare_groups(
                group1_features, group2_features,
                paired=False,
                stat_func='t_test',
                correction_method='fdr_bh',
                permutation=True
            )
            
            self._update_group_stats_table(results)
            
            progress.setValue(100)
            QMessageBox.information(self, '完成', '组水平统计分析已完成!')
            
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, '错误', f'统计分析失败: {str(e)}')

    def _extract_group_features(self, files, progress, start_progress, total_progress):
        n_files = len(files)
        features_list = []
        
        feature_names = [
            'mean_dur_1', 'mean_dur_2', 'mean_dur_3', 'mean_dur_4',
            'freq_1', 'freq_2', 'freq_3', 'freq_4',
            'lempel_ziv', 'sample_entropy', 'shannon_entropy',
            'hurst', 'dfa_alpha', 'complexity_index',
            'explained_variance', 'gfp_mean', 'gfp_std'
        ]
        
        for i, filepath in enumerate(files):
            try:
                loader = EEGDataLoader()
                data, ch_names, sfreq, times = loader.load_edf(filepath)
                pos = loader.get_channel_positions()
                
                preprocessor = Preprocessor(low_freq=1.0, high_freq=40.0, sfreq=sfreq)
                processed_data = preprocessor.preprocess(data, reference_type='average')
                
                gfp_analyzer = GFPAnalyzer(sfreq=sfreq)
                gfp, peak_indices, peak_times, peak_data, _ = gfp_analyzer.analyze(processed_data)
                
                clustering = MicrostateClustering(n_clusters=4, n_init=50, max_iter=1000)
                templates, labels = clustering.fit(peak_data)
                
                template_fitting = TemplateFitting(templates, sfreq=sfreq)
                microstate_sequence, _ = template_fitting.fit(processed_data)
                
                stats_analyzer = StatisticsAnalyzer(sfreq=sfreq, n_clusters=4)
                stats = stats_analyzer.analyze(microstate_sequence)
                
                nonlinear_analyzer = NonlinearDynamicsAnalyzer(n_clusters=4)
                nonlinear = nonlinear_analyzer.analyze(
                    microstate_sequence, transition_matrix=stats['transition_probabilities']
                )
                
                features = np.array([
                    stats['mean_durations'][0], stats['mean_durations'][1], 
                    stats['mean_durations'][2], stats['mean_durations'][3],
                    stats['frequencies'][0], stats['frequencies'][1],
                    stats['frequencies'][2], stats['frequencies'][3],
                    nonlinear['lempel_ziv_complexity'], nonlinear['sample_entropy'],
                    nonlinear['shannon_entropy'], nonlinear['hurst_exponent'],
                    nonlinear['dfa_alpha'], nonlinear['complexity_index'],
                    clustering.explained_variance, np.mean(gfp), np.std(gfp)
                ])
                
                features_list.append(features)
                
                progress_val = start_progress + int((i + 1) / n_files * total_progress)
                progress.setValue(progress_val)
                progress.setLabelText(f'正在处理组数据 {i+1}/{n_files}...')
                
            except Exception as e:
                print(f"处理文件 {filepath} 时出错: {e}")
                continue
        
        return np.array(features_list)

    def _update_group_stats_table(self, results):
        feature_names = [
            '平均持续时间_状态1', '平均持续时间_状态2', '平均持续时间_状态3', '平均持续时间_状态4',
            '出现频率_状态1', '出现频率_状态2', '出现频率_状态3', '出现频率_状态4',
            'Lempel-Ziv复杂度', '样本熵', '香农熵',
            'Hurst指数', 'DFA α', '复杂度指数',
            '解释方差', 'GFP均值', 'GFP标准差'
        ]
        
        self.group_stats_table.setRowCount(len(feature_names))
        
        for row in range(len(feature_names)):
            self.group_stats_table.setItem(row, 0, QTableWidgetItem(feature_names[row]))
            self.group_stats_table.setItem(row, 1, QTableWidgetItem(f"{results['statistic'][row]:.4f}"))
            self.group_stats_table.setItem(row, 2, QTableWidgetItem(f"{results['p_values'][row]:.4f}"))
            self.group_stats_table.setItem(row, 3, QTableWidgetItem(f"{results['p_values_corrected'][row]:.4f}"))
            self.group_stats_table.setItem(row, 4, QTableWidgetItem(f"{results['effect_size'][row]:.4f}"))
            sig = '***' if results['significant'][row] else ''
            self.group_stats_table.setItem(row, 5, QTableWidgetItem(sig))
