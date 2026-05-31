# Unity城市交通仿真器 (City Traffic Simulator)

基于Unity3D开发的桌面城市交通仿真应用，支持程序化城市场景生成、AI交通流、玩家接管控制、轨迹记录与回放、场景导出等功能。

## 功能特性

### 场景生成
- **可配置参数**：车道数(2-8)、曲率(0-1)、车辆密度(0.1-5)、交通信号灯周期(5-60秒)、天气类型、行人数量(0-50)
- **静态元素**：程序化生成道路（网格布局、弯曲道路、交叉口）、多层建筑物、交通标志（停车、限速、让行、人行横道）
- **动态元素**：AI控制车辆（轿车、卡车、公交车、摩托车）、AI控制行人

### 交通AI
- 车辆：车道跟随、前车距离检测、交通信号灯响应、自动变道
- 行人：沿人行道行走、自动往返
- 交通灯：交叉路口协调同步、红黄绿三色自动切换

### 记录与回放
- **轨迹记录**：记录位置、旋转、速度、方向盘角度、油门、刹车
- **碰撞检测**：记录时间、碰撞物体、位置、法向量、相对速度
- **回放系统**：时间插值回放、暂停/继续、速度调节

### 玩家控制
- **接管驾驶**：按T键或点击"Take Control"按钮驾驶一辆车
- **键盘控制**：W/↑ 加速，S/↓ 刹车/倒车，A/← D/→ 转向，Space 手刹，R 重置位置
- **退出控制**：ESC 释放控制权

### 摄像机系统
- **俯视视角** (F1)：边缘滚动漫游，鼠标右键拖动
- **跟随视角** (F2)：平滑跟随车辆
- **第一人称视角** (F3)：车内视角
- **Tab**：循环切换视角

### 天气系统
- 晴天、雨天（粒子+雾效）、雾天（指数雾）、雪天（粒子+雾效）、夜晚（低光照）

### 导出功能
- **标准JSON导出**：完整场景描述文件
- **CARLA兼容导出**：OpenDRIVE道路描述 + 演员定义，可导入CARLA自动驾驶仿真器

## 项目结构

```
Assets/
├── Scenes/
│   └── Main.unity              # 主场景
├── Scripts/
│   ├── CitySimulator.asmdef    # 程序集定义
│   ├── Core/                   # 核心管理
│   │   ├── Enums.cs            # 枚举类型
│   │   ├── SceneParameters.cs  # 场景参数
│   │   ├── DataModels.cs       # 数据模型
│   │   ├── SimulationManager.cs # 仿真管理器
│   │   ├── SceneGenerator.cs   # 场景生成协调器
│   │   ├── SceneBootstrap.cs   # 场景引导
│   │   └── GlobalInputHandler.cs # 全局输入处理
│   ├── RoadSystem/             # 道路系统
│   │   ├── RoadGenerator.cs    # 道路生成
│   │   ├── BuildingGenerator.cs # 建筑物生成
│   │   └── TrafficSignGenerator.cs # 交通标志生成
│   ├── Traffic/                # 交通系统
│   │   └── TrafficLightGenerator.cs # 交通信号灯
│   ├── Vehicles/               # 车辆系统
│   │   ├── VehicleGenerator.cs # 车辆生成
│   │   ├── VehicleAIController.cs # 车辆AI
│   │   ├── ILDriverModel.cs    # 模仿学习驾驶员模型
│   │   └── CollaborativeLaneChangeManager.cs # 协同变道与博弈
│   ├── Scenario/               # 场景生成
│   │   └── CornerCaseGenerator.cs # 边缘场景生成器
│   ├── Pedestrians/            # 行人系统
│   │   ├── PedestrianGenerator.cs # 行人生成
│   │   └── PedestrianAIController.cs # 行人AI
│   ├── Player/                 # 玩家控制
│   │   └── PlayerVehicleController.cs # 玩家车辆控制
│   ├── Recording/              # 记录系统
│   │   ├── CollisionDetector.cs # 碰撞检测
│   │   ├── TrajectoryRecorder.cs # 轨迹记录
│   │   └── ReplaySystem.cs     # 回放系统
│   ├── Export/                 # 导出系统
│   │   └── SceneExporter.cs    # 场景导出
│   ├── CameraSystem/           # 摄像机系统
│   │   └── CameraSystem.cs     # 多视角摄像机
│   ├── Environment/            # 环境系统
│   │   └── WeatherSystem.cs    # 天气系统
│   └── UI/                     # 用户界面
│       └── UIController.cs     # UI控制面板
```

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `F1` | 俯视视角 |
| `F2` | 跟随视角 |
| `F3` | 第一人称视角 |
| `Tab` | 循环切换视角 |
| `Space` | 暂停/继续仿真 |
| `T` | 接管/释放车辆控制权 |
| `ESC` | 退出玩家控制 |
| `W / ↑` | 加速 |
| `S / ↓` | 刹车/倒车 |
| `A / ←` | 左转 |
| `D / →` | 右转 |
| `Space (驾驶中)` | 手刹 |
| `R (驾驶中)` | 重置车辆位置 |
| `Ctrl + R` | 重新生成场景 |
| `Ctrl + S` | 保存录制 |
| `Ctrl + L` | 加载录制 |

