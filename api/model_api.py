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
import random

from collections import deque
from datetime import datetime, timedelta
import aiosqlite
import requests
from datetime import datetime,date,timedelta

import math

from fastapi import Query


app =FastAPI()
base_path = Path(__file__).resolve().parent.parent

# lien api huggingFace
API_URL = "https://api.groq.com/openai/v1/chat/completions"
headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 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"
    }

# dossier de fichier statique a servir a  l'interface
app.mount("/static", StaticFiles(directory=f"{base_path}/static"), name="static")

# dossier contenant les différentes fichier html ou css a retourner
templates = Jinja2Templates(directory = base_path/"client/interface")

# Coordonnées de Lokossa (Bénin)
latitude = 6.633
longitude = 1.717

tarrif_kwh = 125 # tariff du kwh au benin 
taxe = 0.18 # TVA

# declaration de variable
maxProdValue = 250  # Valeur maximale de production trouvée
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
    weatherData =  getWeatherData()
    # print(weatherData)
    #weatherData = {'WindSpeed': [4.5, 5.5, 4.8, 4.9, 5.0, 4.4, 4.5, 5.7, 5.0, 6.3, 9.3, 5.8, 5.6, 6.3, 12.2, 7.3, 5.8, 6.1, 12.0, 10.0, 9.6, 7.9, 6.0, 7.4], 'Sunshine': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 57.46783333333334, 0.0, 0.0, 0.0, 0.0], 'AirPressure': [1013.7, 1013.1, 1012.6, 1012.0, 1011.5, 1011.4, 1011.5, 1012.3, 1012.8, 1013.4, 1013.6, 1013.7, 1013.2, 1012.2, 1011.2, 1010.1, 1009.4, 1008.6, 1009.1, 1009.1, 1010.1, 1010.9, 1011.9, 1012.0], 'Radiation': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 5.0, 119.0, 325.0, 539.0, 695.0, 826.0, 886.0, 856.0, 655.0, 592.0, 447.0, 234.0, 60.0, 0.0, 0.0, 0.0, 0.0], 'AirTemperature': [26.1, 26.2, 25.8, 25.6, 25.5, 25.2, 25.1, 25.4, 26.6, 28.2, 29.8, 30.8, 31.5, 32.0, 29.4, 29.5, 30.6, 30.9, 28.9, 27.6, 27.1, 26.8, 26.5, 26.4], 'RelativeAirHumidity': [93, 93, 95, 95, 95, 96, 96, 94, 90, 85, 76, 72, 71, 70, 81, 80, 73, 69, 79, 88, 90, 91, 92, 92], 'Hour': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'Month': [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5], 'weatherCode': [2, 1, 2, 3, 3, 3, 3, 0, 0, 0, 1, 0, 95, 95, 80, 80, 51, 51, 51, 51, 2, 1, 0, 1]}
except Exception as e: 
    print("error-----------------------------------------")

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

# endpoint pour récupérer les informations de la batterie
@app.get("/batterie/today")
async def getBattData():
    """Récupère toutes les données de la batterie depuis la BDD"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, battPercentage, battCapacity
                FROM batterie
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
# endpoint pour récuperer les donnée de la batterie du jours
async def get_today_batt_data():
    """Récupère les données de la batterie du jours"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, battPercentage, battCapacity
                FROM batterie
                WHERE timestamp >= date('now')
                ORDER BY timestamp DESC
            """, ) as cursor:
                rows = await cursor.fetchall()
                data = [dict(row) for row in rows]
                return {
                    "count": len(data),
                    "date": date.today().isoformat(),
                    "data": data
                }
    except Exception as e:
        return {e}

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
            "prediction_kw": max(0,round(pred_float / 1000, 2)),
            "prediction_wh": max(0,round(pred_float, 2))
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
 
# ENDPOINT 
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

# ============ ENDPOINTS POUR LIRE LES DONNÉES DE PRODUCTION DE LA BDD ============

# Endpoint pour récupérer toutes les données de production
@app.get("/production/all")
async def get_all_production():
    """Récupère toutes les données de production de la base de données"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, productionReel,productionPred, windSpeed, sunshine, 
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

