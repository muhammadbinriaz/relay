import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Relay · Durable Workflow Engine",
  description: "Control plane for durable business workflows — retries, approvals, audit.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
