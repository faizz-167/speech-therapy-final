import { NeoButton } from "@/components/ui/NeoButton";
import { NeoCard } from "@/components/ui/NeoCard";

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}

export function ErrorState({ message, onRetry, retryLabel = "Try Again" }: ErrorStateProps) {
  return (
    <div className="min-h-[40vh] flex items-center justify-center">
      <NeoCard accent="accent" className="mx-4 max-w-md space-y-4 p-8 text-center">
        <p className="font-black uppercase tracking-wide text-neo-black">{message}</p>
        {onRetry && (
          <NeoButton onClick={onRetry} variant="ghost">
            {retryLabel}
          </NeoButton>
        )}
      </NeoCard>
    </div>
  );
}
