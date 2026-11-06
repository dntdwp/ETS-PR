# Laporan Akhir

## 1. Hasil evaluasi

Keluaran perintah `python evaluate.py` setelah seluruh file sampel diuji dan `data/ground_truth.csv` dilengkapi:

```text
Dievaluasi: audit.sql, campuran_error.sql, laporan_penjualan.sql, pemeliharaan.sql (27 triple)

Metode   Precision  Recall     F1
parser        1.00    1.00   1.00
regex         0.65    0.81   0.72

[regex]
  salah ditemukan (FP): ('audit.sql', 16, 'sesi', 'R')
  salah ditemukan (FP): ('campuran_error.sql', 4, 'pesanan', 'R')
  salah ditemukan (FP): ('campuran_error.sql', 8, 'keranjang', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pelanggan', 'D')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pelanggan', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pesanan', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'rahasia', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 15, 'pesanan', 'R')
  salah ditemukan (FP): ('pemeliharaan.sql', 2, 'crm.alamat', 'R')
  salah ditemukan (FP): ('pemeliharaan.sql', 2, 'crm.pelanggan', 'R')
  salah ditemukan (FP): ('pemeliharaan.sql', 2, 'pelanggan_lama', 'U')
  salah ditemukan (FP): ('pemeliharaan.sql', 15, 'crm.alamat', 'R')
  terlewat (FN):       ('audit.sql', 2, 'pesanan', 'R')
  terlewat (FN):       ('laporan_penjualan.sql', 3, 'pelanggan', 'R')
  terlewat (FN):       ('laporan_penjualan.sql', 3, 'pesanan', 'R')
  terlewat (FN):       ('pemeliharaan.sql', 3, 'crm.alamat', 'R')
  terlewat (FN):       ('pemeliharaan.sql', 3, 'crm.pelanggan', 'R')
```

## 2. Tiga kasus di mana regex salah

### Kasus 1: Teks SQL di dalam komentar blok (`pemeliharaan.sql` baris 1–2)

**Cuplikan SQL:**
```sql
/* Skrip pemeliharaan data pelanggan.
   Catatan lama: UPDATE pelanggan_lama sudah tidak dipakai. */
```

- **Kesalahan regex:** Regex mendeteksi operasi `U` palsu pada tabel `pelanggan_lama` di baris 2 (False Positive: `('pemeliharaan.sql', 2, 'pelanggan_lama', 'U')`).
- **Mengapa parser benar (Konsep Lexing):** Lexer bekerja membaca aliran karakter (*stream*). Saat mendeteksi pasangan karakter pembuka `/*`, lexer mengabaikan seluruh isi teks di dalamnya hingga menemukan penutup `*/` tanpa menghasilkan token sama sekali. Teks `UPDATE pelanggan_lama` tidak pernah menjadi token, sehingga parser dan analyzer tidak memprosesnya sebagai statement SQL. Regex sebaliknya tidak memiliki konteks apakah sebuah kata kunci berada di dalam blok komentar atau kode aktif.

### Kasus 2: Multi-tabel dipisahkan koma pada klausa FROM (`audit.sql` baris 2–3)

**Cuplikan SQL:**
```sql
SELECT p.id, p.nama
FROM pelanggan p, pesanan o
WHERE o.pelanggan_id = p.id
```

- **Kesalahan regex:** Regex hanya menangkap tabel pertama `pelanggan` dan melewatkan tabel kedua `pesanan` (False Negative: `('audit.sql', 2, 'pesanan', 'R')`).
- **Mengapa parser benar (Konsep Parsing):** Parser memanfaatkan aturan tata bahasa bebas konteks (*Context-Free Grammar*) untuk klausa sumber data: `FROM table_ref { "," table_ref }`. Melalui perulangan token pemisah koma, parser memasukkan setiap tabel ke dalam daftar `sources` pada objek AST `Select`. Analyzer kemudian membaca seluruh elemen daftar tersebut dan mencatat operasi `R` untuk tabel `pelanggan` maupun `pesanan`. Pola regex linier `FROM\s+([a-zA-Z0-9_.]+)` hanya membaca satu kata setelah keyword `FROM` sehingga gagal menangkap pola daftar berulang.

### Kasus 3: Statement DELETE diidentifikasi ganda sebagai Delete dan Read (`audit.sql` baris 16)

**Cuplikan SQL:**
```sql
DELETE FROM sesi s WHERE s.kedaluwarsa < :sekarang;
```

- **Kesalahan regex:** Regex mencatat dua operasi sekaligus untuk tabel `sesi`: operasi `D` dan operasi `R` (False Positive: `('audit.sql', 16, 'sesi', 'R')`).
- **Mengapa parser benar (Konsep Analisis Semantik AST):** Parser mengenali struktur query sebagai `ast.Delete`. Pada tahap analisis semantik (`analyze_statement()`), analyzer memeriksa tipe node AST tersebut. Untuk `ast.Delete`, tabel target hanya dicatat sebagai operasi `D`, sementara operasi `R` hanya dicari dari klausa filter `stmt.where` jika memuat subquery. Karena query di atas tidak memiliki subquery pembacaan, tabel `sesi` hanya dicatat sebagai `D`. Regex menghasilkan FP karena memiliki aturan pencocokan terpisah untuk `DELETE FROM` dan `FROM\s+nama_tabel` tanpa memahami hierarki statement induk.

## 3. Batas pendekatan kami

