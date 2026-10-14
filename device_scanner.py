from device import Device

# Type Windows (PNPClass) -> categorie affichee
CLASSES = {
    "DiskDrive": "Disque",
    "CDROM": "Lecteur CD/DVD",
    "Net": "Reseau",
    "Bluetooth": "Bluetooth",
    "MEDIA": "Audio",
    "AudioEndpoint": "Audio",
    "Display": "Affichage",
    "Monitor": "Affichage",
    "Keyboard": "Clavier",
    "Mouse": "Souris",
    "USB": "USB",
    "Camera": "Camera",
    "Image": "Camera",
    "Printer": "Imprimante",
    "WPD": "Appareil portable",
    "Battery": "Batterie",
    "Biometric": "Biometrie",
    "Ports": "Ports",
}

# Code d'erreur Windows (ConfigManagerErrorCode) -> etat. Tout autre code = probleme.
ETATS = {0: "OK", 22: "Desactiver"}
_wmi = None  # connexion WMI, creer au premier appel

def query(wmi_class, fields="*"):
    """Interroge une classe WMI et retourne la liste des objets trouves. Leve RuntimeError avec un message clair en cas de probleme."""
    global _wmi
    try:
        if _wmi is None:
            import win32com.client 
            #Cette bibliotheque fournie par pywin32, permet a Python de communiquer avec certaines interfaces Windows, notamment via COM. C'est le moyen utiliser ici pour acceder a WMI.
            _wmi = win32com.client.GetObject("winmgmts:\\\\.\\root\\cimv2")
        return list(_wmi.ExecQuery(f"SELECT {fields} FROM {wmi_class}")) #la requete ressemble a du SQL, le langage souvent utiliser pour interroger des bdd. Mais ici on utilise le langage de requetes de WMI, appeler WQL (WMI Query Language).
    except ImportError:
        raise RuntimeError("pywin32 est introuvable. Installe-le avec : pip install pywin32") from None
    except Exception as error:
        raise RuntimeError(f"Lecture de {wmi_class} impossible : {error}") from None


def safe_get(obj, name, default=None):
    """Lit une propriete WMI. Absente ou vide -> default (la valeur 0 est gardee)."""
    try:
        value = getattr(obj, name)
    except Exception:
        return default
    return default if value is None or value == "" else value


def scan_all():
    """Retourne la liste des peripheriques, tries par categorie puis par nom."""
    devices = []
    for obj in query("Win32_PnPEntity"):
        category = CLASSES.get(safe_get(obj, "PNPClass"))
        if category is None:
            continue  # type de peripherique ignore

        code = safe_get(obj, "ConfigManagerErrorCode")
        maker = str(safe_get(obj, "Manufacturer", "")).strip()
        if maker.startswith("("):  # ex. "(Standard disk drives)" : pas un vrai fabricant
            maker = ""

        devices.append(Device(
            name=str(safe_get(obj, "Name", "")).strip() or "Inconnu",
            category=category,
            manufacturer=maker or "Inconnu",
            device_id=str(safe_get(obj, "PNPDeviceID", "")).strip(),
            status="Inconnu" if code is None else ETATS.get(code, "Erreur"),
        ))
    devices.sort(key=lambda d: (d.category, d.name.lower()))
    return devices