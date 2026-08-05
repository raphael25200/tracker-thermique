import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

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

def recuperer_incendies(zone="world", jours=3, seuil_intensite=330, confiance_min='n'):
    cle = os.getenv('FIRMS_API_KEY')
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{cle}/VIIRS_NOAA20_NRT/{zone}/{jours}"

    try:
        df = pd.read_csv(url)
    except Exception as e:
        return None, f"Erreur lors de la récupération des données FIRMS : {e}"

    df_filtre = df[df['bright_ti4'] >= seuil_intensite]

    if confiance_min == 'h':
        df_filtre = df_filtre[df_filtre['confidence'] == 'h']
    elif confiance_min == 'n':
        df_filtre = df_filtre[df_filtre['confidence'].isin(['n', 'h'])]

    resultats = []
    for _, ligne in df_filtre.iterrows():
        date_convertie = datetime.strptime(str(ligne['acq_date']), "%Y-%m-%d").date()
        heure_brute = str(int(ligne['acq_time'])).zfill(4)
        heure_formatee = f"{heure_brute[:2]}:{heure_brute[2:]}"

        resultats.append({
            "date": date_convertie,
            "heure": heure_formatee,
            "zone": f"{ligne['latitude']:.2f}, {ligne['longitude']:.2f}",
            "region": determiner_region(ligne['latitude'], ligne['longitude']),
            "latitude": ligne['latitude'],
            "longitude": ligne['longitude'],
            "intensite": ligne['bright_ti4'],
            "frp": ligne['frp'],
            "satellite": ligne['satellite'],
            "confidence": ligne['confidence'],
            "daynight": ligne['daynight'],
            "bright_ti5": ligne['bright_ti5'],
            "scan": ligne['scan'],
            "track": ligne['track'],
            "version": ligne['version'],
            "source_url": None
        })

    return resultats, None