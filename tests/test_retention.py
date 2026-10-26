"""
Tests de la purge, du plafond de securite et de la deduplication.
Lancer depuis la racine du projet : python -m unittest discover -s tests -v
Utilise une base SQLite en memoire : aucune donnee reelle n'est touchee, aucun reseau.
"""
import os
import sys
import struct
import unittest
from datetime import date, timedelta
from unittest.mock import patch

os.environ['DATABASE_URL'] = 'sqlite://'  # base en memoire, prioritaire sur .env
os.environ.setdefault('SECRET_KEY', 'cle-de-test')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cron_quotidien as cron
from app import app, db
from models import Evenement
from firms import cle_detection


def simple_precision(valeur):
    """Simule le stockage MySQL FLOAT (simple precision)."""
    return struct.unpack('f', struct.pack('f', valeur))[0]


def ajouter(jour, nb, lat_depart=10.0):
    for i in range(nb):
        db.session.add(Evenement(
            date=jour, zone="test", type_evenement="Incendie",
            latitude=lat_depart + i * 0.01, longitude=20.0))
    db.session.commit()


def detection(jour, lat, lon):
    return {
        'date': jour, 'heure': '12:00', 'zone': f"{lat}, {lon}", 'region': 'europe',
        'latitude': lat, 'longitude': lon, 'intensite': 340.0, 'frp': 5.0,
        'satellite': 'N20', 'confidence': 'n', 'daynight': 'D',
        'bright_ti5': 290.0, 'scan': 0.4, 'track': 0.4, 'version': '2.0NRT'}


