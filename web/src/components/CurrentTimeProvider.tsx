"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

const CurrentTimeContext = createContext<number>(Math.floor(Date.now() / 1000));

export function CurrentTimeProvider({ children }: { children: React.ReactNode }) {
  const [currentTime, setCurrentTime] = useState(Math.floor(Date.now() / 1000));

  useEffect(() => {
    const t = setInterval(() => {
      setCurrentTime(Math.floor(Date.now() / 1000));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <CurrentTimeContext.Provider value={currentTime}>
      {children}
    </CurrentTimeContext.Provider>
  );
}

export function useCurrentTime() {
  return useContext(CurrentTimeContext);
}
