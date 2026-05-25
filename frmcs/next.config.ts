import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone"
};

module.exports = {
  allowedDevOrigins: ['192.168.56.1'],
}


export default nextConfig;
