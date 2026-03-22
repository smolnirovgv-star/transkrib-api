"""
Модуль проверки лицензионных ключей Transkrib.

Лицензия проверяется офлайн через HMAC-подпись, встроенную в ключ.
Активированный ключ сохраняется как JSON в license.key в APP_DATA_DIR.

Формат ключа: TRSK-{PLAN}-{XXXX}-{XXXX}-{HMAC8}
  PLAN: BASE (10 дней) | STND (30 дней) | PREM (365 дней)
  HMAC вычисляется от PLAN+part1+part2 (12 символов)
"""

import hmac
import json
import hashlib
import base64
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple

logger = logging.getLogger("video_processor.license")

# PRODUCTION SECRET KEY - KEEP SECURE!
# Криптографически стойкий 64-байтовый ключ для HMAC подписи
# ВАЖНО: Должен совпадать с tools/keygen.py
SECRET_KEY = bytes.fromhex(
    "7c3f9a2e8d1b4f6c5a9e3d7f1c8b2a6e"
    "4d9c7f3a1e5b8d2c6f9a4e7c3d1b5a8f"
    "2e6c9d4f7a3b1e8c5d2f6a9b4e7c3d1f"
    "8a5c3e9f2d6b1a7c4e8d3f9b2c6a5e1d"
)

# План → количество дней лицензии
PLAN_DAYS = {
    "BASE": 10,
    "STND": 30,
    "PREM": 365,
}


class LicenseManager:
    """Менеджер лицензий с офлайн проверкой через HMAC."""

    def __init__(self, data_dir: Path):
        """
        Args:
            data_dir: Папка для хранения license.key (обычно AppData/Transkrib/.license)
        """
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.license_file = self.data_dir / "license.key"

    def verify_key_signature(self, key: str) -> bool:
        """
        Проверяет HMAC подпись ключа (офлайн проверка).

        Формат: TRSK-{PLAN}-{XXXX}-{XXXX}-{HMAC8}
        где HMAC8 — подпись от PLAN+part1+part2 (12 символов).
        """
        if not key.startswith("TRSK-"):
            return False

        parts = key.replace("TRSK-", "").split("-")
        if len(parts) != 4:
            return False

        # Данные для подписи — первые 3 части (PLAN + 2 random groups)
        data = "".join(parts[:3])
        signature = parts[3]

        # Вычисляем ожидаемую подпись
        h = hmac.new(SECRET_KEY, data.encode(), hashlib.sha256)
        digest = h.digest()
        expected_sig = base64.b32encode(digest[:5]).decode().rstrip("=")[:8]

        return hmac.compare_digest(signature, expected_sig)

    def _parse_plan(self, key: str) -> Tuple[str, int]:
        """
        Извлекает план и срок действия из ключа.

        Returns:
            (plan_code, days) — например ('BASE', 10)
        """
        parts = key.replace("TRSK-", "").split("-")
        plan = parts[0] if parts else "BASE"
        days = PLAN_DAYS.get(plan, 10)
        return plan, days

    def _read_license_data(self) -> dict | None:
        """Читает license.key как JSON. Возвращает None если файл не существует или повреждён."""
        if not self.license_file.exists():
            return None

        try:
            content = self.license_file.read_text(encoding="utf-8").strip()
            # Сначала пробуем JSON (новый формат)
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"License file read error: {e}")
            return None

        # Старый текстовый формат — миграция при следующей активации
        return None

    def is_licensed(self) -> Tuple[bool, str]:
        """
        Проверяет, активирована ли лицензия и не истёк ли срок.

        Returns:
            (is_licensed, message)
        """
        data = self._read_license_data()
        if data is None:
            return False, "License key not found. Please activate."

        key = data.get("key", "")
        if not key:
            return False, "License data corrupted."

        # Проверяем подпись
        if not self.verify_key_signature(key):
            return False, "Invalid license key signature."

        # Проверяем срок действия
        activated_str = data.get("activated", "")
        days = data.get("days", 0)
        if activated_str and days:
            try:
                activated = datetime.fromisoformat(activated_str)
                elapsed = (datetime.now() - activated).days
                if elapsed >= days:
                    return False, f"License expired ({elapsed} / {days} days used)."
            except Exception:
                pass  # если дата повреждена — пускаем (консервативно)

        logger.info(f"License verified: {key[:15]}...")
        return True, f"Licensed: {key}"

    def activate(self, key: str) -> Tuple[bool, str]:
        """
        Активирует лицензию — проверяет подпись и сохраняет JSON.

        Args:
            key: Лицензионный ключ (TRSK-PLAN-XXXX-XXXX-XXXX)

        Returns:
            (success, message)
        """
        key = key.strip().upper()

        # Проверяем подпись
        if not self.verify_key_signature(key):
            return False, "Invalid license key."

        # Определяем план и срок
        plan, days = self._parse_plan(key)

        # Сохраняем как JSON
        try:
            data = {
                "key": key,
                "activated": datetime.now().isoformat(),
                "days": days,
                "plan": plan,
            }
            self.license_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info(f"License activated: {key[:15]}... plan={plan} days={days}")
            return True, f"License activated successfully. Plan: {plan} ({days} days)."

        except Exception as e:
            logger.error(f"License activation error: {e}")
            return False, f"Activation failed: {e}"

    def deactivate(self):
        """Удаляет лицензионный ключ (деактивация)."""
        if self.license_file.exists():
            self.license_file.unlink()
            logger.info("License deactivated")

    def get_license_info(self) -> dict:
        """Возвращает информацию о лицензии для API."""
        is_licensed, message = self.is_licensed()

        if is_licensed:
            data = self._read_license_data() or {}
            key = data.get("key", "")
            days = data.get("days", 0)
            plan = data.get("plan", "")
            activated_str = data.get("activated", "")

            days_remaining = 0
            if activated_str and days:
                try:
                    activated = datetime.fromisoformat(activated_str)
                    elapsed = (datetime.now() - activated).days
                    days_remaining = max(0, days - elapsed)
                except Exception:
                    pass

            return {
                "licensed": True,
                "key": key[:15] + "..." if len(key) > 15 else key,
                "message": "License active",
                "plan": plan,
                "days_remaining": days_remaining,
            }
        else:
            return {
                "licensed": False,
                "key": None,
                "message": message,
            }
