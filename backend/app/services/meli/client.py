import httpx


class MercadoLibreClient:
    def __init__(
        self,
        access_token: str = "",
        base_url: str = "https://api.mercadolibre.com",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30,
    ):
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def get(self, path: str) -> dict:
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{path}", headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}{path}", json=payload, headers=self._headers()
            )
            response.raise_for_status()
            return response.json()
