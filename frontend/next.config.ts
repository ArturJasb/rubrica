import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Exporta o site como arquivos estáticos (pasta out/): servido por CDN, não "dorme" no plano grátis
  output: "export",
  trailingSlash: true,
};

export default nextConfig;
