# Job Hunter Automation

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.103+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/Licence-MIT-green?style=for-the-badge)
![Version](https://img.shields.io/badge/Version-1.0.0-blue?style=for-the-badge)

> Pipeline automatisé de recherche d'emploi : scraping quotidien, scoring hybride (mots-clés + IA) et notifications Discord.

---

## Sommaire

1. [Présentation](#1-présentation)
2. [Fonctionnalités](#2-fonctionnalités)
3. [Architecture](#3-architecture)
4. [Stack technique](#4-stack-technique)
5. [Installation rapide](#5-installation-rapide)
6. [Configuration](#6-configuration)
7. [Utilisation](#7-utilisation)
8. [API REST](#8-api-rest)
9. [Structure du projet](#9-structure-du-projet)
10. [Personnalisation](#10-personnalisation)
11. [Roadmap](#11-roadmap)

---

## 1. Présentation

### Le problème

Chercher un emploi, c'est répéter chaque jour les mêmes actions : ouvrir 5 sites, scroller des dizaines d'offres, lire des fiches de poste, évaluer si ça correspond... Ça prend du temps, c'est répétitif, et on finit par rater des opportunités.

### La solution

**Job Hunter Automation** fait tout ça à ta place, tous les matins à 9h :

1. Il **scrape** les nouvelles offres depuis Welcome to the Jungle et LinkedIn (via alertes email)
2. Il **élimine** les offres non pertinentes avec un scoring par mots-clés (gratuit, sans IA)
3. Il **expose** les offres restantes à un agent IA via une API REST pour un scoring fin
4. Il **t'envoie** sur Discord les offres avec un score >= 70%, avec un résumé et un lien direct

Tu te réveilles, tu ouvres Discord, tu as tes offres du jour. Tu postules.

---

## 2. Fonctionnalités

| Fonctionnalité | Description | Statut |
|---|---|---|
| Scraping WTTJ | Recherche via l'API Algolia de Welcome to the Jungle | v1 |
| Alertes LinkedIn | Parsing des emails d'alerte LinkedIn via Gmail API | v1 |
| Pré-filtre mots-clés | Scoring algorithmique sans IA (0 coût) | v1 |
| Scoring IA | API REST pour scoring par un agent IA externe (OpenClaw) | v1 |
| Notifications Discord | Envoi des offres pertinentes via webhook | v1 |
| Déduplication | Hash SHA256 pour éviter les doublons | v1 |
| Nettoyage auto | Suppression des offres > 30 jours | v1 |
| Base SQLite | Stockage léger et portable | v1 |
| Logs avec rotation | Rotation automatique sur 7 jours | v1 |
| Auto-candidature | Postuler automatiquement aux meilleures offres | Roadmap |
| Scraper Indeed | Support d'Indeed | Roadmap |
| Interface web | Dashboard de suivi des offres | Roadmap |

---

## 3. Architecture

### 3.1 Flux global

```
 ┌─────────────────────────────────────────────────────────────┐
 │                   CRON QUOTIDIEN (9h00)                     │
 │                python -m src.main --scrape-only             │
 └─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
  ┌─────────────────────┐         ┌─────────────────────┐
  │   Scraper WTTJ      │         │   Parser Gmail      │
  │   (API Algolia)     │         │   (Alertes LinkedIn)│
  └─────────────────────┘         └─────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
              ┌───────────────────────────────┐
              │   Déduplication (SHA256)      │
              │   Stockage SQLite             │
              └───────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   Pré-filtre mots-clés        │
              │   Score algorithmique 0-100   │
              │   Élimine les < 30%           │
              └───────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   API REST (FastAPI)          │
              │   GET  /api/jobs/pending      │
              │   POST /api/jobs/scores       │
              └───────────────────────────────┘
                              │
                         Agent IA (OpenClaw)
                         Score IA 0-100
                              │
                              ▼
              ┌───────────────────────────────┐
              │   Score final =               │
              │   30% mots-clés + 70% IA      │
              └───────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   Score >= 70% ?              │
              │   OUI → Discord webhook       │
              │   NON → Archive               │
              └───────────────────────────────┘
```

### 3.2 Système de scoring hybride

Le scoring fonctionne en deux étapes pour minimiser les coûts IA :

| Étape | Méthode | Coût | Rôle |
|---|---|---|---|
| **Pré-filtre** | Algorithme mots-clés | Gratuit | Élimine ~60-70% des offres non pertinentes |
| **Scoring fin** | Agent IA via API | Quelques centimes/jour | Évalue finement les offres restantes |

Le pré-filtre utilise un système de poids configurable :
- **Compétences requises** (Power BI, SQL) : poids élevé, éliminatoire si absentes
- **Compétences importantes** (DAX, Python) : poids moyen
- **Compétences bonus** (Dashboard, KPI) : poids faible
- **Compétences non maîtrisées** (DBT, SAS) : malus si requises dans l'offre
- **Mots-clés éliminatoires** (Senior, Lead, 10 ans) : score = 0

---

## 4. Stack technique

| Composant | Technologie | Justification |
|---|---|---|
| Langage | Python 3.11+ | Écosystème scraping riche, facile à maintenir |
| Base de données | SQLite via SQLAlchemy | Léger, portable, zéro config serveur |
| API | FastAPI | Rapide, async, documentation OpenAPI auto |
| Scraping WTTJ | requests + Algolia API | Stable, pas de Selenium nécessaire |
| Email parsing | Google Gmail API | Fiable, OAuth 2.0 |
| Notifications | Discord Webhook | Gratuit, simple, push instantané |
| HTTP client | httpx | Async-ready, moderne |
| Logging | logging + rotation | Rotation automatique 7 jours |

---

## 5. Installation rapide

### 5.1 Prérequis

- Python 3.11 ou supérieur
- pip
- git
- Un compte Gmail (pour les alertes LinkedIn)
- Un serveur Discord (pour les notifications)

### 5.2 Installation

```bash
# Cloner le projet
git clone https://github.com/Alexandre78500/Job-Hunt-Automation-v2.git
cd Job-Hunt-Automation-v2

# Créer l'environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Créer les dossiers nécessaires
mkdir -p data credentials logs

# Configurer l'environnement
cp .env.example .env
# Éditer .env avec tes valeurs (voir section 6)
```

### 5.3 Vérification

```bash
python -c "from src.utils.config import load_settings, load_profile; print('Installation OK')"
```

---

## 6. Configuration

### 6.1 Variables d'environnement (`.env`)

| Variable | Description | Obligatoire |
|---|---|:-:|
| `DISCORD_WEBHOOK_URL` | URL du webhook Discord | Oui |
| `GMAIL_CREDENTIALS_PATH` | Chemin vers le JSON OAuth Gmail | Oui |
| `GMAIL_TOKEN_PATH` | Chemin vers le token Gmail généré | Oui |
| `OPENCLAW_API_URL` | URL de l'API OpenClaw | Non |

### 6.2 Profil candidat (`config/profile.yaml`)

Ce fichier définit **qui tu es** et **ce que tu cherches**. Le système de scoring l'utilise pour évaluer chaque offre.

```yaml
candidate:
  name: "Alexandre"
  title: "Data Analyst"
  experience_years: 2

search:
  job_titles:
    - "Data Analyst"
    - "Consultant Data"
    - "Power BI"
  locations:
    - "Paris"
    - "Île-de-France"
  contract_types:
    - "CDI"

skills:
  required:
    - keyword: "Power BI"
      weight: 15
  important:
    - keyword: "DAX"
      weight: 10
  nice_to_have:
    - keyword: "Dashboard"
      weight: 4
  not_known:
    - keyword: "DBT"
      penalty: -10
```

Voir `config/profile.yaml` pour la configuration complète.

### 6.3 Configuration globale (`config/settings.yaml`)

| Paramètre | Défaut | Description |
|---|---|---|
| `database.path` | `data/jobs.db` | Chemin de la base SQLite |
| `database.cleanup_days` | `30` | Supprime les offres après N jours |
| `scoring.keyword_prefilter_threshold` | `30` | Score minimum pour passer au scoring IA |
| `scoring.ai_scoring_threshold` | `70` | Score minimum pour notification Discord |
| `scoring.weights.keyword_score` | `0.3` | Poids du score mots-clés dans le score final |
| `scoring.weights.ai_score` | `0.7` | Poids du score IA dans le score final |
| `scraping.wttj.max_pages` | `5` | Pages maximum par requête de recherche |
| `scraping.wttj.delay_between_requests` | `2` | Secondes entre chaque requête (rate limiting) |
| `api.port` | `8000` | Port de l'API REST |

### 6.4 Gmail OAuth

```bash
# 1. Placer le fichier OAuth Google dans credentials/
# 2. Générer le token
python scripts/setup_gmail_oauth.py
```

Voir `AGENT.md` section 4.2 pour les instructions détaillées.

---

## 7. Utilisation

### 7.1 Mode scraping (quotidien)

Lance le scraping, le pré-filtre et le stockage :

```bash
python -m src.main --scrape-only
```

### 7.2 Mode API (permanent)

Lance le serveur FastAPI pour que l'agent IA puisse scorer les offres :

```bash
python -m src.main --api-only
```

L'API est disponible sur `http://localhost:8000`. Documentation interactive sur `http://localhost:8000/docs`.

### 7.3 Cron automatique

```bash
# Ajouter dans crontab -e :
0 9 * * * cd /chemin/vers/projet && .venv/bin/python -m src.main --scrape-only >> logs/cron.log 2>&1
```

### 7.4 Commandes utiles

```bash
# Voir les statistiques
curl http://localhost:8000/api/stats

# Voir les offres en attente de scoring
curl http://localhost:8000/api/jobs/pending?limit=10

# Déclencher un scraping manuellement via l'API
curl -X POST http://localhost:8000/api/trigger-scrape

# Tester le scraper WTTJ
python3 -c "
from src.scrapers.wttj_scraper import WttjScraper
s = WttjScraper('https://www.welcometothejungle.com', ['Data Analyst'], 'Paris, France', 'CDI', max_pages=1)
jobs = s.scrape()
print(f'{len(jobs)} offres trouvées')
"
```

---

## 8. API REST

### 8.1 Endpoints

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/api/jobs/pending` | Offres en attente de scoring IA |
| `POST` | `/api/jobs/scores` | Soumettre les scores IA |
| `GET` | `/api/stats` | Statistiques globales |
| `POST` | `/api/trigger-scrape` | Déclencher un scraping manuel |

### 8.2 Exemples

#### Récupérer les offres à scorer

```bash
curl http://localhost:8000/api/jobs/pending?limit=5&include_prompt=true
```

```json
[
  {
    "id": 42,
    "title": "Data Analyst Power BI",
    "company": "Capgemini",
    "location": "Paris",
    "contract_type": "CDI",
    "description": "...",
    "keyword_score": 65.3,
    "url": "https://...",
    "prompt": "Evaluate this job offer..."
  }
]
```

#### Soumettre les scores

```bash
curl -X POST http://localhost:8000/api/jobs/scores \
  -H "Content-Type: application/json" \
  -d '{
    "scores": [
      {"job_id": 42, "ai_score": 85, "reasoning": "Bon match Power BI + SQL en ESN."}
    ]
  }'
```

```json
{"updated": 1}
```

---

## 9. Structure du projet

```
Job-Hunt-Automation-v2/
│
├── src/
│   ├── __init__.py
│   ├── main.py                      # Orchestrateur (point d'entrée)
│   │
│   ├── scrapers/
│   │   ├── base_scraper.py          # Classe abstraite + dataclass JobOffer
│   │   ├── wttj_scraper.py          # Scraper WTTJ via Algolia
│   │   └── linkedin_email.py        # Parser des alertes LinkedIn via Gmail
│   │
│   ├── matcher/
│   │   ├── keyword_matcher.py       # Scoring algorithmique par mots-clés
│   │   └── ai_scorer.py             # Construction des prompts pour l'IA
│   │
│   ├── notifier/
│   │   └── discord_notifier.py      # Envoi via webhook Discord
│   │
│   ├── database/
│   │   ├── models.py                # Modèles SQLAlchemy (Job, ScrapeLog)
│   │   └── repository.py            # CRUD + déduplication
│   │
│   ├── api/
│   │   └── routes.py                # Endpoints FastAPI pour OpenClaw
│   │
│   └── utils/
│       ├── config.py                # Chargement YAML + .env
│       ├── deduplication.py         # Hash SHA256, normalisation URL
│       └── logger.py                # Logging avec rotation
│
├── config/
│   ├── profile.yaml                 # Profil candidat (compétences, poids)
│   └── settings.yaml                # Configuration globale
│
├── scripts/
│   └── setup_gmail_oauth.py         # Configuration OAuth Gmail (one-time)
│
├── tests/
│   ├── test_deduplication.py
│   └── test_matcher.py
│
├── data/                            # Base SQLite (gitignore)
├── credentials/                     # OAuth Gmail (gitignore)
├── logs/                            # Logs avec rotation (gitignore)
│
├── PLAN.md                          # Plan de développement détaillé
├── AGENT.md                         # Instructions pour l'agent IA (Orion)
├── README.md                        # Ce fichier
├── requirements.txt
├── .env.example
├── .gitignore
└── run.py                           # Lanceur alternatif
```

---

## 10. Personnalisation

### 10.1 Modifier le profil candidat

Édite `config/profile.yaml` pour changer :
- Les titres de poste recherchés
- Les compétences et leurs poids
- Les mots-clés éliminatoires
- Les bonus et malus

### 10.2 Ajouter un nouveau scraper

1. Crée un fichier dans `src/scrapers/` (ex: `indeed_scraper.py`)
2. Hérite de `BaseScraper` et implémente `scrape()`, `is_available()` et `source_name`
3. Ajoute la configuration dans `config/settings.yaml`
4. Enregistre le scraper dans `src/main.py` > `run_scrape_cycle()`

```python
from .base_scraper import BaseScraper, JobOffer

class IndeedScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "indeed"

    def scrape(self) -> list[JobOffer]:
        # Implémentation...
        pass

    def is_available(self) -> bool:
        # Vérification...
        pass
```

### 10.3 Ajuster les seuils de scoring

Dans `config/settings.yaml` :

```yaml
scoring:
  keyword_prefilter_threshold: 30   # Baisser = plus d'offres passent au scoring IA
  ai_scoring_threshold: 70          # Baisser = plus de notifications Discord
  weights:
    keyword_score: 0.3              # Augmenter = plus de poids aux mots-clés
    ai_score: 0.7                   # Augmenter = plus de poids à l'IA
```

---

## 11. Roadmap

- [ ] Auto-candidature (easy apply LinkedIn / WTTJ)
- [ ] Scraper Indeed
- [ ] Scraper HelloWork / RegionsJob
- [ ] Interface web de suivi des offres
- [ ] Analyse des tendances (salaires, compétences demandées)
- [ ] Génération automatique de lettres de motivation
- [ ] Intégration calendrier pour les entretiens
- [ ] Support Telegram en plus de Discord

---

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

*Développé par Alexandre - Automatiser la recherche d'emploi, un commit à la fois.*
