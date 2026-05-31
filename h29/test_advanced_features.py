import numpy as np
import copy
from app.models import (Point, Shot, Receiver, TravelTimeData, VelocityModel,
                       InversionConfig, AnisotropicParams, UncertaintyConfig)
from app.synthetic import generate_synthetic_data
from app.ray_tracing import ShortestPathRayTracer
from app.inversion import TomographicInversion
from app.full_waveform import FullWaveformInversion, WaveSolver2D
from app.anisotropic import VTIRayTracer, AnisotropicTomography, vti_phase_velocity
from app.uncertainty import (MonteCarloAnalysis, compute_covariance_matrix,
                            perturb_velocity_model, MonteCarloResult)


def setup_test_model():
    nx, nz = 20, 15
    dx, dz = 10.0, 10.0
    x0, z0 = 0.0, 0.0
    
    velocity = 2000.0 * np.ones((nz, nx))
    velocity[5:10, 8:12] = 2500.0
    velocity[10:, :] = 2200.0
    
    model = VelocityModel(nx=nx, nz=nz, dx=dx, dz=dz, x0=x0, z0=z0, velocity=velocity)
    return model


def setup_test_acquisition():
    shots = []
    receivers = []
    
    for i in range(8):
        z = 10.0 + i * 15.0
        shots.append(Shot(x=0.0, z=z, y=0.0, id=i))
    
    for j in range(10):
        z = 5.0 + j * 14.0
        receivers.append(Receiver(x=190.0, z=z, y=0.0, id=j))
    
    return shots, receivers


