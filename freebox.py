import requests
import hmac
import hashlib
from datetime import datetime
import json
from pathlib import Path

class FreeboxAPI:
    """Classe pour interagir avec l'API Freebox"""
    
    def __init__(self, api_base_url, app_token=None, session_token=None):
        self.api_base_url = api_base_url
        self.app_token = app_token
        self.session_token = session_token
        self.app_id = "fr.freebox.magneto_freebox"
        self.app_name = "Magneto Freebox"
        self.app_version = "1.0"
        self.device_name = "MagnetoFreebox"
        
    def set_tokens(self, app_token=None, session_token=None):
        """Mettre à jour les tokens"""
        if app_token:
            self.app_token = app_token
        if session_token:
            self.session_token = session_token
    
    def _make_request(self, method, endpoint, data=None, use_session=True):
        """Effectuer une requête à l'API Freebox"""
        url = f"{self.api_base_url}{endpoint}"
        headers = {}
        
        if use_session and self.session_token:
            headers['X-Fbx-App-Auth'] = self.session_token
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=10, verify=False)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10, verify=False)
            else:
                raise ValueError(f"Méthode {method} non supportée")
            
            return response
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erreur de connexion à l'API Freebox: {str(e)}")
    
    def get_auth_status(self):
        """Vérifier le statut d'authentification"""
        try:
            response = self._make_request('GET', 'login/authorize/', use_session=False)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            raise Exception(f"Erreur lors de la vérification du statut: {str(e)}")
    
    def request_authorization(self):
        """Demander une autorisation à la Freebox"""
        try:
            response = self._make_request('POST', 'login/authorize/', {
                'app_id': self.app_id,
                'app_name': self.app_name,
                'app_version': self.app_version,
                'device_name': self.device_name
            }, use_session=False)
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            raise Exception(f"Erreur lors de la demande d'autorisation: {str(e)}")
    
    def get_challenge(self):
        """Récupérer le challenge pour la création de session"""
        try:
            response = self._make_request('GET', 'login/', use_session=False)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            raise Exception(f"Erreur lors de la récupération du challenge: {str(e)}")
    
    def create_session(self, challenge):
        """Créer une session avec le challenge"""
        if not self.app_token:
            raise Exception("App token non défini")
        
        try:
            # Calculer la réponse HMAC-SHA1
            challenge_bytes = challenge.encode('utf-8')
            app_token_bytes = self.app_token.encode('utf-8')
            password_hash = hmac.new(app_token_bytes, challenge_bytes, hashlib.sha1).hexdigest()
            
            response = self._make_request('POST', 'login/session/', {
                'app_id': self.app_id,
                'password': password_hash
            }, use_session=False)
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            raise Exception(f"Erreur lors de la création de session: {str(e)}")
    
    def refresh_session(self):
        """Rafraîchir la session en utilisant le app_token stocké (sans interaction utilisateur)"""
        if not self.app_token:
            raise Exception("App token non défini, impossible de rafraîchir la session")

        challenge_result = self.get_challenge()
        if not challenge_result or not challenge_result.get('success'):
            raise Exception("Impossible de récupérer le challenge pour le rafraîchissement")

        challenge = challenge_result['result']['challenge']
        session_result = self.create_session(challenge)

        if session_result and session_result.get('success'):
            self.session_token = session_result['result']['session_token']

        return session_result

    def get_tv_channels(self):
        """Récupérer la liste des chaînes TV"""
        try:
            response = self._make_request('GET', 'tv/channels/')
            if response.status_code == 200:
                result = response.json()
                # Vérifier que le résultat est un dictionnaire avec la structure attendue
                if isinstance(result, dict) and result.get('success') is not None:
                    return result
                else:
                    # Si ce n'est pas la structure attendue, retourner une erreur standard
                    return {
                        'success': False,
                        'msg': 'Format de réponse inattendu',
                        'result': result if isinstance(result, list) else []
                    }
            return None
        except Exception as e:
            raise Exception(f"Erreur lors de la récupération des chaînes: {str(e)}")
    
    def get_channel_info(self, channel_id):
        """Récupérer les informations d'une chaîne spécifique"""
        try:
            response = self._make_request('GET', f'tv/channels/{channel_id}/')
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            raise Exception(f"Erreur lors de la récupération des infos de la chaîne: {str(e)}")
    
    def get_current_program(self, channel_id):
        """Récupérer le programme en cours sur une chaîne"""
        try:
            response = self._make_request('GET', f'tv/channels/{channel_id}/programs/current/')
            if response.status_code == 200:
                result = response.json()
                # Vérifier que le résultat est un dictionnaire avec la structure attendue
                if isinstance(result, dict) and result.get('success') is not None:
                    return result
                else:
                    # Si ce n'est pas la structure attendue, retourner une erreur standard
                    return {
                        'success': False,
                        'msg': 'Format de réponse inattendu',
                        'result': {}
                    }
            return None
        except Exception as e:
            raise Exception(f"Erreur lors de la récupération du programme en cours: {str(e)}")

class FreeboxConfig:
    """Classe pour gérer la configuration et les credentials Freebox"""
    
    def __init__(self, config_dir='data/config'):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / 'freebox.json'
    
    def load_credentials(self):
        """Charger les credentials depuis le fichier"""
        if not self.config_file.exists():
            return self._get_default_credentials()
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                # S'assurer que tous les champs existent
                return self._get_default_credentials(data)
        except Exception as e:
            print(f"Erreur lors du chargement des credentials: {str(e)}")
            return self._get_default_credentials()
    
    def save_credentials(self, credentials):
        """Sauvegarder les credentials"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(credentials, f, indent=2)
            return True
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des credentials: {str(e)}")
            return False
    
    def _get_default_credentials(self, existing_data=None):
        """Retourner les credentials par défaut"""
        default = {
            "api_base_url": "https://192.168.0.254/api/v4/",
            "app_token": None,
            "session_token": None,
            "track_id": None,
            "auth_status": "not_started",  # not_started, waiting_approval, authorized, session_created
            "challenge": None,
            "last_auth_attempt": None
        }
        
        if existing_data:
            for key, value in default.items():
                if key not in existing_data:
                    existing_data[key] = value
            return existing_data
        
        return default