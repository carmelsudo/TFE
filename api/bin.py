import os
import requests

API_URL = "https://router.huggingface.co/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {"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"}",
}

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()
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
output = "chargerBatt: true, mode: normal,sourceActive:[solarPannel]"
parameter = "Conso=149.42, prod= 4077.79 battPercentage=0 battTotalCapacity=3000 seuil=100 sbee=True,index=index"
exemple = """Tu dois produire dans une liste des json suivant cet exemple: { 'index':'l'index que tu recoit','sourceActive’: 'je prévoit une production de 180 et une consommation de 20, la production etant supérieur a la consommation, je bascule alors l’installation sur les panneaux solaire pour économiser...’,
'chargerBatt’: 'Le pourcentage des batterie est de 20% pour éviter une décharge profonde j’utilise le surplus de production pour recharger les recharger’,
'mode’: si le mode est normal ' en autosuffisance solaire:alors tout les appareils sont autorisé a consommé l’énergie disponible’ ou si le mode est saving 'economie denergie’: les appareils a forte consommation sont desactiver pour augmenter l’autonomei’ et si c’est ultrasaving 'energie disponible très faible, seul les appareils neccessaires sont activée}’
"""
response = query({
    "messages": [
        {
            "role": "user",
            "content": f"{explication} ton role est d'expliquer chaciune de ces sorties {output} avec leurs paramètres en te basant sur cet exemple {exemple}"
        }
    ],
    "model": "deepseek-ai/DeepSeek-V4-Pro:novita"
})

print(response["choices"][0]["message"].get('content'))