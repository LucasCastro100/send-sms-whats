import type { NextConfig } from "next";

// Em dev, o Next faz proxy de /api para o FastAPI (mesma origem, sem CORS).
// Em produção (Docker), API_INTERNAL_URL aponta para o serviço `api`.
// Atenção: o valor é resolvido no build (routes-manifest), por isso o
// docker-compose passa API_INTERNAL_URL como build arg.
const API_URL = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // `standalone` é para rodar em Docker/servidor próprio. Na Vercel o build
  // dela é usado, então deixamos o padrão.
  output: process.env.VERCEL ? undefined : "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
