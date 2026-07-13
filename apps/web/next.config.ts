import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const api = process.env.INTERNAL_API_URL ?? "http://localhost:8000"
    return [
      { source: "/api/docs", destination: `${api}/docs` },
      { source: "/api/openapi.json", destination: `${api}/openapi.json` },
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/health", destination: `${api}/health` },
    ]
  },
};

export default nextConfig;
