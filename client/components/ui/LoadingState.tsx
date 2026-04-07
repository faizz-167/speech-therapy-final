interface LoadingStateProps {
  message?: string;
}

export function LoadingState({ message = "Loading…" }: LoadingStateProps) {
  return (
    <div className="min-h-[40vh] flex items-center justify-center">
      <div className="border-4 border-neo-black shadow-neo-sm bg-white p-8 flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-8 border-neo-black border-t-neo-accent animate-spin" />
        <p className="font-black uppercase tracking-widest">{message}</p>
      </div>
    </div>
  );
}
