"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { NeoInput } from "@/components/ui/NeoInput";
import { NeoButton } from "@/components/ui/NeoButton";
import { NeoCard } from "@/components/ui/NeoCard";
import type { LoginRequest, TokenResponse } from "@/types";
import Link from "next/link";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const setSessionExpired = useAuthStore((s) => s.setSessionExpired);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showExpiredBanner, setShowExpiredBanner] = useState(false);

  useEffect(() => {
    const expired = useAuthStore.getState().sessionExpired;
    if (expired) {
      setShowExpiredBanner(true);
      setSessionExpired(false);
    }
  }, [setSessionExpired]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload: LoginRequest = { email, password };
      const res = await api.post<TokenResponse>("/auth/login", payload);
      setAuth(res.access_token, res.role, res.user_id, res.full_name);
      router.push(res.role === "therapist" ? "/therapist/dashboard" : "/patient/home");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-pattern-grid">
      <div className="relative w-full max-w-md mt-16">
        <div className="absolute -top-8 -left-8 w-20 h-20 bg-neo-accent border-4 border-neo-black rounded-none flex items-center justify-center rotate-[-15deg] z-10 shadow-neo-sm">
          <span className="font-black text-3xl">!!</span>
        </div>
        <div className="absolute -bottom-8 -right-8 w-24 h-24 bg-neo-secondary border-4 border-neo-black rounded-full flex items-center justify-center rotate-[20deg] z-10 shadow-neo-sm">
          <span className="font-black text-xl text-center leading-none">GO<br/>FAST</span>
        </div>

        <NeoCard className="relative space-y-8 z-0 bg-white border-8 p-8">
          <div className="text-center space-y-3">
            <h1 className="text-5xl font-black uppercase tracking-tighter text-stroke-black text-white drop-shadow-[4px_4px_0_rgba(0,0,0,1)]">SPEECHPATH</h1>
            <div className="inline-block">
               <p className="font-black uppercase tracking-widest text-neo-black border-4 border-neo-black px-3 py-1 bg-neo-secondary rotate-2 shadow-neo-sm">Sign in to your account</p>
            </div>
          </div>

          {showExpiredBanner && (
            <div className="border-4 border-neo-black bg-neo-accent px-6 py-4 font-black uppercase tracking-widest text-sm shadow-neo-sm mb-6">
              Session expired. Please log in again.
            </div>
          )}

          {error && <div className="bg-neo-accent border-4 border-neo-black p-4 font-black text-lg uppercase shadow-neo-sm animate-shake">{error}</div>}

          <form onSubmit={handleLogin} className="space-y-5">
            <NeoInput label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <NeoInput label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <div className="pt-2">
              <NeoButton type="submit" size="lg" className="w-full text-2xl py-6 tracking-wider border-4" disabled={loading}>
                {loading ? "SYSTEM BOOT..." : "ENTER SYSTEM ➔"}
              </NeoButton>
            </div>
          </form>

          <div className="flex flex-col gap-3 pt-6 border-t-8 border-neo-black mt-6">
            <Link href="/register/therapist" className="font-black uppercase tracking-wide hover:bg-neo-secondary p-2 transition-colors border-2 border-transparent hover:border-neo-black flex justify-between items-center group">
              <span>Register as Therapist</span>
              <span className="opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
            </Link>
            <Link href="/register/patient" className="font-black uppercase tracking-wide hover:bg-neo-primary p-2 transition-colors border-2 border-transparent hover:border-neo-black flex justify-between items-center group">
               <span>Register as Patient</span>
               <span className="opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
            </Link>
          </div>
        </NeoCard>
      </div>
    </div>
  );
}
