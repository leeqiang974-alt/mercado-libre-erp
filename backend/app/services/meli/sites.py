SITE_CURRENCIES = {
    "MLA": "ARS",
    "MBO": "BOB",
    "MLB": "BRL",
    "MLC": "CLP",
    "MCO": "COP",
    "MCR": "CRC",
    "MRD": "DOP",
    "MEC": "USD",
    "MSV": "USD",
    "MGT": "GTQ",
    "MHN": "HNL",
    "MLM": "MXN",
    "MNI": "NIO",
    "MPA": "USD",
    "MPY": "PYG",
    "MPE": "PEN",
    "MLU": "UYU",
    "MLV": "VES",
}


def expected_currency(site_id: str) -> str:
    return SITE_CURRENCIES.get(site_id.strip().upper(), "")
