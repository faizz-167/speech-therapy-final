"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { TherapistNav } from "@/components/therapist/TherapistNav";
import { BootstrapLoader } from "@/components/ui/BootstrapLoader";

export default function TherapistLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { token, role, bootstrapped, bootstrapAuth } = useAuthStore();

  useEffect(() => {
    if (!bootstrapped) {
      bootstrapAuth();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!bootstrapped) return <BootstrapLoader />;

  if (!token || role !== "therapist") {
    router.push("/login");
    return null;
  }

  return (
    <div className="min-h-screen flex flex-col">
      <TherapistNav />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
