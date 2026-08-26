"use client";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;
export function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        "flex flex-wrap gap-1 rounded-lg bg-zinc-100 p-1 dark:bg-zinc-900",
        className
      )}
      {...props}
    />
  );
}
export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "rounded-md px-3 py-1.5 text-sm data-[state=active]:bg-white data-[state=active]:shadow dark:data-[state=active]:bg-zinc-800",
        className
      )}
      {...props}
    />
  );
}
export const TabsContent = TabsPrimitive.Content;
