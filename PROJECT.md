# PROJECT.md — Tracker thermique par satellite

Document de référence pour cadrer les décisions du projet. À relire en début de session, à mettre à jour à chaque décision structurante.

## 1. Vision

Suivre les détections thermiques satellite (NASA FIRMS/VIIRS) dans le monde, avec une carte interactive et un accès aux données brutes pour analyse. Né comme mini-projet d'apprentissage Python/Flask, devenu un vrai outil complet — décision assumée en cours de route (voir §5) de continuer à l'étoffer plutôt que de le clore rapidement.

**Ce que ce projet n'est pas** : un outil d'alerte précoce, un outil professionnel de gestion de crise, une source de vérité sur "où sont les incendies". C'est un outil de visualisation de données ouvertes, avec ses limites documentées (voir §6).

## 2. Stack et pourquoi

| Choix                                | Pourquoi                                                                                                                                                                                     |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Flask (pas Django)                   | Plus proche pédagogiquement de Symfony sans framework, apprentissage brique par brique                                                                                                       |
| SQLite en local, MySQL en production | SQLite suffisant pour développer seul ; MySQL imposé par l'hébergement mutualisé OVH (pas le choix)                                                                                          |
| Leaflet.js                           | Léger, standard, bonne doc, déjà connu via le projet hydro-observatoire                                                                                                                      |
| CGI (`app.cgi`) pour la production   | Pas de vrai support WSGI/Passenger disponible sur l'offre `hosting-pro` — solution de repli fonctionnelle mais avec un vrai coût de performance (relance tout le processus à chaque requête) |

## 3. Architecture : différences local / production

**Ces différences sont volontaires et documentées, pas des oublis** :

- **Base de données** : SQLite (local) vs MySQL 8.4 (prod) — `DATABASE_URL` en variable d'environnement bascule automatiquement
- **Flask** : 3.1.3 en local, 2.2.5 en production — l'hébergement (Python 3.7) ne supporte pas les versions récentes
- **SQLAlchemy** : 2.0 en local, **1.4.49 forcé en production** — 2.0 dépend de `greenlet`, qui nécessite une compilation C impossible sur ce mutualisé (`gcc` absent)
- **pandas** : utilisé dans les scripts locaux (`scripts/import_historique.py`), **banni de `firms.py`** (remplacé par `csv`/`urllib` natifs) — pandas/numpy ne compilent pas sur ce serveur (`failed to map segment from shared object`)

**Piège à ne pas retomber dedans** : toute nouvelle dépendance ajoutée en local doit être testée manuellement sur le serveur (`pip install --user ...`) avant de supposer qu'elle fonctionnera en production — l'environnement OVH est nettement plus restrictif que le local.

## 4. Contraintes réseau de l'hébergement (découvertes à l'usage, coûteuses en temps)

- **Aucun accès distant à MySQL** depuis l'extérieur (confirmé par le support OVH) — toute migration de données doit se faire _depuis_ le serveur, jamais depuis un PC local
- **Le contexte shell/SSH/Cron classique a un accès réseau sortant bloqué** (même vers son propre domaine, même en HTTP simple) — mais **le contexte CGI/web ne l'est pas**
- **Conséquence pratique** : `cron_quotidien.py` (qui appelle FIRMS) fonctionne **directement en tâche Cron OVH classique**, à condition d'utiliser le bon chemin absolu (`www/projets/tracker/...`, pas de raccourci) — pas besoin du détour CGI+curl qu'on a construit puis abandonné
- **Logs Cron** : consultables dans Hébergement → Statistiques et logs → filtre "cron", pas dans l'onglet de configuration lui-même
- **Incident clé FIRMS (08/2026)** : la clé API a été partagée en clair pendant une session de débogage (chat), et une hypothèse de "clé limitée/invalide" a été explorée pour expliquer un trou d'import Cron de 2 jours — écartée après vérification via `mapkey_status`. La clé reste valide, mais par prudence elle devrait être régénérée (bonne pratique après exposition, même pour une clé en lecture seule sur données publiques).

## 5. Décisions d'architecture (historique, pour ne pas revenir dessus sans raison)