## 使用说明

### 1. 启动场景
1. 用Unity 2022.3.20f1 LTS打开项目
2. 打开 `Assets/Scenes/Main.unity`
3. 点击Play按钮运行

### 2. 生成场景
1. 在左侧控制面板调整参数
2. 点击 **Generate Scene** 按钮生成场景
3. 或按 `Ctrl + R` 重新生成

### 3. 接管控制
1. 点击 **Take Control** 按钮或按 `T` 键
2. 使用WASD/方向键驾驶车辆
3. 按 `ESC` 或点击 **Release Control** 退出

### 4. 记录与回放
1. 点击 **Start Recording** 开始记录
2. 点击 **Stop Recording** 停止记录
3. 点击 **Save Recording** 保存为JSON文件
4. 点击 **Load Recording** 加载记录文件
5. 点击 **Play Replay** 开始回放

### 5. 导出场景
1. 点击 **Export Scene JSON** 导出标准格式
2. 点击 **Export for CARLA** 导出CARLA兼容格式
3. 文件保存在项目根目录的 `Exports/` 文件夹

## 技术架构

### 设计模式
- **单例模式**：所有管理器使用单例模式，便于全局访问
- **模块化设计**：按功能划分命名空间，各系统低耦合
- **事件驱动**：状态变更通过事件通知

### 核心系统
- `SimulationManager`：仿真状态机管理
- `SceneGenerator`：场景生成协调
- `TrajectoryRecorder`：轨迹和碰撞记录
- `ReplaySystem`：时间插值回放
- `SceneExporter`：JSON序列化导出

### 数据模型
所有数据类均支持JSON序列化：
- `SceneDescription`：完整场景描述
- `RecordingData`：记录数据（轨迹点+碰撞事件）
- `Vector3Data`、`QuaternionData`：可序列化的数学类型

## CARLA导出格式

导出的CARLA兼容JSON包含：
```json
{
  "version": "1.0",
  "open_drive": "...", // OpenDRIVE 1.4格式道路描述
  "actors": [
    {
      "type": "vehicle.tesla.model3",
      "transform": { "x": 0, "y": 0, "z": 0, "pitch": 0, "yaw": 0, "roll": 0 },
      "role_name": "autopilot"
    }
  ]
}
```

## 系统要求

- **Unity版本**：2022.3.20f1 LTS
- **操作系统**：Windows 10/11, macOS 10.15+, Linux
- **.NET版本**：.NET Standard 2.1
- **内存**：建议8GB以上

## 许可证

MIT License
