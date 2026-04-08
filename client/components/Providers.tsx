"use client";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { queryClient } from "@/lib/queryClient";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster
        toastOptions={{
          style: {
            background: "#ffffff",
            border: "3px solid #000000",
            borderRadius: "0",
            fontFamily: "inherit",
            fontWeight: "700",
            boxShadow: "4px 4px 0 #000000",
          },
        }}
        position="top-right"
      />
    </QueryClientProvider>
  );
}
