import { InputHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

interface NeoInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const NeoInput = forwardRef<HTMLInputElement, NeoInputProps>(
  ({ label, error, className, ...props }, ref) => (
    <div className="flex flex-col gap-1">
      {label && <label className="font-black uppercase tracking-widest text-sm">{label}</label>}
      <input
        ref={ref}
        className={cn(
          "border-4 border-neo-black px-4 h-14 font-bold text-lg bg-white focus:bg-neo-secondary focus:shadow-neo-sm focus:outline-none focus:ring-0 transition-all rounded-none",
          error && "border-neo-accent",
          className
        )}
        {...props}
      />
      {error && <span className="text-neo-accent text-xs font-bold">{error}</span>}
    </div>
  )
);
NeoInput.displayName = "NeoInput";
