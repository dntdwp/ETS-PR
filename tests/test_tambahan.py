"""Test tambahan buatan kelompok.

Isi dengan:
1. Satu test regresi untuk setiap bug yang kalian perbaiki (gagal sebelum perbaikan,
   lulus sesudahnya). Beri nama yang menjelaskan bug-nya.
2. Lima test kasus tepi, masing-masing dengan komentar singkat mengapa kasus itu berisiko.
"""

from crud.lexer import TokenType as T, tokenize
import pytest
from crud.lexer import LexError
from crud.parser import parse_sql
from crud.ast_nodes import BinaryOp
from crud.resolver import Resolver
from crud import ast_nodes as ast
from crud.analyzer import analyze_statement


def test_bug1_keyword_case_insensitive():
    """Bug 1: Keyword dengan variasi huruf besar/kecil harus dikenali sebagai KEYWORD

    dan nilainya dinormalisasi ke huruf kapital.
    """
    toks = tokenize("sElEcT iD FrOm t WhErE aNd oR")
    keywords = [t for t in toks if t.type == T.KEYWORD]
    assert [k.value for k in keywords] == ["SELECT", "FROM", "WHERE", "AND", "OR"]

    # Memastikan kata yang hanya diawali keyword tetap menjadi IDENT
    ident_toks = tokenize("selection fromage")
    assert [t.type for t in ident_toks if t.type != T.EOF] == [T.IDENT, T.IDENT]

def test_bug2_operator_not_equals():
    """Bug 2: Operator '<>' harus dibaca sebagai satu token OP tunggal (maximal munch)."""
    toks = tokenize("a <> 1")
    op_tokens = [t for t in toks if t.type == T.OP]
    assert len(op_tokens) == 1
    assert op_tokens[0].value == "<>"

    # Memastikan operator pembanding lain tetap bekerja utuh
    toks_all = tokenize("< <= <> > >= !=")
    assert [t.value for t in toks_all if t.type == T.OP] == ["<", "<=", "<>", ">", ">=", "!="]

def test_bug3_string_escaped_quote():
    """Bug 3: Dua kutip tunggal berturut-turut ('') di dalam string mewakili satu karakter kutip asli."""
    toks = tokenize("'O''Brien'")
    assert len(toks) == 2  # Token STRING dan EOF
    assert toks[0].type == T.STRING
    assert toks[0].value == "O'Brien"

    # Kasus kutip escape di awal dan akhir string
    toks_edge = tokenize("'''halo'''")
    assert toks_edge[0].type == T.STRING
    assert toks_edge[0].value == "'halo'"

def test_todo_t3_komentar_blok():
    """TODO(T3): Komentar blok /* ... */ tidak menghasilkan token, boleh multi-baris,

    boleh berisi '*', dan melempar LexError jika tidak ditutup.
    """
    # 1. Komentar satu baris dan multi-baris
    toks = tokenize("/* komentar satu baris */ SELECT /* baris 1\n baris 2 */ id FROM t")
    assert [t.value for t in toks if t.type != T.EOF] == ["SELECT", "id", "FROM", "t"]

    # 2. Komentar berisi karakter '*' dan '/' di dalamnya
    toks_star = tokenize("/* perkalian: 2 * 3 / 6 = 1 ***/ SELECT id FROM t")
    assert toks_star[0].value == "SELECT"

    # 3. Komentar tidak ditutup harus memicu LexError
    with pytest.raises(LexError):
        tokenize("/* komentar tidak pernah ditutup\nSELECT id FROM t")

def test_bug4_panic_mode_recovery_semicolon():
    """Bug 4: Panic mode error recovery harus membuang token sampai ';' berikutnya

    dan statement valid setelahnya tetap diproses (SPESIFIKASI.md bagian 6).
    """
    sql = "SELECT id nama, FROM pesanan; SELECT id FROM pelanggan;"
    script = parse_sql(sql)
    # Harus ada 1 error dari statement pertama yang rusak
    assert len(script.errors) == 1
    # Statement kedua yang valid HARUS tetap berhasil diparse
    assert len(script.statements) == 1
    assert script.statements[0].sources[0].name == "pelanggan"

def test_bug5_precedence_and_or():
    """Bug 5: Operator AND memiliki presedensi lebih tinggi daripada OR (SPESIFIKASI.md bagian 3.1).

    Contoh: a = 1 OR b = 2 AND c = 3 harus diparse sebagai a = 1 OR (b = 2 AND c = 3).
    """
    sql = "SELECT id FROM t WHERE a = 1 OR b = 2 AND c = 3;"
    script = parse_sql(sql)
    assert script.errors == []
    where = script.statements[0].where

    # Puncak pohon (root) harus OR
    assert isinstance(where, BinaryOp)
    assert where.op == "OR"

    # Cabang kanan dari OR harus operasi AND
    assert isinstance(where.right, BinaryOp)
    assert where.right.op == "AND"

