import { useEffect } from 'react';
import { Gamepad2, Vibrate, Zap, Waves, Wind } from 'lucide-react';
import { useAudioStore } from '../../store/useAudioStore';

export const HapticPanel = () => {
  const { haptic, setHaptic, triggerHaptic, beatFrequency, isPlaying, breathing } = useAudioStore();

  useEffect(() => {
    const checkGamepad = () => {
      const gamepads = navigator.getGamepads();
      const hasConnected = gamepads.some(g => g !== null);
      if (hasConnected !== haptic.isConnected) {
        setHaptic({ isConnected: hasConnected });
      }
    };

    const interval = setInterval(checkGamepad, 1000);
    checkGamepad();

    const onConnect = () => setHaptic({ isConnected: true });
    const onDisconnect = () => {
      const gamepads = navigator.getGamepads();
      const hasConnected = gamepads.some(g => g !== null);
      setHaptic({ isConnected: hasConnected });
    };

    window.addEventListener('gamepadconnected', onConnect);
    window.addEventListener('gamepaddisconnected', onDisconnect);

    return () => {
      clearInterval(interval);
      window.removeEventListener('gamepadconnected', onConnect);
      window.removeEventListener('gamepaddisconnected', onDisconnect);
    };
  }, [haptic.isConnected, setHaptic]);

  const patterns = [
    { id: 'beat' as const, label: '节拍', icon: Zap, desc: '与脑波频率同步震动' },
    { id: 'wave' as const, label: '波浪', icon: Waves, desc: '渐变波浪式震动' },
    { id: 'breathing' as const, label: '呼吸', icon: Wind, desc: '跟随呼吸节奏' }
  ];

  const testVibration = () => {
    if (haptic.enabled && haptic.isConnected) {
      triggerHaptic(200);
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white/80 tracking-wider flex items-center gap-2">
        <Gamepad2 size={14} />
        触觉反馈
      </h3>
      <div className="p-4 bg-white/5 rounded-2xl backdrop-blur-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`
                w-12 h-12 rounded-xl flex items-center justify-center
                transition-all duration-300
              `}
              style={{
                backgroundColor: haptic.isConnected
                  ? 'rgba(16, 185, 129, 0.2)'
                  : 'rgba(255, 255, 255, 0.05)',
                boxShadow: haptic.isConnected && haptic.enabled
                  ? '0 0 20px rgba(16, 185, 129, 0.4)'
                  : 'none'
              }}
            >
              <Vibrate
                size={24}
                style={{
                  color: haptic.isConnected ? '#10b981' : 'rgba(255, 255, 255, 0.3)'
                }}
              />
            </div>
            <div>
              <div className="text-sm font-medium text-white">
                {haptic.isConnected ? '游戏手柄已连接' : '未检测到游戏手柄'}
              </div>
              <div className="text-xs text-white/50">
                {haptic.isConnected
                  ? '支持 DualShock 4 / Xbox 手柄等'
                  : '请连接支持震动的游戏手柄'}
              </div>
            </div>
          </div>
          <div
            className={`
              w-12 h-6 rounded-full relative transition-all duration-300 cursor-pointer
              ${haptic.enabled ? '' : 'bg-white/10'}
            `}
            style={{
              backgroundColor: haptic.enabled ? '#10b981' : undefined
            }}
            onClick={() => haptic.isConnected && setHaptic({ enabled: !haptic.enabled })}
          >
            <div
              className={`
                absolute top-0.5 w-5 h-5 rounded-full bg-white
                transition-all duration-300 shadow-md
              `}
              style={{
                left: haptic.enabled ? '26px' : '2px',
                opacity: haptic.isConnected ? 1 : 0.5
              }}
            />
          </div>
        </div>

        {haptic.isConnected && haptic.enabled && (
          <>
            <div className="space-y-2">
              <div className="text-xs text-white/60">震动模式</div>
              <div className="grid grid-cols-3 gap-2">
                {patterns.map(({ id, label, icon: Icon, desc }) => {
                  const isActive = haptic.pattern === id;
                  return (
                    <button
                      key={id}
                      onClick={() => setHaptic({ pattern: id })}
                      className={`
                        flex flex-col items-center gap-1 p-3 rounded-xl
                        transition-all duration-300
                        ${isActive
                          ? 'bg-white/15 text-white'
                          : 'bg-white/5 text-white/50 hover:bg-white/10'
                        }
                      `}
                      title={desc}
                    >
                      <Icon size={18} />
                      <span className="text-[11px]">{label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <span className="text-xs text-white/70">震动强度</span>
                <span className="text-xs font-mono text-white/90">
                  {Math.round(haptic.intensity * 100)}%
                </span>
              </div>
              <div className="relative h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="absolute left-0 top-0 h-full rounded-full transition-all duration-150"
                  style={{
                    width: `${haptic.intensity * 100}%`,
                    background: 'linear-gradient(90deg, #10b98180, #10b981)'
                  }}
                />
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={haptic.intensity}
                  onChange={(e) => setHaptic({ intensity: parseFloat(e.target.value) })}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
              </div>
            </div>

            <button
              onClick={testVibration}
              disabled={!isPlaying}
              className={`
                w-full py-2 rounded-xl text-sm font-medium
                transition-all duration-300 flex items-center justify-center gap-2
                ${isPlaying
                  ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border border-emerald-500/30'
                  : 'bg-white/5 text-white/30 cursor-not-allowed border border-white/10'
                }
              `}
            >
              <Vibrate size={14} />
              测试震动
            </button>

            <div className="text-[11px] text-white/40 text-center">
              {isPlaying
                ? `当前与 ${beatFrequency.toFixed(1)}Hz 节拍同步`
                : '请先开始播放以使用触觉反馈'}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
