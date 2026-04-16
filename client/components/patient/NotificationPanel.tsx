"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { NeoButton } from "@/components/ui/NeoButton";
import { cn } from "@/lib/utils";
import type { PatientNotification } from "@/types/patient";

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
  if (type === "therapist_approved") return "✅";
  if (type === "plan_approved") return "🗂️";
  if (type === "plan_updated") return "📝";
  if (type === "daily_task_reminder") return "📅";
  if (type === "pending_tasks") return "⏳";
  return "🔔";
}

function navTarget(notification: PatientNotification): string {
  if (notification.assignment_id) {
    return `/patient/tasks/${notification.assignment_id}`;
  }
  if (notification.notification_type === "therapist_approved") {
    return "/patient/baseline";
  }
  if (
    notification.notification_type === "plan_approved" ||
    notification.notification_type === "plan_updated" ||
    notification.notification_type === "daily_task_reminder" ||
    notification.notification_type === "pending_tasks"
  ) {
    return "/patient/tasks";
  }
  return "/patient/home";
}

interface Props {
  onClose: () => void;
  onUnreadCountChange: (count: number) => void;
}

export function NotificationPanel({ onClose, onUnreadCountChange }: Props) {
  const router = useRouter();
  const panelRef = useRef<HTMLDivElement>(null);
  const [notifications, setNotifications] = useState<PatientNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.get<PatientNotification[]>("/patient/notifications");
      setNotifications(data);
      onUnreadCountChange(data.filter((notification) => !notification.is_read).length);
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
    const previous = notifications;
    setNotifications((current) =>
      current.map((notification) =>
        notification.id === id ? { ...notification, is_read: true } : notification
      )
    );
    onUnreadCountChange(
      notifications.filter((notification) => !notification.is_read && notification.id !== id).length
    );
    try {
      await api.post(`/patient/notifications/${id}/read`, {});
      return true;
    } catch {
      setNotifications(previous);
      onUnreadCountChange(previous.filter((notification) => !notification.is_read).length);
      setError("Failed to mark as read.");
      return false;
    }
  }

  async function markAllRead() {
    const previous = notifications;
    setNotifications((current) => current.map((notification) => ({ ...notification, is_read: true })));
    onUnreadCountChange(0);
    try {
      await api.post("/patient/notifications/read-all", {});
    } catch {
      setNotifications(previous);
      onUnreadCountChange(previous.filter((notification) => !notification.is_read).length);
      setError("Failed to mark all as read.");
    }
  }

  async function handleClick(notification: PatientNotification) {
    const marked = await markRead(notification.id);
    if (!marked) return;
    onClose();
    router.push(navTarget(notification));
  }

  const hasUnread = notifications.some((notification) => !notification.is_read);

  return (
    <div
      ref={panelRef}
      className="absolute right-0 top-full mt-2 w-[420px] bg-white border-4 border-neo-black shadow-neo-lg z-50"
      role="dialog"
      aria-label="Notifications"
      tabIndex={-1}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b-4 border-neo-black bg-neo-primary">
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

      {error && (
        <div className="px-4 py-2 bg-red-100 border-b-4 border-neo-black text-sm font-bold text-red-700 flex items-center justify-between">
          {error}
          <button onClick={() => setError(null)} className="ml-2 font-black">×</button>
        </div>
      )}

      <div className="max-h-[480px] overflow-y-auto">
        {loading ? (
          <div className="px-4 py-8 text-center font-bold text-neo-muted">Loading…</div>
        ) : notifications.length === 0 ? (
          <div className="px-4 py-8 text-center font-bold text-neo-muted uppercase tracking-widest text-sm">
            No notifications
          </div>
        ) : (
          <ul>
            {notifications.map((notification) => (
              <li key={notification.id}>
                <button
                  onClick={() => handleClick(notification)}
                  className={cn(
                    "w-full text-left flex items-start gap-3 px-4 py-3 border-b-2 border-neo-black transition-colors hover:bg-neo-muted focus:outline-none focus:bg-neo-muted",
                    !notification.is_read && "border-l-4 border-l-neo-primary bg-neo-primary/10 font-bold"
                  )}
                  aria-label={notification.message}
                >
                  <span className="text-xl flex-shrink-0 mt-0.5">{typeIcon(notification.notification_type)}</span>
                  <div className="flex-1 min-w-0">
                    <p className={cn("text-sm leading-snug break-words", !notification.is_read ? "font-bold" : "font-normal")}>
                      {notification.message}
                    </p>
                    <p className="text-xs text-neo-muted mt-1 font-medium">{formatRelativeTime(notification.created_at)}</p>
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
