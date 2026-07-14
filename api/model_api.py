from fastapi import FastAPI, Request,Form,WebSocket, WebSocketDisconnect, Body
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
import traceback
import math
import aiomqtt
from fastapi import Query


app =FastAPI()
base_path = Path(__file__).resolve().parent.parent

# lien api huggingFace
API_URL = "https://api.groq.com/openai/v1/chat/completions"
headers = {
        "Content-Type": "application/json",
    }

# dossier de fichier statique a servir a  l'interface
app.mount("/static", StaticFiles(directory=f"{base_path}/static"), name="static")

# dossier contenant les différentes fichier html ou css a retourner
templates = Jinja2Templates(directory = base_path/"client/interface")

# Coordonnées de Lokossa (Bénin)
latitude = 6.633
longitude = 1.717
# custom timestamp pour les test;

tarrif_kwh = 125 # tariff du kwh au benin 
taxe = 0.18 # TVA
# broquer mqtt
# Configuration MQTT
MQTT_BROKER = "broker.hivemq.com"  # localhost
MQTT_PORT = 1883                   # Port par défaut Mosquitto
MQTT_USERNAME = ""                 # Laissez vide si pas d'authentification
MQTT_PASSWORD = ""
MQTT_TOPIC_PREFIX = "esp32tfecarmelfiacre"        # Préfixe des topics

# Topic pour les données remontées par l'ESP32
# pour envoyer la stratégie à l'ESP32
MQTT_TOPIC_COMMAND = f"{MQTT_TOPIC_PREFIX}/command"

# declaration de variable
maxProdValue = 250  # Valeur maximale de production trouvée
# url open meteo
weather_url = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={latitude}&longitude={longitude}"
    f"&hourly=windspeed_10m,sunshine_duration,pressure_msl,shortwave_radiation,temperature_2m,relativehumidity_2m,weathercode"
    f"&timezone=auto&forecast_days=1"
)
# fonction pour récuperer les données météorologiques d'une date précise
def getPastWeatherData(target_date):
    """
    Récupère les données météo horaires pour une date précise.
    Utilise l'endpoint ARCHIVE pour les dates trop anciennes pour l'API de prévisions.
    target_date : objet datetime.date ou chaîne 'YYYY-MM-DD'
    """
       # Convertir en objet date
    if isinstance(target_date, datetime):
        target_date = target_date.date()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    # sinon on suppose que c'est déjà un date

    date_str = target_date.isoformat()  # 'YYYY-MM-DD'

    latitude = 6.6515
    longitude = 1.7203

    # L'API d'archive n'a pas de données pour les jours trop récents (moins de 5-6 jours).
    # On vérifie donc si la date est trop récente.
    today = datetime.now().date()
    if isinstance(target_date, str):
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    # Si la date est dans les 7 derniers jours, on utilise l'API de prévisions.
    # Sinon, on utilise l'API d'archive.
    if (today - target_date).days <= 7:
        print(f"Utilisation de l'API de prévisions pour la date {date_str}")
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}&longitude={longitude}"
            f"&hourly=windspeed_10m,sunshine_duration,pressure_msl,shortwave_radiation,temperature_2m,relativehumidity_2m,weathercode"
            f"&timezone=auto"
            f"&start_date={date_str}&end_date={date_str}"
        )
    else:
        print(f"Utilisation de l'API d'archive pour la date {date_str}")
        url = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={latitude}&longitude={longitude}"
            f"&hourly=windspeed_10m,sunshine_duration,pressure_msl,shortwave_radiation,temperature_2m,relativehumidity_2m,weathercode"
            f"&timezone=auto"
            f"&start_date={date_str}&end_date={date_str}"
        )

    response = requests.get(url)
    data = response.json()

    if "error" in data:
        return {"error": data["reason"]}

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
        "weatherCode": hourly["weathercode"]
    }

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
    #print(weatherData)
    #weatherData = {'WindSpeed': [4.1, 3.6, 4.5, 5.4, 3.8, 2.9, 5.6, 4.5, 2.7, 5.4, 9.8, 9.5, 8.3, 6.8, 8.3, 10.1, 10.7, 9.2, 6.4, 4.1, 6.3, 1.9, 3.5, 4.0], 'Sunshine': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.307166666666667, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 3.355, 60.0, 22.023000000000003, 0.0, 0.0, 0.0, 0.0, 0.0], 'AirPressure': [1015.7, 1015.1, 1014.6, 1014.0, 1014.0, 1014.6, 1014.5, 1015.0, 1015.9, 1016.0, 1016.1, 1016.0, 1015.0, 1014.1, 1013.0, 1011.4, 1011.1, 1011.6, 1012.6, 1013.3, 1014.5, 1015.2, 1015.6, 1014.9], 'Radiation': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.0, 74.0, 277.0, 488.0, 626.0, 763.0, 818.0, 819.0, 695.0, 264.0, 316.0, 161.0, 26.0, 0.0, 0.0, 0.0, 0.0], 'AirTemperature': [24.7, 25.9, 25.3, 25.1, 24.9, 24.8, 24.6, 24.5, 25.3, 26.8, 28.5, 29.6, 30.6, 31.4, 31.5, 29.9, 27.5, 27.7, 25.8, 25.1, 24.1, 23.8, 24.0, 23.8], 'RelativeAirHumidity': [98, 95, 97, 98, 98, 98, 98, 97, 95, 89, 78, 72, 67, 65, 65, 72, 88, 86, 92, 94, 97, 98, 96, 96], 'Hour': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'Month': [6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6], 'weatherCode': [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 51, 51, 51, 3, 3, 51, 80, 55, 81, 81, 81, 81, 61, 53]}
