# Laporan Bug

Dokumentasi sembilan bug yang ditemukan pada pipeline ekstraktor CRUD matrix beserta analisis penyebab teknisnya berdasarkan konsep *Crafting Interpreters* dan `SPESIFIKASI.md`.

---

## Bug 1: Keyword Huruf Kecil Dianggap Identifier

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Kemal Melvin Ibrahim

**Gejala.** Query SQL yang ditulis menggunakan huruf kecil seperti `select id from pelanggan;` gagal diproses sebagai statement SELECT. Token pertama yang dihasilkan bertipe `IDENT` bernilai `'select'`, bukan `KEYWORD` `'SELECT'`. Menurut SPESIFIKASI.md bagian 2.2, keyword bersifat case-insensitive dan nilainya dinormalisasi ke huruf besar.

**Reproduksi minimal.**

```sql
select id from t;
```

**Akar masalah.** Kesalahan terjadi pada **Tahap 1 Pipeline (Lexer / Scanning)** di file `crud/lexer.py` fungsi `_word()`. Leksikograf mengambil potongan teks langsung dari kode sumber (`text = self.src[start:self.pos]`) dan mencocokkannya ke himpunan `KEYWORDS` secara peka huruf besar/kecil (`if text in KEYWORDS:`). Karena seluruh elemen di konstanta `KEYWORDS` ditulis dalam huruf kapital, kata kunci berhuruf kecil gagal cocok dan jatuh ke cabang `else` sebagai token `IDENT`. Hal ini melanggar konsep pemindaian *reserved words* dan *identifiers* pada *Crafting Interpreters* Bab 4 (Scanning), di mana proses pengenalan kata kunci pada bahasa yang *case-insensitive* wajib menormalisasi kapitalisasi leksim terlebih dahulu sebelum pencocokan tabel kata kunci.

**Perbaikan.** Pada `crud/lexer.py` fungsi `_word()`, tambahkan normalisasi `text_upper = text.upper()`. Jika `text_upper in KEYWORDS`, simpan token `KEYWORD` dengan nilai `text_upper`. Jika bukan, tetap simpan sebagai `IDENT` dengan nilai asli `text`. Alternatif mendaftarkan variasi huruf kecil ke himpunan `KEYWORDS` ditolak karena memboroskan memori, tidak menangani campuran huruf besar-kecil (`SeLeCt`), dan nilai token tidak otomatis ternormalisasi kapital.

**Test regresi.** `test_bug1_keyword_case_insensitive` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver membantu memetakan letak fungsi `_word()` terhadap konsep Bab 4 dan menyarankan struktur test regresi. Diverifikasi langsung oleh Kemal dengan menjalankan `pytest tests/test_lexer.py::test_keyword_huruf_kecil -v` dan `pytest tests/test_tambahan.py -v`.

---

## Bug 2: Operator Perbandingan `<>` Dipecah Menjadi Dua Token

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Pernyataan SQL dengan operator `<>` menghasilkan error `ParseError: Baris 6, kolom 41: diharapkan ekspresi, ditemukan '>'` pada `laporan_penjualan.sql`. Lexer menghasilkan dua token terpisah: `OP` bernilai `'<'` lalu `OP` bernilai `'>'`. Menurut SPESIFIKASI.md bagian 2.5, `<>` adalah satu token `OP`.

**Reproduksi minimal.**

```sql
SELECT id FROM t WHERE a <> 1;
```

**Akar masalah.** Kesalahan terjadi pada **Tahap 1 Pipeline (Lexer / Scanning)** di file `crud/lexer.py` fungsi `_scan_token()`. Saat membaca karakter `<`, cabang kondisional hanya melakukan *lookahead* satu karakter untuk `=` (`<=`), tanpa memeriksa kemungkinan karakter `>` (`<>`). Akibatnya, lexer hanya mengonsumsi `<` sebagai token tunggal dan menyisakan `>` untuk perulangan pemindaian berikutnya. Penyebab ini melanggar prinsip **maximal munch** (*Crafting Interpreters* Bab 4: Scanning), yaitu aturan bahwa ketika dua pola leksikal cocok pada awalan yang sama, scanner wajib mengonsumsi rangkaian karakter terpanjang yang membentuk token valid (`<>` alih-alih `<` diikuti `>`).

