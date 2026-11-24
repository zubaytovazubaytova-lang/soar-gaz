# SOAR GAZ — zaxira nusxasi va tiklash

GitHub'da faqat **kod** saqlanadi. Baza (xodimlar va ularning kirish kodlari, mijozlar, arizalar,
to'lovlar), yuklangan hujjatlar (`backend/media`) va server sozlamasi (`/etc/soargaz/env`) faqat
serverda. Ularni shu tizim saqlaydi.

## Qanday ishlaydi

| Nima | Qayerda |
|---|---|
| Har kuni 03:30 da nusxa | `soargaz-zaxira.timer` → `soargaz-zaxira.service` → `/usr/local/sbin/soargaz-zaxira` |
| Serverdagi nusxalar (oxirgi 14 kun) | `/var/backups/soargaz/soargaz-YYYYMMDD-HHMM.tar` (faqat root) |
| Serverdan tashqari nusxa | Administratorning Telegram'i (@soargaz_bot), **AES-256 bilan shifrlangan** `.tar.gpg` |
| Xato bo'lsa | Administratorga Telegram'da ogohlantirish |

Paket ichida: `db-*.dump` (PostgreSQL, `pg_dump -Fc`), `media-*.tar.gz`, `env-*` (maxfiy kalitlar).
Nusxa olish saytni to'xtatmaydi. Shifr paroli o'rnatilmagan bo'lsa, nusxa Telegram'ga **yuborilmaydi**.

## O'rnatish (yangi serverda)

```bash
install -m 750 soargaz-zaxira /usr/local/sbin/soargaz-zaxira
install -m 750 soargaz-zaxira-parol /usr/local/bin/soargaz-zaxira-parol
install -m 644 soargaz-zaxira.service soargaz-zaxira.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now soargaz-zaxira.timer
soargaz-zaxira-parol                 # shifr parolini o'rnatish (yashirin kiritiladi)
systemctl start soargaz-zaxira       # darhol nusxa olish; jurnal: journalctl -u soargaz-zaxira
```

## Tiklash

1. Nusxani oling: serverdagi `/var/backups/soargaz/...tar` yoki Telegram'dagi `...tar.gpg` faylni yangi serverga yuklang.
2. Telegram'dan olingan bo'lsa, shifrni oching (zaxira paroli so'raladi):
   ```bash
   gpg -o soargaz.tar -d soargaz-YYYYMMDD-HHMM.tar.gpg
   ```
3. Paketni oching: `tar -xf soargaz.tar` → `db-*.dump`, `media-*.tar.gz`, `env-*`.
4. Sozlama: `env-*` faylini `/etc/soargaz/env` ga qo'ying (`chown root:soargaz`, `chmod 640`).
5. Baza (bo'sh `soargaz` bazasiga):
   ```bash
   runuser -u postgres -- pg_restore -d soargaz --no-owner --exit-on-error db-*.dump
   ```
6. Fayllar: `tar -xzf media-*.tar.gz -C /srv/soargaz/backend` (`chown -R soargaz:soargaz /srv/soargaz/backend/media`).
7. `systemctl restart soargaz`.

**Zaxira paroli yo'qolsa, Telegram'dagi nusxalarni ochib bo'lmaydi.** Uni serverdan tashqarida
(daftar, parol menejeri) saqlang.

Tiklash sinovi (2026-11-19): nusxa vaqtinchalik bazaga tiklanib, barcha jadval va xodim kodlari
asl baza bilan bir xil chiqdi.
