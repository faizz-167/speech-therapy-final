"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";

interface Profile {
  patient_id: string;
  full_name: string;
  email: string;
  date_of_birth: string;
  gender: string | null;
  status: string;
  current_streak: number;
}

export default function PatientProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Profile>("/patient/profile")
      .then(setProfile)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <ErrorBanner message={error} />;
  if (!profile) return <SkeletonList count={1} />;

  return (
    <div className="space-y-6 animate-fade-up max-w-lg">
      <h1 className="text-3xl font-black uppercase">Profile</h1>
      <NeoCard className="space-y-3">
        <div className="grid grid-cols-2 gap-3 text-sm font-medium">
          <span className="font-black uppercase">Name:</span>
          <span>{profile.full_name}</span>
          <span className="font-black uppercase">Email:</span>
          <span>{profile.email}</span>
          <span className="font-black uppercase">DOB:</span>
          <span>{profile.date_of_birth}</span>
          <span className="font-black uppercase">Gender:</span>
          <span>{profile.gender ?? "—"}</span>
          <span className="font-black uppercase">Status:</span>
          <span className="font-black uppercase">{profile.status}</span>
        </div>
      </NeoCard>
      <NeoCard accent="secondary" className="text-center space-y-1">
        <div className="text-4xl font-black">{profile.current_streak}</div>
        <div className="font-black uppercase text-sm">Day Streak</div>
      </NeoCard>
    </div>
  );
}
