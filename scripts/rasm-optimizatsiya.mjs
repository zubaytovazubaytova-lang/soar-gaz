/* ============================================================
   Rasmlarni mobil uchun tayyorlaydi.
   Ishga tushirish:  npm run rasm

   Har bir JPG/PNG uchun yonida .webp nusxa yaratadi (o'lchami
   odatda 25-35% kichik). Asl fayl O'CHIRILMAYDI — WebP ni
   qo'llab-quvvatlamaydigan eski brauzerlar uchun zaxira bo'lib
   qoladi. Qaysi birini berish serverda hal qilinadi
   (backend/soargaz/urls.py -> rasm_bilan_webp).

   Skript takroriy ishga tushirilsa, faqat o'zgargan fayllarni
   qayta ishlaydi.
   ============================================================ */

import sharp from "sharp";
import { readdir, stat, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ILDIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const RASM_PAPKA = path.join(ILDIZ, "images");

// Telefon ekrani uchun eng katta mantiqiy kenglik. Bundan kattasi
// mobil qurilmada baribir kichraytirib ko'rsatiladi — bekorga trafik.
const ENG_KATTA_EN = 1400;
const WEBP_SIFAT = 82;

async function* fayllar(papka) {
  for (const nom of await readdir(papka, { withFileTypes: true })) {
    const toliq = path.join(papka, nom.name);
    if (nom.isDirectory()) yield* fayllar(toliq);
    else yield toliq;
  }
}

let yangi = 0, otkazildi = 0, tejaldi = 0;

for await (const fayl of fayllar(RASM_PAPKA)) {
  if (!/\.(jpe?g|png)$/i.test(fayl)) continue;

  const webp = fayl.replace(/\.(jpe?g|png)$/i, ".webp");

  // Allaqachon bor va asl fayldan yangi bo'lsa — qayta ishlamaymiz
  if (existsSync(webp)) {
    const [a, b] = await Promise.all([stat(fayl), stat(webp)]);
    if (b.mtimeMs >= a.mtimeMs) { otkazildi++; continue; }
  }

  const kirish = sharp(fayl);
  const meta = await kirish.metadata();

  await kirish
    .resize({ width: Math.min(meta.width ?? ENG_KATTA_EN, ENG_KATTA_EN), withoutEnlargement: true })
    .webp({ quality: WEBP_SIFAT })
    .toFile(webp);

  const [asl, natija] = await Promise.all([stat(fayl), stat(webp)]);
  tejaldi += asl.size - natija.size;
  yangi++;
  const foiz = Math.round((1 - natija.size / asl.size) * 100);
  console.log(
    `  ${path.relative(ILDIZ, webp)}  ${(asl.size / 1024).toFixed(0)} -> ` +
    `${(natija.size / 1024).toFixed(0)} KB  (${foiz}% kam)`
  );
}

console.log(
  `\nTayyor: ${yangi} ta yangi, ${otkazildi} ta o'zgarmagan. ` +
  `Jami tejaldi: ${(tejaldi / 1024 / 1024).toFixed(2)} MB`
);
