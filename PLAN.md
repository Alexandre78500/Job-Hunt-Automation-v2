# Job Hunter Automation - Plan de Développement

> Document de référence pour l'implémentation du projet par les agents IA.
> Dernière mise à jour : 4 février 2026

---

## 1. Vue d'ensemble

### 1.1 Objectif
Automatiser la recherche d'emploi quotidienne en :
1. Scrapant les offres d'emploi depuis plusieurs sources
2. Comparant les offres au profil du candidat via un système de scoring hybride
3. Notifiant les offres pertinentes (≥70% de match) sur Discord

### 1.2 Contexte d'exécution
- **Environnement** : VPS Linux avec OpenClaw (assistant IA open-source)
- **Déclenchement** : Cron job quotidien (scraping séquentiel par plateforme)
- **Intégration** : API REST pour communication avec OpenClaw

### 1.3 Profil cible

| Critère | Valeur |
|---------|--------|
| **Poste recherché** | Data Analyst / Consultant Data / Data Analyst Power BI |
| **Localisation** | Paris / Île-de-France |
| **Type de contrat** | CDI uniquement |
| **Disponibilité** | Immédiate |
| **Cible entreprises** | ESN / Conseil (diversité de missions) |

**Stack technique :**
- **Expert** : Power BI (DAX, Power Query), SQL avancé
- **Confirmé** : Python, Excel
- **Connaissances** : Tableau, Snowflake, Azure, Talend

**Ne connaît PAS** : DBT, SAS, Dataiku, Google Analytics, Data Science/ML avancé

---

## 2. Architecture technique

### 2.1 Stack technologique

| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| Langage | Python 3.11+ | Excellent écosystème scraping, facile à maintenir |
| Base de données | SQLite | Léger, portable, suffisant pour le volume |
| API | FastAPI | Rapide, async, documentation auto (OpenAPI) |
| Scraping | requests + BeautifulSoup | Léger pour WTTJ |
| Email parsing | Google Gmail API | Fiable pour parser les alertes LinkedIn |
| Notifications | Discord Webhook | Simple, gratuit, intégré à l'écosystème |

### 2.2 Diagramme de flux

Le pipeline exécute les scrapers séquentiellement, chacun étant indépendant. Un seul cron
lance tout l'un après l'autre. Le temps d'exécution n'est pas une contrainte.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CRON QUOTIDIEN (un seul cron)                    │
│                           main.py (Orchestrateur)                       │
└─────────────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌──────────────────────┐           ┌──────────────────────────────┐
│  WTTJ Scraper        │           │  LinkedIn Scraper            │
│  (API Algolia)       │           │                              │
│                      │           │  Temps 1: Parser Gmail       │
│  1. Recherche Algolia│           │    → titres, URLs, entreprise│
│  2. Parse résultats  │           │                              │
│  3. Délai: 2s/req    │           │  Temps 2: Fetch fiches       │
│                      │           │    → GET avec cookie li_at   │
└──────────┬───────────┘           │    → Parse HTML complet      │
           │                       │    → Délai: 15s/requête      │
           │                       └──────────────┬───────────────┘
           │                                      │
           ▼                                      ▼
┌──────────────────────┐           ┌──────────────────────────────┐
│ SQLite               │           │ SQLite                       │
│ source="wttj"        │           │ source="linkedin"            │
└──────────┬───────────┘           └──────────────┬───────────────┘
           │                                      │
           └──────────────────┬───────────────────┘
                              ▼
              ┌───────────────────────────────┐
              │     Déduplication (SHA256)     │
              │   + Pré-filtre mots-clés      │
              │   (scoring algorithmique)     │
              │   Élimine les < 30%           │
              └───────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   API REST ← OpenClaw/Orion   │
              │   (scoring IA des 30-100%)    │
              └───────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   Filtre final (≥ 70%)        │
              └───────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   Discord Webhook             │
              │   Récapitulatif groupé        │
              │   par source                  │
              └───────────────────────────────┘
