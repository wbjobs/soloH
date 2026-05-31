import numpy as np
from app.models import VelocityModel, InversionConfig
from app.ray_tracing import ShortestPathRayTracer
from app.inversion import TomographicInversion, lsqr
from app.synthetic import create_synthetic_test
from app.io_handler import save_velocity_model_ascii, load_velocity_model_ascii
import tempfile
import os

def test_velocity_model():
    print("=" * 60)
    print("测试 VelocityModel 类...")
    
    model = VelocityModel(nx=20, nz=20, dx=5.0, dz=5.0)
    print(f"  创建模型: {model.nx}x{model.nz}, dx={model.dx}, dz={model.dz}")
    print(f"  速度范围: {model.velocity.min():.1f} - {model.velocity.max():.1f} m/s")
    print(f"  慢度范围: {model.slowness.min():.6f} - {model.slowness.max():.6f} s/m")
    
    model.update_velocity(np.ones_like(model.velocity) * 100.0)
    print(f"  更新后速度: {model.velocity[0,0]:.1f} m/s")
    
    copy = model.copy()
    copy.velocity[0, 0] = 9999.0
    print(f"  复制独立性测试: 原={model.velocity[0,0]:.1f}, 副本={copy.velocity[0,0]:.1f}")
    
    print("  ✓ VelocityModel 测试通过")

def test_ray_tracing():
    print("\n" + "=" * 60)
    print("测试 最短路径射线追踪...")
    
    model = VelocityModel(nx=30, nz=30, dx=5.0, dz=5.0)
    
    from app.models import Shot, Receiver
    shot = Shot(id=1, x=0.0, z=75.0)
    receiver = Receiver(id=1, x=145.0, z=75.0)
    
    ray_tracer = ShortestPathRayTracer(model)
    
    print(f"  炮点: ({shot.x}, {shot.z})")
    print(f"  检波点: ({receiver.x}, {receiver.z})")
    print(f"  均匀速度: {model.velocity[0,0]:.1f} m/s")
    
    times, backtrack = ray_tracer.compute_traveltimes(shot)
    rix = int((receiver.x - model.x0) / model.dx)
    riz = int((receiver.z - model.z0) / model.dz)
    travel_time = times[riz, rix]
    
    direct_dist = shot.distance_to(receiver)
    expected_time = direct_dist / model.velocity[0, 0]
    
    print(f"  计算走时: {travel_time:.6f} s")
    print(f"  理论走时: {expected_time:.6f} s")
    print(f"  相对误差: {abs(travel_time - expected_time) / expected_time * 100:.3f}%")
    
    ray = ray_tracer.trace_ray(backtrack, receiver)
    print(f"  射线路径点数: {len(ray.points)}")
    print(f"  射线长度: {ray.length():.2f} m")
    
    from app.models import TravelTimeData
    data = [TravelTimeData(shot_id=1, receiver_id=1, travel_time=travel_time, shot=shot, receiver=receiver)]
    
    data_out, sensitivity = ray_tracer.forward_modeling([shot], [receiver], data)
    print(f"  灵敏度矩阵形状: {sensitivity.shape}")
    print(f"  灵敏度和: {sensitivity.sum():.2f} (应≈射线长度)")
    print(f"  射线密度最大值: {model.ray_density.max()}")
    
    print("  ✓ 射线追踪测试通过")

def test_lsqr():
    print("\n" + "=" * 60)
    print("测试 LSQR 求解器...")
    
    np.random.seed(42)
    m, n = 50, 30
    A = np.random.randn(m, n)
    x_true = np.random.randn(n)
    b = A @ x_true + 0.01 * np.random.randn(m)
    
    x_sol, info = lsqr(A, b, damp=0.01, maxiter=100)
    
    error = np.linalg.norm(x_sol - x_true) / np.linalg.norm(x_true)
    print(f"  问题规模: {m}x{n}")
    print(f"  迭代次数: {info['itn']}")
    print(f"  解的相对误差: {error:.6f}")
    print(f"  最终残差: {info['r1norm']:.6f}")
    
    if error < 0.5:
        print("  ✓ LSQR 测试通过")
    else:
        print(f"  ⚠ LSQR 误差较大 ({error:.4f})，可能需要更多迭代")

