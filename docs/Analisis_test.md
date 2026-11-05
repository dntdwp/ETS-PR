## Ada 30 test: berhasil 25 gagal 5 (CLI)
## Gagal:
    1. FAILED tests/test_analyzer.py::test_matrix_laporan_penjualan - assert (None is None and [ParseError("...temukan '>'")] == []
    2. FAILED tests/test_lexer.py::test_keyword_huruf_kecil - AssertionError: assert (<TokenType.IDENT: 2> == <TokenType.KEYWORD: 1>)
    3. FAILED tests/test_lexer.py::test_komentar_blok - crud.lexer.LexError: Baris 1, kolom 1: komentar blok belum didukung
    4. FAILED tests/test_parser.py::test_insert_select - AssertionError: [ParseError("Baris 1, kolom 24: INSERT ... SELECT belum didukung, d...
    5. FAILED tests/test_resolver.py::test_kolom_tanpa_qualifier_satu_tabel - AssertionError: assert {None} == {'pelanggan'}

### LIST IDENTIFIKASI BUG DAN TODO (AST)

### A. audit.sql

1. **Baris 2–6 (Query SELECT pelanggan & pesanan)**
   - **Status:** BUG (Parser)
   - **Potongan Kode:** `... AND ... OR ... AND ...`
   - **Penjelasan Masalah:** Parser menganggap derajat kekuatan operator `AND` dan `OR` itu sama rata (dijalankan berurutan dari kiri ke kanan). Padahal menurut aturan, `AND` harus diprioritaskan lebih dulu daripada `OR` (mirip seperti perkalian lebih kuat dari penjumlahan).
   - **Akibat:** Pohon logika AST salah mengelompokkan syarat `WHERE`.

2. **Baris 12–14 (Query SELECT dengan Subquery IN)**
   - **Status:** BUG (Resolver)
   - **Potongan Kode:** `SELECT x.id FROM pelanggan x WHERE ... (SELECT x.pelanggan_id FROM pesanan x ...)`
   - **Penjelasan Masalah:** Di luar ada tabel `pelanggan` dengan alias `x`, dan di dalam kurung (subquery) ada tabel `pesanan` yang juga memakai alias `x`. Sistem mencarinya terbalik (dari luar ke dalam), sehingga alias `x` di luar malah menimpa alias `x` di dalam.
   - **Akibat:** Kolom `total` dan `pelanggan_id` salah ditebak sebagai milik `pelanggan`, padahal aslinya milik `pesanan`.

3. **Baris 16 (Query DELETE sesi)**
   - **Status:** BUG (Resolver)
   - **Potongan Kode:** `DELETE FROM sesi s WHERE s.kedaluwarsa < :sekarang;`
   - **Penjelasan Masalah:** Setelah baris ini selesai diproses, sistem lupa membuang alias `s` dari daftar ingatannya (fungsi `self._pop()` kelupaan dipanggil).
   - **Akibat:** Alias `s` (tabel `sesi`) masih nyangkut di memori dan bocor ke baris berikutnya.

4. **Baris 18 (Query SELECT pengguna)**
   - **Status:** BUG (Resolver)
   - **Potongan Kode:** `SELECT s.id FROM pengguna u WHERE u.aktif = 1;`
   - **Penjelasan Masalah:** Di query ini tabelnya cuma `pengguna u`, tidak ada alias `s`. Harusnya sistem mengeluarkan pesan error: *"alias 's' tidak terdefinisi"*. Tapi karena efek bocor dari baris 16 tadi, sistem mengira `s` itu adalah `sesi`.
   - **Akibat:** Perintah SQL yang sebenarnya salah ketik alias malah lolos dianggap valid.

5. **Baris 20–21 (Query UPDATE pesanan)**
   - **Status:** TODO & BUG
     - **TODO (T2 - Resolver):** Kolom seperti `status` dan `pelanggan_id` tidak ada awalan tabelnya (cuma nama kolom saja). Sistem belum punya kodingan untuk menebak tabel asalnya, sehingga hasilnya masih kosong (`None`).
     - **BUG (Analyzer - Salah Label CRUD):** Di dalam klausa `WHERE`, ada subquery membaca data dari tabel `pelanggan`. Sistem malah memberi label tabel `pelanggan` sebagai **U (Update)**, padahal subquery di dalam WHERE fungsinya murni hanya dibaca alias **R (Read)**.
   - **Akibat:** Laporan CRUD matrix salah mencatat tabel `pelanggan` ikut diubah/di-update.

### B. campuran_error.sql

1. **Baris 2 (Query SELECT pelanggan)**
   - **Status:** TODO (T2 - Resolver)
   - **Potongan Kode:** `SELECT id, nama FROM pelanggan WHERE aktif = 1;`
   - **Penjelasan Masalah:** Query ini valid dan pohon AST berhasil dibuat. Namun kolom `id`, `nama`, dan `aktif` tidak memiliki tanda panah `-> pelanggan` karena fitur resolusi kolom tanpa awalan tabel (`TODO(T2)`) belum diisi.
   - **Akibat:** Kolom belum terhubung ke tabel asalnya di hasil AST.

2. **Baris 4 (Query SELECT pesanan yang rusak)**
   - **Status:** Perilaku Normal (Syntax Error Terdeteksi)
   - **Potongan Kode:** `SELECT id nama, FROM pesanan;`
   - **Penjelasan Masalah:** Kode SQL ini memang sengaja salah ketik (ada tanda koma `,` yang langsung diikuti kata `FROM` tanpa ada nama kolom lagi). Parser sudah tepat mengeluarkan pesan error: `PARSE ERROR: Baris 4, kolom 17: diharapkan ekspresi, ditemukan 'FROM'`.
   - **Akibat:** Baris 4 digagalkan karena memang melanggar tata bahasa SQL.

3. **Baris 6 & 8 (Query UPDATE produk & DELETE keranjang yang HILANG)**
   - **Status:** BUG BESAR (Parser - Gagal Error Recovery / Panic Mode)
   - **Potongan Kode:** 
     - Baris 6: `UPDATE produk SET stok = ...;`
     - Baris 8: `DELETE FROM keranjang WHERE ...;`
   - **Penjelasan Masalah:** Kedua perintah ini sebenarnya 100% benar dan valid. Tapi karena baris 4 tadi error, parser langsung panik dan menyerah total, tidak mau membaca sisa baris di bawahnya. Parser tidak membuang token sampai tanda titik koma (`;`) untuk pulih kembali.
   - **Akibat:** Baris 6 dan 8 tidak pernah diproses sama sekali. Hal ini menyebabkan operasi UPDATE dan DELETE di file ini hilang dari laporan evaluasi (tercatat sebagai data yang terlewat).


### C. laporan_penjualan.sql

1. **Baris 6 (Operator `<>`)**
   - **Status:** BUG (Lexer)
   - **Potongan Kode:** `WHERE ... AND o.catatan <> 'FROM rahasia'`
   - **Masalah:** Lexer memotong simbol `<>` menjadi dua token terpisah (`<` lalu `>`). Saat parser membaca tanda `<`, ia mengharapkan ekspresi nilai, tetapi malah menemukan tanda `>`.
   - **Pesan Error:** `PARSE ERROR: Baris 6, kolom 41: diharapkan ekspresi, ditemukan '>'`.
   - **Akibat:** File langsung gagal diparse di baris ini dan seluruh baris di bawahnya ikut macet.

2. **Baris 9–10 (Query `INSERT ... SELECT`)**
   - **Status:** TODO (T1 - Parser)
   - **Potongan Kode:** `INSERT INTO arsip_pesanan (id, total) SELECT id, total FROM pesanan WHERE ...`
   - **Masalah:** Parser belum mendukung sintaks memasukkan data dari hasil query `SELECT` (saat ini baru bisa `INSERT ... VALUES`).
   - **Akibat:** Melempar error `INSERT ... SELECT belum didukung`.

3. **Baris 12–13 (Query UPDATE dengan Subquery di WHERE)**
   - **Status:** BUG (Analyzer) & TODO (T2 - Resolver)
   - **Potongan Kode:** `UPDATE pelanggan ... WHERE id IN (SELECT pelanggan_id FROM pesanan ...)`
   - **Masalah:**
     - **TODO (T2):** Kolom `id` tidak punya awalan tabel, resolver belum bisa mengisi tabel asalnya.
     - **BUG (Analyzer):** Subquery `SELECT` di dalam klausa `WHERE` pada perintah `UPDATE` salah dilabeli sebagai **U (Update)**, padahal harusnya cuma dibaca alias **R (Read)**.
   - **Akibat:** Tabel `pesanan` salah dicatat ikut terkena operasi update.

### D. pemeliharaan.sql

1. **Baris 1–2 (Komentar Blok `/* ... */`)**
   - **Status:** TODO (T3 - Lexer)
   - **Potongan Kode:** `/* Skrip pemeliharaan data pelanggan... */`
   - **Masalah:** Lexer belum mendukung komentar blok multi-baris (`/* ... */`). Begitu melihat karakter `/*`, kode bawaan sengaja melempar error `LexError: komentar blok belum didukung`.
   - **Akibat:** File langsung berhenti total di baris 1 kolom 1.

2. **Baris 3–6 (Keyword Huruf Kecil)**
   - **Status:** BUG (Lexer)
   - **Potongan Kode:** `select c.id, c.nama, a.kota from ... where ...`
   - **Masalah:** Perintah SQL ditulis dengan huruf kecil (`select`, `from`, `where`). Lexer tidak mengubahnya ke huruf besar sebelum mengecek daftar kata kunci, sehingga kata-kata penting ini salah dibaca sebagai nama kolom/identifier (`IDENT`).
   - **Akibat:** Parser gagal memahami bahwa ini adalah perintah `SELECT`.

3. **Baris 6 & 9 (Tanda Petik di Dalam Teks `'O''Brien'`)**
   - **Status:** BUG (Lexer - String Escaping)
   - **Potongan Kode:** `c.nama = 'O''Brien'` dan `'O''Neil'`
   - **Masalah:** Di SQL, dua kutip satu berturut-turut (`''`) di dalam teks artinya satu karakter kutip asli (`O'Brien`). Tapi lexer mengira tanda kutip kedua adalah penutup string.
   - **Akibat:** Pembacaan string terputus di tengah jalan dan teks setelahnya menjadi rusak.

4. **Baris 6 (Presedensi Logika `OR` vs `AND`)**
   - **Status:** BUG (Parser)
   - **Potongan Kode:** `where c.nama = '...' or c.kota = '...' and c.aktif = 1;`
   - **Masalah:** Parser salah mengelompokkan urutan logika karena menganggap `OR` dan `AND` setara.
   - **Akibat:** Kondisi pencarian `WHERE` salah dipahami oleh sistem AST.

5. **Baris 12–13 (Query `INSERT ... SELECT`)**
   - **Status:** TODO (T1 - Parser)
   - **Potongan Kode:** `insert into ... select id, 'nama diperbarui' from ...`
   - **Masalah:** Fitur memasukkan data dari hasil `SELECT` belum diimplementasikan.
   - **Akibat:** Melempar error sintaks `INSERT ... SELECT belum didukung`.

6. **Baris 10 & 16 (Kolom Tanpa Awalan Tabel)**
   - **Status:** TODO (T2 - Resolver)
   - **Potongan Kode:** `where id = :id;` dan `where pelanggan_id not in ...`
   - **Masalah:** Kolom `id` dan `pelanggan_id` berdiri sendiri tanpa nama tabel di depannya, belum bisa di-resolve ke tabel asalnya.
   - **Akibat:** Nilai `resolved` pada kolom masih kosong (`None`).