import { HTMLAttributes, forwardRef } from 'react';
import { cn } from '../../utils/formatters';

type BadgeVariant = 'default' | 'accent' | 'green' | 'red' | 'amber';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-surface text-muted',
  accent: 'bg-accent-light text-accent',
  green: 'bg-green/10 text-green',
  red: 'bg-red/10 text-red',
  amber: 'bg-amber/10 text-amber',
};

const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = 'default', className, children, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
          variantStyles[variant],
          className,
        )}
        {...props}
      >
        {children}
      </span>
    );
  },
);

Badge.displayName = 'Badge';

export default Badge;
