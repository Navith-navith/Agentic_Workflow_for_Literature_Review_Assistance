/** @type {import('next').NextConfig} */
const nextConfig = {
  // API requests to FastAPI backend are proxied through Next.js in dev
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
