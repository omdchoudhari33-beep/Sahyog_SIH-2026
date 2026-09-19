/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Self-contained server.js build (only the traced dependencies, not the
  // full node_modules) - the standard minimal-image pattern for a
  // containerized Next.js app. No effect on `next dev`.
  output: "standalone",
};

module.exports = nextConfig;
