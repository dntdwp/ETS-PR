# Laporan Bug

Salinan entri laporan setiap bug yang ditemukan dalam codebase. Bagian akar masalah dianalisis menggunakan konsep dari buku *Crafting Interpreters*.

---

## Bug 1: Keyword Huruf Kecil Dianggap Identifier

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Query SQL yang ditulis menggunakan huruf kecil seperti `select id from pelanggan;` gagal diproses sebagai statement SELECT. Token pertama yang dihasilkan bertipe `IDENT` bernilai `'select'`, bukan `KEYWORD` `'SELECT'`. Menurut SPESIFIKASI.md bagian 2.2, keyword bersifat case-insensitive dan nilainya dinormalisasi ke huruf besar.

**Reproduksi minimal.**

```sql
select 1;
```

**Akar masalah.** Pada `crud/lexer.py` fungsi `_word()`, string diambil langsung dari kode sumber dan dicocokkan ke himpunan `KEYWORDS` tanpa diubah ke huruf besar (`if text in KEYWORDS:`). Karena seluruh elemen di set `KEYWORDS` berhuruf kapital, kata kunci huruf kecil masuk ke blok `else` sebagai `IDENT`. Hal ini melanggar konsep scanning reserved words (*Crafting Interpreters* Bab 4: Scanning), di mana penentuan token keyword harus mengabaikan perbedaan kapitalisasi.

**Perbaikan.** Normalisasi string ke huruf besar (`text.upper()`) sebelum pengecekan ke `KEYWORDS` pada `crud/lexer.py` fungsi `_word()`. Jika cocok, simpan token dengan nilai hasil kapitalisasi tersebut. Alternatif mendaftarkan variasi huruf kecil ke dalam himpunan `KEYWORDS` ditolak karena memboroskan memori dan tidak menghasilkan token bernilai huruf kapital sesuai spesifikasi.

**Test regresi.** `test_bug_keyword_case_insensitive` di `tests/test_tambahan.py`.

**Peran AI.** Menunjukkan posisi percabangan `_word` saat membedakan identifier dan keyword. Diverifikasi lewat eksekusi `pytest tests/test_lexer.py::test_keyword_huruf_kecil`.

---

## Bug 2: Operator Perbandingan `<>` Dipecah Menjadi Dua Token

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Pernyataan SQL dengan operator `<>` menghasilkan error `ParseError: Baris 6, kolom 41: diharapkan ekspresi, ditemukan '>'` pada `laporan_penjualan.sql`. Lexer menghasilkan dua token terpisah: `OP` bernilai `'<'` lalu `OP` bernilai `'>'`. Menurut SPESIFIKASI.md bagian 2.5, `<>` adalah satu token `OP`.

**Reproduksi minimal.**

```sql
SELECT 1 WHERE 1 <> 2;
```

**Akar masalah.** Pada `crud/lexer.py` fungsi `_scan_token()`, penanganan karakter `<` hanya memeriksa kemungkinan karakter `=` (`<=`). Karakter `>` tidak dicek, sehingga `>` dibaca pada perulangan pemindaian berikutnya sebagai token tersendiri. Kode melanggar prinsip *maximal munch* (*Crafting Interpreters* Bab 4: Scanning), di mana lexer wajib mengambil deretan karakter terpanjang yang valid untuk membentuk satu token.

**Perbaikan.** Tambahkan pengecekan `self._match(">")` pada blok kondisi karakter `<` di fungsi `_scan_token()` untuk menghasilkan token `OP` bernilai `'<>'`. Alternatif menggabungkan dua token operator terpisah di tingkat parser ditolak karena melanggar batas tanggung jawab pipeline (parser tidak bertugas merapikan kesalahan tokenisasi lexer).

**Test regresi.** `test_bug_operator_not_equals` di `tests/test_tambahan.py`.

**Peran AI.** Membantu melacak kenapa karakter `>` dianggap token mandiri saat membaca klausa WHERE. Diverifikasi lewat output token pada sesi interaktif Python.

---

## Bug 3: Karakter Kutip Tunggal `''` di Dalam String Menutup String Lebih Awal

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** Kemal Melvin Ibrahim

**Gejala.** String SQL yang memuat karakter escape dua tanda kutip seperti `'O''Brien'` terpotong menjadi token `'O'`. Tanda kutip kedua dianggap sebagai penutup string, sehingga teks sisanya memicu error sintaks atau karakter tidak dikenal. Menurut SPESIFIKASI.md bagian 2.4, dua kutip tunggal berurutan di dalam string melambangkan satu karakter kutip asli.

