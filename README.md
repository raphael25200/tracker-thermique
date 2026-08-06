# Tracker thermique par satellite

![Statut](https://img.shields.io/badge/statut-en%20d%C3%A9veloppement-orange)
![Python](https://img.shields.io/badge/Python-3.13-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-black)

## English summary

A Flask web application that tracks satellite thermal detections worldwide, using NASA FIRMS (VIIRS) open data. Features an interactive map (clusters, heatmap, true-color satellite imagery via NASA GIBS), a filterable scientific data page with CSV export, and daily/historical import tools. Built as a learning project to move from PHP/Symfony toward Python/Flask, developed with heavy AI-assisted pair-programming (Claude) — see the *Approche de développement* section below for an honest account of what was autonomous vs. assisted. **Important:** this tool detects thermal anomalies, not confirmed wildfires — see *Limites connues*.

---

## À propos

Application web Flask qui centralise et visualise les détections thermiques repérées par satellite dans le monde entier, à partir des données ouvertes **NASA FIRMS** (capteur VIIRS). Le projet propose une carte interactive riche, une page de données scientifiques filtrables avec export CSV, et des outils d'import (quotidien et historique).

Ce projet est né d'un test d'apprentissage Python/Flask (dans la continuité d'un parcours PHP/Symfony) et a progressivement grandi en un vrai outil complet — voir la section *Historique du projet* pour le contexte.

## Fonctionnalités

**Carte interactive** (`/`)
- Trois vues : points groupés (clusters), points détaillés, carte de chaleur (densité cumulée)
- Fonds de carte : plan, imagerie satellite (Esri), photo satellite réelle en couleurs naturelles (NASA GIBS)
- Navigation jour par jour avec calendrier, recherche de lieu
- KPI du jour (total, tendance, pic d'intensité, régions actives) avec repérage visuel du foyer le plus intense
- Panneau d'aide intégré expliquant la lecture des données

**Page données** (`/donnees`)
- Filtres scientifiques complets : période, température, FRP (puissance radiative), confiance de détection, jour/nuit, région
- Pagination, export CSV de la sélection filtrée avec toutes les colonnes (position, satellite, dimensions du pixel, etc.)

**Administration** (connexion requise)
- Import manuel depuis FIRMS (zone mondiale, jusqu'à 5 jours de couverture)
- Script d'import historique par tranches, avec bascule automatique entre données archivées (SP) et temps réel (NRT)
- CRUD complet sur les événements

## Stack technique

- **Backend** : Python, Flask, SQLAlchemy, Flask-Login
- **Base de données** : SQLite (développement) — migration MySQL prévue pour la mise en ligne
- **Frontend** : Jinja2, CSS natif (design system maison), Leaflet.js (cartographie), Flatpickr (calendrier)
- **Données** : [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) (VIIRS NOAA-20), [NASA GIBS](https://wiki.earthdata.nasa.gov/display/GIBS) (imagerie satellite)

## Limites connues (important)

Ce tracker affiche des **détections thermiques**, pas des incendies confirmés. Une détection peut correspondre à :
- un feu de forêt ou de végétation
- une installation industrielle, une torchère de gaz
- un brûlage agricole
- plus rarement, un faux positif (réflexion solaire, etc.)

Autres limites à connaître :
- **Résolution variable** : chaque détection correspond à un pixel satellite d'environ 375 m, mais sa taille réelle varie selon la position dans le passage du satellite (effet "bowtie")
- **Couverture temporelle partielle** : le satellite ne repasse que 1 à 2 fois par jour au-dessus d'un point donné — un import ponctuel peut manquer des événements
- **Carte de chaleur** : une zone rouge peut représenter un seul foyer intense ou de nombreux petits foyers proches (ex. brûlage agricole en Afrique) — la densité cumulée ne distingue pas les deux cas
- **Photo satellite réelle (GIBS)** : résolution limitée à un niveau de zoom modéré, et parfois des zones sans image (le satellite ne couvre pas systématiquement toute la planète chaque jour)

## Installation

```bash
git clone https://github.com/raphael25200/tracker-thermique.git
cd tracker-thermique
python -m venv venv
venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
```

Copier `.env.example` en `.env` et renseigner :
- `FIRMS_API_KEY` — clé gratuite sur [firms.modaps.eosdis.nasa.gov/api](https://firms.modaps.eosdis.nasa.gov/api/)
- `SECRET_KEY` — générer avec `python -c "import secrets; print(secrets.token_hex(32))"`

```bash
python app.py
```

## Historique du projet

Démarré comme mini-projet d'apprentissage Python/Flask (dans la continuité d'un parcours PHP/Symfony), avec pour objectif initial de tester la stack sur quelques jours. Le projet s'est étoffé progressivement : première source de données (GDELT, abandonnée pour cause de limitation de débit trop agressive — voir `archives/`), bascule vers NASA FIRMS, puis ajout de la carte interactive, de l'import historique et des outils d'analyse.

## Approche de développement

Ce projet a été développé en pair-programming avec assistance IA (Claude, Anthropic) — génération de code guidée, avec explications systématiques à chaque étape et débogage actif (lecture de tracebacks, compréhension des erreurs, décisions d'architecture). Ce n'est pas un projet Python entièrement autonome comme [hydro-observatoire](https://github.com/raphael25200/hydro-observatoire), mais ça va au-delà du simple prompt engineering : la compréhension du code produit et les choix techniques (sources de données, structure de la base, compromis performance/précision) sont miens.

## Auteur

Raphaël Navarro — [GitHub](https://github.com/raphael25200) · [LinkedIn](https://www.linkedin.com/in/navarroraphael/)
