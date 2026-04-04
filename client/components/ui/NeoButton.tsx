import { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface NeoButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
}

export function NeoButton({ variant = "primary", size = "md", className, children, ...props }: NeoButtonProps) {
  const base = "font-black uppercase tracking-wide border-4 border-black transition-all active:translate-x-[2px] active:translate-y-[2px] active:shadow-none disabled:opacity-50 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-[#FF6B6B] text-black shadow-[4px_4px_0px_0px_#000] hover:shadow-[2px_2px_0px_0px_#000]",
    secondary: "bg-[#FFD93D] text-black shadow-[4px_4px_0px_0px_#000] hover:shadow-[2px_2px_0px_0px_#000]",
    ghost: "bg-white text-black shadow-[4px_4px_0px_0px_#000] hover:shadow-[2px_2px_0px_0px_#000]",
  };
  const sizes = { sm: "px-3 py-1 text-xs", md: "px-5 py-2 text-sm", lg: "px-8 py-3 text-base" };
  return (
    <button className={cn(base, variants[variant], sizes[size], className)} {...props}>
      {children}
    </button>
  );
}
