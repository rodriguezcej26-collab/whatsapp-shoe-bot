import os
import json
import httpx
import base64
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from app.inventory import search_by_text, search_by_image, find_similar_products
from app.whatsapp import send_text_message, send_image_message, send_cta_url_message

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Shoe Store WhatsApp Bot")

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mi_token_secreto")


@app.get("/webhook")
async def verify_webhook(request: Request):
    """WhatsApp webhook verification"""
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verificado correctamente")
        return PlainTextResponse(content=challenge)

    raise HTTPException(status_code=403, detail="Token inválido")


@app.post("/webhook")
async def receive_message(request: Request):
    """Receive and process WhatsApp messages"""
    try:
        body = await request.json()
        logger.info(f"Mensaje recibido: {json.dumps(body, indent=2)}")

        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "ok"}

        message = messages[0]
        from_number = message.get("from")
        msg_type = message.get("type")

        if msg_type == "text":
            user_text = message["text"]["body"]
            await handle_text_message(from_number, user_text)

        elif msg_type == "image":
            image_id = message["image"]["id"]
            await handle_image_message(from_number, image_id)

        else:
            await send_text_message(
                from_number,
                "Hola! 👟 Puedes escribirme el nombre o modelo del zapato que buscas, o enviarme una foto. ¡Te ayudo a encontrarlo!"
            )

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")
        return {"status": "error", "detail": str(e)}


async def handle_text_message(phone: str, text: str):
    """Handle text-based product search"""
    await send_text_message(phone, "🔍 Buscando en nuestro inventario...")

    results = await search_by_text(text)

    if results:
        product = results[0]
        await send_product_response(phone, product)
    else:
        await send_text_message(
            phone,
            "😕 No encontré ese modelo exacto. ¿Puedes darme más detalles o enviarme una foto del zapato que buscas?"
        )


async def handle_image_message(phone: str, image_id: str):
    """Handle image-based product search"""
    await send_text_message(phone, "📸 Analizando la foto que enviaste...")

    # Download image from WhatsApp
    image_bytes = await download_whatsapp_image(image_id)
    if not image_bytes:
        await send_text_message(phone, "No pude procesar la imagen. ¿Puedes intentar de nuevo?")
        return

    results = await search_by_image(image_bytes)

    if results:
        product = results[0]
        await send_product_response(phone, product)
    else:
        await send_text_message(
            phone,
            "😕 No encontré ese modelo en nuestro inventario. ¿Tienes el nombre o referencia del zapato?"
        )


async def send_product_response(phone: str, product: dict):
    """Send product availability response to user"""
    name = product.get("nombre", "Zapato")
    reference = product.get("referencia", "")
    sizes = product.get("tallas_disponibles", "")
    quantity = int(product.get("cantidad", 0))
    foto_url = product.get("foto_url", "")
    buy_url = product.get("url_compra", "")
    color = product.get("color", "")

    if quantity > 0:
        # Product available
        msg = (
            f"✅ *¡Tenemos este modelo disponible!*\n\n"
            f"👟 *{name}*\n"
            f"🎨 Color: {color}\n"
            f"🔖 Ref: {reference}\n"
            f"📏 Tallas disponibles: {sizes}\n"
            f"📦 Unidades: {quantity}\n\n"
            f"¡Haz tu pedido ahora! 👇"
        )
        await send_text_message(phone, msg)

        if foto_url:
            await send_image_message(phone, foto_url, f"{name} - {color}")

        if buy_url:
            await send_cta_url_message(
                phone,
                "¿Te lo llevo? Haz clic para hacer tu pedido:",
                "🛒 Comprar ahora",
                buy_url
            )
    else:
        # Out of stock — find similar
        msg = (
            f"😕 *{name}* ({color}) está agotado por el momento.\n\n"
            f"Pero mira estos modelos similares que tenemos disponibles:"
        )
        await send_text_message(phone, msg)

        similar = await find_similar_products(product)
        if similar:
            for sim in similar[:2]:
                sim_msg = (
                    f"👟 *{sim['nombre']}*\n"
                    f"🎨 Color: {sim['color']}\n"
                    f"📏 Tallas: {sim['tallas_disponibles']}\n"
                    f"📦 Unidades: {sim['cantidad']}"
                )
                await send_text_message(phone, sim_msg)
                if sim.get("foto_url"):
                    await send_image_message(phone, sim["foto_url"], sim["nombre"])
                if sim.get("url_compra"):
                    await send_cta_url_message(
                        phone,
                        "Ver este modelo:",
                        "🛒 Ver producto",
                        sim["url_compra"]
                    )
        else:
            await send_text_message(phone, "Lo siento, por el momento no tenemos modelos similares disponibles. ¡Pronto habrá nuevas llegadas! 🎉")


async def download_whatsapp_image(image_id: str) -> bytes | None:
    """Download image from WhatsApp media servers"""
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    try:
        async with httpx.AsyncClient() as client:
            # Get media URL
            r = await client.get(
                f"https://graph.facebook.com/v19.0/{image_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            media_url = r.json().get("url")
            if not media_url:
                return None

            # Download image
            r2 = await client.get(media_url, headers={"Authorization": f"Bearer {token}"})
            return r2.content
    except Exception as e:
        logger.error(f"Error descargando imagen: {e}")
        return None


@app.get("/")
async def root():
    return {"status": "running", "service": "WhatsApp Shoe Bot 👟"}
