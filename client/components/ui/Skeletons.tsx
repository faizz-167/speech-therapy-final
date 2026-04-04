import { cn } from "@/lib/utils";

export function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("bg-neo-black/10 animate-pulse border-4 border-neo-black rounded-none", className)} />;
}

export function SkeletonCard() {
  return (
    <div className="border-4 border-neo-black shadow-neo-md p-6 space-y-4 bg-white">
      <SkeletonBlock className="h-8 w-1/2" />
      <SkeletonBlock className="h-5 w-3/4" />
      <SkeletonBlock className="h-5 w-1/3" />
    </div>
  );
}

export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-6">
      {Array.from({ length: count }).map((_, i) => <SkeletonCard key={i} />)}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="border-4 border-neo-black bg-neo-accent p-6 font-black uppercase shadow-neo-sm text-neo-black">
      {message}
    </div>
  );
}
