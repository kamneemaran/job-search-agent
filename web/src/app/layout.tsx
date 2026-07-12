import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import AuthNav from "@/components/AuthNav";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "JobPilot — AI Job Search for Tech Roles",
  description:
    "AI-powered job search engine for software engineers and IT professionals. Auto-score, match, and track your applications.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-gray-950 text-gray-100">
        <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-md sticky top-0 z-50">
          <nav className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 font-bold text-xl">
              <span className="text-indigo-400">&#9992;</span>
              <span>JobPilot</span>
            </Link>
            <AuthNav />
          </nav>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-gray-800 py-6 text-center text-sm text-gray-500">
          JobPilot &mdash; AI-powered job search for tech roles
        </footer>
      </body>
    </html>
  );
}
