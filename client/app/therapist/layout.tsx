"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { TherapistNav } from "@/components/therapist/TherapistNav";

export default function TherapistLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { token, role, hydrated } = useAuthStore();

  useEffect(() => {
    if (!hydrated) return;
    if (!token || role !== "therapist") {
      const t = setTimeout(() => router.push("/login"), 0);
      return () => clearTimeout(t);
    }
  }, [hydrated, token, role, router]);

  if (!hydrated || !token || role !== "therapist") return null;

  return (
    <div className="min-h-screen flex flex-col">
      <TherapistNav />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