def test_bug6_left_outer_join():
    """Bug 6: Mendukung sintaks LEFT OUTER JOIN eksplisit (kata 'OUTER' opsional setelah 'LEFT')
    sesuai SPESIFIKASI.md bagian 3.
    """
    sql = "SELECT c.id FROM pelanggan c LEFT OUTER JOIN alamat a ON a.id = c.id;"
    script = parse_sql(sql)
    assert script.errors == []
    stmt = script.statements[0]
    assert len(stmt.joins) == 1
    assert stmt.joins[0].kind == "LEFT"
    assert stmt.joins[0].source.name == "alamat"

    # Memastikan LEFT JOIN (tanpa OUTER) dan INNER JOIN biasa tetap bekerja
    sql_mix = "SELECT * FROM t LEFT JOIN a ON a.id = t.id JOIN b ON b.id = t.id;"
    script_mix = parse_sql(sql_mix)
    assert script_mix.errors == []
    assert [j.kind for j in script_mix.statements[0].joins] == ["LEFT", "INNER"]

def test_todo_t1_insert_select():
    """TODO(T1): Mendukung sintaks INSERT INTO ... SELECT ... tanpa klausa VALUES
    sesuai SPESIFIKASI.md bagian 3 dan 5.
    """
    sql = "INSERT INTO arsip (id, total) SELECT id, total FROM pesanan WHERE tanggal < :batas;"
    script = parse_sql(sql)
    assert script.errors == []
    stmt = script.statements[0]
    assert stmt.table.name == "arsip"
    assert stmt.columns == ["id", "total"]
    assert stmt.values == []
    assert stmt.query is not None
    assert stmt.query.sources[0].name == "pesanan"

    # Kasus INSERT INTO ... SELECT tanpa daftar kolom eksplisit
    sql_no_cols = "INSERT INTO log SELECT * FROM aktivitas;"
    script_no_cols = parse_sql(sql_no_cols)
    assert script_no_cols.errors == []
    assert script_no_cols.statements[0].columns == []
    assert script_no_cols.statements[0].query.sources[0].name == "aktivitas"

def test_bug7_subquery_shadowing_innermost_first():
    """Bug 7: Qualifier harus dicari dari scope terdalam ke luar (shadowing)
    sesuai SPESIFIKASI.md bagian 4.3 dan Bab 11 Crafting Interpreters.
    Alias 'x' di subquery harus menutupi (shadow) alias 'x' di query luar.
    """
    sql = "SELECT x.id FROM pelanggan x WHERE x.id IN (SELECT x.id FROM pesanan x);"
    script = parse_sql(sql)
    Resolver().resolve_script(script)

    # Ambil kolom x.id di dalam subquery
    subquery = script.statements[0].where.query
    inner_col = subquery.columns[0].expr

    # Harus terhubung ke 'pesanan' (scope dalam), bukan 'pelanggan' (scope luar)
    assert inner_col.resolved == "pesanan"

def test_bug8_delete_scope_leakage():
    """Bug 8: Scope statement DELETE harus ditutup (_pop) agar aliasnya tidak bocor
    ke statement berikutnya sesuai SPESIFIKASI.md bagian 4.5.
    """
    sql = "DELETE FROM sesi s WHERE s.id = 1; SELECT s.id FROM pengguna u;"
    script = parse_sql(sql)
    diags = Resolver().resolve_script(script)

    # Statement kedua tidak punya alias 's', wajib menghasilkan error diagnostik
    assert any(d.level == "error" and "'s'" in d.message for d in diags)

    # Kolom s.id di statement kedua tidak boleh ter-resolve ke 'sesi'
    select_col = script.statements[1].columns[0].expr
    assert select_col.resolved is None

def test_todo_t2_unqualified_column():
    """TODO(T2): Kolom tanpa qualifier di scope terdalam:

    - 1 tabel: di-resolve ke tabel tersebut.
    - >1 tabel: warning 'ambigu tanpa skema', resolved tetap None.
    - 0 tabel: warning (SPESIFIKASI.md bagian 4.3).
    """
    # 1. Tepat satu tabel -> di-resolve ke tabel itu
    script1 = parse_sql("SELECT nama FROM pelanggan WHERE aktif = 1;")
    diags1 = Resolver().resolve_script(script1)
    cols1 = [n for n in ast.iter_nodes(script1) if isinstance(n, ast.ColumnRef)]
    assert {c.resolved for c in cols1} == {"pelanggan"}
    assert diags1 == []

    # 2. Lebih dari satu tabel -> warning ambigu tanpa skema, resolved tetap None
    script2 = parse_sql("SELECT id FROM t1, t2;")
    diags2 = Resolver().resolve_script(script2)
    col2 = [n for n in ast.iter_nodes(script2) if isinstance(n, ast.ColumnRef)][0]
    assert col2.resolved is None
    assert any(d.level == "warning" and "ambigu tanpa skema" in d.message for d in diags2)

def test_bug9_update_subquery_read_only():
    """Bug 9: Subquery di klausa SET maupun WHERE pada UPDATE hanya membaca tabel (operasi 'R')

    bukan operasi 'U' (SPESIFIKASI.md bagian 5).
    """
    sql = "UPDATE t1 SET a = 1 WHERE b IN (SELECT c FROM t2);"
    script = parse_sql(sql)
    usage = analyze_statement(script.statements[0])
    assert usage["t1"] == {"U"}
    # Tabel t2 di dalam subquery HARUS 'R', bukan 'U'
    assert usage["t2"] == {"R"}