```

### 2.3 Structure du projet

```
Job-Hunter-Automation/
│
├── src/
│   ├── __init__.py
│   ├── main.py                    # Point d'entrée, orchestrateur
│   │
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base_scraper.py        # Classe abstraite BaseScraper
│   │   ├── wttj_scraper.py        # Welcome to the Jungle
│   │   └── linkedin_email.py      # Parser Gmail pour alertes LinkedIn
│   │
│   ├── matcher/
│   │   ├── __init__.py
│   │   ├── keyword_matcher.py     # Scoring algorithmique (pré-filtre)
│   │   └── ai_scorer.py           # Interface vers OpenClaw API
│   │
│   ├── notifier/
│   │   ├── __init__.py
│   │   └── discord_notifier.py    # Webhook Discord
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py              # Modèles SQLAlchemy
│   │   └── repository.py          # CRUD operations
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py              # FastAPI endpoints pour OpenClaw
│   │
│   └── utils/
│       ├── __init__.py
│       ├── deduplication.py       # Génération hash, vérification doublons
│       ├── config.py              # Chargement configuration
│       └── logger.py              # Configuration logging
│
├── config/
│   ├── profile.yaml               # Profil candidat (mots-clés, préférences)
│   └── settings.yaml              # Configuration globale
│
├── data/
│   └── jobs.db                    # Base SQLite (créée automatiquement)
│
├── credentials/
│   └── gmail_credentials.json     # OAuth Gmail (gitignore)
│
├── tests/
│   ├── __init__.py
│   ├── test_scrapers.py
│   ├── test_matcher.py
│   └── test_deduplication.py
│
├── scripts/
│   └── setup_gmail_oauth.py       # Script one-time pour auth Gmail
│
├── requirements.txt
├── .env.example
├── .gitignore
├── PLAN.md
└── README.md
```

---

## 3. Schéma de la base de données

### 3.1 Table `jobs`

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,              -- SHA256 pour déduplication
    
    -- Identifiants
    source TEXT NOT NULL,                   -- 'wttj', 'linkedin'
    external_id TEXT,                       -- ID sur le site source
    url TEXT NOT NULL,
    
    -- Informations de l'offre
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    contract_type TEXT,                     -- 'CDI', 'CDD', 'Freelance', etc.
    salary_min INTEGER,
    salary_max INTEGER,
    description TEXT,                       -- Fiche de poste complète
    
    -- Scoring
    keyword_score REAL,                     -- Score pré-filtre (0-100)
    ai_score REAL,                          -- Score IA OpenClaw (0-100)
    final_score REAL,                       -- Score combiné final
    ai_reasoning TEXT,                      -- Explication du score IA
    
    -- Statut et métadonnées
    status TEXT DEFAULT 'new',              -- 'new', 'scored', 'notified', 'applied', 'ignored'
    detail_status TEXT DEFAULT 'pending',     -- 'pending', 'fetched', 'failed' (pour LinkedIn fetch)
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scored_at TIMESTAMP,
    notified_at TIMESTAMP,
    
    -- Index pour performance
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_source ON jobs(source);
CREATE INDEX idx_jobs_final_score ON jobs(final_score);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
```

### 3.2 Table `scrape_logs` (optionnel, pour monitoring)

```sql
CREATE TABLE scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    jobs_found INTEGER DEFAULT 0,
    jobs_new INTEGER DEFAULT 0,
    jobs_duplicate INTEGER DEFAULT 0,
    error_message TEXT,
    status TEXT DEFAULT 'running'           -- 'running', 'success', 'failed'
);
```

---

## 4. Configuration

### 4.1 Fichier `config/profile.yaml`