- **GDELT abandonné** au profit de FIRMS — rate limiting trop agressif et imprévisible (code conservé dans `archives/` par souci de traçabilité)
- **EFFIS (zones brûlées) abandonné** — trop d'incertitude technique sur la structure WMS, temps investi disproportionné au résultat
- **NOAA HMS Smoke abandonné** — couverture Amérique du Nord uniquement, hors sujet pour un usage centré Europe
- **NASA GIBS (photo satellite réelle) retenu** — fonctionne bien, limites connues et acceptées (zoom max 9, trous de couverture selon les passages satellite)
- **Rétention des données limitée à 180 jours** — calculé pour rester sous le quota MySQL de 2 Go (≈170 octets/ligne, ~50k lignes/jour en moyenne)
- **Historique 2025 supprimé** (3,1M lignes) — décision consciente de ne pas maintenir un historique continu coûteux en stockage ; remplacé par l'idée d'un **widget de comparaison à la demande** (interroger FIRMS en direct pour l'année précédente, sans stocker) — **non encore implémenté**
- **Widget de comparaison N-1 (§7 backlog) : tenté puis abandonné après test utilisateur.** Architecture testée et fonctionnelle (route `/api/comparaison`, `recuperer_incendies()` adaptée avec paramètres `source`/`date_debut`), mais l'affichage carte (panneau + graphique) jugé peu lisible/pratique et retiré. La route a été retirée d'`app.py` ; les paramètres `source`/`date_debut` restent dans `firms.py` (rétrocompatibles, sans effet si non utilisés) au cas où une page stats dédiée reprendrait cette logique plus tard.

## 6. Limites des données (rappel, détail complet dans le README)

Détections thermiques ≠ incendies confirmés. Peuvent être : feux de forêt, sites industriels, torchères, brûlage agricole. La heatmap peut confondre "un gros foyer" et "beaucoup de petits foyers proches" (ex. Afrique). Précision de position ≈375m, variable selon la position dans le passage satellite.

## 6bis. Écarts constatés avec la documentation FIRMS (à ne pas re-découvrir)

- **`DAY_RANGE` réellement limité à 5, pas 10** — la documentation générale de l'API FIRMS annonce `[1..10]`, mais `VIIRS_NOAA20_NRT` refuse au-delà de 5 (message d'erreur constaté : `"Invalid day range. Expects [1..5]"`). Cohérent avec le `jours=5` déjà utilisé dans `cron_quotidien.py` — ce n'était pas arbitraire.
- **NRT vs SP** : les données NRT (temps quasi-réel) ne couvrent que les ~2 derniers mois. Pour toute requête sur une période plus ancienne (ex. comparaison année N-1), il faut utiliser la source `VIIRS_NOAA20_SP` (Standard Processing), pas `VIIRS_NOAA20_NRT`.
- **Erreurs FIRMS peu lisibles par défaut** : `urllib` ne remonte que `HTTP Error 400: Bad Request` sans corps de réponse. Le vrai message d'erreur FIRMS est dans le corps HTTP — nécessite de capturer `urllib.error.HTTPError` explicitement et lire `e.read()` pour voir le détail utile.

## 7. Backlog / feuille de route

**Non fait, discuté et mis en attente** :

- Assistant IA conversationnel (question en langage naturel → requête structurée sécurisée → réponse) — architecture pensée (function calling, jamais de SQL généré directement exécuté), pas commencé, clé API à créer
- Widget de comparaison à l'année précédente, à la demande, sans stockage — architecture esquissée en §5, route `/api/comparaison` à écrire, nécessite d'adapter `firms.py` pour accepter une date de départ précise
- Captures d'écran dans le README (à faire une fois l'UI stabilisée)
- Filtre par précision de pixel (`scan`/`track`) — discuté et **volontairement écarté** (contraire à l'objectif de vue continue), gardé seulement comme information affichée

**Fait cette session, à ne pas refaire** :

- Sécurité (CSRF, limitation de connexion, debug conditionnel)
- Déploiement complet OVH (CGI, MySQL, Git sur serveur)
- Cron quotidien fonctionnel (import + purge)
- KPI dynamique par date, export CSV avec limite de volume (50 000 lignes max, contrainte réelle de performance mutualisée)

## 8. Comment reprendre le contexte en début de session

1. Lire ce fichier en entier avant de proposer une nouvelle fonctionnalité
2. Vérifier le §5 avant de ré-explorer une piste déjà abandonnée
3. Toute nouvelle dépendance Python : tester sur le serveur avant de considérer que c'est acquis
4. Toute modification de `app.py`/`models.py`/`firms.py`/templates : transférer en production (`scp` ou `git pull` depuis le serveur) et vérifier en ligne, pas seulement en local
