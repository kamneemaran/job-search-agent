"use client";

import { useEffect } from "react";
import { getBrowserClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const supabase = getBrowserClient();
    
    // Check if we already have a session immediately
    const checkSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        const searchParams = new URLSearchParams(window.location.search);
        const nextParam = searchParams.get("next") || "/resume";
        router.push(nextParam);
        router.refresh();
      }
    };
    checkSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event: AuthChangeEvent, session: Session | null) => {
      if (session) {
        const searchParams = new URLSearchParams(window.location.search);
        const nextParam = searchParams.get("next") || "/resume";
        router.push(nextParam);
        router.refresh();
      } else if (event === "SIGNED_OUT") {
        router.push("/auth/signin");
      }
    });

    // If there is no code in the URL and no session after 3 seconds, redirect to signin
    const searchParams = new URLSearchParams(window.location.search);
    const hasCode = searchParams.has("code");
    const timer = setTimeout(async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session && !hasCode) {
        router.push("/auth/signin");
      }
    }, 3000);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timer);
    };
  }, [router]);

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-400 mx-auto mb-4" />
        <p className="text-gray-400">Completing login...</p>
      </div>
    </div>
  );
}
