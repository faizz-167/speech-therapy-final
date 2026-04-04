import { SelectHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

interface NeoSelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

export const NeoSelect = forwardRef<HTMLSelectElement, NeoSelectProps>(
  ({ label, error, className, children, ...props }, ref) => (
    <div className="flex flex-col gap-1">
      {label && <label className="font-black uppercase tracking-widest text-sm">{label}</label>}
      <select
        ref={ref}
        className={cn(
          "border-4 border-neo-black px-4 h-14 font-bold text-lg bg-white focus:bg-neo-secondary focus:shadow-neo-sm focus:outline-none focus:ring-0 transition-all rounded-none",
          error && "border-neo-accent",
          className
        )}
        {...props}
      >
        {children}
      </select>
      {error && <span className="text-neo-accent text-xs font-bold">{error}</span>}
    </div>
  )
);
NeoSelect.displayName = "NeoSelect";