**Perbaikan.** Pada `crud/lexer.py` fungsi `_scan_token()`, pada blok penanganan karakter `<`, tambahkan cabang `elif self._match(">"): op = "<>"` sebelum cabang `else`. Alternatif menggabungkan dua token operator terpisah di tingkat parser ditolak karena melanggar batas tanggung jawab pipeline (parser tidak bertugas memperbaiki kegagalan maximal munch dari lexer).

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

**Akar masalah.** Kesalahan terjadi pada **Tahap 1 Pipeline (Lexer / Scanning)** di file `crud/lexer.py` fungsi `_string()`. Perulangan pembacaan literal string langsung mengeksekusi `break` begitu menemukan karakter `'` pertama setelah pembuka, tanpa melakukan *lookahead* satu karakter ke depan (`_peek()`). Hal ini melanggar mekanisme pemindaian *string literals* dengan *escape sequence* (*Crafting Interpreters* Bab 4: Scanning), di mana scanner harus mengintip karakter berikutnya saat menjumpai delimiter: jika karakter setelah `'` adalah `'` lagi, maka pasangan `''` tersebut adalah representasi satu karakter kutip di dalam nilai string, bukan penutup token.

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

**Akar masalah.** Kesalahan terjadi pada **Tahap 2 Pipeline (Parser)** di file `crud/parser.py` fungsi `_synchronize()`. Fungsi pemulihan hanya berisi perulangan `while not self._at_end(): self._advance()` tanpa kondisi berhenti pada pembatas statement, sehingga saat terjadi satu `ParseError`, parser membuang seluruh sisa token di file hingga `EOF`. Penyebab ini melanggar konsep **titik sinkronisasi (synchronization point) pada Panic Mode Error Recovery** (*Crafting Interpreters* Bab 6: Parsing Expressions), di mana parser harus berhenti membuang token begitu melewati batas statement (token `;` / `SEMICOLON`) agar state parser kembali selaras dengan awal statement berikutnya dan tidak membatalkan pemrosesan sisa file.

**Perbaikan.** Pada `crud/parser.py` fungsi `_synchronize()`, ubah perulangan agar membaca dan membuang token sampai menemukan token berjenis `SEMICOLON` (`if self._advance().type == T.SEMICOLON: return`), lalu keluar dari mode panik untuk memproses statement berikutnya. Alternatif sinkronisasi berbasis keyword awal statement (`SELECT`, `INSERT`) ditolak karena berisiko berhenti prematur pada keyword `SELECT` milik subquery di dalam statement yang masih rusak, serta melanggar SPESIFIKASI.md bagian 6.

**Test regresi.** `test_bug4_panic_mode_recovery_semicolon` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver memandu penerapan konsep titik sinkronisasi panic mode recovery (*Crafting Interpreters* Bab 6). Diverifikasi langsung oleh Kemal dengan menjalankan `pytest tests/test_tambahan.py -v -k "bug4"`.

---

## Bug 5: Presedensi Operator Logika `AND` dan `OR` Disamakan

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Kemal Melvin Ibrahim

**Gejala.** Pada ekspresi kondisi `WHERE a = 1 OR b = 2 AND c = 3`, parser menghasilkan pohon AST `BinaryOp` yang mengelompokkan operasi dari kiri ke kanan: `((a = 1) OR (b = 2)) AND (c = 3)`. Menurut SPESIFIKASI.md bagian 3.1, `AND` berada di tingkat presedensi 2 (lebih tinggi) dibanding `OR` di tingkat presedensi 1, sehingga pohon AST wajib berbentuk `(a = 1) OR ((b = 2) AND (c = 3))`.

**Reproduksi minimal.**

```sql
SELECT id FROM t WHERE a = 1 OR b = 2 AND c = 3;
```

