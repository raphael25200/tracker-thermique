from app import app, db
from sqlalchemy import text

with app.app_context():
    resultat = db.session.execute(text("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND tbl_name='evenement'"))
    for ligne in resultat:
        print(ligne)
