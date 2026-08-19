SITE_CURRENCIES = {
    "CBT": "USD",  # Cross-Border Trade (全球卖家)
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

SITE_MARKETPLACE_DOMAINS = {
    "CBT": "mercadolibre.com",  # Cross-Border Trade 全球站
    "MLA": "mercadolibre.com.ar",
    "MBO": "mercadolibre.com.bo",
    "MLB": "mercadolivre.com.br",
    "MLC": "mercadolibre.cl",
    "MCO": "mercadolibre.com.co",
    "MCR": "mercadolibre.co.cr",
    "MRD": "mercadolibre.com.do",
    "MEC": "mercadolibre.com.ec",
    "MSV": "mercadolibre.com.sv",
    "MGT": "mercadolibre.com.gt",
    "MHN": "mercadolibre.com.hn",
    "MLM": "mercadolibre.com.mx",
    "MNI": "mercadolibre.com.ni",
    "MPA": "mercadolibre.com.pa",
    "MPY": "mercadolibre.com.py",
    "MPE": "mercadolibre.com.pe",
    "MLU": "mercadolibre.com.uy",
    "MLV": "mercadolibre.com.ve",
}


def expected_currency(site_id: str) -> str:
    return SITE_CURRENCIES.get(site_id.strip().upper(), "")


def authorization_base_url(site_id: str) -> str:
    domain = SITE_MARKETPLACE_DOMAINS.get(site_id.strip().upper())
    if not domain:
        raise ValueError("unsupported_mercado_libre_site")
    return f"https://auth.{domain}/authorization"
