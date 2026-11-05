# Laporan Bug

Salinan entri laporan setiap bug yang ditemukan dalam codebase. Bagian akar masalah dianalisis menggunakan konsep dari buku *Crafting Interpreters*. Bagian perbaikan dan test regresi diisi secara bertahap saat sesi pair programming berlangsung.

---

## Bug 1: Keyword Huruf Kecil Dianggap Identifier

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Kemal Melvin Ibrahim


**Gejala.** Query SQL yang ditulis menggunakan huruf kecil seperti `select id from pelanggan;` gagal diproses sebagai statement SELECT. Token pertama yang dihasilkan bertipe `IDENT` bernilai `'select'`, bukan `KEYWORD` `'SELECT'`. Menurut SPESIFIKASI.md bagian 2.2, keyword bersifat case-insensitive dan nilainya dinormalisasi ke huruf besar.

**Reproduksi minimal.**

```sql
select id from t;
```

**Akar masalah.** Pada `crud/lexer.py` fungsi `_word()`, string diambil langsung dari kode sumber dan dicocokkan ke himpunan `KEYWORDS` tanpa diubah ke huruf besar (`if text in KEYWORDS:`). Karena seluruh elemen di set `KEYWORDS` berhuruf kapital, kata kunci huruf kecil masuk ke blok `else` sebagai `IDENT`. Hal ini melanggar konsep scanning reserved words (*Crafting Interpreters* Bab 4: Scanning), di mana penentuan token keyword harus mengabaikan perbedaan kapitalisasi.

**Perbaikan.** Pada `crud/lexer.py` fungsi `_word()`, tambahkan normalisasi `text_upper = text.upper()`. Jika `text_upper in KEYWORDS`, simpan token `KEYWORD` dengan nilai `text_upper`. Jika bukan, tetap simpan sebagai `IDENT` dengan nilai asli `text`. Alternatif mendaftarkan variasi huruf kecil ke himpunan `KEYWORDS` ditolak karena memboroskan memori dan nilai token tidak otomatis ternormalisasi kapital.

**Test regresi.** `test_bug1_keyword_case_insensitive` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver membantu menunjukkan letak fungsi `_word()` di Bab 4 dan menyarankan struktur test regresi. Diverifikasi langsung oleh Kemal dengan menjalankan `pytest tests/test_lexer.py::test_keyword_huruf_kecil -v` dan `pytest tests/test_tambahan.py -v`.

---

## Bug 2: Operator Perbandingan `<>` Dipecah Menjadi Dua Token

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Pernyataan SQL dengan operator `<>` menghasilkan error `ParseError: Baris 6, kolom 41: diharapkan ekspresi, ditemukan '>'` pada `laporan_penjualan.sql`. Lexer menghasilkan dua token terpisah: `OP` bernilai `'<'` lalu `OP` bernilai `'>'`. Menurut SPESIFIKASI.md bagian 2.5, `<>` adalah satu token `OP`.

**Reproduksi minimal.**

```sql
SELECT id FROM t WHERE a <> 1;
```

**Akar masalah.** Pada `crud/lexer.py` fungsi `_scan_token()`, penanganan karakter `<` hanya memeriksa kemungkinan karakter `=` (`<=`). Karakter `>` tidak dicek, sehingga `>` dibaca pada perulangan pemindaian berikutnya sebagai token tersendiri. Kode melanggar prinsip *maximal munch* (*Crafting Interpreters* Bab 4: Scanning), di mana lexer wajib mengambil deretan karakter terpanjang yang valid untuk membentuk satu token.

**Perbaikan.** Pada `crud/lexer.py` fungsi `_scan_token()`, pada blok penanganan karakter `<`, tambahkan cabang `elif self._match(">"): op = "<>"` sebelum cabang `else`. Alternatif menggabungkan dua token operator terpisah di tingkat parser ditolak karena melanggar batas tanggung jawab pipeline (parser tidak bertugas merapikan kesalahan tokenisasi lexer).

**Test regresi.** `test_bug2_operator_not_equals` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver membantu menjelaskan konsep maximal munch (Bab 4) dan struktur test regresi. Diverifikasi langsung oleh Denta dengan menjalankan `pytest tests/test_tambahan.py -v -k "bug2"`.

---

