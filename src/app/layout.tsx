import type { Metadata } from "next";
import { Hanken_Grotesk } from "next/font/google";
import "./globals.css";

const hankenGrotesk = Hanken_Grotesk({
  variable: "--font-hanken",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://www.levitypavic.vip"),
  title: "Levity Pavic",
  description: "Levity Pavic — exclusive content and updates.",
  // Explicit link-preview tags, so Meta (and iMessage, X, etc.) don't
  // have to guess the image from the page.
  openGraph: {
    title: "Levity Pavic",
    description: "Levity Pavic — exclusive content and updates.",
    url: "/",
    siteName: "Levity Pavic",
    type: "website",
    images: [
      {
        url: "/images/hero-bg.jpg",
        width: 1296,
        height: 2299,
        alt: "Levity Pavic",
      },
    ],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${hankenGrotesk.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        {children}
      </body>
    </html>
  );
}
