"""
Supprime les doublons de detections : memes date et memes coordonnees arrondies a
4 decimales. Conserve la ligne la plus ancienne (plus petit id) de chaque groupe.

Usage :
  python scripts/dedoublonner.py                       SIMULATION : compte, ne supprime rien
  python scripts/dedoublonner.py --appliquer           supprime, jour par jour
  python scripts/dedoublonner.py --depuis 2026-10-01 --jusqua 2026-10-05 --appliquer

Par defaut le jour en cours est exclu (le cron y ecrit encore). Les evenements sans
coordonnees ne sont jamais touches. A lancer APRES le deploiement du cron corrige, et
apres une sauvegarde : une suppression est definitive. Traite une journee par transaction.
"""
import sys
import os
import argparse
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sqlalchemy import func, text
from app import app, db
from models import Evenement

# Numerote les lignes d'un meme point (date + coordonnees arrondies) : rn > 1 = doublon.
_NUMEROTATION = """
    SELECT id, ROW_NUMBER() OVER (
        PARTITION BY ROUND(latitude, 4), ROUND(longitude, 4) ORDER BY id) AS rn
    FROM evenement
    WHERE date = :jour AND latitude IS NOT NULL AND longitude IS NOT NULL
"""

SQL_COMPTER = text("SELECT COUNT(*) FROM (" + _NUMEROTATION + ") t WHERE t.rn > 1")

# Forme deja employee avec succes sur MySQL (incident d'aout 2026).
SQL_SUPPRIMER_MYSQL = text(
    "DELETE e FROM evenement e JOIN (SELECT id FROM (" + _NUMEROTATION +
    ") t WHERE t.rn > 1) d ON d.id = e.id")

# SQLite (tests et developpement local) ne connait pas DELETE ... JOIN.
SQL_SUPPRIMER_PORTABLE = text(
    "DELETE FROM evenement WHERE id IN (SELECT id FROM (" + _NUMEROTATION + ") t WHERE t.rn > 1)")


def compter_doublons(jour):
    return db.session.execute(SQL_COMPTER, {"jour": jour.isoformat()}).scalar()


def supprimer_doublons(jour):
    sql = SQL_SUPPRIMER_MYSQL if db.engine.dialect.name == 'mysql' else SQL_SUPPRIMER_PORTABLE
    nb = db.session.execute(sql, {"jour": jour.isoformat()}).rowcount
    db.session.commit()
    return nb


def _date(valeur):
    return datetime.strptime(valeur, '%Y-%m-%d').date()


def main():
    parseur = argparse.ArgumentParser(description="Supprime les doublons de detections.")
    parseur.add_argument('--appliquer', action='store_true', help="supprime reellement (sinon simulation)")
    parseur.add_argument('--depuis', help="premiere date AAAA-MM-JJ (defaut : la plus ancienne en base)")
    parseur.add_argument('--jusqua', help="derniere date AAAA-MM-JJ (defaut : hier)")
    args = parseur.parse_args()

    with app.app_context():
        premier, dernier = db.session.query(func.min(Evenement.date), func.max(Evenement.date)).one()
        if premier is None:
            print("Base vide.")
            return
        depuis = _date(args.depuis) if args.depuis else premier
        jusqua = _date(args.jusqua) if args.jusqua else min(dernier, datetime.now().date() - timedelta(days=1))

        print("MODE : %s" % ("SUPPRESSION" if args.appliquer else "SIMULATION (rien n'est supprime)"))
        print("Periode : %s -> %s" % (depuis, jusqua))
        total = 0
        jour = depuis
        while jour <= jusqua:
            try:
                nb = supprimer_doublons(jour) if args.appliquer else compter_doublons(jour)
            except Exception as e:
                db.session.rollback()
                print("ERREUR le %s : %s" % (jour, e))
                sys.exit(1)
            if nb:
                print("  %s : %d doublons" % (jour, nb))
            total += nb
            jour += timedelta(days=1)
        print("Total : %d doublons %s." % (total, "supprimes" if args.appliquer else "detectes"))


if __name__ == '__main__':
    main()
