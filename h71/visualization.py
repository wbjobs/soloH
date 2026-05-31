import numpy as np
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.patches import Rectangle
from config import Config
from magnitude import estimate_magnitude_from_pd
from focal_mechanism import format_focal_mechanism
from warning_zone import format_warning_zone

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


ALERT_COLORS = {
    'normal': 'gray',
    'info': 'blue',
    'warning': 'orange',
    'alarm': 'red',
    'critical': 'darkred'
}


def plot_waveform(waveform_data, detections=None, title='三分量加速度波形', show=True, save_path=None):
    times = waveform_data.times
    data = waveform_data.data
    components = ['Z (垂直)', 'N (北)', 'E (东)']
    colors = ['black', 'blue', 'red']

    fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)

    for i, (ax, comp, color) in enumerate(zip(axes, components, colors)):
        ax.plot(times, data[:, i], color=color, linewidth=0.8, label=comp)
        ax.set_ylabel('加速度 (m/s²)')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        if detections:
            for det in detections:
                arr_time = det.get('arrival_time', det.get('global_arrival_time', 0))
                ax.axvline(x=arr_time, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
                if i == 0:
                    mag_text = f" M={det.get('magnitude', 'N/A'):.1f}" if 'magnitude' in det and not np.isnan(det.get('magnitude', np.nan)) else ""
                    conf_text = f" conf={det.get('overall_confidence', det.get('confidence', 0)):.2f}"
                    alert_level = det.get('alert_level', 'normal')
                    ax.text(arr_time, ax.get_ylim()[1] * 0.9,
                            f'P波{mag_text}{conf_text}',
                            color=ALERT_COLORS.get(alert_level, 'red'),
                            rotation=90, verticalalignment='top', fontsize=9)

    axes[0].set_title(title, fontsize=14, fontweight='bold')
    axes[-1].set_xlabel('时间 (s)')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()

    return fig, axes


def plot_sta_lta(times, sta, lta, sta_lta_ratio, threshold=None, detections=None,
                 title='STA/LTA检测结果', show=True, save_path=None):
    if threshold is None:
        threshold = Config.sta_lta_threshold

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)

    ax1.plot(times, sta, color='red', linewidth=0.8, label='STA')
    ax1.plot(times, lta, color='blue', linewidth=0.8, label='LTA')
    ax1.set_ylabel('振幅')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)
    ax1.set_title(title, fontsize=14, fontweight='bold')

    ax2.plot(times, sta_lta_ratio, color='green', linewidth=0.8, label='STA/LTA')
    ax2.axhline(y=threshold, color='red', linestyle='--', linewidth=1.5, label=f'阈值={threshold}')
    ax2.set_ylabel('STA/LTA比值')
    ax2.set_xlabel('时间 (s)')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    if detections:
        for det in detections:
            arr_time = det.get('arrival_time', det.get('global_arrival_time', 0))
            ax2.axvline(x=arr_time, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
            ratio = det.get('sta_lta_ratio', 0)
            ax2.scatter([arr_time], [ratio], color='red', s=50, zorder=5)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()

    return fig, (ax1, ax2)


def plot_polarization(times, rectilinearity, incidence_angle, azimuth,
                      detections=None, title='极化分析结果', show=True, save_path=None):
    fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)

    axes[0].plot(times, rectilinearity, color='purple', linewidth=0.8)
    axes[0].axhline(y=Config.rectilinearity_threshold, color='red', linestyle='--', alpha=0.7,
                   label=f'阈值={Config.rectilinearity_threshold}')
    axes[0].set_ylabel('直线度')
    axes[0].set_ylim(0, 1.05)
    axes[0].legend(loc='upper right')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_title(title, fontsize=14, fontweight='bold')

    axes[1].plot(times, incidence_angle, color='orange', linewidth=0.8)
    axes[1].set_ylabel('入射角 (°)')
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(times, azimuth, color='teal', linewidth=0.8)
    axes[2].set_ylabel('方位角 (°)')
    axes[2].set_xlabel('时间 (s)')
    axes[2].set_ylim(0, 360)
    axes[2].grid(True, alpha=0.3)

    if detections:
        for det in detections:
            arr_time = det.get('arrival_time', det.get('global_arrival_time', 0))
            for ax in axes:
                ax.axvline(x=arr_time, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
            if 'is_p_wave' in det:
                marker = '✓' if det['is_p_wave'] else '✗'
                color = 'green' if det['is_p_wave'] else 'red'
                axes[0].text(arr_time, 0.95, marker, color=color,
                            fontsize=14, ha='center', fontweight='bold')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()

    return fig, axes


def plot_combined_analysis(waveform_data, sta, lta, sta_lta_ratio,
                           polarization_params, detections=None,
                           title='地震波综合分析结果', show=True, save_path=None):
    fig = plt.figure(figsize=(16, 14))
    gs = gridspec.GridSpec(6, 1, height_ratios=[2, 2, 2, 1.5, 1.5, 1.5], hspace=0.3)

    times = waveform_data.times
    data = waveform_data.data
    components = ['Z (垂直)', 'N (北)', 'E (东)']
    colors = ['black', 'blue', 'red']

    event_type_markers = {
        'mainshock': '★',
        'aftershock': '◇',
        'foreshock': '◆',
        'possible_aftershock': '◇',
        'separate_event': '○',
        'single': '●'
    }

    for i in range(3):
        ax = plt.subplot(gs[i])
        ax.plot(times, data[:, i], color=colors[i], linewidth=0.8, label=components[i])
        ax.set_ylabel('加速度\n(m/s²)')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)
        if i == 0:
            ax.set_title(title, fontsize=14, fontweight='bold')

        if detections:
            for det in detections:
                arr_time = det.get('arrival_time', det.get('global_arrival_time', 0))
                alert_level = det.get('alert_level', 'normal')
                event_type = det.get('event_type', 'single')
                marker = event_type_markers.get(event_type, '●')

                ax.axvline(x=arr_time, color=ALERT_COLORS.get(alert_level, 'red'),
                          linestyle='--', linewidth=1.5, alpha=0.8)

                if 's_arrival_time' in det and det['s_arrival_time'] is not None:
                    s_time = det['s_arrival_time']
                    ax.axvline(x=s_time, color='green',
                              linestyle=':', linewidth=1.5, alpha=0.7)

                if i == 0:
                    mag = det.get('magnitude', np.nan)
                    mag_str = f' M{mag:.1f}' if not np.isnan(mag) else ''
                    delay_str = f' 延迟={det.get("detection_delay", 0):.1f}s' if 'detection_delay' in det else ''
                    conf = det.get('overall_confidence', det.get('confidence', 0))
                    et_str = f' [{event_type[:3]}]' if event_type != 'single' else ''

                    y_pos = ax.get_ylim()[1] * 0.95
                    ax.text(arr_time, y_pos,
                            f'{marker}P{mag_str}{delay_str}{et_str} conf={conf:.2f}',
                            color=ALERT_COLORS.get(alert_level, 'red'),
                            rotation=90, verticalalignment='top', fontsize=8)

                    if 's_arrival_time' in det and det['s_arrival_time'] is not None:
                        s_time = det['s_arrival_time']
                        ax.text(s_time, ax.get_ylim()[1] * 0.7,
                                f'S (S-P={s_time - arr_time:.1f}s)',
                                color='green',
                                rotation=90, verticalalignment='top', fontsize=7)

    ax_stalta = plt.subplot(gs[3])
    ax_stalta.plot(times, sta_lta_ratio, color='green', linewidth=0.8)
    ax_stalta.axhline(y=Config.sta_lta_threshold, color='red', linestyle='--', alpha=0.7,
                     label=f'STA/LTA阈值={Config.sta_lta_threshold}')
    ax_stalta.set_ylabel('STA/LTA')
    ax_stalta.legend(loc='upper right', fontsize=9)
    ax_stalta.grid(True, alpha=0.3)

    ax_rect = plt.subplot(gs[4])
    ax_rect.plot(times, polarization_params['rectilinearity'], color='purple', linewidth=0.8)
    ax_rect.axhline(y=Config.rectilinearity_threshold, color='red', linestyle='--', alpha=0.7,
                   label=f'直线度阈值={Config.rectilinearity_threshold}')
    ax_rect.set_ylabel('直线度')
    ax_rect.set_ylim(0, 1.05)
    ax_rect.legend(loc='upper right', fontsize=9)
    ax_rect.grid(True, alpha=0.3)

    ax_inc = plt.subplot(gs[5])
    ax_inc.plot(times, polarization_params['incidence_angle'], color='orange', linewidth=0.8)
    ax_inc.set_ylabel('入射角\n(°)')
    ax_inc.set_xlabel('时间 (s)')
    ax_inc.grid(True, alpha=0.3)

    if detections:
        for det in detections:
            arr_time = det.get('arrival_time', det.get('global_arrival_time', 0))
            alert_level = det.get('alert_level', 'normal')
            for ax in [ax_stalta, ax_rect, ax_inc]:
                ax.axvline(x=arr_time, color=ALERT_COLORS.get(alert_level, 'red'),
                          linestyle='--', linewidth=1.5, alpha=0.8)

            if 's_arrival_time' in det and det['s_arrival_time'] is not None:
                s_time = det['s_arrival_time']
                for ax in [ax_stalta, ax_rect, ax_inc]:
                    ax.axvline(x=s_time, color='green',
                              linestyle=':', linewidth=1.0, alpha=0.5)

    fig.tight_layout(rect=[0, 0, 1, 0.98])

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()

    return fig, gs


