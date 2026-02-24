from flask import Flask, render_template, request, redirect, url_for, jsonify
from freebox import FreeboxAPI, FreeboxConfig
from datetime import datetime
import json

# Configuration en dur (inspirée de getprog.py)
FREEBOX_IP = "192.168.0.254"
API_BASE_URL = f"https://{FREEBOX_IP}/api/v4/"
APP_ID = "fr.freebox.magneto_freebox"
APP_NAME = "Magneto Freebox"
APP_VERSION = "1.0"
DEVICE_NAME = "MagnetoFreebox"

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['FREEBOX_API_URL'] = API_BASE_URL

# Initialiser les classes Freebox
def get_freebox_api():
    """Initialiser et retourner une instance de FreeboxAPI avec les credentials actuels"""
    config = FreeboxConfig()
    credentials = config.load_credentials()
    
    freebox_api = FreeboxAPI(
        api_base_url=credentials['api_base_url'],
        app_token=credentials['app_token'],
        session_token=credentials['session_token']
    )
    
    return freebox_api, config, credentials

def save_freebox_credentials(credentials):
    """Sauvegarder les credentials Freebox"""
    config = FreeboxConfig()
    return config.save_credentials(credentials)

def get_channels():
    config = FreeboxConfig()
    channels_file = config.config_dir / "channels.json"
    if not channels_file.exists():
        return []
    
    try:
        with open(channels_file, 'r') as f:
            data = json.load(f)
            return data.get("channels", [])
    except Exception as e:
        print(f"Erreur lors du chargement des chaînes: {str(e)}")
        return []

def save_channels(channels):
    config = FreeboxConfig()
    channels_file = config.config_dir / "channels.json"
    try:
        with open(channels_file, 'w') as f:
            json.dump({
                "channels": channels,
                "last_updated": datetime.now().isoformat()
            }, f, indent=2)
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des chaînes: {str(e)}")

def auto_refresh_session(credentials, freebox_api):
    """Tenter un rafraîchissement automatique de la session sans interaction utilisateur"""
    if not credentials.get('app_token'):
        return False
    try:
        result = freebox_api.refresh_session()
        if result and result.get('success'):
            credentials['session_token'] = result['result']['session_token']
            credentials['auth_status'] = 'session_created'
            save_freebox_credentials(credentials)
            return True
    except Exception as e:
        print(f"Échec du rafraîchissement de session: {str(e)}")
    return False


def init_default_data():
    # Initialiser les credentials Freebox si inexistants
    config = FreeboxConfig()
    
    if not config.config_file.exists():
        default_creds = config._get_default_credentials()
        config.save_credentials(default_creds)

    # Initialiser les chaînes par défaut si inexistantes
    channels_file = config.config_dir / "channels.json"
    if not channels_file.exists():
        default_channels = [
            {"id": 1, "name": "Canal+", "enabled": True, "logo": "canal_plus.png"},
            {"id": 2, "name": "Canal+ Cinéma", "enabled": True, "logo": "canal_cinema.png"},
            {"id": 3, "name": "OCS Max", "enabled": True, "logo": "ocs_max.png"},
            {"id": 4, "name": "Ciné+ Premier", "enabled": True, "logo": "cine_premier.png"}
        ]
        # Sauvegarder les chaînes directement
        with open(channels_file, 'w') as f:
            json.dump({"channels": default_channels, "last_updated": datetime.now().isoformat()}, f, indent=2)

