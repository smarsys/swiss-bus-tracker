# Déploiement

## Déploiement Jelastic / Infomaniak

### Création de l'environnement

1. Connectez-vous au [panel Jelastic Infomaniak](https://jca.infomaniak.com/)
2. Créez un nouvel environnement **Python 3.12**
3. Topologie recommandée :
   - 1x Application Server Python (uvicorn)
   - Pas besoin de base de données
   - Optionnel : un noeud Apache/Nginx en frontal (reverse proxy)

### Import du code

- **Via Git** : dans le panneau de déploiement, ajoutez le repo `https://github.com/smarsys/swiss-bus-tracker.git` (branche `main`)
- **Via SSH** : `git clone` dans le répertoire de l'application

### Variables d'environnement

Configurez dans le panel Jelastic → Variables d'environnement :

| Variable | Obligatoire | Valeur par défaut | Description |
|----------|-------------|-------------------|-------------|
| `OJP_API_KEY` | Oui | — | Clé API opentransportdata.swiss |
| `OJP_ENDPOINT` | Non | `https://api.opentransportdata.swiss/ojp20` | Endpoint OJP |
| `CACHE_TTL_SECONDS` | Non | `20` | Durée du cache en secondes |
| `USER_AGENT` | Non | `swiss-bus-tracker/0.1` | User-Agent pour l'API OJP |
| `CORS_ORIGINS` | Non | _(vide)_ | Origines CORS autorisées (ex: `https://bus.tondomaine.ch`) |
| `PORT` | Non | `8000` | Port d'écoute (Jelastic le définit automatiquement) |
| `WORKERS` | Non | `2` | Nombre de workers uvicorn |

### Commande de démarrage

```bash
bash start.sh
```

### Healthcheck

Endpoint : `GET /health` → `{"status": "ok", "version": "0.2.0"}`

---

## Sous-domaine custom

1. Dans le panel Jelastic, ajoutez le sous-domaine `bus.tondomaine.ch` à l'environnement
2. Dans le panel DNS Infomaniak, créez un enregistrement CNAME :
   ```
   bus  →  <votre-env>.jelastic.infomaniak.com
   ```
3. Activez **Let's Encrypt SSL** automatique dans le panel Jelastic (section SSL)

---

## Mise à jour

### Manuelle

```bash
cd /path/to/app
git pull origin main
# Redémarrer le noeud Python dans le panel Jelastic
```

### Automatique (webhook)

Configurez un webhook GitHub → Jelastic deploy hook pour déclencher un redéploiement automatique à chaque push sur `main`. Voir la [documentation Jelastic](https://docs.jelastic.com/git-svn-auto-deploy/).

---

## Déploiement alternatif via Docker

### Build et test local

```bash
docker build -t swiss-bus-tracker .
docker run --rm -p 8080:8080 -e OJP_API_KEY=your_key_here swiss-bus-tracker
# Vérifier : curl http://localhost:8080/health
```

Le conteneur expose le port `8080` par défaut et inclut un healthcheck intégré (`/health`).

### Jelastic Custom Container

1. Dans le panel Jelastic, créez un environnement de type **Custom Docker Container**
2. Pointez vers votre image :
   - Build depuis le repo GitHub directement, ou
   - Publiez l'image sur Docker Hub / GitHub Container Registry puis référencez-la
3. Variables d'environnement à configurer dans le panel (même tableau que ci-dessus)
4. Le port `8080` est exposé par défaut — configurez le mapping dans Jelastic si nécessaire
5. Le healthcheck Docker est déjà configuré (`curl /health` toutes les 30s)
