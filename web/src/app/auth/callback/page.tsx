"use client";

import { useEffect } from "react";
import { getBrowserClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const supabase = getBrowserClient();
    supabase.auth.onAuthStateChange((event, session) => {
      if (session) {
        router.push("/dashboard");
      } else {
        router.push("/auth/signin");
      }
    });
  }, [router]);

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-400 mx-auto mb-4" />
        <p className="text-gray-400">Confirming your email...</p>
      </div>
    </div>
  );
}
