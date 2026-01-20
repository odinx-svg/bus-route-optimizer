import { motion, Variants } from 'framer-motion';
import { ReactNode } from 'react';

interface NeonButtonProps {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'green' | 'cyan';
  disabled?: boolean;
  className?: string;
  type?: 'button' | 'submit';
}

const buttonVariants: Variants = {
  initial: { scale: 1 },
  hover: {
    scale: 1.02,
    transition: { type: 'spring', stiffness: 400, damping: 10 }
  },
  tap: { scale: 0.98 }
};

const colorClasses = {
  green: 'bg-neon-green/10 border-neon-green text-neon-green hover:shadow-neon-green',
  cyan: 'bg-cyan-blue/10 border-cyan-blue text-cyan-blue hover:shadow-neon-cyan',
};

export function NeonButton({
  children,
  onClick,
  variant = 'green',
  disabled = false,
  className = '',
  type = 'button'
}: NeonButtonProps) {
  return (
    <motion.button
      type={type}
      variants={buttonVariants}
      initial="initial"
      whileHover={disabled ? undefined : "hover"}
      whileTap={disabled ? undefined : "tap"}
      onClick={onClick}
      disabled={disabled}
      className={`
        px-6 py-3 rounded-lg border font-semibold
        transition-shadow duration-300
        ${colorClasses[variant]}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${className}
      `}
    >
      {children}
    </motion.button>
  );
}
