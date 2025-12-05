"""Client pour l'API SIREN de l'INSEE"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Generator
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class SirenAPIClient:
    """Client pour interagir avec l'API SIREN de l'INSEE"""

    def __init__(self, consumer_key: str, consumer_secret: str,
                 base_url: str = "https://api.insee.fr/entreprises/sirene/V3",
                 timeout: int = 30, max_retries: int = 3, rate_limit_delay: float = 1.0):
        """
        Initialise le client API SIREN

        Args:
            consumer_key: Clé consumer API
            consumer_secret: Secret consumer API
            base_url: URL de base de l'API
            timeout: Timeout pour les requêtes
            max_retries: Nombre de tentatives en cas d'échec
            rate_limit_delay: Délai entre les appels (en secondes)
        """
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.base_url = base_url
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay

        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

        # Configuration de la session avec retry
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.info("Client API SIREN initialisé")

    def _get_token(self) -> str:
        """
        Obtient un token d'authentification OAuth2

        Returns:
            Token d'authentification

        Raises:
            requests.RequestException: En cas d'erreur d'authentification
        """
        # Vérifier si le token est encore valide
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token

        logger.info("Récupération d'un nouveau token OAuth2")

        auth_url = "https://api.insee.fr/token"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'client_credentials'
        }

        try:
            response = self.session.post(
                auth_url,
                headers=headers,
                data=data,
                auth=(self.consumer_key, self.consumer_secret),
                timeout=self.timeout
            )
            response.raise_for_status()

            token_data = response.json()
            self.token = token_data['access_token']

            # Le token expire généralement après 24h, on met une marge de sécurité
            expires_in = token_data.get('expires_in', 86400)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)

            logger.info("Token OAuth2 obtenu avec succès")
            return self.token

        except requests.RequestException as e:
            logger.error(f"Erreur lors de l'authentification: {e}")
            raise

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Effectue une requête à l'API

        Args:
            endpoint: Point de terminaison de l'API
            params: Paramètres de requête

        Returns:
            Réponse JSON

        Raises:
            requests.RequestException: En cas d'erreur de requête
        """
        token = self._get_token()
        url = f"{self.base_url}/{endpoint}"

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        try:
            # Respect du rate limiting
            time.sleep(self.rate_limit_delay)

            response = self.session.get(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()

            return response.json()

        except requests.RequestException as e:
            logger.error(f"Erreur lors de la requête {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Réponse: {e.response.text}")
            raise

    def get_siret_by_department(self, department: str, cursor: str = "*",
                                modified_since: Optional[str] = None,
                                nombre: int = 1000) -> Dict:
        """
        Récupère les établissements SIRET d'un département

        Args:
            department: Code département (ex: "75" pour Paris)
            cursor: Curseur de pagination (utiliser "*" pour la première page)
            modified_since: Date ISO pour récupérer uniquement les modifications (mode delta)
            nombre: Nombre de résultats par page (max 1000)

        Returns:
            Réponse JSON contenant les établissements et le curseur suivant
        """
        params = {
            'q': f'codeCommuneEtablissement:{department}*',
            'nombre': min(nombre, 1000),
            'curseur': cursor
        }

        # Ajouter le filtre de date pour le mode delta
        if modified_since:
            params['q'] += f' AND dateDernierTraitementEtablissement:[{modified_since} TO *]'

        logger.info(f"Récupération des établissements pour le département {department} "
                   f"(cursor: {cursor[:20]}...)")

        return self._make_request('siret', params)

    def get_siren_by_department(self, department: str, cursor: str = "*",
                               modified_since: Optional[str] = None,
                               nombre: int = 1000) -> Dict:
        """
        Récupère les unités légales SIREN d'un département

        Args:
            department: Code département
            cursor: Curseur de pagination
            modified_since: Date ISO pour le mode delta
            nombre: Nombre de résultats par page

        Returns:
            Réponse JSON
        """
        params = {
            'q': f'codeCommuneEtablissement:{department}*',
            'nombre': min(nombre, 1000),
            'curseur': cursor
        }

        if modified_since:
            params['q'] += f' AND dateDernierTraitementUniteLegale:[{modified_since} TO *]'

        logger.info(f"Récupération des unités légales pour le département {department}")

        return self._make_request('siren', params)

    def fetch_all_siret_by_department(self, department: str,
                                     modified_since: Optional[str] = None,
                                     batch_size: int = 1000) -> Generator[List[Dict], None, None]:
        """
        Récupère tous les établissements SIRET d'un département avec pagination automatique

        Args:
            department: Code département
            modified_since: Date ISO pour le mode delta
            batch_size: Taille des lots

        Yields:
            Lots d'établissements
        """
        cursor = "*"
        total_fetched = 0

        while True:
            try:
                response = self.get_siret_by_department(
                    department=department,
                    cursor=cursor,
                    modified_since=modified_since,
                    nombre=batch_size
                )

                # Vérifier si on a des résultats
                if 'etablissements' not in response or not response['etablissements']:
                    logger.info(f"Aucun établissement trouvé (département {department})")
                    break

                etablissements = response['etablissements']
                total_fetched += len(etablissements)

                logger.info(f"Récupéré {len(etablissements)} établissements "
                          f"(total: {total_fetched}) pour le département {department}")

                yield etablissements

                # Vérifier s'il y a d'autres pages
                header = response.get('header', {})
                cursor = header.get('curseurSuivant')

                if not cursor:
                    logger.info(f"Fin de la pagination pour le département {department}")
                    break

            except requests.RequestException as e:
                logger.error(f"Erreur lors de la récupération des données: {e}")
                raise

        logger.info(f"Total récupéré: {total_fetched} établissements pour le département {department}")

    def fetch_all_siren_by_department(self, department: str,
                                     modified_since: Optional[str] = None,
                                     batch_size: int = 1000) -> Generator[List[Dict], None, None]:
        """
        Récupère toutes les unités légales SIREN d'un département

        Args:
            department: Code département
            modified_since: Date ISO pour le mode delta
            batch_size: Taille des lots

        Yields:
            Lots d'unités légales
        """
        cursor = "*"
        total_fetched = 0

        while True:
            try:
                response = self.get_siren_by_department(
                    department=department,
                    cursor=cursor,
                    modified_since=modified_since,
                    nombre=batch_size
                )

                if 'unitesLegales' not in response or not response['unitesLegales']:
                    logger.info(f"Aucune unité légale trouvée (département {department})")
                    break

                unites = response['unitesLegales']
                total_fetched += len(unites)

                logger.info(f"Récupéré {len(unites)} unités légales "
                          f"(total: {total_fetched}) pour le département {department}")

                yield unites

                header = response.get('header', {})
                cursor = header.get('curseurSuivant')

                if not cursor:
                    logger.info(f"Fin de la pagination pour le département {department}")
                    break

            except requests.RequestException as e:
                logger.error(f"Erreur lors de la récupération des données: {e}")
                raise

        logger.info(f"Total récupéré: {total_fetched} unités légales pour le département {department}")

    def close(self):
        """Ferme la session"""
        self.session.close()
        logger.info("Session API fermée")
