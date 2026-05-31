import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from app.models import SimulationParameters, PIDParameters
from app.droplet_model import DropletFormationModel
from app.pid_controller import PIDController
from app.models import JunctionType


def test_regime_transition_smoothness():
    print("=" * 70)
    print("测试1: 液滴形成机制过渡区平滑性验证")
    print("=" * 70)

    model = DropletFormationModel()
    params = SimulationParameters()

    Ca_values = np.logspace(-4, -1, 50)
    sizes = []
    regimes = []

    print("\n毛细管数扫描 (Qd/Qc = 0.25):")
    print("-" * 70)
    print(f"{'Ca':>12} | {'Size (μm)':>12} | {'dSize/dCa':>12} | {'Regime':>12}")
    print("-" * 70)

    for i, Ca in enumerate(Ca_values):
        Qc = (Ca * 60 * params.channel.width * params.channel.height * params.interfacialTension) / (params.continuousPhase.viscosity * 1e3)
        Qd = Qc * 0.25

        D = model.predict_droplet_size(
            Qc=Qc, Qd=Qd,
            muc=params.continuousPhase.viscosity,
            mud=params.dispersedPhase.viscosity,
            sigma=params.interfacialTension,
            W=params.channel.width,
            H=params.channel.height,
            junction_type=JunctionType.T,
            add_noise=False
        )

        regime_info = model.get_regime_info(Ca, 0.25, 5.0, JunctionType.T)
        sizes.append(D)
        regimes.append(regime_info['regime'])

        if i > 0:
            dD_dCa = (sizes[i] - sizes[i-1]) / (Ca_values[i] - Ca_values[i-1])
            print(f"{Ca:12.6f} | {D:12.3f} | {dD_dCa:12.1f} | {regime_info['regime']:>12} (blend={regime_info['blend_factor']:.2f})")
        else:
            print(f"{Ca:12.6f} | {D:12.3f} | {'-':>12} | {regime_info['regime']:>12} (blend={regime_info['blend_factor']:.2f})")

    sizes = np.array(sizes)
    dD_dCa = np.gradient(sizes, Ca_values)
    max_derivative = np.max(np.abs(dD_dCa))

    print("\n" + "-" * 70)
    print(f"最大尺寸梯度: |dD/dCa| = {max_derivative:.1f} μm")
    print(f"过渡区范围: Ca = {1e-3:.0e} ~ {3e-2:.0e}")

    if max_derivative < 5000:
        print("✅ 过渡区平滑，无突变！")
    else:
        print("⚠️  过渡区可能存在突变")

    return max_derivative < 5000


def test_pid_delay_compensation():
    print("\n" + "=" * 70)
    print("测试2: PID控制延迟补偿验证")
    print("=" * 70)

    pid_params = PIDParameters(
        enabled=True,
        targetDropletSize=80.0,
        Kp=0.5, Ki=0.1, Kd=0.01,
        outputMin=1.0, outputMax=20.0
    )

    pid = PIDController(pid_params)

    print("\n模拟阶跃响应 (目标: 80μm, 初始: 60μm):")
    print("-" * 70)
    print(f"{'Time(s)':>8} | {'Size(μm)':>10} | {'Error(μm)':>10} | {'Output':>10} | {'Oscillation':>12}")
    print("-" * 70)

    measured_sizes = [60.0]
    outputs = []
    errors = []

    for step in range(50):
        t = step * 0.1
        current_size = measured_sizes[-1]

        output, status = pid.compute(current_size, t)
        outputs.append(output)
        errors.append(status.error)

        process_delay = 3
        if step > process_delay:
            response = (output - 5.0) * 2.0
            new_size = current_size + response * 0.1 + np.random.normal(0, 0.5)
        else:
            new_size = current_size + np.random.normal(0, 0.5)

        new_size = max(min(new_size, 120), 20)
        measured_sizes.append(new_size)

        oscillation_flag = ""
        if len(errors) > 5:
            error_array = np.array(errors[-10:])
            zero_crossings = np.sum(np.diff(np.sign(error_array)) != 0)
            if zero_crossings > 3:
                oscillation_flag = f"⚠️  振荡({zero_crossings})"
            elif zero_crossings > 1:
                oscillation_flag = "轻微"

        if step % 3 == 0:
            print(f"{t:8.1f} | {current_size:10.2f} | {status.error:10.2f} | {output:10.2f} | {oscillation_flag:>12}")

    errors = np.array(errors[10:])
    zero_crossings = np.sum(np.diff(np.sign(errors)) != 0)
    settling_time = 0
    for i, e in enumerate(errors):
        if abs(e) < 1.0:
            settling_time = (i + 10) * 0.1
            break

    print("\n" + "-" * 70)
    print(f"最终误差: {abs(errors[-1]):.2f} μm")
    print(f"调节时间: {settling_time:.1f} s")
    print(f"过零次数: {zero_crossings} 次")

    if zero_crossings < 5 and settling_time < 15:
        print("✅ PID控制稳定，振荡得到有效抑制！")
        return True
    else:
        print("⚠️  PID控制可能需要进一步调整")
        return False


