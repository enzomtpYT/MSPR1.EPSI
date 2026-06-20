# MSPR1.EPSI - Plateforme HealthAI Coach

HealthAI Coach est une plateforme sante/fitness basee sur une architecture microservices.

Elle regroupe:

- Un frontend Vue.js pour les utilisateurs et les operations admin
- Un backend FastAPI pour l'authentification, les API metier, les analytics et les exports
- Un service ETL qui ingere des fichiers CSV de facon asynchrone via RabbitMQ
- Un microservice IA (FastAPI) pour les recommandations nutritionnelles et sportives
- Une base PostgreSQL pour la persistance des donnees
- Une base MongoDB pour le stockage des recommandations IA
- Un broker RabbitMQ pour decoupler l'ingestion et le traitement
- Une stack d'observabilite complete (Prometheus + Grafana + cAdvisor + exporters)

Ce depot est la racine d'orchestration de tous les services.

## Sommaire

- Vue d'ensemble du projet
- Ce que fait l'application
- Architecture
- Modele conceptuel de donnees (MCD)
- Stack technique
- Structure du repository
- Prerequis
- Variables d'environnement
- Lancer avec Docker (recommande)
- Setup local (sans stack Docker complete)
- Flux d'import ETL
- Utilisation de l'API et documentation
- Monitoring et Observabilite
- Tests
- Depannage
- Evolutions possibles

## Vue d'ensemble du projet

La plateforme couvre les besoins suivants:

- Gestion des comptes utilisateurs avec authentification JWT
- Operations CRUD sur nutrition, produits, equipements, entrainements et mesures biometrie
- Donnees analytics pour le dashboard
- Exports CSV pour les besoins administratifs / compliance
- Pipelines d'ingestion CSV pour injecter des jeux de donnees externes

Le systeme est decoupe en services independants afin de faciliter l'evolution, le deploiement et la scalabilite.

## Ce que fait l'application

L'application fonctionne selon deux modes principaux.

1. Usage interactif (frontend + backend):
- L'utilisateur se connecte et manipule ses donnees via l'interface web.
- Le frontend appelle l'API FastAPI exposee sous /api/v0.
- Le backend gere auth, validation, logique metier et acces base.

2. Ingestion en masse (backend + RabbitMQ + ETL worker):
- Un fichier CSV est charge via l'endpoint backend /api/v0/etl/upload.
- Le backend detecte le type de CSV et publie les lignes dans une file:
  - daily_food_queue
  - diet_rec_queue
  - exercise_queue
- Les consumers ETL lisent les messages puis inserent/transforment les donnees en base PostgreSQL.

## Architecture

```text
Navigateur (Vue 3 + Vite)
        |
        v
Container Frontend (nginx)
        |
        v
Backend FastAPI (/api/v0)              AI Microservice (/api/v1)
   |                    \                    |
   | REST + SQLAlchemy   \ pub CSV           | ML + LLM
   v                      v                  v
PostgreSQL <--------- RabbitMQ          MongoDB
                          |
                          v
                    ETL Worker (3 consumers)

─── Observabilite ───────────────────────────────────
Prometheus  <──  cAdvisor (metriques Docker)
            <──  postgres-exporter
            <──  mongodb-exporter
            <──  rabbitmq (plugin prometheus)
            <──  backend /metrics
            <──  ai-microservice /metrics
     |
     v
  Grafana (dashboards pre-provisionnes)
```

## Modele conceptuel de donnees (MCD)

Le schema Merise du domaine metier (utilisateurs, produits, equipements, logs nutrition/exercice/biometrie) est disponible ci-dessous:

![MCD HealthAI Coach](MSPR1.EPSI-FastAPI/docs/MeriseMCD.png)

Fichier source:

- `MSPR1.EPSI-FastAPI/docs/MeriseMCD.png`

Services definis dans docker-compose:

