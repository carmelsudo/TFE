import requests
from datetime import datetime
import pandas as pd
import json
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
# Coordonnées de Lokossa (Bénin)
latitude = 6.633
longitude = 1.717

# url de  récupération des informations météo depuis open-meteo
weather_url = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={latitude}&longitude={longitude}"
    f"&hourly=windspeed_10m,sunshine_duration,pressure_msl,shortwave_radiation,temperature_2m,relativehumidity_2m"
    f"&timezone=auto&forecast_days=1"
)
prod_model_url = "http://localhost:8000/prediction/production" # endpoint depuis fastapi pour la prediction 

# fonction pour recurer les info météo du jours
def getweatherData():
    # Requête GET
    response = requests.get(weather_url)
    data = response.json()  # Dictionnaire Python
    
    if "error" in data:
        print("Erreur API :", data["reason"])
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
        } 
# fonction pour récuperer les données météo d'une date précise : 

# Date cible (exemple: 7 avril 2026)
def getPastWeatherData(y:int,m: int,d:int):
    date_cible = datetime(y, m, d)
    # Construction de l'URL pour l'API Historique d'Open-Meteo
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={latitude}&longitude={longitude}"
        f"&start_date={date_cible.strftime('%Y-%m-%d')}"
        f"&end_date={date_cible.strftime('%Y-%m-%d')}"
        f"&hourly=temperature_2m,relative_humidity_2m,pressure_msl,shortwave_radiation,sunshine_duration,wind_speed_10m,weathercode"
        f"&timezone=auto"
    )
    # Requête API
    response = requests.get(url)
    data = response.json()

    # Extraction et formatage des données
    if "hourly" in data:
        hourly = data["hourly"]
        times = hourly["time"]
        
        for i, t_str in enumerate(times):
            dt = datetime.fromisoformat(t_str)
            # print({
            #     "Hour": dt.hour,
            #     "Month": dt.month,
            #     "day" : dt.day,
            #     "WindSpeed": hourly["wind_speed_10m"][i],
            #     "Sunshine": hourly["sunshine_duration"][i] / 60.0,  # Conversion secondes -> minutes
            #     "AirPressure": hourly["pressure_msl"][i],
            #     "Radiation": hourly["shortwave_radiation"][i],
            #     "AirTemperature": hourly["temperature_2m"][i],
            #     "RelativeAirHumidity": hourly["relative_humidity_2m"][i]
            # })
            return {
            "WindSpeed": hourly["wind_speed_10m"],
            "Sunshine": [s/60 for s in hourly["sunshine_duration"]],         
            "AirPressure": hourly["pressure_msl"],
            "Radiation": hourly["shortwave_radiation"],     
            "AirTemperature": hourly["temperature_2m"],
            "RelativeAirHumidity": hourly["relative_humidity_2m"],
            "Hour": [datetime.fromisoformat(t).hour for t in hourly["time"]],            
            "Month": [datetime.fromisoformat(t).month for t in hourly["time"]],             
        } 
    else:
        print("Erreur:", data.get("reason", "Erreur inconnue"))
# fonction pour appeler fastAPI et obtenir la prédiction avec la date du jours

def getPred():
    prod_data = getweatherData()
    # envoie de la requete a fastAPI pour la prédiction de la consommation
    prod_pred = requests.post(
        prod_model_url,
        data=json.dumps(prod_data),
        headers={"Content-Type":"Application/json"}
    )
    return prod_pred.json()

print(getPred())

x = [ t for t in range(24)]
hourly_prod = []
requested_data = getPred()
for r in requested_data['hourly_predictions']:
    hourly_prod .append(r["prediction_wh"] if r["prediction_wh"]>0 else 0)

# plt.plot(x,hourly_prod)
# plt.xticks(x)
# plt.grid(True)
# plt.show()
# --------------------Consommation de la maison ------------------------------------
conso_model_url = "http://localhost:8000/prediction/consommation" # endpoint depuis fastapi pour la prediction 


def get_conso_pred(data):
    request_data = {
        "heure" : data["heure"],
        "WE" : data["WE"],
        "JF" : data['JF'],
        "SP" : data["SP"],
        "SC" : data["SC"]
    }
    conso_pred = requests.post(
        conso_model_url,
        data= json.dumps(request_data),
        headers={"Content-Type":"Application/json"}
    )
    return conso_pred.json() 

hourly_cons = []
for i in range(24):
    hourly_cons.append(get_conso_pred({"heure":i,"WE":1,"JF":0,"SP":1,"SC":0})["prediction de consommation"])
print(hourly_prod)


# {
#     "heure": 20,
#     "WE" : 0 ,
#     "JF": 0 ,
#     "SP" : 1,
#     "SC" : 0
# }