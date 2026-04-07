interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  dangerous?: boolean;
}

export function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  dangerous = false,
}: ConfirmModalProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-white border-8 border-neo-black shadow-[8px_8px_0_0_black] p-8 max-w-md w-full mx-4 space-y-6">
        <h2 className="text-2xl font-black uppercase">{title}</h2>
        <p className="font-medium">{message}</p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 border-4 border-neo-black px-4 py-2 font-black uppercase hover:bg-neo-muted transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`flex-1 border-4 border-neo-black px-4 py-2 font-black uppercase transition-colors ${
              dangerous
                ? "bg-neo-accent hover:bg-yellow-400"
                : "bg-neo-black text-white hover:bg-gray-800"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