class TestRetention(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.create_all()
        Evenement.query.delete()
        db.session.commit()
        self.aujourdhui = date.today()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_purge_supprime_uniquement_l_ancien_par_lots(self):
        ajouter(self.aujourdhui - timedelta(days=61), 7, 10.0)
        ajouter(self.aujourdhui - timedelta(days=59), 5, 11.0)
        ajouter(self.aujourdhui, 4, 12.0)
        with patch.object(cron, 'TAILLE_LOT_PURGE', 3):  # force plusieurs lots
            supprimes = cron.purger_anciennes_donnees()
        self.assertEqual(supprimes, 7)
        self.assertEqual(Evenement.query.count(), 9)
        self.assertEqual(Evenement.query.filter(
            Evenement.date < self.aujourdhui - timedelta(days=60)).count(), 0)

    def test_plafond_supprime_les_jours_les_plus_anciens(self):
        ajouter(self.aujourdhui - timedelta(days=3), 10, 10.0)
        ajouter(self.aujourdhui - timedelta(days=2), 10, 11.0)
        ajouter(self.aujourdhui, 5, 12.0)
        with patch.object(cron, 'PLAFOND_LIGNES', 12):
            supprimes = cron.purger_jusqua_plafond()
        self.assertEqual(supprimes, 20)
        self.assertEqual(Evenement.query.count(), 5)
        self.assertEqual(Evenement.query.filter(Evenement.date == self.aujourdhui).count(), 5)

    def test_plafond_ne_vide_jamais_le_jour_le_plus_recent(self):
        ajouter(self.aujourdhui, 20, 10.0)
        with patch.object(cron, 'PLAFOND_LIGNES', 12):
            supprimes = cron.purger_jusqua_plafond()
        self.assertEqual(supprimes, 0)
        self.assertEqual(Evenement.query.count(), 20)

    def test_plafond_inactif_sous_le_seuil(self):
        ajouter(self.aujourdhui - timedelta(days=1), 5, 10.0)
        with patch.object(cron, 'PLAFOND_LIGNES', 12):
            self.assertEqual(cron.purger_jusqua_plafond(), 0)
        self.assertEqual(Evenement.query.count(), 5)


class TestDeduplication(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.create_all()
        Evenement.query.delete()
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_cle_identique_apres_passage_en_simple_precision(self):
        jour = date(2026, 10, 25)
        lat, lon = 45.12347, 5.56781
        relu = (jour, simple_precision(lat), simple_precision(lon))
        # L'ancienne comparaison brute echoue : c'est le bug a l'origine de l'incident d'aout.
        self.assertNotEqual((jour, lat, lon), relu)
        self.assertEqual(cle_detection(jour, lat, lon), cle_detection(*relu))

    def test_coordonnees_arrondies_stables_apres_simple_precision(self):
        """Stocker les coordonnees arrondies rend la cle identique apres relecture MySQL."""
        import random
        random.seed(1)
        jour = date(2026, 10, 25)
        divergences_sans_arrondi = 0
        total = 20000
        for _ in range(total):
            lat = random.uniform(-90, 90)
            lon = random.uniform(-180, 180)
            cle_recue = cle_detection(jour, lat, lon)
            # Avec arrondi avant stockage : la cle relue doit etre strictement identique.
            stocke = (simple_precision(round(lat, 4)), simple_precision(round(lon, 4)))
            self.assertEqual(cle_recue, cle_detection(jour, *stocke))
            # Sans arrondi avant stockage (ancien comportement) : on compte les ecarts.
            brut = (simple_precision(lat), simple_precision(lon))
            if cle_recue != cle_detection(jour, *brut):
                divergences_sans_arrondi += 1
        print("\n  taux de divergence SANS arrondi stocke : %.1f %%" % (100.0 * divergences_sans_arrondi / total))
        self.assertGreater(divergences_sans_arrondi, 0)

    def test_import_ignore_les_doublons_et_les_coordonnees_nulles(self):
        jour = date.today()
        lat, lon = 45.12347, 5.56781
        # detection deja en base, relue en simple precision
        db.session.add(Evenement(date=jour, zone="a", type_evenement="Incendie",
                                 latitude=simple_precision(lat), longitude=simple_precision(lon)))
        # evenement saisi a la main, sans coordonnees (provoquait un plantage du cron)
        db.session.add(Evenement(date=jour, zone="manuel", type_evenement="Autre"))
        db.session.commit()

        recues = [detection(jour, lat, lon), detection(jour, 46.5, 6.5)]
        with patch.object(cron, 'recuperer_incendies', return_value=(recues, None)):
            nb, erreur = cron.importer_nouvelles_donnees()
        self.assertIsNone(erreur)
        self.assertEqual(nb, 1)  # seule la detection 46.5 / 6.5 est nouvelle
        self.assertEqual(Evenement.query.count(), 3)

        # Un deuxieme passage identique n'ajoute plus rien.
        with patch.object(cron, 'recuperer_incendies', return_value=(recues, None)):
            nb, _ = cron.importer_nouvelles_donnees()
        self.assertEqual(nb, 0)


class TestDedoublonnage(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.create_all()
        Evenement.query.delete()
        db.session.commit()
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
        import dedoublonner
        self.script = dedoublonner

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _ajouter(self, jour, lat, lon):
        e = Evenement(date=jour, zone="t", type_evenement="Incendie", latitude=lat, longitude=lon)
        db.session.add(e)
        db.session.commit()
        return e.id

    def test_supprime_les_doublons_en_gardant_le_plus_ancien(self):
        jour = date(2026, 10, 20)
        lat, lon = 12.34567, 123.45678
        # Trois copies du meme point (valeurs relues legerement differentes), plus des lignes a conserver.
        ids = [self._ajouter(jour, v, lon) for v in (lat, simple_precision(lat), simple_precision(lat))]
        distinct = self._ajouter(jour, 50.0, 5.0)
        autre_jour = self._ajouter(jour + timedelta(days=1), lat, lon)
        sans_coordonnees = self._ajouter(jour, None, None)

        self.assertEqual(self.script.compter_doublons(jour), 2)
        self.assertEqual(Evenement.query.count(), 6)  # la simulation ne supprime rien

        self.assertEqual(self.script.supprimer_doublons(jour), 2)
        restants = {e.id for e in Evenement.query.all()}
        self.assertEqual(restants, {ids[0], distinct, autre_jour, sans_coordonnees})
        self.assertEqual(self.script.compter_doublons(jour), 0)  # idempotent


if __name__ == '__main__':
    unittest.main()