- database: PostgreSQL 15
- rabbitmq: RabbitMQ 3.11 + interface de management + plugin prometheus
- backend: service FastAPI (expose /metrics)
- etl-worker: worker Python avec 3 consumers
- frontend: application Vue build avec Vite et servie par nginx
- mongodb: MongoDB 7 pour le microservice IA
- ai-microservice: FastAPI pour les recommandations IA (expose /metrics)
- prometheus: collecte et stockage des metriques
- grafana: dashboards de supervision (provisionnes automatiquement)
- cadvisor: metriques de consommation des conteneurs Docker
- postgres-exporter: exporteur de metriques PostgreSQL
- mongodb-exporter: exporteur de metriques MongoDB

Le frontend est deploye avec nginx en mode SPA: toutes les routes non statiques renvoient vers `index.html`, ce qui evite les 404 au rechargement sur `/login` ou toute autre route Vue.

## Stack technique

Frontend:

- Vue 3
- Vite
- TypeScript
- Pinia (state management)
- Vue Router
- Axios
- Bootstrap + Chart.js

Backend:

- Python 3.12+
- FastAPI
- SQLAlchemy
- Alembic
- L'URL de l'API cote navigateur doit etre `http://localhost:8000/api/v0` afin d'eviter un appel vers le nom de service Docker interne `backend`.
- Driver PostgreSQL (psycopg2)
- Auth JWT (python-jose)
- Hash des mots de passe (bcrypt)

ETL:

- Python 3.12+
- Pydantic pour la validation des lignes
- RabbitMQ (pika)
- psycopg2 pour les ecritures PostgreSQL
- Mode worker multiprocessing

Infra / DevOps:

- Docker et Docker Compose
- nginx (runtime frontend)
- uv (image/runtime Python dans les Dockerfiles)

Monitoring / Observabilite:

- Prometheus (collecte de metriques)
- Grafana (visualisation et dashboards)
- cAdvisor (metriques Docker / conteneurs)
- postgres-exporter (metriques PostgreSQL)
- mongodb-exporter (metriques MongoDB)
- rabbitmq_prometheus (plugin natif RabbitMQ)
- prometheus-fastapi-instrumentator (instrumentation FastAPI)

## Structure du repository

```text
MSPR1.EPSI/
├── docker-compose.yml               # Orchestration des services
├── .env.example                     # Template d'env partage
├── ETL/                             # Microservice ETL
│   ├── Dockerfile
│   ├── worker.py                    # Lance tous les consumers
│   ├── consumers/
│   │   ├── daily_food_consumer.py
│   │   ├── diet_rec_consumer.py
│   │   └── exercise_consumer.py
│   └── schemas.py                   # Schemas de lignes en entree
├── MSPR1.EPSI-FastAPI/              # Microservice backend
│   ├── Dockerfile
│   ├── alembic/
│   ├── src/
│   │   ├── app.py
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── models/
│   │   ├── router/
│   │   └── test/
│   └── docs/
├── ai-microservice/                 # Microservice IA
│   ├── Dockerfile
│   └── src/
│       ├── app.py
│       ├── config.py
│       ├── models/
│       └── router/
├── frontmspr/                       # Microservice frontend
│   ├── Dockerfile
│   ├── src/
│   └── package.json
└── monitoring/                      # Stack d'observabilite
    ├── prometheus/
    │   └── prometheus.yml           # Configuration scrape targets
    └── grafana/
        ├── provisioning/
        │   ├── datasources/
        │   │   └── datasource.yml   # Datasource Prometheus auto-provisionnee
        │   └── dashboards/
        │       └── dashboard.yml    # Provider de dashboards
        └── dashboards/
            ├── fastapi-services.json     # Dashboard FastAPI (backend + AI)
            ├── docker-cadvisor.json      # Dashboard Docker / cAdvisor
            └── databases-rabbitmq.json   # Dashboard PostgreSQL / MongoDB / RabbitMQ
```

## Prerequis

Minimum:

- Docker Desktop (ou Docker Engine + Compose)

Pour du developpement local sans stack Docker complete:

- Python 3.12+
- Node.js 20.19+ (ou 22.12+)
- npm
- PostgreSQL
- RabbitMQ

## Variables d'environnement

Le fichier racine .env.example contient une configuration partagee pour tous les services.

Etapes:

