"use client";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export function Switch({
  className,
  ...props
}: ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent bg-zinc-300 transition-colors data-[state=checked]:bg-zinc-900 dark:bg-zinc-700 dark:data-[state=checked]:bg-zinc-100",
        className
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg transition-transform data-[state=checked]:translate-x-4 dark:bg-zinc-900" />
    </SwitchPrimitive.Root>
  );
}
