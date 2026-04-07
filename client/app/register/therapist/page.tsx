"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { NeoInput } from "@/components/ui/NeoInput";
import { NeoButton } from "@/components/ui/NeoButton";
import { NeoCard } from "@/components/ui/NeoCard";
import type { TokenResponse } from "@/types";
import Link from "next/link";

export default function TherapistRegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", years_of_experience: "", specialization: "", license_number: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await api.post<TokenResponse>(
        "/auth/register/therapist",
        { ...form, years_of_experience: form.years_of_experience ? Number(form.years_of_experience) : null }
      );
      setAuth(res.access_token, res.role, res.user_id, res.full_name);
      router.push("/therapist/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <NeoCard className="w-full max-w-md space-y-6">
        <h1 className="text-2xl font-black uppercase">Therapist Registration</h1>
        {error && <div className="bg-[#FF6B6B] border-4 border-black p-3 font-bold text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <NeoInput label="Full Name" value={form.full_name} onChange={set("full_name")} required />
          <NeoInput label="Email" type="email" value={form.email} onChange={set("email")} required />
          <NeoInput label="Password" type="password" value={form.password} onChange={set("password")} required />
          <NeoInput label="Years of Experience" type="number" value={form.years_of_experience} onChange={set("years_of_experience")} />
          <NeoInput label="Specialization" value={form.specialization} onChange={set("specialization")} />
          <NeoInput label="License Number" value={form.license_number} onChange={set("license_number")} />
          <NeoButton type="submit" className="w-full" disabled={loading}>
            {loading ? "Registering..." : "Register"}
          </NeoButton>
        </form>
        <Link href="/login" className="text-sm font-bold underline">Back to Login</Link>
      </NeoCard>
    </div>
  );
}