except Exception as e: 
    print("error-----------------------------------------")

pastWeatherData = None
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

class DeviceModes(BaseModel):
    modes: dict
    
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


# === Endpoints pour la gestion du mot de passe administrateur ===
class PasswordUpdate(BaseModel):
    current_password: str | None = None
    new_password: str


async def _ensure_settings_table():
    async with aiosqlite.connect("energy.db") as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        await db.commit()


async def _get_setting(key: str):
    await _ensure_settings_table()
    async with aiosqlite.connect("energy.db") as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def _set_setting(key: str, value: str):
    await _ensure_settings_table()
    async with aiosqlite.connect("energy.db") as db:
        await db.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        await db.commit()


@app.get('/settings/password')
async def api_get_password():
    """Récupère le mot de passe administrateur depuis la base de données.
    ATTENTION: renvoyer un mot de passe en clair au client est généralement
    une mauvaise pratique. Ici on suit la demande explicite du client.
    """
    try:
        pwd = await _get_setting('admin_password')
        if pwd is None:
            # Valeur par défaut si absente
            pwd = ' '
            await _set_setting('admin_password', pwd)
        return {"password": pwd}
    except Exception as e:
        return {"error": str(e)}


@app.put('/settings/password')
async def api_update_password(payload: PasswordUpdate = Body(...)):
    """Met à jour le mot de passe administrateur en base.
    Body: { current_password: str|null, new_password: str }
    """
    try:
        stored = await _get_setting('admin_password')
        if stored is None:
            stored = 'motdepasse123'
            await _set_setting('admin_password', stored)

        # Si un mot de passe courant est fourni, on le vérifie
        if payload.current_password is not None and payload.current_password != stored:
            return {"error": "Mot de passe actuel incorrect"}

        await _set_setting('admin_password', payload.new_password)
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


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
global prediction_consommation,prediction_production
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
        
        # table devices (appareils et leurs modes d'autorisation)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS devices(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                allowed_normal BOOLEAN DEFAULT 1,
                allowed_saving BOOLEAN DEFAULT 1,
                allowed_ultrasaving BOOLEAN DEFAULT 0
            )
        """)
        await db.commit()

# Fonction pour initialiser les appareils dans la table devices

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
                await applyRealOrTestStrategy(test_data["cts"])
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
        # Production solaire avec courbe lisse
        production= break_hourly_average(prediction_production["hourly_predictions"][hour]['prediction_wh'],3600)[now.minute]
        # Consommation avec bruit
        consommation = break_hourly_average(prediction_consommation[hour]["prediction de consommation"])[now.minute]
        return max(0, production), max(0, consommation)
# mettre a jours les données de capteurs toutes les 5 secondes 
changement_de_strategie = False
async def updateSensorData():
    global changement_de_strategie,strategie
    """Mettre à jour les données des capteurs en continu"""
    try:
        while True:
            await asyncio.sleep(5)
            sensor_data["production"],sensor_data["consommation"] = generate_data() 
            sensor_data["battPercentage"] = test_data["battPercentage"]
            sensor_data["sbee"] = test_data["sbee"]
            # mise a jour des données stratégiques
            predictionData["battPercentage"] = sensor_data["battPercentage"]
            predictionData["sbee"] = sensor_data["sbee"]
            # mettre a jours le time stamp
            sensor_data["timestamp"] = asyncio.get_event_loop().time()
            # vérification de la sbee et lancement d'une nouvelle stratégie
            if not sensor_data["sbee"] and not changement_de_strategie:
                changement_de_strategie = True
                print("=======changement de stratégie================")
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
    await mqtt_publisher.connect()
    #asyncio.create_task(send_mqtt_command({"mode": "saving", "seuil": 500, "charger_batt": True}))

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
    await mqtt_publisher.disconnect()

#donnée instantannée en prod ces donnée doivent provenir de la lecture des capteur du RBP
test_data = {
    "battPercentage" : 100,
    "battCapacity": 3000,
    "seuil" : 1000,
    "sbee"  : True,
    "timestamp": None,
    "cts" : "null",
}

sensor_data = {
    "production": 0,
    "consommation": 0,
    "battPercentage" : test_data["battPercentage"],
    "battCapacity": test_data["battCapacity"],
    "activeSource" :["solarPannel"],
    "timestamp": None,
    "sbee" : test_data["sbee"] # en prod, cette data doit provenir de la lecture de capteur, 
}
# liste des appareils 

# donnée horaire, sont mise a jours toute les heures dans ccycle1h
hourly_data={
    "production_h" : 0,
    "consommation_h" : 0,
}


# Cache des dernières données envoyées pour éviter les doublons
last_sent_data = None

# Classe MQTT pour récupérer les données
class PersistentMQTTClient:
    """Client MQTT persistant avec reconnexion automatique si la connexion est perdue."""
    def __init__(self):
        self.client = None
        self.connected = False
        self._reconnect_task = None

    async def connect(self):
        """Établit la connexion MQTT et lance la surveillance de reconnexion."""
        await self._connect_internal()
        # Démarrer la tâche de surveillance (reconnexion si perte)
        self._reconnect_task = asyncio.create_task(self._watch_connection())

    async def _connect_internal(self):
        try:
            if self.client:
                await self.disconnect()
            self.client = aiomqtt.Client(
                hostname=MQTT_BROKER,
                port=MQTT_PORT,
                username=MQTT_USERNAME if MQTT_USERNAME else None,
                password=MQTT_PASSWORD if MQTT_PASSWORD else None,
            )
            await self.client.__aenter__()
            self.connected = True
            print(f"✅ MQTT connecté à {MQTT_BROKER}:{MQTT_PORT}")
        except Exception as e:
            self.connected = False
            print(f"❌ Échec connexion MQTT : {e}")

    async def _watch_connection(self):
        """Surveille la connexion et tente de reconnecter si elle est perdue."""
        while True:
            await asyncio.sleep(10)
            if not self.connected:
                print("🔄 MQTT déconnecté, tentative de reconnexion...")
                await self._connect_internal()

    async def publish(self, topic: str, payload: str, qos: int = 1):
        """Publie un message sur le topic donné."""
        if self.client and self.connected:
            try:
                await self.client.publish(topic, payload=payload, qos=qos)
                return True
            except Exception as e:
                print(f"❌ Erreur publication MQTT : {e}")
                self.connected = False  # déclenchera la reconnexion
        else:
            print(f"⚠️ MQTT non connecté, impossible de publier sur {topic}")
        return False

    async def disconnect(self):
        """Ferme proprement la connexion MQTT."""
        if self.client and self.connected:
            try:
                await self.client.__aexit__(None, None, None)
            except:
                pass
            self.client = None
            self.connected = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

# Instance globale du client MQTT (sera initialisée au startup)
mqtt_publisher = PersistentMQTTClient()
# fonction pour l'envoie d'une commande au mqtt
async def send_mqtt_command(command: dict):
    payload = json.dumps(command)
    await mqtt_publisher.publish(MQTT_TOPIC_COMMAND, payload)
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

# endpoint pour la page de test 
@app.get("/test")
def test_page(request:Request):
    return templates.TemplateResponse(
        request = request,
        name = "test.html",
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

# Endpoint pour récupérer tous les appareils
@app.get("/devices")
async def get_devices():
    """Récupère tous les appareils avec leurs permissions par mode"""
    try:
        async with aiosqlite.connect("energy.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT name, allowed_normal, allowed_saving, allowed_ultrasaving
                FROM devices
                ORDER BY name ASC
            """) as cursor:
                rows = await cursor.fetchall()
                devices = []
                for row in rows:
                    devices.append({
                        "name": row["name"],
                        "modes": {
                            "normal": bool(row["allowed_normal"]),
                            "saving": bool(row["allowed_saving"]),
                            "ultraSaving": bool(row["allowed_ultrasaving"])
                        }
                    })
                return {
                    "devices": devices,
                    "count": len(devices)
                }
    except Exception as e:
        return {
            "error": f"Erreur lors de la lecture des appareils: {str(e)}"
        }

