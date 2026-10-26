import type { NextConfig } from "next";
const config: NextConfig = {
  poweredByHeader: false,
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
  reactStrictMode: true,
};
export default config;