# Endpoint pour récupérer les données de production du jours 
@app.get("/production/today/")
async def get_production_today():
    """Récupère les données de production du jours"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, productionReel,productionPred, windSpeed, sunshine, 
                       airPressure, radiation, airTemperature, relativeHumidity
                FROM production
                WHERE timestamp >= date('now')
                ORDER BY timestamp DESC
            """, ) as cursor:
                rows = await cursor.fetchall()
                data = [dict(row) for row in rows]
                return {
                    "count": len(data),
                    "date": date.today().isoformat(),
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
                SELECT id, timestamp, productionReel,productionPred, windSpeed, sunshine, 
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
                SELECT id, timestamp, productionReel,productionPred, windSpeed, sunshine, 
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

# Endpoint pour récupérer les données de consommation du jours
@app.get("/consommation/today")
async def get_today_consumption():
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, consommationReel, consommationPred 
                FROM consommation
                WHERE timestamp >= date('now')
                ORDER BY timestamp DESC
            """, ) as cursor:
                rows = await cursor.fetchall()
                data = [dict(row) for row in rows]
                return {
                    "count": len(data),
                    "date": date.today().isoformat(),
                    "data": data
                }
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture de la base de données: {str(e)}"
        }



# stocker les prédictions pour aujourd'hui
# ============ ENDPOINTS POUR CALCULER LES ÉCONOMIES ============



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

# prédictions de la production pour la journée d'aujourd'hui
def getPred(weatherData):
    cle = ["WindSpeed","Sunshine","AirPressure","Radiation","AirTemperature","RelativeAirHumidity","Hour","Month"]
    weather_dict = {k:weatherData[k] for k in cle if k in weatherData}
    # Créer une instance du modèle Pydantic
    prod_data_instance = prod_data(**weather_dict)
    predProd = getPredProd(prod_data_instance)
    return predProd

# donnée graphique initiale
graphic_data = {
    "prod" : [i-i for i in range(datetime.now().hour)],# remplissage avec 0
    "conso" : [i-i for i in range(datetime.now().hour)],
    "batt" : [i-i for i in range(datetime.now().hour)]
}
async def getTodayGraphicData():
    """
        ajouter les données de la BDD aux tableau de donnée
    """
    prod_data = await get_production_today()
    conso_data = await get_today_consumption()
    batt_data = await get_today_batt_data()
    if prod_data["count"] >0:
        for i in range(prod_data["count"]-1):
            dt = datetime.strptime(prod_data["data"][i].get("timestamp"),"%Y-%m-%d %H:%M:%S")
            hour = int(dt.strftime('%H'))
            graphic_data["prod"][hour] = prod_data["data"][i]["productionReel"]
    if conso_data["count"]>0: 
        for i in range(conso_data["count"]-1):
            dt = datetime.strptime(prod_data["data"][0].get("timestamp"),"%Y-%m-%d %H:%M:%S")
            hour = int(dt.strftime('%H'))
            graphic_data["conso"][hour] = conso_data["data"][i]["consommationReel"]
    if batt_data["count"]>0:
        for i in range(batt_data["count"]-1):
            dt = datetime.strptime(prod_data["data"][0].get("timestamp"),"%Y-%m-%d %H:%M:%S")
            hour = int(dt.strftime('%H'))
            graphic_data["batt"][hour] = batt_data["data"][i]["battPercentage"]
    return graphic_data

# mise a jours imédiate des donnée du graphe
asyncio.create_task(getTodayGraphicData())

# variable pour stocker les prédictions
# stockages des features(est_weekend,est_jour_ferie,sc,sp) pour la prediction de la consommation
cf = analyser_lokossa()
conso_features = {
    "est_weekend" : cf[0],
    "est_jour_ferie" : cf[1],
    "saison_chaudes": cf[2],
    "saison_pluies" : cf[3]
}
prediction_consommation = getConso(cf)
prediction_production = getPred(weatherData)
# initialisation de la BDD
async def init_db():
    print("database initiated")
    async with aiosqlite.connect("energy.db") as db:
        # table consommation
        await db.execute("""
            CREATE TABLE IF NOT EXISTS consommation(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                consommationReel REAL,
                consommationPred REAL,
                consoFeatures TEXT
            )
        """)
        # await db.execute("""
        #     ALTER TABLE consommation ADD COLUMN consoFeatures TEXT DEFAULT 0 
        # """)
        # table batterie
        await db.execute("""
            CREATE TABLE IF NOT EXISTS batterie(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                battPercentage REAL,
                battCapacity REAL
            )
        """)
        # table gain
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gain(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                gain REAL, 
                tva REAL,
                kwh REAL
            )
        """)
        # table archive journalière
        await db.execute("""
            CREATE TABLE IF NOT EXISTS archive(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                production REAL, 
                consommation REAL,
                gain REAL,
                status TEXT
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON batterie(timestamp)")
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
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON gain(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON archive(timestamp)")
        await db.commit()

start_time = datetime.now()
# fonction pour choisir un status
def statusProvider(prod,conso):
    """retourne un status(optimale,déficitaire,equilibré) en fonction de prod, et conso

    Args:
        prod (_float_): _description_
        conso (_float_): _description_

    Returns:
        _string_: _description_
    """
    if prod>conso : return "optimale"
    elif prod<conso : return "déficitaire"
    elif prod == conso :return "equilibré"
    else: return "inconnu"
# fonction a executer tout les 24h
async def cycle24h():
    while True:
        print(f"initiation du de 24h cycle a {datetime.now().hour}:{datetime.now().minute}")
        await asyncio.sleep(86400)  # attend 24 heures
        # sauvegarde de l'archive dans la base de donées
        production = prod_cumul_24h.energie_wh()
        consommation = conso_cumul_24h.energie_wh()
        gain = conso_ER_24h.energie_kwh* tarrif_kwh*taxe
        status = statusProvider(production,consommation)
        async with aiosqlite.connect("energy.db") as db:
            try:
                await db.execute(
                    """INSERT INTO archive(production, consommation, gain, status) VALUES (?, ?, ?, ?)""",
                    (production,consommation,gain,status)
                )
                await db.commit()
                print("---donnée de 24h inséré dans la BDD---")
            except Exception as e:
                print(e)
        
# fonction a executer toute les heures
async def cycle1h():
    """Cycle de 1 heure pour enregistrer les données dans la BDD et actualiser les données"""
    global maxProdValue
    try:
        while True:
            print(f"initiation du cycle a {datetime.now().hour}:{datetime.now().minute}")
            await asyncio.sleep(3600)  # attend 1 heure
            # Action à faire toutes les heures
            # Récupérer l'heure actuelle pour obtenir l'indice dans les listes
            try:
                applyStrategy()
                # mise a jours des donnée prod et conso
                hourly_data["consommation_h"],hourly_data["production_h"] = conso_cumul.energie_wh(),prod_cumul.energie_wh()
                # mise a jours des données graphique 
                graphic_data["prod"].append(hourly_data["production_h"])
                graphic_data["conso"].append(hourly_data["consommation_h"])
                current_hour = datetime.now().hour
                # Récupérer la prédiction de consommation de façon sécurisée
                try:
                    predConso = predictionData["predConso"][current_hour].get('prediction de consommation', 0)
                except (KeyError, IndexError, TypeError) as e:
                    print(e)
                    predConso = 0
                
                async with aiosqlite.connect("energy.db") as db:
                    await db.execute("INSERT INTO consommation (consommationReel,consommationPred,consoFeatures) VALUES (?,?,?)", (conso_cumul.energie_wh(),predConso,json.dumps(conso_features)))
                    if not("Erreur API " in str(weatherData)):
                        try:
                            # Extraire les valeurs scalaires correspondant à l'heure actuelle
                            wind_speed = weatherData["WindSpeed"][current_hour] if isinstance(weatherData["WindSpeed"], list) else weatherData["WindSpeed"]
                            sunshine = weatherData["Sunshine"][current_hour] if isinstance(weatherData["Sunshine"], list) else weatherData["Sunshine"]
                            air_pressure = weatherData["AirPressure"][current_hour] if isinstance(weatherData["AirPressure"], list) else weatherData["AirPressure"]
                            radiation = weatherData["Radiation"][current_hour] if isinstance(weatherData["Radiation"], list) else weatherData["Radiation"]
                            air_temperature = weatherData["AirTemperature"][current_hour] if isinstance(weatherData["AirTemperature"], list) else weatherData["AirTemperature"]
                            relative_humidity = weatherData["RelativeAirHumidity"][current_hour] if isinstance(weatherData["RelativeAirHumidity"], list) else weatherData["RelativeAirHumidity"]
                            # Récupérer la prédiction de production de façon sécurisée
                            try:
                                predProd = predictionData["predProd"]["hourly_predictions"][current_hour].get("prediction_kw", 0)
                            except (KeyError, IndexError, TypeError):
                                predProd = 0
                            
                            await db.execute(
                                """INSERT INTO production 
                                (productionReel, productionPred ,windSpeed, sunshine, airPressure, radiation, airTemperature, relativeHumidity)
                                VALUES (?,?,?, ?, ?, ?, ?, ?)""",
                                (prod_cumul.energie_wh(),predProd,wind_speed, sunshine, air_pressure, radiation, air_temperature, relative_humidity)
                            )
                            await db.execute(
                                """INSERT INTO batterie 
                                (battPercentage, battCapacity)
                                VALUES (?, ?)""",
                                (sensor_data["battPercentage"],sensor_data["battCapacity"])
                            )
                            # insertion du gain par heure ou epargne dans la BDD
                            await db.execute(
                                """INSERT INTO gain
                                (gain, tva,kwh)
                                VALUES (?, ?, ?)""",
                                (epargne,taxe,tarrif_kwh)
                            )
                            await db.commit()
                            print("donnée inséré dans la BDD")
                        except IndexError as e:
                            print(f"Erreur: indice heure hors limites - {e}")
                        except Exception as e:
                            print(f"Erreur lors de l'insertion de la production: {e}")
                # calculer le pic de production avec les données de la BDD
                maxProdValue = await maxProd(maxProdValue)
                print(f"Une heure s'est écoulée depuis {start_time}")
            except Exception as e:
                print(f"Erreur dans cycle1h: {type(e).__name__}: {e}")
                # La boucle continue malgré l'erreur
    except asyncio.CancelledError:
        print("Tâche cycle1h annulée")

# fonction pour simuler la consommation de la maisons en conformité avec notre datasets
def break_hourly_average(hourly_avg_watts, n_points=60, variation=0.1):
    """
    Break an hourly average power into n_points instantaneous values.
    
    Parameters:
        hourly_avg_watts : float, average power for the hour (W)
        n_points          : int, number of points to generate (e.g., 60 for per-minute)
        variation         : float, relative random variation (0.1 = ±10%)
    
    Returns:
        list of instantaneous power values (W) with the same average ± noise
    """
    # Generate n_points values with average = hourly_avg_watts
    points = []
    for _ in range(n_points):
        # Random factor around 1 with uniform or normal distribution
        factor = 1 + random.uniform(-variation, variation)
        value = hourly_avg_watts * factor
        points.append(max(0, value))   # no negative power
    
    # Optionally re‑scale to exactly match the given average (remove bias)
    actual_avg = sum(points) / n_points
    if actual_avg > 0:
        scale = hourly_avg_watts / actual_avg
        points = [p * scale for p in points]
    
    return points

# fonction pour génerer les donnée de production et de consommation de la maison, en prod ces données doivent provenir de la lecture des capteurs donc il faudrait mettre en place des fonctions pour lire les données des capteurs
def generate_data():
        """Génère des données avec tendances réalistes"""
        now = datetime.now()
        hour = now.hour
        sunshine = weatherData["Sunshine"][hour]
        # Production solaire avec courbe lisse
        production= break_hourly_average(prediction_production["hourly_predictions"][hour]['prediction_wh'],3600)[now.minute]
        # Consommation avec bruit
        consommation = break_hourly_average(prediction_consommation[hour]["prediction de consommation"])[now.minute]
        return max(0, production), max(0, consommation)
# mettre a jours les données de capteurs toutes les 5 secondes 
async def updateSensorData():
    """Mettre à jour les données des capteurs en continu"""
    try:
        while True:
            await asyncio.sleep(5)
            sensor_data["production"],sensor_data["consommation"] = generate_data() 
            sensor_data["battPercentage"] = 50
            sensor_data["sbee"] = True
            # mise a jour des données stratégiques
            predictionData["battPercentage"] = sensor_data["battPercentage"]
            predictionData["sbee"] = sensor_data["sbee"]
            # mettre a jours le time stamp
            sensor_data["timestamp"] = asyncio.get_event_loop().time()
            # vérification de la sbee et lancement d'une nouvelle stratégie
            if not sensor_data["sbee"]:
                print("changement de stratégie--------------------------------------- ")
                hourlyStrategy(predictionData)
            # Log des données mises à jour
    except asyncio.CancelledError:
        print("Tâche updateSensorData annulée")

# fonction pour calculer le pic de production par jours
async def maxProd(prevMaxProdValue):
    allProd = await get_all_production()
    if not "error" in allProd :
        for i in range(allProd["count"]) :
            prevMaxProdValue = allProd["data"][i]["productionReel"] if allProd["data"][i]["productionReel"]> prevMaxProdValue else prevMaxProdValue
            return prevMaxProdValue
    else:
        return 0  # Retourner 0
    
# Variables globales pour stocker les tâches en arrière-plan
background_tasks = []

# Event Startup - 
@app.on_event("startup")
async def startup_event():
    global maxProdValue, background_tasks
    # Créer et stocker les tâches
    background_tasks = [
        asyncio.create_task(cycle1h()),
        asyncio.create_task(cycle24h()),
        asyncio.create_task(updateSensorData())
    ]
    await init_db()
    await init_cumuls()  # Initialiser les cumuls avec les données de la BDD
    maxProdValue = await maxProd(0)

# Event Shutdown - Arrêter proprement les tâches en arrière-plan
@app.on_event("shutdown")
async def shutdown_event():
    """Annuler les tâches en arrière-plan lors de l'arrêt du serveur"""
    global background_tasks
    print("Arrêt du serveur - annulation des tâches en arrière-plan")
    for task in background_tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    background_tasks.clear()

#donnée instantannée en prod ces donnée doivent provenir de la lecture des capteur du RBP
sensor_data = {
    "production": 0,
    "consommation": 0,
    "battPercentage" : 0,
    "battCapacity": 3000,
    "activeSource" :"solarPannel",
    "timestamp": None,
    "sbee" : True, # en prod, cette data doit provenir de la lecture de capteur, 
}
# donnée horaire, sont mise a jours toute les heures dans ccycle1h
hourly_data={
    "production_h" : 0,
    "consommation_h" : 0,
}


# Cache des dernières données envoyées pour éviter les doublons
last_sent_data = None

# Classe MQTT pour récupérer les données

# classe pour stocker la production instantanée afin d'obtenir la production et la consommation horaire
class EnergyCumul:
    def __init__(self, duree_heures=1):
        self.duree = timedelta(hours=duree_heures)
        self.echantillons = deque()  # (timestamp, puissance_watts)
    # récuperer puis ajouter la production stockée dans la BDD du jous
    async def sync_prod_data_from_data_base(self):
        # recuper les infos depuis la BDD
        prod = await get_production_today()
        if prod["count"] ==0 :
            return 
        else :
            for i in range(prod['count']):
                str_date = datetime.strptime(prod["data"][i]["timestamp"], "%Y-%m-%d %H:%M:%S")
                self.echantillons.append((str_date,prod["data"][i]["productionReel"])) 
    # recuperer les données de consommation stocké dans la BDD
    async def sync_conso_data_from_data_base(self):
        # recuper les infos depuis la BDD
        conso = await get_today_consumption()
        if conso["count"] ==0 :
            return 
        else :
            for i in range(conso['count']):
                str_date = datetime.strptime(conso["data"][i]["timestamp"], "%Y-%m-%d %H:%M:%S")
                self.echantillons.append((str_date,conso["data"][i]["consommationReel"]))
    
    def ajouter(self, puissance_w, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now()
        self.echantillons.append((timestamp, puissance_w))
        self._nettoyer()

    def _nettoyer(self):
        limite = datetime.now() - self.duree
        while self.echantillons and self.echantillons[0][0] < limite:
            self.echantillons.popleft()
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
conso_ER = EnergyCumul() # cumule de la consommation sur les energies renouvelables pour calculer l'epargne
conso_ER_24h = EnergyCumul(duree_heures=24)# cumule de la consommation sur les energies renouvelables pour calculer l'epargne sur une journée

async def init_cumuls():
    """Initialiser les cumuls avec les données de la base de données"""
    await prod_cumul_24h.sync_prod_data_from_data_base() # ajout des données précédent depuis la base de donnée
    await conso_cumul_24h.sync_conso_data_from_data_base() # ajout des données précédent depuis la base de donnée

# Instancier et démarrer l'écoute du client MQTT global

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
@app.get("/optimisation")
async def formular(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="optimisation.html",
    )
@app.get("/meteo")   
async def formular(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="meteo.html",
    )    

@app.get("/settings")
async def settings_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
    )

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
# Endpoint pour récupérer les gains du jour
@app.get("/gain/today")
async def get_today_gain():
    """Récupère les données de gain du jour"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, gain, tva, kwh
                FROM gain
                WHERE timestamp >= date('now')
                ORDER BY timestamp DESC
            """) as cursor:
                rows = await cursor.fetchall()
                data = [dict(row) for row in rows]
                return {
                    "count": len(data),
                    "date": date.today().isoformat(),
                    "data": data
                }
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture de la base de données: {str(e)}"
        }

# Endpoint pour récupérer les archives du jour
@app.get("/archive/today")
async def get_today_archive():
    """Récupère les données d'archive du jour"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, production, consommation, gain, status
                FROM archive
                WHERE timestamp >= date('now')
                ORDER BY timestamp DESC
            """) as cursor:
                rows = await cursor.fetchall()
                data = [dict(row) for row in rows]
                return {
                    "count": len(data),
                    "date": date.today().isoformat(),
                    "data": data
                }
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture de la base de données: {str(e)}"
        }
        
