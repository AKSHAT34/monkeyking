/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  basePath: '/mk2026',
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://backend:8000/api/:path*' },
    ];
  },
};
module.exports = nextConfig;
