"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { PatientNav } from "@/components/patient/PatientNav";
import { BootstrapLoader } from "@/components/ui/BootstrapLoader";

export default function PatientLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { token, role, bootstrapped, bootstrapAuth } = useAuthStore();

  useEffect(() => {
    if (!bootstrapped) {
      bootstrapAuth();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!bootstrapped) return <BootstrapLoader />;

  if (!token || role !== "patient") {
    router.push("/login");
    return null;
  }

  return (
    <div className="min-h-screen flex flex-col">
      <PatientNav />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
