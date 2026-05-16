"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  {
    href: "/",
    label: "Chat Workspace",
    description: "Streaming AI chat",
  },
  {
    href: "/documents",
    label: "Document Assistant",
    description: "PDF RAG Q&A",
  },
];

export default function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="mx-auto mb-8 mt-6 w-full max-w-6xl px-6">
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-2 shadow-lg shadow-black/20">
        <div className="grid gap-2 sm:grid-cols-2">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-xl px-4 py-3 transition ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
                }`}
              >
                <div className="text-sm font-semibold">{item.label}</div>
                <div
                  className={`mt-1 text-xs ${
                    isActive ? "text-blue-100" : "text-zinc-500"
                  }`}
                >
                  {item.description}
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
