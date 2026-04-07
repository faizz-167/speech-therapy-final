"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { PatientNav } from "@/components/patient/PatientNav";
import { BootstrapLoader } from "@/components/ui/BootstrapLoader";
import { onAuthExpired } from "@/lib/api";

export default function PatientLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { role, hydrated, bootstrapped, bootstrapAuth } = useAuthStore();

  useEffect(() => {
    if (!hydrated) return;
    void bootstrapAuth();
  }, [hydrated, bootstrapAuth]);

  useEffect(() => onAuthExpired(() => router.push("/login")), [router]);

  useEffect(() => {
    if (bootstrapped && role !== "patient") {
      router.push("/login");
    }
  }, [bootstrapped, role, router]);

  if (!hydrated || !bootstrapped) return <BootstrapLoader />;
  if (role !== "patient") return null;

  return (
    <div className="min-h-screen flex flex-col">
      <PatientNav />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
