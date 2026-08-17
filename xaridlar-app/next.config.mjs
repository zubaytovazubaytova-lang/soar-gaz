/** @type {import('next').NextConfig} */

// Productionda do'kon asosiy domen ostida `/xaridlar/` manzilida turadi
// (nginx uni shu ilovaga proxy qiladi), shuning uchun Next.js o'z
// resurslarini ham shu prefiks bilan berishi kerak.
// Dev rejimda prefiks bo'sh — ilova localhost:3000 ildizida ochiladi.
//   Production: NEXT_BASE_PATH=/xaridlar npm run build && npm start
const basePath = process.env.NEXT_BASE_PATH || "";

const nextConfig = {
  reactStrictMode: true,
  basePath,
  // Skript va rasm havolalari ham shu prefiksdan boshlanadi
  assetPrefix: basePath || undefined,
  // Klient kodida kerak bo'lsa (masalan qo'lda qurilgan havolalar uchun)
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};

export default nextConfig;
