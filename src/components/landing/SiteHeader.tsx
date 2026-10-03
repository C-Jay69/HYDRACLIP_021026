import { Button } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import { useState } from "react";

import brandMark from "../../assets/hydraclip-mark.webp";

const NAV_LINKS = [
  { href: "#features", label: "Features" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faq", label: "FAQ" },
] as const;

export function SiteHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-border/80 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-3.5">
        <a
          href="#top"
          aria-label="HydraClip home"
          className="flex items-center gap-2.5 rounded-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <img
            src={brandMark}
            alt=""
            aria-hidden="true"
            width={512}
            height={512}
            className="size-9 rounded-xl object-cover shadow-lg shadow-blue-500/15"
          />
          <span className="text-lg font-bold tracking-[0.04em]">
            HYDRA<span className="hc-gradient-text">CLIP</span>
          </span>
        </a>

        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Button variant="ghost" asChild>
            <a href="/auth">Sign in</a>
          </Button>
          <Button asChild>
            <a href="/auth?mode=signup">Get started</a>
          </Button>
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </Button>
      </div>

      {open && (
        <div id="mobile-nav" className="border-t border-border bg-background md:hidden">
          <nav aria-label="Mobile" className="mx-auto flex max-w-7xl flex-col gap-1 px-6 py-4">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="rounded-md px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
            <div className="mt-2 flex flex-col gap-2">
              <Button variant="outline" asChild>
                <a href="/auth" onClick={() => setOpen(false)}>
                  Sign in
                </a>
              </Button>
              <Button asChild>
                <a href="/auth?mode=signup" onClick={() => setOpen(false)}>
                  Get started
                </a>
              </Button>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
