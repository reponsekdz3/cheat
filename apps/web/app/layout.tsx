import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Exam Integrity | Rwanda",
  description: "Secure examination operations and evidence-based integrity review.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
