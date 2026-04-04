"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { PatientNav } from "@/components/patient/PatientNav";

export default function PatientLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { token, role, hydrated } = useAuthStore();

  useEffect(() => {
    if (!hydrated) return;
    if (!token || role !== "patient") {
      const t = setTimeout(() => router.push("/login"), 0);
      return () => clearTimeout(t);
    }
  }, [hydrated, token, role, router]);

  if (!hydrated || !token || role !== "patient") return null;

  return (
    <div className="min-h-screen flex flex-col">
      <PatientNav />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
