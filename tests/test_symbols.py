from services.symbols import clean_symbol


def test_clean_symbol_removes_dot_p():
    assert clean_symbol("BTCUSDT.P") == "BTCUSDT"


def test_clean_symbol_no_suffix():
    assert clean_symbol("BTCUSDT") == "BTCUSDT"


def test_clean_symbol_other_suffix():
    assert clean_symbol("BTCUSDT.X") == "BTCUSDT.X"


def test_clean_symbol_empty():
    assert clean_symbol("") == ""


def test_clean_symbol_only_dot_p():
    assert clean_symbol(".P") == ""
