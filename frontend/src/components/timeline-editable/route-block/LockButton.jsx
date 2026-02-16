import { Lock, Unlock } from 'lucide-react';

export function LockButton({ isLocked, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`
        absolute -top-2 -right-2 w-5 h-5 rounded-full 
        flex items-center justify-center
        ${isLocked 
          ? 'bg-red-500 text-white' 
          : 'bg-green-500 text-white opacity-0 group-hover:opacity-100'}
        transition-all duration-200 z-10
        hover:scale-110 active:scale-95
      `}
      title={isLocked ? 'Desbloquear' : 'Bloquear'}
    >
      {isLocked ? <Lock size={12} /> : <Unlock size={12} />}
    </button>
  );
}
