import csv
import io
import os
import urllib.request
import socket
from dotenv import load_dotenv
from datetime import datetime

# Force IPv4 uniquement
socket.setdefaulttimeout(60)
_getaddrinfo_original = socket.getaddrinfo
def _getaddrinfo_ipv4(*args, **kwargs):
    return [addr for addr in _getaddrinfo_original(*args, **kwargs) if addr[0] == socket.AF_INET]
socket.getaddrinfo = _getaddrinfo_ipv4

load_dotenv()

REGIONS_BBOX = {
    "europe": (34, -25, 72, 45),
    "amerique_nord": (5, -170, 75, -50),
    "amerique_sud": (-58, -82, 13, -34),
    "afrique": (-35, -18, 38, 52),
    "asie": (-10, 45, 55, 150),
    "oceanie": (-50, 110, 0, 180)
}


def determiner_region(lat, lon):
    for nom, (sud, ouest, nord, est) in REGIONS_BBOX.items():
        if sud <= lat <= nord and ouest <= lon <= est:
            return nom
    return "autre"


def recuperer_incendies(zone="world", jours=5, seuil_intensite=330, confiance_min='n'):
    cle = os.getenv('FIRMS_API_KEY')
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{cle}/VIIRS_NOAA20_NRT/{zone}/{jours}"

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        requete = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(requete, timeout=60) as reponse:
            contenu = reponse.read().decode('utf-8')
    except Exception as e:
        return None, f"Erreur lors de la récupération des données FIRMS : {e}"

    if not contenu or contenu.startswith("Please limit"):
        return None, f"Réponse invalide de FIRMS : {contenu[:200]}"

    lecteur = csv.DictReader(io.StringIO(contenu))

    resultats = []
    for ligne in lecteur:
        try:
            intensite = float(ligne['bright_ti4'])
            confidence = ligne['confidence']
        except (KeyError, ValueError):
            continue

        if intensite < seuil_intensite:
            continue

        if confiance_min == 'h' and confidence != 'h':
            continue
        elif confiance_min == 'n' and confidence not in ('n', 'h'):
            continue

        try:
            date_convertie = datetime.strptime(ligne['acq_date'], "%Y-%m-%d").date()
            lat = float(ligne['latitude'])
            lon = float(ligne['longitude'])
            heure_brute = str(int(ligne['acq_time'])).zfill(4)
            heure_formatee = f"{heure_brute[:2]}:{heure_brute[2:]}"
            frp = float(ligne['frp']) if ligne.get('frp') else None
            bright_ti5 = float(ligne['bright_ti5']) if ligne.get('bright_ti5') else None
            scan = float(ligne['scan']) if ligne.get('scan') else None
            track = float(ligne['track']) if ligne.get('track') else None
        except (KeyError, ValueError):
            continue

        resultats.append({
            "date": date_convertie,
            "heure": heure_formatee,
            "zone": f"{lat:.2f}, {lon:.2f}",
            "region": determiner_region(lat, lon),
            "latitude": lat,
            "longitude": lon,
            "intensite": intensite,
            "frp": frp,
            "satellite": ligne.get('satellite'),
            "confidence": confidence,
            "daynight": ligne.get('daynight'),
            "bright_ti5": bright_ti5,
            "scan": scan,
            "track": track,
            "version": ligne.get('version'),
            "source_url": None
        })

    return resultats, None