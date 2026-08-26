import * as React from "react";
import { cn } from "@/lib/utils";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "flex h-9 w-full rounded-md border border-zinc-300 bg-transparent px-3 py-1 text-sm shadow-sm outline-none focus:ring-2 focus:ring-zinc-400 dark:border-zinc-700",
        className
      )}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      className={cn(
        "flex min-h-[80px] w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-400 dark:border-zinc-700",
        className
      )}
      {...props}
    />
  );
}

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return <label className={cn("text-sm font-medium leading-none", className)} {...props} />;
}

export function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950",
        className
      )}
      {...props}
    />
  );
}

export function Badge({
  className,
  tone = "neutral",
  ...props
}: React.ComponentProps<"span"> & { tone?: "ok" | "bad" | "neutral" | "busy" }) {
  const colors = {
    ok: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
    bad: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200",
    busy: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
    neutral: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200",
  };
  return (
    <span
      className={cn("inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium", colors[tone], className)}
      {...props}
    />
  );
}
