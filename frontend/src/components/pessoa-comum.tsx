"use client";

import type { PresencaEvento, PresencaResumo } from "@/lib/api";
import { cn } from "@/lib/utils";

export function formatarTelefone(valor: string): string {
  const digitos = valor.replace(/\D/g, "");
  if (digitos.length === 13) {
    return `+${digitos.slice(0, 2)} (${digitos.slice(2, 4)}) ${digitos.slice(
      4,
      9,
    )}-${digitos.slice(9)}`;
  }
  if (digitos.length === 12) {
    return `+${digitos.slice(0, 2)} (${digitos.slice(2, 4)}) ${digitos.slice(
      4,
      8,
    )}-${digitos.slice(8)}`;
  }
  if (digitos.length === 11) {
    return `(${digitos.slice(0, 2)}) ${digitos.slice(2, 7)}-${digitos.slice(7)}`;
  }
  if (digitos.length === 10) {
    return `(${digitos.slice(0, 2)}) ${digitos.slice(2, 6)}-${digitos.slice(6)}`;
  }
  return valor;
}

export function classeDias(dias: number | null): string {
  if (dias === null) return "text-muted-foreground";
  if (dias <= 30) return "border-emerald-500/40 text-emerald-600 dark:text-emerald-400";
  if (dias <= 90) return "border-amber-500/40 text-amber-600 dark:text-amber-400";
  return "border-destructive/40 text-destructive";
}

export function rotuloDias(dias: number | null): string {
  if (dias === null) return "sem registro";
  if (dias <= 30) return "em dia";
  if (dias <= 90) return "atenção";
  if (dias <= 180) return "atrasada";
  return "prioridade";
}

function dataCurta(data: string): string {
  return data.length >= 10 ? data.slice(0, 5) : data;
}

export function GraficoPresenca({
  eventos,
  altura = "h-24",
}: {
  eventos: PresencaEvento[];
  altura?: string;
}) {
  if (eventos.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Ainda não há presença lançada para esta vida.
      </p>
    );
  }

  // A API devolve do mais recente para o mais antigo; o gráfico lê da
  // esquerda (antigo) para a direita (recente).
  const ordenados = [...eventos].reverse();

  return (
    <div className="space-y-2">
      <div
        className={cn(
          "flex items-end gap-1 rounded-lg border bg-muted/20 p-2",
          altura,
        )}
      >
        {ordenados.map((evento) => (
          <div
            key={`${evento.dia}-${evento.tipo}`}
            className="group flex h-full flex-1 flex-col justify-end"
            title={`${evento.data} · ${evento.tipo_rotulo} · ${
              evento.presente ? "presente" : "falta"
            }`}
          >
            <div
              className={cn(
                "w-full rounded-sm transition-opacity group-hover:opacity-70",
                evento.presente ? "bg-brand" : "bg-destructive/60",
                evento.tipo === "escola_biblica" && "border border-dashed",
              )}
              style={{ height: evento.presente ? "100%" : "35%" }}
            />
          </div>
        ))}
      </div>
      <div className="flex justify-between text-[0.65rem] text-muted-foreground">
        <span>{dataCurta(ordenados[0]?.data ?? "")}</span>
        <span>{dataCurta(ordenados[ordenados.length - 1]?.data ?? "")}</span>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[0.7rem] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="size-2 rounded-sm bg-brand" /> presente
        </span>
        <span className="flex items-center gap-1">
          <span className="size-2 rounded-sm bg-destructive/60" /> falta
        </span>
        <span className="flex items-center gap-1">
          <span className="size-2 rounded-sm border border-dashed bg-brand" />
          Escola Bíblica
        </span>
      </div>
    </div>
  );
}

export function ResumoPresenca({
  rotulo,
  resumo,
}: {
  rotulo: string;
  resumo: PresencaResumo;
}) {
  return (
    <div className="rounded-lg border bg-muted/20 p-2.5">
      <p className="text-[0.7rem] text-muted-foreground">{rotulo}</p>
      <p className="text-lg leading-tight font-semibold">
        {resumo.total ? `${resumo.percentual}%` : "—"}
      </p>
      <p className="text-[0.65rem] text-muted-foreground">
        {resumo.presencas}/{resumo.total} presenças
      </p>
    </div>
  );
}
