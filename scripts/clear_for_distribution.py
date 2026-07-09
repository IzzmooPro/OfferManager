"""Dağıtım öncesinde kullanıcı verilerini güvenli biçimde sıfırla.

Müşteri, ürün, teklif ve teklif kalemleri temizlenir. Şirket ayarları, logo,
imzalar ve tema korunur. İşlemden önce otomatik ZIP yedeği alınır.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.app_paths import BACKUP_DIR, DB_PATH, PDF_DIR
from ui.dialogs.backup_manager import create_backup


def _confirm() -> bool:
    try:
        answer = input("Program verileri sıfırlansın mı? (evet/hayır): ")
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().casefold() in {"evet", "e", "yes", "y"}


def clear_for_distribution(assume_yes: bool = False) -> tuple[str, int]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Veritabanı bulunamadı: {DB_PATH}")

    if not assume_yes and not _confirm():
        raise SystemExit("İşlem iptal edildi.")

    backup_path = create_backup(str(BACKUP_DIR))

    with sqlite3.connect(str(DB_PATH), timeout=30) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            conn.execute("DELETE FROM offer_items")
            conn.execute("DELETE FROM offers")
            conn.execute("DELETE FROM customers")
            conn.execute("DELETE FROM products")
            conn.execute("DELETE FROM offer_counter")
            # Faz 3 tabloları — kategori ve teklif şablonları da kullanıcı verisidir
            conn.execute("DELETE FROM product_categories")
            conn.execute("DELETE FROM offer_templates")
            conn.execute(
                "DELETE FROM sqlite_sequence WHERE name IN "
                "('offers','offer_items','customers','products','offer_counter',"
                "'product_categories','offer_templates')"
            )
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError(f"Veritabanı bütünlük kontrolü başarısız: {integrity}")
        conn.execute("VACUUM")

    removed_pdfs = 0
    if PDF_DIR.exists():
        for pdf_path in PDF_DIR.glob("*.pdf"):
            pdf_path.unlink()
            removed_pdfs += 1

    return backup_path, removed_pdfs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="Onay istemeden çalıştır")
    args = parser.parse_args()

    try:
        backup_path, removed_pdfs = clear_for_distribution(args.yes)
    except Exception as exc:
        print(f"[HATA] Sıfırlama başarısız: {exc}", file=sys.stderr)
        return 1

    print(f"[OK] Yedek: {backup_path}")
    print("[OK] Müşteri, ürün, teklif ve sayaç kayıtları temizlendi.")
    print(f"[OK] Silinen teklif PDF sayısı: {removed_pdfs}")
    print("[OK] Şirket ayarları, logo, imzalar ve tema korundu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
