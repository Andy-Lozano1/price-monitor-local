import argparse
import json
import os
import re
import smtplib
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


DEFAULT_STATE_FILE = "monitor_state.json"
DEFAULT_PRODUCTS_FILE = "products.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class MonitorConfig:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        base = config or {}
        self.monitor_interval_seconds = int(base.get("monitor_interval_seconds", 300))
        self.email = base.get("email", {})
        self.products = base.get("products", [])


class ProductMonitor:
    def __init__(self, products: List[Dict[str, Any]], state_file: str = DEFAULT_STATE_FILE, demo_mode: bool = False):
        self.products = products
        self.state_file = Path(state_file)
        self.demo_mode = demo_mode
        self.state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            return {"last_checked": None, "products": {}}
        try:
            with self.state_file.open("r", encoding="utf-8") as archivo:
                return json.load(archivo)
        except Exception:
            return {"last_checked": None, "products": {}}

    def _save_state(self):
        self.state["last_checked"] = now_iso()
        with self.state_file.open("w", encoding="utf-8") as archivo:
            json.dump(self.state, archivo, ensure_ascii=False, indent=2)

    def _send_alert_email(self, message: str, product_name: str) -> None:
        email_cfg = self.email_config or {}
        if not email_cfg.get("enabled"):
            return

        sender = email_cfg.get("sender")
        password = email_cfg.get("password")
        recipient = email_cfg.get("recipient")
        smtp_server = email_cfg.get("smtp_server")
        smtp_port = int(email_cfg.get("smtp_port", 587))

        if not all([sender, password, recipient, smtp_server]):
            print("[alerta] Email configurado incompleto. Revisa sender/password/recipient/smtp_server.")
            return

        try:
            msg = EmailMessage()
            msg["Subject"] = f"Alerta de monitoreo: {product_name}"
            msg["From"] = sender
            msg["To"] = recipient
            msg.set_content(message)

            with smtplib.SMTP(smtp_server, smtp_port) as servidor:
                servidor.starttls()
                servidor.login(sender, password)
                servidor.send_message(msg)
            print("[alerta] Correo de notificación enviado.")
        except Exception as exc:  # pragma: no cover
            print(f"[alerta] No se pudo enviar el email: {exc}")

    def _send_alert_telegram(self, message: str, product_name: str) -> None:
        telegram_cfg = self.telegram_config or {}
        if not telegram_cfg.get("enabled"):
            return

        token = telegram_cfg.get("token")
        chat_id = telegram_cfg.get("chat_id")
        if not token or not chat_id:
            print("[alerta] Telegram configurado incompleto. Revisa token y chat_id.")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": f"[{product_name}]\n{message}", "disable_web_page_preview": True}

        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code == 200:
                print("[alerta] Notificación por Telegram enviada.")
            else:
                print(f"[alerta] Telegram respondió con código {response.status_code}: {response.text}")
        except Exception as exc:  # pragma: no cover
            print(f"[alerta] No se pudo enviar la alerta por Telegram: {exc}")

    def set_email_config(self, email_config: Dict[str, Any]):
        self.email_config = email_config

    def set_telegram_config(self, telegram_config: Dict[str, Any]):
        self.telegram_config = telegram_config

    @staticmethod
    def _parse_price(value: str) -> Optional[float]:
        if value is None:
            return None
        cleaned = re.sub(r"[^0-9,\.\-]", "", value)
        if not cleaned:
            return None
        if cleaned.count(",") and cleaned.count("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif cleaned.count(",") == 1 and cleaned.count(".") == 0:
            cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _request_page(self, url: str) -> Dict[str, Any]:
        if self.demo_mode:
            return {"status_code": 200, "text": "<html><body>demo</body></html>"}

        try:
            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    "Accept-Language": "es-ES,es;q=0.9",
                },
            )
            return {"status_code": response.status_code, "text": response.text}
        except Exception as exc:
            return {"status_code": 0, "text": f"Error de conexión: {exc}"}

    def _extract_text(self, page_html: str) -> str:
        return re.sub(r"<[^>]+>", " ", page_html, flags=re.IGNORECASE | re.MULTILINE)

    def _active_price(self, product: Dict[str, Any], page_html: str) -> Optional[float]:
        selector = product.get("price_selector")
        if selector:
            try:
                re.search(rf"{re.escape(selector)}", page_html, re.IGNORECASE)
            except Exception:
                pass

        plain = self._extract_text(page_html)
        text = plain.lower()
        url = (product.get("url") or "").lower()

        candidate_matches: List[str] = []
        if "amazon" in url:
            candidate_matches.extend(re.findall(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text))
            candidate_matches.extend(re.findall(r"\b(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*usd\b", text))

        matches = re.findall(r"(?:\$|usd|eur|mxn)?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)", text)
        candidate_matches.extend(matches)

        prices = []
        for value in candidate_matches:
            parsed = self._parse_price(value)
            if parsed is not None:
                prices.append(parsed)

        if not prices:
            return None

        # Amazon search pages usually include a few numbers; prefer the most likely product price via the largest value under a reasonable threshold.
        if "amazon" in url:
            real_prices = [p for p in prices if p > 20]
            if real_prices:
                return max(real_prices)
        return max(prices)

    def _availability_flag(self, product: Dict[str, Any], page_html: str) -> Optional[bool]:
        text = self._extract_text(page_html).lower()
        in_stock_terms = product.get("in_stock_terms", ["in stock", "available", "disponible", "en existencia", "en stock", "add to cart", "comprar"])
        out_of_stock_terms = product.get("out_of_stock_terms", ["out of stock", "agotado", "sold out", "sin stock", "unavailable", "currently unavailable", "temporarily unavailable", "not available"])

        if "amazon" in (product.get("url") or "").lower():
            in_stock_terms = in_stock_terms + ["in stock", "available", "add to cart", "buy now", "currently in stock"]
            out_of_stock_terms = out_of_stock_terms + ["currently unavailable", "out of stock", "unavailable", "temporarily unavailable"]

        has_in = any(term.lower() in text for term in in_stock_terms)
        has_out = any(term.lower() in text for term in out_of_stock_terms)

        if has_in and not has_out:
            return True
        if has_out and not has_in:
            return False
        if has_in and has_out:
            return True
        return None

    def _demo_snapshot(self, product: Dict[str, Any]) -> Dict[str, Any]:
        target_price = float(product.get("target_price", 100.0))
        base = float(product.get("base_price", target_price))
        price = round(base + (time.time() % 17) * 3.5, 2)
        price = min(price, target_price * 1.25)
        available = bool(int(time.time() // 8) % 2 == 0)
        return {"price": price, "available": available, "source": "demo"}

    def check_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        product_name = product.get("name", "Producto")
        url = product.get("url", "")

        if self.demo_mode:
            snapshot = self._demo_snapshot(product)
        else:
            response = self._request_page(url)
            if response["status_code"] != 200:
                return {
                    "name": product_name,
                    "url": url,
                    "price": None,
                    "available": None,
                    "error": response.get("text", "Sin respuesta"),
                }

            page_html = response["text"]
            price = self._active_price(product, page_html)
            available = self._availability_flag(product, page_html)
            snapshot = {"price": price, "available": available, "source": url}

        snapshot["name"] = product_name
        snapshot["url"] = url
        snapshot["checked_at"] = now_iso()
        return snapshot

    def _should_alert(self, product: Dict[str, Any], snapshot: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> List[str]:
        alerts: List[str] = []
        if snapshot.get("price") is None:
            return alerts

        if previous is None:
            alerts.append("estado inicial registrado")
            return alerts

        prev_price = previous.get("price")
        prev_available = previous.get("available")
        new_price = snapshot.get("price")
        new_available = snapshot.get("available")

        if prev_available is not None and new_available is not None and prev_available != new_available:
            status = "disponible" if new_available else "sin stock"
            alerts.append(f"cambio de disponibilidad: {status}")

        target_price = float(product.get("target_price", 0) or 0)
        if target_price and new_price <= target_price:
            alerts.append(f"precio por debajo del objetivo (${target_price:,.2f})")

        if prev_price is not None:
            delta = ((new_price - prev_price) / prev_price) * 100 if prev_price else 0
            threshold = float(product.get("price_drop_threshold_percent", 5.0) or 0)
            if delta <= -threshold:
                alerts.append(f"caída de precio: {delta:.2f}%")

        return alerts

    def run_once(self) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for product in self.products:
            snapshot = self.check_product(product)
            previous = self.state["products"].get(product.get("id") or product.get("name"))
            alerts = self._should_alert(product, snapshot, previous)

            if alerts:
                message = (
                    f"[{snapshot['name']}] {', '.join(alerts)} | "
                    f"precio: ${snapshot.get('price') if snapshot.get('price') is not None else 'N/A'} | "
                    f"disponible: {'Sí' if snapshot.get('available') is True else 'No' if snapshot.get('available') is False else 'Desconocido'}"
                )
                print(f"\n[ALERTA] {message}")
                self._send_alert_email(message, snapshot["name"])
                self._send_alert_telegram(message, snapshot["name"])

            self.state["products"][product.get("id") or product.get("name")] = snapshot
            results.append(snapshot)

        self._save_state()
        return {"checked_at": now_iso(), "results": results}

    def run_forever(self, interval_seconds: Optional[int] = None):
        interval = interval_seconds or self.monitor_interval_seconds
        print(f"[monitor] Iniciado. Intervalo: {interval} segundos")
        while True:
            self.run_once()
            time.sleep(interval)


def load_products_from_file(path: str) -> List[Dict[str, Any]]:
    config_file = Path(path)
    if not config_file.exists():
        return []
    try:
        with config_file.open("r", encoding="utf-8") as archivo:
            data = json.load(archivo)
        return data.get("products", []) if isinstance(data, dict) else data
    except Exception as exc:
        print(f"[config] No se pudo cargar {path}: {exc}")
        return []


def build_demo_products() -> List[Dict[str, Any]]:
    return [
        {
            "id": "laptop-pro",
            "name": "Laptop Pro 14",
            "url": "https://example.com/laptop-pro",
            "target_price": 1200.0,
            "price_drop_threshold_percent": 8.0,
            "base_price": 1350.0,
            "in_stock_terms": ["in stock", "available", "disponible", "en existencia"],
            "out_of_stock_terms": ["out of stock", "agotado", "sold out", "sin stock", "unavailable"],
        },
        {
            "id": "airbuds",
            "name": "Airbuds Max",
            "url": "https://example.com/airbuds-max",
            "target_price": 220.0,
            "price_drop_threshold_percent": 12.0,
            "base_price": 280.0,
            "in_stock_terms": ["in stock", "available", "disponible", "en existencia"],
            "out_of_stock_terms": ["out of stock", "agotado", "sold out", "sin stock", "unavailable"],
        },
    ]


def main():
    parser = argparse.ArgumentParser(description="Sistema automatizado de alertas y monitoreo de precios/disponibilidad.")
    parser.add_argument("--config", default=DEFAULT_PRODUCTS_FILE, help="Ruta del archivo JSON con la lista de productos.")
    parser.add_argument("--demo", action="store_true", help="Usa un modo de demostración sin depender de APIs reales.")
    parser.add_argument("--once", action="store_true", help="Ejecuta una sola verificación y termina.")
    parser.add_argument("--interval", type=int, default=300, help="Intervalo de recolección en segundos.")
    parser.add_argument("--smtp-server", default=None, help="Servidor SMTP para alertas por correo.")
    parser.add_argument("--smtp-port", type=int, default=587, help="Puerto SMTP.")
    parser.add_argument("--smtp-user", default=None, help="Usuario SMTP.")
    parser.add_argument("--smtp-password", default=None, help="Contraseña SMTP.")
    parser.add_argument("--mail-to", default=None, help="Correo del destinatario.")
    parser.add_argument("--telegram-token", default=None, help="Token del bot de Telegram para alertas.")
    parser.add_argument("--telegram-chat-id", default=None, help="Chat ID de Telegram para recibir alertas.")
    args = parser.parse_args()

    products = []
    if args.config and Path(args.config).exists():
        products = load_products_from_file(args.config)
    if not products or args.demo:
        products = build_demo_products()

    email_config = {
        "enabled": bool(args.smtp_server and args.smtp_user and args.smtp_password and args.mail_to),
        "smtp_server": args.smtp_server,
        "smtp_port": args.smtp_port,
        "sender": args.smtp_user,
        "password": args.smtp_password,
        "recipient": args.mail_to,
    }

    telegram_config = {
        "enabled": bool(args.telegram_token and args.telegram_chat_id),
        "token": args.telegram_token,
        "chat_id": args.telegram_chat_id,
    }

    monitor = ProductMonitor(products, demo_mode=args.demo)
    monitor.set_email_config(email_config)
    monitor.set_telegram_config(telegram_config)

    print("=========================================")
    print("  SISTEMA DE ALERTAS Y MONITOREO")
    print("  Precios + Disponibilidad")
    print("=========================================")

    if args.once:
        result = monitor.run_once()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    monitor.run_forever(interval_seconds=args.interval)


if __name__ == "__main__":
    main()

