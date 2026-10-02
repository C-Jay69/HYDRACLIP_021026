import brandLogo from "../../brand-logo.svg";
import { PLATFORM_LABELS, PlatformIcon, type Platform } from "./PlatformIcon";

const COLUMNS = [
  {
    heading: "Product",
    links: [
      { label: "Features", href: "#features" },
      { label: "How it works", href: "#how-it-works" },
      { label: "Pricing", href: "#pricing" },
      { label: "FAQ", href: "#faq" },
    ],
  },
  {
    heading: "Platforms",
    links: [
      { label: "YouTube", href: "#features" },
      { label: "Instagram", href: "#features" },
      { label: "TikTok", href: "#features" },
      { label: "X", href: "#features" },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About", href: "#top" },
      { label: "Blog", href: "#top" },
      { label: "Privacy", href: "#top" },
    ],
  },
  {
    heading: "Resources",
    links: [
      { label: "Docs", href: "#faq" },
      { label: "API", href: "#faq" },
      { label: "Status", href: "#faq" },
    ],
  },
] as const;

const SOCIALS: Platform[] = ["youtube", "instagram", "tiktok", "x"];

export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-surface px-6 py-14">
      <div className="mx-auto max-w-7xl">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-6">
          <div className="col-span-2">
            <a href="#top" className="flex items-center gap-2.5">
              <img src={brandLogo} alt="" aria-hidden="true" className="size-8 rounded-lg" />
              <span className="text-lg font-bold tracking-tight">Videoforce</span>
            </a>
            <p className="mt-4 max-w-xs text-sm text-muted-foreground">
              AI video content scheduling that runs on open-source models you control.
            </p>
            <a
              href="mailto:hello@videoforce.com"
              className="mt-4 inline-block text-sm text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline"
            >
              hello@videoforce.com
            </a>
          </div>

          {COLUMNS.map((column) => (
            <nav key={column.heading} aria-label={column.heading}>
              <h3 className="text-sm font-semibold">{column.heading}</h3>
              <ul className="mt-4 space-y-2.5">
                {column.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-border pt-8 sm:flex-row">
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} Videoforce. All rights reserved.
          </p>
          <ul className="flex items-center gap-2">
            {SOCIALS.map((platform) => (
              <li key={platform}>
                <a
                  href="#top"
                  className="flex size-9 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:border-brand/60 hover:bg-brand/15 hover:text-foreground"
                >
                  <PlatformIcon platform={platform} className="size-4" />
                  <span className="sr-only">{PLATFORM_LABELS[platform]}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </footer>
  );
}