**Reproduksi minimal.**

```sql
SELECT 'O''Brien';
```

**Akar masalah.** Pada `crud/lexer.py` fungsi `_string()`, loop pemindaian karakter langsung berhenti (`break`) setiap kali menemukan karakter `'` tanpa memeriksa karakter berikutnya. Mengacu pada konsep string escape sequence (*Crafting Interpreters* Bab 4: Scanning), scanner harus menggunakan teknik lookahead (`_peek()`). Jika karakter kutip diikuti oleh kutip lagi, scanner harus mengonsumsi keduanya dan menyimpan satu karakter `'` ke buffer.

**Perbaikan.** Pada `crud/lexer.py` di dalam fungsi `_string()`, saat bertemu karakter `'`, lakukan pengecekan `if self._peek() == "'":`. Jika benar, panggil `self._advance()` dan masukkan karakter `'` ke dalam list karakter string. Alternatif memakai regex replace string di akhir parsing ditolak karena pemindaian karakter di lexer sudah terlanjur putus di tengah jalan.

**Test regresi.** `test_bug_string_escaped_quote` di `tests/test_tambahan.py`.

**Peran AI.** Mengonfirmasi logika lookahead satu karakter untuk escaping SQL standar. Diverifikasi langsung dengan menjalankan pemindaian teks pada data sampel `pemeliharaan.sql`.

---

## Bug 4: Panic Mode Error Recovery Membuang Seluruh Token Sampai Akhir File

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Pada file `campuran_error.sql`, baris 4 mengalami syntax error (`SELECT id nama, FROM pesanan;`). Akibatnya, statement valid di baris 6 (UPDATE) dan baris 8 (DELETE) hilang total dari AST dan `crud_matrix.csv`. Menurut SPESIFIKASI.md bagian 6, setelah syntax error ditemukan, parser harus membuang token sampai dan termasuk tanda `;` berikutnya, lalu melanjutkan pemrosesan statement valid sesudahnya.

**Reproduksi minimal.**

```sql
SELECT 1 FROM ;
SELECT 2 FROM pelanggan;
```

**Akar masalah.** Fungsi `_synchronize()` pada `crud/parser.py` hanya berisi loop `while not self._at_end(): self._advance()`. Fungsi ini menghabiskan seluruh token yang tersisa hingga `EOF`. Hal ini melanggar konsep *Panic Mode Error Recovery* (*Crafting Interpreters* Bab 6: Parsing Expressions), di mana parser seharusnya hanya membuang token sampai batas sinkronisasi tertentu (pada SQL adalah batas akhir statement berupa `;`).

**Perbaikan.** Ubah loop pada fungsi `_synchronize()` di `crud/parser.py` agar berhenti setelah mengonsumsi token berjenis `SEMICOLON` (`if self._advance().type == T.SEMICOLON: return`). Alternatif sinkronisasi berbasis keyword awal statement (`SELECT`, `INSERT`, dsb.) ditolak karena spesifikasi bagian 6 secara tegas mensyaratkan token dibuang sampai dan termasuk titik koma.

**Test regresi.** `test_bug_panic_mode_recovery_semicolon` di `tests/test_tambahan.py`.

**Peran AI.** Menjelaskan implementasi panic mode standar dari buku Bab 6. Diverifikasi dengan menjalankan CLI pada file `campuran_error.sql` dan memastikan baris 6 serta baris 8 tetap terbaca.

---

## Bug 5: Presedensi Operator Logika `AND` dan `OR` Disamakan

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Kemal Melvin Ibrahim

**Gejala.** Pada ekspresi kondisi `WHERE a = 1 OR b = 2 AND c = 3`, parser menghasilkan pohon AST `BinaryOp` yang mengelompokkan operasi dari kiri ke kanan: `((a = 1) OR (b = 2)) AND (c = 3)`. Menurut SPESIFIKASI.md bagian 3.1, `AND` berada di tingkat presedensi 2 (lebih tinggi) dibanding `OR` di tingkat presedensi 1, sehingga pohon AST wajib berbentuk `(a = 1) OR ((b = 2) AND (c = 3))`.

**Reproduksi minimal.**

```sql
SELECT 1 WHERE 1 = 1 OR 2 = 2 AND 3 = 3;
```

