from fastapi import FastAPI, Request,Form,WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pickle as pkl
import pandas as pd
from fastapi.templating import Jinja2Templates
from pathlib import Path
from starlette.staticfiles import StaticFiles

from typing import List
import asyncio
import json
import aiomqtt
import random

from collections import deque
from datetime import datetime, timedelta
import aiosqlite
import requests
from datetime import datetime,date,timedelta
# Coordonnées de Lokossa (Bénin)
latitude = 6.633
longitude = 1.717
# declaration de variable
maxProdValue = 0  # Valeur maximale de production trouvée
activeSource =["batt","solarPannel"] # les sources a activer
# url open meteo
weather_url = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={latitude}&longitude={longitude}"
    f"&hourly=windspeed_10m,sunshine_duration,pressure_msl,shortwave_radiation,temperature_2m,relativehumidity_2m,weathercode"
    f"&timezone=auto&forecast_days=1"
)

# fonction récupérer les données météorologique
def getWeatherData():
    # Requête GET
    print("requette vers open-météo")
    response = requests.get(weather_url)
    print("fin de requette vers open-météo")
    data = response.json()  # Dictionnaire Python
    
    if "error" in data:
        return("Erreur API :", data["reason"])

    else:
        # Extraction des listes horaires
        hourly = data["hourly"]
        return {
            "WindSpeed": hourly["windspeed_10m"],
            "Sunshine": [s/60 for s in hourly["sunshine_duration"]],         
            "AirPressure": hourly["pressure_msl"],
            "Radiation": hourly["shortwave_radiation"],     
            "AirTemperature": hourly["temperature_2m"],
            "RelativeAirHumidity": hourly["relativehumidity_2m"],
            "Hour": [datetime.fromisoformat(t).hour for t in hourly["time"]],            
            "Month": [datetime.fromisoformat(t).month for t in hourly["time"]], 
            "weatherCode" : hourly["weathercode"]            
        } 
try :
    # weatherData =  getWeatherData()
    weatherData = {'WindSpeed': [6.0, 8.7, 4.2, 5.0, 4.6, 4.3, 4.1, 3.5, 4.4, 7.7, 5.5, 5.7, 5.4, 5.2, 8.4, 11.7, 9.4, 9.4, 13.0, 9.7, 8.8, 7.6, 5.5, 3.7], 'Sunshine': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 15.255166666666666, 0.0, 0.0, 0.0, 0.0], 'AirPressure': [1012.4, 1012.5, 1011.9, 1011.5, 1010.9, 1011.2, 1011.9, 1012.3, 1013.0, 1013.9, 1013.8, 1013.3, 1012.7, 1011.9, 1010.5, 1009.7, 1008.6, 1008.4, 1008.8, 1009.6, 1010.7, 1011.5, 1012.2, 1012.6], 'Radiation': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.0, 108.0, 318.0, 492.0, 683.0, 804.0, 861.0, 841.0, 644.0, 594.0, 363.0, 196.0, 49.0, 0.0, 0.0, 0.0, 0.0], 'AirTemperature': [25.9, 25.8, 25.6, 25.3, 24.8, 24.7, 24.4, 24.4, 26.0, 28.1, 29.5, 30.8, 31.8, 32.5, 32.3, 31.0, 31.6, 30.9, 29.9, 28.5, 27.6, 26.9, 26.5, 26.1], 'RelativeAirHumidity': [84, 84, 86, 87, 90, 90, 92, 94, 89, 80, 72, 67, 63, 61, 62, 67, 64, 65, 71, 77, 82, 85, 87, 90], 'Hour': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'Month': [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4], 'weatherCode': [3, 1, 3, 2, 3, 3, 3, 0, 0, 1, 1, 1, 51, 0, 51, 55, 51, 51, 51, 3, 3, 3, 3, 3]}

except Exception as e: 
    print("error-----------------------------------------")
