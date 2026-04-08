import { useEffect } from "react";
import { NeoButton } from "@/components/ui/NeoButton";

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
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onCancel]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onCancel}>
      <div className="bg-white border-8 border-neo-black shadow-[8px_8px_0_0_black] p-8 max-w-md w-full mx-4 space-y-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-2xl font-black uppercase">{title}</h2>
        <p className="font-medium">{message}</p>
        <div className="flex gap-3">
          <NeoButton
            onClick={onCancel}
            variant="ghost"
            className="flex-1"
          >
            {cancelLabel}
          </NeoButton>
          <NeoButton
            onClick={onConfirm}
            variant={dangerous ? "primary" : "secondary"}
            className={`flex-1 ${dangerous ? "bg-neo-accent" : "bg-neo-black text-white hover:bg-white hover:text-neo-black"}`}
          >
            {confirmLabel}
          </NeoButton>
        </div>
      </div>
    </div>
  );
}
