# ETL - HealthAI Coach

Service ETL (Extract, Transform, Load) du projet MSPR1.EPSI, charge de traiter des lignes CSV publiees sur RabbitMQ puis de les injecter dans PostgreSQL.

Ce microservice fonctionne de maniere asynchrone avec 3 consumers dedies:

- `daily_food_consumer` pour les donnees nutritionnelles
- `diet_rec_consumer` pour les recommandations alimentaires patient
- `exercise_consumer` pour les donnees d'entrainement

## Sommaire

- [ETL - HealthAI Coach](#etl---healthai-coach)
  - [Sommaire](#sommaire)
  - [Objectif du service](#objectif-du-service)
  - [Comment fonctionne l'ETL](#comment-fonctionne-letl)
  - [Architecture technique](#architecture-technique)
  - [Structure du dossier](#structure-du-dossier)
  - [Prerequis](#prerequis)
  - [Configuration](#configuration)
  - [Execution](#execution)
    - [Mode local (service ETL seul)](#mode-local-service-etl-seul)
    - [Mode Docker Compose (stack complete)](#mode-docker-compose-stack-complete)
  - [Schemas de donnees supportes](#schemas-de-donnees-supportes)
    - [Daily Food](#daily-food)
    - [Diet Recommendation](#diet-recommendation)
    - [Exercise](#exercise)
  - [Comportement par consumer](#comportement-par-consumer)
    - [1) `daily_food_consumer`](#1-daily_food_consumer)
    - [2) `diet_rec_consumer`](#2-diet_rec_consumer)
    - [3) `exercise_consumer`](#3-exercise_consumer)
  - [Logs et supervision](#logs-et-supervision)
  - [Depannage](#depannage)
  - [Limites connues](#limites-connues)

## Objectif du service

Le service ETL a pour role de:

- consommer des messages JSON depuis RabbitMQ
- valider chaque ligne avec des schemas Pydantic
- transformer certaines valeurs (formats, unites, donnees derivees)
- inserer ou mettre a jour les donnees dans la base PostgreSQL metier

Il est pense pour fonctionner en parallele du backend FastAPI, qui se charge de l'upload des CSV et de la publication des messages vers les files RabbitMQ.

## Comment fonctionne l'ETL

Flux global:

1. Un fichier CSV est envoye via l'endpoint backend `/api/v0/etl/upload`.
2. Le backend detecte le type de CSV et publie chaque ligne dans une file RabbitMQ:
	- `daily_food_queue`
	- `diet_rec_queue`
	- `exercise_queue`
3. Le service ETL lance 3 processus workers en parallele (`worker.py`).
4. Chaque consumer lit sa file, valide la ligne, puis ecrit en base.
5. Le message est acquitte (`ack`) pour sortir de la file.

## Architecture technique

```text
Backend FastAPI (/api/v0/etl/upload)
					 |
					 v
RabbitMQ (3 files) -------------------------------+
  - daily_food_queue                              |
  - diet_rec_queue                                |
  - exercise_queue                                |
																	v
ETL worker (multiprocessing, 3 consumers) ----> PostgreSQL
```

Points importants:

- Le worker principal demarre 3 processus Python isoles.
- Chaque consumer declare sa queue (`durable=true`) et utilise `prefetch_count=10`.
- Les erreurs de validation n'interrompent pas le service: la ligne est loggee puis acquittee.

## Structure du dossier

```text
ETL/
├── worker.py                          # Lance les 3 consumers en parallele
├── publisher.py                       # Utilitaire connexion RabbitMQ
├── schemas.py                         # Schemas Pydantic des lignes entrantes
├── consumers/
│   ├── daily_food_consumer.py         # Insertion des produits nutrition
│   ├── diet_rec_consumer.py           # Creation / MAJ utilisateurs patient
│   └── exercise_consumer.py           # Insertion workout + biometrics
├── pyproject.toml                     # Dependances Python
└── .env.example                       # Variables d'environnement exemple
```

## Prerequis

- Python 3.12+
- PostgreSQL accessible
- RabbitMQ accessible

Dans le mode recommande du projet, PostgreSQL et RabbitMQ sont demarres via `docker compose` a la racine du repository.

## Configuration

1. Copier le fichier d'environnement:

```bash
cp .env.example .env
```

2. Adapter au besoin les variables principales:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mspr_db
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

Remarque:

- L'ETL lit directement `DATABASE_URL` et `RABBITMQ_URL` depuis l'environnement.
- Les autres variables presentes dans `.env.example` (JWT / frontend) viennent de la configuration partagee du projet et ne sont pas utilisees directement par les consumers ETL.

## Execution

### Mode local (service ETL seul)

Depuis le dossier `ETL/`:

```bash
pip install -e .
python worker.py
```

Le worker reste actif et ecoute les 3 queues RabbitMQ.

### Mode Docker Compose (stack complete)

Depuis la racine `MSPR1.EPSI/`:

```bash
docker compose up --build
```

Pour suivre les logs ETL:

```bash
docker compose logs -f etl-worker
```

## Schemas de donnees supportes

Les messages attendus doivent correspondre aux colonnes ci-dessous (alias Pydantic).

### Daily Food

- `Food_Item`
- `Calories (kcal)`
- `Protein (g)`
- `Carbohydrates (g)`
- `Fat (g)`
- `Fiber (g)`
- `Sugars (g)`
- `Sodium (mg)`
- `Cholesterol (mg)`
- `Category` (optionnel)
- `Meal_Type` (optionnel)

### Diet Recommendation

- `Patient_ID`
- `Age`
- `Gender`
- `Weight_kg`
- `Height_cm`
- `Allergies` (optionnel)
- `Dietary_Restrictions` (optionnel)
- `Diet_Recommendation` (optionnel)

### Exercise

- `Age`
- `Gender`
- `Weight (kg)`
- `Height (m)`
- `Max_BPM`
- `Avg_BPM`
- `Resting_BPM`
- `Session_Duration (hours)`
- `Workout_Type`

## Comportement par consumer

### 1) `daily_food_consumer`

- Lit `daily_food_queue`
- Valide via `DailyFoodRow`
- Insere dans la table `products`

Mapping principal:

- `Food_Item` -> `product_name`
- `Calories (kcal)` -> `product_kcal`
- `Protein (g)` -> `product_protein`
- `Carbohydrates (g)` -> `product_carbs`
- `Fat (g)` -> `product_fat`
- `Fiber (g)` -> `product_fiber`
- `Sugars (g)` -> `product_sugar`
- `Sodium (mg)` -> `product_sodium`
- `Cholesterol (mg)` -> `product_chol`
- `Category` -> `product_diet_tags`
- `Meal_Type` -> `product_price_category`

### 2) `diet_rec_consumer`

- Lit `diet_rec_queue`
- Valide via `DietRecRow`
- Genere un email technique: `patient_<Patient_ID>@etl.local`
- Si utilisateur absent: creation dans `users`
- Si utilisateur present: mise a jour des attributs metier

Transformation notable:

- `Height_cm` est converti en metres si la valeur est > 3.0

### 3) `exercise_consumer`

- Lit `exercise_queue`
- Valide via `ExerciseRow`
- Cree un utilisateur technique unique `tracker_<uuid>@etl.local`
- Insere une ligne dans `workout_sessions`
- Insere une ligne dans `biometrics_logs`

Transformations notables:

- `Session_Duration (hours)` -> duree en minutes (`int(hours * 60)`)
- La date de session/log est fixee au jour courant (UTC)

## Logs et supervision

Les scripts utilisent le module standard `logging` avec niveau `INFO` par defaut.

Evenements traces:

- demarrage de chaque process
- connexion RabbitMQ
- reception de message
- erreurs de validation JSON/Pydantic
- erreurs SQL (avec rollback)
- commit des transactions reussies

## Depannage

1. Aucun message n'est traite

- Verifier que le backend publie bien dans les queues RabbitMQ.
- Verifier la valeur de `RABBITMQ_URL`.
- Verifier les logs du container `etl-worker`.

2. Erreurs de connexion PostgreSQL

- Verifier `DATABASE_URL`.
- Verifier que la base est demarree.
- Verifier que les migrations backend ont ete appliquees (`alembic upgrade head`).

3. Messages recus mais rejetes

- Verifier les noms exacts des colonnes CSV (alias attendus par `schemas.py`).
- Verifier les types (ex: nombres, champs obligatoires).

4. Le worker quitte immediatement

- Consulter les logs au demarrage pour identifier le consumer en echec.
- Verifier l'accessibilite RabbitMQ depuis l'environnement d'execution.

## Limites connues

- Les insertions ne sont pas idempotentes pour tous les flux (risque de doublons selon le dataset).
- Les erreurs SQL sont loggees mais les lignes invalides ne sont pas stockees dans une dead-letter queue.
- Le service ne fournit pas encore d'endpoint de healthcheck dedie.