```yaml
# Profil candidat pour le scoring

candidate:
  name: "Alexandre"
  title: "Data Analyst"
  experience_years: 2
  availability: "immediate"
  languages:
    - name: "Français"
      level: "native"
    - name: "Anglais"
      level: "professional"

# Critères de recherche
search:
  job_titles:
    - "Data Analyst"
    - "Consultant Data"
    - "Data Analyst Power BI"
    - "Business Intelligence Analyst"
    - "BI Analyst"
    - "Analyste Données"
  
  locations:
    - "Paris"
    - "Île-de-France"
    - "92"  # Hauts-de-Seine
    - "75"  # Paris
    - "Remote"
    - "Télétravail"
  
  contract_types:
    - "CDI"
  
  company_types_preferred:
    - "ESN"
    - "Conseil"
    - "Cabinet de conseil"

# Compétences pour le scoring par mots-clés
skills:
  # Compétences obligatoires (éliminatoire si absent)
  required:
    - keyword: "Power BI"
      weight: 15
      aliases: ["PowerBI", "Power-BI"]
    - keyword: "SQL"
      weight: 12
      aliases: ["SQL Server", "PostgreSQL", "MySQL"]
  
  # Compétences importantes
  important:
    - keyword: "DAX"
      weight: 10
    - keyword: "Power Query"
      weight: 10
      aliases: ["M Language"]
    - keyword: "Python"
      weight: 8
    - keyword: "Excel"
      weight: 5
      aliases: ["VBA", "Tableaux croisés"]
    - keyword: "Tableau"
      weight: 6
      aliases: ["Tableau Software"]
    - keyword: "Snowflake"
      weight: 7
    - keyword: "Azure"
      weight: 6
      aliases: ["Azure Data Factory", "Azure Synapse"]
    - keyword: "Talend"
      weight: 5
  
  # Compétences bonus
  nice_to_have:
    - keyword: "Dashboard"
      weight: 4
      aliases: ["Dashboarding", "Tableaux de bord"]
    - keyword: "KPI"
      weight: 3
      aliases: ["Indicateurs"]
    - keyword: "Reporting"
      weight: 3
    - keyword: "Data Quality"
      weight: 4
      aliases: ["Qualité des données"]
    - keyword: "ETL"
      weight: 4
    - keyword: "Data Warehouse"
      weight: 4
      aliases: ["DWH", "Entrepôt de données"]
  
  # Compétences non maîtrisées (malus si requises)
  not_known:
    - keyword: "DBT"
      penalty: -10
    - keyword: "SAS"
      penalty: -8
    - keyword: "Dataiku"
      penalty: -8
    - keyword: "Google Analytics"
      penalty: -5
    - keyword: "Machine Learning"
      penalty: -5
      aliases: ["ML", "Deep Learning"]
    - keyword: "Data Science"
      penalty: -5

# Mots-clés éliminatoires (offre ignorée si présent)
exclusions:
  titles:
    - "Senior"      # Trop d'expérience requise
    - "Lead"
    - "Manager"
    - "Directeur"
    - "Head of"
  
  requirements:
    - "10 ans"
    - "10+ ans"
    - "8 ans"
    - "expérience significative"
  
  companies:
    []  # Ajouter ici les entreprises à éviter

# Mots-clés bonus
bonuses:
  - keyword: "Junior"
    bonus: 10
  - keyword: "Confirmé"
    bonus: 5
  - keyword: "2 ans"
    bonus: 5
  - keyword: "3 ans"
    bonus: 3
```

### 4.2 Fichier `config/settings.yaml`

```yaml
# Configuration globale de l'application

app:
  name: "Job Hunter Automation"
  version: "1.0.0"
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR

# Configuration base de données
database:
  path: "data/jobs.db"
  cleanup_days: 30  # Supprimer les offres > 30 jours

# Configuration scraping
scraping:
  # Welcome to the Jungle
  wttj:
    enabled: true
    base_url: "https://www.welcometothejungle.com"
    search_queries:
      - "Data Analyst"
      - "Consultant Data"
      - "Power BI"
    location: "Paris, France"
    contract_type: "CDI"
    max_pages: 5  # Pages max par requête
    delay_between_requests: 2  # Secondes
  
  # LinkedIn (via alertes email Gmail + fetch fiches via cookie)
  linkedin:
    enabled: true
    email_label: "LinkedIn Jobs"       # Label Gmail pour filtrer les alertes
    max_emails_per_run: 50
    # Fetch des fiches complètes via cookie li_at
    fetch_details: true                # Activer le fetch des fiches LinkedIn
    delay_between_requests: 15         # Secondes entre chaque fetch (anti-ban)
    max_fetches_per_run: 30            # Max fiches à récupérer par exécution
    user_agents:                       # Rotation de User-Agents réalistes
      - "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      - "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Configuration scoring
scoring:
  # Seuils
  keyword_prefilter_threshold: 30   # Score min pour passer à l'IA
  ai_scoring_threshold: 70          # Score min pour notification
  
  # Pondération score final
  weights:
    keyword_score: 0.3    # 30% score mots-clés
    ai_score: 0.7         # 70% score IA

# Configuration API (pour OpenClaw)
api:
  host: "0.0.0.0"
  port: 8000
  
  # Endpoints
  endpoints:
    get_pending_jobs: "/api/jobs/pending"      # Jobs à scorer
    submit_scores: "/api/jobs/scores"          # Soumettre scores IA
    get_stats: "/api/stats"                    # Statistiques

# Configuration notifications
notifications:
  discord:
    enabled: true
    webhook_url: "${DISCORD_WEBHOOK_URL}"  # Via .env
    
    # Format du message
    embed_color: 0x00D166  # Vert
    include_fields:
      - score
      - company
      - location
      - contract
      - salary
      - ai_reasoning

# Configuration OpenClaw
openclaw:
  # Prompt système pour le scoring IA
  system_prompt: |
    Tu es un assistant spécialisé dans l'évaluation de la pertinence des offres d'emploi.
    Tu dois évaluer si une offre correspond au profil d'un Data Analyst avec 2 ans d'expérience,
    expert en Power BI/DAX/SQL, basé à Paris, cherchant un CDI en ESN/Conseil.
    
    Réponds UNIQUEMENT en JSON avec ce format:
    {
      "score": <0-100>,
      "reasoning": "<explication courte en 1-2 phrases>"
    }
  
  # Timeout pour les appels
  timeout_seconds: 30
```

