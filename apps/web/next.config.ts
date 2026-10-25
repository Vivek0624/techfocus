import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Build output folder. Overridable so a stale or unwritable .next never blocks startup.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
