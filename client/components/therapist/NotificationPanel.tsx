"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { NeoButton } from "@/components/ui/NeoButton";
import { cn } from "@/lib/utils";
import type { Notification } from "@/types/therapist";

function formatRelativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function typeIcon(type: string): string {
  if (type === "patient_registered") return "👤";
  if (type === "review_flagged") return "🚩";
  return "🔔";
}

function navTarget(n: Notification): string {
  if (n.notification_type === "patient_registered" && n.patient_id != null) {
    return `/therapist/patients/${n.patient_id}`;
  }
  if (n.notification_type === "review_flagged" && n.patient_id != null) {
    return `/therapist/patients/${n.patient_id}/progress`;
  }
  return "/therapist/patients";
}

interface Props {
  onClose: () => void;
  onUnreadCountChange: (count: number) => void;
}

export function NotificationPanel({ onClose, onUnreadCountChange }: Props) {
  const router = useRouter();
  const panelRef = useRef<HTMLDivElement>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.get<Notification[]>("/therapist/notifications");
      setNotifications(data);
      onUnreadCountChange(data.filter((n) => !n.is_read).length);
    } catch {
      setError("Failed to load notifications.");
    } finally {
      setLoading(false);
    }
  }, [onUnreadCountChange]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  async function markRead(id: string): Promise<boolean> {
    const prev = notifications;
    setNotifications((ns) =>
      ns.map((n) => (n.id === id ? { ...n, is_read: true } : n))
    );
    onUnreadCountChange(
      notifications.filter((n) => !n.is_read && n.id !== id).length
    );
    try {
      await api.post(`/therapist/notifications/${id}/read`, {});
      return true;
    } catch {
      setNotifications(prev);
      onUnreadCountChange(prev.filter((n) => !n.is_read).length);
      setError("Failed to mark as read.");
      return false;
    }
  }

  async function markAllRead() {
    const prev = notifications;
    setNotifications((ns) => ns.map((n) => ({ ...n, is_read: true })));
    onUnreadCountChange(0);
    try {
      await api.post("/therapist/notifications/read-all", {});
    } catch {
      setNotifications(prev);
      onUnreadCountChange(prev.filter((n) => !n.is_read).length);
      setError("Failed to mark all as read.");
    }
  }

  async function handleClick(n: Notification) {
    const marked = await markRead(n.id);
    if (!marked) return;
    onClose();
    router.push(navTarget(n));
  }

  const hasUnread = notifications.some((n) => !n.is_read);

  return (
    <div
      ref={panelRef}
      className="absolute right-0 top-full mt-2 w-[420px] bg-white border-4 border-neo-black shadow-neo-lg z-50"
      role="dialog"
      aria-label="Notifications"
      tabIndex={-1}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b-4 border-neo-black bg-neo-accent">
        <span className="font-black uppercase tracking-widest text-sm">Notifications</span>
        <div className="flex items-center gap-2">
          {hasUnread && (
            <NeoButton size="sm" variant="ghost" onClick={markAllRead}>
              Mark all read
            </NeoButton>
          )}
          <button
            onClick={onClose}
            aria-label="Close notifications"
            className="font-black text-lg leading-none w-8 h-8 flex items-center justify-center border-4 border-neo-black bg-white hover:bg-neo-muted transition-colors"
          >
            ×
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-red-100 border-b-4 border-neo-black text-sm font-bold text-red-700 flex items-center justify-between">
          {error}
          <button onClick={() => setError(null)} className="ml-2 font-black">×</button>
        </div>
      )}

      {/* Body */}
      <div className="max-h-[480px] overflow-y-auto">
        {loading ? (
          <div className="px-4 py-8 text-center font-bold text-neo-muted">Loading…</div>
        ) : notifications.length === 0 ? (
          <div className="px-4 py-8 text-center font-bold text-neo-muted uppercase tracking-widest text-sm">
            No notifications
          </div>
        ) : (
          <ul>
            {notifications.map((n) => (
              <li key={n.id}>
                <button
                  onClick={() => handleClick(n)}
                  className={cn(
                    "w-full text-left flex items-start gap-3 px-4 py-3 border-b-2 border-neo-black transition-colors hover:bg-neo-muted focus:outline-none focus:bg-neo-muted",
                    !n.is_read && "border-l-4 border-l-neo-accent bg-neo-accent/10 font-bold"
                  )}
                  aria-label={n.message}
                >
                  <span className="text-xl flex-shrink-0 mt-0.5">{typeIcon(n.notification_type)}</span>
                  <div className="flex-1 min-w-0">
                    <p className={cn("text-sm leading-snug break-words", !n.is_read ? "font-bold" : "font-normal")}>
                      {n.message}
                    </p>
                    <p className="text-xs text-neo-muted mt-1 font-medium">{formatRelativeTime(n.created_at)}</p>
                  </div>
                  <span className="text-neo-muted flex-shrink-0 mt-1 text-sm">→</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
