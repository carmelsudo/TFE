import asyncio
import random
import aiomqtt
from datetime import datetime

class ESP32Simulator:
    def __init__(self, esp32_id="sim_001"):
        self.esp32_id = esp32_id
        self.running = True
        
    def generate_data(self):
        """Génère des données avec tendances réalistes"""
        now = datetime.now()
        hour = now.hour
        
        # Production solaire avec courbe lisse
        if 6 <= hour <= 18:
            # Courbe sinusoïdale simplifiée
            factor = (hour - 6) / 12  # 0 à 1 sur la journée
            production = 3000 * (1 - (2*factor - 1)**2)  # Parabole
            production += random.randint(-100, 100)
        else:
            production = random.randint(0, 30)
        
        # Consommation avec bruit
        base_consumption = 400
        if 7 <= hour <= 9:  # Matin
            base_consumption = 1200
        elif 12 <= hour <= 14:  # Midi
            base_consumption = 800
        elif 18 <= hour <= 22:  # Soir
            base_consumption = 1500
            
        consommation = base_consumption + random.randint(-200, 200)
        return max(0, production), max(0, consommation)
    
    async def run(self):
        async with aiomqtt.Client("localhost") as client:
            while self.running:
                prod, conso = self.generate_data()
                battPercentage = 20
                timestamp = datetime.now().isoformat()
                
                # Envoi au broker (comme un vrai ESP32)
                await client.publish(
                    f"maison/{self.esp32_id}/production",
                    payload=str(prod)
                )
                await client.publish(
                    f"maison/{self.esp32_id}/consommation",
                    payload=str(conso)
                )
                await client.publish(
                    f"maison/{self.esp32_id}/battPercentage",
                    payload=str(battPercentage)
                )
                # lire les donnée des capteur en rapport avec la présence ou pas de la sbee
                readSensor = True
                sbee = 1 if readSensor else 0
                await client.publish(
                    f"maison/{self.esp32_id}/sbee",
                    payload= int(sbee)
                )
                
                print(f"[{timestamp}] ESP32-{self.esp32_id} → Prod:{prod:.0f}W Conso:{conso:.0f}W battP:{battPercentage} sbee:{sbee}")
                await asyncio.sleep(5)  # Envoi toutes les 5 secondes

async def main():
    ESP32Simulator("esp_1") 
    await asyncio.gather(ESP32Simulator("esp_1").run())
if __name__ == "__main__":
    asyncio.run(main())