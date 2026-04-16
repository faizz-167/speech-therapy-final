"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { queryClient } from "@/lib/queryClient";
import { createWebSocket, WebSocketHandle } from "@/lib/ws";
import { NeoButton } from "@/components/ui/NeoButton";
import { NotificationPanel } from "@/components/patient/NotificationPanel";
import { cn } from "@/lib/utils";
import type { PatientNotification } from "@/types/patient";

const links = [
  { href: "/patient/home", label: "Home" },
  { href: "/patient/tasks", label: "Tasks" },
  { href: "/patient/progress", label: "Progress" },
  { href: "/patient/profile", label: "Profile" },
];

export function PatientNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { fullName, clearAuth, userId, bootstrapped } = useAuthStore();
  const [panelOpen, setPanelOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const bellRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocketHandle | null>(null);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const data = await api.get<PatientNotification[]>("/patient/notifications?unread_only=true");
      setUnreadCount(data.length);
    } catch {
      // Ignore polling failures.
    }
  }, []);

  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 60_000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  useEffect(() => {
    if (!bootstrapped || !userId) return;
    wsRef.current?.disconnect();
    wsRef.current = createWebSocket(
      userId,
      () => {},
      (data) => {
        if (!data || typeof data !== "object") return;
        const event = data as { type?: string };
        if (event.type !== "plan_updated") return;
        void queryClient.invalidateQueries({ queryKey: ["patient", "home"] });
        void queryClient.invalidateQueries({ queryKey: ["patient", "tasks"] });
        void queryClient.invalidateQueries({ queryKey: ["exercise"] });
        void fetchUnreadCount();
      }
    );
    return () => {
      wsRef.current?.disconnect();
      wsRef.current = null;
    };
  }, [bootstrapped, fetchUnreadCount, userId]);

  useEffect(() => {
    if (!panelOpen) return;
    function handleClickOutside(event: MouseEvent) {
      if (bellRef.current && !bellRef.current.contains(event.target as Node)) {
        setPanelOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [panelOpen]);

  async function logout() {
    try {
      await api.post("/auth/logout", {}, { handleAuthFailure: false });
    } finally {
      clearAuth();
      router.push("/login");
    }
  }

  return (
    <nav className="bg-neo-secondary border-b-4 border-neo-black px-6 py-4 flex items-center justify-between shadow-neo-sm relative z-10 bg-pattern-halftone">
      <div className="flex items-center gap-8">
        <span className="font-black text-2xl uppercase tracking-tighter bg-white px-2 py-1 border-4 border-neo-black shadow-neo-sm rotate-2">SpeechPath</span>
        <div className="flex items-center gap-2">
          {links.map((l) => {
            const isActive = pathname.startsWith(l.href);
            return (
              <Link key={l.href} href={l.href}
                className={cn("font-black uppercase text-sm tracking-widest px-3 py-1 border-4 transition-all duration-100 ease-linear",
                  isActive ? "bg-neo-black text-white border-neo-black -rotate-1 shadow-neo-sm" : "border-transparent hover:border-neo-black hover:bg-white hover:rotate-1 hover:shadow-neo-sm"
                )}
              >{l.label}</Link>
            )
          })}
        </div>
      </div>
      <div className="flex items-center gap-6">
        <div ref={bellRef} className="relative">
          <button
            onClick={() => setPanelOpen((open) => !open)}
            aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ""}`}
            aria-expanded={panelOpen}
            aria-haspopup="dialog"
            className="relative w-10 h-10 flex items-center justify-center border-4 border-neo-black bg-white shadow-neo-sm hover:bg-neo-muted transition-colors focus:outline-none focus:ring-2 focus:ring-neo-black"
          >
            <span className="text-lg" aria-hidden="true">🔔</span>
            {unreadCount > 0 && (
              <span className="absolute -top-2 -right-2 min-w-[20px] h-5 flex items-center justify-center bg-neo-accent border-2 border-neo-black text-neo-black text-xs font-black px-1 rounded-none">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </button>
          {panelOpen && (
            <NotificationPanel
              onClose={() => setPanelOpen(false)}
              onUnreadCountChange={setUnreadCount}
            />
          )}
        </div>
        <span className="font-bold text-base px-3 py-1 bg-white border-4 border-neo-black shadow-neo-sm -rotate-1">{fullName}</span>
        <NeoButton size="sm" variant="primary" onClick={logout} className="rotate-1">Logout</NeoButton>
      </div>
    </nav>
  );
}
