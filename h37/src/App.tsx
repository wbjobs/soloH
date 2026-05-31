import { BandSelector } from './components/ControlPanel/BandSelector';
import { AudioControls } from './components/ControlPanel/AudioControls';
import { BackgroundSounds } from './components/ControlPanel/BackgroundSounds';
import { Presets } from './components/ControlPanel/Presets';
import { ExportPanel } from './components/ControlPanel/ExportPanel';
import { PlayControls } from './components/ControlPanel/PlayControls';
import { HRVPanel } from './components/ControlPanel/HRVPanel';
import { HapticPanel } from './components/ControlPanel/HapticPanel';
import { AdaptiveAIPanel } from './components/ControlPanel/AdaptiveAIPanel';
import { ParticleScene } from './components/Visualizer3D/ParticleScene';
import { SpectrumChart } from './components/SpectrumAnalyzer/SpectrumChart';
import { WaveformChart } from './components/SpectrumAnalyzer/WaveformChart';
import { PhaseIndicator } from './components/SpectrumAnalyzer/PhaseIndicator';
import { BreathingLight } from './components/BreathingGuide/BreathingLight';
import { useAudioStore } from './store/useAudioStore';
import { Waves } from 'lucide-react';

function App() {
  const { currentBand } = useAudioStore();

  return (
    <div
      className="min-h-screen w-full flex flex-col lg:flex-row overflow-hidden"
      style={{
        background: `
          radial-gradient(ellipse at 20% 20%, ${currentBand.color}15 0%, transparent 50%),
          radial-gradient(ellipse at 80% 80%, ${currentBand.color}10 0%, transparent 50%),
          linear-gradient(180deg, #0a0e1a 0%, #050810 100%)
        `
      }}
    >
      <div className="w-full lg:w-[420px] h-auto lg:h-screen flex-shrink-0 overflow-y-auto
                    bg-black/30 backdrop-blur-xl border-r border-white/5
                    p-6 space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{
              background: `linear-gradient(135deg, ${currentBand.color}, ${currentBand.color}80)`,
              boxShadow: `0 0 20px ${currentBand.glowColor}`
            }}
          >
            <Waves size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">脑波音疗</h1>
            <p className="text-[11px] text-white/50">Brainwave Sound Therapy</p>
          </div>
        </div>

        <PlayControls />
        <BandSelector />
        <AudioControls />
        <BackgroundSounds />
        <HRVPanel />
        <HapticPanel />
        <AdaptiveAIPanel />
        <Presets />
        <ExportPanel />

        <div className="pt-4 border-t border-white/10">
          <p className="text-[10px] text-white/30 text-center">
            ⚠️ 请使用立体声耳机以获得最佳体验
          </p>
        </div>
      </div>

      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 relative min-h-[400px] lg:min-h-0">
          <ParticleScene />
          <BreathingLight />
        </div>

        <div className="bg-black/50 backdrop-blur-xl border-t border-white/5 p-4
                        flex flex-col lg:flex-row gap-4 items-stretch lg:items-center">
          <div className="flex items-center gap-4">
            <div className="hidden lg:block">
              <PhaseIndicator />
            </div>
            <div className="flex-1 min-w-0 space-y-2">
              <div className="h-24">
                <SpectrumChart />
              </div>
              <div className="h-20">
                <WaveformChart />
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-4 text-xs justify-center lg:justify-end">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: currentBand.color }} />
              <span className="text-white/50">左声道波形</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-amber-500" />
              <span className="text-white/50">右声道波形</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
