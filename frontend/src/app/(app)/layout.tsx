"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AppMobileHeader, AppSidebar } from "@/components/app-sidebar";
import { AuthProvider, useAuth } from "@/components/auth-provider";
import { Skeleton } from "@/components/ui/skeleton";

function Protegido({ children }: { children: React.ReactNode }) {
  const { usuario, carregando } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!carregando && !usuario) {
      router.replace("/login");
    }
  }, [carregando, usuario, router]);

  if (carregando) {
    return (
      <div className="flex min-h-svh items-center justify-center p-6">
        <div className="w-full max-w-md space-y-3">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    );
  }

  if (!usuario) {
    return null;
  }

  return (
    <div className="min-h-svh bg-muted/25">
      <AppSidebar />
      <AppMobileHeader />
      <main className="md:pl-[17rem]">
        <div className="mx-auto w-full max-w-6xl px-4 py-6 md:px-8 md:py-9">
          {children}
        </div>
      </main>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Protegido>{children}</Protegido>
    </AuthProvider>
  );
}
