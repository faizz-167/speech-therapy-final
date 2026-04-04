"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { NeoInput } from "@/components/ui/NeoInput";
import { NeoButton } from "@/components/ui/NeoButton";
import { NeoCard } from "@/components/ui/NeoCard";
import Link from "next/link";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await api.post<{ access_token: string; role: string; user_id: string; full_name: string }>(
        "/auth/login",
        { email, password }
      );
      setAuth(res.access_token, res.role as "therapist" | "patient", res.user_id, res.full_name);
      router.push(res.role === "therapist" ? "/therapist/dashboard" : "/patient/home");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <NeoCard className="w-full max-w-md space-y-6">
        <h1 className="text-3xl font-black uppercase tracking-wide">SPEECHPATH</h1>
        <p className="font-bold text-gray-600">Sign in to your account</p>
        {error && <div className="bg-[#FF6B6B] border-4 border-black p-3 font-bold text-sm">{error}</div>}
        <form onSubmit={handleLogin} className="space-y-4">
          <NeoInput label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <NeoInput label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <NeoButton type="submit" className="w-full" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </NeoButton>
        </form>
        <div className="flex gap-4 text-sm font-bold">
          <Link href="/register/therapist" className="underline">Register as Therapist</Link>
          <Link href="/register/patient" className="underline">Register as Patient</Link>
        </div>
      </NeoCard>
    </div>
  );
}
