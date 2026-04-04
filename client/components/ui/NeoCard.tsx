import { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface NeoCardProps extends HTMLAttributes<HTMLDivElement> {
  accent?: "default" | "muted" | "accent" | "secondary";
  hover?: boolean;
}

export function NeoCard({ accent = "default", hover = false, className, children, ...props }: NeoCardProps) {
  const accents = {
    default: "bg-white",
    muted: "bg-[#C4B5FD]",
    accent: "bg-[#FF6B6B]",
    secondary: "bg-[#FFD93D]",
  };
  return (
    <div
      className={cn(
        "border-4 border-black shadow-[4px_4px_0px_0px_#000] p-4",
        accents[accent],
        hover && "transition-transform hover:-translate-y-1 hover:shadow-[6px_6px_0px_0px_#000] cursor-pointer",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
