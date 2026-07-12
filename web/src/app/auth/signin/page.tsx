"use client";

import { useState } from "react";
import { getBrowserClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const supabase = getBrowserClient();
    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      setError(authError.message);
      setLoading(false);
    } else {
      router.push("/dashboard");
      router.refresh();
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold">Sign in to JobPilot</h1>
          <p className="text-gray-400 mt-2">
            Track your applications and get personalized matches.
          </p>
        </div>

        <form
          onSubmit={handleSignIn}
          className="rounded-2xl border border-gray-800 bg-gray-900/50 p-8 space-y-5"
        >
          {error && (
            <div className="rounded-lg bg-red-900/20 border border-red-800 p-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-indigo-600 px-4 py-3 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>

          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-700" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-gray-900 px-2 text-gray-500">or continue with</span>
            </div>
          </div>

          <button
            type="button"
            onClick={async () => {
              const supabase = getBrowserClient();
              await supabase.auth.signInWithOAuth({
                provider: "google",
                options: { redirectTo: `${window.location.origin}/auth/callback` },
              });
            }}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 font-semibold text-white hover:bg-gray-700 transition-colors"
          >
            Sign in with Google
          </button>

          <p className="text-center text-sm text-gray-500">
            Don&apos;t have an account?{" "}
            <Link
              href="/auth/signup"
              className="text-indigo-400 hover:text-indigo-300"
            >
              Sign up free
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