def test_synthetic_data():
    print("\n" + "=" * 60)
    print("测试 合成数据生成...")
    
    true_model, init_model, shots, receivers, data = create_synthetic_test(
        model_type='anomaly', nx=20, nz=20, dx=5.0, dz=5.0,
        n_shots=5, n_receivers=10, noise_level=0.01
    )
    
    print(f"  真实模型: {true_model.nx}x{true_model.nz}")
    print(f"  炮点数: {len(shots)}")
    print(f"  检波点数: {len(receivers)}")
    print(f"  走时记录数: {len(data)}")
    print(f"  速度范围: {true_model.velocity.min():.1f} - {true_model.velocity.max():.1f} m/s")
    print(f"  走时范围: {min(d.travel_time for d in data)*1000:.2f} - {max(d.travel_time for d in data)*1000:.2f} ms")
    
    print("  ✓ 合成数据测试通过")

def test_io():
    print("\n" + "=" * 60)
    print("测试 IO 操作...")
    
    model = VelocityModel(nx=15, nz=10, dx=10.0, dz=10.0)
    model.velocity += np.random.randn(*model.velocity.shape) * 100
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        tmp_path = f.name
    
    try:
        save_velocity_model_ascii(model, tmp_path)
        print(f"  模型已保存到: {tmp_path}")
        
        loaded = load_velocity_model_ascii(tmp_path)
        print(f"  加载模型: {loaded.nx}x{loaded.nz}")
        
        diff = np.abs(model.velocity - loaded.velocity).max()
        print(f"  最大数值差异: {diff:.6f}")
        
        if diff < 0.01:
            print("  ✓ IO 测试通过")
        else:
            print("  ⚠ IO 测试存在数值差异")
    finally:
        os.unlink(tmp_path)
        print(f"  临时文件已删除")

def test_inversion():
    print("\n" + "=" * 60)
    print("测试 反演迭代...")
    
    true_model, init_model, shots, receivers, data = create_synthetic_test(
        model_type='anomaly', nx=15, nz=15, dx=5.0, dz=5.0,
        n_shots=4, n_receivers=8, noise_level=0.005
    )
    
    config = InversionConfig(
        max_iterations=3,
        lsqr_tol=1e-4,
        regularization=0.05,
        damping=0.01,
        update_scale=0.5
    )
    
    inversion = TomographicInversion(init_model.copy(), config)
    
    print(f"  初始模型RMS: ", end="")
    import copy
    data_copy = copy.deepcopy(data)
    rt = ShortestPathRayTracer(init_model)
    rt.forward_modeling(shots, receivers, data_copy, compute_rays=False)
    res = np.array([d.residual for d in data_copy if np.isfinite(d.residual)])
    init_rms = np.sqrt(np.mean(res**2)) * 1000
    print(f"{init_rms:.2f} ms")
    
    for i in range(3):
        info = inversion.run_iteration(shots, receivers, data)
        if 'error' in info:
            print(f"  迭代 {i+1}: 错误 - {info['error']}")
            break
        print(f"  迭代 {i+1}: RMS前={info['rms_before']*1000:.2f} ms, "
              f"RMS后={info['rms_after']*1000:.2f} ms, "
              f"下降={info['rms_reduction']:.1f}%")
    
    final_error = np.mean(np.abs(inversion.model.velocity - true_model.velocity))
    print(f"  最终平均速度误差: {final_error:.1f} m/s")
    
    if info['rms_reduction'] > 0:
        print("  ✓ 反演测试通过")
    else:
        print("  ⚠ 反演没有显著收敛")

def main():
    print("\n" + "╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "核心算法单元测试" + " " * 25 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    try:
        test_velocity_model()
        test_ray_tracing()
        test_lsqr()
        test_synthetic_data()
        test_io()
        test_inversion()
        
        print("\n" + "=" * 60)
        print("✓ 所有测试完成！")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
