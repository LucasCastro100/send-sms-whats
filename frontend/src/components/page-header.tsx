import { cn } from "@/lib/utils";

/**
 * Cabeçalho padrão das telas do painel.
 */
export function PageHeader({
  titulo,
  descricao,
  sobretitulo,
  children,
  className,
}: {
  titulo: React.ReactNode;
  descricao?: React.ReactNode;
  sobretitulo?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-end justify-between gap-4 border-b border-border/70 pb-5",
        className,
      )}
    >
      <div className="space-y-1">
        {sobretitulo ? (
          <p className="text-[0.68rem] font-semibold tracking-[0.16em] text-brand uppercase">
            {sobretitulo}
          </p>
        ) : null}
        <h1 className="text-[1.65rem] leading-tight font-semibold tracking-tight">
          {titulo}
        </h1>
        {descricao ? (
          <p className="max-w-2xl text-sm text-muted-foreground">{descricao}</p>
        ) : null}
      </div>
      {children ? (
        <div className="flex flex-wrap items-center gap-2">{children}</div>
      ) : null}
    </div>
  );
}
