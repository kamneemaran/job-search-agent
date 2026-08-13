"use client";

import { useState, useEffect } from "react";

interface TimerProps {
  children: (currentTime: number) => React.ReactNode;
}

export function CurrentTimeUpdater({ children }: TimerProps) {
  const [currentTime, setCurrentTime] = useState(Math.floor(Date.now() / 1000));

  useEffect(() => {
    const t = setInterval(() => {
      setCurrentTime(Math.floor(Date.now() / 1000));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  return <>{children(currentTime)}</>;
}
