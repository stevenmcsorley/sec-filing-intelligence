import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SEC Filing Intelligence",
  description: "Real-time SEC filing insights with AI-driven analysis and RBAC.",
};

const RootLayout = ({ children }: { children: React.ReactNode }) => (
  <html lang="en">
    <body className="font-sans bg-slate-950 text-slate-100">
      <main>{children}</main>
    </body>
  </html>
);

export default RootLayout;
