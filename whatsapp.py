import os
import httpx
import logging

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v19.0"


def get_headers():
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def get_phone_id():
    return os.getenv("WHATSAPP_PHONE_NUMBER_ID")


async def send_text_message(to: str, text: str):
    """Send a plain text message"""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text, "preview_url": False}
    }
    await _send(payload)


async def send_image_message(to: str, image_url: str, caption: str = ""):
    """Send an image message with optional caption"""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    await _send(payload)


async def send_cta_url_message(to: str, body_text: str, button_text: str, url: str):
    """Send a message with a CTA URL button"""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body_text},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text,
                    "url": url
                }
            }
        }
    }
    await _send(payload)


async def _send(payload: dict):
    """Internal function to send API request"""
    phone_id = get_phone_id()
    url = f"{WHATSAPP_API_URL}/{phone_id}/messages"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=get_headers(), timeout=10)
            if r.status_code != 200:
                logger.error(f"WhatsApp API error: {r.status_code} - {r.text}")
            else:
                logger.info(f"Mensaje enviado correctamente a {payload.get('to')}")
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
