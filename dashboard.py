import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE_FILE = Path("monitor_state.json")


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api"):
            self._serve_api()
            return

        self._serve_html()

    def _serve_api(self):
        payload = {"last_checked": None, "products": []}
        if STATE_FILE.exists():
            try:
                with STATE_FILE.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                payload = {"last_checked": None, "products": []}

        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self):
        html = """
        <!doctype html>
        <html lang="es">
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Monitor de Precios</title>
            <style>
                body { font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }
                h1 { margin-bottom: 16px; }
                .card { background: #111827; border: 1px solid #334155; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
                .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
                .product { background: #1f2937; border: 1px solid #475569; border-radius: 10px; padding: 16px; }
                .status { font-weight: bold; }
                .ok { color: #4ade80; }
                .bad { color: #f87171; }
                .warn { color: #fbbf24; }
                .small { color: #94a3b8; font-size: 12px; }
                button { background: #2563eb; color: white; border: none; border-radius: 8px; padding: 10px 16px; cursor: pointer; }
            </style>
        </head>
        <body>
            <h1>Monitor de Precios y Disponibilidad</h1>
            <div class="card">
                <p><strong>Última verificación:</strong> <span id="lastChecked">Cargando...</span></p>
                <button onclick="loadData()">Actualizar</button>
            </div>
            <div id="products" class="grid"></div>

            <script>
                async function loadData() {
                    try {
                        const response = await fetch('/api');
                        const data = await response.json();
                        document.getElementById('lastChecked').textContent = data.last_checked || 'Sin datos';
                        const products = data.products || {};
                        const list = Object.values(products);
                        const container = document.getElementById('products');
                        container.innerHTML = '';

                        if (!list.length) {
                            container.innerHTML = '<div class="card">No hay datos disponibles todavía.</div>';
                            return;
                        }

                        list.forEach(product => {
                            const name = product.name || 'Producto';
                            const price = product.price != null ? '$' + Number(product.price).toLocaleString('es-ES', { maximumFractionDigits: 2 }) : 'N/A';
                            const available = product.available == true ? 'Disponible' : product.available == false ? 'Sin stock' : 'Desconocido';
                            const cls = product.available == true ? 'ok' : product.available == false ? 'bad' : 'warn';
                            const item = document.createElement('div');
                            item.className = 'product';
                            item.innerHTML = `
                                <h3>${name}</h3>
                                <p><strong>Precio:</strong> ${price}</p>
                                <p><strong>Disponibilidad:</strong> <span class="status ${cls}">${available}</span></p>
                                <p class="small">Verificado: ${product.checked_at || 'N/A'}</p>
                                <p class="small">Fuente: ${product.source || 'N/A'}</p>
                            `;
                            container.appendChild(item);
                        });
                    } catch (error) {
                        document.getElementById('products').innerHTML = '<div class="card">Error al cargar la información.</div>';
                    }
                }
                loadData();
                setInterval(loadData, 30000);
            </script>
        </body>
        </html>
        """
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8000), DashboardHandler)
    print("[dashboard] Ejecutando en http://localhost:8000")
    server.serve_forever()
