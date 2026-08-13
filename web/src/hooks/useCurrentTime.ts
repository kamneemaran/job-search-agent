"use client";

import { useState, useEffect } from "react";

/**
 * Hook that returns the current time and updates every second.
 * Only re-renders the component that uses this hook, not the entire page.
 */
export function useCurrentTime() {
  const [currentTime, setCurrentTime] = useState(Math.floor(Date.now() / 1000));

  useEffect(() => {
    const t = setInterval(() => {
      setCurrentTime(Math.floor(Date.now() / 1000));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  return currentTime;
}