## Bug 3: Karakter Kutip Tunggal `''` di Dalam String Menutup String Lebih Awal

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** String SQL yang memuat karakter escape dua tanda kutip seperti `'O''Brien'` terpotong menjadi token `'O'`. Tanda kutip kedua dianggap sebagai penutup string, sehingga teks sisanya memicu error sintaks atau karakter tidak dikenal. Menurut SPESIFIKASI.md bagian 2.4, dua kutip tunggal berurutan di dalam string melambangkan satu karakter kutip asli.

**Reproduksi minimal.**

```sql
SELECT 'O''Brien' FROM t;
```

**Akar masalah.** Pada `crud/lexer.py` fungsi `_string()`, loop pemindaian karakter langsung berhenti (`break`) setiap kali menemukan karakter `'` tanpa memeriksa karakter berikutnya. Mengacu pada konsep string escape sequence (*Crafting Interpreters* Bab 4: Scanning), scanner harus menggunakan teknik lookahead (`_peek()`). Jika karakter kutip diikuti oleh kutip lagi, scanner harus mengonsumsi keduanya dan menyimpan satu karakter `'` ke buffer.

**Perbaikan.** Pada `crud/lexer.py` fungsi `_string()`, saat mendeteksi karakter `'`, tambahkan pemeriksaan lookahead `if self._peek() == "'":`. Jika ada kutip berikutnya, konsumsi dengan `self._advance()` dan masukkan satu karakter `'` ke buffer `chars`. Jika bukan, hentikan loop pembacaan string (`break`). Alternatif memakai regex replace string setelah token selesai ditolak karena loop `_string` sudah terlanjur putus di tengah jalan.

**Test regresi.** `test_bug3_string_escaped_quote` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver menyarankan alur TDD (membuat test regresi gagal terlebih dahulu sebelum perbaikan) dan logika lookahead (*Crafting Interpreters* Bab 4). Diverifikasi langsung oleh Denta dengan menjalankan `pytest tests/test_tambahan.py -v -k "bug3"`.

---

## Bug 4: Panic Mode Error Recovery Membuang Seluruh Token Sampai Akhir File

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Kemal Melvin Ibrahim

**Gejala.** Pada file `campuran_error.sql`, baris 4 mengalami syntax error (`SELECT id nama, FROM pesanan;`). Akibatnya, statement valid di baris 6 (UPDATE) dan baris 8 (DELETE) hilang total dari AST dan `crud_matrix.csv`. Menurut SPESIFIKASI.md bagian 6, setelah syntax error ditemukan, parser harus membuang token sampai dan termasuk tanda `;` berikutnya, lalu melanjutkan pemrosesan statement valid sesudahnya.

**Reproduksi minimal.**

```sql
SELECT id nama, FROM t;
SELECT id FROM t;
```

**Akar masalah.** Fungsi `_synchronize()` pada `crud/parser.py` hanya berisi loop `while not self._at_end(): self._advance()`. Fungsi ini menghabiskan seluruh token yang tersisa hingga `EOF`. Hal ini melanggar konsep *Panic Mode Error Recovery* (*Crafting Interpreters* Bab 6: Parsing Expressions), di mana parser seharusnya hanya membuang token sampai batas sinkronisasi tertentu (pada SQL adalah batas akhir statement berupa `;`).

**Perbaikan.** Pada `crud/parser.py` fungsi `_synchronize()`, ubah perulangan agar membaca dan membuang token sampai menemukan token berjenis `SEMICOLON` (`if self._advance().type == T.SEMICOLON: return`), lalu keluar dari mode panik untuk memproses statement berikutnya. Alternatif sinkronisasi berbasis keyword awal statement (`SELECT`, `INSERT`) ditolak karena spesifikasi bagian 6 secara tegas mensyaratkan token dibuang sampai dan termasuk titik koma.

**Test regresi.** `test_bug4_panic_mode_recovery_semicolon` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver memandu penerapan konsep panic mode recovery batas titik koma (*Crafting Interpreters* Bab 6). Diverifikasi langsung oleh Kemal dengan menjalankan `pytest tests/test_tambahan.py -v -k "bug4"`.

---

## Bug 5: Presedensi Operator Logika `AND` dan `OR` Disamakan

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Kemal Melvin Ibrahim