def plot_magnitude_estimation(times, displacement, pd, arrival_time, magnitude,
                              title='震级估算结果 (Pd法)', show=True, save_path=None):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))

    disp_horizontal = np.sqrt(displacement[:, 1] ** 2 + displacement[:, 2] ** 2) if displacement.ndim > 1 else displacement

    ax1.plot(times, disp_horizontal * 100, color='blue', linewidth=1.0)
    ax1.axvline(x=arrival_time, color='red', linestyle='--', label='P波到时')
    ax1.axhline(y=pd * 100, color='green', linestyle='--', label=f'Pd={pd*100:.3f} cm')

    window_end = arrival_time + Config.pd_window
    ax1.axvspan(arrival_time, window_end, alpha=0.2, color='yellow', label='Pd计算窗口')

    ax1.set_ylabel('水平位移 (cm)')
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    pd_values = np.logspace(-3, 1, 100)
    mag_values = Config.magnitude_calibration_a + Config.magnitude_calibration_b * np.log10(pd_values * 100)

    ax2.loglog(pd_values * 100, mag_values, 'b-', linewidth=1.5, label='震级标定曲线')
    ax2.scatter([pd * 100], [magnitude], color='red', s=100, zorder=5,
               label=f'当前: Pd={pd*100:.3f}cm, M={magnitude:.1f}')
    ax2.set_xlabel('Pd (cm)')
    ax2.set_ylabel('预估震级 M')
    ax2.grid(True, alpha=0.3, which='both')
    ax2.legend(loc='lower right')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()

    return fig, (ax1, ax2)


