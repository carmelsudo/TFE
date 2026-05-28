#!/usr/bin/env python3
"""
Script d'injection de données artificielles dans la table 'archive'
Période : du 2025-12-01 à aujourd'hui
Base de données : energy.db (créée si absente)
Table archive : id (auto), timestamp, production, consommation, gain, status
"""

import sqlite3
import random
from datetime import datetime, timedelta, date

# Configuration
DB_PATH = "energy.db"
START_DATE = date(2025, 12, 1)
END_DATE = date.today()
TARIF_KWH = 125   # FCFA/kWh
TAXE = 0.18       # TVA (18%)

# Fonction pour générer une production réaliste (Wh) en fonction du mois
def generate_production(dt: date) -> float:
    """
    Production solaire journalière en Wh.
    Dépend du mois : plus élevée en saison sèche (nov-fév) et surtout mars-avril,
    plus faible en saison des pluies (mai-oct). On ajoute une variation aléatoire.
    """
    month = dt.month
    # Base saisonnière : mois secs (nov-fév) ~ 4000-6000 Wh, pluvieux ~ 1500-3500 Wh
    if 3 <= month <= 5:   # printemps, bonne production
        base = random.uniform(4000, 7000)
    elif 6 <= month <= 8:  # début pluies
        base = random.uniform(2000, 4000)
    elif 9 <= month <= 10: # pluies
        base = random.uniform(1500, 3500)
    elif month == 11:      # transition
        base = random.uniform(3000, 5500)
    else:                 # déc, jan, fév
        base = random.uniform(3500, 6000)
    # Variation journalière ±20%
    variation = random.uniform(0.8, 1.2)
    prod = base * variation
    return round(prod, 2)

# Fonction pour générer une consommation réaliste (Wh)
def generate_consumption(dt: date) -> float:
    """
    Consommation journalière en Wh.
    Légèrement plus élevée en semaine qu'en weekend, et en saison chaude (ventilation/réfrigération).
    """
    month = dt.month
    # Saison chaude (nov-fév) -> conso un peu plus élevée (clim, ventilateurs)
    if month in [11, 12, 1, 2]:
        base = random.uniform(3500, 5500)
    else:  # saison pluvieuse, moins chaud
        base = random.uniform(2500, 4500)
    # Weekend : conso souvent plus élevée (présence)
    if dt.weekday() >= 5:  # samedi=5, dimanche=6
        base *= random.uniform(1.05, 1.15)
    # Variation journalière
    variation = random.uniform(0.85, 1.15)
    conso = base * variation
    return round(conso, 2)

# Fonction pour déterminer le status
def get_status(prod: float, conso: float) -> str:
    if prod > conso:
        return "optimale"
    elif prod < conso:
        return "déficitaire"
    else:
        return "equilibré"

# Calcul du gain (en monnaie locale, par exemple FCFA)
def compute_gain(conso_renewable_wh: float) -> float:
    """
    Pour l'archive, le gain représente l'économie réalisée grâce aux énergies renouvelables
    (production solaire + batterie). On suppose ici que toute la consommation est couverte
    par le renouvelable, donc gain = conso * tarif * (1+taxe) en Wh -> conversion en kWh.
    """
    kwh = conso_renewable_wh / 1000.0
    return round(kwh * TARIF_KWH * (1 + TAXE), 2)

# Connexion à la base et injection
def inject_archive_data():
    # Vérifier si la table existe, sinon la créer (structure identique à celle du code original)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS archive(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            production REAL,
            consommation REAL,
            gain REAL,
            status TEXT
        )
    """)
    
    # Supprimer les anciennes données sur la période si vous voulez repartir de zéro
    # (optionnel : décommentez les lignes suivantes pour purger la période)
    cursor.execute("DELETE FROM archive WHERE timestamp >= ? AND timestamp <= ?", 
                    (START_DATE.isoformat(), END_DATE.isoformat()))
    print(f"Anciennes données supprimées pour la période {START_DATE} à {END_DATE}")
    
    # Générer et insérer les données
    current_date = START_DATE
    inserted = 0
    while current_date <= END_DATE:
        # Convertir date en datetime pour le timestamp (0h00)
        timestamp = datetime.combine(current_date, datetime.min.time()).isoformat()
        
        prod = generate_production(current_date)
        conso = generate_consumption(current_date)
        status = get_status(prod, conso)
        gain = compute_gain(conso)  # ici gain = économie totale si tout renouvelable
        
        try:
            cursor.execute("""
                INSERT INTO archive (timestamp, production, consommation, gain, status)
                VALUES (?, ?, ?, ?, ?)
            """, (timestamp, prod, conso, gain, status))
            inserted += 1
        except sqlite3.IntegrityError:
            # Si la ligne existe déjà (par exemple clé unique sur timestamp), on ignore ou on met à jour
            # Ici on passe pour éviter les doublons
            print(f"Doublon ignoré pour {timestamp}")
        
        current_date += timedelta(days=1)
    
    conn.commit()
    conn.close()
    print(f"Injection terminée : {inserted} lignes insérées de {START_DATE} à {END_DATE}")

if __name__ == "__main__":
    inject_archive_data()