@app.route('/')
def index():
    credentials = get_freebox_api()[2]
    # Rediriger vers la page de connexion si l'authentification n'est pas configurée
    if credentials['auth_status'] == 'not_started':
        return redirect(url_for('connection'))
    
    # Charger les chaînes sélectionnées (nouveau système)
    selected_channels = load_selected_channels()
    
    # Charger uniquement les chaînes sélectionnées depuis l'API
    try:
        freebox_api, config, creds = get_freebox_api()
        channels_result = freebox_api.get_tv_channels()
        
        # Charger les programmations PVR (si autorisé)
        recordings = []
        pvr_error = None
        try:
            # Vérifier si l'API PVR est accessible
            recordings_result = freebox_api._make_request('GET', 'pvr/programmed/')
            # Si session expirée, tenter un rafraîchissement automatique
            if recordings_result.status_code == 403:
                try:
                    body = recordings_result.json()
                    if body.get('error_code') == 'auth_required' and auto_refresh_session(creds, freebox_api):
                        recordings_result = freebox_api._make_request('GET', 'pvr/programmed/')
                except Exception:
                    pass
            if recordings_result.status_code == 200:
                recordings_data = recordings_result.json()
                if recordings_data.get('success'):
                    for recording in recordings_data.get('result', []):
                        # Convertir les timestamps Unix en dates lisibles
                        start_time = datetime.fromtimestamp(recording.get('start', 0)).strftime('%Y-%m-%d %H:%M') if recording.get('start') else 'Inconnu'
                        end_time = datetime.fromtimestamp(recording.get('end', 0)).strftime('%Y-%m-%d %H:%M') if recording.get('end') else 'Inconnu'
                        
                        recordings.append({
                            'id': recording.get('id'),
                            'title': recording.get('name', 'Sans titre'),  # name au lieu de title
                            'channel': recording.get('channel_name', 'Chaîne inconnue'),
                            'start_time': start_time,
                            'end_time': end_time,
                            'status': recording.get('state', 'inconnu')  # state au lieu de status
                        })
            elif recordings_result.status_code == 403:
                pvr_error = "Accès refusé: authentification requise pour le PVR"
            elif recordings_result.status_code == 404:
                pvr_error = "Endpoint PVR non disponible sur cette Freebox"
            else:
                pvr_error = f"Erreur PVR: {recordings_result.status_code} - {recordings_result.text}"
        except Exception as e:
            pvr_error = f"PVR non accessible: {str(e)}"
            print(f"Erreur lors du chargement des programmations: {str(e)}")
        
        if channels_result and channels_result.get('success'):
            channels_dict = channels_result.get('result', {})
            # Filtrer UNIQUEMENT les chaînes sélectionnées et disponibles
            selected_channels_list = []
            for channel_uuid, channel_data in channels_dict.items():
                if channel_data.get('available', False) and channel_data.get('uuid') in selected_channels:
                    logo_url = channel_data.get('logo_url')
                    if logo_url and not logo_url.startswith('http'):
                        logo_url = credentials['api_base_url'].replace('/api/v4/', '').replace('https://', 'http://') + logo_url
                    elif logo_url and logo_url.startswith('https://'):
                        logo_url = logo_url.replace('https://', 'http://')
                    
                    selected_channels_list.append({
                        'id': channel_data.get('uuid'),
                        'name': channel_data.get('name'),
                        'logo': logo_url,
                        'selected': True  # Toujours true puisque filtré
                    })
            
            # Trier par UUID croissant
            selected_channels_list.sort(key=lambda x: x['id'])
            return render_template('index.html',
                                 app_name=APP_NAME,
                                 credentials=credentials,
                                 channels=selected_channels_list,
                                 recordings=recordings,
                                 pvr_error=pvr_error)
    except Exception as e:
        print(f"Erreur lors du chargement des chaînes: {str(e)}")
        return render_template('index.html',
                             app_name=APP_NAME,
                             credentials=credentials,
                             channels=[],
                             recordings=[],
                             pvr_error="Erreur de connexion")

# @app.route('/settings')
# def settings():
#     return render_template('settings.html',
#                          app_name=APP_NAME,
#                          credentials=get_freebox_api()[2],
#                          channels=get_channels())

# @app.route('/toggle_channel/<int:channel_id>', methods=['POST'])
# def toggle_channel(channel_id):
#     channels = get_channels()
#     for channel in channels:
#         if channel['id'] == channel_id:
#             channel['enabled'] = not channel['enabled']
#             break
#     save_channels(channels)
#     return redirect(url_for('settings'))

@app.route('/connection')
def connection():
    return render_template('connection.html',
                         app_name=APP_NAME,
                         credentials=get_freebox_api()[2],
                         channels=get_channels())

@app.route('/update_freebox_url', methods=['POST'])
def update_freebox_url():
    freebox_url = request.form.get('freeboxUrl')
    credentials = get_freebox_api()[2]
    credentials['api_base_url'] = freebox_url
    save_freebox_credentials(credentials)
    return redirect(url_for('settings'))

@app.route('/start_authentication', methods=['POST'])
def start_authentication():
    """Démarrer le processus d'authentification"""
    credentials = get_freebox_api()[2]
    credentials['auth_status'] = 'waiting_approval'
    credentials['last_auth_attempt'] = datetime.now().isoformat()
    
    try:
        # Utiliser la nouvelle classe FreeboxAPI
        freebox_api, config, creds = get_freebox_api()
        
        # Demander un app_token à l'API Freebox
        auth_result = freebox_api.request_authorization()
        
        if not auth_result or not auth_result.get("success"):
            return jsonify({
                'success': False,
                'error': auth_result.get("msg", "Échec de la demande d'autorisation") if auth_result else "Échec de la demande d'autorisation"
            }), 500
        
        # Mettre à jour les credentials avec le track_id
        credentials['track_id'] = auth_result['result']['track_id']
        credentials['app_token'] = auth_result['result']['app_token']
        save_freebox_credentials(credentials)
        
        return jsonify({
            'success': True,
            'message': 'Demande d\'autorisation envoyée. Veuillez appuyer sur le bouton de votre Freebox.',
            'track_id': credentials['track_id']
        })
    except Exception as e:
        credentials['auth_status'] = 'not_started'
        save_freebox_credentials(credentials)
        return jsonify({
            'success': False,
            'error': f"Erreur de connexion: {str(e)}"
        }), 500

