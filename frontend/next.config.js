/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    dirs: ["app", "components", "hooks", "services", "domain", "types", "utils"]
  }
};

module.exports = nextConfig;
