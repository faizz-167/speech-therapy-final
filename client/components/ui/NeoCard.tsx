import { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface NeoCardProps extends HTMLAttributes<HTMLDivElement> {
  accent?: "default" | "muted" | "accent" | "secondary";
  hover?: boolean;
}

export function NeoCard({ accent = "default", hover = false, className, children, ...props }: NeoCardProps) {
  const accents = {
    default: "bg-white",
    muted: "bg-neo-muted",
    accent: "bg-neo-accent",
    secondary: "bg-neo-secondary",
  };
  return (
    <div
      className={cn(
        "border-4 border-neo-black shadow-neo-md p-6 rounded-none bg-pattern-halftone",
        accents[accent],
        hover && "transition-all duration-200 ease-out hover:-translate-y-[4px] hover:-translate-x-[4px] hover:shadow-neo-lg cursor-pointer",
        className
      )}
      {...props}
    >
      <div className="bg-white border-4 border-neo-black p-4 h-full shadow-neo-sm">{children}</div>
    </div>
  );
}
