"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [montado, setMontado] = useState(false);

  useEffect(() => {
    setMontado(true);
  }, []);

  if (!montado) {
    return (
      <Button variant="ghost" size="icon" aria-label="Alternar tema">
        <Sun />
      </Button>
    );
  }

  const escuro = resolvedTheme === "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Alternar tema"
      onClick={() => setTheme(escuro ? "light" : "dark")}
    >
      {escuro ? <Sun /> : <Moon />}
    </Button>
  );
}