**Akar masalah.** Kesalahan terjadi pada **Tahap 2 Pipeline (Parser)** di file `crud/parser.py` fungsi `_logical()`. Kedua operator logika (`AND` dan `OR`) digabungkan dalam satu perulangan dan satu fungsi produksi yang sama: `while self._check_kw("AND", "OR"):`. Penyatuan ini membuat `AND` dan `OR` memiliki **level presedensi** yang sama dan hanya dievaluasi berurutan dari kiri ke kanan. Hal ini melanggar konsep **stratifikasi aturan grammar berdasarkan level presedensi (precedence stratification)** pada *recursive descent parser* (*Crafting Interpreters* Bab 6: Parsing Expressions), di mana setiap tingkat presedensi wajib direpresentasikan oleh satu metode terpisah yang memanggil metode berpresedensi lebih tinggi (`or_expr` memanggil `and_expr`, dan `and_expr` memanggil `not_expr`).

**Perbaikan.** Pada `crud/parser.py`, ganti fungsi `_logical()` menjadi dua fungsi terpisah: `_or_expr()` untuk level presedensi 1 (`OR`) yang memanggil `_and_expr()`, serta `_and_expr()` untuk level presedensi 2 (`AND`) yang memanggil `_not()`. Fungsi `_expr()` diarahkan memanggil `_or_expr()`. Alternatif menggunakan algoritma Pratt parser atau shunting-yard ditolak karena seluruh ekspresi lain di codebase sudah menggunakan pola stratified recursive descent.

**Test regresi.** `test_bug5_precedence_and_or` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver memandu pembagian level presedensi (*stratified grammar* Bab 6) menjadi `_or_expr` dan `_and_expr`. Diverifikasi langsung oleh Kemal dengan menjalankan `pytest tests/test_tambahan.py -v -k "bug5"`.

---

## Bug 6: Keyword `OUTER` pada Klausa `LEFT OUTER JOIN` Ditolak Parser

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Query pada `pemeliharaan.sql` baris 5 yang menggunakan sintaks `left outer join` memicu error `ParseError: Baris 1, kolom 25: diharapkan JOIN, ditemukan 'OUTER'`. Menurut SPESIFIKASI.md bagian 3, aturan tata bahasa join mendukung klausa `[ "INNER" | "LEFT" [ "OUTER" ] ] "JOIN"`.

**Reproduksi minimal.**

```sql
SELECT a.id FROM a LEFT OUTER JOIN b ON b.a_id = a.id;
```

**Akar masalah.** Kesalahan terjadi pada **Tahap 2 Pipeline (Parser)** di file `crud/parser.py` fungsi `_join()`. Setelah cabang `elif self._match_kw("LEFT"):` berhasil mengonsumsi token `LEFT`, fungsi langsung mengeksekusi `self._expect_kw("JOIN")` tanpa mengonsumsi token opsional `OUTER`. Penyebab ini melanggar prinsip **translasi produksi Context-Free Grammar (CFG) ke kode recursive descent** (*Crafting Interpreters* Bab 5: Representing Code & Bab 6: Parsing Expressions), di mana simbol opsional `[ "OUTER" ]` pada aturan produksi `join = [ "INNER" | "LEFT" [ "OUTER" ] ] "JOIN" ...` wajib diterjemahkan menjadi pencocokan kondisional (`_match_kw("OUTER")`) sebelum parser menuntut token terminal wajib berikutnya (`"JOIN"`).

**Perbaikan.** Pada `crud/parser.py` fungsi `_join()`, tambahkan pemanggilan `self._match_kw("OUTER")` di dalam blok `elif self._match_kw("LEFT"):` sebelum pemanggilan `self._expect_kw("JOIN")`. Alternatif mengubah lexer agar menggabungkan `LEFT OUTER` menjadi satu token ditolak karena mengaburkan pemisahan leksikal dan sintaksis.

**Test regresi.** `test_bug6_left_outer_join` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver memverifikasi kesesuaian implementasi `_join()` dengan aturan produksi EBNF di SPESIFIKASI.md bagian 3. Diverifikasi langsung oleh Denta dengan menjalankan `pytest tests/test_tambahan.py -v -k "bug6"`.