1. **Common Table Expressions (CTE / klausa `WITH`)**
   - **Contoh kueri:**
     ```sql
     WITH data_aktif AS (
         SELECT id FROM pelanggan WHERE aktif = 1
     )
     SELECT * FROM data_aktif;
     ```
   - **Akibat pada CRUD matrix:** Keyword `WITH` belum didukung oleh grammar parser. Parser akan memicu `ParseError` saat membaca token pertama, mengaktifkan recovery mode hingga titik koma, dan mengabaikan statement. Tabel `pelanggan` tidak akan tercatat sama sekali di matriks.
   - **Informasi yang dibutuhkan:** Penambahan aturan grammar untuk klausa `WITH alias AS (subquery)` pada parser, serta mekanisme penyimpanan deklarasi tabel sementara (*temporary table binding*) pada tumpukan scope resolver.

2. **Resolusi kolom tanpa qualifier pada kueri multi-tabel tanpa katalog skema**
   - **Contoh kueri:**
     ```sql
     SELECT nama, total FROM pelanggan p JOIN pesanan o ON p.id = o.pelanggan_id;
     ```
   - **Akibat pada CRUD matrix:** Operasi tingkat tabel tetap terbaca benar (`pelanggan: R`, `pesanan: R`). Namun saat CLI dipanggil dengan opsi `--kolom`, resolver mengeluarkan warning ambiguitas dan nilai `col.resolved` tetap `None`. Akibatnya, pemetaan detail kolom `nama` dan `total` ke tabel asalnya tidak dapat ditentukan.
   - **Informasi yang dibutuhkan:** Metadata skema database (*database schema / DDL definition*) yang mendefinisikan kolom-kolom bawaan setiap tabel, agar resolver dapat memeriksa kepemilikan kolom saat kueri tidak menyertakan alias.

3. **Kueri DDL (Data Definition Language) dan Stored Procedure**
   - **Contoh kueri:**
     ```sql
     CREATE TABLE arsip_pesanan AS SELECT * FROM pesanan;
     EXEC bersihkan_log_kedaluwarsa;
     ```
   - **Akibat pada CRUD matrix:** Karena grammar dirancang khusus untuk DML (`SELECT`, `INSERT`, `UPDATE`, `DELETE`), statement `CREATE` atau `EXEC` dianggap error sintaks. Akses tabel pada kueri pembuatan tabel atau prosedur tersimpan tidak dapat dianalisis.
   - **Informasi yang dibutuhkan:** Parser terpisah atau modul ekstensi untuk spesifikasi grammar DDL dan bahasa prosedural SQL (PL/SQL atau T-SQL) guna menelusuri isi blok prosedur.

## 4. Pembagian kerja

Pengerjaan tugas proyek dilakukan secara *pair programming* bergantian peran *driver* dan *navigator* setiap 30 menit:

- **Kemal Melvin Ibrahim (Driver):**
  - Mengimplementasikan perbaikan Bug 1 (`crud/lexer.py`: normalisasi keyword case-insensitive).
  - Mengimplementasikan perbaikan Bug 4 (`crud/parser.py`: panic mode error recovery sampai titik koma `;`).
  - Mengimplementasikan perbaikan Bug 5 (`crud/parser.py`: presedensi berjenjang `AND` atas `OR`).
  - Mengimplementasikan TODO(T3) (`crud/lexer.py`: scanning komentar blok `/* ... */`).
  - Mengimplementasikan TODO(T2) (`crud/resolver.py`: resolusi kolom tanpa qualifier dan diagnostik warning).
  - Mengimplementasikan perbaikan Bug 9 (`crud/analyzer.py`: subquery di klausa `UPDATE` hanya membaca operasi `R`).

- **Denta Dwipawasesa (Driver):**
  - Mengimplementasikan perbaikan Bug 2 (`crud/lexer.py`: operator `<>` maximal munch).
  - Mengimplementasikan perbaikan Bug 3 (`crud/lexer.py`: penanganan escaped quote `''` pada string).
  - Mengimplementasikan perbaikan Bug 6 (`crud/parser.py`: dukungan kata kunci `OUTER` opsional pada `LEFT JOIN`).
  - Mengimplementasikan TODO(T1) (`crud/parser.py`: sintaks `INSERT INTO ... SELECT ...`).
  - Mengimplementasikan perbaikan Bug 7 (`crud/resolver.py`: pembalikan arah rantai pencarian scope / *shadowing*).
  - Mengimplementasikan perbaikan Bug 8 (`crud/resolver.py`: penutupan scope pada statement `DELETE` agar tidak bocor).
  - Menyusun 5 test kasus tepi (*edge cases*) dan analisis risiko pada `tests/test_tambahan.py`.
  - Melakukan pelabelan manual ground truth untuk `audit.sql` dan `pemeliharaan.sql` pada `data/ground_truth.csv`.
  - Melengkapi dokumen keputusan arsitektur di `docs/KARTU_DESAIN.md` dan analisis evaluasi di `docs/LAPORAN_AKHIR.md`.

Untuk memastikan pemahaman menyeluruh oleh kedua anggota, setiap bug dan TODO diselesaikan dengan metode TDD murni: skenario kegagalan ditulis terlebih dahulu di `tests/test_tambahan.py`, diverifikasi berdua saat kondisi *RED*, lalu diimplementasikan dan diverifikasi bersama saat kondisi *GREEN*. Pergantian peran driver-navigator di setiap komponen (lexer, parser, resolver, analyzer) membuat kedua anggota memahami alur eksekusi pipeline secara utuh dari kode sumber hingga matriks CRUD.
