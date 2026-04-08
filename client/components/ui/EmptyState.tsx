import type { ReactNode } from "react";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";

interface EmptyStateProps {
  icon?: ReactNode;
  heading: string;
  subtext?: string;
  cta?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon, heading, subtext, cta }: EmptyStateProps) {
  return (
    <div className="min-h-[32vh] flex items-center justify-center">
      <NeoCard className="max-w-xl space-y-4 p-8 text-center">
        {icon ? <div className="text-4xl">{icon}</div> : null}
        <h2 className="text-2xl font-black uppercase tracking-tight">{heading}</h2>
        {subtext ? <p className="text-sm font-medium text-neo-black/70">{subtext}</p> : null}
        {cta ? (
          <div className="pt-2">
            <NeoButton onClick={cta.onClick}>{cta.label}</NeoButton>
          </div>
        ) : null}
      </NeoCard>
    </div>
  );
}