---

## Bug 7: Pencarian Scope Resolver Terbalik dari Luar ke Dalam

**Ditemukan oleh:** Kemal Melvin Ibrahim · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Pada query subquery di mana alias lokal sama dengan alias luar (misalnya `SELECT x.id FROM pelanggan x WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x ...)` di `audit.sql`), kolom `x.pelanggan_id` dan `x.total` di dalam subquery salah dihubungkan ke tabel luar `pelanggan`. Berdasarkan SPESIFIKASI.md bagian 4.3, qualifier harus dicari dari scope terdalam ke luar agar terjadi mekanisme shadowing.

**Reproduksi minimal.**

```sql
SELECT x.id FROM t1 x WHERE x.id IN (SELECT x.id FROM t2 x);
```

**Akar masalah.** Kesalahan terjadi pada **Tahap 3 Pipeline (Resolver)** di file `crud/resolver.py` fungsi `_lookup(name)`. Saat mengumpulkan **rantai scope** dari `self.scope` (scope terdalam) menuju `scope.parent` (scope luar) ke dalam list `chain`, kode justru mengiterasi list tersebut secara terbalik menggunakan `for scope in reversed(chain):`. Pembalikan urutan ini menyebabkan resolusi nama dimulai dari scope paling luar (induk) menuju scope terdalam. Hal ini melanggar konsep **penelusuran rantai scope (scope chain traversal) dan lexical shadowing** (*Crafting Interpreters* Bab 11: Resolving and Binding), di mana resolusi variabel/alias wajib berjalan dari lingkungan terdalam (*innermost scope*) ke luar agar deklarasi lokal menutupi (*shadow*) nama yang sama di scope luar.

**Perbaikan.** Pada `crud/resolver.py` fungsi `_lookup()`, hapus list perantara `chain` dan `reversed(chain)`, lalu telusuri langsung pointer `scope = scope.parent` mulai dari `self.scope` (terdalam) hingga `None`. Alternatif tetap memakai list tanpa `reversed()` ditolak karena alokasi list baru di setiap pencarian kolom tidak efisien dibanding menelusuri pointer linked-list `parent` secara langsung.

**Test regresi.** `test_bug7_subquery_shadowing_innermost_first` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver menjelaskan konsep rantai scope dan *shadowing* (Bab 11 *Crafting Interpreters*) serta menyusun skenario test regresi. Diverifikasi langsung oleh Denta lewat `pytest tests/test_tambahan.py -v -k "bug7"`.

---

## Bug 8: Lingkungan Scope Statement `DELETE` Bocor ke Statement Selanjutnya

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** Denta Dwipawasesa

**Gejala.** Pada `audit.sql` baris 16 terdapat query `DELETE FROM sesi s ...`, disusul baris 18 `SELECT s.id FROM pengguna u ...`. Query baris 18 tidak mendefinisikan alias `s`, namun resolver tidak mengeluarkan error `alias 's' tidak terdefinisi`. Kolom `s.id` malah dianggap merujuk ke tabel `sesi`. Menurut SPESIFIKASI.md bagian 4.5, setiap statement berdiri sendiri dan scope statement sebelumnya tidak boleh tersisa.

**Reproduksi minimal.**

```sql
DELETE FROM t1 s;
SELECT s.id FROM t2;
```

**Akar masalah.** Kesalahan terjadi pada **Tahap 3 Pipeline (Resolver)** di file `crud/resolver.py` fungsi `_delete()`. Fungsi tersebut membuka scope baru di awal eksekusi dengan `self._push()`, tetapi tidak memanggil `self._pop()` setelah selesai meresolusi klausa `WHERE`. Akibatnya, objek `Scope` milik statement `DELETE` tetap berada di puncak **rantai scope** (`self.scope`), sehingga statement berikutnya menjadikan scope `DELETE` tersebut sebagai `parent` scope-nya. Hal ini melanggar aturan **siklus hidup scope blok (block scope entry and exit symmetry)** pada *Crafting Interpreters* Bab 11 (Resolving and Binding), di mana setiap pembukaan scope (`beginScope` / `_push`) wajib memiliki pasangan penutupan (`endScope` / `_pop`) yang simetris saat keluar dari node AST statement.

