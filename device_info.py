from device_scanner import query, safe_get
NA = "N/A"  # afficher quand une information n'est pas disponible

# Caches : on lit chaque classe WMI une seule fois (la lecture est lente).
_objects = {}           # classe WMI -> {identifiant en MAJUSCULES: objet WMI}
_drivers = None         # identifiant en MAJUSCULES -> objet pilote
_driver_error = None    # message si la lecture des pilotes a echouer

def clear_cache():
    global _drivers, _driver_error
    _objects.clear()
    _drivers = None
    _driver_error = None

# Petits outils de mise en forme
def _text(value, unit=""):
    if value is None:
        return NA
    return f"{value} {unit}".strip()

def _gb(size_in_bytes):
    try:
        return round(int(size_in_bytes) / 1024 ** 3, 1)
    except (TypeError, ValueError):
        return None

def _mbps(bits_per_second):
    """bits/s -> Mb/s. WMI renvoie une valeur geante quand la vitesse est inconnue."""
    try:
        value = int(bits_per_second)
    except (TypeError, ValueError):
        return None
    return round(value / 1_000_000) if 0 < value <= 10 ** 12 else None

def _date(wmi_date):
    """Date WMI '20230415000000.000000+000' -> '15/04/2023'. None si invalide."""
    text = str(wmi_date or "")
    if len(text) < 8 or not text[:8].isdigit():
        return None
    return f"{text[6:8]}/{text[4:6]}/{text[:4]}"

def _first(value):
    """WMI renvoie parfois un tuple (ex. HardwareID) : on garde le premier element."""
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value

# Une fonction par type de peripherique : objet WMI -> {libelle: valeur}
def _generic(obj):
    """Details valables pour TOUS les peripheriques (objet Win32_PnPEntity)."""
    return {
        "Description": _text(safe_get(obj, "Description")),
        "Identifiant materiel": _text(_first(safe_get(obj, "HardwareID"))),
    }

def _disk(obj):
    serial = safe_get(obj, "SerialNumber")
    return {
        "Taille": _text(_gb(safe_get(obj, "Size")), "Go"),
        "Interface": _text(safe_get(obj, "InterfaceType")),
        "Partitions": _text(safe_get(obj, "Partitions")),
        "Numero de serie": _text(str(serial).strip() if serial else None),
        "Firmware": _text(safe_get(obj, "FirmwareRevision")),
    }

def _network(obj):
    return {
        "Adresse MAC": _text(safe_get(obj, "MACAddress")),
        "Nom de la connexion": _text(safe_get(obj, "NetConnectionID")),
        "Vitesse": _text(_mbps(safe_get(obj, "Speed")), "Mb/s"),
    }

def _video(obj):
    ram = safe_get(obj, "AdapterRAM")
    try:
        ram_mb = round(int(ram) / 1024 ** 2) if ram is not None else None
    except (TypeError, ValueError):
        ram_mb = None
    width = safe_get(obj, "CurrentHorizontalResolution")
    height = safe_get(obj, "CurrentVerticalResolution")
    return {
        "Memoire video": _text(ram_mb, "Mo"),
        "Resolution": NA if width is None or height is None else f"{width}x{height}",
        "Frequence d'affichage": _text(safe_get(obj, "CurrentRefreshRate"), "Hz"),
        "Processeur video": _text(safe_get(obj, "VideoProcessor")),
    }

# Catégorie (celle du scanner) -> (classe WMI à consulter, fonction qui la lit).
# Les catégories absentes de ce tableau n'ont que les détails génériques.
# Pour en ajouter une : écris une fonction _xxx(obj) et ajoute une ligne ici.
SPECIFIC = {
    "Disque": ("Win32_DiskDrive", _disk),
    "Reseau": ("Win32_NetworkAdapter", _network),
    "Affichage": ("Win32_VideoController", _video),
}

# Retrouver l'objet WMI d'un périphérique
def _find(wmi_class, device_id):
    """Retourne l'objet de cette classe WMI qui a cet identifiant, ou None."""
    if wmi_class not in _objects:
        _objects[wmi_class] = {
            str(safe_get(obj, "PNPDeviceID", "")).upper(): obj
            for obj in query(wmi_class)
        }
    return _objects[wmi_class].get(device_id.upper())

# Pilote (fournisseur, version, date)
def _find_driver(device_id):
    """Retourne l'objet pilote du périphérique. Tous les pilotes sont lus une fois."""
    global _drivers, _driver_error
    if _drivers is None:
        try:
            fields = "DeviceID, DriverVersion, DriverDate, DriverProviderName, InfName"
            _drivers = {
                str(safe_get(obj, "DeviceID", "")).upper(): obj
                for obj in query("Win32_PnPSignedDriver", fields)
            }
        except RuntimeError as error:
            _drivers = {}
            _driver_error = str(error)
    return _drivers.get(device_id.upper())

def _fill_driver(device):
    """Remplit device.driver et ajoute les infos du pilote dans device.details."""
    obj = _find_driver(device.device_id)
    if obj is None:
        if _driver_error:
            device.details["Pilote"] = f"Indisponible ({_driver_error})"
        return
    provider = safe_get(obj, "DriverProviderName")
    version = safe_get(obj, "DriverVersion")
    device.driver = f"{provider or ''} {version or ''}".strip() or NA
    device.details["Date du pilote"] = _text(_date(safe_get(obj, "DriverDate")))

# Fonction principale
def get_details(device, with_driver=True):
    """Remplit device.details (et device.driver) puis retourne le même Device.

    with_driver=False évite la lecture des pilotes (plus rapide la première fois).
    En cas de problème, l'erreur est écrite dans device.details au lieu de
    faire planter le programme.
    """
    try:
        pnp = _find("Win32_PnPEntity", device.device_id)
        if pnp is None:
            device.details["Information"] = "Périphérique introuvable (débranché ou désactivé ?)"
        else:
            if device.category in SPECIFIC:
                wmi_class, builder = SPECIFIC[device.category]
                obj = _find(wmi_class, device.device_id)
                if obj is not None:
                    device.details.update(builder(obj))
            device.details.update(_generic(pnp))
    except Exception as error:
        device.details["Erreur"] = f"Lecture des détails impossible : {error}"

    if with_driver:
        try:
            _fill_driver(device)
        except Exception as error:
            device.details["Pilote"] = f"Indisponible ({error})"

    device.details = {
        label: value for label, value in device.details.items()
        if value != NA and value != device.name
    }
    return device