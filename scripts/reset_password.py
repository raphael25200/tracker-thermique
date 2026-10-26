"""
Cree ou reinitialise le mot de passe d'un utilisateur de l'application.

Usage : python scripts/reset_password.py NOM_UTILISATEUR

A lancer SUR LE SERVEUR pour la production : le mot de passe est enregistre avec
l'algorithme de la version de Werkzeug installee la-bas, ce qui garantit que le site
saura le relire. Un hash produit en local (Werkzeug recent) peut etre illisible pour
la version plus ancienne du serveur. Le mot de passe est saisi de facon masquee et
n'est jamais affiche.
"""
import sys
import os
import getpass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import app, db
from models import User

LONGUEUR_MIN = 10


def main():
    if len(sys.argv) != 2:
        print("Usage : python scripts/reset_password.py NOM_UTILISATEUR")
        sys.exit(1)
    nom = sys.argv[1]

    with app.app_context():
        utilisateur = User.query.filter_by(username=nom).first()
        if utilisateur is None:
            reponse = input(f"L'utilisateur '{nom}' n'existe pas. Le creer ? (oui/non) : ")
            if reponse.strip().lower() != 'oui':
                print("Annule.")
                return
            utilisateur = User(username=nom)

        mot_de_passe = getpass.getpass("Nouveau mot de passe : ")
        if len(mot_de_passe) < LONGUEUR_MIN:
            print(f"Mot de passe trop court (minimum {LONGUEUR_MIN} caracteres).")
            sys.exit(1)
        if getpass.getpass("Confirmer le mot de passe : ") != mot_de_passe:
            print("Les deux saisies sont differentes. Rien n'a ete modifie.")
            sys.exit(1)

        utilisateur.set_password(mot_de_passe)
        db.session.add(utilisateur)
        db.session.commit()
        print(f"Mot de passe enregistre pour '{nom}'.")


if __name__ == '__main__':
    main()
