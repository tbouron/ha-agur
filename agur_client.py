import uuid
from typing import Any

from requests import post, get


class AgurClient:
    app_id = str(uuid.uuid4())
    # TODO: This should come from the integration configuration? Maybe?
    access_key = "XX_fr-5DjklsdMM-AGR-PRD"
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/113.0"
    session_token = None
    auth_token = None

    def __init__(self, session_token: str = None, auth_token: str = None):
        self.session_token = session_token
        self.auth_token = auth_token

    def init(self) -> dict[str, Any]:
        response = post("https://ael.agur.fr/webapi/Acces/generateToken", headers={
            "ConversationId": self.app_id,
            "Token": self.access_key,
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": self.user_agent,
        }, json={
            "ConversationId": self.app_id,
            "ClientId": "AEL-TOKEN-AGR-PRD",
            "AccessKey": self.access_key,
        })
        response.raise_for_status()

        return response.json()

    def login(self, username, password) -> dict[str, Any]:
        response = post("https://ael.agur.fr/webapi/Utilisateur/authentification", headers={
            "ConversationId": self.app_id,
            "Token": self.session_token,
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": self.user_agent,
        }, json={
            "identifiant": username,
            "motDePasse": password,
        })
        response.raise_for_status()

        return response.json()

    def get_contracts(self) -> list[dict[str, Any]]:
        response = get(
            "https://ael.agur.fr/webapi/Abonnement/contrats?userWebId=&recherche=&tri=NumeroContrat&triDecroissant=false&indexPage=0&nbElements=25",
            headers={
                "ConversationId": self.app_id,
                "User-Agent": self.user_agent,
                "Token": self.auth_token,
            })
        response.raise_for_status()

        return list(map(lambda contract: {
            "id": contract["numeroContrat"],
            "owner": contract["nomClientTitulaire"],
            "address": contract["adresseLivraisonConstruite"]
        }, response.json()["resultats"]))

    def get_data(self, contract_id) -> list[dict[str, Any]]:
        response = get(f"https://ael.agur.fr/webapi/Facturation/listeConsommationsFacturees/{contract_id}", headers={
            "ConversationId": self.app_id,
            "User-Agent": self.user_agent,
            "Token": self.auth_token,
        })
        response.raise_for_status()

        return list(response.json()["resultats"])
