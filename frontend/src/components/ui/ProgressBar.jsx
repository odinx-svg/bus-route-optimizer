import React from 'react';

export const ProgressBar = ({ 
  progress, 
  size = 'md',
  showPercentage = true,
  className = '' 
}) => {
  const sizes = { sm: 'h-1.5', md: 'h-2', lg: 'h-3' };
  
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className={`flex-1 ${sizes[size]} bg-[#0b141f] rounded-full overflow-hidden`}>
        <div 
          className="h-full rounded-full transition-all duration-500"
          style={{ 
            width: `${Math.min(100, Math.max(0, progress))}%`,
            background: 'linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%)'
          }}
        />
      </div>
      {showPercentage && (
        <span className="text-xs font-semibold text-blue-400 min-w-[36px] text-right">
          {Math.round(progress)}%
        </span>
      )}
    </div>
  );
};
