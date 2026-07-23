import type { Metadata } from "next";
import { JetBrains_Mono, Newsreader } from "next/font/google";
import { GeistSans } from "geist/font/sans";
import "./globals.css";

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

const serif = Newsreader({
  subsets: ["latin"],
  weight: ["400"],
  style: ["normal", "italic"],
  variable: "--font-serif",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://encodebench.org"),
  title: "EncodeBench — can a model write the law as code?",
  description:
    "EncodeBench measures how well AI models encode statutes into cited, executable rules, graded by deterministic gates: the encoding compiles, passes CI, and contains no number the source text doesn't. From The Axiom Foundation.",
  openGraph: {
    title: "EncodeBench",
    description:
      "Can a model write the law as code? A benchmark from The Axiom Foundation, sister to PolicyBench.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${mono.variable} ${GeistSans.variable} ${serif.variable}`}
    >
      <head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
      </head>
      <body>{children}</body>
    </html>
  );
}
