"""
Import historique FIRMS sur une longue periode (par defaut : 1 an), zone mondiale.
Utilise VIIRS_NOAA20_SP pour les dates anciennes (donnees archivees et validees),
et VIIRS_NOAA20_NRT pour les dates recentes (le SP n'est pas encore publie).
A lancer depuis le terminal : python import_historique.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import time
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta

from app import app, db
from models import Evenement

load_dotenv()

ZONE = "world"
JOURS_PAR_CHUNK = 5  # max autorise par l'API FIRMS, pour SP comme pour NRT
DATE_DEBUT_IMPORT = datetime(2025, 7, 1).date()
DATE_FIN_IMPORT = datetime(2025, 8, 31).date()
DATE_BASCULE_SP_VERS_NRT = datetime(2026, 6, 1).date()  # avant cette date : SP, apres : NRT
SEUIL_INTENSITE = 330
CONFIANCE_MIN = 'n'
MAX_TENTATIVES = 3
ATTENTE_ENTRE_TENTATIVES = 15  # secondes
ATTENTE_ENTRE_CHUNKS = 3  # secondes, pour ne pas saturer l'API

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


def choisir_source(date_debut_chunk):
    if date_debut_chunk < DATE_BASCULE_SP_VERS_NRT:
        return "VIIRS_NOAA20_SP"
    return "VIIRS_NOAA20_NRT"


def recuperer_chunk(source, date_debut_str, jours, tentative=1):
    cle = os.getenv('FIRMS_API_KEY')
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{cle}/{source}/{ZONE}/{jours}/{date_debut_str}"

    try:
        df = pd.read_csv(url)
        return df, None
    except Exception as e:
        if tentative < MAX_TENTATIVES:
            print(f"    Echec (tentative {tentative}/{MAX_TENTATIVES}) : {e}")
            print(f"    Nouvelle tentative dans {ATTENTE_ENTRE_TENTATIVES}s...")
            time.sleep(ATTENTE_ENTRE_TENTATIVES)
            return recuperer_chunk(source, date_debut_str, jours, tentative + 1)
        return None, str(e)


def main():
    date_fin = DATE_FIN_IMPORT
    date_debut_totale = DATE_DEBUT_IMPORT

    print(f"Import historique du {date_debut_totale} au {date_fin}")
    print(f"Bascule SP -> NRT au {DATE_BASCULE_SP_VERS_NRT}")
    print(f"Zone : {ZONE}, seuil : {SEUIL_INTENSITE}K")
    print("-" * 60)

    with app.app_context():
        existants = db.session.query(Evenement.date, Evenement.latitude, Evenement.longitude).all()
        set_existants = set(existants)
        print(f"{len(set_existants)} evenements deja en base (verification anti-doublon active)")

        date_courante = date_debut_totale
        chunk_num = 0
        nb_jours_periode = (date_fin - date_debut_totale).days
        total_chunks = (nb_jours_periode // JOURS_PAR_CHUNK) + 1
        total_ajoutes = 0

        while date_courante <= date_fin:
            chunk_num += 1
            date_str = date_courante.strftime('%Y-%m-%d')
            source = choisir_source(date_courante)
            print(f"\n[{chunk_num}/{total_chunks}] Chunk a partir du {date_str} ({JOURS_PAR_CHUNK} jours, source: {source})...")

            df, erreur = recuperer_chunk(source, date_str, JOURS_PAR_CHUNK)

            if erreur:
                print(f"    ECHEC DEFINITIF pour ce chunk : {erreur}")
                print(f"    On continue avec le chunk suivant.")
                date_courante += timedelta(days=JOURS_PAR_CHUNK)
                time.sleep(ATTENTE_ENTRE_CHUNKS)
                continue

            if df is None or len(df) == 0:
                print(f"    Aucune donnee recue pour ce chunk.")
                date_courante += timedelta(days=JOURS_PAR_CHUNK)
                time.sleep(ATTENTE_ENTRE_CHUNKS)
                continue

            df_filtre = df[df['bright_ti4'] >= SEUIL_INTENSITE]
            if CONFIANCE_MIN == 'h':
                df_filtre = df_filtre[df_filtre['confidence'] == 'h']
            elif CONFIANCE_MIN == 'n':
                df_filtre = df_filtre[df_filtre['confidence'].isin(['n', 'h'])]

            print(f"    {len(df)} lignes brutes -> {len(df_filtre)} apres filtre intensite/confiance")

            nouveaux = []
            for _, ligne in df_filtre.iterrows():
                date_evt = datetime.strptime(str(ligne['acq_date']), "%Y-%m-%d").date()
                lat = ligne['latitude']
                lon = ligne['longitude']
                cle_dedupe = (date_evt, lat, lon)

                if cle_dedupe in set_existants:
                    continue

                heure_brute = str(int(ligne['acq_time'])).zfill(4)
                heure_formatee = f"{heure_brute[:2]}:{heure_brute[2:]}"

                nouveaux.append(Evenement(
                    date=date_evt,
                    heure=heure_formatee,
                    zone=f"{lat:.2f}, {lon:.2f}",
                    region=determiner_region(lat, lon),
                    type_evenement="Incendie",
                    description=f"Intensite detectee : {ligne['bright_ti4']} K, FRP : {ligne['frp']} MW",
                    latitude=lat,
                    longitude=lon,
                    intensite=ligne['bright_ti4'],
                    frp=ligne['frp'],
                    satellite=ligne['satellite'],
                    confidence=ligne['confidence'],
                    daynight=ligne['daynight'],
                    bright_ti5=ligne['bright_ti5'],
                    scan=ligne['scan'],
                    track=ligne['track'],
                    version=ligne['version']
                ))
                set_existants.add(cle_dedupe)

            if nouveaux:
                db.session.bulk_save_objects(nouveaux)
                db.session.commit()
                total_ajoutes += len(nouveaux)
                print(f"    {len(nouveaux)} nouveaux evenements ajoutes (total cumule : {total_ajoutes})")
            else:
                print(f"    Aucun nouvel evenement (tous deja en base).")

            date_courante += timedelta(days=JOURS_PAR_CHUNK)
            time.sleep(ATTENTE_ENTRE_CHUNKS)

        print("\n" + "=" * 60)
        print(f"IMPORT TERMINE. Total ajoute : {total_ajoutes} evenements.")


if __name__ == '__main__':
    main()