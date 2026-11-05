# Log Penggunaan AI

Catat setiap penggunaan AI atau coding agent yang memengaruhi kode atau laporan.

| No | Siapa | Prompt / tugas (ringkas) | Hasil: diterima, diubah, atau ditolak | Alasan | Cara verifikasi |
| --- | --- | --- | --- | --- | --- |
| 1 | Kemal & Denta | Diskusi akar masalah Bug 1 (keyword lowercase) dan struktur test regresi di test_tambahan.py | Diterima | Solusi to-the-point sesuai Bab 4 Crafting Interpreters dan memenuhi SPESIFIKASI.md bagian 2.2 | Menjalankan `pytest tests/test_lexer.py::test_keyword_huruf_kecil -v` dan `pytest tests/test_tambahan.py -v` (keduanya lulus) |
| 2 | Denta & Kemal | Diskusi konsep maximal munch Bab 4 untuk Bug 2 (operator `<>`) dan struktur test regresinya | Diterima | Solusi langsung menangani `<>` sebagai token tunggal di lexer sesuai SPESIFIKASI.md bagian 2.5 | Menjalankan `pytest tests/test_tambahan.py -v -k "bug2"` (lulus) |

**Refleksi (3-5 kalimat).** Di bagian mana AI paling membantu? Di mana AI keliru atau
menyesatkan, dan bagaimana kalian mengetahuinya?
