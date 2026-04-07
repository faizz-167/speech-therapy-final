export function BootstrapLoader() {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-neo-bg z-50">
      <div className="border-8 border-neo-black p-8 shadow-[8px_8px_0_0_black] bg-white">
        <div className="w-16 h-16 border-8 border-neo-black border-t-neo-accent rounded-full animate-spin" />
        <p className="mt-4 font-black uppercase tracking-widest text-center">Loading...</p>
      </div>
    </div>
  );
}
