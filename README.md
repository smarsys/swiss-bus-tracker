# 🚌 Swiss Bus Tracker

Application web de suivi en temps réel des bus et trains du transport public suisse (CarPostal, CFF, tl, etc.). Utilise l'API OJP 2.0 d'[opentransportdata.swiss](https://opentransportdata.swiss) pour afficher les prochains départs à un arrêt donné, avec heure planifiée, heure réelle, retard et indication si le véhicule est déjà passé.

## Aperçu

- Recherche d'arrêts avec autocomplétion
- Ajout de favoris avec filtre par ligne et direction
- Affichage des 5 prochains départs avec retard en temps réel
- Rafraîchissement automatique toutes les 30 secondes
- Interface mobile-first, responsive

## Prérequis

- Python 3.11+
- Clé API OJP 2.0 (gratuite) — [créer un compte et obtenir une clé](https://opentransportdata.swiss/en/dev-dashboard/)

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditer .env et coller votre clé API
```

## Lancement

```bash
uvicorn app.main:app --reload --port 8000
```

Ouvrir [http://localhost:8000](http://localhost:8000) dans un navigateur.

## Utilisation

1. Tapez le nom d'un arrêt dans la barre de recherche (ex: "Oulens")
2. Sélectionnez l'arrêt dans la liste déroulante
3. Optionnellement, filtrez par numéro de ligne et/ou direction
4. Cliquez "Ajouter" pour créer un favori
5. Les prochains départs s'affichent automatiquement et se rafraîchissent toutes les 30s

## Tests

```bash
pytest
```

## Déploiement

Le projet est prêt pour un déploiement sur Jelastic/Infomaniak ou tout hébergeur supportant Python. Lancez avec :

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Assurez-vous que la variable d'environnement `OJP_API_KEY` est configurée sur le serveur.

## Licence

MIT — Copyright (c) 2026 Cristobal
