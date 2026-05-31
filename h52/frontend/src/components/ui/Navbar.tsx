import { NavLink, Link } from 'react-router-dom';
import { Video, Zap, History, Home, Brain, Moon, Sun } from 'lucide-react';
import { useAppStore } from '@/store';
import { cn } from '@/utils';

export function Navbar() {
  const { darkMode, toggleDarkMode } = useAppStore();

  const navItems = [
    { path: '/', label: '首页', icon: Home },
    { path: '/record', label: '视频录制', icon: Video },
    { path: '/realtime', label: '实时分析', icon: Zap },
    { path: '/history', label: '历史记录', icon: History },
  ];

  return (
    <nav className="fixed top-0 left-0 right-0 z-40 bg-background/80 backdrop-blur-xl border-b border-white/10">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center group-hover:animate-glow transition-all">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold font-display text-gradient">
                EmotionAI
              </h1>
              <p className="text-[10px] text-muted-foreground -mt-1">
                多模态情感分析系统
              </p>
            </div>
          </Link>

          <div className="flex items-center gap-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300',
                    isActive
                      ? 'bg-primary/20 text-primary'
                      : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
                  )
                }
              >
                <item.icon className="w-4 h-4" />
                <span className="hidden md:inline">{item.label}</span>
              </NavLink>
            ))}

            <button
              onClick={toggleDarkMode}
              className="ml-2 p-2 rounded-xl text-muted-foreground hover:text-foreground hover:bg-white/5 transition-all"
              title={darkMode ? '切换浅色模式' : '切换深色模式'}
            >
              {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