1. Copier .env.example vers .env a la racine.
2. Adapter les secrets et les URLs a votre environnement.
3. Garder les valeurs DB coherentes:
   - POSTGRES_DB doit correspondre au nom de base dans DATABASE_URL.

Variables principales:

- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_DB
- RABBITMQ_DEFAULT_USER
- RABBITMQ_DEFAULT_PASS
- DATABASE_URL
- RABBITMQ_URL
- SECRET_KEY
- ALGORITHM
- ACCESS_TOKEN_EXPIRE_MINUTES
- DEFAULT_ADMIN_EMAIL
- DEFAULT_ADMIN_PASSWORD
- DEFAULT_ADMIN_IS_ADMIN
- VITE_API_URL
- VITE_APP_NAME
- GF_SECURITY_ADMIN_PASSWORD (mot de passe admin Grafana, defaut: admin)

If DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD are set, the backend creates that user automatically at startup after migrations are applied. Leave them empty to disable automatic seeding.

## Lancer avec Docker (recommande)

Lancement de tous les microservices depuis la racine du repository.

1. Creer le fichier d'environnement:

```bash
cp .env.example .env
```

2. Builder et demarrer tous les services:

```bash
docker compose up --build
```

3. Acces aux services:

- Frontend: http://localhost
- API backend: http://localhost:8000
- Swagger: http://localhost:8000/docs
- AI Microservice: http://localhost:8001
- Swagger AI: http://localhost:8001/docs
- RabbitMQ management: http://localhost:15672
- Grafana: http://localhost:3000 (login: admin / mot de passe: voir GF_SECURITY_ADMIN_PASSWORD)
- Prometheus: http://localhost:9090
- cAdvisor: http://localhost:8080

4. Initialiser le schema DB (premier lancement / changement schema):

```bash
docker compose exec backend alembic upgrade head
```

Le backend cree aussi automatiquement l'utilisateur admin defini par DEFAULT_ADMIN_EMAIL et DEFAULT_ADMIN_PASSWORD au demarrage. Si ces variables sont vides, aucun compte par defaut n'est cree.

