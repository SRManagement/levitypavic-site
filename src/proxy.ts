import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Countries that get the "not available in your region" page instead of
// the site. Two-letter ISO country codes — add or remove any time, then
// commit and Vercel redeploys automatically.
const BLOCKED_COUNTRIES = new Set([
  "IN", // India
  "PK", // Pakistan
  "BD", // Bangladesh
  "NP", // Nepal
  "LK", // Sri Lanka
  "NG", // Nigeria
  "EG", // Egypt
  "MA", // Morocco
  "DZ", // Algeria
  "ID", // Indonesia
  "VN", // Vietnam
  "PH", // Philippines
]);

// Plain HTML, no scripts, no images — blocked visitors download a couple of
// kilobytes and nothing else. Fonts match the site's own system stacks, so
// no external files are needed.
const BLOCKED_HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="robots" content="noindex" />
<title>Not available</title>
<style>
  html, body { margin: 0; height: 100%; background: #000; }
  body { display: flex; align-items: center; justify-content: center; padding: 0 24px; text-align: center; }
  h1 { margin: 0; color: #fff; font: 700 20px/1.3 "Helvetica Neue", Helvetica, Arial, sans-serif; text-transform: uppercase; letter-spacing: 0.02em; }
  p { margin: 12px 0 0; color: #8a8a8a; font: 12px/1.6 "SF Mono", ui-monospace, Menlo, monospace; }
</style>
</head>
<body>
  <div>
    <h1>Not available in your region</h1>
    <p>This page isn't available where you are.</p>
  </div>
</body>
</html>`;

export function proxy(request: NextRequest) {
  // Vercel adds this header to every request. It's missing when running
  // locally, which simply means nobody is blocked during local testing.
  const country = request.headers.get("x-vercel-ip-country")?.toUpperCase();

  if (!country || !BLOCKED_COUNTRIES.has(country)) {
    return NextResponse.next();
  }

  // Blocked visitors also can't hit the tracking endpoints directly, so
  // they can't inflate your stats.
  if (request.nextUrl.pathname.startsWith("/api/")) {
    return new NextResponse(null, { status: 403 });
  }

  return new NextResponse(BLOCKED_HTML, {
    status: 403,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

export const config = {
  // Runs on pages and API routes. Skips Next's own build files and anything
  // that's a plain media file (images, video, audio, icons), so it never
  // slows down asset loading for everyone else.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|gif|webp|svg|ico|mp4|mp3)$).*)",
  ],
};
