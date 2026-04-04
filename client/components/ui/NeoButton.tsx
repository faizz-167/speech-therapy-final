import { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface NeoButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
}

export function NeoButton({ variant = "primary", size = "md", className, children, ...props }: NeoButtonProps) {
  const base = "font-black uppercase tracking-wide border-4 border-neo-black rounded-none transition-all duration-100 ease-linear active:translate-x-[4px] active:translate-y-[4px] active:shadow-none disabled:opacity-50 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-neo-accent text-neo-black shadow-neo-sm hover:brightness-95",
    secondary: "bg-neo-secondary text-neo-black shadow-neo-sm hover:brightness-95",
    ghost: "bg-white text-neo-black shadow-neo-sm hover:bg-neo-muted",
  };
  const sizes = { sm: "h-10 px-4 text-sm", md: "h-14 px-6 text-base", lg: "h-16 px-10 text-lg" };
  return (
    <button className={cn(base, variants[variant], sizes[size], className)} {...props}>
      {children}
    </button>
  );
}
