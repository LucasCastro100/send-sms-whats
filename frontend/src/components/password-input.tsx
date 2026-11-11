"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** Campo de senha com o botão de mostrar/ocultar a escrita. */
export function PasswordInput({
  className,
  ...props
}: React.ComponentProps<typeof Input>) {
  const [visivel, setVisivel] = useState(false);

  return (
    <div className="relative">
      <Input
        {...props}
        type={visivel ? "text" : "password"}
        className={cn("pr-11", className)}
      />
      <button
        type="button"
        onClick={() => setVisivel((atual) => !atual)}
        aria-label={visivel ? "Ocultar senha" : "Mostrar senha"}
        aria-pressed={visivel}
        title={visivel ? "Ocultar senha" : "Mostrar senha"}
        data-slot="password-toggle"
        className="absolute inset-y-1 right-1 z-10 flex w-9 items-center justify-center rounded-lg text-brand transition-colors hover:bg-brand-soft focus-visible:bg-brand-soft focus-visible:outline-none"
      >
        {visivel ? (
          <EyeOff className="size-[1.05rem]" />
        ) : (
          <Eye className="size-[1.05rem]" />
        )}
      </button>
    </div>
  );
}
