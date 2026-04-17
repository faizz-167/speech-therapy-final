"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { TherapistProfile } from "@/types";

function getInitials(name: string): string {
  return name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2);
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<TherapistProfile | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get<TherapistProfile>("/therapist/profile").then(setProfile).catch((e) => setError(e.message));
  }, []);

  async function copyCode() {
    if (!profile?.therapist_code) return;
    try {
      await navigator.clipboard.writeText(profile.therapist_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback for non-secure contexts
      const el = document.createElement("textarea");
      el.value = profile.therapist_code;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  if (error) return <ErrorState message={error} />;
  if (!profile) return <LoadingState label="Loading therapist profile..." />;

  return (
    <div className="animate-fade-up p-4 md:p-8 max-w-2xl mx-auto space-y-8">

      {/* ── HEADER ── */}
      <div className="border-b-8 border-neo-black pb-6">
        <div className="inline-block bg-neo-accent border-4 border-neo-black px-4 py-1 font-black uppercase tracking-widest text-sm mb-3 rotate-1 shadow-neo-sm">
          Your Account
        </div>
        <h1 className="text-5xl font-black uppercase tracking-tighter leading-none">Profile</h1>
      </div>

      {/* ── IDENTITY CARD ── */}
      <div className="border-4 border-neo-black bg-white shadow-neo-lg overflow-hidden">
        {/* Avatar bar */}
        <div className="bg-neo-accent border-b-4 border-neo-black px-8 py-6 flex items-center gap-5">
          <div className="w-16 h-16 border-4 border-neo-black bg-white flex items-center justify-center font-black text-2xl shadow-neo-sm -rotate-2 shrink-0">
            {getInitials(profile.full_name)}
          </div>
          <div>
            <h2 className="text-3xl font-black uppercase tracking-tighter leading-none">{profile.full_name}</h2>
            <p className="font-medium text-sm text-neo-black/70 mt-1">{profile.email}</p>
          </div>
        </div>

        {/* Details grid */}
        <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[
            { label: "License Number", value: profile.license_number ?? "—" },
            { label: "Specialization", value: profile.specialization ?? "—" },
            { label: "Experience", value: profile.years_of_experience ? `${profile.years_of_experience} years` : "—" },
            { label: "Role", value: "Therapist" },
          ].map(({ label, value }) => (
            <div key={label} className="border-2 border-neo-black px-4 py-3 bg-neo-bg hover:-translate-y-0.5 hover:shadow-neo-sm transition-all duration-150">
              <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-1">{label}</p>
              <p className="font-bold text-sm">{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── THERAPIST CODE ── */}
      <div className="border-4 border-neo-black bg-neo-secondary shadow-neo-md overflow-hidden">
        <div className="bg-neo-black text-white px-6 py-3 font-black uppercase tracking-widest text-sm">
          Your Therapist Code
        </div>
        <div className="p-6 space-y-4">
          <p className="font-medium text-sm text-neo-black/70">
            Share this code with patients when they register. They&apos;ll use it to link their account to you.
          </p>

          <div className="flex items-center gap-3">
            {/* Code display */}
            <div className="flex-1 border-4 border-neo-black bg-white px-6 py-4 font-black text-4xl tracking-[0.4em] text-center shadow-neo-sm select-all">
              {profile.therapist_code}
            </div>

            {/* Copy button */}
            <button
              onClick={copyCode}
              className={`border-4 border-neo-black px-5 py-4 font-black uppercase tracking-widest text-sm shadow-neo-sm transition-all duration-150 active:translate-x-1 active:translate-y-1 active:shadow-none shrink-0 ${
                copied
                  ? "bg-neo-black text-white"
                  : "bg-white hover:bg-neo-black hover:text-white"
              }`}
              aria-label="Copy therapist code to clipboard"
            >
              {copied ? "✓ Copied!" : "Copy"}
            </button>
          </div>

          <p className="text-xs font-medium text-neo-black/50 border-t-2 border-neo-black/20 pt-3">
            Keep this code confidential — only share with patients under your care.
          </p>
        </div>
      </div>
    </div>
  );
}
