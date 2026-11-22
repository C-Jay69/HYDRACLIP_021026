import "./globals.css";
import { Providers } from "./providers";

export const metadata = {
  title: "HydraClip — AI Video Studio",
  description:
    "Generate short-form videos with OpenRouter and Remotion, then schedule and publish them.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
