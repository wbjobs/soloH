import os
import numpy as np
from app.synthetic import create_synthetic_test
from app.io_handler import (save_velocity_model_ascii, save_geometry,
                            save_travel_times)


def main():
    sample_dir = 'sample_data'
    os.makedirs(sample_dir, exist_ok=True)
    
    print("生成示例数据...")
    
    true_model, init_model, shots, receivers, data = create_synthetic_test(
        model_type='anomaly',
        nx=30, nz=30,
        dx=5.0, dz=5.0,
        n_shots=8, n_receivers=25,
        noise_level=0.01
    )
    
    true_model_path = os.path.join(sample_dir, 'true_velocity_model.txt')
    save_velocity_model_ascii(true_model, true_model_path)
    print(f"  ✓ 真实速度模型: {true_model_path}")
    
    init_model_path = os.path.join(sample_dir, 'initial_velocity_model.txt')
    save_velocity_model_ascii(init_model, init_model_path)
    print(f"  ✓ 初始速度模型: {init_model_path}")
    
    geometry_path = os.path.join(sample_dir, 'geometry.txt')
    save_geometry(shots, receivers, geometry_path)
    print(f"  ✓ 观测系统: {geometry_path}")
    
    tt_path = os.path.join(sample_dir, 'travel_times.txt')
    save_travel_times(data, tt_path)
    print(f"  ✓ 走时数据: {tt_path}")
    
    print("\n示例数据生成完成！")
    print(f"\n数据概览:")
    print(f"  模型: {true_model.nx}x{true_model.nz} 网格, {true_model.dx}x{true_model.dz}m")
    print(f"  速度范围: {true_model.velocity.min():.1f} - {true_model.velocity.max():.1f} m/s")
    print(f"  炮点: {len(shots)}个")
    print(f"  检波点: {len(receivers)}个")
    print(f"  走时记录: {len(data)}条")
    
    print(f"\n使用方法:")
    print(f"  1. 启动程序: python main.py")
    print(f"  2. 导入初始模型: 文件 -> 导入速度模型 -> {init_model_path}")
    print(f"  3. 导入观测系统: 文件 -> 导入观测系统 -> {geometry_path}")
    print(f"  4. 导入走时数据: 文件 -> 导入走时数据 -> {tt_path}")
    print(f"  5. 或者直接使用: 工具 -> 生成合成测试数据")
    print(f"  6. 设置参数: 工具 -> 反演参数设置")
    print(f"  7. 开始反演: 工具 -> 执行层析反演")


if __name__ == '__main__':
    main()