def plot_detection_performance(detection_delays, title='检测延迟分布', show=True, save_path=None):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.hist(detection_delays, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
    ax1.axvline(x=np.mean(detection_delays), color='red', linestyle='--', linewidth=2,
               label=f'均值={np.mean(detection_delays):.2f}s')
    ax1.set_xlabel('检测延迟 (s)')
    ax1.set_ylabel('频数')
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.boxplot(detection_delays, vert=True, patch_artist=True,
               boxprops=dict(facecolor='skyblue', alpha=0.7))
    ax2.set_ylabel('检测延迟 (s)')
    ax2.set_title('延迟箱线图')
    ax2.grid(True, alpha=0.3)

    stats_text = f'均值: {np.mean(detection_delays):.2f}s\n' \
                 f'中位数: {np.median(detection_delays):.2f}s\n' \
                 f'最小值: {np.min(detection_delays):.2f}s\n' \
                 f'最大值: {np.max(detection_delays):.2f}s\n' \
                 f'标准差: {np.std(detection_delays):.2f}s'
    ax2.text(1.1, 0.5, stats_text, transform=ax2.transAxes,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            verticalalignment='center')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()

    return fig, (ax1, ax2)


def print_detection_summary(detections, true_p_arrival=None):
    print("\n" + "="*80)
    print("P波检测结果汇总")
    print("="*80)

    if not detections:
        print("未检测到P波到时")
        return

    for i, det in enumerate(detections, 1):
        arr_time = det.get('arrival_time', det.get('global_arrival_time', 0))
        print(f"\n检测 #{i}:")
        print(f"  P波到时:       {arr_time:.3f} s")

        if 's_arrival_time' in det and det['s_arrival_time'] is not None:
            s_time = det['s_arrival_time']
            print(f"  S波到时:       {s_time:.3f} s")
            print(f"  S-P间隔:       {s_time - arr_time:.3f} s")
            if 's_detection_info' in det:
                s_info = det['s_detection_info']
                print(f"  S波检测:       {s_info.get('method', 'N/A')}")
                if 'score' in s_info:
                    print(f"  S波检测得分:   {s_info['score']:.3f}")

        if true_p_arrival is not None:
            error = arr_time - true_p_arrival
            print(f"  真实到时:      {true_p_arrival:.3f} s")
            print(f"  到时误差:      {error:.3f} s")

        delay = det.get('detection_delay', None)
        if delay is not None:
            print(f"  检测延迟:      {delay:.3f} s")

        if 'event_type' in det:
            event_type_colors = {
                'mainshock': '主震',
                'aftershock': '余震',
                'foreshock': '前震',
                'possible_aftershock': '可能余震',
                'separate_event': '独立事件',
                'single': '单事件'
            }
            et = det['event_type']
            print(f"  事件类型:      {event_type_colors.get(et, et)}")
            if 'cluster_id' in det:
                print(f"  所属聚类:      #{det['cluster_id']}")
            if 'cluster_size' in det:
                print(f"  聚类大小:      {det['cluster_size']} 个事件")
            if 'time_since_mainshock' in det:
                print(f"  距主震时间:    {det['time_since_mainshock']:.2f} s")

        print(f"  STA/LTA比值:   {det.get('sta_lta_ratio', 'N/A'):.2f}")
        print(f"  置信度:        {det.get('overall_confidence', det.get('confidence', 'N/A')):.3f}")

        mag = det.get('magnitude', np.nan)
        if not np.isnan(mag):
            print(f"  预估震级:      M{mag:.2f} ± {det.get('uncertainty', 'N/A'):.2f}")
            if 'pd' in det:
                print(f"    Pd:          {det['pd']*100:.4f} cm")
            if 'tau_c' in det:
                print(f"    τc:          {det['tau_c']:.3f} s")
            if 'magnitude_pd' in det:
                print(f"    Pd法震级:    M{det['magnitude_pd']:.2f}")
            if 'magnitude_tau_c' in det:
                print(f"    τc法震级:    M{det['magnitude_tau_c']:.2f}")

        if 'corrections' in det:
            corr = det['corrections']
            swc = corr.get('s_wave_correction', {})
            if swc.get('method') == 's_wave_corrected':
                orig_mag = estimate_magnitude_from_pd(swc.get('original_pd', 0)) if 'original_pd' in swc else None
                if orig_mag is not None and not np.isnan(orig_mag):
                    print(f"  S波校正:       已应用 (震级降低{orig_mag - mag:.2f}级)")
                    print(f"    原始Pd:      {swc['original_pd']*100:.4f} cm")
                    print(f"    校正后Pd:    {corr.get('corrected_pd', det['pd'])*100:.4f} cm")
                    print(f"    PS间隔:      {swc.get('ps_interval', 'N/A'):.2f} s")
            elif swc.get('method') == 'estimated':
                print(f"  S波校正:       已应用（估算S波）")
            else:
                print(f"  S波校正:       未应用 ({swc.get('method', 'N/A')})")

            sc = corr.get('site_correction', {})
            if sc.get('correction_factor', 1.0) != 1.0:
                print(f"  场地校正:      已应用")
                print(f"    场地类别:    {sc.get('site_class', 'N/A')}")
                print(f"    校正因子:    {sc.get('correction_factor', 1.0):.3f}")
            elif sc.get('method') == 'disabled':
                print(f"  场地校正:       已禁用")
            else:
                print(f"  场地校正:       无需校正 (C类场地)")

        if 'is_p_wave' in det:
            print(f"  P波验证:       {'通过 ✓' if det['is_p_wave'] else '未通过 ✗'}")
            print(f"  直线度:        {det.get('rectilinearity', 'N/A'):.3f}")
            print(f"  极化度:        {det.get('degree_of_polarization', 'N/A'):.3f}")
            print(f"  入射角:        {det.get('incidence_angle', 'N/A'):.1f}°")
            print(f"  方位角:        {det.get('azimuth', 'N/A'):.1f}°")

        print(f"  报警级别:      {det.get('alert_level', 'normal').upper()}")

        if 'method' in det:
            method_names = {
                'sta_lta': 'STA/LTA',
                'cnn_lstm': 'CNN+LSTM深度学习',
                'hybrid': '混合检测'
            }
            method = det['method']
            print(f"  检测方法:      {method_names.get(method, method)}")
            if 'detection_methods' in det:
                methods = [method_names.get(m, m) for m in det['detection_methods']]
                print(f"    融合方法:    {', '.join(methods)}")
            if 'dl_confidence' in det:
                print(f"    DL置信度:    {det['dl_confidence']:.3f}")

        if 'focal_mechanism' in det:
            fm_lines = format_focal_mechanism(det['focal_mechanism'])
            for line in fm_lines:
                print(line)

        if 'warning_zone' in det:
            wz_lines = format_warning_zone(det['warning_zone'])
            for line in wz_lines:
                print(line)

    print("\n" + "="*80)