**Perbaikan.** Pada `crud/resolver.py` fungsi `_delete()`, tambahkan pemanggilan `self._pop()` di baris terakhir fungsi agar scope `DELETE` dilepas dari tumpukan begitu statement selesai di-resolve. Alternatif mereset paksa `self.scope = None` di fungsi `resolve_statement()` ditolak karena hanya menambal gejala dari luar dan dapat menyembunyikan ketidakseimbangan `_push()`/`_pop()` pada subquery bersarang.

**Test regresi.** `test_bug8_delete_scope_leakage` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver memandu pemeriksaan simetri `_push()` dan `_pop()` pada rantai scope (*Crafting Interpreters* Bab 11). Diverifikasi langsung oleh Denta lewat `pytest tests/test_tambahan.py -v -k "bug8"`.

---

## Bug 9: Subquery pada Pernyataan `UPDATE` Dilabeli Sebagai Operasi `U`

**Ditemukan oleh:** Denta Dwipawasesa · **Diperbaiki oleh:** Kemal Melvin Ibrahim

**Gejala.** Pada `audit.sql` baris 20 (`UPDATE pesanan SET ... WHERE pelanggan_id IN (SELECT id FROM pelanggan ...)`), tabel `pelanggan` tercatat memiliki operasi `U` pada `detail.csv`, sehingga matrix file menjadi `RU`. Menurut SPESIFIKASI.md bagian 5, membaca tabel lewat subquery selalu bernilai `R` tanpa memandang jenis statement luarnya.

**Reproduksi minimal.**

```sql
UPDATE t1 SET a = 1 WHERE b IN (SELECT c FROM t2);
```

**Akar masalah.** Kesalahan terjadi pada **Tahap 4 Pipeline (Analyzer / AST Semantic Pass)** di file `crud/analyzer.py` fungsi `analyze_statement()`. Pada cabang `elif isinstance(stmt, ast.Update):`, setelah mencatat tabel target sebagai `"U"`, fungsi menelusuri child node ekspresi `assignment.value` dan `stmt.where` dengan meneruskan argumen konteks operasi `"U"` (`_collect(assignment.value, usage, "U")` dan `_collect(stmt.where, usage, "U")`). Hal ini melanggar prinsip **penelusuran pohon sintaks kontekstual (contextual AST traversal / semantic analysis pass)** pada *Crafting Interpreters* Bab 5 (Representing Code) dan Bab 11 (Resolving and Binding) serta aturan semantik domain `SPESIFIKASI.md` bagian 5: efek samping mutasi (`"U"`) hanya berlaku pada node target utama `stmt.table`, sedangkan seluruh child node ekspresi di dalam klausa `SET` dan `WHERE` berada dalam konteks evaluasi pembacaan nilai (*read-only query context*) sehingga wajib diteruskan dengan konteks operasi `"R"`.

**Perbaikan.** Pada `crud/analyzer.py` fungsi `analyze_statement()` cabang `ast.Update`, ubah argumen operasi pada pemanggilan `_collect(assignment.value, usage, "R")` dan `_collect(stmt.where, usage, "R")` dari `"U"` menjadi `"R"`. Alternatif memodifikasi fungsi `_collect_select()` agar mengabaikan parameter `op` dan selalu menulis `"R"` ditolak karena membuat parameter `op` pada `_collect()` dan `_collect_select()` menjadi redundan serta membingungkan kontrak antarfungsi di dalam analyzer.

**Test regresi.** `test_bug9_update_subquery_read_only` di `tests/test_tambahan.py`.

**Peran AI.** Co-driver membantu memetakan pemisahan konteks mutasi vs pembacaan saat *AST traversal* (Bab 5 & Bab 11) sesuai aturan semantik SPESIFIKASI.md bagian 5. Diverifikasi langsung oleh Kemal lewat `pytest tests/test_tambahan.py -v -k "bug9"`.
