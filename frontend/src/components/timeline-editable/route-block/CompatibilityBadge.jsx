import { Check, AlertTriangle, X } from 'lucide-react';

export function CompatibilityBadge({ compatibility }) {
  if (!compatibility) return null;

  const { status, score } = compatibility;

  const config = {
    compatible: {
      icon: Check,
      bgClass: 'bg-green-500',
      textClass: 'text-white',
      label: 'OK'
    },
    warning: {
      icon: AlertTriangle,
      bgClass: 'bg-amber-500',
      textClass: 'text-white',
      label: score ? `${score}%` : '!'
    },
    incompatible: {
      icon: X,
      bgClass: 'bg-red-500',
      textClass: 'text-white',
      label: score ? `${score}%` : 'X'
    }
  };

  const { icon: Icon, bgClass, textClass, label } = config[status] || config.compatible;

  return (
    <div 
      className={`
        absolute -bottom-2 left-1/2 -translate-x-1/2 
        px-1.5 py-0.5 rounded-full 
        flex items-center gap-0.5
        ${bgClass} ${textClass}
        text-[9px] font-medium
        shadow-sm
        transition-all duration-200
      `}
    >
      <Icon size={8} />
      <span>{label}</span>
    </div>
  );
}
