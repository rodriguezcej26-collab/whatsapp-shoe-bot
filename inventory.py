import os
import base64
import json
import logging
import anthropic
import gspread
from google.oauth2.service_account import Credentials
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Inventario Calzado")
WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "inventario")


def get_sheet_client():
    """Connect to Google Sheets using service account"""
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/google_service_account.json")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client


def get_all_products() -> list[dict]:
    """Fetch all products from Google Sheets"""
    try:
        client = get_sheet_client()
        sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
        records = sheet.get_all_records()
        logger.info(f"Inventario cargado: {len(records)} productos")
        return records
    except Exception as e:
        logger.error(f"Error leyendo Google Sheets: {e}")
        return []


def similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def search_by_text(query: str) -> list[dict]:
    """
    Search inventory by text query.
    Uses Claude to understand the query and match products.
    """
    products = get_all_products()
    if not products:
        return []

    # Build product catalog string for Claude
    catalog = "\n".join([
        f"- Ref:{p.get('referencia')} | Nombre:{p.get('nombre')} | Color:{p.get('color')} | "
        f"Tallas:{p.get('tallas_disponibles')} | Cantidad:{p.get('cantidad')}"
        for p in products
    ])

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""Eres el asistente de una tienda de calzado. El cliente busca: "{query}"

Inventario disponible:
{catalog}

Tu tarea: identifica cuál producto del inventario coincide mejor con lo que busca el cliente.
Considera el nombre, color, y talla si la menciona.

Responde SOLO con el JSON de los campos del producto más relevante, así:
{{"referencia": "...", "coincidencia": true/false}}

Si no hay ninguna coincidencia razonable, responde: {{"coincidencia": false}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(response.content[0].text.strip())

        if result.get("coincidencia") and result.get("referencia"):
            ref = result["referencia"]
            matched = [p for p in products if str(p.get("referencia")) == str(ref)]
            return matched if matched else []

        return []

    except Exception as e:
        logger.error(f"Error en búsqueda por texto: {e}")
        # Fallback: simple string matching
        query_lower = query.lower()
        matches = []
        for p in products:
            name_sim = similarity(query_lower, str(p.get("nombre", "")))
            color_mentioned = str(p.get("color", "")).lower() in query_lower
            if name_sim > 0.4 or color_mentioned:
                matches.append((p, name_sim))
        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:3]]


async def search_by_image(image_bytes: bytes) -> list[dict]:
    """
    Search inventory by image using Claude Vision.
    Analyzes the image and matches against inventory.
    """
    products = get_all_products()
    if not products:
        return []

    catalog = "\n".join([
        f"- Ref:{p.get('referencia')} | Nombre:{p.get('nombre')} | Color:{p.get('color')} | "
        f"Tallas:{p.get('tallas_disponibles')} | Cantidad:{p.get('cantidad')}"
        for p in products
    ])

    # Encode image to base64
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": f"""Eres el asistente de una tienda de calzado.
El cliente te envió esta foto de un zapato que busca.

Analiza la imagen y describe:
1. Tipo de calzado (tenis, botas, sandalias, etc.)
2. Color principal
3. Posible marca o estilo si es visible

Luego compara con este inventario y encuentra el más similar:
{catalog}

Responde SOLO con JSON:
{{"referencia": "REF_DEL_PRODUCTO", "coincidencia": true/false, "descripcion_imagen": "descripción breve"}}

Si no hay coincidencia: {{"coincidencia": false, "descripcion_imagen": "descripción breve"}}"""
                    }
                ]
            }]
        )

        result = json.loads(response.content[0].text.strip())
        logger.info(f"Análisis de imagen: {result}")

        if result.get("coincidencia") and result.get("referencia"):
            ref = result["referencia"]
            matched = [p for p in products if str(p.get("referencia")) == str(ref)]
            return matched if matched else []

        return []

    except Exception as e:
        logger.error(f"Error en búsqueda por imagen: {e}")
        return []


async def find_similar_products(product: dict) -> list[dict]:
    """Find similar products when a product is out of stock"""
    all_products = get_all_products()

    target_name = str(product.get("nombre", "")).lower()
    target_color = str(product.get("color", "")).lower()
    target_ref = str(product.get("referencia", ""))

    similar = []
    for p in all_products:
        # Skip the same product and out-of-stock items
        if str(p.get("referencia")) == target_ref:
            continue
        if int(p.get("cantidad", 0)) <= 0:
            continue

        name_sim = similarity(target_name, str(p.get("nombre", "")))
        color_sim = similarity(target_color, str(p.get("color", "")))
        score = (name_sim * 0.7) + (color_sim * 0.3)

        if score > 0.35:
            similar.append((p, score))

    similar.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in similar[:3]]
