#include <WiFi.h>
#include <PubSubClient.h>

// --- Informations Wi-Fi (Wokwi les simule, mettez ce que vous voulez) ---
const char* ssid = "Wokwi-GUEST";      // N'importe quel nom fonctionne
const char* password = "";              // Peut rester vide

// --- Informations MQTT ---
const char* mqtt_broker = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* mqtt_topic = "esp32tfecarmelfiacre/command";

// --- Objets pour la connexion ---
WiFiClient espClient;
PubSubClient client(espClient);

int messageCount = 0;
unsigned long lastPublishTime = 0;
const long publishInterval = 5000;
// les différentes led représentant un appareil et un relai

// ------------------------------------------------------------
// Callback : quand un message arrive sur le topic
// ------------------------------------------------------------
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("📩 Message reçu sur [");
  Serial.print(topic);
  Serial.print("] : ");

  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println(message);
}

// ------------------------------------------------------------
// Reconnexion MQTT
// ------------------------------------------------------------
void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print("🔌 Connexion au broker MQTT...");
    
    String clientId = "ESP32Client-";
    clientId += String(WiFi.macAddress());
    
    if (client.connect(clientId.c_str())) {
      Serial.println(" ✅ Connecté !");
      client.subscribe(mqtt_topic);
      Serial.print("📡 Abonné au topic : ");
      Serial.println(mqtt_topic);
    } else {
      Serial.print(" ❌ Échec, code : ");
      Serial.print(client.state());
      Serial.println(" -> Nouvel essai dans 5s...");
      delay(5000);
    }
  }
}

// ------------------------------------------------------------
// SETUP
// ------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(100);

  // Connexion Wi-Fi (simulée automatiquement sur Wokwi)
  Serial.print("📶 Connexion au Wi-Fi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" ✅ Connecté !");
  Serial.print("📡 Adresse IP : ");
  Serial.println(WiFi.localIP());

  // Configuration MQTT
  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(callback);
  reconnectMQTT();
}

// ------------------------------------------------------------
// LOOP
// ------------------------------------------------------------
void loop() {
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();

  // Publication toutes les 5 secondes
  /*unsigned long now = millis();
  if (now - lastPublishTime >= publishInterval) {
    lastPublishTime = now;
    messageCount++;
    String payload = "Hello depuis ESP32 ! (";
    payload += messageCount;
    payload += ")";

    if (client.publish(mqtt_topic, payload.c_str())) {
      Serial.print("📤 Publié : ");
      Serial.println(payload);
    } else {
      Serial.println("❌ Échec publication !");
    }
  }*/
}

