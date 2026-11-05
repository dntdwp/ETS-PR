"""Test tambahan buatan kelompok.

Isi dengan:
1. Satu test regresi untuk setiap bug yang kalian perbaiki (gagal sebelum perbaikan,
   lulus sesudahnya). Beri nama yang menjelaskan bug-nya.
2. Lima test kasus tepi, masing-masing dengan komentar singkat mengapa kasus itu berisiko.
"""

from crud.lexer import TokenType as T, tokenize

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