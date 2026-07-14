from datetime import date,datetime, timedelta
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
    
    return [est_weekend,est_jour_ferie,sp,sc]

# test d'analyse d'une date quelconque : 

print(analyser_lokossa(datetime.fromisoformat("2025-06-05T14:02:00.000Z"))) 

#