def clean_symbol(symbol: str) -> str:
    if symbol.endswith(".P"):
        return symbol[:-2]
    return symbol

