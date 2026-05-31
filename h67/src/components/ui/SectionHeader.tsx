import React from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface SectionHeaderProps {
  title: string;
  icon?: React.ReactNode;
  isOpen: boolean;
  onToggle: () => void;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  icon,
  isOpen,
  onToggle
}) => {
  return (
    <button
      onClick={onToggle}
      className="w-full flex items-center gap-3 py-3 px-2 -mx-2 text-left hover:bg-zinc-800/50 rounded-lg transition-colors group"
    >
      {icon && (
        <div className="w-5 h-5 text-blue-400 flex-shrink-0">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-semibold text-zinc-200 flex-1">{title}</h3>
      <div className="w-5 h-5 text-zinc-500 group-hover:text-zinc-300 transition-colors flex-shrink-0">
        {isOpen ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
      </div>
    </button>
  );
};