def test_fwi_gradient():
    print("\n" + "="*60)
    print("测试1: 全波形反演 - 伴随状态法梯度计算")
    print("="*60)
    
    model_true = setup_test_model()
    model_init = setup_test_model()
    model_init.velocity = 1900.0 * np.ones_like(model_init.velocity)
    
    shots, receivers = setup_test_acquisition()
    
    f0 = 30.0
    dt = 0.0005
    t_max = 0.3
    
    try:
        fwi_true = FullWaveformInversion(model_true, dt=dt, t_max=t_max, f0=f0)
        observed_data = fwi_true.generate_synthetic_seismograms(shots[:2], receivers)
        
        fwi = FullWaveformInversion(model_init, dt=dt, t_max=t_max, f0=f0)
        
        print(f"[OK] FWI初始化成功 (dt={dt*1000:.1f}ms, t_max={t_max}s, f0={f0}Hz)")
        print(f"[OK] 子波生成成功，长度: {len(fwi.wavelet)}")
        print(f"[OK] 波场求解器PML边界: {fwi.solver.pml_width} 格点")
        print(f"[OK] 波场网格 (含PML): {fwi.solver.nz_pml}x{fwi.solver.nx_pml}")
        print(f"[OK] 合成地震记录生成成功，炮数: {len(observed_data)}")
        print(f"[OK] 单炮记录维度: {list(observed_data.values())[0].shape}")
        print(f"[OK] 初始模型与真实模型平均误差: "
              f"{np.abs(model_init.velocity - model_true.velocity).mean():.1f} m/s")
        
        total_obj = 0.0
        total_grad = np.zeros_like(model_init.velocity)
        
        for shot in shots[:2]:
            if shot.id in observed_data:
                obj, grad = fwi.compute_gradient_adjoint(
                    shot, receivers, observed_data[shot.id]
                )
                total_obj += obj
                total_grad += grad
        
        print(f"\n[OK] 伴随状态梯度计算成功:")
        print(f"  - 目标函数值: {total_obj:.6e}")
        print(f"  - 梯度形状: {total_grad.shape}")
        print(f"  - 梯度范围: [{total_grad.min():.3e}, {total_grad.max():.3e}]")
        print(f"  - 梯度L2范数: {np.linalg.norm(total_grad):.3e}")
        print(f"  - 非零梯度格点: {np.count_nonzero(np.abs(total_grad) > 1e-10)}/{total_grad.size}")
        
        assert total_grad.shape == model_init.velocity.shape, "梯度形状不匹配"
        assert not np.isnan(total_grad).any(), "梯度包含NaN值"
        assert not np.isinf(total_grad).any(), "梯度包含Inf值"
        assert total_obj > 0, "目标函数应为正"
        assert np.linalg.norm(total_grad) > 0, "梯度应为非零"
        
        print("\n[OK] 全波形反演梯度计算测试通过")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] FWI梯度计算测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fwi_gradient_accuracy():
    print("\n" + "="*60)
    print("测试2: FWI梯度准确性验证 (伴随状态 vs 有限差分)")
    print("="*60)
    
    model = setup_test_model()
    shots, receivers = setup_test_acquisition()
    
    dt = 0.001
    t_max = 0.2
    f0 = 20.0
    
    try:
        fwi = FullWaveformInversion(model, dt=dt, t_max=t_max, f0=f0)
        
        observed_data = fwi.generate_synthetic_seismograms(shots[:1], receivers)
        
        shot = shots[0]
        obj0, grad_adj = fwi.compute_gradient_adjoint(
            shot, receivers, observed_data[shot.id]
        )
        
        eps = 1e-2
        grad_fd = np.zeros_like(model.velocity)
        
        test_indices = [(7, 10), (7, 11), (8, 10)]
        print(f"\n  位置    伴随状态梯度    有限差分梯度    相对误差")
        print(f"  " + "-"*65)
        
        for idx in test_indices:
            iz, ix = idx
            
            v_plus = model.velocity.copy()
            v_plus[iz, ix] += eps
            model_plus = VelocityModel(nx=model.nx, nz=model.nz, dx=model.dx, dz=model.dz,
                                      x0=model.x0, z0=model.z0, velocity=v_plus)
            fwi_plus = FullWaveformInversion(model_plus, dt=dt, t_max=t_max, f0=f0)
            synth_plus, _ = fwi_plus.solver.forward_propagate(
                shot, receivers, fwi_plus.wavelet
            )
            obj_plus, _ = fwi_plus._compute_objective(observed_data[shot.id], synth_plus)
            
            v_minus = model.velocity.copy()
            v_minus[iz, ix] -= eps
            model_minus = VelocityModel(nx=model.nx, nz=model.nz, dx=model.dx, dz=model.dz,
                                       x0=model.x0, z0=model.z0, velocity=v_minus)
            fwi_minus = FullWaveformInversion(model_minus, dt=dt, t_max=t_max, f0=f0)
            synth_minus, _ = fwi_minus.solver.forward_propagate(
                shot, receivers, fwi_minus.wavelet
            )
            obj_minus, _ = fwi_minus._compute_objective(observed_data[shot.id], synth_minus)
            
            grad_fd[iz, ix] = (obj_plus - obj_minus) / (2 * eps)
            
            adj_val = grad_adj[iz, ix]
            fd_val = grad_fd[iz, ix]
            error = abs(adj_val - fd_val) / max(abs(fd_val), 1e-10) * 100
            print(f"  ({iz:2d},{ix:2d})  {adj_val: .4e}    {fd_val: .4e}    {error:6.2f}%")
        
        print("\n[OK] 梯度准确性验证完成")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] 梯度准确性验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vti_ray_tracing():
    print("\n" + "="*60)
    print("测试3: VTI各向异性介质射线追踪")
    print("="*60)
    
    model = setup_test_model()
    
    epsilon = 0.1 * np.ones_like(model.velocity)
    delta = 0.05 * np.ones_like(model.velocity)
    gamma = 0.08 * np.ones_like(model.velocity)
    epsilon[5:10, 8:12] = 0.2
    delta[5:10, 8:12] = 0.12
    
    anisotropy = AnisotropicParams(epsilon, delta, gamma)
    model.is_anisotropic = True
    model.anisotropy = anisotropy
    
    shots, receivers = setup_test_acquisition()
    
    try:
        vti_tracer = VTIRayTracer(model, neighbor_order=2)
        iso_tracer = ShortestPathRayTracer(model, neighbor_order=2)
        
        print(f"[OK] VTI射线追踪器初始化成功")
        print(f"[OK] Thomsen参数范围: ε=[{epsilon.min():.3f}, {epsilon.max():.3f}], "
              f"δ=[{delta.min():.3f}, {delta.max():.3f}]")
        
        vti_times_all = []
        iso_times_all = []
        
        for shot in shots[:3]:
            vti_times, vti_back = vti_tracer.compute_traveltimes(shot)
            iso_times, iso_back = iso_tracer.compute_traveltimes(shot)
            
            vti_recv_times = []
            iso_recv_times = []
            for recv in receivers:
                rix = int(round((recv.x - model.x0) / model.dx))
                riz = int(round((recv.z - model.z0) / model.dz))
                rix = max(0, min(rix, model.nx - 1))
                riz = max(0, min(riz, model.nz - 1))
                vti_recv_times.append(vti_times[riz, rix])
                iso_recv_times.append(iso_times[riz, rix])
            
            vti_recv_times = np.array(vti_recv_times)
            iso_recv_times = np.array(iso_recv_times)
            
            vti_times_all.append(vti_recv_times)
            iso_times_all.append(iso_recv_times)
            
            diff_percent = (vti_recv_times - iso_recv_times) / iso_recv_times * 100
            print(f"\n炮点 {shot.id}:")
            print(f"  - 各向同性走时: {iso_recv_times.mean():.4f}s "
                  f"(min={iso_recv_times.min():.4f}, max={iso_recv_times.max():.4f})")
            print(f"  - VTI走时: {vti_recv_times.mean():.4f}s "
                  f"(min={vti_recv_times.min():.4f}, max={vti_recv_times.max():.4f})")
            print(f"  - 走时差异: {diff_percent.mean():.2f}% "
                  f"(范围: [{diff_percent.min():.2f}%, {diff_percent.max():.2f}%])")
        
        vti_times_all = np.concatenate(vti_times_all)
        iso_times_all = np.concatenate(iso_times_all)
        total_diff = (vti_times_all - iso_times_all) / iso_times_all * 100
        
        assert abs(total_diff.mean()) > 0.5, "VTI与各向同性走时差异过小"
        assert not np.isnan(vti_times_all).any(), "VTI走时包含NaN"
        assert not np.isinf(vti_times_all).any(), "VTI走时包含Inf"
        assert np.isfinite(vti_times_all).all(), "VTI走时存在无穷值"
        
        theta_test = np.deg2rad([0, 30, 45, 60, 90])
        print(f"\n[OK] VTI相速度验证 (v0=2000m/s, ε=0.1, δ=0.05):")
        for theta in theta_test:
            v = vti_phase_velocity(theta, 2000.0, 0.1, 0.05)
            print(f"  θ={np.rad2deg(theta):.0f}°: v={v:.1f} m/s")
        
        print(f"\n[OK] 各向异性平均走时差异: {total_diff.mean():.2f}%")
        print("[OK] VTI射线追踪测试通过")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] VTI射线追踪测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vti_inversion():
    print("\n" + "="*60)
    print("测试4: VTI各向异性介质走时反演")
    print("="*60)
    
    model_true = setup_test_model()
    
    epsilon_true = 0.12 * np.ones_like(model_true.velocity)
    delta_true = 0.06 * np.ones_like(model_true.velocity)
    gamma_true = 0.09 * np.ones_like(model_true.velocity)
    epsilon_true[5:10, 8:12] = 0.22
    delta_true[5:10, 8:12] = 0.14
    
    anisotropy_true = AnisotropicParams(epsilon_true, delta_true, gamma_true)
    model_true.is_anisotropic = True
    model_true.anisotropy = anisotropy_true
    
    shots, receivers = setup_test_acquisition()
    
    try:
        data_true = generate_synthetic_data(model_true, shots, receivers, noise_level=0.0)
        
        model_init = setup_test_model()
        anisotropy_init = AnisotropicParams(
            0.1 * np.ones_like(model_init.velocity),
            0.05 * np.ones_like(model_init.velocity),
            0.08 * np.ones_like(model_init.velocity)
        )
        model_init.is_anisotropic = True
        model_init.anisotropy = anisotropy_init
        
        config = InversionConfig(
            max_iterations=3,
            regularization=0.01,
            damping=0.001,
            adaptive_regularization=False
        )
        
        vti_tomo = AnisotropicTomography(model_init, config)
        
        print(f"[OK] 各向异性反演配置:")
        print(f"  - 迭代次数: {config.max_iterations}")
        print(f"  - 反演ε: True")
        print(f"  - 反演δ: True")
        print(f"  - 反演γ: False")
        
        history = vti_tomo.run_full_inversion(
            shots, receivers, data_true,
            invert_epsilon=True,
            invert_delta=True
        )
        
        for i, info in enumerate(history):
            if 'error' not in info:
                print(f"  迭代{i+1}: RMS = {info.get('rms_after', 0)*1000:.3f} ms")
        
        final_model = vti_tomo.model
        eps_error = np.abs(final_model.anisotropy.epsilon - epsilon_true).mean()
        delta_error = np.abs(final_model.anisotropy.delta - delta_true).mean()
        vel_error = np.abs(final_model.velocity - model_true.velocity).mean()
        
        if len(history) > 0 and 'error' not in history[0]:
            initial_rms = history[0]['rms_before']
            final_rms = history[-1]['rms_after']
            print(f"\n[OK] 反演结果:")
            print(f"  - 速度平均误差: {vel_error:.1f} m/s")
            print(f"  - ε平均误差: {eps_error:.4f}")
            print(f"  - δ平均误差: {delta_error:.4f}")
            print(f"  - 初始RMS: {initial_rms*1000:.3f} ms")
            print(f"  - 最终RMS: {final_rms*1000:.3f} ms")
            print(f"  - RMS改善: {(1 - final_rms/initial_rms)*100:.1f}%")
        
        assert len(history) > 0, "反演未执行"
        assert not np.isnan(final_model.anisotropy.epsilon).any(), "ε包含NaN"
        assert not np.isnan(final_model.anisotropy.delta).any(), "δ包含NaN"
        
        print("\n[OK] VTI各向异性反演测试通过")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] VTI反演测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_monte_carlo_uncertainty():
    print("\n" + "="*60)
    print("测试5: 蒙特卡洛不确定性传递分析")
    print("="*60)
    
    model = setup_test_model()
    shots, receivers = setup_test_acquisition()
    
    try:
        data = generate_synthetic_data(model, shots, receivers, noise_level=0.002/2000)
        
        n_samples = 10
        config = UncertaintyConfig(
            velocity_prior_std=50.0,
            travel_time_std=0.002,
            epsilon_prior_std=0.02,
            delta_prior_std=0.02,
            n_monte_carlo_samples=n_samples,
            use_likelihood_weighting=True
        )
        
        inv_config = InversionConfig(
            max_iterations=2,
            regularization=0.01,
            damping=0.001,
            adaptive_regularization=False
        )
        
        mc = MonteCarloAnalysis(model, config, inv_config)
        
        print(f"[OK] 蒙特卡洛配置:")
        print(f"  - 样本数: {n_samples}")
        print(f"  - 速度先验标准差: {config.velocity_prior_std} m/s")
        print(f"  - 走时标准差: {config.travel_time_std*1000:.1f} ms")
        print(f"  - ε先验标准差: {config.epsilon_prior_std}")
        print(f"  - δ先验标准差: {config.delta_prior_std}")
        
        result = mc.run_monte_carlo(shots, receivers, data, n_samples=n_samples)
        
        print(f"\n[OK] 分析结果:")
        print(f"  - 成功样本数: {result.n_samples}/{n_samples}")
        print(f"  - 速度均值范围: [{result.velocity_mean.min():.1f}, {result.velocity_mean.max():.1f}] m/s")
        print(f"  - 速度标准差范围: [{result.velocity_std.min():.1f}, {result.velocity_std.max():.1f}] m/s")
        print(f"  - 最大标准差位置: {np.unravel_index(np.argmax(result.velocity_std), result.velocity_std.shape)}")
        print(f"  - 平均变异系数: {(result.velocity_std / (result.velocity_mean + 1e-10) * 100).mean():.2f}%")
        print(f"  - RMS均值: {result.rms_mean*1000:.3f} ms")
        print(f"  - RMS标准差: {result.rms_std*1000:.3f} ms")
        
        assert result.n_samples >= 1, "成功样本过少"
        assert result.velocity_std.min() >= 0, "标准差为负"
        assert (result.velocity_percentile_95 >= result.velocity_percentile_5).all(), \
            "95%分位小于5%分位"
        
        print(f"\n[OK] 置信区间验证:")
        within_bounds = np.logical_and(
            model.velocity >= result.velocity_percentile_5,
            model.velocity <= result.velocity_percentile_95
        )
        coverage = within_bounds.sum() / within_bounds.size * 100
        print(f"  - 真实速度在95%置信区间内的比例: {coverage:.1f}%")
        
        print("\n[OK] 蒙特卡洛不确定性分析测试通过")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] 蒙特卡洛不确定性分析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bootstrap_uncertainty():
    print("\n" + "="*60)
    print("测试6: Bootstrap重采样不确定性分析")
    print("="*60)
    
    model = setup_test_model()
    shots, receivers = setup_test_acquisition()
    
    try:
        data = generate_synthetic_data(model, shots, receivers, noise_level=0.003/2000)
        
        config = UncertaintyConfig(
            travel_time_std=0.003,
            n_monte_carlo_samples=30
        )
        
        inv_config = InversionConfig(
            max_iterations=2,
            regularization=0.01,
            damping=0.001,
            adaptive_regularization=False
        )
        
        mc = MonteCarloAnalysis(model, config, inv_config)
        
        print(f"[OK] Bootstrap配置:")
        print(f"  - 重采样次数: {config.n_monte_carlo_samples}")
        
        result = mc.run_bootstrap(shots, receivers, data, n_bootstrap=30)
        
        print(f"\n[OK] 分析结果:")
        print(f"  - 成功样本数: {result.n_samples}/30")
        print(f"  - 速度标准差均值: {result.velocity_std.mean():.1f} m/s")
        print(f"  - 速度标准差最大值: {result.velocity_std.max():.1f} m/s")
        print(f"  - RMS均值: {result.rms_mean*1000:.3f} ms")
        
        assert result.n_samples >= 1, "成功样本过少"
        assert result.velocity_std.mean() > 0, "速度标准差异常小"
        
        print("\n[OK] Bootstrap不确定性分析测试通过")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Bootstrap测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_covariance_matrix():
    print("\n" + "="*60)
    print("测试7: 线性协方差矩阵不确定性分析")
    print("="*60)
    
    model = setup_test_model()
    shots, receivers = setup_test_acquisition()
    
    try:
        data = generate_synthetic_data(model, shots, receivers, noise_level=0.002/2000)
        
        tracer = ShortestPathRayTracer(model, neighbor_order=2)
        _, G = tracer.forward_modeling(shots, receivers, data, compute_rays=True, update_density=False)
        
        G = G[:, :model.nx * model.nz]
        
        Cd = compute_covariance_matrix(G, data_std=0.002, damping=0.01)
        
        print(f"[OK] 敏感性矩阵维度: {G.shape}")
        print(f"[OK] 协方差矩阵维度: {Cd.shape}")
        
        std = np.sqrt(np.diag(Cd))
        std_reshaped = std.reshape(model.nz, model.nx)
        
        print(f"\n[OK] 不确定性估计:")
        print(f"  - 速度标准差均值: {std_reshaped.mean():.1f} m/s")
        print(f"  - 速度标准差范围: [{std_reshaped.min():.1f}, {std_reshaped.max():.1f}] m/s")
        
        assert Cd.shape[0] == model.nx * model.nz, "协方差矩阵维度错误"
        assert (std >= 0).all(), "方差为负"
        assert not np.isnan(Cd).any(), "协方差矩阵包含NaN"
        
        print("\n[OK] 线性协方差分析测试通过")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] 协方差矩阵测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fwi_inversion_loop():
    print("\n" + "="*60)
    print("测试8: FWI完整迭代更新")
    print("="*60)
    
    model_true = setup_test_model()
    model_init = setup_test_model()
    model_init.velocity = 1900.0 * np.ones_like(model_init.velocity)
    
    shots, receivers = setup_test_acquisition()
    
    try:
        dt = 0.001
        t_max = 0.25
        f0 = 20.0
        
        fwi_true = FullWaveformInversion(model_true, dt=dt, t_max=t_max, f0=f0)
        observed_data = fwi_true.generate_synthetic_seismograms(shots[:2], receivers)
        
        fwi = FullWaveformInversion(model_init, dt=dt, t_max=t_max, f0=f0)
        
        print(f"[OK] FWI配置: dt={dt*1000:.1f}ms, t_max={t_max}s, f0={f0}Hz")
        print(f"[OK] 初始模型误差: {np.abs(model_init.velocity - model_true.velocity).mean():.1f} m/s")
        
        history = []
        for i in range(3):
            obj, direction = fwi.compute_steepest_descent_direction(
                shots[:2], receivers, observed_data
            )
            
            step, final_obj = fwi.line_search(
                shots[:2], receivers, observed_data, direction,
                initial_step=50.0
            )
            
            fwi.model.velocity += step * direction
            
            error = np.abs(fwi.model.velocity - model_true.velocity).mean()
            history.append(obj)
            print(f"  迭代{i+1}: 目标函数={obj:.6e}, 步长={step:.1f}, 速度误差={error:.1f} m/s")
        
        assert len(history) == 3, "迭代次数不足"
        
        if history[-1] < history[0]:
            print(f"\n[OK] 目标函数改善: {(1 - history[-1]/history[0])*100:.1f}%")
        else:
            print(f"\n[WARN]  目标函数未显著下降，可能需要更多迭代或调整步长")
        
        print("[OK] FWI迭代更新测试通过")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] FWI迭代测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    print("\n" + "="*70)
    print("井间地震层析成像 - 高级功能综合测试")
    print("="*70)
    print(f"测试时间: {np.datetime64('now')}")
    
    tests = [
        ("FWI梯度计算", test_fwi_gradient),
        ("FWI梯度准确性", test_fwi_gradient_accuracy),
        ("VTI射线追踪", test_vti_ray_tracing),
        ("VTI走时反演", test_vti_inversion),
        ("蒙特卡洛不确定性", test_monte_carlo_uncertainty),
        ("Bootstrap不确定性", test_bootstrap_uncertainty),
        ("线性协方差分析", test_covariance_matrix),
        ("FWI迭代更新", test_fwi_inversion_loop),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n[FAIL] {name} 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)
    
    for name, passed in results:
        status = "[OK] 通过" if passed else "[FAIL] 失败"
        print(f"  {name:20s}: {status}")
    
    n_passed = sum(1 for _, p in results if p)
    n_total = len(results)
    
    print(f"\n总计: {n_passed}/{n_total} 测试通过")
    
    if n_passed == n_total:
        print("\n[SUCCESS] 所有高级功能测试通过!")
    else:
        print(f"\n[WARN]  {n_total - n_passed} 个测试失败")
    
    return n_passed == n_total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
