def logique(conso, prod,battPercentage,seuil,sbee):
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
        battEnergy = battPercentage * 10/100
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
             
print(logique(150,50,70,20,False))

import pickle
with open("/home/camo/Desktop/TFE/api/model/conso_model.pkl", "rb") as f:
    model = pickle.load(f)
    print("Colonnes attendues:", model.n_features_in_)
    if hasattr(model, 'feature_names_in_'):
        print("Noms des features:", model.feature_names_in_)