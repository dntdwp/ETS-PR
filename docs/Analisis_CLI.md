# Analisis CLI (Jam 1)

Pelengkap `Analisis_test.md` (test dan `--ast`). File ini mencatat gejala dari keluaran CLI:
`crud_matrix.csv`, `--detail`, `--kolom`, dan `evaluate.py`, pada kode **sebelum** ada perbaikan
(commit `65dbadd`).

## 0. Cara menjalankan

Perintah di PDF memakai glob `data/sample/*.sql`. Di **PowerShell** glob tidak diekspansi untuk
program eksternal, sehingga Python menerima teks `data/sample/*.sql` apa adanya:

```text
OSError: [Errno 22] Invalid argument: 'data\\sample\\*.sql'
```

Ini masalah shell, bukan bug tool. Di PowerShell pakai:

```powershell
python -m crud.cli (Get-ChildItem data/sample/*.sql).FullName --out crud_matrix.csv --detail detail.csv --kolom kolom.csv
python -m crud.cli data/sample/audit.sql --ast
python evaluate.py
```

(Di Git Bash perintah asli dari PDF langsung jalan.) File `*.csv` hasil CLI sudah diabaikan
oleh `.gitignore`, kecuali `data/*.csv`.

## 1. Keluaran mentah

### stderr dan exit code

| File | stderr | Exit code |
| --- | --- | --- |
| audit.sql | (kosong) | 0 |
| campuran_error.sql | `PARSE ERROR: Baris 4, kolom 17: diharapkan ekspresi, ditemukan 'FROM'` | 1 |
| laporan_penjualan.sql | `PARSE ERROR: Baris 6, kolom 41: diharapkan ekspresi, ditemukan '>'` | 1 |
| pemeliharaan.sql | `LEX ERROR: Baris 1, kolom 1: komentar blok belum didukung` | 1 |

Tidak ada satu pun diagnostik resolver (warning/error) yang tercetak untuk keempat file.

### crud_matrix.csv

```text
file,pelanggan,pembayaran,pengguna,pesanan,sesi
audit.sql,RU,R,R,RU,D
campuran_error.sql,R,,,,
laporan_penjualan.sql,,,,,
pemeliharaan.sql,,,,,
```

### detail.csv

```text
file,baris,jenis,tabel,operasi
audit.sql,2,SELECT,pelanggan,R
audit.sql,2,SELECT,pesanan,R
audit.sql,8,SELECT,pelanggan,R
audit.sql,8,SELECT,pembayaran,R
audit.sql,12,SELECT,pelanggan,R
audit.sql,12,SELECT,pesanan,R
audit.sql,16,DELETE,sesi,D
audit.sql,18,SELECT,pengguna,R
audit.sql,20,UPDATE,pelanggan,U
audit.sql,20,UPDATE,pesanan,U
campuran_error.sql,2,SELECT,pelanggan,R
```

### kolom.csv

```text
file,baris,tabel,kolom,operasi
audit.sql,2,pelanggan,aktif,R
audit.sql,2,pelanggan,id,R
audit.sql,2,pelanggan,level,R
audit.sql,2,pelanggan,nama,R
audit.sql,2,pesanan,pelanggan_id,R
audit.sql,2,pesanan,tanggal,R
audit.sql,8,pelanggan,id,R
audit.sql,8,pelanggan,nama,R
audit.sql,8,pembayaran,pelanggan_id,R
audit.sql,8,pembayaran,status,R
audit.sql,12,pelanggan,id,R
audit.sql,12,pelanggan,pelanggan_id,R
audit.sql,12,pelanggan,total,R
audit.sql,16,sesi,kedaluwarsa,R
audit.sql,18,pengguna,aktif,R
audit.sql,18,sesi,id,R
```

### evaluate.py

```text
Belum berlabel (tidak dievaluasi): audit.sql, pemeliharaan.sql

Dievaluasi: campuran_error.sql, laporan_penjualan.sql (10 triple)

Metode   Precision  Recall     F1
parser        1.00    0.10   0.18
regex         0.53    0.80   0.64
```

Parser melewatkan 9 dari 10 triple (semua kecuali `campuran_error.sql,2,pelanggan,R`).

## 2. Gejala aneh dari keluaran CLI

### A. crud_matrix.csv dan detail.csv

1. **`laporan_penjualan.sql` dan `pemeliharaan.sql` satu baris kosong semua**
   - **Gejala:** Dua file berisi 4 statement valid, tapi tidak ada satu operasi pun yang tercatat.
   - **Penyebab:** `pemeliharaan.sql` mati di lexer (TODO T3, komentar blok). `laporan_penjualan.sql`
     gagal di statement pertama karena `<>` dipecah lexer, lalu error recovery membuang semua token
     sampai akhir file. Lihat Analisis_test.md C.1 dan B.3.

2. **`campuran_error.sql` cuma punya `pelanggan,R`**
   - **Gejala:** `produk` (UPDATE baris 6) dan `keranjang` (DELETE baris 8) tidak muncul di matrix
     maupun detail, padahal keduanya valid.
   - **Penyebab:** Bug error recovery (`Parser._synchronize` tidak berhenti di `;`). Spesifikasi
     bagian 6: statement valid setelah statement rusak tetap harus diproses.

