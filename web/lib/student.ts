"use client";

import { createContext, useContext, useEffect, useMemo, useSyncExternalStore } from "react";
import { usePathname, useRouter } from "next/navigation";

const KEY = "student_id";

export function readStudentId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function saveStudentId(id: string) {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* storage blocked: id lasts only for this page load */
  }
}

export function sessionGet<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function sessionSet(key: string, value: unknown) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

const subscribe = (cb: () => void) => {
  window.addEventListener("storage", cb);
  return () => window.removeEventListener("storage", cb);
};

/** undefined = not known yet (server render), null = no student, string = student id. */
export function useStoredStudentId(): string | null | undefined {
  return useSyncExternalStore(subscribe, readStudentId, () => undefined);
}

const StudentContext = createContext<string | null>(null);
export const StudentProvider = StudentContext.Provider;

export function useStudent(): string {
  const id = useContext(StudentContext);
  if (!id) throw new Error("useStudent used outside StudentGate");
  return id;
}

/** Redirects to /start when there is no student id; renders children only once there is one. */
export function useStudentGate(): string | null {
  const id = useStoredStudentId();
  const pathname = usePathname();
  const router = useRouter();
  const needsStudent = pathname !== "/start";
  useEffect(() => {
    if (needsStudent && id === null) router.replace("/start");
  }, [needsStudent, id, router]);
  return id ?? null;
}

const noopSubscribe = () => () => {};

/** JSON from sessionStorage: undefined = not known yet (server render), null = missing. */
export function useSessionJson<T>(key: string): T | null | undefined {
  const raw = useSyncExternalStore(
    noopSubscribe,
    () => {
      try {
        return sessionStorage.getItem(key);
      } catch {
        return null;
      }
    },
    () => undefined,
  );
  return useMemo(() => {
    if (raw === undefined) return undefined;
    try {
      return raw ? (JSON.parse(raw) as T) : null;
    } catch {
      return null;
    }
  }, [raw]);
}
