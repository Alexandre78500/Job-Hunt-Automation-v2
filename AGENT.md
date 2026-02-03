# Instructions pour Orion - Job Hunter Automation

> Ce document est ta référence, Orion. Il contient tout ce que tu dois savoir pour installer,
> configurer, lancer et maintenir le projet Job Hunter Automation sur le VPS.
> Lis-le en entier avant de commencer. En cas de doute, demande à Alexandre.

---

## Sommaire

1. [Contexte et objectif](#1-contexte-et-objectif)
2. [Ton rôle dans le pipeline](#2-ton-rôle-dans-le-pipeline)
3. [Installation sur le VPS](#3-installation-sur-le-vps)
4. [Configuration](#4-configuration)
5. [Lancement et vérification](#5-lancement-et-vérification)
6. [Configuration du cron quotidien](#6-configuration-du-cron-quotidien)
7. [Workflow de scoring IA](#7-workflow-de-scoring-ia)
8. [Notifications Discord](#8-notifications-discord)
9. [Maintenance](#9-maintenance)
10. [Dépannage](#10-dépannage)

---

## 1. Contexte et objectif

### 1.1 Le projet en bref

Job Hunter Automation est un pipeline automatisé qui chaque matin à 9h :
1. **Scrape** les offres d'emploi depuis Welcome to the Jungle + alertes LinkedIn via Gmail
2. **Pré-filtre** les offres par mots-clés (scoring algorithmique, sans IA, gratuit)
3. **Expose une API REST** pour qu'un agent IA score les offres restantes
4. **Notifie** Alexandre sur Discord avec les offres pertinentes (score >= 70%)

### 1.2 Le profil d'Alexandre

| Critère | Valeur |
|---------|--------|
| **Poste recherché** | Data Analyst / Consultant Data / Data Analyst Power BI |
| **Localisation** | Paris / Île-de-France |
| **Contrat** | CDI uniquement |
| **Stack principale** | Power BI (DAX, Power Query), SQL avancé, Python |
| **Cible entreprises** | ESN / Conseil |

Le profil complet est dans `config/profile.yaml`. Tu n'as pas besoin de le modifier sauf si Alexandre te le demande.

---

## 2. Ton rôle dans le pipeline

```
┌──────────────────────────────────────────────────────────────────────┐
│                     CRON 9h00 (automatique)                         │
│                  python -m src.main --scrape-only                   │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                 ┌──────────────────────────────┐
                 │  Scraping WTTJ + LinkedIn     │
                 │  Pré-filtre mots-clés         │  ← Le script fait ça
                 │  Stockage SQLite              │     tout seul
                 └──────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     TOI, ORION                                       │
│                                                                      │
│  1. Appeler GET /api/jobs/pending?include_prompt=true                │
│  2. Pour chaque offre, scorer avec ton modèle IA                    │
│  3. Renvoyer les scores via POST /api/jobs/scores                   │
│                                                                      │
│  Tu peux déléguer le scoring à un sous-agent si tu veux.            │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                 ┌──────────────────────────────┐
                 │  Le script calcule le score   │
                 │  final et notifie Discord     │  ← Automatique
                 │  si score >= 70%              │
                 └──────────────────────────────┘
```

**Résumé de tes responsabilités :**

| Tâche | Quand | Comment |
|-------|-------|---------|
| Installer le projet | Une seule fois | Suivre la section 3 |
| Configurer .env, Gmail, Discord | Une seule fois | Suivre la section 4 (demander à Alexandre pour les parties sensibles) |
| Configurer le cron | Une seule fois | Suivre la section 6 |
| Scorer les offres via l'API | Tous les jours après le scraping | Suivre la section 7 |
| Surveiller les erreurs | En continu | Suivre la section 9 |

---

## 3. Installation sur le VPS

### 3.1 Prérequis

Vérifie que tu as :
- **Python 3.11+** (`python3 --version`)
- **pip** (`pip3 --version`)
- **git** (`git --version`)
- **Accès sudo** (tu l'as)

Si Python 3.11+ n'est pas installé :
```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip
```

### 3.2 Cloner le projet

```bash
cd /home/orion/projects
git clone https://github.com/Alexandre78500/Job-Hunt-Automation-v2.git
cd Job-Hunt-Automation-v2
```

### 3.3 Créer l'environnement virtuel

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.4 Créer les dossiers nécessaires

```bash
mkdir -p data credentials logs
```

### 3.5 Vérification

```bash
python -c "from src.utils.config import load_settings, load_profile; print('OK')"
```

Si ça affiche `OK`, l'installation est bonne.

---

## 4. Configuration

> **MODE INTERACTIF** : Pour cette section, demande à Alexandre de valider chaque étape
> avant de passer à la suivante. Ce sont des configurations sensibles.

### 4.1 Fichier .env

```bash
cp .env.example .env
```

Édite le fichier `.env` avec les valeurs réelles :

```bash
# Discord - Demande à Alexandre de créer un webhook ou aide-le
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy

# Gmail OAuth - sera généré à l'étape 4.2
GMAIL_CREDENTIALS_PATH=credentials/gmail_credentials.json
GMAIL_TOKEN_PATH=credentials/gmail_token.json

# OpenClaw API (optionnel)
OPENCLAW_API_URL=http://localhost:3000
```

### 4.2 Configuration Gmail OAuth

**Objectif** : Permettre au script de lire les emails d'alerte LinkedIn depuis un compte Gmail.

#### Étape 1 : Projet Google Cloud

1. Aller sur https://console.cloud.google.com/
2. Créer un nouveau projet (ou en utiliser un existant)
3. Activer l'API Gmail :
   - Menu > APIs & Services > Library
   - Chercher "Gmail API"
   - Cliquer "Enable"

#### Étape 2 : Credentials OAuth

1. Menu > APIs & Services > Credentials
2. Cliquer "Create Credentials" > "OAuth 2.0 Client ID"
3. Application type : "Desktop app"
4. Télécharger le fichier JSON
5. Le placer dans `credentials/gmail_credentials.json`

#### Étape 3 : Générer le token

```bash
cd /home/orion/projects/Job-Hunt-Automation-v2
source .venv/bin/activate
python scripts/setup_gmail_oauth.py
```

> **NOTE** : Cette commande va ouvrir un navigateur pour l'authentification.
> Si tu es en SSH sans navigateur, utilise le flag `--no-browser` ou demande
> à Alexandre de faire cette étape sur sa machine et de copier le token généré.

Le token sera sauvegardé dans `credentials/gmail_token.json`.

#### Étape 4 : Créer le label Gmail

Dans le compte Gmail utilisé pour les alertes :
1. Créer un label appelé exactement : **LinkedIn Jobs**
2. Configurer un filtre pour que les emails de LinkedIn (from: `@linkedin.com` contenant "job") soient automatiquement marqués avec ce label

### 4.3 Configurer les alertes LinkedIn

1. Se connecter à LinkedIn avec le compte d'Alexandre
2. Aller dans Jobs > Job Alerts
3. Créer des alertes pour :
   - "Data Analyst" - Paris
   - "Consultant Data" - Paris
   - "Power BI" - Paris
4. S'assurer que les alertes sont envoyées à l'adresse Gmail configurée

### 4.4 Configurer Discord

#### Créer un webhook Discord

1. Sur le serveur Discord d'Alexandre, choisir un channel (ex: `#job-alerts`)
2. Paramètres du channel > Integrations > Webhooks
3. Créer un webhook, lui donner un nom (ex: "Job Hunter")
4. Copier l'URL du webhook
5. La coller dans le fichier `.env` à la ligne `DISCORD_WEBHOOK_URL`

#### Tester le webhook

```bash
curl -X POST "URL_DU_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"content": "Job Hunter Automation est connecté !"}'
```

Si le message apparaît dans Discord, c'est bon.

> **DEMANDE À ALEXANDRE** : Confirme-lui que Discord est configuré et montre-lui
> le message de test. Attends sa validation avant de continuer.

---

## 5. Lancement et vérification

### 5.1 Premier test de scraping

```bash
cd /home/orion/projects/Job-Hunt-Automation-v2
source .venv/bin/activate
python -m src.main --scrape-only
```

**Ce que tu dois vérifier :**
- Pas d'erreur dans la sortie
- Le fichier `data/jobs.db` a été créé
- Des offres ont été trouvées

Pour vérifier la base :
```bash
python3 -c "
from src.database.repository import DatabaseManager
db = DatabaseManager('data/jobs.db')
stats = db.get_stats()
print(f'Total: {stats[\"total\"]} | New: {stats[\"new\"]} | Scored: {stats[\"scored\"]} | Notified: {stats[\"notified\"]}')
"
```

### 5.2 Lancer l'API

```bash
python -m src.main --api-only
```

L'API sera disponible sur `http://localhost:8000`.

**Tester :**
```bash
curl http://localhost:8000/api/stats
curl http://localhost:8000/api/jobs/pending?limit=5
```

### 5.3 Lancer l'API en arrière-plan

Pour que l'API tourne en permanence (nécessaire pour le scoring) :

```bash
# Option 1 : nohup
nohup python -m src.main --api-only > logs/api.log 2>&1 &

# Option 2 : systemd (recommandé)
sudo tee /etc/systemd/system/job-hunter-api.service > /dev/null << 'EOF'
[Unit]
Description=Job Hunter API
After=network.target

[Service]
Type=simple
User=orion
WorkingDirectory=/home/orion/projects/Job-Hunt-Automation-v2
ExecStart=/home/orion/projects/Job-Hunt-Automation-v2/.venv/bin/python -m src.main --api-only
Restart=on-failure
RestartSec=10
Environment="PATH=/home/orion/projects/Job-Hunt-Automation-v2/.venv/bin:/usr/bin"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable job-hunter-api
sudo systemctl start job-hunter-api
sudo systemctl status job-hunter-api
```

---

## 6. Configuration du cron quotidien

### 6.1 Script wrapper

Crée un script wrapper pour le cron :

```bash
cat > /home/orion/projects/Job-Hunt-Automation-v2/run_daily.sh << 'EOF'
#!/bin/bash
set -e

PROJECT_DIR="/home/orion/projects/Job-Hunt-Automation-v2"
VENV="$PROJECT_DIR/.venv/bin/python"
LOG="$PROJECT_DIR/logs/scrape-$(date +%Y-%m-%d).log"

cd "$PROJECT_DIR"
echo "=== Job Hunter Scraping - $(date) ===" >> "$LOG"
$VENV -m src.main --scrape-only >> "$LOG" 2>&1
echo "=== Terminé - $(date) ===" >> "$LOG"
EOF

chmod +x /home/orion/projects/Job-Hunt-Automation-v2/run_daily.sh
```

### 6.2 Configurer le cron

```bash
crontab -e
```

Ajouter cette ligne :
```
0 9 * * * /home/orion/projects/Job-Hunt-Automation-v2/run_daily.sh
```

**Explication** : Tous les jours à 9h00, le script scrape les offres, les pré-filtre par mots-clés et les stocke dans la base SQLite.

### 6.3 Cron pour le scoring (après le scraping)

Ajoute un second cron 15 minutes après le scraping pour lancer le scoring IA.
Tu peux soit :
- Écrire un petit script Python qui appelle l'API et score les offres
- Ou le faire toi-même via ton propre système de tâches

Exemple de cron si tu crées un script de scoring :
```
15 9 * * * /home/orion/projects/Job-Hunt-Automation-v2/.venv/bin/python /home/orion/projects/Job-Hunt-Automation-v2/scripts/run_scoring.sh
```

Voir la section 7 pour le workflow de scoring.

### 6.4 Cron de nettoyage des logs

```bash
# Ajouter dans crontab
0 0 * * 0 find /home/orion/projects/Job-Hunt-Automation-v2/logs -name "*.log" -mtime +7 -delete
```

---

## 7. Workflow de scoring IA

C'est la partie la plus importante de ton rôle quotidien. Après le scraping de 9h00, tu dois scorer les offres pré-filtrées.

### 7.1 Étape 1 : Récupérer les offres à scorer

```
GET http://localhost:8000/api/jobs/pending?limit=50&include_prompt=true
```

**Réponse** (exemple) :
```json
[
  {
    "id": 42,
    "title": "Data Analyst Power BI",
    "company": "Capgemini",
    "location": "Paris",
    "contract_type": "CDI",
    "description": "Nous recherchons un Data Analyst...",
    "keyword_score": 65.3,
    "url": "https://www.welcometothejungle.com/...",
    "prompt": "Evaluate this job offer for a Data Analyst Power BI (2 years exp, Paris, CDI).\n\nOFFER:\n- Title: Data Analyst Power BI\n- Company: Capgemini\n..."
  }
]
```

**Le champ `prompt`** contient le prompt pré-construit que tu peux envoyer directement à ton modèle IA. Il contient déjà le profil d'Alexandre et les instructions de scoring.

### 7.2 Étape 2 : Scorer chaque offre

Pour chaque offre, envoie le `prompt` à ton modèle IA (ou celui d'un sous-agent). Le modèle doit répondre en JSON :

```json
{
  "score": 82,
  "reasoning": "Poste Power BI + SQL en ESN à Paris, correspond bien au profil. DAX mentionné."
}
```

**Critères de scoring à respecter :**

| Score | Signification |
|-------|---------------|
| 90-100 | Match parfait : Power BI + SQL + ESN/Conseil + Paris + CDI + junior/confirmé |
| 70-89 | Bon match : la plupart des critères sont présents |
| 50-69 | Match partiel : quelques critères manquent |
| 30-49 | Faible match : beaucoup de critères manquants |
| 0-29 | Pas pertinent |

**Points clés pour le scoring :**
- Power BI et SQL sont **obligatoires** → sans eux, score < 30
- Si l'offre exige DBT, SAS, Dataiku, ML avancé comme compétences principales → malus
- ESN/Conseil = bonus
- Paris/IDF/Remote = OK, autre ville = malus
- CDI = OK, autre contrat = score 0
- Senior/Lead/Manager = score 0

### 7.3 Étape 3 : Renvoyer les scores

```
POST http://localhost:8000/api/jobs/scores
Content-Type: application/json

{
  "scores": [
    {"job_id": 42, "ai_score": 82, "reasoning": "Power BI + SQL en ESN, Paris, CDI."},
    {"job_id": 43, "ai_score": 45, "reasoning": "Demande principalement SAS, pas dans le profil."},
    {"job_id": 44, "ai_score": 91, "reasoning": "Match parfait : Power BI, DAX, SQL, ESN conseil, Paris."}
  ]
}
```

**Réponse :**
```json
{"updated": 3}
```

Le script va automatiquement :
1. Calculer le score final (30% mots-clés + 70% score IA)
2. Envoyer sur Discord les offres avec un score final >= 70%
3. Marquer ces offres comme "notified"

### 7.4 Script de scoring automatique (optionnel)

Si tu veux automatiser le scoring sans intervention manuelle, crée ce script :

```bash
cat > /home/orion/projects/Job-Hunt-Automation-v2/scripts/run_scoring.sh << 'SCRIPT'
#!/bin/bash
# Ce script est un placeholder.
# Orion, remplace-le par ton propre mécanisme de scoring.
# L'idée : appeler l'API, scorer avec un LLM, renvoyer les scores.

API="http://localhost:8000"

# 1. Récupérer les offres
JOBS=$(curl -s "$API/api/jobs/pending?include_prompt=true&limit=50")

# 2. Vérifier s'il y a des offres
COUNT=$(echo "$JOBS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
if [ "$COUNT" = "0" ]; then
    echo "Aucune offre à scorer."
    exit 0
fi

echo "$COUNT offres à scorer."

# 3. Scoring IA
# Orion : branche ici ton modèle IA pour scorer chaque offre.
# Tu peux utiliser le champ "prompt" de chaque offre.
# Exemple avec curl vers un LLM API :
#
# for job in jobs:
#     response = call_llm(job["prompt"])
#     scores.append({"job_id": job["id"], "ai_score": response["score"], "reasoning": response["reasoning"]})
#
# 4. Envoyer les scores
# curl -X POST "$API/api/jobs/scores" -H "Content-Type: application/json" -d '{"scores": [...]}'

echo "Scoring terminé."
SCRIPT

chmod +x /home/orion/projects/Job-Hunt-Automation-v2/scripts/run_scoring.sh
```

### 7.5 Vérifier les stats

À tout moment, tu peux vérifier l'état du système :

```
GET http://localhost:8000/api/stats
```

Réponse :
```json
{
  "total": 150,
  "new": 12,
  "scored": 85,
  "notified": 53
}
```

---

## 8. Notifications Discord

### 8.1 Format des notifications

Quand une offre dépasse le seuil de 70%, le script envoie automatiquement un message Discord avec :

| Champ | Description |
|-------|-------------|
| **Titre** | Titre du poste (lien cliquable vers l'offre) |
| **Entreprise** | Nom de l'entreprise |
| **Localisation** | Ville / région |
| **Contrat** | Type de contrat |
| **Score** | Score final en pourcentage |
| **Salaire** | Fourchette si disponible |
| **Analyse IA** | Explication du score par l'IA |

### 8.2 En cas de problème avec Discord

Si les notifications ne partent pas :
1. Vérifier le webhook URL dans `.env`
2. Tester manuellement : `curl -X POST "WEBHOOK_URL" -H "Content-Type: application/json" -d '{"content":"test"}'`
3. Vérifier les logs : `tail -f logs/job-hunter.log`
4. Le rate limit Discord est de 30 requêtes/minute par webhook

---

## 9. Maintenance

### 9.1 Logs

Les logs sont dans `logs/job-hunter.log` avec rotation automatique (7 jours).

```bash
# Voir les derniers logs
tail -50 logs/job-hunter.log

# Chercher des erreurs
grep -i error logs/job-hunter.log
```

### 9.2 Nettoyage automatique

Le script supprime automatiquement les offres de plus de 30 jours à chaque exécution.
Ce délai est configurable dans `config/settings.yaml` > `database.cleanup_days`.

### 9.3 Mise à jour du projet

```bash
cd /home/orion/projects/Job-Hunt-Automation-v2
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart job-hunter-api
```

### 9.4 Surveillance

**Chaque semaine, vérifie :**
- Que le cron s'exécute bien : `grep "Job Hunter" /var/log/syslog` ou `ls -la logs/`
- Que la base n'est pas corrompue : `python3 -c "from src.database.repository import DatabaseManager; db = DatabaseManager('data/jobs.db'); print(db.get_stats())"`
- Que le scraper WTTJ fonctionne toujours (les sites changent leur HTML)
- Que le token Gmail n'a pas expiré

**Si le scraper WTTJ casse** (0 offres trouvées), c'est probablement parce que WTTJ a modifié son front-end ou ses clés Algolia. Le script réextrait automatiquement les clés à chaque exécution, mais si la structure HTML change, il faudra mettre à jour `src/scrapers/wttj_scraper.py`.

### 9.5 Alerter Alexandre

Si tu détectes un problème critique (scraping cassé, API down, token expiré), préviens Alexandre sur Discord ou via le canal de communication habituel.

---

## 10. Dépannage

### 10.1 Erreurs courantes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `ModuleNotFoundError` | Venv pas activé | `source .venv/bin/activate` |
| `FileNotFoundError: gmail_credentials.json` | Credentials Gmail manquantes | Suivre la section 4.2 |
| `Token has been expired or revoked` | Token Gmail expiré | Relancer `python scripts/setup_gmail_oauth.py` |
| `Algolia config not found` | WTTJ a changé sa page | Vérifier manuellement si le site est accessible |
| `Discord webhook error 404` | Webhook supprimé | Recréer le webhook dans Discord |
| `sqlite3.OperationalError: database is locked` | Deux processus accèdent à la DB | S'assurer qu'un seul scraping tourne à la fois |
| `ConnectionError` | Pas d'internet ou site down | Vérifier la connectivité, réessayer plus tard |

### 10.2 Reset complet

En dernier recours, pour repartir de zéro :

```bash
cd /home/orion/projects/Job-Hunt-Automation-v2
rm -f data/jobs.db
python -m src.main --scrape-only
```

### 10.3 Tester un composant individuellement

```bash
# Tester le scraper WTTJ
python3 -c "
from src.scrapers.wttj_scraper import WttjScraper
s = WttjScraper('https://www.welcometothejungle.com', ['Data Analyst'], 'Paris, France', 'CDI', max_pages=1)
print('Available:', s.is_available())
jobs = s.scrape()
print(f'Found {len(jobs)} jobs')
for j in jobs[:3]:
    print(f'  - {j.title} @ {j.company}')
"

# Tester le keyword matcher
python3 -c "
from src.matcher.keyword_matcher import calculate_keyword_score
from src.scrapers.base_scraper import JobOffer
from src.utils.config import load_profile

profile = load_profile()
job = JobOffer(
    source='test', external_id=None,
    url='https://example.com',
    title='Data Analyst Power BI',
    company='Accenture',
    location='Paris', contract_type='CDI',
    salary_min=40000, salary_max=50000,
    description='Power BI, DAX, SQL, reporting, dashboards'
)
score = calculate_keyword_score(job, profile)
print(f'Score: {score}%')
"

# Tester Discord
python3 -c "
from src.notifier.discord_notifier import DiscordNotifier
from src.utils.config import load_env, load_settings
import os
load_env()
settings = load_settings()
n = DiscordNotifier(settings['notifications']['discord'])
print('Webhook configuré:', bool(n.webhook_url))
"
```

---

## Checklist de mise en route

Utilise cette checklist pour t'assurer que tout est en place :

- [ ] Projet cloné dans `/home/orion/projects/Job-Hunt-Automation-v2`
- [ ] Environnement virtuel créé et dépendances installées
- [ ] Fichier `.env` configuré
- [ ] Gmail OAuth configuré (credentials + token)
- [ ] Label "LinkedIn Jobs" créé dans Gmail
- [ ] Alertes LinkedIn configurées vers l'adresse Gmail
- [ ] Webhook Discord créé et testé
- [ ] Premier scraping (`--scrape-only`) réussi
- [ ] API lancée en arrière-plan (systemd)
- [ ] Cron quotidien configuré (scraping à 9h)
- [ ] Workflow de scoring IA testé
- [ ] Alexandre a reçu une notification Discord de test

---

*Orion, si tu as tout coché ci-dessus, le système est opérationnel. Bon travail !*
