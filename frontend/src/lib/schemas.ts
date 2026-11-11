import { z } from "zod";

/**
 * Validação dos formulários. Toda a checagem fica aqui (zod); os campos do
 * HTML não usam `required`, `minLength` nem `pattern`.
 */

export const loginSchema = z.object({
  usuario: z.string().trim().min(1, "Informe o usuário."),
  senha: z.string().min(1, "Informe a senha."),
});

export type LoginInput = z.infer<typeof loginSchema>;

export const FUNCOES = ["admin", "lider", "frente"] as const;

export const usuarioNovoSchema = z
  .object({
    nome: z
      .string()
      .trim()
      .min(2, "Informe pelo menos 2 caracteres.")
      .max(80, "Use no máximo 80 caracteres."),
    usuario: z
      .string()
      .trim()
      .min(3, "Use pelo menos 3 caracteres.")
      .max(120, "Use no máximo 120 caracteres.")
      .regex(
        /^[a-zA-Z0-9._@-]+$/,
        "Use apenas letras, números, ponto, hífen, underline e @.",
      ),
    senha: z
      .string()
      .min(6, "A senha precisa ter pelo menos 6 caracteres.")
      .max(72, "Use no máximo 72 caracteres."),
    funcao: z.enum(FUNCOES),
    grupo_id: z.number().int().positive().nullable(),
  })
  .superRefine((dados, ctx) => {
    if (dados.funcao === "lider" && !dados.grupo_id) {
      ctx.addIssue({
        code: "custom",
        path: ["grupo_id"],
        message: "Escolha o grupo de assistência do líder.",
      });
    }
  });

export type UsuarioNovoInput = z.infer<typeof usuarioNovoSchema>;

export const senhaSchema = z.object({
  senha: z
    .string()
    .min(6, "A senha precisa ter pelo menos 6 caracteres.")
    .max(72, "Use no máximo 72 caracteres."),
});

/** Transforma o erro do zod em { campo: primeiraMensagem }. */
export function errosPorCampo(erro: z.ZodError): Record<string, string> {
  const erros: Record<string, string> = {};
  for (const problema of erro.issues) {
    const campo = String(problema.path[0] ?? "");
    if (campo && !erros[campo]) erros[campo] = problema.message;
  }
  return erros;
}
