"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { NeoInput } from "@/components/ui/NeoInput";
import { NeoButton } from "@/components/ui/NeoButton";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoSelect } from "@/components/ui/NeoSelect";
import Link from "next/link";

export default function PatientRegisterPage() {
  const [form, setForm] = useState({ full_name: "", email: "", password: "", date_of_birth: "", gender: "", therapist_code: "" });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.post("/auth/register/patient", form);
      setSuccess(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  if (success) return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <NeoCard className="w-full max-w-md space-y-4" accent="secondary">
        <h2 className="text-xl font-black uppercase">Registration Submitted!</h2>
        <p className="font-bold">Your account is pending therapist approval. You will be able to log in once approved.</p>
        <Link href="/login"><NeoButton className="w-full">Back to Login</NeoButton></Link>
      </NeoCard>
    </div>
  );

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <NeoCard className="w-full max-w-md space-y-6">
        <h1 className="text-2xl font-black uppercase">Patient Registration</h1>
        {error && <div className="bg-[#FF6B6B] border-4 border-black p-3 font-bold text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <NeoInput label="Full Name" value={form.full_name} onChange={set("full_name")} required />
          <NeoInput label="Email" type="email" value={form.email} onChange={set("email")} required />
          <NeoInput label="Password" type="password" value={form.password} onChange={set("password")} required />
          <NeoInput label="Date of Birth" type="date" value={form.date_of_birth} onChange={set("date_of_birth")} required />
          <NeoSelect label="Gender" value={form.gender} onChange={set("gender")}>
            <option value="">Select gender</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </NeoSelect>
          <NeoInput label="Therapist Code" value={form.therapist_code} onChange={set("therapist_code")} required placeholder="e.g. AW8GFF02" />
          <NeoButton type="submit" className="w-full" disabled={loading}>
            {loading ? "Registering..." : "Register"}
          </NeoButton>
        </form>
        <Link href="/login" className="text-sm font-bold underline">Back to Login</Link>
      </NeoCard>
    </div>
  );
}
