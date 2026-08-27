import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/Navbar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "AI AssemblyTwin | DigitalTwin.ai",
  description:
    "Live digital twin of a vehicle assembly line — predicts bottlenecks and defects before they happen.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen" style={{ background: "var(--bg)" }}>
        <Navbar />
        <main className="pt-16">{children}</main>
      </body>
    </html>
  );
}
