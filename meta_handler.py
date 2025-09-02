import aiohttp
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Tuple, Any


@dataclass
class AppResponse:
    success: bool
    message: str


class WhatsAppMetaHandler:
    def __init__(self, meta_api_key: str, base_url: str, api_version: str, audio_client=None):
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.audio_client = audio_client
        self.messaging_product = "whatsapp"
        self.recipient_type = "individual"
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {meta_api_key}",
                "Accept": "application/json",
            }
        )

    async def _post(self, phone_number_id: str, data: dict) -> AppResponse:
        url = f"{self.base_url}/{self.api_version}/{phone_number_id}/messages"
        async with self.session.post(url, json=data) as resp:
            if resp.status != 200:
                return AppResponse(False, "Error occurred")
            return AppResponse(True, "Successful operation")

    async def send_text_message(self, phone_number_id: str, to: str, text: str, preview_url: bool = False) -> AppResponse:
        return await self._post(phone_number_id, {
            "messaging_product": self.messaging_product,
            "recipient_type": self.recipient_type,
            "to": to,
            "type": "text",
            "text": {"preview_url": preview_url, "body": text}
        })

    async def send_document(self, phone_number_id: str, to: str,
                            document_id: Optional[str] = None,
                            document_url: Optional[str] = None,
                            caption: Optional[str] = None,
                            filename: Optional[str] = None) -> AppResponse:
        if not (document_id or document_url):
            return AppResponse(False, "Either documentId or documentUrl must be provided")

        document_data = {}
        if document_id: document_data["id"] = document_id
        if document_url: document_data["link"] = document_url
        if caption: document_data["caption"] = caption
        if filename: document_data["filename"] = filename

        return await self._post(phone_number_id, {
            "messaging_product": self.messaging_product,
            "recipient_type": self.recipient_type,
            "to": to,
            "type": "document",
            "document": document_data
        })

    async def send_image(self, phone_number_id: str, to: str, image_url: str, caption: Optional[str] = None) -> AppResponse:
        if not image_url.strip():
            return AppResponse(False, "Image URL must be provided")

        return await self._post(phone_number_id, {
            "messaging_product": self.messaging_product,
            "recipient_type": self.recipient_type,
            "to": to,
            "type": "image",
            "image": {
                "link": image_url,
                "caption": caption or ""
            }
        })

    async def send_template(self, phone_number_id: str, to: str, template_name: str,
                            language_code: str = "en_US", components: Optional[List[Any]] = None) -> AppResponse:
        return await self._post(phone_number_id, {
            "messaging_product": self.messaging_product,
            "recipient_type": self.recipient_type,
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components or []
            }
        })

    async def get_media_url(self, media_id: str) -> str:
        if not media_id:
            return ""
        url = f"{self.base_url}/{self.api_version}/{media_id}"
        async with self.session.get(url) as resp:
            if resp.status != 200:
                return ""
            data = await resp.json()
            return data.get("url", "")

    async def close(self):
        await self.session.close()


# Example usage
async def main():
    handler = WhatsAppMetaHandler(
        meta_api_key="YOUR_API_KEY",
        base_url="https://graph.facebook.com",
        api_version="v18.0"
    )

    resp = await handler.send_text_message("1234567890", "15551234567", "Hello from Python!")
    print(resp)

    await handler.close()

# asyncio.run(main())
