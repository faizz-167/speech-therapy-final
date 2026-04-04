"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";

interface AssignedDefect { defect_id: string; name: string; category: string; }
interface Profile {
  patient_id: string;
  full_name: string;
  email: string;
  date_of_birth: string;
  gender: string | null;
  status: string;
  current_streak: number;
  assigned_defects: AssignedDefect[];
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
      {profile.assigned_defects && profile.assigned_defects.length > 0 && (
        <NeoCard className="space-y-3">
          <h2 className="font-black uppercase text-sm">Assigned Conditions</h2>
          <div className="space-y-2">
            {profile.assigned_defects.map((d) => (
              <div key={d.defect_id} className="flex items-center justify-between border-2 border-black px-3 py-2">
                <span className="font-bold">{d.name}</span>
                <span className="text-xs font-black uppercase border-2 border-black px-2 py-0.5 bg-[#FFD93D]">{d.category}</span>
              </div>
            ))}
          </div>
        </NeoCard>
      )}
      <NeoCard accent="secondary" className="text-center space-y-1">
        <div className="text-4xl font-black">{profile.current_streak}</div>
        <div className="font-black uppercase text-sm">Day Streak</div>
      </NeoCard>
    </div>
  );
}