### 4.3 Fichier `.env.example`

```bash
# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy

# Gmail OAuth (généré par scripts/setup_gmail_oauth.py)
GMAIL_CREDENTIALS_PATH=credentials/gmail_credentials.json
GMAIL_TOKEN_PATH=credentials/gmail_token.json

# OpenClaw API (si nécessaire)
OPENCLAW_API_URL=http://localhost:3000

# LinkedIn session cookie (récupérer depuis DevTools > Application > Cookies > li_at)
# Durée de vie : ~12 mois. Orion notifiera sur Discord quand il expire.
LINKEDIN_LI_AT_COOKIE=AQEDAx...

# Optionnel: Proxy pour scraping
# HTTP_PROXY=http://proxy:port
# HTTPS_PROXY=http://proxy:port
```

---

## 5. Spécifications des modules

### 5.1 Module `scrapers/base_scraper.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class JobOffer:
    """Structure standard pour une offre d'emploi."""
    source: str                      # 'wttj', 'linkedin'
    external_id: Optional[str]
    url: str
    title: str
    company: str
    location: Optional[str]
    contract_type: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    description: str
    scraped_at: datetime = None

class BaseScraper(ABC):
    """Classe abstraite pour tous les scrapers."""
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Nom de la source (ex: 'wttj')."""
        pass
    
    @abstractmethod
    def scrape(self) -> List[JobOffer]:
        """Récupère les offres d'emploi."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Vérifie si la source est accessible."""
        pass
