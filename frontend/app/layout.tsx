import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rubrica · entrevistas estruturadas com IA",
  description:
    "Rubrica grava, transcreve e resume entrevistas de recrutamento no Google Meet e Teams, entregando uma rubrica de avaliação estruturada.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
