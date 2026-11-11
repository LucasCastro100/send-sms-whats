import { cn } from "@/lib/utils";

/**
 * Nome do painel, exibido na sidebar, no header mobile e nas telas de login.
 */
export function Brand({
  className,
  tom = "padrao",
}: {
  className?: string;
  tom?: "padrao" | "claro";
}) {
  const claro = tom === "claro";

  return (
    <p
      className={cn(
        "font-heading text-[0.95rem] font-semibold tracking-tight",
        claro ? "text-white" : "text-foreground",
        className,
      )}
    >
      Gestão de membros
    </p>
  );
}
