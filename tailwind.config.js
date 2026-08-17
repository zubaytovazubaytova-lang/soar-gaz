/** @type {import('tailwindcss').Config} */

// DIQQAT: bu konfiguratsiya ilgari index.html ichida `tailwind.config = {...}`
// ko'rinishida CDN uchun yozilgan edi. Endi CSS build vaqtida generatsiya
// qilinadi (`npm run css`), shuning uchun mavzu shu yerda turadi.
// Ranglarni o'zgartirgandan keyin CSS ni QAYTA build qilish shart.

module.exports = {
  content: ["./index.html"],

  // Tailwind sinf nomlarini fayl matnidan qidiradi. index.html ichidagi JS
  // ba'zi sinflarni yig'ib quradi (`text-${b.rang}-400` kabi) — bunday
  // nomlar matnda to'liq uchramaydi, shuning uchun qo'lda sanab o'tamiz.
  // Aks holda ular build'dan tushib qoladi va rang yo'qoladi.
  safelist: [
    // `text-${b.rang}-300|400` va `focus:border-${b.rang}-500`
    // b.rang qiymatlari: cobalt | gold | teal
    "text-cobalt-300", "text-gold-300", "text-teal-300",
    "text-cobalt-400", "text-gold-400", "text-teal-400",
    "focus:border-cobalt-500", "focus:border-gold-500", "focus:border-teal-500",
    // _otpStartCountdown(..., 'blue')
    "text-blue-400",
  ],

  theme: {
    extend: {
      colors: {
        // Suyuq shisha mavzusi — sirtlar shaffof ko'k tuslar
        navy:   { 950:'#f2f8ff', 900:'#eef5ff', 800:'#e8f1fd', 700:'#e0ecfb', 600:'#c9dcf4', 500:'#b5cff0' },
        // Matn — to'q ko'k-kulrang
        ink:    { 900:'#1c3d63', 700:'#2f5580', 500:'#5b7fa6' },
        // Barcha urg'ular bitta ko'k oilada
        gold:   { 300:'#6fb0ee', 400:'#0d6efd', 500:'#0d6efd', 600:'#0d6efd' },
        cobalt: { 300:'#6fb0ee', 400:'#0d6efd', 500:'#0d6efd', 600:'#0d6efd' },
        teal:   { 300:'#7cc0f0', 400:'#3f96de', 500:'#0d6efd', 600:'#1a6f9e' },
      },
      fontFamily: { sans: ['Inter', 'sans-serif'] },

      // index.html da `bg-cobalt-500/8` va `bg-teal-500/7` ishlatilgan.
      // Tailwind'ning standart shaffoflik shkalasida 7 va 8 yo'q — bu
      // sinflar CDN davrida ham generatsiya qilinmagan, ya'ni fon rangi
      // umuman qo'llanmagan. Shkalaga qo'shib, ishlaydigan qilamiz.
      opacity: { 7: '0.07', 8: '0.08' },
    },
  },

  plugins: [],
};
