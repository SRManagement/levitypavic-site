import type { Metadata } from "next";
import { Playfair_Display, Anton } from "next/font/google";
import "./globals.css";

const playfair = Playfair_Display({
  variable: "--font-display",
  subsets: ["latin"],
  style: ["italic", "normal"],
  weight: ["600", "700", "800", "900"],
});

const anton = Anton({
  variable: "--font-condensed",
  subsets: ["latin"],
  weight: ["400"],
});

export const metadata: Metadata = {
  title: "Levity Pavic",
  description: "Levity Pavic — exclusive content and updates.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${playfair.variable} ${anton.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
