import { InputHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

interface NeoInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const NeoInput = forwardRef<HTMLInputElement, NeoInputProps>(
  ({ label, error, className, ...props }, ref) => (
    <div className="flex flex-col gap-1">
      {label && <label className="font-black uppercase text-xs tracking-wide">{label}</label>}
      <input
        ref={ref}
        className={cn(
          "border-4 border-black px-3 py-2 font-medium bg-white focus:bg-[#FFD93D] focus:outline-none transition-colors",
          error && "border-[#FF6B6B]",
          className
        )}
        {...props}
      />
      {error && <span className="text-[#FF6B6B] text-xs font-bold">{error}</span>}
    </div>
  )
);
NeoInput.displayName = "NeoInput";
