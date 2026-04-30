import requests
import json
import matplotlib.pyplot as plt

conso_model_url = "http://localhost:8000/prediction/consommation" # endpoint depuis fastapi pour la prediction 

# {
#     "heure": 20,
#     "WE" : 0 ,
#     "JF": 0 ,
#     "SP" : 1,
#     "SC" : 0
# } 
jour = []
parametre = [
    
]
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
# prediction pour les paramètres
get_conso_pred( {
    "heure": 20,
    "WE" : 0 ,
    "JF": 0 ,
    "SP" : 1,
    "SC" : 0
 })  
y = []
x = []
combinaison = [
    [0,0,0,1],
    [0,0,1,0],
    [0,1,0,1],
    [0,1,1,0],
    [1,0,0,1],
    [1,0,1,0],
    [1,1,0,1],
    [1,1,1,0],
]
predictions =[]
inter = []
for c in combinaison :
    for i in range(24):
            inter.append(get_conso_pred({"heure":i,"WE":c[0],"JF":c[1],"SP":c[2],"SC":c[3]})["prediction de consommation"])
    predictions.append(inter.copy())
    inter.clear()

import matplotlib.pyplot as plt
import numpy as np

import matplotlib.pyplot as plt
import numpy as np
# fonction généré par deepseek pour tracer les courbe d'évolution de la consommation
def tracer_courbes_horaires(liste_series, x=None, labels=None):
    """

    Paramètres
    ----------
    liste_series : list of lists
        Liste contenant des sous‑listes de 24 valeurs.
    x : array-like, optionnel
        Les abscisses (les 24 heures). Si None ou si sa longueur ≠ 24,
        np.arange(24) est utilisé.
    labels : list of str, optionnel
        Noms des courbes pour la légende. Si None, "Série 1", "Série 2", etc.
    """
    # Vérification et création de l'axe x
    if x is None or len(x) != 24:
        if x is not None:
            print(f"Attention : x a {len(x)} élément(s) au lieu de 24. Utilisation de np.arange(24).")
        x = np.arange(24)

    n_series = len(liste_series)
    if n_series == 0:
        raise ValueError("La liste de séries est vide.")

    # Vérification de la longueur de chaque série
    for i, serie in enumerate(liste_series):
        if len(serie) != 24:
            print(f"Attention : série {i+1} de longueur {len(serie)} (24 attendu).")

    # Préparation des couleurs (16 maximum pour rester lisibles)
    max_couleurs = 20
    couleurs = plt.cm.tab20(np.linspace(0, 1, max_couleurs))
    if n_series > max_couleurs:
        print(f"Attention : plus de {max_couleurs} séries, les couleurs seront réutilisées.")
        couleurs = np.tile(couleurs, int(np.ceil(n_series / max_couleurs)))[:n_series]

    # Labels par défaut
    if labels is None:
        labels = [f'Série {i+1}' for i in range(n_series)]
    elif len(labels) != n_series:
        print("Attention : le nombre de labels ne correspond pas au nombre de séries. Labels par défaut utilisés.")
        labels = [f'Série {i+1}' for i in range(n_series)]


    for i, (serie, label) in enumerate(zip(liste_series, labels)):
        plt.figure(figsize=(16, 6))
        plt.grid(True)
        plt.title(label=combinaison[i])
        plt.plot(x, serie, label=label, color=couleurs[i % len(couleurs)], linewidth=1.5)
        plt.xticks(x)
        plt.xlabel('Heure de la journée')
        plt.ylabel('Valeur')
        plt.title('Données horaires')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()
        plt.savefig(f"static/images/conso_plot_{'_'.join(map(str, combinaison[i]))}.png") # Enregistre le graphique
label = combinaison
tracer_courbes_horaires(predictions,labels=label)
