import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "@/styles/globals.css";
import { Toaster } from "react-hot-toast";
import { Navbar, Footer } from "@/components/common";
import ReduxProvider from "@/redux/provider";


const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FRMCS",
  description: "Application for testing FRMCS",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
        <ReduxProvider>
          <Navbar></Navbar>

          <Toaster position="top-right" />

          <div className="mx-auto max-w-7xl px-2 sm:px-6 lg:px-8 my-8">{children}</div>
          <Footer></Footer>
        </ReduxProvider>
      </body>
    </html>
  );
}
