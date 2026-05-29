import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes (used by shadcn/ui in Step 2). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
