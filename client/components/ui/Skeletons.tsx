import { cn } from "@/lib/utils";

export function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("bg-gray-200 animate-pulse border-2 border-black", className)} />;
}

export function SkeletonCard() {
  return (
    <div className="border-4 border-black shadow-[4px_4px_0px_0px_#000] p-4 space-y-3">
      <SkeletonBlock className="h-5 w-1/2" />
      <SkeletonBlock className="h-4 w-3/4" />
      <SkeletonBlock className="h-4 w-1/3" />
    </div>
  );
}

export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => <SkeletonCard key={i} />)}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="border-4 border-black bg-[#FF6B6B] p-4 font-black uppercase">
      {message}
    </div>
  );
}
