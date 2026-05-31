import { NavLink, useLocation } from 'react-router-dom';
import { Music2, Home, Upload, Edit, FileText, Volume2, Library, Layers } from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { path: '/', label: '首页', icon: Home },
  { path: '/upload', label: '上传', icon: Upload },
  { path: '/editor', label: '编辑', icon: Edit },
  { path: '/result', label: '结果', icon: FileText },
  { path: '/audio', label: '音频', icon: Volume2 },
  { path: '/library', label: '曲谱库', icon: Library },
  { path: '/styles', label: '流派', icon: Layers },
];

export default function Navbar() {
  const location = useLocation();

  return (
    <nav className="bg-gradient-to-r from-tanmu-dark via-tanmu to-tanmu-dark text-xuanzhi shadow-lg border-b border-tanmu-light">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-xuanzhi to-xuanzhi-dark flex items-center justify-center shadow-inner">
              <Music2 className="w-6 h-6 text-tanmu" />
            </div>
            <div>
              <h1 className="text-lg font-kai font-bold tracking-wider">
                古琴减字谱智能识别
              </h1>
              <p className="text-xs text-xuanzhi/60 tracking-widest">
                GUQIN JIANZIPU RECOGNITION
              </p>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-300 text-sm font-medium',
                    isActive
                      ? 'bg-tanmu-light text-xuanzhi shadow-inner'
                      : 'text-xuanzhi/70 hover:text-xuanzhi hover:bg-tanmu-light/50'
                  )}
                >
                  <Icon className="w-4 h-4" />
                  <span className="font-kai">{item.label}</span>
                </NavLink>
              );
            })}
          </div>

          <div className="md:hidden flex items-center gap-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={cn(
                    'p-2 rounded-lg transition-all duration-300',
                    isActive
                      ? 'bg-tanmu-light text-xuanzhi'
                      : 'text-xuanzhi/70 hover:text-xuanzhi hover:bg-tanmu-light/50'
                  )}
                  title={item.label}
                >
                  <Icon className="w-5 h-5" />
                </NavLink>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
