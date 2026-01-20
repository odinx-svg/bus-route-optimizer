import { ReactNode } from 'react';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  padding?: 'sm' | 'md' | 'lg';
}

const paddingClasses = {
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
};

export function GlassCard({
  children,
  className = '',
  padding = 'md'
}: GlassCardProps) {
  return (
    <div
      className={`
        bg-glass backdrop-blur-glass
        border border-glass-border
        rounded-xl shadow-glass
        ${paddingClasses[padding]}
        ${className}
      `}
    >
      {children}
    </div>
  );
}
