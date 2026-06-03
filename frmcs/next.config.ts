import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone"
};

module.exports = {
  allowedDevOrigins: ['192.168.1.219'],
}


export default nextConfig;