```

### 5.2 Module `scrapers/wttj_scraper.py`

**Responsabilités :**
- Construire les URLs de recherche avec les paramètres (titre, localisation, contrat)
- Parser les pages de résultats (liste des offres)
- Extraire les détails de chaque offre (fiche complète)
- Gérer la pagination
- Respecter les délais entre requêtes

**Points d'attention :**
- WTTJ a une API GraphQL non documentée qui peut être utilisée
- Alternativement, parser le HTML avec BeautifulSoup
- Gérer les erreurs 429 (rate limiting)

### 5.3 Module `scrapers/linkedin_email.py`

**Architecture en deux temps :**

Le scraper LinkedIn fonctionne en deux phases séquentielles :

**Temps 1 : Parser les alertes Gmail (rapide, ~10 secondes)**
- Se connecter à Gmail via OAuth 2.0
- Récupérer les emails non lus avec le label "LinkedIn Jobs"
- Parser le HTML des emails pour extraire : titre, entreprise, localisation, URL LinkedIn
- Marquer les emails comme lus après traitement

**Temps 2 : Fetch des fiches complètes via cookie `li_at` (lent, ~7.5 min pour 30 offres)**
- Pour chaque URL LinkedIn extraite au Temps 1
- Effectuer un `requests.get()` avec le cookie `li_at` et des headers réalistes
- Parser le HTML de la page LinkedIn pour extraire la description complète
- Respecter un délai de 15 secondes entre chaque requête (configurable)
- Rotation des User-Agents pour réduire l'empreinte

**Gestion du cookie `li_at` :**
- Le cookie est stocké dans `.env` sous `LINKEDIN_LI_AT_COOKIE`
- Durée de vie : ~12 mois
- Si le cookie est absent ou expiré (réponse 401/403) :
  - Logger l'erreur
  - Envoyer une notification Discord à Alexandre : "Cookie LinkedIn expiré, renouvellement nécessaire"
  - Ne PAS scorer les offres LinkedIn ce jour-là (skip complet)
  - Les offres restent en base avec `detail_status='failed'` pour retry ultérieur

**Sécurité anti-ban :**

| Paramètre | Valeur | Raison |
|---|---|---|
| Délai entre requêtes | 15 secondes | Simule un humain qui lit |
| Max fetches/jour | 30 | Volume réaliste d'un utilisateur |
| User-Agent | Navigateur réaliste (rotation) | Pas de signature bot |
| Headers | Accept-Language: fr-FR | Cohérent avec le profil |

**Code de référence :**

```python
class LinkedInEmailScraper(BaseScraper):

    def scrape(self) -> List[JobOffer]:
        # Temps 1 : Parser les emails Gmail → URLs + métadonnées
        raw_offers = self._parse_gmail_alerts()

        # Temps 2 : Enrichir avec les fiches complètes via cookie
        if self.li_at_cookie and self.fetch_details_enabled:
            enriched_offers = self._fetch_job_details(raw_offers)
        else:
            enriched_offers = raw_offers

        return enriched_offers

    def _fetch_job_details(self, offers: List[JobOffer]) -> List[JobOffer]:
        for offer in offers:
            html = self._fetch_linkedin_page(offer.url)
            if html:
                details = self._parse_job_page(html)
                offer.description = details.get("description", offer.description)
                offer.contract_type = details.get("contract_type", offer.contract_type)
                offer.salary_min = details.get("salary_min", offer.salary_min)
                offer.salary_max = details.get("salary_max", offer.salary_max)
            time.sleep(self.delay_between_requests)
        return offers

    def _fetch_linkedin_page(self, url: str) -> Optional[str]:
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Cookie": f"li_at={self.li_at_cookie}",
        }
        response = self.session.get(url, headers=headers, timeout=15, allow_redirects=False)
        if response.status_code == 200:
            return response.text
        if response.status_code in (401, 403):
            self._notify_cookie_expired()
            return None
        return None
```

### 5.4 Module `matcher/keyword_matcher.py`

**Algorithme de scoring :**

```python
def calculate_keyword_score(job: JobOffer, profile: dict) -> float:
    """
    Calcule un score de 0 à 100 basé sur les mots-clés.
    
    Algorithme:
    1. Vérifier les exclusions (retourne 0 si match)
    2. Calculer les points positifs (skills required, important, nice_to_have)
    3. Appliquer les pénalités (skills not_known)
    4. Appliquer les bonus (keywords bonus)
    5. Normaliser sur 100
    """
    score = 0
    max_possible_score = sum(skill['weight'] for category in ['required', 'important', 'nice_to_have'] 
                             for skill in profile['skills'].get(category, []))
    
    text_to_search = f"{job.title} {job.description}".lower()
    
    # 1. Vérifier exclusions
    for exclusion in profile['exclusions']['titles']:
        if exclusion.lower() in job.title.lower():
            return 0
    
    # 2. Calculer points positifs
    for category in ['required', 'important', 'nice_to_have']:
        for skill in profile['skills'].get(category, []):
            keywords = [skill['keyword']] + skill.get('aliases', [])
            if any(kw.lower() in text_to_search for kw in keywords):
                score += skill['weight']
    
    # 3. Appliquer pénalités
    for skill in profile['skills'].get('not_known', []):
        keywords = [skill['keyword']] + skill.get('aliases', [])
        if any(kw.lower() in text_to_search for kw in keywords):
            # Pénalité seulement si c'est une exigence ("requis", "obligatoire")
            if is_required_in_context(text_to_search, keywords):
                score += skill['penalty']  # Valeur négative
    
    # 4. Appliquer bonus
    for bonus in profile.get('bonuses', []):
        if bonus['keyword'].lower() in text_to_search:
            score += bonus['bonus']
    
    # 5. Normaliser
    normalized_score = max(0, min(100, (score / max_possible_score) * 100))
    return round(normalized_score, 1)
