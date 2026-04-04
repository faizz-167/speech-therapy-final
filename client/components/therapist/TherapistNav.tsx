"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { NeoButton } from "@/components/ui/NeoButton";
import { cn } from "@/lib/utils";

const links = [
  { href: "/therapist/dashboard", label: "Dashboard" },
  { href: "/therapist/patients", label: "Patients" },
  { href: "/therapist/profile", label: "Profile" },
];

export function TherapistNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { fullName, clearAuth } = useAuthStore();

  function logout() { clearAuth(); router.push("/login"); }

  return (
    <nav className="bg-[#FF6B6B] border-b-4 border-black px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <span className="font-black text-xl uppercase tracking-wide">SpeechPath</span>
        {links.map((l) => (
          <Link key={l.href} href={l.href}
            className={cn("font-black uppercase text-sm tracking-wide hover:underline",
              pathname.startsWith(l.href) && "underline"
            )}
          >{l.label}</Link>
        ))}
      </div>
      <div className="flex items-center gap-4">
        <span className="font-bold text-sm">{fullName}</span>
        <NeoButton size="sm" variant="ghost" onClick={logout}>Logout</NeoButton>
      </div>
    </nav>
  );
}
