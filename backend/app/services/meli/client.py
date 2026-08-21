import httpx


class MercadoLibreResponseError(httpx.RequestError):
    pass


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

    async def get(self, path: str) -> dict | list:
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{path}", headers=self._headers())
            response.raise_for_status()
            return _response_json(response)

    async def post(self, path: str, payload: dict) -> dict | list:
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}{path}", json=payload, headers=self._headers()
            )
            response.raise_for_status()
            return _response_json(response)

    async def put(self, path: str, payload: dict) -> dict | list:
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            response = await client.put(
                f"{self.base_url}{path}", json=payload, headers=self._headers()
            )
            response.raise_for_status()
            return _response_json(response)

    async def upload_picture(
        self, *, content: bytes, filename: str, content_type: str
    ) -> dict | list:
        """Upload a validated image to Mercado Libre before a Global listing."""
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/pictures/items/upload",
                headers=self._headers(),
                files={"file": (filename, content, content_type)},
            )
            response.raise_for_status()
            return _response_json(response)


def _response_json(response: httpx.Response) -> dict | list:
    if not response.content.strip():
        return {}
    try:
        payload = response.json()
    except ValueError as exc:
        raise MercadoLibreResponseError(
            "Mercado Libre returned a non-JSON success response.",
            request=response.request,
        ) from exc
    if not isinstance(payload, (dict, list)):
        raise MercadoLibreResponseError(
            "Mercado Libre returned an unexpected JSON response.",
            request=response.request,
        )
    return payload
