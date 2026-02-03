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
      we
