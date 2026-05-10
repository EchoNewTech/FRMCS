import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone"
};

module.exports = {
  allowedDevOrigins: ['192.168.0.87'],
}


export default nextConfig;