```

### 5.5 Module `matcher/ai_scorer.py`

**Responsabilités :**
- Exposer les offres pré-filtrées via l'API REST
- Recevoir les scores d'OpenClaw
- Construire les prompts pour l'IA

**Format de prompt pour OpenClaw :**

```
Évalue cette offre d'emploi pour un Data Analyst Power BI (2 ans exp, Paris, CDI).

OFFRE:
- Titre: {title}
- Entreprise: {company}
- Localisation: {location}
- Contrat: {contract_type}
- Description: {description[:2000]}

PROFIL CANDIDAT:
- Expert: Power BI, DAX, Power Query, SQL
- Connaît: Python, Tableau, Snowflake, Azure, Talend
- Ne connaît PAS: DBT, SAS, Dataiku, ML avancé
- Cherche: ESN/Conseil, missions variées

Réponds en JSON: {"score": 0-100, "reasoning": "..."}
```

### 5.6 Module `api/routes.py`

**Endpoints FastAPI :**

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Job Hunter API", version="1.0.0")

# --- Modèles Pydantic ---

class JobForScoring(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str]
    contract_type: Optional[str]
    description: str
    keyword_score: float

class ScoreSubmission(BaseModel):
    job_id: int
    ai_score: float
    reasoning: str

class BulkScoreSubmission(BaseModel):
    scores: List[ScoreSubmission]

# --- Endpoints ---

@app.get("/api/jobs/pending", response_model=List[JobForScoring])
async def get_pending_jobs():
    """
    Retourne les offres en attente de scoring IA.
    (status='new' et keyword_score >= seuil pré-filtre)
    """
    pass

@app.post("/api/jobs/scores")
async def submit_scores(submission: BulkScoreSubmission):
    """
    Reçoit les scores IA d'OpenClaw et met à jour la DB.
    Déclenche l'envoi Discord pour les scores >= 70%.
    """
    pass

@app.get("/api/stats")
async def get_stats():
    """
    Statistiques: offres aujourd'hui, scores moyens, etc.
    """
    pass

@app.post("/api/trigger-scrape")
async def trigger_scrape():
    """
    Déclenche manuellement un cycle de scraping.
    """
    pass
```

### 5.7 Module `notifier/discord_notifier.py`

**Format : Embed récapitulatif groupé par source**

Au lieu d'envoyer un embed par offre, le notifier envoie UN récapitulatif quotidien groupé par source.

**Structure du message Discord :**

```python
def send_daily_recap(self, jobs_by_source: Dict[str, List[Job]]) -> bool:
    """
    Envoie un récapitulatif quotidien groupé par source.

    jobs_by_source = {
        "wttj": [Job, Job, ...],
        "linkedin": [Job, Job, ...],
    }
    """
    embeds = []

    # Embed d'en-tête avec résumé
    total = sum(len(jobs) for jobs in jobs_by_source.values())
    summary_parts = [f"{len(jobs)} {source.upper()}" for source, jobs in jobs_by_source.items()]
    summary = ", ".join(summary_parts)

    embeds.append({
        "title": f"Job Hunter - Rapport du {date.today().strftime('%d/%m/%Y')}",
        "description": f"**{total} offres trouvées** ({summary})",
        "color": 0x00D166,
    })

    # Un embed par source
    for source, jobs in jobs_by_source.items():
        source_label = {"wttj": "Welcome to the Jungle", "linkedin": "LinkedIn"}.get(source, source)
        lines = []
        for i, job in enumerate(jobs, 1):
            score_str = f"**{job.final_score}%**" if job.final_score else "N/A"
            location_str = f" | {job.location}" if job.location else ""
            contract_str = f" | {job.contract_type}" if job.contract_type else ""
            reasoning = f"\n> {job.ai_reasoning[:150]}" if job.ai_reasoning else ""
            lines.append(
                f"**{i}. [{job.title}]({job.url})** — {job.company}\n"
                f"Score: {score_str}{location_str}{contract_str}{reasoning}\n"
            )
        embeds.append({
            "title": f"── {source_label} ({len(jobs)} offres) ──",
            "description": "\n".join(lines)[:4000],  # Limite Discord
            "color": 0x5865F2 if source == "linkedin" else 0xFFCD00,
        })

    # Envoyer (Discord limite à 10 embeds par message)
    payload = {"embeds": embeds[:10]}
    return self._send_webhook(payload)
```

