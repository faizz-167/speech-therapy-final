"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { TherapistProfile } from "@/types";

export default function ProfilePage() {
  const [profile, setProfile] = useState<TherapistProfile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<TherapistProfile>("/therapist/profile").then(setProfile).catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!profile) return <LoadingState label="Loading therapist profile..." />;

  return (
    <div className="space-y-6 animate-fade-up max-w-lg">
      <h1 className="text-3xl font-black uppercase">Profile</h1>
      <NeoCard className="space-y-3">
        <div className="grid grid-cols-2 gap-3 text-sm font-medium">
          <span className="font-black uppercase">Name:</span><span>{profile.full_name}</span>
          <span className="font-black uppercase">Email:</span><span>{profile.email}</span>
          <span className="font-black uppercase">License:</span><span>{profile.license_number ?? "—"}</span>
          <span className="font-black uppercase">Specialization:</span><span>{profile.specialization ?? "—"}</span>
          <span className="font-black uppercase">Experience:</span><span>{profile.years_of_experience ? `${profile.years_of_experience} years` : "—"}</span>
        </div>
      </NeoCard>
      <NeoCard accent="secondary" className="space-y-2">
        <p className="font-black uppercase text-sm">Your Therapist Code</p>
        <p className="text-4xl font-black tracking-widest">{profile.therapist_code}</p>
        <p className="text-xs font-medium text-gray-600">Share this code with patients when they register</p>
      </NeoCard>
    </div>
  );
}
