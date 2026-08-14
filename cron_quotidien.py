#!/usr/bin/python3

"""
Script destine au Cron OVH : import quotidien des detections FIRMS + purge
des donnees de plus de 180 jours, pour rester sous le quota de la base.
A configurer dans le planificateur de taches OVH (execution quotidienne).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from app import app, db
from models import Evenement
from firms import recuperer_incendies

LIMITE_RETENTION_JOURS = 180


def purger_anciennes_donnees():
    date_limite = datetime.now().date() - timedelta(days=LIMITE_RETENTION_JOURS)
    nb_supprimes = Evenement.query.filter(Evenement.date < date_limite).delete()
    db.session.commit()
    return nb_supprimes


def importer_nouvelles_donnees():
    resultats, erreur = recuperer_incendies(zone="world", jours=1, seuil_intensite=330, confiance_min='n')

    if erreur:
        return 0, erreur

    existants = db.session.query(Evenement.date, Evenement.latitude, Evenement.longitude).all()
    set_existants = set((d, round(lat, 4), round(lon, 4)) for d, lat, lon in existants)

    nouveaux = []
    for item in resultats:
        cle = (item['date'], round(item['latitude'], 4), round(item['longitude'], 4))
        if cle in set_existants:
            continue

        nouveaux.append(Evenement(
            date=item['date'], heure=item['heure'], zone=item['zone'], region=item['region'],
            type_evenement="Incendie",
            description=f"Intensite detectee : {item['intensite']} K, FRP : {item['frp']} MW",
            latitude=item['latitude'], longitude=item['longitude'],
            intensite=item['intensite'], frp=item['frp'],
            satellite=item['satellite'], confidence=item['confidence'], daynight=item['daynight'],
            bright_ti5=item['bright_ti5'], scan=item['scan'], track=item['track'], version=item['version']
        ))
        set_existants.add(cle)

    if nouveaux:
        db.session.bulk_save_objects(nouveaux)
        db.session.commit()

    return len(nouveaux), None


def main():
    horodatage = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{horodatage}] Debut de la tache cron")

    with app.app_context():
        try:
            nb_ajoutes, erreur = importer_nouvelles_donnees()
            if erreur:
                print(f"  ERREUR import : {erreur}")
            else:
                print(f"  {nb_ajoutes} nouveaux evenements importes")
        except Exception as e:
            print(f"  ERREUR import (exception) : {e}")
            db.session.rollback()

        try:
            nb_supprimes = purger_anciennes_donnees()
            print(f"  {nb_supprimes} evenements purges (plus de {LIMITE_RETENTION_JOURS} jours)")
        except Exception as e:
            print(f"  ERREUR purge : {e}")
            db.session.rollback()

        total_actuel = Evenement.query.count()
        print(f"  Total en base : {total_actuel}")

    print(f"[{horodatage}] Fin de la tache cron")


if __name__ == '__main__':
    main()