# Endpoint pour mettre à jour les permissions d'un appareil
@app.put("/devices/{device_name}")
async def update_device(device_name: str, data: DeviceModes):
    """Met à jour les permissions d'un appareil"""
    try:
        modes = data.modes
        async with aiosqlite.connect("energy.db") as db:
            await db.execute(
                """UPDATE devices 
                   SET allowed_normal = ?, allowed_saving = ?, allowed_ultrasaving = ?
                   WHERE name = ?""",
                (int(modes.get("normal", 0)), int(modes.get("saving", 0)), int(modes.get("ultraSaving", 0)), device_name)
            )
            await db.commit()
            return {"success": True, "message": f"Appareil '{device_name}' mis à jour"}
    except Exception as e:
        return {"error": f"Erreur lors de la mise à jour: {str(e)}"}

# Endpoint pour réinitialiser les permissions par défaut
@app.post("/devices/reset")
async def reset_devices():
    """Réinitialise tous les appareils aux permissions par défaut"""
    devices_defaults = [
        ("Climatisation salon", 1, 1, 0),
        ("Climatisation chambre", 1, 1, 0),
        ("Micro-ondes", 1, 1, 0),
        ("Machine à laver", 1, 0, 0),
        ("Chauffe-eau", 1, 0, 0),
        ("Congélateur", 1, 1, 1),
        ("Réfrigérateur", 1, 1, 1),
    ]
    try:
        async with aiosqlite.connect("energy.db") as db:
            for name, normal, saving, ultrasaving in devices_defaults:
                await db.execute(
                    """UPDATE devices 
                       SET allowed_normal = ?, allowed_saving = ?, allowed_ultrasaving = ?
                       WHERE name = ?""",
                    (normal, saving, ultrasaving, name)
                )
            await db.commit()
            return {"success": True, "message": "Tous les appareils ont été réinitialisés aux permissions par défaut"}
    except Exception as e:
        return {"error": f"Erreur lors de la réinitialisation: {str(e)}"}

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
def build_prediction_context():
    use_test_values = not (str(test_data.get("cts", "null")).strip().lower() in {"", "null", "none"})
    return {
        "battPercentage": test_data["battPercentage"] if use_test_values else sensor_data["battPercentage"],
        "battCapacity": test_data["battCapacity"] if use_test_values else sensor_data["battCapacity"],
        "seuil": test_data["seuil"] if use_test_values else 1000,
        "sbee": test_data["sbee"] if use_test_values else sensor_data["sbee"],
        "predProd": prediction_production,
        "predConso": prediction_consommation,
    }

