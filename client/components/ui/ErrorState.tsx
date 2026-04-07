interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}

export function ErrorState({ message, onRetry, retryLabel = "Try Again" }: ErrorStateProps) {
  return (
    <div className="min-h-[40vh] flex items-center justify-center">
      <div className="border-4 border-neo-black bg-neo-accent shadow-neo-sm p-8 max-w-md w-full mx-4 space-y-4">
        <p className="font-black uppercase tracking-wide text-neo-black">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="border-4 border-neo-black bg-white px-6 py-2 font-black uppercase hover:bg-neo-black hover:text-white transition-colors"
          >
            {retryLabel}
          </button>
        )}
      </div>
    </div>
  );
}