Commandes utiles:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f etl-worker
docker compose down
docker compose down -v
```

## Setup local (sans stack Docker complete)

Vous pouvez lancer chaque service separement pour le developpement.

### 1) Demarrer base + RabbitMQ

Utiliser Docker uniquement pour l'infra:

```bash
docker compose up -d database rabbitmq
```

### 2) Backend (FastAPI)

Depuis MSPR1.EPSI-FastAPI:

```bash
cp .env.example .env
pip install -e ".[dev]"
alembic upgrade head
fastapi dev src/app.py
```

URL backend:

- http://localhost:8000

### 3) ETL worker

Depuis ETL:

```bash
cp .env.example .env
pip install -e .
python worker.py
```

### 4) Frontend

Depuis frontmspr:

```bash
cp .env.example .env.local
npm install
npm run dev
```

URL frontend dev (par defaut Vite):

- http://localhost:5173

## Flux d'import ETL

Endpoint d'upload:

- POST /api/v0/etl/upload

Detection des schemas CSV supportes:

- daily_food_queue si les colonnes incluent Food_Item et Calories (kcal)
- diet_rec_queue si les colonnes incluent Patient_ID et Diet_Recommendation
- exercise_queue si les colonnes incluent Max_BPM et Workout_Type

Comportement des consumers:

- daily_food_consumer:
  - Valide les lignes avec DailyFoodRow
  - Insere les lignes dans la table products

- diet_rec_consumer:
  - Valide les lignes avec DietRecRow
  - Cree/met a jour des users avec email patient genere

- exercise_consumer:
  - Valide les lignes avec ExerciseRow
  - Cree un user technique + workout_session + biometrics_log

## Utilisation de l'API et documentation

Prefixe principal API:

- /api/v0

Domaines principaux:

- users
- products
- equipment
- meal_log
- workout_session
- biometrics_log
- analytics
- exports
- etl

Documentation:

- Swagger UI: /docs
- OpenAPI JSON: /openapi.json
- Doc fonctionnelle backend: MSPR1.EPSI-FastAPI/docs/endpoints.md

Flux d'authentification:

1. Creer un utilisateur via POST /api/v0/users/
2. Se connecter via POST /api/v0/users/login
3. Envoyer Authorization: Bearer <token> sur les routes protegees

## Monitoring et Observabilite

La stack de monitoring est deployee automatiquement avec `docker compose up`. Elle comprend:

### Composants

| Service | Role | Port |
|---|---|---|
| Prometheus | Collecte et stockage des metriques (scrape toutes les 15s) | 9090 |
| Grafana | Dashboards de visualisation | 3000 |
| cAdvisor | Metriques Docker (CPU, RAM, reseau, disque) | 8080 |
| postgres-exporter | Metriques PostgreSQL (connexions, transactions, taille) | 9187 |
| mongodb-exporter | Metriques MongoDB (connexions, operations) | 9216 |
| RabbitMQ plugin | Metriques files de messages (plugin natif rabbitmq_prometheus) | 15692 |

### Dashboards pre-provisionnes

Trois dashboards Grafana sont disponibles des le premier demarrage :

1. **FastAPI Services** : Sante des services, taux de requetes, latence p95, requetes en cours, taille des reponses.
2. **Docker Containers (cAdvisor)** : CPU, memoire, reseau et utilisation disque par conteneur.
3. **Databases & RabbitMQ** : Connexions PostgreSQL, taille des bases, transactions/s, cache hit ratio, connexions MongoDB, operations MongoDB, profondeur des files RabbitMQ, debit de messages.

### Instrumentation des API

Les deux services FastAPI (backend et ai-microservice) exposent leurs metriques Prometheus sur la route `/metrics` grace au package `prometheus-fastapi-instrumentator`.

### Verification de la stack

1. Verifier les cibles Prometheus : http://localhost:9090/targets (toutes doivent etre "UP")
2. Acceder a Grafana : http://localhost:3000 (admin / admin par defaut)
3. Les dashboards sont dans le dossier "HealthAI Coach"

## Tests

Suite de tests backend:

Depuis MSPR1.EPSI-FastAPI:

```bash
pytest src/test -q
```

Exemple avec couverture:

```bash
pytest src/test --cov=src --cov-report=term-missing --cov-report=html
```

Le repository ne contient pas actuellement de script de tests frontend dans package.json.

## Depannage

1) Le frontend ne joint pas le backend

- Verifier la valeur de VITE_API_URL.
- En Docker, utiliser la cible backend du reseau compose dans les args/env.
- Verifier les logs backend: docker compose logs -f backend.

2) Erreurs de connexion base de donnees

- Verifier la coherence DATABASE_URL / POSTGRES_DB.
- Verifier l'etat du container database: docker compose ps.
- Rejouer les migrations: docker compose exec backend alembic upgrade head.

3) Upload ETL accepte mais pas de donnees en base

- Verifier les logs worker: docker compose logs -f etl-worker.
- Verifier que les headers CSV correspondent a un schema supporte.
- Verifier RabbitMQ et les credentials utilises dans RABBITMQ_URL.

4) Conflits de ports (80, 8000, 5432, 5672, 15672, 3000, 8080, 9090)

- Arreter les services locaux qui occupent ces ports ou changer les mappings dans docker-compose.yml.

5) Grafana n'affiche pas de dashboards

- Verifier que le volume `./monitoring/grafana/dashboards` est correctement monte.
- Verifier que le fichier `monitoring/grafana/provisioning/dashboards/dashboard.yml` existe.
- Redemarrer Grafana : `docker compose restart grafana`.

## Evolutions possibles

- Ajouter des endpoints de healthcheck backend et ETL
- Ajouter une strategie robuste d'injection d'env frontend au runtime
- Ajouter une CI complete (lint/test/build) sur chaque microservice
- ~~Ajouter de l'observabilite (logs structures, metrics, traces)~~ ✅ Stack Prometheus + Grafana deployee
- Ajouter du tracing distribue (OpenTelemetry / Jaeger)
- Ajouter des regles d'alerte Prometheus (AlertManager)
- Ajouter des scripts de seed et datasets de demo pour onboarding rapide
