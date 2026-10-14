"""
main.py - Teste device.py, device_scanner.py et device_info.py.

Utilisation (sous Windows) :
    python main.py                          -> 1 ligne par périphérique
    python main.py --details                -> + pilote et caractéristiques
    python main.py --category Disque --details
    python main.py --name realtek --details
    python main.py --all                    -> inclut les périphériques techniques
"""

import argparse
import sys
import time

from device_scanner import scan_all
from device_info import get_details, clear_cache

# Périphériques techniques masqués par défaut (virtuels, internes à Windows).
NOISE = ("WAN Miniport", "Kernel Debug", "Wi-Fi Direct", "MS Idd",
         "Proxy de service", "Hub USB racine", "USB composite")


def is_noise(device):
    return any(word.lower() in device.name.lower() for word in NOISE)


def print_device(device, with_details):
    print(f"  - {device.name} | {device.manufacturer} | {device.status}")
    if with_details:
        if device.driver:
            print(f"        Pilote : {device.driver}")
        for label, value in device.details.items():
            print(f"        {label} : {value}")


def main():
    parser = argparse.ArgumentParser(description="Test du scanner de périphériques")
    parser.add_argument("--details", action="store_true", help="lire aussi les détails et le pilote")
    parser.add_argument("--all", action="store_true", help="inclure les périphériques techniques")
    parser.add_argument("--category", help="filtrer par catégorie (ex. Disque, Réseau)")
    parser.add_argument("--name", help="filtrer par texte contenu dans le nom")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    start = time.time()
    try:
        devices = scan_all()
    except RuntimeError as error:
        print(f"Erreur : {error}")
        return
    total = len(devices)
    print(f"{total} périphériques détectés en {time.time() - start:.1f} s")

    if not args.all:
        devices = [d for d in devices if not is_noise(d)]
    if args.category:
        devices = [d for d in devices if d.category.lower() == args.category.lower()]
    if args.name:
        devices = [d for d in devices if args.name.lower() in d.name.lower()]
    print(f"{len(devices)} affichés (--all pour tout voir)")

    if args.details:
        clear_cache()
        start = time.time()
        for device in devices:
            get_details(device)
        print(f"Détails lus en {time.time() - start:.1f} s")

    current = None
    for device in devices:
        if device.category != current:
            current = device.category
            print(f"\n[{current}]")
        print_device(device, args.details)


if __name__ == "__main__":
    main()