**Akar masalah.** Pada `crud/parser.py` fungsi `_logical()`, kedua operator diproses dalam satu loop bersama: `while self._check_kw("AND", "OR"):`. Ini membuat kedua operator memiliki kedudukan yang setara dalam grammar. Mengacu pada aturan grammar ekspresi berlapis (*Crafting Interpreters* Bab 6: Parsing Expressions), setiap tingkatan presedensi harus dipisahkan ke dalam fungsi grammar yang berbeda agar operator berprioritas lebih tinggi dievaluasi lebih dalam pada hierarki pemanggilan fungsi.

**Perbaikan.** Pisahkan logika parsing ekspresi logika menjadi dua fungsi: `_or_expr()` untuk operator `OR` (memanggil `_and_expr()`) dan `_and_expr()` untuk operator `AND` (memanggil `_not()`). Alternatif menggunakan algoritma shunting-yard ditolak karena codebase memakai arsitektur recursive descent murni.

**Test regresi.** `test_bug_precedence_and_or` di `tests/test_tambahan.py`.

**Peran AI.** Membantu memvalidasi penurunan grammar ekspresi berjenjang. Diverifikasi dengan mengecek struktur pohon AST melalui opsi CLI `--ast` pada `audit.sql` baris 2-6.

---

## Bug 6: Keyword `OUTER` pada Klausa `LEFT OUTER JOIN` Ditolak Parser

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Query pada `pemeliharaan.sql` baris 5 yang menggunakan sintaks `left outer join` memicu error `ParseError: Baris X, kolom Y: diharapkan JOIN, ditemukan 'OUTER'`. Menurut SPESIFIKASI.md bagian 3, aturan tata bahasa join mendukung klausa `[ "INNER" | "LEFT" [ "OUTER" ] ] "JOIN"`.

**Reproduksi minimal.**

```sql
SELECT a.id FROM a LEFT OUTER JOIN b ON b.a_id = a.id;
```

**Akar masalah.** Pada `crud/parser.py` fungsi `_join()`, saat parser menemukan token `LEFT`, parser langsung memanggil `self._expect_kw("JOIN")` tanpa memeriksa kemungkinan keberadaan keyword opsional `OUTER`. Konsep yang dilanggar adalah kepatuhan terhadap aturan tata bahasa formal (*Crafting Interpreters* Bab 6: Parsing Expressions), di mana seluruh komponen opsional grammar harus dicocokkan sebelum melanjutkan ke token wajib berikutnya.

**Perbaikan.** Pada `crud/parser.py` fungsi `_join()`, tambahkan pemanggilan `self._match_kw("OUTER")` setelah mendeteksi token `LEFT` dan sebelum memanggil `self._expect_kw("JOIN")`. Alternatif mengubah lexer agar menggabungkan kata `LEFT` dan `OUTER` menjadi satu token ditolak karena menyalahi daftar token baku.

**Test regresi.** `test_bug_left_outer_join` di `tests/test_tambahan.py`.

**Peran AI.** Menemukan akar penolakan query saat menguji sintaks join bertingkat. Diverifikasi lewat pengetesan unit test parser langsung.

---

## Bug 7: Pencarian Scope Resolver Terbalik dari Luar ke Dalam

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Pada query subquery di mana alias lokal sama dengan alias luar (misalnya `SELECT x.id FROM pelanggan x WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x ...)` di `audit.sql`), kolom `x.pelanggan_id` dan `x.total` di dalam subquery salah dihubungkan ke tabel luar `pelanggan`. Berdasarkan SPESIFIKASI.md bagian 4.3, qualifier harus dicari dari scope terdalam ke luar agar terjadi mekanisme shadowing.

**Reproduksi minimal.**

```sql
SELECT x.id FROM t1 x WHERE x.id IN (SELECT x.id FROM t2 x);
```

**Akar masalah.** Pada `crud/resolver.py` fungsi `_lookup(name)`, rantai scope dikumpulkan lalu dibalik urutannya dengan `for scope in reversed(chain):`. Karena rantai sudah dibentuk dari scope aktif menuju scope induk (`parent`), pembalikan ini justru membuat penelusuran bermula dari scope terluar (global/induk). Hal ini melanggar konsep lexical scope resolution (*Crafting Interpreters* Bab 11: Resolving and Binding), di mana deklarasi lokal terdekat wajib menyembunyikan (*shadow*) deklarasi dengan nama serupa di lingkungan luar.

**Perbaikan.** Ubah `_lookup()` di `crud/resolver.py` agar menelusuri pointer `parent` secara langsung menggunakan loop `while scope is not None:`, tanpa memakai list `chain` dan `reversed()`. Alternatif membalik logika pembuatan list ditolak karena penelusuran langsung melalui pointer rantai lingkungan lebih sederhana dan sesuai implementasi baku Bab 11.