predictionData = build_prediction_context()
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
    batt_total_capacity = predictionData.get("battCapacity", 3000)
    seuil = predictionData.get("seuil", 1000)
    for i in range(24):
        lo = logique(
            hourly_conso[i]['prediction de consommation'],
            hourly_prod[i]['prediction_wh'],
            predictionData["battPercentage"],
            batt_total_capacity,
            seuil,
            predictionData["sbee"],
            i
        )
        strategy.append(lo)
    return strategy


def refresh_strategy():
    global predictionData, strategie
    predictionData = build_prediction_context()
    strategie = hourlyStrategy(predictionData)
    return strategie

# variable contenant la stratégie a adopter par le système pour une journée:
strategie = refresh_strategy() # a envoyer pour interpretation
print("================strat 1 =======================")
print(strategie[1])

# commande des appareils autorisé pour chaque mode

def get_device_id(device_name: str) -> int:
    """
    Retourne un ID (0 à 6) pour un nom d'appareil donné.
    
    Args:
        device_name (str): Nom de l'appareil (ex: "Chauffe-eau").
    
    Returns:
        int: ID de l'appareil (0 à 6).
    
    Raises:
        ValueError: Si le nom de l'appareil n'est pas reconnu.
    """
    mapping = {
        "Chauffe-eau": 0,
        "Climatisation chambre": 1,
        "Climatisation salon": 2,
        "Congélateur": 3,
        "Machine à laver": 4,
        "Micro-ondes": 5,
        "Réfrigérateur": 6
    }
    
    # Vérifier si l'appareil existe
    if device_name not in mapping:
        raise ValueError(f"Appareil inconnu : '{device_name}'. "
                         f"Choisissez parmi {list(mapping.keys())}")
    
    return mapping[device_name]

