import type { Metadata } from "next";
import { IconPlayground } from "@/components/icon-playground";

export const metadata: Metadata = {
  title: "Icon",
  description: "Explore the 3D text-to-cad icon, its motion and color palettes.",
  alternates: { canonical: "/icon" },
  openGraph: {
    title: "Icon | text-to-cad",
    description: "Explore the 3D text-to-cad icon, its motion and color palettes.",
    url: "/icon",
    images: [{ url: "/favicon.png", width: 512, height: 512, alt: "Blue 3D text-to-cad icon" }],
  },
  twitter: {
    card: "summary",
    title: "Icon | text-to-cad",
    description: "Explore the 3D text-to-cad icon, its motion and color palettes.",
    images: ["/favicon.png"],
  },
};

export default function IconPage() {
  return <IconPlayground />;
}