# initialisation de la BDD
async def init_db():
    print("database initiated")
    async with aiosqlite.connect("energy.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS consommation(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                consommationReel REAL,
                consommationPred REAL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON consommation(timestamp)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS production(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                productionReel REAL,
                productionPred REAL,
                windSpeed REAL,
                sunshine REAL,
                airPressure REAL,
                radiation REAL,
                airTemperature REAL,
                relativeHumidity REAL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON production(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON consommation(timestamp)")
        await db.commit()
app =FastAPI()
base_path = Path(__file__).resolve().parent.parent

# dossier de fichier statique a servir a  l'interface
app.mount("/static", StaticFiles(directory=f"{base_path}/static"), name="static")

# dossier contenant les différentes fichier html ou css a retourner
templates = Jinja2Templates(directory = base_path/"client/interface")
start_time = datetime.now()
# fonction a executer tout les 24h

async def cycle24h():
    while True:
        weatherData = getWeatherData()
        
# fonction a executer toute les heures


async def cycle1h():
    while True:
        await asyncio.sleep(3600)  # attend 1 heure
        # Action à faire toutes les heures
        # insérer les données dans la BDD
        async with aiosqlite.connect("energy.db") as db:
            await db.execute("INSERT INTO consommation (consommation) VALUES (?)", (conso_cumul.energie_kwh,))
            if not("Erreur API " in str(weatherData)):
                try:
                    # Récupérer l'heure actuelle pour obtenir l'indice dans les listes
                    current_hour = datetime.now().hour
                    
                    # Extraire les valeurs scalaires correspondant à l'heure actuelle
                    wind_speed = weatherData["WindSpeed"][current_hour] if isinstance(weatherData["WindSpeed"], list) else weatherData["WindSpeed"]
                    sunshine = weatherData["Sunshine"][current_hour] if isinstance(weatherData["Sunshine"], list) else weatherData["Sunshine"]
                    air_pressure = weatherData["AirPressure"][current_hour] if isinstance(weatherData["AirPressure"], list) else weatherData["AirPressure"]
                    radiation = weatherData["Radiation"][current_hour] if isinstance(weatherData["Radiation"], list) else weatherData["Radiation"]
                    air_temperature = weatherData["AirTemperature"][current_hour] if isinstance(weatherData["AirTemperature"], list) else weatherData["AirTemperature"]
                    relative_humidity = weatherData["RelativeAirHumidity"][current_hour] if isinstance(weatherData["RelativeAirHumidity"], list) else weatherData["RelativeAirHumidity"]
                    
                    await db.execute(
                        """INSERT INTO production 
                        (production, windSpeed, sunshine, airPressure, radiation, airTemperature, relativeHumidity)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (prod_cumul.energie_kwh, wind_speed, sunshine, air_pressure, radiation, air_temperature, relative_humidity)
                    )
                    await db.commit()
                    print("donnée inséré dans la BDD")
                except IndexError as e:
                    print(f"Erreur: indice heure hors limites - {e}")
                except Exception as e:
                    print(f"Erreur lors de l'insertion de la production: {e}")
        # calculer le pic de production avec les données de la BDD
        global maxProdValue
        maxProdValue = await maxProd(maxProdValue)
        print(f"Une heure s'est écoulée depuis {start_time}")

# fonction pour calculer le pic de production par jours
async def maxProd(prevMaxProdValue):
    allProd = await get_all_production()
    if not "error" in allProd :
        for i in range(allProd["count"]) :
            prevMaxProdValue = allProd["data"][i]["production"] if allProd["data"][i]["production"]> prevMaxProdValue else prevMaxProdValue
            return prevMaxProdValue
    else:
        return "error" 
       
    
# Event Startup - Démarrer le client MQTT
@app.on_event("startup")
async def startup_event():
    """Démarre le client MQTT au démarrage de l'application"""
    global maxProdValue
    asyncio.create_task(mqtt_client.start())
    print("[SERVER] Client MQTT démarré")
    asyncio.create_task(cycle1h())
    await init_db() 
    maxProdValue = await maxProd(0)

available_source = ["solarPannel","batt","sbee"]
# Dictionnaire global pour stocker les données en temps réel
sensor_data = {
    "production": 0,
    "consommation": 0,
    "battPercentage" : 0,
    "activeSource" :"solarPannel",
    "timestamp": None,
    "sbee" : None,
}

# Cache des dernières données envoyées pour éviter les doublons
last_sent_data = None

# Classe MQTT pour récupérer les données
class MQTTClient:
    def __init__(self, broker="localhost", port=1883):
        self.broker = broker
        self.port = port
        self.running = False
    
    async def start(self):
        """Démarre le client MQTT et écoute les topics"""
        self.running = True
        try:
            async with aiomqtt.Client(self.broker, self.port) as client:
                print(f"[MQTT] Connecté au broker {self.broker}:{self.port}")
                await client.subscribe("maison/#")
                print("[MQTT] Souscrit aux topics: maison/#")
                
                async for message in client.messages:
                    topic = str(message.topic)
                    payload = message.payload.decode()
                    print(f"topic : {topic}")
                    
                    # Mettre à jour le timestamp à chaque message
                    sensor_data["timestamp"] = asyncio.get_event_loop().time()
                    
                    # Extraction des données du topic
                    if "production" in topic:
                        sensor_data["production"] = float(payload) / 1000  # Conversion en kW 
                        # Si production > 0, source active = solaire
                    elif "consommation" in topic:
                        sensor_data["consommation"] = float(payload) / 1000  # Conversion en kW
                    elif "battPercentage" in topic:
                        sensor_data["battPercentage"] = float(payload)
                    elif "sbee" in topic:
                        sensor_data["sbee"] = bool(int(payload))
                        
                    # mise a jour des données stratégiques
                    predictionData["battPercentage"] = sensor_data["battPercentage"]
                    predictionData["sbee"] = sensor_data["sbee"]
                    # vérification de la sbee et lancement d'une nouvelle stratégie
                    if not sensor_data["sbee"]:
                        print("changement de stratégie--------------------------------------- ")
                        hourlyStrategy(predictionData)
                    # Log des données mises à jour
                    print(f"[MQTT] Données actuelles: {sensor_data}")
        except Exception as e:
            print(f"[MQTT ERROR] {e}")
            self.running = False
# classe pour stocker la production instantanée afin d'obtenir la production et la consommation horaire
class EnergyCumul:
    def __init__(self, duree_heures=1):
        self.duree = timedelta(hours=duree_heures)
        self.echantillons = deque()  # (timestamp, puissance_watts)

    def ajouter(self, puissance_w, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now()
        self.echantillons.append((timestamp, puissance_w))
        self._nettoyer()

    def _nettoyer(self):
        limite = datetime.now() - self.duree
        while self.echantillons and self.echantillons[0][0] < limite:
            self.echantillons.popleft()

    def energie_wh(self):
        """Énergie sur la période glissante (Watt-heures)"""
        if len(self.echantillons) < 2:
            return 0.0
        energie = 0.0
        for i in range(1, len(self.echantillons)):
            t1, p1 = self.echantillons[i-1]
            t2, p2 = self.echantillons[i]
            dt_sec = (t2 - t1).total_seconds()
            p_moy = (p1 + p2) / 2.0
            energie += p_moy * (dt_sec / 3600.0)  # Wh
        return energie

    @property
    def energie_kwh(self):
        return self.energie_wh() / 1000.0
# Initialisation des cumuls
prod_cumul = EnergyCumul(duree_heures=1)
conso_cumul = EnergyCumul(duree_heures=1)
prod_cumul_24h = EnergyCumul(duree_heures=24)
conso_cumul_24h = EnergyCumul(duree_heures=24)
# Instancier et démarrer l'écoute du client MQTT global
mqtt_client = MQTTClient()

# web socket


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        # Créer une liste des connexions à supprimer
        connections_to_remove = []
        for connection in self.active_connections[:]:  # Copie de la liste
            try:
                await connection.send_text(message)
            except Exception as e:
                # Si l'envoi échoue, marquer la connexion pour suppression
                print(f"Erreur lors de l'envoi WebSocket: {e}")
                connections_to_remove.append(connection)

        # Supprimer les connexions défaillantes
        for connection in connections_to_remove:
            if connection in self.active_connections:
                self.active_connections.remove(connection)
                print(f"Connexion WebSocket supprimée: {len(self.active_connections)} connexions actives")

manager = ConnectionManager()

# web socket

@app.get("/")
async def formular(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="main.html",
    )
@app.get("/analyse_ia")
async def formular(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="analyse_IA.html",
    )  
# 
@app.post("/formulaire",response_class = HTMLResponse)
def handle_form(request:Request,windspeed :str  = Form(...)):
    context ={
        "request" :request,
        "windspeed" : windspeed,
    }
    return templates.TemplateResponse(
        request=request,
        name="main.html",
        context=context
    )

# model de classe
#model de classe pour la prédiction
class prod_data(BaseModel):
    WindSpeed: list
    Sunshine: list         # Plein soleil (60 minutes )
    AirPressure: list
    Radiation: list     
    AirTemperature: list
    RelativeAirHumidity: list
    Hour: list
    Month: list
   
# chargement des model :
# model de  prédiction de la consommation
with open("model/conso_model.pkl","rb") as f:
    model_conso = pkl.load(f)

# model de production de la production solaire

with open("model/solar_model.pkl","rb") as f:
    model_prod = pkl.load(f)
  
# endpoint pour predire la production
@app.post("/prediction/production")
def getPredProd(data :prod_data) :
    # Transformer les données Pydantic en dictionnaire puis en DataFrame
    data_dict = data.model_dump()
    df = pd.DataFrame(data_dict)
    
    # Convertir toutes les colonnes en numériques (float)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    # Faire la prédiction pour chaque heure
    predictions = model_prod.predict(df)
    # Créer une liste de prédictions horaires
    hourly_predictions = []
    for i, pred in enumerate(predictions):
        # Convertir numpy.float32 en float Python
        pred_float = float(pred)
        hourly_predictions.append({
            "hour": int(df.iloc[i]["Hour"]),
            "prediction_kw": round(pred_float / 1000, 2),
            "prediction_wh": round(pred_float, 2)
        })
    
    # Calculer la production totale journalière (convertir en float)
    total_production = sum(float(p) for p in predictions)
    
    return{
        "hourly_predictions": hourly_predictions,
        "total_daily_production": {
            "kw": round(total_production / 1000, 2),
            "wh": round(total_production, 2)
        },
        "dataset_info": {
            "rows": len(df),
            "columns": df.columns.tolist(),
            "hours_covered": sorted([int(h) for h in df["Hour"].unique()])
        }
    }
 
    
# endpoint pour prédire la consommation

class conso_data(BaseModel):
    heure: int
    est_weekend : int #weekend
    est_jour_ferie: int #jour férié
    saison_Saison_chaude: int # saison chaude
    saison_Saison_Pluies: int #saison pluvieuse
 
    
@app.post("/prediction/consommation")
def getPredConso(data :conso_data):
    df = pd.DataFrame([[data.heure, data.est_weekend, data.est_jour_ferie, data.saison_Saison_chaude, data.saison_Saison_Pluies]], 
                      columns=['heure', 'est_weekend', 'est_jour_ferie', 'saison_Saison_Chaude', 'saison_Saison_Pluies'])
    #return{ "prediction de consommation" : f"{model_conso.predict(df)[0]:.2f}Kw a {data.heure}"}
    return{ "prediction de consommation" : round(model_conso.predict(df)[0], 2)}

# endpoint pour récuperer les données météorologiques 
@app.get('/weather')
async def get_hourly_weather_data():
    """Retourne les données météorologiques actuelles"""
    try:
        if isinstance(weatherData, dict) and "error" not in str(weatherData):
            return {
                "WindSpeed": weatherData.get("WindSpeed", []),
                "Sunshine": weatherData.get("Sunshine", []),
                "AirPressure": weatherData.get("AirPressure", []),
                "Radiation": weatherData.get("Radiation", []),
                "AirTemperature": weatherData.get("AirTemperature", []),
                "RelativeAirHumidity": weatherData.get("RelativeAirHumidity", []),
                "Hour": weatherData.get("Hour", []),
                "Month": weatherData.get("Month", []),
                "weatherCode" : weatherData.get("weatherCode",[]),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {"error": "Impossible de récupérer les données météorologiques"}
    except Exception as e:
        return {"error": f"Erreur: {str(e)}"}


# prédictions de la production pour la journée d'aujourd'hui
def getPred(weatherData):
    cle = ["WindSpeed","Sunshine","AirPressure","Radiation","AirTemperature","RelativeAirHumidity","Hour","Month"]
    weather_dict = {k:weatherData[k] for k in cle if k in weatherData}
    # Créer une instance du modèle Pydantic
    prod_data_instance = prod_data(**weather_dict)
    predProd = getPredProd(prod_data_instance)
    return predProd

# prédiction de la consommation pour une journée
def getConso(data):
    we = data[0]
    jf = data[1]
    sp = data[2]
    sc = data[3]
    hourly_pred_conso = []
    for i in range(24):
        consoData = {
            'heure': i,
            'est_weekend': we, #weekend
            'est_jour_ferie': jf, #jour férié
            'saison_Saison_chaude': sc, # saison chaude
            'saison_Saison_Pluies': sp #saison pluvieuse
        }
        conso_data_instance = conso_data(**consoData)
        hourly_pred_conso.append(getPredConso(conso_data_instance))
    return hourly_pred_conso

# ----- Fonctions internes (ne pas appeler directement) -----
def _est_jour_ferie_benin(date_heure):
    """Retourne True si la date (ignorant l'heure) est un jour férié béninois."""
    jour = date_heure.date()
    # Jours fixes
    fixes = {
        (1, 1),   # Nouvel An
        (1, 10),  # Fête du Vodoun
        (5, 1),   # Fête du Travail
        (8, 1),   # Indépendance
        (8, 15),  # Assomption
        (11, 1),  # Toussaint
        (12, 25)  # Noël
    }
    if (jour.month, jour.day) in fixes:
        return True
    
    # Lundi de Pâques (algorithme de Butcher)
    annee = jour.year
    a = annee % 19
    b = annee // 100
    c = annee % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois_paques = (h + l - 7 * m + 114) // 31
    jour_paques = ((h + l - 7 * m + 114) % 31) + 1
    paques = date(annee, mois_paques, jour_paques)
    lundi_paques = paques + timedelta(days=1)
    
    return jour == lundi_paques


def _get_saisons_lokossa(date_heure):
    """
    Retourne (saison_chaude, saison_pluies) pour Lokossa.
    Saison chaude (sèche) : novembre à février (mois 11,12,1,2)
    Saison des pluies   : mars à octobre (mois 3 à 10)
    """
    mois = date_heure.month
    saison_chaude = 1 if mois in (11, 12, 1, 2) else 0
    saison_pluies = 1 if 3 <= mois <= 10 else 0
    return saison_chaude, saison_pluies

def analyser_lokossa(date_heure=None):
    """
    Analyse la date et l'heure pour Lokossa.
    
    Paramètre :
        date_heure (datetime ou date, optionnel) : Objet datetime ou date à analyser.
            - Si None, utilise la date et l'heure actuelles.
            - Si un objet date est passé (sans heure), l'heure est fixée à 0.
            - Si un objet datetime est passé, l'heure est conservée.
    
    Retourne :
        dict : {
            'heure': int (0-23),
            'est_weekend': 0 ou 1,
            'est_jour_ferie': 0 ou 1,
            'saison_Saison_chaude': 0 ou 1,
            'saison_Saison_Pluies': 0 ou 1
        }
    """
    # 1. Déterminer la date/heure avec valeur par défaut
    if date_heure is None:
        maintenant = datetime.now()
    elif isinstance(date_heure, datetime):
        maintenant = date_heure
    elif isinstance(date_heure, date):
        # Si seulement une date (pas d'heure), on met l'heure à 0
        maintenant = datetime.combine(date_heure, datetime.min.time())
    else:
        raise TypeError("date_heure doit être datetime, date ou None")
    
    # 2. Heure
    heure = maintenant.hour
    
    # 3. Weekend (samedi=5, dimanche=6)
    est_weekend = 1 if maintenant.weekday() >= 5 else 0
    
    # 4. Jour férié (Bénin)
    est_jour_ferie = 1 if _est_jour_ferie_benin(maintenant) else 0
    
    # 5. Saisons pour Lokossa
    sc, sp = _get_saisons_lokossa(maintenant)
    
    return [est_weekend,est_jour_ferie,sc,sp]


# analyse de la journée et extraction des donnée de prédiciton de la consommation
predictionData = {
        "battPercentage" : 100,
        "sbee" : sensor_data["sbee"],
        "predProd" : getPred(weatherData), 
        "predConso" : getConso(analyser_lokossa()),
    }
# fonction de décision!
def logique(conso, prod,battPercentage,battTotalCapacity,seuil,sbee):
    # production supérieure a la consommmation
    if prod> conso:
        # vérifier si il faut charger les batterie
        if battPercentage >= 70 :
            return {
                "sourceActive"  : ["solarPannel"],
                "chargerBatt" : False,
                "mode":"normal"
            }
        elif battPercentage < 70 : 
            # peut ton charger la batt pendant qu'on alimente l'installation ?
            puissanceRestante = prod - conso
            if puissanceRestante >= seuil : 
                return {
                    "sourceActive" : ["solarPannel"],
                    "chargerBatt" : True,
                    "mode":"normal"
                }
    # production inférieure a la consommation : 
    elif prod< conso : 
        # vérifier si la battérie peut fournir l'énergie néccessaire pour les 1h tout en restant >=20%?
        battEnergy = (battPercentage * battTotalCapacity)/100
        if battEnergy >= conso :  
            # on peut basculer sur la batterie mais pourrons nous la recharger plustard?
            return {
                "sourceActive" : ["batt"],
                "chargerBatt" : False,
                "mode":"normal"
            }
        elif battEnergy+prod >= conso :
            # combinaison des deux sources
            return{
                "sourceActive": ["batt","solarPannel"],
                "chargerBatt" : False,
                "mode":"normal"
            }
        elif battEnergy+prod < conso:
            # aucune des sources renouvelables n'est suffisant :
            if sbee: 
                return{
                    "sourceActive" : ["sbee"],
                    "chargerBatt" : True if prod>=seuil else False,
                    "mode" : "saving"
                }
            else :
                # sbee abscent donc il faut retourner sur le combo PS+Batt et activer le mode ultra  économie
                return{
                    "sourceActive": ["batt","solarPannel"],
                    "chargerBatt" : False,
                    "mode" : "ultraSaving"
                } 
    elif prod == conso:
    # production est égale a la consommation
        if battPercentage>=70 : 
            return{
                    "sourceActive": ["solarPannel"],
                    "chargerBatt" : False,
                    "mode" : "normal"
                }
        else :
            return{
                    "sourceActive": ["sbee"] if sbee else ["solarPannel"],
                    "chargerBatt" : True if sbee else False,
                    "mode" : "normal" if sbee else "ultraSaving"
                }
# création des stratégies horaire pour la journée
def hourlyStrategy(predictionData):
    strategy =[]
    hourly_prod = predictionData["predProd"]["hourly_predictions"]
    hourly_conso = predictionData["predConso"]
    for i in range(24):
        lo = logique(hourly_conso[i]['prediction de consommation'],hourly_prod[i]['prediction_wh'],predictionData["battPercentage"],3000,1000,predictionData["sbee"])
        strategy.append(lo)
    return strategy
# variable contenant la stratégie a adopter par le système pour une journée:
strategie = hourlyStrategy(predictionData)
# fonction pour activer le mode de fonctionnement
def activateMode(mode):
    if mode == "normal":
        return "Mode normal Activé. Tout les appareils sont autorisé a fonctionner"
    elif mode == "saving":
        return "Mode Economie Activé, desormains les appareils de forte consommation sont désactiver pour économiser l'énergie"
    elif mode == "ultraSaving":
        return "mode ultra économie activé, seul les appareils de premières néccésité sont activé"
# fonction pour application de la strategie:
def applyStrategy():
    nowStrategy = strategie[datetime.now().hour]
    if nowStrategy["chargerBat"]:
        # activer le chargement des batterie
        print("chargement des battéries: Autoriser le relais ")
    activateMode(nowStrategy["mode"])

@app.websocket("/ws/energy")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    print(f"Nouvelle connexion WebSocket: {len(manager.active_connections)} connexions actives")

    # Envoyer immédiatement les données actuelles à la connexion
    if sensor_data["timestamp"] is not None:
        initial_data = {
            "production": f"{sensor_data['production']:.2f}",
            "consommation": f"{sensor_data['consommation']:.2f}",
            "timestamp": sensor_data["timestamp"],
            "battPercentage" : f"{predictionData['battPercentage']:.2f}",
            "activeSource"  : activeSource,
        }
        try:
            await websocket.send_text(json.dumps(initial_data))
            print("Données initiales envoyées à la nouvelle connexion")
        except Exception as e:
            print(f"Erreur lors de l'envoi des données initiales: {e}")
            return

    try:
        while True:
            # cumule des données 
            prod_cumul.ajouter(sensor_data['production'])
            conso_cumul.ajouter(sensor_data['consommation'])
            prod_cumul_24h.ajouter(sensor_data['production'])
            conso_cumul_24h.ajouter(sensor_data['consommation'])
            # récuperer la stratégie
            strategie = hourlyStrategy(predictionData)
            # Créer les données actuelles
            current_data = {
                "production": f"{sensor_data['production']:.2f}",
                "consommation": f"{sensor_data['consommation']:.2f}",
                "timestamp": sensor_data["timestamp"],
                "battPercentage" : f"{sensor_data['battPercentage']:.2f}",
                "activeSource"  : strategie[datetime.now().hour]["sourceActive"],
                "production_h" : round(prod_cumul.energie_kwh,3),
                "consommation_h" : round(conso_cumul.energie_kwh,3),
                "production_24h" : round(prod_cumul_24h.energie_kwh,3),
                "maxProd" : round(maxProdValue,3),
                "consommation_24h" : round(conso_cumul_24h.energie_kwh,3),
                "sbee" : predictionData["sbee"],
                "strategie" : strategie
            }            
            # insérer dans la base de données après 1H
            # N'envoyer que si les données ont changé
            global last_sent_data
            if last_sent_data != current_data and sensor_data["timestamp"] is not None:
                await manager.broadcast(json.dumps(current_data))
                last_sent_data = current_data.copy()
            await asyncio.sleep(5)  # Intervalle de mise à jour 5 secondes
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Erreur WebSocket inattendue: {e}")
        manager.disconnect(websocket)
    finally:
        print(f"Connexion WebSocket terminée: {len(manager.active_connections)} connexions actives") 

# ============ ENDPOINTS POUR LIRE LES DONNÉES DE PRODUCTION DE LA BDD ============

# Endpoint pour récupérer toutes les données de production
@app.get("/production/all")
async def get_all_production():
    """Récupère toutes les données de production de la base de données"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, production, windSpeed, sunshine, 
                       airPressure, radiation, airTemperature, relativeHumidity
                FROM production
                ORDER BY timestamp DESC
            """) as cursor:
                rows = await cursor.fetchall()
                data = [dict(row) for row in rows]
                return {
                    "count": len(data),
                    "data": data
                }
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture de la base de données: {str(e)}"
        }

# Endpoint pour récupérer les données de production des N dernières heures
@app.get("/production/last-hours/{hours}")
async def get_production_last_hours(hours: int):
    """Récupère les données de production des N dernières heures"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, production, windSpeed, sunshine, 
                       airPressure, radiation, airTemperature, relativeHumidity
                FROM production
                WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp DESC
            """, (hours,)) as cursor:
                rows = await cursor.fetchall()
                data = [dict(row) for row in rows]
                return {
                    "count": len(data),
                    "period_hours": hours,
                    "data": data
                }
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture de la base de données: {str(e)}"
        }

# Endpoint pour récupérer les données de production d'une période
@app.get("/production/date-range")
async def get_production_by_date_range(start_date: str, end_date: str):
    """
    Récupère les données de production entre deux dates
    Format: YYYY-MM-DD HH:MM:SS ou YYYY-MM-DD
    """
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, production, windSpeed, sunshine, 
                       airPressure, radiation, airTemperature, relativeHumidity
                FROM production
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
            """, (start_date, end_date)) as cursor:
                rows = await cursor.fetchall()
                data = [dict(row) for row in rows]
                return {
                    "count": len(data),
                    "start_date": start_date,
                    "end_date": end_date,
                    "data": data
                }
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture de la base de données: {str(e)}"
        }

# Endpoint pour obtenir les statistiques de production
@app.get("/production/statistics")
async def get_production_statistics():
    """Récupère les statistiques de production (moyenne, min, max, total)"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            async with db.execute("""
                SELECT 
                    COUNT(*) as count,
                    AVG(production) as avg_production,
                    MIN(production) as min_production,
                    MAX(production) as max_production,
                    SUM(production) as total_production,
                    AVG(windSpeed) as avg_windSpeed,
                    AVG(airTemperature) as avg_airTemperature,
                    AVG(radiation) as avg_radiation
                FROM production
            """) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "count": row[0],
                        "average_production_w": round(row[1], 2) if row[1] else 0,
                        "min_production_w": round(row[2], 2) if row[2] else 0,
                        "max_production_w": round(row[3], 2) if row[3] else 0,
                        "total_production_wh": round(row[4], 2) if row[4] else 0,
                        "avg_windspeed": round(row[5], 2) if row[5] else 0,
                        "avg_air_temperature": round(row[6], 2) if row[6] else 0,
                        "avg_radiation": round(row[7], 2) if row[7] else 0
                    }
                else:
                    return {"error": "Aucune donnée disponible"}
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture de la base de données: {str(e)}"
        }

# Endpoint pour obtenir les statistiques de production du jour
@app.get("/production/today-statistics")
async def get_today_production_statistics():
    """Récupère les statistiques de production du jour"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            async with db.execute("""
                SELECT 
                    COUNT(*) as count,
                    AVG(production) as avg_production,
                    MIN(production) as min_production,
                    MAX(production) as max_production,
                    SUM(production) as total_production,
                    MIN(timestamp) as first_record,
                    MAX(timestamp) as last_record
                FROM production
                WHERE DATE(timestamp) = DATE('now')
            """) as cursor:
                row = await cursor.fetchone()
                if row and row[0] > 0:
                    return {
                        "date": datetime.now().date().isoformat(),
                        "count": row[0],
                        "average_production_w": round(row[1], 2) if row[1] else 0,
                        "min_production_w": round(row[2], 2) if row[2] else 0,
                        "max_production_w": round(row[3], 2) if row[3] else 0,
                        "total_production_wh": round(row[4], 2) if row[4] else 0,
                        "first_record": row[5],
                        "last_record": row[6]
                    }
                else:
                    return {
                        "date": datetime.now().date().isoformat(),
                        "message": "Aucune donnée de production pour aujourd'hui"
                    }
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture de la base de données: {str(e)}"
        }

# Endpoint pour récupérer les données de production par jour
@app.get("/production/daily-summary")
async def get_daily_summary(days: int = 30):
    """Récupère un résumé quotidien de la production pour les N derniers jours"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as count,
                    AVG(production) as avg_production,
                    MIN(production) as min_production,
                    MAX(production) as max_production,
                    SUM(production) as total_production
                FROM production
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """, (days,)) as cursor:
                rows = await cursor.fetchall()
                data = [dict(row) for row in rows]
                return {
                    "period_days": days,
                    "count_days": len(data),
                    "data": data
                }
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture de la base de données: {str(e)}"
        }

# fonction pour produire les features néccessaire au model de prédiction de la consommation
