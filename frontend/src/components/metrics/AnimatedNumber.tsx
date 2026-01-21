import { motion, useSpring, useTransform } from 'framer-motion';
import { useEffect } from 'react';

interface AnimatedNumberProps {
  value: number;
  className?: string;
  /** Number of decimal places to display */
  decimals?: number;
}

/**
 * Animated number counter using Framer Motion springs.
 * Updates smoothly when value changes without causing React re-renders.
 *
 * Based on BuildUI recipe: https://buildui.com/recipes/animated-number
 */
export function AnimatedNumber({
  value,
  className = '',
  decimals = 0
}: AnimatedNumberProps) {
  const spring = useSpring(value, {
    mass: 0.8,
    stiffness: 75,
    damping: 15
  });

  const display = useTransform(spring, (current) => {
    if (decimals > 0) {
      return current.toFixed(decimals);
    }
    return Math.round(current).toLocaleString();
  });

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  return <motion.span className={className}>{display}</motion.span>;
}