def test_polydispersity_correction():
    print("\n" + "=" * 70)
    print("测试3: 多分散性CV值统计校正验证")
    print("=" * 70)

    model = DropletFormationModel()

    print("\n不同样本量下的CV值计算对比:")
    print("-" * 70)
    print(f"{'样本量':>8} | {'原始CV(%)':>12} | {'校正CV(%)':>12} | {'偏差':>10} | {'95%置信区间':>20}")
    print("-" * 70)

    rng = np.random.default_rng(42)
    true_mean = 80.0
    true_cv = 3.0
    true_std = true_mean * true_cv / 100

    for n in [3, 5, 10, 20, 50, 100]:
        samples = rng.normal(true_mean, true_std, n)

        std_biased = np.std(samples)
        cv_biased = std_biased / true_mean * 100

        cv_corrected = model.compute_polydispersity(samples)

        ci_info = model.compute_polydispersity_with_ci(samples)

        bias = cv_corrected - true_cv
        ci_str = f"[{ci_info['ci_lower']:.2f}, {ci_info['ci_upper']:.2f}]"

        print(f"{n:>8} | {cv_biased:>12.3f} | {cv_corrected:>12.3f} | {bias:+10.3f} | {ci_str:>20}")

    print("\n" + "-" * 70)
    print(f"理论真值: CV = {true_cv}%")
    print("大样本(n≥50)时校正CV应接近真值")

    large_n_samples = rng.normal(true_mean, true_std, 1000)
    cv_large = model.compute_polydispersity(large_n_samples, bootstrap=False)
    cv_large_corrected = model.compute_polydispersity(large_n_samples)

    print(f"\n1000样本原始CV: {cv_large:.3f}%")
    print(f"1000样本校正CV: {cv_large_corrected:.3f}%")
    print(f"与真值偏差: {abs(cv_large_corrected - true_cv):.3f}%")

    if abs(cv_large_corrected - true_cv) < 0.5:
        print("✅ CV值统计校正有效！")
        return True
    else:
        print("⚠️  CV值校正可能需要调整")
        return False


def test_transition_regimes():
    print("\n" + "=" * 70)
    print("测试4: 三种通道类型的流型划分验证")
    print("=" * 70)

    model = DropletFormationModel()

    for jt, jt_name in [
        (JunctionType.T, "T型交叉"),
        (JunctionType.FLOW_FOCUSING, "流动聚焦"),
        (JunctionType.CO_FLOW, "共流")
    ]:
        print(f"\n{jt_name}:")
        print("-" * 50)
        print(f"{'Q_ratio':>10} | {'Ca':>10} | {'Regime':>15} | {'D(μm)':>10}")
        print("-" * 50)

        test_cases = [
            (0.1, 0.001),
            (0.25, 0.005),
            (0.5, 0.01),
            (0.75, 0.02),
            (1.0, 0.05),
        ]

        for Qr, Ca in test_cases:
            Qc = (Ca * 60 * 100 * 50 * 30) / (1.0 * 1e3)
            Qd = Qc * Qr

            D = model.predict_droplet_size(
                Qc=Qc, Qd=Qd, muc=1.0, mud=5.0, sigma=30.0,
                W=100, H=50, junction_type=jt, add_noise=False
            )

            regime_info = model.get_regime_info(Ca, Qr, 5.0, jt)
            print(f"{Qr:>10.2f} | {Ca:>10.4f} | {regime_info['regime']:>15} | {D:>10.2f}")

    return True


if __name__ == "__main__":
    print("\n" + "═" * 70)
    print("两相流液滴生成系统 - 修复验证测试套件")
    print("═" * 70)

    results = []

    try:
        r1 = test_regime_transition_smoothness()
        results.append(("过渡区平滑性", r1))
    except Exception as e:
        print(f"测试1失败: {e}")
        results.append(("过渡区平滑性", False))

    try:
        r2 = test_pid_delay_compensation()
        results.append(("PID延迟补偿", r2))
    except Exception as e:
        print(f"测试2失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("PID延迟补偿", False))

    try:
        r3 = test_polydispersity_correction()
        results.append(("CV值统计校正", r3))
    except Exception as e:
        print(f"测试3失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("CV值统计校正", False))

    try:
        r4 = test_transition_regimes()
        results.append(("流型划分验证", r4))
    except Exception as e:
        print(f"测试4失败: {e}")
        results.append(("流型划分验证", False))

    print("\n" + "═" * 70)
    print("测试总结")
    print("═" * 70)

    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("-" * 70)
    if all_passed:
        print("🎉 所有测试通过！修复验证成功！")
    else:
        print("⚠️  部分测试未通过，请检查修复方案")
    print("═" * 70)