# fonction pour activer le mode de fonctionnement
async def activateMode(mode):
    devices =  await get_devices()
    devicesList = devices.get("devices")
    onDevices = [] # liste des appareils a allumer pour le mode actif
    if mode == "normal":
        for device in devicesList:
            if device["modes"]["normal"]:
                onDevices.append(get_device_id(device['name']))
        print ("Mode normal Activé. Tout les appareils sont autorisé a fonctionner")
    elif mode == "saving":
        for device in devicesList:
            if device["modes"]["saving"]:
                onDevices.append(get_device_id(device['name']))
        print ("Mode Economie Activé, desormains les appareils de forte consommation sont désactiver pour économiser l'énergie")
    elif mode == "ultraSaving":
        for device in devicesList:
            if device["modes"]["ultraSaving"]:
                onDevices.append(get_device_id(device['name']))
        print ("mode ultra économie activé, seul les appareils de premières néccésité sont activé")
    # envoie de la commande finale
    command = {
        "onDevice" : onDevices
    }
    return command

# fonction pour activer la ou les sources pour alimenter la maison
#def activateSource(asrc):
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
async def applyStrategy(cts= False):
    global strategie
    refresh_strategy()
    nowStrategy = strategie[datetime.now().hour if type(cts)== bool else cts]# datetime.now().hour if type(cts)== bool else cts
    print(nowStrategy)
    if nowStrategy["chargerBatt"]:
        # activer le chargement des batterie
        print("chargement des battéries: Autoriser le relais connecté a la batterie ")
        chargerBatt = True
    else :
        chargerBatt = False
    activeMode = await activateMode(nowStrategy["mode"])
    activeSource =  nowStrategy["sourceActive"]
    command = {
        "chargerBatt" : chargerBatt,
        "activateMode" : activeMode,
        "activeSource" : activeSource,
        "lcd" : [sensor_data["battPercentage"],nowStrategy["mode"],math.floor(sensor_data['production']*100)/100, math.floor(round(conso_cumul_24h.energie_wh())*100)/100]
    }
    await send_mqtt_command(command)
    print("================commandes envoyé====================")