@app.route('/check_auth_status', methods=['GET'])
def check_auth_status():
    """Vérifier l'état de l'authentification"""
    credentials = get_freebox_api()[2]  # get_freebox_api() retourne (api, config, credentials)

    if credentials['auth_status'] != 'waiting_approval':
        return jsonify({'status': credentials['auth_status']})

    # Vérifier si le délai de 30 secondes a été dépassé
    if credentials.get('last_auth_attempt'):
        last_attempt = datetime.fromisoformat(credentials['last_auth_attempt'])
        if (datetime.now() - last_attempt).total_seconds() > 30:
            credentials['auth_status'] = 'not_started'
            save_freebox_credentials(credentials)
            return jsonify({'status': 'not_started', 'message': 'Délai expiré. Veuillez réessayer.'})

    try:
        # Utiliser la nouvelle classe FreeboxAPI
        freebox_api, config, creds = get_freebox_api()
        
        # Vérifier si l'utilisateur a approuvé sur la Freebox
        auth_status_result = freebox_api.get_auth_status()
        
        if not auth_status_result or not auth_status_result.get("success"):
            return jsonify({
                'status': 'waiting_approval',
                'message': auth_status_result.get("msg", "En attente...") if auth_status_result else "En attente d'approbation...",
                'current_status': auth_status_result.get("result", {}).get("status") if auth_status_result else None
            })

        # Si approuvé, récupérer le challenge pour la session
        if auth_status_result['result']['status'] == 'granted':
            # Récupérer le challenge
            challenge_result = freebox_api.get_challenge()
            
            if not challenge_result or not challenge_result.get("success"):
                return jsonify({
                    'status': 'error',
                    'message': challenge_result.get("msg", "Impossible de récupérer le challenge") if challenge_result else "Impossible de récupérer le challenge"
                }), 500

            credentials['auth_status'] = 'authorized'
            credentials['challenge'] = challenge_result['result']['challenge']
            save_freebox_credentials(credentials)
            
            # Créer automatiquement la session
            try:
                session_result = create_session_helper(credentials)
                if session_result['success']:
                    return jsonify({
                        'status': 'session_created',
                        'message': 'Session créée avec succès!',
                        'session_token': credentials['session_token']
                    })
                else:
                    # Si la création automatique échoue, garder le statut authorized
                    # pour permettre une tentative manuelle
                    return jsonify({
                        'status': 'authorized',
                        'message': 'Authentification approuvée! La création automatique de session a échoué.',
                        'challenge': credentials['challenge'],
                        'error': session_result.get('error', 'Erreur inconnue')
                    })
            except Exception as e:
                return jsonify({
                    'status': 'authorized',
                    'message': 'Authentification approuvée! La création automatique de session a échoué.',
                    'challenge': credentials['challenge'],
                    'error': str(e)
                })

        return jsonify({
            'status': 'waiting_approval',
            'message': 'En attente d\'approbation...',
            'current_status': auth_status_result['result']['status']
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f"Erreur de connexion: {str(e)}"
        }), 500

def create_session_helper(credentials):
    """Helper pour créer une session - utilisée par check_auth_status et create_session"""
    if credentials['auth_status'] != 'authorized':
        return {
            'success': False,
            'error': 'Authentification non approuvée. Veuillez d\'abord obtenir une approbation.'
        }

    if not credentials['challenge']:
        return {
            'success': False,
            'error': 'Aucun challenge disponible. Le processus d\'authentification semble incomplet.'
        }

    try:
        # Utiliser la nouvelle classe FreeboxAPI
        freebox_api, config, creds = get_freebox_api()
        freebox_api.set_tokens(app_token=credentials['app_token'])
        
        # Créer la session
        session_result = freebox_api.create_session(credentials['challenge'])
        
        if not session_result or not session_result.get("success"):
            return {
                'success': False,
                'error': session_result.get("msg", "Échec de la création de session") if session_result else "Pas de réponse de l'API",
                'error_code': session_result.get("error_code") if session_result else None
            }

        # Mettre à jour les credentials
        credentials['session_token'] = session_result['result']['session_token']
        credentials['auth_status'] = 'session_created'
        credentials['last_auth_attempt'] = datetime.now().isoformat()
        save_freebox_credentials(credentials)

        return {
            'success': True,
            'message': 'Session créée avec succès!',
            'session_token': credentials['session_token'],
            'permissions': session_result['result'].get('permissions', {})
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Erreur de connexion: {str(e)}"
        }


