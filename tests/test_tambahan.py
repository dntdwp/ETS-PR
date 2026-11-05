"""Test tambahan buatan kelompok.

Isi dengan:
1. Satu test regresi untuk setiap bug yang kalian perbaiki (gagal sebelum perbaikan,
   lulus sesudahnya). Beri nama yang menjelaskan bug-nya.
2. Lima test kasus tepi, masing-masing dengan komentar singkat mengapa kasus itu berisiko.
"""

from crud.lexer import TokenType as T, tokenize
import pytest
from crud.lexer import LexError

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
    with pytest.raises(LexError) as exc:
        tokenize("/* komentar tidak pernah ditutup\nSELECT id FROM t")
    assert "tidak ditutup" in str(exc.value)