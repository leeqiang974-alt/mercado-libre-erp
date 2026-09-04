"""Retry + error-detail behaviour for picture materialization."""

import asyncio

import httpx

from app.services.meli import pictures as pics


class FakeDownloader:
    def __init__(self, statuses):
        self._statuses = list(statuses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, source):
        status = self._statuses.pop(0) if self._statuses else 200
        req = httpx.Request("GET", "https://example.com/x.jpg")
        if status == 200:
            return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"\xff\xd8xx", request=req)
        raise httpx.HTTPStatusError(f"status {status}", request=req, response=httpx.Response(status, request=req))


class FakeClient:
    def __init__(self, statuses):
        self._statuses = list(statuses)
        self.calls = 0

    async def upload_picture(self, *, content, filename, content_type):
        self.calls += 1
        req = httpx.Request("POST", "https://api.mercadolibre.com/pictures/items/upload")
        status = self._statuses.pop(0) if self._statuses else 200
        if status == 200:
            return {"id": "PIC-1"}
        raise httpx.HTTPStatusError(f"status {status}", request=req, response=httpx.Response(status, request=req))


def _req() -> httpx.Request:
    return httpx.Request("GET", "https://example.com/x.jpg")


def test_download_retries_transient_then_succeeds():
    async def run():
        downloader = FakeDownloader([500, 200])
        pics.httpx.AsyncClient = lambda *a, **k: downloader
        response = await pics._download_with_retry("https://example.com/x.jpg")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"

    asyncio.run(run())


def test_download_does_not_retry_400():
    async def run():
        downloader = FakeDownloader([400])
        pics.httpx.AsyncClient = lambda *a, **k: downloader
        try:
            await pics._download_with_retry("https://example.com/x.jpg")
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code == 400
        else:
            raise AssertionError("400 should not be retried")

    asyncio.run(run())


def test_upload_retries_transient_then_succeeds():
    async def run():
        client = FakeClient([503, 200])
        uploaded = await pics._upload_with_retry(client, content=b"x", filename="a.jpg", content_type="image/jpeg")
        assert uploaded["id"] == "PIC-1"
        assert client.calls == 2

    asyncio.run(run())


def test_upload_does_not_retry_400():
    async def run():
        client = FakeClient([400])
        try:
            await pics._upload_with_retry(client, content=b"x", filename="a.jpg", content_type="image/jpeg")
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code == 400
        else:
            raise AssertionError("400 should not be retried")
        assert client.calls == 1

    asyncio.run(run())


def test_error_detail_extracts_xml_message():
    response = httpx.Response(
        400,
        request=_req(),
        content=b"<Error><Code>InvalidArgument</Code><Message>Invalid access key</Message></Error>",
    )
    assert pics._upload_error_detail(response) == "：Invalid access key"


def test_error_detail_extracts_json():
    response = httpx.Response(400, request=_req(), json={"error": "bad_request", "message": "invalid image"})
    assert pics._upload_error_detail(response) == "：bad_request: invalid image"


def test_materialize_retries_transient_download(monkeypatch):
    async def run():
        downloader = FakeDownloader([503, 200])
        pics.httpx.AsyncClient = lambda *a, **k: downloader
        monkeypatch.setattr(pics, "normalize_listing_image", lambda data, ct: (data, "image/jpeg", (500, 500), (500, 500)))
        uploaded = []

        class _C:
            async def upload_picture(self, **kwargs):
                uploaded.append(1)
                return {"id": "PIC-FINAL"}

        client = _C()
        payload = {"pictures": [{"source": "https://example.com/x.jpg"}], "sites_to_sell": []}
        out = await pics.materialize_global_picture_sources(client, payload)
        assert out["pictures"] == [{"id": "PIC-FINAL"}]
        assert len(uploaded) == 1

    asyncio.run(run())
