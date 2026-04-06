"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
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
    <div className="space-y-6 animate-fade-up max-w-3xl mx-auto pt-8">
      <h1 className="text-3xl font-black uppercase tracking-wide px-2">My Profile</h1>
      
      {/* Name and Email Header */}
      <div className="bg-neo-accent border-4 border-neo-black p-6 flex items-center gap-6 shadow-neo-sm relative overflow-hidden group">
        <div className="w-20 h-20 bg-neo-black text-white font-black text-4xl flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
          {profile.full_name.charAt(0).toUpperCase()}
        </div>
        <div>
          <h2 className="text-3xl font-black">{profile.full_name}</h2>
          <p className="font-bold text-lg">{profile.email}</p>
        </div>
      </div>

      {/* Streaks */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-neo-warning border-4 border-neo-black p-4 text-center shadow-neo-sm hover:-translate-y-1 transition-transform">
          <div className="text-4xl font-black pb-2">🔥 {profile.current_streak}</div>
          <div className="font-black uppercase tracking-widest text-sm border-t-4 border-neo-black pt-2">Current Streak</div>
        </div>
        <div className="bg-neo-secondary border-4 border-neo-black p-4 text-center shadow-neo-sm hover:-translate-y-1 transition-transform">
          <div className="text-4xl font-black pb-2">⭐ {profile.current_streak}</div>
          <div className="font-black uppercase tracking-widest text-sm border-t-4 border-neo-black pt-2">Best Streak</div>
        </div>
      </div>

      {/* Details List */}
      <div className="bg-white border-4 border-neo-black shadow-neo-sm">
        <div className="flex justify-between items-center px-4 py-4 border-b-4 border-neo-black hover:bg-gray-50">
          <span className="font-black uppercase text-gray-500 tracking-wider">Date of Birth</span>
          <span className="font-black text-lg">{profile.date_of_birth}</span>
        </div>
        <div className="flex justify-between items-center px-4 py-4 border-b-4 border-neo-black hover:bg-gray-50">
          <span className="font-black uppercase text-gray-500 tracking-wider">Gender</span>
          <span className="font-black text-lg lowercase">{profile.gender ?? "—"}</span>
        </div>
        <div className="flex justify-between items-center px-4 py-4 border-b-4 border-neo-black hover:bg-gray-50">
          <span className="font-black uppercase text-gray-500 tracking-wider">Status</span>
          <span className="font-black text-lg uppercase">{profile.status}</span>
        </div>
        <div className="flex justify-between items-center px-4 py-4 border-b-4 border-neo-black hover:bg-gray-50">
          <span className="font-black uppercase text-gray-500 tracking-wider">Therapist</span>
          <span className="font-black text-lg">Faiz</span>
        </div>
        <div className="flex justify-between items-center px-4 py-4 border-b-4 border-neo-black hover:bg-gray-50">
          <span className="font-black uppercase text-gray-500 tracking-wider">Diagnosis</span>
          <span className="font-black text-lg">—</span>
        </div>
        <div className="flex justify-between items-center px-4 py-4 hover:bg-gray-50">
          <span className="font-black uppercase text-gray-500 tracking-wider">Member Since</span>
          <span className="font-black text-lg">01/04/2026</span>
        </div>
      </div>

      {/* Defects */}
      {profile.assigned_defects && profile.assigned_defects.length > 0 && (
        <div className="bg-white border-4 border-neo-black p-6 shadow-neo-sm">
          <h3 className="font-black uppercase tracking-wider mb-6">Assigned Defects</h3>
          <div className="flex flex-wrap gap-4">
            {profile.assigned_defects.map((d) => (
              <div key={d.defect_id} className="font-bold border-4 border-neo-black px-4 py-2 bg-neo-secondary shadow-neo-sm flex flex-col gap-1 items-start group hover:-translate-y-1 transition-transform">
                <span className="text-xl uppercase tracking-tight">{d.name}</span>
                <span className="text-xs uppercase tracking-widest font-black opacity-80">{d.category}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