# recuperer toute les données archivée
@app.get("/archive/all")
async def get_today_archive():
    """Récupère les données d'archive du jour"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, timestamp, production, consommation, gain, status
                FROM archive
                ORDER BY timestamp DESC
            """) as cursor:
                rows = await cursor.fetchall()
                data = [dict(row) for row in rows]
                return {
                    "count": len(data),
                    "date": date.today().isoformat(),
                    "data": data
                }
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture de la base de données: {str(e)}"
        }

# endpoint pour récuperer les données d'archive 
@app.get("/archive/grouped")
async def get_archive_all_grouped():
    """
    Retourne les données de la table archive regroupées par jour, par mois et par année.
    """
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            result = {}

            # 1. Regroupement par jour
            async with db.execute("""
                SELECT 
                    DATE(timestamp) AS periode,
                    SUM(production) AS total_production,
                    SUM(consommation) AS total_consommation,
                    SUM(gain) AS total_gain,
                    AVG(gain) AS avg_gain,
                    COUNT(*) AS count
                FROM archive
                GROUP BY periode
                ORDER BY periode DESC
            """) as cursor:
                rows = await cursor.fetchall()
                result["daily"] = [dict(row) for row in rows]

            # 2. Regroupement par mois
            async with db.execute("""
                SELECT 
                    strftime('%Y-%m', timestamp) AS periode,
                    SUM(production) AS total_production,
                    SUM(consommation) AS total_consommation,
                    SUM(gain) AS total_gain,
                    AVG(gain) AS avg_gain,
                    COUNT(*) AS count
                FROM archive
                GROUP BY periode
                ORDER BY periode DESC
            """) as cursor:
                rows = await cursor.fetchall()
                result["monthly"] = [dict(row) for row in rows]

            # 3. Regroupement par année
            async with db.execute("""
                SELECT 
                    strftime('%Y', timestamp) AS periode,
                    SUM(production) AS total_production,
                    SUM(consommation) AS total_consommation,
                    SUM(gain) AS total_gain,
                    AVG(gain) AS avg_gain,
                    COUNT(*) AS count
                FROM archive
                GROUP BY periode
                ORDER BY periode DESC
            """) as cursor:
                rows = await cursor.fetchall()
                result["yearly"] = [dict(row) for row in rows]

            # Arrondir les valeurs numériques
            for group in ["daily", "monthly", "yearly"]:
                for item in result[group]:
                    for key in ["total_production", "total_consommation", "total_gain", "avg_gain"]:
                        if item.get(key) is not None:
                            item[key] = round(item[key], 2)

            return result

    except Exception as e:
        return {"error": f"Erreur lors du regroupement des archives : {str(e)}"}