**Méthode `send_job()` conservée** pour les cas où une seule offre doit être notifiée (ex: via l'API).

**Nouveau flow dans `main.py` :**

Le notifier n'envoie plus les offres une par une. L'orchestrateur collecte toutes les offres
notifiables après le scoring, les groupe par source, puis appelle `send_daily_recap()`.

### 5.8 Module `utils/deduplication.py`

```python
import hashlib
from typing import Optional

def generate_job_hash(url: str, title: Optional[str] = None, company: Optional[str] = None) -> str:
    """
    Génère un hash unique pour une offre.
    
    Priorité:
    1. URL (si disponible et valide)
    2. Combinaison titre + entreprise (fallback)
    """
    if url and url.startswith('http'):
        # Normaliser l'URL (supprimer paramètres tracking)
        clean_url = normalize_url(url)
        content = clean_url
    elif title and company:
        content = f"{title.lower().strip()}|{company.lower().strip()}"
    else:
        raise ValueError("Impossible de générer un hash: URL ou titre+entreprise requis")
    
    return hashlib.sha256(content.encode()).hexdigest()

def normalize_url(url: str) -> str:
    """Supprime les paramètres de tracking de l'URL."""
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    
    parsed = urlparse(url)
    # Garder seulement les paramètres essentiels
    params = parse_qs(parsed.query)
    essential_params = {k: v for k, v in params.items() 
                       if k not in ['utm_source', 'utm_medium', 'utm_campaign', 'ref', 'source']}
    
    clean = parsed._replace(query=urlencode(essential_params, doseq=True))
    return urlunparse(clean)
```

---

## 6. Étapes d'implémentation

### Phase 1 : Fondations (Priorité haute)

| # | Tâche | Fichier(s) | Estimation |
|---|-------|------------|------------|
| 1.1 | Créer la structure du projet | Tous les dossiers et `__init__.py` | 15 min |
| 1.2 | Configurer `requirements.txt` | `requirements.txt` | 10 min |
| 1.3 | Implémenter le chargement de config | `src/utils/config.py` | 30 min |
| 1.4 | Créer les fichiers de configuration | `config/profile.yaml`, `config/settings.yaml` | 20 min |
| 1.5 | Implémenter les modèles SQLAlchemy | `src/database/models.py` | 30 min |
| 1.6 | Implémenter le repository (CRUD) | `src/database/repository.py` | 45 min |
| 1.7 | Implémenter la déduplication | `src/utils/deduplication.py` | 20 min |
| 1.8 | Configurer le logging | `src/utils/logger.py` | 15 min |

### Phase 2 : Scrapers (Priorité haute)

| # | Tâche | Fichier(s) | Estimation |
|---|-------|------------|------------|
| 2.1 | Implémenter `BaseScraper` | `src/scrapers/base_scraper.py` | 20 min |
| 2.2 | Implémenter le scraper WTTJ | `src/scrapers/wttj_scraper.py` | 2h |
| 2.3 | Script setup OAuth Gmail | `scripts/setup_gmail_oauth.py` | 30 min |
| 2.4 | Implémenter le parser LinkedIn email (Temps 1: Gmail) | `src/scrapers/linkedin_email.py` | 1h |
| 2.5 | Implémenter le fetch LinkedIn via cookie li_at (Temps 2) | `src/scrapers/linkedin_email.py` | 1h30 |
| 2.6 | Tests unitaires scrapers | `tests/test_scrapers.py` | 1h |

### Phase 3 : Système de matching (Priorité haute)

| # | Tâche | Fichier(s) | Estimation |
|---|-------|------------|------------|
| 3.1 | Implémenter le scoring par mots-clés | `src/matcher/keyword_matcher.py` | 1h |
| 3.2 | Implémenter l'interface IA | `src/matcher/ai_scorer.py` | 45 min |
| 3.3 | Tests unitaires matcher | `tests/test_matcher.py` | 45 min |

### Phase 4 : API et notifications (Priorité moyenne)

| # | Tâche | Fichier(s) | Estimation |
|---|-------|------------|------------|
| 4.1 | Implémenter l'API FastAPI | `src/api/routes.py` | 1h |
| 4.2 | Implémenter le notifier Discord (récapitulatif groupé par source) | `src/notifier/discord_notifier.py` | 1h |
| 4.3 | Tests API | `tests/test_api.py` | 30 min |

### Phase 5 : Orchestration et finalisation (Priorité moyenne)

| # | Tâche | Fichier(s) | Estimation |
|---|-------|------------|------------|
| 5.1 | Implémenter l'orchestrateur `main.py` | `src/main.py` | 1h |
| 5.2 | Créer le script de démarrage | `run.py` ou `Makefile` | 15 min |
| 5.3 | Documentation README | `README.md` | 30 min |
| 5.4 | Configuration cron pour VPS | Documentation | 15 min |

### Phase 6 : Tests et déploiement (Priorité basse)

| # | Tâche | Fichier(s) | Estimation |
|---|-------|------------|------------|
| 6.1 | Tests d'intégration complets | `tests/` | 1h |
| 6.2 | Test de bout en bout | Manuel | 30 min |
| 6.3 | Déploiement VPS | Scripts/Documentation | 1h |

---

## 7. Dépendances (`requirements.txt`)

```
# Core
python-dotenv>=1.0.0
pyyaml>=6.0

# Database
sqlalchemy>=2.0.0

# Web scraping
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0

# Gmail API
google-auth>=2.22.0
google-auth-oauthlib>=1.0.0
google-api-python-client>=2.95.0

# API
fastapi>=0.103.0
uvicorn>=0.23.0
pydantic>=2.0.0

# HTTP client async (pour notifier)
httpx>=0.24.0

# Utilities
python-dateutil>=2.8.0

# Dev/Test
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

---

## 8. Notes importantes pour l'implémentation

### 8.1 Gestion des erreurs

- Chaque scraper doit gérer ses propres erreurs sans faire crasher l'ensemble
- Logger toutes les erreurs avec contexte (source, URL, etc.)
- Retry automatique avec backoff exponentiel pour les erreurs réseau

### 8.2 Rate limiting

- WTTJ : 2 secondes minimum entre chaque requête
- Gmail API : Respecter les quotas (250 requêtes/utilisateur/seconde)
- Discord : Max 30 requêtes/minute sur un webhook
- LinkedIn : 15 secondes minimum entre chaque requête, max 30 fetches/jour
- Cookie `li_at` : Si réponse 401/403, ne pas retry, notifier sur Discord

### 8.3 Sécurité

- Ne jamais commiter les credentials (`credentials/` dans `.gitignore`)
- Variables sensibles uniquement via `.env`
- Valider toutes les entrées de l'API
- Cookie LinkedIn `li_at` uniquement via `.env`, ne jamais le logger

### 8.4 Maintenance

- Nettoyer les offres > 30 jours automatiquement
- Rotation des logs (garder 7 jours)
- Monitoring des erreurs de scraping (les sites changent leur HTML)

---

## 9. Commandes utiles

```bash
# Installation
pip install -r requirements.txt

# Configurer Gmail OAuth (one-time)
python scripts/setup_gmail_oauth.py

# Lancer le scraping manuellement
python -m src.main --scrape-only

# Lancer l'API pour OpenClaw
python -m src.main --api-only

# Lancer le cycle complet
python -m src.main

# Tests
pytest tests/ -v

# Cron (sur VPS)
# Ajouter dans crontab -e :
0 9 * * * cd /path/to/job-hunter && /path/to/venv/bin/python -m src.main >> /var/log/job-hunter.log 2>&1
```

---

## 10. Évolutions futures (hors scope v1)

- [ ] Auto-candidature (easy apply LinkedIn/WTTJ)
- [ ] Interface web pour visualiser les offres
- [ ] Scraper Indeed
- [ ] Scraper HelloWork
- [ ] Analyse des tendances (salaires, skills demandés)
- [ ] Génération automatique de lettres de motivation
- [ ] Intégration calendrier pour les entretiens

---

*Ce document est la référence pour l'implémentation. Toute modification doit être reflétée ici.*