**Gejala.** Pada ekspresi kondisi `WHERE a = 1 OR b = 2 AND c = 3`, parser menghasilkan pohon AST `BinaryOp` yang mengelompokkan operasi dari kiri ke kanan: `((a = 1) OR (b = 2)) AND (c = 3)`. Menurut SPESIFIKASI.md bagian 3.1, `AND` berada di tingkat presedensi 2 (lebih tinggi) dibanding `OR` di tingkat presedensi 1, sehingga pohon AST wajib berbentuk `(a = 1) OR ((b = 2) AND (c = 3))`.

**Reproduksi minimal.**

```sql
SELECT id FROM t WHERE a = 1 OR b = 2 AND c = 3;
```

**Akar masalah.** Pada `crud/parser.py` fungsi `_logical()`, kedua operator diproses dalam satu loop bersama: `while self._check_kw("AND", "OR"):`. Ini membuat kedua operator memiliki kedudukan yang setara dalam grammar. Mengacu pada aturan grammar ekspresi berlapis (*Crafting Interpreters* Bab 6: Parsing Expressions), setiap tingkatan presedensi harus dipisahkan ke dalam fungsi grammar yang berbeda agar operator berprioritas lebih tinggi dievaluasi lebih dalam pada hierarki pemanggilan fungsi.

**Perbaikan.** Pada `crud/parser.py`, ganti fungsi `_logical()` menjadi dua fungsi terpisah: `_or_expr()` yang memproses operator `OR` (memanggil `_and_expr()`) dan `_and_expr()` yang memproses operator `AND` (memanggil `_not()`). Fungsi `_expr()` diarahkan untuk memanggil `_or_expr()`. Alternatif menggunakan algoritma shunting-yard ditolak karena codebase memakai arsitektur recursive descent murni.

**Test regresi.** `test_bug5_precedence_and_or` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver memandu pembagian tingkat presedensi berjenjang (*stratified grammar* Bab 6) dan pemecahan fungsi `_logical` menjadi `_or_expr` dan `_and_expr`. Diverifikasi langsung oleh Kemal dengan menjalankan `pytest tests/test_tambahan.py -v -k "bug5"`.

---

## Bug 6: Keyword `OUTER` pada Klausa `LEFT OUTER JOIN` Ditolak Parser

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Query pada `pemeliharaan.sql` baris 5 yang menggunakan sintaks `left outer join` memicu error `ParseError: Baris 1, kolom 25: diharapkan JOIN, ditemukan 'OUTER'`. Menurut SPESIFIKASI.md bagian 3, aturan tata bahasa join mendukung klausa `[ "INNER" | "LEFT" [ "OUTER" ] ] "JOIN"`.

**Reproduksi minimal.**

```sql
SELECT a.id FROM a LEFT OUTER JOIN b ON b.a_id = a.id;
```

**Akar masalah.** Pada `crud/parser.py` fungsi `_join()`, saat parser menemukan token `LEFT`, parser langsung memanggil `self._expect_kw("JOIN")` tanpa memeriksa kemungkinan keberadaan keyword opsional `OUTER`. Konsep yang dilanggar adalah kepatuhan terhadap aturan tata bahasa formal (*Crafting Interpreters* Bab 6: Parsing Expressions), di mana seluruh komponen opsional grammar harus dicocokkan sebelum melanjutkan ke token wajib berikutnya.

**Perbaikan.** Pada `crud/parser.py` fungsi `_join()`, tambahkan pemanggilan `self._match_kw("OUTER")` setelah mendeteksi token `LEFT` dan sebelum memanggil `self._expect_kw("JOIN")`. Alternatif mengubah lexer agar menggabungkan kata `LEFT` dan `OUTER` menjadi satu token ditolak karena menyalahi daftar token baku.

**Test regresi.** `test_bug6_left_outer_join` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver memverifikasi aturan grammar join di SPESIFIKASI.md bagian 3. Diverifikasi langsung oleh Denta dengan menjalankan `pytest tests/test_tambahan.py -v -k "bug6"`.

---

## Bug 7: Pencarian Scope Resolver Terbalik dari Luar ke Dalam

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** (belum diperbaiki)