3. **`audit.sql,20,UPDATE,pelanggan,U`**
   - **Gejala:** `pelanggan` hanya dibaca di subquery `WHERE ... IN (SELECT id FROM pelanggan ...)`,
     tapi dicatat `U`. Akibatnya di matrix level file `pelanggan` jadi `RU`.
   - **Penyebab:** Bug analyzer. Cabang `Update` di `analyze_statement` meneruskan `"U"` ke
     `_collect` untuk nilai `SET` dan `WHERE`. Spesifikasi bagian 5: membaca tabel lewat subquery
     **selalu** R.

### B. kolom.csv (paling jelas memperlihatkan bug resolver)

4. **`audit.sql,12,pelanggan,pelanggan_id,R` dan `audit.sql,12,pelanggan,total,R`**
   - **Gejala:** Kolom `x.pelanggan_id` dan `x.total` ada di subquery `FROM pesanan x`, tapi
     tercatat sebagai kolom `pelanggan`.
   - **Penyebab:** Bug `Resolver._lookup` yang mencari scope dari luar ke dalam, sehingga `x` luar
     (`pelanggan`) menutupi `x` dalam (`pesanan`). Kebalikan dari shadowing di spesifikasi 4.3.

5. **`audit.sql,18,sesi,id,R`**
   - **Gejala:** Statement baris 18 hanya punya `FROM pengguna u`, tapi muncul kolom tabel `sesi`.
     Selain itu stderr **tidak** mencetak error `alias 's' tidak terdefinisi`.
   - **Penyebab:** Bug `Resolver._delete` tidak memanggil `_pop()`, sehingga alias `s` dari DELETE
     baris 16 bocor ke statement berikutnya. Melanggar spesifikasi 4.5. Dicek langsung:
     `analyze_source("DELETE FROM sesi s WHERE s.id = 1; SELECT s.id FROM pengguna u;").diagnostics`
     menghasilkan `[]`.

6. **Tidak ada baris untuk `audit.sql` baris 20 dan `campuran_error.sql` baris 2**
   - **Gejala:** Statement tersebut memakai kolom tanpa qualifier (`status`, `pelanggan_id`, `id`,
     `nama`, `aktif`, ...), tapi tidak ada satu pun yang masuk `kolom.csv`.
   - **Penyebab:** TODO T2 (resolusi kolom tanpa qualifier). `column_usage` hanya mencatat kolom
     yang `resolved`-nya terisi.

### C. Perilaku CLI itu sendiri

7. **`--ast` crash dengan traceback kalau ada LexError, dan file berikutnya tidak diproses**
   - **Gejala:** `python -m crud.cli data/sample/pemeliharaan.sql data/sample/campuran_error.sql --ast`
     berhenti dengan traceback `crud.lexer.LexError`; `campuran_error.sql` tidak dicetak sama sekali.
   - **Penyebab:** `_print_ast` di `crud/cli.py` memanggil `parse_sql` tanpa menangkap `LexError`,
     berbeda dengan `analyze_source` di `pipeline.py` yang menangkapnya. Spesifikasi 2.7:
     LexError menghentikan pemrosesan **file tersebut**, bukan seluruh program.
   - **Catatan:** Ini mode debug, bukan bagian API publik yang diuji (spesifikasi 7). Akan hilang
     sendiri untuk `pemeliharaan.sql` setelah T3 selesai, tapi tetap muncul untuk file lain yang
     mengandung LexError.

8. **Diagnostik `error` dari resolver tidak memengaruhi exit code**
   - **Gejala:** Di `main()`, `had_error` hanya diset untuk LexError dan ParseError. Diagnostik
     resolver level `error` (mis. alias tidak terdefinisi) hanya dicetak, exit code tetap 0.
   - **Status:** Observasi. Spesifikasi tidak mengatur exit code, jadi belum tentu bug. Perlu
     didiskusikan.

### D. Temuan tambahan yang belum tercatat di Analisis_test.md

9. **`LEFT OUTER JOIN` ditolak parser**
   - **Gejala:** `SELECT a.id FROM a LEFT OUTER JOIN b ON b.a_id = a.id;` menghasilkan
     `ParseError: Baris 1, kolom 25: diharapkan JOIN, ditemukan 'OUTER'`.
   - **Penyebab:** `Parser._join` tidak mengonsumsi `OUTER` opsional setelah `LEFT`, padahal grammar
     spesifikasi bagian 3: `join = [ "INNER" | "LEFT" [ "OUTER" ] ] "JOIN" ...`.
   - **Kenapa belum kelihatan di CLI:** `pemeliharaan.sql` baris 5 memakai `left outer join`, tapi
     file itu sudah mati duluan di lexer (T3, keyword huruf kecil). Bug ini baru akan muncul setelah
     bug lexer diperbaiki.

## 3. Ringkasan untuk jam berikutnya

| No | Gejala CLI | Modul | Jenis |
| --- | --- | --- | --- |
| 1 | laporan_penjualan & pemeliharaan kosong | Lexer + Parser | T3, bug `<>`, bug recovery |
| 2 | produk & keranjang hilang | Parser | bug recovery |
| 3 | pelanggan dapat `U` di UPDATE | Analyzer | bug |
| 4 | kolom subquery salah tabel | Resolver | bug `_lookup` |
| 5 | `sesi,id` di statement baris 18 | Resolver | bug `_delete` |
| 6 | kolom tanpa qualifier tidak tercatat | Resolver | T2 |
| 7 | `--ast` crash saat LexError | CLI | observasi / kandidat bug |
| 8 | error resolver tidak ubah exit code | CLI | observasi |
| 9 | `LEFT OUTER JOIN` ditolak | Parser | bug (belum terlihat di CLI) |
