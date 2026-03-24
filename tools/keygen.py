#!/usr/bin/env python3
"""
Генератор лицензионных ключей для Transkrib.

Использование:
    # Сгенерировать все планы (стандартный запуск):
    python keygen.py --all

    # Конкретный план и количество:
    python keygen.py --plan base --count 50
    python keygen.py --plan std --count 30
    python keygen.py --plan pro --count 15

    # Проверить ключ:
    python keygen.py --verify TRSK-BASE-ABCD-EFGH-HMAC1234

Формат ключа: TRSK-{PLAN}-{XXXX}-{XXXX}-{HMAC8}
  PLAN: BASE (10 дней) | STND (30 дней) | PREM (365 дней)
  HMAC — первые 8 символов base32 от SHA256(PLAN+part1+part2)
"""

import argparse
import hmac
import hashlib
import secrets
import base64
from pathlib import Path
from datetime import datetime

# PRODUCTION SECRET KEY - KEEP SECURE!
# Криптографически стойкий 64-байтовый ключ для HMAC подписи
# ВАЖНО: Должен совпадать с backend/app/license.py
SECRET_KEY = bytes.fromhex(
    "7c3f9a2e8d1b4f6c5a9e3d7f1c8b2a6e"
    "4d9c7f3a1e5b8d2c6f9a4e7c3d1b5a8f"
    "2e6c9d4f7a3b1e8c5d2f6a9b4e7c3d1f"
    "8a5c3e9f2d6b1a7c4e8d3f9b2c6a5e1d"
)

BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

# Маппинг CLI-алиасов → код плана + дни
PLAN_MAP = {
    "base": ("BASE", 10),
    "std":  ("STND", 30),
    "pro":  ("PREM", 365),
}


def random_part(length: int = 4) -> str:
    """Генерирует случайную строку из base32 символов."""
    return "".join(secrets.choice(BASE32_ALPHABET) for _ in range(length))


def compute_hmac(data: str) -> str:
    """Вычисляет HMAC-SHA256 и возвращает 8 символов base32."""
    h = hmac.new(SECRET_KEY, data.encode(), hashlib.sha256)
    digest = h.digest()
    b32 = base64.b32encode(digest[:5]).decode().rstrip("=")
    return b32[:8]


def generate_key(plan_code: str) -> str:
    """
    Генерирует один лицензионный ключ для заданного плана.

    Формат: TRSK-{PLAN}-{XXXX}-{XXXX}-{HMAC8}
    HMAC вычисляется от PLAN+part1+part2.
    """
    part1 = random_part(4)
    part2 = random_part(4)
    data = f"{plan_code}{part1}{part2}"
    signature = compute_hmac(data)
    return f"TRSK-{plan_code}-{part1}-{part2}-{signature}"


def verify_key(key: str) -> bool:
    """Проверяет валидность ключа (для тестирования)."""
    if not key.startswith("TRSK-"):
        return False

    parts = key.replace("TRSK-", "").split("-")
    if len(parts) != 4:
        return False

    data = "".join(parts[:3])
    signature = parts[3]
    expected_sig = compute_hmac(data)
    return hmac.compare_digest(signature, expected_sig)


def generate_plan_keys(
    plan_alias: str,
    count: int,
    output_dir: Path,
    subfolder: str,
) -> list[str]:
    """
    Генерирует ключи для одного плана и сохраняет в подпапку.

    Returns:
        Список сгенерированных ключей.
    """
    plan_code, days = PLAN_MAP[plan_alias]
    plan_dir = output_dir / subfolder
    plan_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = plan_dir / f"keys_{timestamp}.txt"

    keys = []
    for i in range(count):
        key = generate_key(plan_code)
        assert verify_key(key), f"Ошибка генерации ключа {i+1} (план {plan_code})"
        keys.append(key)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# Лицензионные ключи Transkrib — {plan_code} ({days} дней)\n")
        f.write(f"# Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Количество: {count}\n")
        f.write(f"# Срок действия: {days} дней с момента активации\n")
        f.write(f"# Формат: TRSK-{plan_code}-XXXX-XXXX-HMAC8\n\n")
        for key in keys:
            f.write(f"{key}\n")

    # Файл учёта использованных ключей
    used_file = plan_dir / "used.txt"
    if not used_file.exists():
        with open(used_file, "w", encoding="utf-8") as f:
            f.write("# Использованные ключи\n")
            f.write("# Формат: ключ | дата активации | примечание\n\n")

    return keys


