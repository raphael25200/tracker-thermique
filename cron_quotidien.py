#!/usr/bin/python3

"""
Script destine au Cron OVH : purge des donnees de plus de 60 jours, puis import
quotidien des detections FIRMS, pour rester sous le quota de la base.
La purge passe AVANT l'import : une base proche du quota doit d'abord se liberer
de la place, sinon l'import echoue et plus rien ne la vide.
A configurer dans le planificateur de taches OVH (execution quotidienne).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from sqlalchemy import func
from app import app, db
from models import Evenement
from firms import recuperer_incendies, cle_detection

LIMITE_RETENTION_JOURS = 60
TAILLE_LOT_PURGE = 10000  # lignes supprimees par transaction (evite un DELETE geant)
# Filet de securite : au-dela de ce nombre de lignes, les jours les plus anciens sont
# supprimes meme s'ils sont dans la fenetre de retention. Estimation a ajuster apres
# mesure : environ 250 octets par ligne, donc 5 000 000 lignes = environ 1,25 Go.
PLAFOND_LIGNES = 5000000


def _supprimer_par_lots(condition):
    """Supprime les evenements correspondant a la condition, par lots d'identifiants
    (compatible MySQL et SQLite). Retourne le nombre de lignes supprimees."""
    total = 0
    while True:
        ids = [r[0] for r in db.session.query(Evenement.id).filter(condition).limit(TAILLE_LOT_PURGE).all()]
        if not ids:
            return total
        Evenement.query.filter(Evenement.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        total += len(ids)


def purger_anciennes_donnees():
    date_limite = datetime.now().date() - timedelta(days=LIMITE_RETENTION_JOURS)
    return _supprimer_par_lots(Evenement.date < date_limite)


def purger_jusqua_plafond():
    """Filet de securite : tant que la table depasse PLAFOND_LIGNES, supprime le jour
    le plus ancien. S'arrete avant de supprimer le jour le plus recent."""
    supprimes = 0
    total = Evenement.query.count()
    dernier_jour = db.session.query(func.max(Evenement.date)).scalar()
    while total > PLAFOND_LIGNES:
        jour = db.session.query(func.min(Evenement.date)).scalar()
        if jour is None or jour >= dernier_jour:
            break
        nb = _supprimer_par_lots(Evenement.date == jour)
        if nb == 0:
            break
        supprimes += nb
        total -= nb
    return supprimes


def importer_nouvelles_donnees():
    resultats, erreur = recuperer_incendies(zone="world", jours=1, seuil_intensite=330, confiance_min='n')

    if erreur:
        return 0, erreur

    if not resultats:
        return 0, None

    # Seules les dates presentes dans la reponse FIRMS peuvent produire des doublons : inutile
    # de charger toute la table en memoire a chaque passage (le cron peut tourner chaque heure).
    dates_recues = list({item['date'] for item in resultats})
    # ROUND cote SQL : MySQL renvoie un FLOAT avec 6 chiffres significatifs seulement (une longitude
    # >= 100 perd une decimale), donc on ne relit jamais la valeur brute pour comparer.
    existants = db.session.query(
        Evenement.date, func.round(Evenement.latitude, 4), func.round(Evenement.longitude, 4)).filter(
        Evenement.date.in_(dates_recues),
        Evenement.latitude.isnot(None), Evenement.longitude.isnot(None)).all()
    set_existants = set(cle_detection(d, lat, lon) for d, lat, lon in existants)

    nouveaux = []
    for item in resultats:
        cle = cle_detection(item['date'], item['latitude'], item['longitude'])
        if cle in set_existants:
            continue

        nouveaux.append(Evenement(
            date=item['date'], heure=item['heure'], zone=item['zone'], region=item['region'],
            type_evenement="Incendie",
            description=f"Intensite detectee : {item['intensite']} K, FRP : {item['frp']} MW",
            # Coordonnees stockees arrondies a 4 decimales (environ 11 m, bien sous le pixel de 375 m) :
            # la valeur relue depuis le FLOAT MySQL redonne alors exactement la meme cle de comparaison.
            latitude=round(item['latitude'], 4), longitude=round(item['longitude'], 4),
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
    debut = datetime.now()
    print(f"[{debut.strftime('%Y-%m-%d %H:%M:%S')}] Debut de la tache cron")

    with app.app_context():
        try:
            nb_supprimes = purger_anciennes_donnees()
            print(f"  {nb_supprimes} evenements purges (plus de {LIMITE_RETENTION_JOURS} jours)")
        except Exception as e:
            print(f"  ERREUR purge : {e}")
            db.session.rollback()

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
            nb_plafond = purger_jusqua_plafond()
            if nb_plafond:
                print(f"  ATTENTION : plafond de {PLAFOND_LIGNES} lignes depasse, {nb_plafond} evenements supprimes en plus")
        except Exception as e:
            print(f"  ERREUR purge de securite : {e}")
            db.session.rollback()

        total_actuel = Evenement.query.count()
        print(f"  Total en base : {total_actuel}")

    fin = datetime.now()
    duree = int((fin - debut).total_seconds())
    print(f"[{fin.strftime('%Y-%m-%d %H:%M:%S')}] Fin de la tache cron (duree : {duree} s)")


if __name__ == '__main__':
    main()