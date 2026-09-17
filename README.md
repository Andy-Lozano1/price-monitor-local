# Price Monitor Local

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Telegram](https://img.shields.io/badge/Alerts-Telegram-26A5E4)

Sistema automatizado para monitorear precios y disponibilidad de productos, con alertas por Telegram y una interfaz web local para consultar el estado en tiempo real.

## Descripción

Este proyecto permite:

- monitorear productos con alertas automáticas
- detectar cambios de precio y disponibilidad
- enviar notificaciones a Telegram
- consultar el estado desde un dashboard local
- probar el funcionamiento con un modo demo

Es una base útil para crear un monitor de compras, alertas de stock, o seguimiento de ofertas en tiendas online.

## Stack

- Python 3.10+
- Requests
- Telegram Bot API
- HTML + JavaScript para el dashboard local

## Estructura del proyecto

```text
monitor-precios/
├── app.py
├── dashboard.py
├── products.json
├── requirements.txt
├── README.md
├── .gitignore
├── LICENSE
├── CHANGELOG.md
├── .github/
│   └── workflows/
│       └── python-app.yml
└── monitor_state.json
```

## Requisitos

- Python 3.10 o superior
- pip
- Acceso a Internet para consultar páginas o probar en modo demo

## Instalación

### 1) Clonar o descargar el proyecto

```bash
git clone https://github.com/Andy-Lozano1/price-monitor-local.git
cd price-monitor-local
```

### 2) Crear entorno virtual

En Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Instalar dependencias

```bash
pip install -r requirements.txt
```

## Uso

### Modo demo

Ejecuta una verificación rápida sin depender de tiendas reales:

```powershell
python app.py --demo --once --telegram-token TU_TOKEN --telegram-chat-id TU_CHAT_ID
```

### Monitor continuo

Ejecuta el monitor cada 300 segundos:

```powershell
python app.py --interval 300 --telegram-token TU_TOKEN --telegram-chat-id TU_CHAT_ID
```

### Dashboard local

Lanza la interfaz web:

```powershell
python dashboard.py
```

Abre en el navegador:

```text
http://localhost:8000
```

## Configuración de Telegram

1. Busca en Telegram a `@BotFather`.
2. Ejecuta el comando:

```text
/newbot
```

3. Siga las instrucciones para crear el bot.
4. Copia el token generado por Telegram.
5. Inicia un chat con tu bot y envía `/start`.
6. Abre esta URL en el navegador:

```text
https://api.telegram.org/botTU_TOKEN/getUpdates
```

7. Busca el campo `chat.id` dentro del JSON para obtener tu identificador de chat.

## Configuración de productos

El archivo [products.json](products.json) contiene la lista de productos a monitorear. Un ejemplo:

```json
{
  "products": [
    {
      "id": "airpods-pro-2",
      "name": "AirPods Pro 2",
      "url": "https://www.amazon.com/s?k=AirPods+Pro+2",
      "target_price": 180,
      "price_drop_threshold_percent": 12,
      "base_price": 250
    }
  ]
}
```

Puede personalizarse con tus propios productos y objetivos de precio.

## Cómo funciona

- La app revisa cada producto según el intervalo configurado.
- Compara el precio actual con el objetivo y con el último valor registrado.
- Detecta cambios de disponibilidad.
- Si ocurre una alerta, envía un mensaje a Telegram y guarda el estado local.

## Limitaciones

Para sitios reales, a menudo es necesario ajustar:

- la URL
- los términos de disponibilidad
- los selectores o patrones de extracción de precio
- el manejo de asincronía o cambios de markup del sitio

Esto es normal porque cada tienda tiene un HTML y estructuras diferentes.

## License

Este proyecto está bajo la licencia MIT. Consulta [LICENSE](LICENSE) para más detalles.

## Changelog

Consulta [CHANGELOG.md](CHANGELOG.md) para ver el historial de cambios.

## Repositorio GitHub

```bash
git add .
git commit -m "Actualización del monitor"
git push origin main
```

## Contacto

Si quieres extender este proyecto con:

- scraping real para Amazon o Mercado Libre
- historial de precios
- dashboard con gráficos
- alertas por email o WhatsApp

se puede continuar desde esta base.
