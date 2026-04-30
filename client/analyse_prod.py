import requests
import json

prod_model_url = "http://localhost:8000/prediction/production" # endpoint depuis fastapi pour la prediction 

# {
#     "heure": 20,
#     "WE" : 0 ,
#     "JF": 0 ,
#     "SP" : 1,
#     "SC" : 0
# }

def get_prod():
    #  préparation de la requette
    req = requests.post(
        prod_model_url,
        data= 
    )
