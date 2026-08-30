import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinTrace · Financial Operations",
  description: "Lifecycle-aware financial exception investigation for modern operations teams.",
  icons: { icon: "/icon.svg" }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
