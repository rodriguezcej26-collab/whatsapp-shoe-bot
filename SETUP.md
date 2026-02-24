# 🚀 Guía de Configuración - WhatsApp Shoe Bot

## Requisitos previos
- Cuenta en Meta for Developers
- Cuenta de Google (para Sheets)
- Cuenta en Render.com
- API Key de Anthropic (claude.ai/settings)

---

## PASO 1 — Configurar Google Sheets

### 1.1 Crear la hoja de cálculo
1. Ve a sheets.google.com y crea una hoja nueva
2. Nómbrala exactamente: **Inventario Calzado**
3. Crea una pestaña llamada **inventario**
4. Agrega estas columnas en la fila 1:

| referencia | nombre | color | tallas_disponibles | cantidad | foto_url | url_compra |
|---|---|---|---|---|---|---|
| ZAP-001 | Nike Air Max 90 | Blanco | 38,39,40,41,42 | 10 | https://... | https://... |
| ZAP-002 | Adidas Stan Smith | Verde | 37,38,39,40 | 5 | https://... | https://... |

> ⚠️ Los nombres de columna deben ser EXACTAMENTE como arriba

### 1.2 Crear Service Account de Google
1. Ve a console.cloud.google.com
2. Crea un proyecto nuevo (o usa uno existente)
3. Busca "Google Sheets API" → habilítala
4. Ve a "Credenciales" → "Crear credenciales" → "Cuenta de servicio"
5. Ponle un nombre, haz clic en "Crear"
6. En "Roles" selecciona "Editor" → continuar → listo
7. Haz clic en la cuenta de servicio creada → pestaña "Claves"
8. "Agregar clave" → "Crear nueva clave" → JSON → Descargar
9. Guarda el archivo JSON como `credentials/google_service_account.json`

### 1.3 Compartir la hoja con el Service Account
1. Abre el archivo JSON que descargaste
2. Copia el campo `"client_email"` (algo como `nombre@proyecto.iam.gserviceaccount.com`)
3. En tu Google Sheet → botón "Compartir"
4. Pega ese email → rol "Lector" → Compartir

---

## PASO 2 — Configurar Meta / WhatsApp Business API

### 2.1 Crear cuenta de desarrollador
1. Ve a developers.facebook.com
2. Inicia sesión con tu cuenta de Facebook
3. "Mis apps" → "Crear app"
4. Tipo: **Empresa** → Siguiente
5. Ponle nombre a tu app → Crear

### 2.2 Agregar WhatsApp
1. En el dashboard de tu app → "Agregar productos"
2. Busca **WhatsApp** → "Configurar"
3. Sigue el asistente para conectar tu cuenta de WhatsApp Business

### 2.3 Obtener credenciales
En la sección WhatsApp → Configuración de la API:
- **Access Token temporal** (para pruebas) → cópialo
- **Phone Number ID** → cópialo

> 💡 El token temporal dura 24h. Para producción necesitas un token permanente.

### 2.4 Agregar número de prueba
Meta te da un número sandbox para testear.
- Agrega tu número personal como destinatario autorizado
- Puedes enviarle mensajes desde WhatsApp normal al número sandbox

---

## PASO 3 — Desplegar en Render

### 3.1 Subir código a GitHub
```bash
git init
git add .
git commit -m "WhatsApp Shoe Bot inicial"
git remote add origin https://github.com/tu-usuario/whatsapp-shoe-bot.git
git push -u origin main
```

### 3.2 Crear servicio en Render
1. Ve a render.com → "New Web Service"
2. Conecta tu repositorio de GitHub
3. Render detecta automáticamente el `render.yaml`
4. En "Environment Variables" agrega:
   - `WHATSAPP_ACCESS_TOKEN` = tu token de Meta
   - `WHATSAPP_PHONE_NUMBER_ID` = tu phone ID de Meta
   - `WHATSAPP_VERIFY_TOKEN` = cualquier texto secreto (ej: `mi_bot_zapatos_2024`)
   - `ANTHROPIC_API_KEY` = tu key de Anthropic
5. Para `google_service_account.json`: en Render → "Secret Files" → sube el archivo como `credentials/google_service_account.json`
6. Deploy!

### 3.3 Obtener la URL de tu bot
Render te dará una URL tipo: `https://whatsapp-shoe-bot.onrender.com`

---

## PASO 4 — Configurar el Webhook en Meta

1. En Meta for Developers → tu app → WhatsApp → Configuración
2. En "Webhooks" → "Editar"
3. **URL del webhook**: `https://whatsapp-shoe-bot.onrender.com/webhook`
4. **Token de verificación**: el mismo que pusiste en `WHATSAPP_VERIFY_TOKEN`
5. "Verificar y guardar"
6. Suscríbete a estos eventos: `messages`

---

## PASO 5 — ¡Probar!

1. Desde tu WhatsApp personal escríbele al número sandbox de Meta
2. Prueba:
   - ✍️ "Busco unas Nike blancas talla 40"
   - 📸 Envía una foto de un zapato
3. El bot debería responder con disponibilidad

---

## Estructura del proyecto

```
whatsapp-shoe-bot/
├── app/
│   ├── main.py          # FastAPI + manejo de webhooks
│   ├── whatsapp.py      # Envío de mensajes WhatsApp
│   └── inventory.py     # Búsqueda en Google Sheets + Claude Vision
├── credentials/
│   └── google_service_account.json  # (no subir a GitHub!)
├── .env.example         # Template de variables de entorno
├── requirements.txt     # Dependencias Python
├── render.yaml          # Configuración de Render
└── SETUP.md             # Esta guía
```

---

## Solución de problemas

**El webhook no verifica:**
→ Asegúrate que el `WHATSAPP_VERIFY_TOKEN` sea idéntico en Meta y en tus variables de entorno

**No lee el Google Sheet:**
→ Verifica que el email del service account tenga acceso a la hoja

**No analiza imágenes:**
→ Verifica que `ANTHROPIC_API_KEY` sea válida y tenga saldo

**El bot no responde:**
→ Revisa los logs en Render → tu servicio → "Logs"

---

## Costos estimados (mes)

| Servicio | Costo |
|---|---|
| Render (Free tier) | $0 |
| WhatsApp API (hasta 1000 conversaciones/mes) | $0 |
| Claude Haiku (miles de consultas) | ~$1-5 |
| **Total** | **Prácticamente $0** |
