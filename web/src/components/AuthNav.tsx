"use client";

import { useState, useEffect } from "react";
import { getBrowserClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import Link from "next/link";
import type { User } from "@supabase/supabase-js";

export default function AuthNav() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const supabase = getBrowserClient();
    supabase.auth.getUser().then((res: any) => {
      setUser(res?.data?.user || null);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event: any, session: any) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  const handleSignOut = async () => {
    const supabase = getBrowserClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  };

  if (loading) {
    return (
      <div className="flex items-center gap-4 text-sm font-medium text-gray-400">
        <div className="h-8 w-20 rounded-lg bg-gray-800 animate-pulse" />
      </div>
    );
  }

  if (user) {
    return (
      <div className="flex items-center gap-4 text-sm font-medium text-gray-400">
        <Link
          href="/resume"
          className="hover:text-white transition-colors"
        >
          Resume
        </Link>
        <Link
          href="/search"
          className="hover:text-white transition-colors"
        >
          Search
        </Link>
        <Link
          href="/dashboard"
          className="hover:text-white transition-colors"
        >
          Dashboard
        </Link>
        <Link
          href="/settings"
          className="hover:text-white transition-colors"
        >
          Settings
        </Link>
        <Link
          href="/guide"
          className="hover:text-white transition-colors text-indigo-400 font-semibold"
        >
          Guide
        </Link>
        <button
          onClick={handleSignOut}
          className="rounded-lg border border-gray-700 px-3 py-1.5 text-gray-300 hover:bg-gray-800 transition-colors"
        >
          Sign Out
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 text-sm font-medium text-gray-400">
      <Link href="/guide" className="hover:text-white transition-colors text-indigo-400 font-semibold">
        Guide
      </Link>
      <Link href="/auth/signin" className="hover:text-white transition-colors">
        Sign In
      </Link>
      <Link
        href="/auth/signup"
        className="rounded-lg bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-500 transition-colors"
      >
        Get Started
      </Link>
    </div>
  );
}