# analyse de la journée et extraction des donnée de prédiciton de la consommation
predictionData = {
        "battPercentage" : sensor_data["battPercentage"],
        "sbee" : sensor_data["sbee"],
        "predProd" : prediction_production ,#getPred(weatherData), 
        "predConso" : prediction_consommation,#getConso(analyser_lokossa()),
    }
# fonction de décision!
def logique(conso, prod,battPercentage,battTotalCapacity,seuil,sbee,index):
    # production supérieure a la consommmation
    if prod> conso:
        # vérifier si il faut charger les batterie
        if battPercentage >= 70 :
            return {
                "index" : index,
                "param" : {"conso":conso,"prod":prod,"battPercentage":battPercentage,"battTotalCapacity":battTotalCapacity,"seuil":seuil,"seuil":seuil},
                "sourceActive"  : ["solarPannel"],
                "chargerBatt" : False,
                "mode":"normal"
            }
        elif battPercentage < 70 : 
            # peut ton charger la batt pendant qu'on alimente l'installation ?
            puissanceRestante = prod - conso
            if puissanceRestante >= seuil : 
                return {
                    "index" : index,
                    "param" : {"conso":conso,"prod":prod,"battPercentage":battPercentage,"battTotalCapacity":battTotalCapacity,"seuil":seuil,"seuil":seuil},
                    "sourceActive" : ["solarPannel"],
                    "chargerBatt" : True,
                    "mode":"normal"
                }
            # si on ne peut pas charger la batterie tout en alimentant la maison alors il faut verifier si on peut reporter la charge de la batterie a plus tard
            else :
                return{
                    "index" : index,
                    "param" : {"conso":conso,"prod":prod,"battPercentage":battPercentage,"battTotalCapacity":battTotalCapacity,"seuil":seuil,"seuil":seuil},
                    "sourceActive" : ["sbee"],
                    "chargerBatt" : True,
                    "mode":"saving"
                }
    # production inférieure a la consommation : 
    elif prod< conso : 
        # vérifier si la battérie peut fournir l'énergie néccessaire pour les 1h tout en restant >=20%?
        battEnergy = (battPercentage * battTotalCapacity)/100 if battPercentage>20 else 0
        if battEnergy >= conso :  
            # on peut basculer sur la batterie mais pourrons nous la recharger plustard?
            return {
                "index" : index,
                "param" : {"conso":conso,"prod":prod,"battPercentage":battPercentage,"battTotalCapacity":battTotalCapacity,"seuil":seuil,"seuil":seuil},
                "sourceActive" : ["batt"],
                "chargerBatt" : False,
                "mode":"normal"
            }
        elif battEnergy+prod >= conso:
            # combinaison des deux sources
            return{
                "index" : index,
                "param" : {"conso":conso,"prod":prod,"battPercentage":battPercentage,"battTotalCapacity":battTotalCapacity,"seuil":seuil,"seuil":seuil},
                "sourceActive": ["batt","solarPannel"],
                "chargerBatt" : False,
                "mode":"normal"
            }
        elif battEnergy+prod < conso:
            # aucune des sources renouvelables n'est suffisant :
            if sbee: 
                return{
                    "index" : index,
                    "param" : {"conso":conso,"prod":prod,"battPercentage":battPercentage,"battTotalCapacity":battTotalCapacity,"seuil":seuil,"seuil":seuil},
                    "sourceActive" : ["sbee"],
                    "chargerBatt" : True if prod>=seuil else False,
                    "mode" : "saving"
                }
            else :
                # sbee abscent donc il faut retourner sur le combo PS+Batt et activer le mode ultra  économie
                return{
                    "index" : index,
                    "param" : {"conso":conso,"prod":prod,"battPercentage":battPercentage,"battTotalCapacity":battTotalCapacity,"seuil":seuil,"seuil":seuil},
                    "sourceActive": ["batt","solarPannel"],
                    "chargerBatt" : False,
                    "mode" : "ultraSaving"
                } 
    elif prod == conso:
    # production est égale a la consommation
        if battPercentage>=70 : 
            return{
                    "index" : index,
                    "param" : {"conso":conso,"prod":prod,"battPercentage":battPercentage,"battTotalCapacity":battTotalCapacity,"seuil":seuil,"seuil":seuil},
                    "sourceActive": ["solarPannel"],
                    "chargerBatt" : False,
                    "mode" : "normal"
                }
        else :
            return{
                    "index" : index,
                    "param" : {"conso":conso,"prod":prod,"battPercentage":battPercentage,"battTotalCapacity":battTotalCapacity,"seuil":seuil,"seuil":seuil},
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
        lo = logique(hourly_conso[i]['prediction de consommation'],hourly_prod[i]['prediction_wh'],predictionData["battPercentage"],3000,1000,predictionData["sbee"],i)
        strategy.append(lo)
    return strategy

# variable contenant la stratégie a adopter par le système pour une journée:
strategie = hourlyStrategy(predictionData) # a envoyer pour interpretation

# fonction pour activer le mode de fonctionnement
def activateMode(mode):
    if mode == "normal":
        return "Mode normal Activé. Tout les appareils sont autorisé a fonctionner"
    elif mode == "saving":
        return "Mode Economie Activé, desormains les appareils de forte consommation sont désactiver pour économiser l'énergie"
    elif mode == "ultraSaving":
        return "mode ultra économie activé, seul les appareils de premières néccésité sont activé"
# fonction pour activer la ou les sources pour alimenter la maison
def activateSource(asrc):
    # desactiver toute les sources puis activer ceux qui sont autorisée
    print(" # relais sp eteint")
    print('# relais batt eteint')
    print("# relais sbee eteint")
    # activation des sources
    for i in asrc:
        if i == "solarPannel" :
            print("# acivation des relais du panneau solaire")
        elif i == "batt":
            print("# activation du relais de la batterie")
        elif i == "sbee" :
            print("# activation du relais de la sbee")

# fonction pour application de la strategie:
def applyStrategy():
    nowStrategy = strategie[datetime.now().hour]
    print(nowStrategy)
    if nowStrategy["chargerBatt"]:
        # activer le chargement des batterie
        print("chargement des battéries: Autoriser le relais connecté a la batterie ")
    activateMode(nowStrategy["mode"])
    activateSource(nowStrategy["sourceActive"])

# application immediate de la stratégie actuelle
applyStrategy()
# fonction pour calculer le gain 
def saving(puissance):
    conso_ER.ajouter(puissance)
    global epargne 
    epargne = conso_ER.energie_kwh * tarrif_kwh * taxe
# fonction pour synchroniser l'application de la stratégie a l'heure exacte correspondante
async def awaitExactHour():
    now = datetime.now()
    minutesActuelle = now.minute
    minutesRestante = 60-minutesActuelle
    # declancher si le retard est supérieur a 10 minutes
    if minutesActuelle>10 :
        await asyncio.sleep(minutesRestante)
        applyStrategy()
# explication de la stratégie par l'ia deepseek
def getExplanation(strategie):
    # system prompt
    explication = """
        Un script python prend 7 paramètres : 
        - `conso` : puissance consommée par l'installation  
        - `prod` : puissance produite par les panneaux solaires  
        - `battPercentage` : pourcentage de charge de la batterie  
        - `battTotalCapacity` : capacité totale de la batterie (en kWh ou autre unité)  
        - `seuil` : seuil de puissance minimum pour autoriser la charge de la batterie  
        - `sbee` : booléen indiquant si une source de secours (ex : réseau) est disponible  
        - `index` : identifiant (simplement recopié dans la sortie)

        Il retourne toujours un objet JSON contenant :  
        - `index` : l'index reçu  
        - `sourceActive` : liste des sources utilisées (`"solarPannel"`, `"batt"`, `"sbee"`)  
        - `chargerBatt` : booléen – `true` si on doit charger la batterie, `false` sinon  
        - `mode` : `"normal"`, `"saving"` ou `"ultraSaving"`

        Détail des cas :

        1. Production > consommation (`prod > conso`)  
        - Si batterie ≥ 70 % → pas de charge.  
            → `sourceActive = ["solarPannel"]`, `chargerBatt = false`, `mode = "normal"`  
        - Sinon (batterie < 70 %) : puissance restante = `prod - conso`.  
            - Si `puissanceRestante ≥ seuil` → charge possible.  
            → `sourceActive = ["solarPannel"]`, `chargerBatt = true`, `mode = "normal"`  
            - Sinon → on utilise `sbee` pour charger plus tard.  
            → `sourceActive = ["sbee"]`, `chargerBatt = true`, `mode = "saving"`

        2. Production < consommation (`prod < conso`)  
        `battEnergy = (battPercentage * battTotalCapacity)/100` si `battPercentage > 20` sinon 0.  
        - Si `battEnergy ≥ conso` → batterie seule.  
            → `sourceActive = ["batt"]`, `chargerBatt = false`, `mode = "normal"`  
        - Sinon, si `battEnergy + prod ≥ conso` → batterie + solaire.  
            → `sourceActive = ["batt","solarPannel"]`, `chargerBatt = false`, `mode = "normal"`  
        - Sinon (insuffisant) :  
            - Si `sbee` est `true` → secours. Charge batterie si `prod ≥ seuil`.  
            → `sourceActive = ["sbee"]`, `chargerBatt = (prod >= seuil)`, `mode = "saving"`  
            - Si `sbee` est `false` → batterie + solaire en ultra‑économie.  
            → `sourceActive = ["batt","solarPannel"]`, `chargerBatt = false`, `mode = "ultraSaving"`

        3. Production = consommation (`prod == conso`)  
        - Si batterie ≥ 70 % → solaire seul.  
            → `sourceActive = ["solarPannel"]`, `chargerBatt = false`, `mode = "normal"`  
        - Sinon (batterie < 70 %) :  
            - Si `sbee` → secours pour charger.  
            → `sourceActive = ["sbee"]`, `chargerBatt = true`, `mode = "normal"`  
            - Si pas `sbee` → solaire seul sans charge, ultra‑économie.  
            → `sourceActive = ["solarPannel"]`, `chargerBatt = false`, `mode = "ultraSaving"`
        """
    output = strategie
    exemple = """Tu dois produire dans une liste des json suivant cet exemple: { "index":"l'index que tu recoit","sourceActive": "je prévoit une production de 180 et une consommation de 20, la production etant supérieur a la consommation, je bascule alors l'installation sur les panneaux solaire pour économiser...","chargerBatt": "Le pourcentage des batterie est de 20% pour éviter une décharge profonde j'utilise le surplus de production pour recharger les recharger","mode": "si le mode est normal: en autosuffisance solaire alors tout les appareils sont autorisé a consommé l'énergie disponible. ou si le mode est saving: economie d'energie, les appareils a forte consommation sont desactiver pour augmenter l'autonomie. et si c'est ultrasaving: energie disponible très faible, seul les appareils neccessaires sont activée"}
    """
    payload ={
        "messages": [
            {
                "role": "user",
                "content": f"{explication} ton role est d'expliquer chaciune de ces sorties {output} avec leurs paramètres en te basant sur cet exemple {exemple} tu es libre de reformuler, aucun commentaire ni explication avant et apres le json n'est néccessaire en dehors de l'interpretation, comporte toi comme une api qui retourne une liste  json valide et incrémentable"
            }
        ],
        "model": "llama-3.3-70b-versatile"
    }
    try:
        request = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        request.raise_for_status()  # Vérifier le status code HTTP
        
        response = request.json()
        content = response["choices"][0]["message"].get('content')
        print(json.loads(content))
        return json.loads(content)
    except requests.exceptions.HTTPError as e:
        print(f"Erreur HTTP {request.status_code}: {request.text}")
        return f"Erreur API: {request.status_code}"
    except requests.exceptions.JSONDecodeError as e:
        print(f"Erreur JSON parsing: {request.text}")
        return f"Erreur: réponse invalide de l'API"
    except requests.exceptions.Timeout:
        print("Timeout: l'API n'a pas répondu à temps")
        return "Erreur: timeout API"
    except Exception as e:
        print(f"Erreur inattendue: {str(e)}")
        return f"Erreur: {str(e)}"
groq_interpretation = getExplanation(strategie) # interpretation des différentes décisions
#groq_interpretation = [{'index': 0, 'sourceActive': "Je prévois une production de 0 et une consommation de 1696,62, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 1, 'sourceActive': "Je prévois une production de 0 et une consommation de 1675,09, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 2, 'sourceActive': "Je prévois une production de 0 et une consommation de 1680,93, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 3, 'sourceActive': "Je prévois une production de 0 et une consommation de 1707,54, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 4, 'sourceActive': "Je prévois une production de 0 et une consommation de 198,64, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 5, 'sourceActive': "Je prévois une production de 0 et une consommation de 236,71, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 6, 'sourceActive': "Je prévois une production de 0 et une consommation de 189,15, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 7, 'sourceActive': "Je prévois une production de 0 et une consommation de 274,81, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 8, 'sourceActive': "Je prévois une production de 0 et une consommation de 152,34, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 9, 'sourceActive': "Je prévois une production de 801,84 et une consommation de 1065,15, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour alimenter l'installation et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 10, 'sourceActive': "Je prévois une production de 1580,1 et une consommation de 1167,32, la production étant supérieure à la consommation, j'utilise les panneaux solaires pour alimenter l'installation et je charge la batterie.", 'chargerBatt': "Puisque la production est supérieure à la consommation, je peux charger la batterie pour préserver l'énergie.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 11, 'sourceActive': "Je prévois une production de 4539,99 et une consommation de 203,74, la production étant supérieure à la consommation, j'utilise les panneaux solaires pour alimenter l'installation et je charge la batterie.", 'chargerBatt': "Puisque la production est supérieure à la consommation, je peux charger la batterie pour préserver l'énergie.", 'mode': "Le mode est normal, l'installation est en autosuffisance solaire."}, {'index': 12, 'sourceActive': "Je prévois une production de 5192,19 et une consommation de 374,1, la production étant supérieure à la consommation, j'utilise les panneaux solaires pour alimenter l'installation et je charge la batterie.", 'chargerBatt': "Puisque la production est supérieure à la consommation, je peux charger la batterie pour préserver l'énergie.", 'mode': "Le mode est normal, l'installation est en autosuffisance solaire."}, {'index': 13, 'sourceActive': "Je prévois une production de 5482,6 et une consommation de 1751,56, la production étant supérieure à la consommation, j'utilise les panneaux solaires pour alimenter l'installation et je charge la batterie.", 'chargerBatt': "Puisque la production est supérieure à la consommation, je peux charger la batterie pour préserver l'énergie.", 'mode': "Le mode est normal, l'installation est en autosuffisance solaire."}, {'index': 14, 'sourceActive': "Je prévois une production de 4163,06 et une consommation de 1754,88, la production étant supérieure à la consommation, j'utilise les panneaux solaires pour alimenter l'installation et je charge la batterie.", 'chargerBatt': "Puisque la production est supérieure à la consommation, je peux charger la batterie pour préserver l'énergie.", 'mode': "Le mode est normal, l'installation est en autosuffisance solaire."}, {'index': 15, 'sourceActive': "Je prévois une production de 4421,34 et une consommation de 1718,76, la production étant supérieure à la consommation, j'utilise les panneaux solaires pour alimenter l'installation et je charge la batterie.", 'chargerBatt': "Puisque la production est supérieure à la consommation, je peux charger la batterie pour préserver l'énergie.", 'mode': "Le mode est normal, l'installation est en autosuffisance solaire."}, {'index': 16, 'sourceActive': "Je prévois une production de 4657,97 et une consommation de 252,8, la production étant supérieure à la consommation, j'utilise les panneaux solaires pour alimenter l'installation et je charge la batterie.", 'chargerBatt': "Puisque la production est supérieure à la consommation, je peux charger la batterie pour préserver l'énergie.", 'mode': "Le mode est normal, l'installation est en autosuffisance solaire."}, {'index': 17, 'sourceActive': "Je prévois une production de 4604,77 et une consommation de 876,57, la production étant supérieure à la consommation, j'utilise les panneaux solaires pour alimenter l'installation et je charge la batterie.", 'chargerBatt': "Puisque la production est supérieure à la consommation, je peux charger la batterie pour préserver l'énergie.", 'mode': "Le mode est normal, l'installation est en autosuffisance solaire."}, {'index': 18, 'sourceActive': "Je prévois une production de 661,85 et une consommation de 752,61, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour alimenter l'installation et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 19, 'sourceActive': "Je prévois une production de 0 et une consommation de 312,7, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 20, 'sourceActive': "Je prévois une production de 0 et une consommation de 188,73, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 21, 'sourceActive': "Je prévois une production de 0 et une consommation de 188,07, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 22, 'sourceActive': "Je prévois une production de 0 et une consommation de 1752,7, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}, {'index': 23, 'sourceActive': "Je prévois une production de 0 et une consommation de 1734,0, la consommation étant supérieure à la production, j'ai besoin d'une source de secours pour alimenter l'installation.", 'chargerBatt': "Puisque la production est insuffisante pour charger la batterie et que le niveau de charge de la batterie est à 0%, la batterie ne peut pas être utilisée pour alimenter l'installation.", 'mode': "Le mode est en économie pour préserver l'énergie disponible."}]

@app.websocket("/ws/energy")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    print(f"Nouvelle connexion WebSocket: {len(manager.active_connections)} connexions actives")

    # Événement pour signaler l'arrêt des tâches
    stop_event = asyncio.Event()

    # ========== TÂCHE 1 : ÉCOUTE DES MESSAGES ENTRANTS ==========
    async def receive_messages():
        try:
            while not stop_event.is_set():
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                    message = json.loads(data)
                    print(f"Message reçu : {message}")
                    msg_type = message.get("type")
                    if msg_type == "commande_appareil":
                        appareil = message.get("appareil")
                        action = message.get("action")
                        print(f"Commande : {action} sur {appareil}")
                        # Traitement (MQTT, GPIO, etc.)
                        await websocket.send_text(json.dumps({
                            "type": "confirmation",
                            "statut": "ok",
                            "appareil": appareil,
                            "action": action
                        }))
                except asyncio.TimeoutError:
                    # Timeout normal pour vérifier stop_event
                    continue
                except WebSocketDisconnect:
                    print("Client déconnecté (réception)")
                    stop_event.set()
                    break
        except Exception as e:
            print(f"Erreur dans receive_messages: {e}")
            stop_event.set()

    # ========== TÂCHE 2 : ENVOI PÉRIODIQUE DES DONNÉES ==========
    async def send_periodic_data(last_sent_data):
        # Envoi initial
        await send_current_data()
        # Boucle périodique
        while not stop_event.is_set():
            try:
                await asyncio.sleep(5)
                # Vérifier que le WebSocket est toujours ouvert
                if websocket.client_state.name != "CONNECTED":
                    print("WebSocket fermé, arrêt de l'envoi périodique")
                    stop_event.set()
                    break
                # processus de mise a jours des données
                prod_cumul.ajouter(sensor_data['production'])
                conso_cumul.ajouter(sensor_data['consommation'])
                prod_cumul_24h.ajouter(sensor_data['production'])
                conso_cumul_24h.ajouter(sensor_data['consommation'])
                # récuperer la stratégie
                strategie = hourlyStrategy(predictionData)
                # calculer l'epargne
                if 'batt' in  sensor_data["activeSource"] or 'solarPannel' in sensor_data["activeSource"]:
                    saving(sensor_data['consommation']) # cumule pour une heure
                    conso_ER_24h.ajouter(sensor_data['consommation'])# cumule pour 24h
                
                # Créer les données actuelles
                current_data = {
                    "production": f"{sensor_data['production']:.2f}",
                    "consommation": round(conso_cumul_24h.energie_wh(),4),
                    "timestamp": sensor_data["timestamp"],
                    "battPercentage" : f"{sensor_data['battPercentage']:.2f}",
                    "activeSource"  : strategie[datetime.now().hour]["sourceActive"],
                    "production_h" : hourly_data["production_h"],
                    "consommation_h" : hourly_data["consommation_h"],
                    "production_24h" : round(prod_cumul_24h.energie_wh(),4),
                    "maxProd" : round(maxProdValue,3) if isinstance(maxProdValue, (int, float)) else 0,
                    "consommation_24h" : round(conso_cumul_24h.energie_wh(),3),
                    "sbee" : predictionData["sbee"],
                    "prediction" : {"consommation": prediction_consommation,"production":prediction_production},
                    "strategie" : strategie,
                    "epargne" : epargne,
                    "graphicData" : graphic_data,
                    "analyse":{
                        "interpretation": groq_interpretation,
                    }
                    
                }
                # Éviter d'envoyer si les données n'ont pas changé
                if current_data != last_sent_data:
                    await manager.broadcast(json.dumps(current_data))
                    last_sent_data = current_data.copy()
            except WebSocketDisconnect:
                print("Client déconnecté (envoi périodique)")
                stop_event.set()
                break
            except Exception as e:
                print(f"Erreur dans send_periodic_data: {e}")
                await asyncio.sleep(1)

    async def send_current_data():
        """Envoi des données initiales à la connexion"""
        if sensor_data.get("timestamp") is not None:
            initial_data = {
                "production": f"{sensor_data['production']:.2f}",
                "consommation": f"{sensor_data['consommation']:.2f}",
                "timestamp": sensor_data["timestamp"],
                "battPercentage": f"{predictionData.get('battPercentage', 0):.2f}",
                "activeSource": sensor_data.get("activeSource", "unknown"),
            }
            try:
                await websocket.send_text(json.dumps(initial_data))
                print("Données initiales envoyées à la nouvelle connexion")
            except WebSocketDisconnect:
                print("Impossible d'envoyer les données initiales, client déconnecté")
                stop_event.set()
            except Exception as e:
                print(f"Erreur lors de l'envoi des données initiales: {e}")

    # Lancer les deux tâches concurrentes
    receive_task = asyncio.create_task(receive_messages())
    send_task = asyncio.create_task(send_periodic_data(last_sent_data))

    # Attendre que l'une des tâches se termine ou que stop_event soit activé
    await asyncio.wait([receive_task, send_task], return_when=asyncio.FIRST_COMPLETED)

    # Annuler l'autre tâche
    receive_task.cancel()
    send_task.cancel()

    # Nettoyer la connexion du manager
    manager.disconnect(websocket)
    print(f"Connexion WebSocket fermée: {len(manager.active_connections)} connexions actives")