import React from 'react';

export const AvatarStack = ({ 
  items = [], 
  max = 3,
  size = 'md',
  className = '' 
}) => {
  const sizes = { sm: 'w-6 h-6 text-[10px]', md: 'w-7 h-7 text-xs', lg: 'w-9 h-9 text-sm' };
  const displayItems = items.slice(0, max);
  const remaining = items.length - max;
  
  if (items.length === 0) return null;
  
  return (
    <div className={`flex items-center ${className}`}>
      {displayItems.map((item, index) => (
        <div
          key={item.id || index}
          className={`${sizes[size]} rounded-full flex items-center justify-center font-semibold border-2 border-[#0b141f] -ml-2 first:ml-0`}
          style={{ 
            zIndex: displayItems.length - index,
            background: item.color || `hsl(${200 + index * 30}, 70%, 50%)`
          }}
          title={item.name}
        >
          {item.name?.charAt(0).toUpperCase() || '?'}
        </div>
      ))}
      {remaining > 0 && (
        <div className={`${sizes[size]} rounded-full bg-[#1a2d3f] border-2 border-[#0b141f] -ml-2 flex items-center justify-center text-[10px] text-gray-400 font-medium`}>
          +{remaining}
        </div>
      )}
    </div>
  );
};