@app.route('/create_session', methods=['POST'])
def create_session():
    """Créer une session après approbation - endpoint conservé pour compatibilité"""
    credentials = get_freebox_api()[2]
    result = create_session_helper(credentials)
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': result['message'],
            'session_token': result['session_token'],
            'permissions': result['permissions']
        })
    else:
        return jsonify({
            'success': False,
            'error': result['error'],
            'details': result.get('details')
        }), 400

@app.route('/logout', methods=['POST'])
def logout():
    """Déconnecter et réinitialiser la session"""
    credentials = get_freebox_api()[2]
    credentials['session_token'] = None
    credentials['auth_status'] = 'not_started'
    credentials['challenge'] = None
    save_freebox_credentials(credentials)
    return jsonify({
        'success': True,
        'message': 'Déconnexion réussie. Vous pouvez démarrer une nouvelle authentification.'
    })

@app.route('/channels')
def channels():
    """Afficher la liste des chaînes TV"""
    try:
        freebox_api, config, credentials = get_freebox_api()
        
        if credentials['auth_status'] != 'session_created':
            return redirect('/connection')
        
        # Récupérer les chaînes depuis l'API Freebox
        channels_result = freebox_api.get_tv_channels()
        
        # Vérifier que la réponse est bien un dictionnaire
        if not channels_result or not isinstance(channels_result, dict) or not channels_result.get('success'):
            if isinstance(channels_result, str):
                error_msg = channels_result
            else:
                error_msg = channels_result.get('msg', 'Impossible de récupérer les chaînes') if channels_result else 'Impossible de récupérer les chaînes'
            return render_template('channels.html', error=error_msg, channels=[])
        
        # La réponse contient un dictionnaire de chaînes, pas une liste
        channels_dict = channels_result.get('result', {})
        
        # Charger les sélections existantes
        selected_channels = load_selected_channels()
        
        # Récupérer uniquement les chaînes disponibles
        channels_with_info = []
        for channel_uuid, channel_data in channels_dict.items():
            # Ne garder que les chaînes disponibles
            if not channel_data.get('available', False):
                continue
            
            # Construire l'URL complète du logo si nécessaire
            logo_url = channel_data.get('logo_url')
            if logo_url and not logo_url.startswith('http'):
                # Si l'URL est relative, la préfixer avec l'URL de base de la Freebox en HTTP
                logo_url = credentials['api_base_url'].replace('/api/v4/', '').replace('https://', 'http://') + logo_url
            elif logo_url and logo_url.startswith('https://'):
                # Forcer HTTP même si l'URL est déjà absolue en HTTPS
                logo_url = logo_url.replace('https://', 'http://')
            
            # Récupérer uniquement les propriétés réellement disponibles et utiles
            channel_info = {
                'id': channel_data.get('uuid'),
                'name': channel_data.get('name'),
                'short_name': channel_data.get('short_name'),
                'logo': logo_url,
                'available': True,  # Toujours true après filtrage
                'favorite': channel_data.get('favorite', False),
                'selected': channel_data.get('uuid') in selected_channels  # État de sélection
            }
            
            channels_with_info.append(channel_info)
        
        # Trier les chaînes par UUID croissant
        channels_with_info.sort(key=lambda x: x['id'])
        
        return render_template('channels.html', channels=channels_with_info, error=None)
        
    except Exception as e:
        return render_template('channels.html', error=str(e), channels=[])

def load_selected_channels():
    """Charger la liste des chaînes sélectionnées depuis le fichier JSON"""
    config = FreeboxConfig()
    selected_file = config.config_dir / "selected_channels.json"
    
    if not selected_file.exists():
        return set()
    
    try:
        with open(selected_file, 'r') as f:
            data = json.load(f)
            return set(data.get('selected', []))
    except Exception as e:
        print(f"Erreur lors du chargement des sélections: {str(e)}")
        return set()

def save_selected_channels(selected_channels):
    """Sauvegarder la liste des chaînes sélectionnées dans un fichier JSON"""
    config = FreeboxConfig()
    selected_file = config.config_dir / "selected_channels.json"
    
    try:
        with open(selected_file, 'w') as f:
            json.dump({'selected': list(selected_channels)}, f, indent=2)
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des sélections: {str(e)}")
        return False

@app.route('/toggle_selection/<channel_id>', methods=['POST'])
def toggle_selection(channel_id):
    """Basculer la sélection d'une chaîne"""
    try:
        # Charger les sélections actuelles
        selected_channels = load_selected_channels()
        
        # Basculer l'état de sélection
        if channel_id in selected_channels:
            selected_channels.remove(channel_id)
        else:
            selected_channels.add(channel_id)
        
        # Sauvegarder les modifications
        save_selected_channels(selected_channels)
        
        return jsonify({'success': True, 'selected': list(selected_channels)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    init_default_data()
    app.run(host='0.0.0.0', port=8030, debug=app.config['DEBUG'])
