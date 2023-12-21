from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from requests import post, get


class AgurContract:
    id: str | None = None
    owner: str | None = None
    address: str | None = None
    meter_id: str | None = None
    meter_serial_number: str | None = None
    meter_endpoint_number: str | None = None

    def __init__(self, json: dict[str, Any]) -> None:
        if "numeroContrat" in json:
            self.id = json["numeroContrat"]

        if "nomClientTitulaire" in json:
            self.owner = json["nomClientTitulaire"]

        if "adresseLivraisonConstruite" in json:
            self.address = json["adresseLivraisonConstruite"]

        if "identifiantAppareil" in json and json["identifiantAppareil"] != "0":
            self.meter_id = json["identifiantAppareil"]

        if "numeroPhysiqueAppareil" in json:
            self.meter_serial_number = json["numeroPhysiqueAppareil"]

        if "numeroPointLivraison" in json:
            self.meter_endpoint_number = json["numeroPointLivraison"]


class AgurDataPoint:
    value: float | None = None
    date: datetime | None = None

    def __init__(self, json: dict[str, Any]) -> None:
        if "valeurIndex" in json:
            self.value = float(json["valeurIndex"])

        if "dateReleve" in json:
            self.date = datetime.fromisoformat(json["dateReleve"])


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

    def get_contracts(self) -> list[AgurContract]:
        response = get(
            "https://ael.agur.fr/webapi/Abonnement/contrats?userWebId=&recherche=&tri=NumeroContrat&triDecroissant=false&indexPage=0&nbElements=25",
            headers={
                "ConversationId": self.app_id,
                "User-Agent": self.user_agent,
                "Token": self.auth_token,
            })
        response.raise_for_status()

        return list(map(lambda contract: AgurContract(json=contract), response.json()["resultats"]))

    def get_contract(self, contract_id: str) -> AgurContract:
        response = get(
            f"https://ael.agur.fr/webapi/Abonnement/detailAbonnement/{contract_id}",
            headers={
                "ConversationId": self.app_id,
                "User-Agent": self.user_agent,
                "Token": self.auth_token,
            })
        response.raise_for_status()

        return AgurContract(json=response.json())

    def get_data(self, contract_id) -> list[AgurDataPoint]:
        response = get(f"https://ael.agur.fr/webapi/Facturation/listeConsommationsFacturees/{contract_id}", headers={
            "ConversationId": self.app_id,
            "User-Agent": self.user_agent,
            "Token": self.auth_token,
        })
        response.raise_for_status()

        return list(map(lambda json: AgurDataPoint(json=json), response.json()["resultats"]))
