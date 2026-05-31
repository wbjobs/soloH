import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


class Exporter:
    def __init__(self):
        pass

    def export_statistics_csv(self, stats, filepath):
        mean_durations = stats['mean_durations']
        std_durations = stats['std_durations']
        frequencies = stats['frequencies']
        transition_probs = stats['transition_probabilities']
        transition_counts = stats['transition_counts']

        summary_data = {
            '微状态': [f'微状态 {i + 1}' for i in range(4)],
            '平均持续时间(ms)': mean_durations,
            '持续时间标准差(ms)': std_durations,
            '出现频率(%)': frequencies * 100
        }
        summary_df = pd.DataFrame(summary_data)

        transition_data = []
        for i in range(4):
            for j in range(4):
                transition_data.append({
                    '当前状态': f'微状态 {i + 1}',
                    '下一个状态': f'微状态 {j + 1}',
                    '转换次数': int(transition_counts[i, j]),
                    '转换概率': transition_probs[i, j]
                })
        transition_df = pd.DataFrame(transition_data)

        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write('微状态统计摘要\n')
            summary_df.to_csv(f, index=False)
            f.write('\n微状态转换矩阵\n')
            transition_df.to_csv(f, index=False)

        return True

    def export_sequence_csv(self, microstate_sequence, times, sfreq, filepath):
        data = {
            '时间(s)': times,
            '样本索引': np.arange(len(times)),
            '微状态': microstate_sequence + 1
        }
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        return True

    def export_durations_csv(self, durations, filepath):
        df = pd.DataFrame(durations)
        df['state'] = df['state'] + 1
        df = df.rename(columns={
            'state': '微状态',
            'start_idx': '开始样本索引',
            'end_idx': '结束样本索引',
            'duration_samples': '持续样本数',
            'duration_ms': '持续时间(ms)'
        })
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        return True

    def export_templates_csv(self, templates, ch_names, filepath):
        data = {'通道名称': ch_names}
        for i in range(templates.shape[1]):
            data[f'微状态 {i + 1}'] = templates[:, i]
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        return True

    def export_topomaps_svg(self, templates, pos, filepath, titles=None):
        from .visualization import Visualizer
        
        visualizer = Visualizer()
        fig = visualizer.plot_microstate_topomaps(templates, pos, titles)
        fig.savefig(filepath, format='svg', dpi=300, bbox_inches='tight')
        plt.close(fig)
        return True

    def export_sequence_svg(self, microstate_sequence, times, sfreq, filepath, gfp=None):
        from .visualization import Visualizer
        
        visualizer = Visualizer()
        fig, ax = plt.subplots(figsize=(12, 3))
        visualizer.plot_microstate_sequence(microstate_sequence, times, sfreq, 
                                            ax=ax, show_gfp=gfp is not None, gfp=gfp)
        fig.savefig(filepath, format='svg', dpi=300, bbox_inches='tight')
        plt.close(fig)
        return True

    def export_transition_matrix_svg(self, transition_probs, filepath):
        from .visualization import Visualizer
        
        visualizer = Visualizer()
        fig, ax = plt.subplots(figsize=(6, 5))
        visualizer.plot_transition_matrix(transition_probs, ax=ax)
        fig.savefig(filepath, format='svg', dpi=300, bbox_inches='tight')
        plt.close(fig)
        return True

    def export_statistics_svg(self, stats, filepath):
        from .visualization import Visualizer
        
        visualizer = Visualizer()
        fig, ax = plt.subplots(figsize=(10, 6))
        visualizer.plot_statistics(stats, ax=ax)
        fig.savefig(filepath, format='svg', dpi=300, bbox_inches='tight')
        plt.close(fig)
        return True

    def export_all_csv(self, results, output_dir):
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        self.export_statistics_csv(results['stats'], 
                                   os.path.join(output_dir, 'statistics.csv'))
        self.export_sequence_csv(results['microstate_sequence'], 
                                 results['times'], results['sfreq'],
                                 os.path.join(output_dir, 'microstate_sequence.csv'))
        self.export_durations_csv(results['stats']['durations'], 
                                  os.path.join(output_dir, 'durations.csv'))
        self.export_templates_csv(results['templates'], results['ch_names'],
                                  os.path.join(output_dir, 'templates.csv'))
        
        return True

    def export_all_svg(self, results, output_dir):
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        self.export_topomaps_svg(results['templates'], results['pos'],
                                 os.path.join(output_dir, 'topomaps.svg'))
        self.export_sequence_svg(results['microstate_sequence'], 
                                 results['times'], results['sfreq'],
                                 os.path.join(output_dir, 'sequence.svg'),
                                 gfp=results['gfp'])
        self.export_transition_matrix_svg(results['stats']['transition_probabilities'],
                                          os.path.join(output_dir, 'transition_matrix.svg'))
        self.export_statistics_svg(results['stats'],
                                   os.path.join(output_dir, 'statistics.svg'))
        
        return True
