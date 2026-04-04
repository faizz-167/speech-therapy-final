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
    <nav className="bg-neo-accent border-b-4 border-neo-black px-6 py-4 flex items-center justify-between shadow-neo-sm relative z-10 bg-pattern-halftone">
      <div className="flex items-center gap-8">
        <span className="font-black text-2xl uppercase tracking-tighter bg-white px-2 py-1 border-4 border-neo-black shadow-neo-sm -rotate-2">SpeechPath</span>
        <div className="flex items-center gap-2">
          {links.map((l) => {
            const isActive = pathname.startsWith(l.href);
            return (
              <Link key={l.href} href={l.href}
                className={cn("font-black uppercase text-sm tracking-widest px-3 py-1 border-4 transition-all duration-100 ease-linear",
                  isActive ? "bg-neo-black text-white border-neo-black rotate-1 shadow-neo-sm" : "border-transparent hover:border-neo-black hover:bg-white hover:-rotate-1 hover:shadow-neo-sm text-neo-black"
                )}
              >{l.label}</Link>
            )
          })}
        </div>
      </div>
      <div className="flex items-center gap-6">
        <span className="font-bold text-base px-3 py-1 bg-white border-4 border-neo-black shadow-neo-sm rotate-1">{fullName}</span>
        <NeoButton size="sm" variant="secondary" onClick={logout} className="-rotate-1">Logout</NeoButton>
      </div>
    </nav>
  );
}
