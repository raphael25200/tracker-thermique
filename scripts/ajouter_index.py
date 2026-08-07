"""
Ajoute des index sur la base existante, sans supprimer les données.
A lancer une seule fois : python ajouter_index.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import app, db
from sqlalchemy import text

with app.app_context():
    print("Creation des index (peut prendre quelques minutes vu le volume)...")

    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_evenement_date ON evenement (date)"))
    print("  Index sur 'date' cree.")

    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_evenement_region ON evenement (region)"))
    print("  Index sur 'region' cree.")

    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_evenement_frp ON evenement (frp)"))
    print("  Index sur 'frp' cree.")

    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_evenement_confidence ON evenement (confidence)"))
    print("  Index sur 'confidence' cree.")

    db.session.commit()
    print("Termine.")