**Gejala.** Pada query subquery di mana alias lokal sama dengan alias luar (misalnya `SELECT x.id FROM pelanggan x WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x ...)` di `audit.sql`), kolom `x.pelanggan_id` dan `x.total` di dalam subquery salah dihubungkan ke tabel luar `pelanggan`. Berdasarkan SPESIFIKASI.md bagian 4.3, qualifier harus dicari dari scope terdalam ke luar agar terjadi mekanisme shadowing.

**Reproduksi minimal.**

```sql
SELECT x.id FROM t1 x WHERE x.id IN (SELECT x.id FROM t2 x);
```

**Akar masalah.** Pada `crud/resolver.py` fungsi `_lookup(name)`, rantai scope dikumpulkan lalu dibalik urutannya dengan `for scope in reversed(chain):`. Karena rantai sudah dibentuk dari scope aktif menuju scope induk (`parent`), pembalikan ini justru membuat penelusuran bermula dari scope terluar (global/induk). Hal ini melanggar konsep lexical scope resolution (*Crafting Interpreters* Bab 11: Resolving and Binding), di mana deklarasi lokal terdekat wajib menyembunyikan (*shadow*) deklarasi dengan nama serupa di lingkungan luar.

**Perbaikan.** *(belum dilakukan)*

**Test regresi.** *(belum dibuat di tests/test_tambahan.py)*

**Peran AI.** *(akan dicatat saat perbaikan dilakukan)*

---

## Bug 8: Lingkungan Scope Statement `DELETE` Bocor ke Statement Selanjutnya

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** (belum diperbaiki)

**Gejala.** Pada `audit.sql` baris 16 terdapat query `DELETE FROM sesi s ...`, disusul baris 18 `SELECT s.id FROM pengguna u ...`. Query baris 18 tidak mendefinisikan alias `s`, namun resolver tidak mengeluarkan error `alias 's' tidak terdefinisi`. Kolom `s.id` malah dianggap merujuk ke tabel `sesi`. Menurut SPESIFIKASI.md bagian 4.5, setiap statement berdiri sendiri dan scope statement sebelumnya tidak boleh tersisa.

**Reproduksi minimal.**

```sql
DELETE FROM t1 s;
SELECT s.id FROM t2;
```

**Akar masalah.** Pada `crud/resolver.py` fungsi `_delete()`, scope dibuka dengan `self._push()`, namun di akhir fungsi tidak terdapat pemanggilan `self._pop()`. Hal ini melanggar siklus hidup scope blok (*Crafting Interpreters* Bab 11: Resolving and Binding). Lingkungan deklarasi lokal yang tidak ditutup menyebabkan entri simbol tabel tetap tertinggal di tumpukan scope saat memproses statement berikutnya.

**Perbaikan.** *(belum dilakukan)*

**Test regresi.** *(belum dibuat di tests/test_tambahan.py)*

**Peran AI.** *(akan dicatat saat perbaikan dilakukan)*

---

## Bug 9: Subquery pada Pernyataan `UPDATE` Dilabeli Sebagai Operasi `U`

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** (belum diperbaiki)

**Gejala.** Pada `audit.sql` baris 20 (`UPDATE pesanan SET ... WHERE pelanggan_id IN (SELECT id FROM pelanggan ...)`), tabel `pelanggan` tercatat memiliki operasi `U` pada `detail.csv`, sehingga matrix file menjadi `RU`. Menurut SPESIFIKASI.md bagian 5, membaca tabel lewat subquery selalu bernilai `R` tanpa memandang jenis statement luarnya.

**Reproduksi minimal.**

```sql
UPDATE t1 SET a = 1 WHERE b IN (SELECT c FROM t2);
```

**Akar masalah.** Pada `crud/analyzer.py` fungsi `analyze_statement()`, blok penanganan `ast.Update` memanggil fungsi pengumpul operasi dengan parameter `op="U"` untuk ekspresi assignment dan WHERE: `_collect(stmt.where, usage, "U")`. Akibatnya, tabel yang hanya dibaca di dalam subquery klausa WHERE ikut terkena cap operasi Update. Ini melanggar aturan semantik CRUD pada spesifikasi proyek.

**Perbaikan.** *(belum dilakukan)*

**Test regresi.** *(belum dibuat di tests/test_tambahan.py)*

**Peran AI.** *(akan dicatat saat perbaikan dilakukan)*
