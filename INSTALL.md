# Installation et Configuration du Projet (Flask)

Ce guide explique comment configurer l'environnement de développement pour le projet Freebox Movies Recorder utilisant Flask.

## Prérequis

- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)
- Une Freebox avec l'API activée

## Étapes d'installation

### 1. Créer un environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou venv\Scripts\activate sur Windows
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Démarrer le serveur de développement

```bash
python app.py
```

Le serveur sera accessible à l'adresse `http://localhost:8030` ou depuis d'autres machines du réseau à `http://[IP_DE_VOTRE_MACHINE]:8030`.

## Structure du projet

```
/
├── app.py                # Application Flask principale
├── templates/           # Templates Jinja2
│   ├── base.html        # Template de base
│   ├── index.html       # Page d'accueil
│   └── settings.html     # Page de configuration
├── static/              # Fichiers statiques
│   └── css/
│       └── style.css
├── data/                # Données persistantes
│   ├── config/
│   │   ├── freebox.json # Credentials Freebox
│   │   └── channels.json # Liste des chaînes
│   └── cache/
├── requirements.txt     # Dépendances Python
├── .env                 # Variables d'environnement
└── README.md             # Documentation
```

## Fonctionnalités

### Routes disponibles
- `GET /` - Page d'accueil
- `GET /settings` - Page de configuration
- `POST /toggle_channel/<id>` - Activer/désactiver une chaîne
- `POST /update_freebox_url` - Mettre à jour l'URL de l'API Freebox

### Gestion des données

Les données sont stockées dans `data/config/` au format JSON :

- `freebox.json` : Informations d'identification et URL de l'API
- `channels.json` : Liste des chaînes surveillées avec leur statut

Le dossier `data/config/` est exclu du contrôle de version (.gitignore).

## Configuration

**Les paramètres sont maintenant en dur dans le code** (inspiré de getprog.py) :

- **IP Freebox** : `192.168.0.254`
- **API URL** : `https://192.168.0.254/api/v4/`
- **APP_ID** : `fr.freebox.movies_recorder`

Pour changer l'IP de la Freebox, modifiez directement la constante `FREEBOX_IP` dans `app.py`.

**Note importante** : 
- L'API utilise **HTTPS** (pas HTTP)
- L'URL se termine par `/api/v4/` pour la version 4 de l'API
- Le certificat SSL est auto-signé (géré par `verify=False`)

## Utilisation

### Processus d'authentification Freebox

1. **Accéder à l'application** : `http://localhost:8030`
2. **Aller dans Paramètres** : Cliquez sur "Paramètres" dans la barre de navigation
3. **Démarrer l'authentification** : Cliquez sur "Démarrer l'authentification"
4. **Approuver sur la Freebox** : 
   - Votre Freebox affichera une notification
   - Appuyez physiquement sur un bouton de votre Freebox pour approuver
5. **Vérifier le statut** : L'application vérifie automatiquement toutes les 5 secondes
6. **Créer une session** : Une fois approuvé, cliquez sur "Créer une session"
7. **Utiliser l'application** : Vous êtes maintenant connecté et pouvez utiliser toutes les fonctionnalités

### Gestion des chaînes

- **Activer/Désactiver** : Depuis la page Paramètres, utilisez les boutons pour chaque chaîne
- **Ajouter/Supprimer** : Modifiez directement le fichier `data/config/channels.json`

### Déconnexion

- Cliquez sur "Déconnecter" dans la section Authentification des paramètres
=======

## Dépendances

- `flask==3.0.0` : Micro-framework web
- `requests==2.31.0` : Client HTTP pour les requêtes API

**Note** : `python-dotenv` a été supprimé car la configuration est maintenant en dur dans le code.

## Interface Utilisateur

L'application utilise **Pico CSS** pour le style :
- Framework CSS minimaliste (~10ko)
- Design moderne et accessible
- Responsive par défaut
- Pas de JavaScript requis pour le style de base

Le CSS personnalisé est dans `static/css/style.css` pour les ajustements spécifiques.

## Commandes utiles

- **Démarrer en mode développement** : `python app.py`
- **Démarrer en production** : `gunicorn -w 4 -b 0.0.0.0:8030 app:app`
- **Initialiser les données** : `python -c "from app import init_default_data; init_default_data()"`

## Déploiement

Pour un déploiement en production :

1. Désactivez le mode debug dans `.env` (`DEBUG=False`)
2. Utilisez un serveur WSGI comme Gunicorn
3. Configurez un reverse proxy (Nginx, Apache)
4. Sécurisez avec HTTPS

Exemple de commande de production :
```bash
gunicorn -w 4 -b 0.0.0.0:8030 app:app
```

## Prochaines étapes

1. **Authentification Freebox** : Implémenter l'authentification avec l'API Freebox
2. **Récupération EPG** : Ajouter la récupération du guide des programmes
3. **Enregistrement** : Implémenter la programmation des enregistrements
4. **Interface** : Améliorer l'interface utilisateur avec plus d'interactivité
5. **Planification** : Ajouter un système de planification automatique

## Processus d'authentification Freebox

L'application utilise le processus standard d'authentification de l'API Freebox v4 :

1. **Enregistrement de l'application** :
   - L'application s'enregistre auprès de la Freebox
   - La Freebox affiche une notification à l'écran
   - L'utilisateur doit appuyer sur un bouton de la télécommande pour approuver

2. **Récupération du challenge** :
   - Une fois approuvé, l'API retourne un challenge
   - L'application calcule une réponse HMAC-SHA1 avec ce challenge

3. **Création de la session** :
   - L'application envoie la réponse HMAC à l'API
   - L'API retourne un token de session valide

4. **Utilisation de la session** :
   - Le token de session est utilisé pour toutes les requêtes suivantes
   - Le token est stocké dans `data/config/freebox.json`

**Note** : Le certificat SSL de la Freebox est auto-signé. C'est normal et le code gère cela avec `verify=False`.

## Résolution des problèmes

- **Port déjà utilisé** : Changez le port dans `app.py` ou tuez le processus existant
- **Erreur de template** : Vérifiez que le dossier `templates/` existe
- **Données corrompues** : Supprimez les fichiers dans `data/config/` et relancez
- **Erreur 404** : Vérifiez les routes et les liens dans les templates
- **Erreur SSL** : Le certificat de la Freebox est auto-signé. C'est normal. Le code utilise `verify=False` pour contourner cela.
- **Échec d'authentification** : Vérifiez que l'URL dans `.env` est correcte et se termine par `/api/v4/`
- **Timeout d'approbation** : Assurez-vous d'appuyer sur le bouton de la Freebox dans les 30 secondes

## Migration depuis FastAPI

Cette version simplifie l'architecture en supprimant l'API interne et en utilisant directement Flask avec des templates Jinja2. Les fonctionnalités principales sont conservées :

- Gestion des chaînes TV
- Configuration de l'API Freebox
- Interface utilisateur responsive
- Stockage persistant des données

La complexité est réduite tout en maintenant les mêmes fonctionnalités de base.