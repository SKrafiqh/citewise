"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { StudentProvider, useStudentGate } from "@/lib/student";
import { Loading } from "./ui";

const LINKS = [
  { href: "/", label: "Tutor" },
  { href: "/assess", label: "Assess" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/map", label: "Map" },
  { href: "/library", label: "Library" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const studentId = useStudentGate();
  const onStart = pathname === "/start";

  return (
    <>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-1 px-4 py-2">
          <span className="font-semibold">Citewise</span>
          <nav aria-label="Main" className="flex flex-wrap gap-1">
            {LINKS.map((l) => {
              const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-md px-3 py-2 text-sm ${active ? "bg-soft font-medium" : "text-muted hover:bg-soft"}`}
                >
                  {l.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {onStart ? children : studentId ? <StudentProvider value={studentId}>{children}</StudentProvider> : <Loading />}
      </main>
    </>
  );
}