def main():
    parser = argparse.ArgumentParser(
        description="Генератор лицензионных ключей Transkrib",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--plan",
        choices=list(PLAN_MAP.keys()),
        help="План: base (10 дней), std (30 дней), pro (365 дней)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Количество ключей (по умолчанию: 10)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./Transkrib_Keys",
        help="Корневая папка для сохранения (по умолчанию: ./Transkrib_Keys)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Сгенерировать все планы: 50 BASE, 30 STND, 15 PREM",
    )
    parser.add_argument(
        "--verify",
        type=str,
        help="Проверить валидность ключа",
    )

    args = parser.parse_args()

    # Режим проверки
    if args.verify:
        is_valid = verify_key(args.verify)
        parts = args.verify.replace("TRSK-", "").split("-")
        plan_code = parts[0] if parts else "?"
        days = {v[0]: v[1] for v in PLAN_MAP.values()}.get(plan_code, "?")
        print(f"Ключ:   {args.verify}")
        print(f"Статус: {'ВАЛИДЕН' if is_valid else 'НЕВАЛИДЕН'}")
        if is_valid:
            print(f"План:   {plan_code} ({days} дней)")
        return

    output_dir = Path(args.output)

    # Генерируем все планы
    if args.all:
        plans = [
            ("base", 50,  "plan_basic"),
            ("std",  30,  "plan_standard"),
            ("pro",  15,  "plan_pro"),
        ]
        total = 0
        for plan_alias, count, subfolder in plans:
            plan_code, days = PLAN_MAP[plan_alias]
            print(f"\nГенерация {count} ключей {plan_code} ({days} дней)...")
            keys = generate_plan_keys(plan_alias, count, output_dir, subfolder)
            total += len(keys)
            print(f"  [OK] {len(keys)} ключей → {output_dir / subfolder}/")
            print(f"  Первые 3: {', '.join(keys[:3])}")

        print(f"\n{'=' * 60}")
        print(f"ИТОГО: {total} ключей в папке {output_dir}/")
        print(f"  plan_basic/    — BASE ({PLAN_MAP['base'][1]} дн., 50 ключей)")
        print(f"  plan_standard/ — STND ({PLAN_MAP['std'][1]} дн., 30 ключей)")
        print(f"  plan_pro/      — PREM ({PLAN_MAP['pro'][1]} дн., 15 ключей)")
        print("=" * 60)
        return

    # Генерируем один план
    if not args.plan:
        parser.error("Укажите --plan или --all")

    plan_code, days = PLAN_MAP[args.plan]
    subfolder = {
        "base": "plan_basic",
        "std":  "plan_standard",
        "pro":  "plan_pro",
    }[args.plan]

    print(f"Генерация {args.count} ключей {plan_code} ({days} дней)...")
    keys = generate_plan_keys(args.plan, args.count, output_dir, subfolder)

    print(f"\n[OK] Успешно создано {args.count} ключей")
    print(f"Папка: {output_dir / subfolder}/")
    print(f"План:  {plan_code} ({days} дней с момента активации)")
    print(f"\nПервые 3 ключа:")
    for i, key in enumerate(keys[:3], 1):
        print(f"  {i}. {key}")
    if len(keys) > 3:
        print(f"  ... и ещё {len(keys) - 3} в файле")


if __name__ == "__main__":
    main()
