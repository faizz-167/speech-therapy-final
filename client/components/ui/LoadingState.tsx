import { NeoCard } from "@/components/ui/NeoCard";

interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label = "Loading..." }: LoadingStateProps) {
  return (
    <div className="min-h-[40vh] flex items-center justify-center">
      <NeoCard className="flex flex-col items-center gap-4 p-8 text-center">
        <div className="w-12 h-12 border-8 border-neo-black border-t-neo-accent animate-spin" />
        <p className="font-black uppercase tracking-widest">{label}</p>
      </NeoCard>
    </div>
  );
}
