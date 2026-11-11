import { Badge } from "@/components/ui/badge";

const ROTULOS: Record<string, string> = {
  open: "Conectado",
  connecting: "Aguardando QR",
  close: "Desconectado",
  nao_existe: "Sem instância",
  sem_chave: "Sem chave",
  erro: "Erro",
};

const CLASSES: Record<string, string> = {
  open: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  connecting: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  close: "bg-muted text-muted-foreground",
  nao_existe: "bg-muted text-muted-foreground",
  sem_chave: "bg-destructive/10 text-destructive",
  erro: "bg-destructive/10 text-destructive",
};

export function StatusWhatsApp({ estado }: { estado: string }) {
  return (
    <Badge className={CLASSES[estado] ?? CLASSES.erro}>
      {ROTULOS[estado] ?? estado}
    </Badge>
  );
}