**Test regresi.** `test_bug_subquery_shadowing_inner_scope` di `tests/test_tambahan.py`.

**Peran AI.** Membantu membaca urutan traversal scope pada `_lookup`. Diverifikasi dengan mencocokkan hasil pemetaan tabel pada `kolom.csv` untuk `audit.sql` baris 12.

---

## Bug 8: Lingkungan Scope Statement `DELETE` Bocor ke Statement Selanjutnya

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** Kemal Melvin Ibrahim

**Gejala.** Pada `audit.sql` baris 16 terdapat query `DELETE FROM sesi s ...`, disusul baris 18 `SELECT s.id FROM pengguna u ...`. Query baris 18 tidak mendefinisikan alias `s`, namun resolver tidak mengeluarkan error `alias 's' tidak terdefinisi`. Kolom `s.id` malah dianggap merujuk ke tabel `sesi`. Menurut SPESIFIKASI.md bagian 4.5, setiap statement berdiri sendiri dan scope statement sebelumnya tidak boleh tersisa.

**Reproduksi minimal.**

```sql
DELETE FROM t1 s;
SELECT s.id FROM t2;
```

**Akar masalah.** Pada `crud/resolver.py` fungsi `_delete()`, scope dibuka dengan `self._push()`, namun di akhir fungsi tidak terdapat pemanggilan `self._pop()`. Hal ini melanggar siklus hidup scope blok (*Crafting Interpreters* Bab 11: Resolving and Binding). Lingkungan deklarasi lokal yang tidak ditutup menyebabkan entri simbol tabel tetap tertinggal di tumpukan scope saat memproses statement berikutnya.

**Perbaikan.** Tambahkan pemanggilan `self._pop()` di baris penutup fungsi `_delete()` pada `crud/resolver.py`. Alternatif mereset paksa `self.scope = None` di awal fungsi `resolve_statement()` ditolak karena cara tersebut hanya menambal gejala di tingkat luar dan bisa menyamarkan bug scope yang tidak tertutup rapi di dalam subquery.

**Test regresi.** `test_bug_delete_scope_leak` di `tests/test_tambahan.py`.

**Peran AI.** Memeriksa kelengkapan pasangan `push` dan `pop` di setiap statement handler. Diverifikasi dengan mengecek daftar diagnostik yang dihasilkan pipeline pada dua query berurutan.

---

## Bug 9: Subquery pada Pernyataan `UPDATE` Dilabeli Sebagai Operasi `U`

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Pada `audit.sql` baris 20 (`UPDATE pesanan SET ... WHERE pelanggan_id IN (SELECT id FROM pelanggan ...)`), tabel `pelanggan` tercatat memiliki operasi `U` pada `detail.csv`, sehingga matrix file menjadi `RU`. Menurut SPESIFIKASI.md bagian 5, membaca tabel lewat subquery selalu bernilai `R` tanpa memandang jenis statement luarnya.

**Reproduksi minimal.**

```sql
UPDATE t1 SET a = 1 WHERE b IN (SELECT c FROM t2);
```

**Akar masalah.** Pada `crud/analyzer.py` fungsi `analyze_statement()`, blok penanganan `ast.Update` memanggil fungsi pengumpul operasi dengan parameter `op="U"` untuk ekspresi assignment dan WHERE: `_collect(stmt.where, usage, "U")`. Akibatnya, tabel yang hanya dibaca di dalam subquery klausa WHERE ikut terkena cap operasi Update. Ini melanggar aturan semantik CRUD pada spesifikasi proyek.

**Perbaikan.** Pada `crud/analyzer.py` fungsi `analyze_statement()` cabang `isinstance(stmt, ast.Update)`, ubah argumen operasi pada pemanggilan `_collect(assignment.value, usage, "R")` dan `_collect(stmt.where, usage, "R")` menjadi `'R'`. Alternatif mengubah matriks gabungan di `pipeline.py` ditolak karena data per-statement di `detail.csv` akan tetap salah jika tidak diperbaiki di sumber analisanya.

**Test regresi.** `test_bug_update_subquery_read_only` di `tests/test_tambahan.py`.

**Peran AI.** Membantu membandingkan aturan tabel CRUD di SPESIFIKASI bagian 5 dengan pemanggilan rekursif di `analyzer.py`. Diverifikasi dengan memeriksa output `detail.csv` pada query sampel `audit.sql`.
