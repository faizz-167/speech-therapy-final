interface EmptyStateProps {
  message: string;
  hint?: string;
}

export function EmptyState({ message, hint }: EmptyStateProps) {
  return (
    <div className="border-4 border-neo-black bg-white p-6 shadow-neo-sm">
      <p className="font-black uppercase tracking-wide">{message}</p>
      {hint && <p className="mt-2 text-sm font-medium text-gray-600">{hint}</p>}
    </div>
  );
}