# fonction pour appliquer la stratégie en fonction  ou non des données de test
async def applyRealOrTestStrategy(cts):
    normalized_cts = cts
    if isinstance(cts, str):
        normalized_cts = cts.strip()
        if normalized_cts.lower() in {"", "null", "none"}:
            normalized_cts = False
        else:
            try:
                normalized_cts = int(normalized_cts)
            except ValueError:
                normalized_cts = False

    if isinstance(normalized_cts, (int, float)) and not isinstance(normalized_cts, bool):
        await applyStrategy(normalized_cts)
        print("Test situation")
    else:
        await applyStrategy()
        print("Real situation")
# application immediate de la stratégie actuelle
asyncio.create_task(applyRealOrTestStrategy(test_data["cts"]))

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
        await applyRealOrTestStrategy(test_data["cts"])
# explication de la stratégie par l'ia deepseek
def getExplanation(strategie):
    print("=================================Relancement de groq============================")
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
    exemple = """Tu dois produire dans une liste des jsons suivant cet exemple: { "index":"l'index que tu recoit","sourceActive": "je prévoit une production de 180w et une consommation de 20w, la production etant supérieur a la consommation, je bascule alors l'installation sur les panneaux solaire pour économiser...","chargerBatt": "Le pourcentage des batterie est de 20% pour éviter une décharge profonde j'utilise le surplus de production pour recharger les recharger","mode": "si le mode est normal: en autosuffisance solaire alors tout les appareils sont autorisé a consommé l'énergie disponible. ou si le mode est saving: economie d'energie, les appareils a forte consommation sont desactivé pour augmenter l'autonomie. et si c'est ultrasaving: energie disponible très faible, seul les appareils neccessaires sont activée"}
    """
    payload ={
        "messages": [
            {
                "role": "user",
                "content": f"{explication} ton role est d'expliquer chacune de ces sorties {output} avec leurs paramètres en te basant sur cet exemple {exemple} tu es libre de reformuler, aucun commentaire ni explication avant et apres le json n'est néccessaire en dehors de l'interpretation, comporte toi comme une api qui retourne une liste  json valide et incrémentable"
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
#groq_interpretation = [{'index': '0', 'sourceActive': "La consommation est de 1695.4 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '1', 'sourceActive': "La consommation est de 1707.13 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '2', 'sourceActive': "La consommation est de 1710.5 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '3', 'sourceActive': "La consommation est de 1685.6 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '4', 'sourceActive': "La consommation est de 200.48 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '5', 'sourceActive': "La consommation est de 239.9 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '6', 'sourceActive': "La consommation est de 187.74 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '7', 'sourceActive': "La consommation est de 277.75 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '8', 'sourceActive': "La consommation est de 151.6 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '9', 'sourceActive': "La consommation est de 149.09 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '10', 'sourceActive': "La consommation est de 151.28 et la production est de 1034.69, la production solaire est supérieure à la consommation, mais la batterie est à 0%, l'installation utilise donc la source de secours pour recharger la batterie.", 'chargerBatt': 'La batterie est à 0% et la production solaire est supérieure au seuil de recharge, la batterie peut être rechargée.', 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '11', 'sourceActive': "La consommation est de 149.42 et la production est de 2413.33, la production solaire est supérieure à la consommation et la batterie est à 0%, l'installation utilise donc les panneaux solaires pour fonctionner et recharger la batterie.", 'chargerBatt': 'La batterie est à 0% et la production solaire est supérieure au seuil de recharge, la batterie peut être rechargée.', 'mode': "Le mode est normal, l'installation fonctionne en autosuffisance solaire et tous les appareils peuvent consommer l'énergie disponible."}, {'index': '12', 'sourceActive': "La consommation est de 328.03 et la production est de 3184.21, la production solaire est supérieure à la consommation et la batterie est à 0%, l'installation utilise donc les panneaux solaires pour fonctionner et recharger la batterie.", 'chargerBatt': 'La batterie est à 0% et la production solaire est supérieure au seuil de recharge, la batterie peut être rechargée.', 'mode': "Le mode est normal, l'installation fonctionne en autosuffisance solaire et tous les appareils peuvent consommer l'énergie disponible."}, {'index': '13', 'sourceActive': "La consommation est de 197.74 et la production est de 3945.44, la production solaire est supérieure à la consommation et la batterie est à 0%, l'installation utilise donc les panneaux solaires pour fonctionner et recharger la batterie.", 'chargerBatt': 'La batterie est à 0% et la production solaire est supérieure au seuil de recharge, la batterie peut être rechargée.', 'mode': "Le mode est normal, l'installation fonctionne en autosuffisance solaire et tous les appareils peuvent consommer l'énergie disponible."}, {'index': '14', 'sourceActive': "La consommation est de 198.48 et la production est de 3691.04, la production solaire est supérieure à la consommation et la batterie est à 0%, l'installation utilise donc les panneaux solaires pour fonctionner et recharger la batterie.", 'chargerBatt': 'La batterie est à 0% et la production solaire est supérieure au seuil de recharge, la batterie peut être rechargée.', 'mode': "Le mode est normal, l'installation fonctionne en autosuffisance solaire et tous les appareils peuvent consommer l'énergie disponible."}, {'index': '15', 'sourceActive': "La consommation est de 199.82 et la production est de 3057.45, la production solaire est supérieure à la consommation et la batterie est à 0%, l'installation utilise donc les panneaux solaires pour fonctionner et recharger la batterie.", 'chargerBatt': 'La batterie est à 0% et la production solaire est supérieure au seuil de recharge, la batterie peut être rechargée.', 'mode': "Le mode est normal, l'installation fonctionne en autosuffisance solaire et tous les appareils peuvent consommer l'énergie disponible."}, {'index': '16', 'sourceActive': "La consommation est de 201.4 et la production est de 1116.54, la production solaire est supérieure à la consommation, mais la batterie est à 0%, l'installation utilise donc la source de secours pour recharger la batterie.", 'chargerBatt': 'La batterie est à 0% et la production solaire est supérieure au seuil de recharge, la batterie peut être rechargée.', 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '17', 'sourceActive': "La consommation est de 149.1 et la production est de 1566.9, la production solaire est supérieure à la consommation et la batterie est à 0%, l'installation utilise donc les panneaux solaires pour fonctionner et recharger la batterie.", 'chargerBatt': 'La batterie est à 0% et la production solaire est supérieure au seuil de recharge, la batterie peut être rechargée.', 'mode': "Le mode est normal, l'installation fonctionne en autosuffisance solaire et tous les appareils peuvent consommer l'énergie disponible."}, {'index': '18', 'sourceActive': "La consommation est de 190.35 et la production est de 1837.99, la production solaire est supérieure à la consommation et la batterie est à 0%, l'installation utilise donc les panneaux solaires pour fonctionner et recharger la batterie.", 'chargerBatt': 'La batterie est à 0% et la production solaire est supérieure au seuil de recharge, la batterie peut être rechargée.', 'mode': "Le mode est normal, l'installation fonctionne en autosuffisance solaire et tous les appareils peuvent consommer l'énergie disponible."}, {'index': '19', 'sourceActive': "La consommation est de 313.7 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '20', 'sourceActive': "La consommation est de 188.51 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '21', 'sourceActive': "La consommation est de 189.77 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '22', 'sourceActive': "La consommation est de 1754.21 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}, {'index': '23', 'sourceActive': "La consommation est de 1742.95 et la production est de 0, aucune énergie solaire disponible, l'installation utilise donc la source de secours pour fonctionner.", 'chargerBatt': "La batterie est à 0% et il n'y a pas de production solaire, la batterie ne peut pas être rechargée.", 'mode': "Le mode est en économie d'énergie, les appareils à forte consommation sont désactivés pour augmenter l'autonomie."}]

# fonction de test
def test(date):
    # recuperer les données météorologiques passées:
    pastWheaterData =  getPastWeatherData(date)
    # récuperer les données du jours de la date 
    dateData =  analyser_lokossa(date)
    pred_consommation =  getConso(dateData)
    pred_production = getPred(pastWheaterData)
    return pred_production,pred_consommation


@app.websocket("/ws/energy")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    print(f"Nouvelle connexion WebSocket: {len(manager.active_connections)} connexions actives")

    # Événement pour signaler l'arrêt des tâches
    stop_event = asyncio.Event()

    # ========== TÂCHE 1 : ÉCOUTE DES MESSAGES ENTRANTS ==========
    async def receive_messages():
        global prediction_production, prediction_consommation, groq_interpretation
        try:
            while not stop_event.is_set():
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                    message = json.loads(data)
                    print(f"\n{'='*60}")
                    print(f"📨 Message reçu : {message}")
                    print(f"{'='*60}")
                    msg_type = message.get("type")
                    
                    if msg_type == "test_data":
                        print(f"\n🔹 DONNÉES DU FORMULAIRE TEST 🔹")
                        print(f"  Timestamp: {message.get('timestamp')}")
                        print(f"  Pourcentage batterie: {message.get('battPercentage')}%")
                        print(f"  Capacité batterie: {message.get('battTotalCapacity')} Wh")
                        print(f"  Seuil: {message.get('seuil')} W")
                        print(f"  SBEE (réseau disponible): {message.get('sbee')}")
                        print(f"  CTS: {message.get('cts')}")
                        print(f"{'='*60}\n")
                        
                        # actualisation des variables de predictions
                        testData = test(datetime.fromisoformat(str(message.get('timestamp'))))
                        prediction_production,prediction_consommation = testData
                        test_data["battPercentage"] = message.get('battPercentage')
                        test_data["battCapacity"] = message.get('battTotalCapacity')
                        test_data["seuil"] = message.get('seuil')
                        test_data["sbee"] = message.get('sbee')
                        try:
                            cts_value = message.get("cts")
                            test_data["cts"] = int(cts_value) if str(cts_value).strip().lower() not in {"", "null", "none"} else "null"
                        except (TypeError, ValueError):
                            test_data["cts"] = "null"
                        strategie = refresh_strategy()
                        print(strategie)
                        # Répondre au client
                        await websocket.send_text(json.dumps({
                            "type": "confirmation",
                            "statut": "ok",
                            "message": "Données de test reçues et traitées"
                        }))
                        await applyRealOrTestStrategy(test_data["cts"])
                        groq_interpretation = getExplanation(strategie)# interpretation des différentes décisions
                        print("-----------------------------")
                        print(groq_interpretation[1])
                    elif msg_type == "commande_appareil":
                        appareil = message.get("appareil")
                        action = message.get("action")
                        print(f"Commande : {action} sur {appareil}")
                        # Traitement (MQTT, GPIO, etc.)
                        await send_mqtt_command(
                            {
                                "appareil" : appareil,
                                "action" : action
                            }
                        )
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
            traceback.print_exc() 
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
                refresh_strategy()
                #strategie = logique()
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
                    },
                    "autorizedDevices" :await get_devices(),
                    "cts" : test_data["cts"],
                    
                }
                # Éviter d'envoyer si les données n'ont pas changé
                if current_data != last_sent_data:
                    await manager.broadcast(json.dumps(current_data))
                    last_sent_data = current_data.copy()
                # publication périodique des données sur mosquitto
                await applyRealOrTestStrategy(test_data["cts"])
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
