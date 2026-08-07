"""
Migre toutes les donnees de la base SQLite locale vers la base MySQL (OVH).
A lancer une seule fois, apres avoir verifie que DATABASE_URL (MySQL) fonctionne.
Usage : python migrer_vers_mysql.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

TAILLE_LOT = 5000  # nombre de lignes inserees a chaque fois

URL_SQLITE = "sqlite:///instance/tracker.db"
URL_MYSQL = os.getenv('DATABASE_URL')

if not URL_MYSQL or not URL_MYSQL.startswith('mysql'):
    print("ERREUR : DATABASE_URL ne pointe pas vers une base MySQL.")
    print("Verifiez votre fichier .env avant de continuer.")
    exit(1)


def main():
    print(f"Source (SQLite) : {URL_SQLITE}")
    print(f"Destination (MySQL) : {URL_MYSQL.split('@')[1] if '@' in URL_MYSQL else '???'}")
    print("-" * 60)

    moteur_sqlite = create_engine(URL_SQLITE)
    moteur_mysql = create_engine(URL_MYSQL)

    # 1. Creer la structure des tables sur MySQL (identique a SQLite)
    print("Creation de la structure des tables sur MySQL...")
    from models import db
    from app import app
    with app.app_context():
        app.config['SQLALCHEMY_DATABASE_URI'] = URL_MYSQL
        db.init_app(app)
        with app.app_context():
            db.create_all()
    print("Structure creee.")

    # 2. Compter le volume total a migrer
    with moteur_sqlite.connect() as connexion:
        total = connexion.execute(text("SELECT COUNT(*) FROM evenement")).scalar()
    print(f"Total a migrer : {total} lignes")

    if total == 0:
        print("Rien a migrer.")
        return

    confirmation = input(f"Confirmer la migration de {total} lignes vers MySQL ? (oui/non) : ")
    if confirmation.lower() != 'oui':
        print("Migration annulee.")
        return

    # 3. Migrer par lots
    colonnes = [
        "id", "date", "heure", "zone", "region", "type_evenement", "description",
        "source_url", "latitude", "longitude", "intensite", "frp", "satellite",
        "confidence", "daynight", "bright_ti5", "scan", "track", "version"
    ]
    colonnes_str = ", ".join(colonnes)
    placeholders = ", ".join([f":{c}" for c in colonnes])

    offset = 0
    total_migre = 0

    with moteur_sqlite.connect() as connexion_source:
        while offset < total:
            resultat = connexion_source.execute(
                text(f"SELECT {colonnes_str} FROM evenement ORDER BY id LIMIT :limite OFFSET :decalage"),
                {"limite": TAILLE_LOT, "decalage": offset}
            )
            lignes = resultat.mappings().all()

            if not lignes:
                break

            with moteur_mysql.begin() as connexion_dest:
                connexion_dest.execute(
                    text(f"INSERT INTO evenement ({colonnes_str}) VALUES ({placeholders})"),
                    [dict(ligne) for ligne in lignes]
                )

            total_migre += len(lignes)
            offset += TAILLE_LOT
            print(f"  {total_migre}/{total} lignes migrees...")

    print("-" * 60)
    print(f"MIGRATION TERMINEE : {total_migre} lignes transferees.")


if __name__ == '__main__':
    main()
