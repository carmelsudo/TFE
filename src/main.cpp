// ============================================================

// 1. AUGMENTER LA TAILLE MAX DES PAQUETS MQTT (AVANT l'include)

// ============================================================

#define MQTT_MAX_PACKET_SIZE 2048   // 2 Ko (ajustez si besoin)



#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <LiquidCrystal.h>

// ========== CONFIGURATION ==========

// --- Wi-Fi (modifiez pour votre réseau) ---

const char* ssid = "Wokwi-GUEST";    //M022_052F ou "Wokwi-GUEST" sur simulateur

const char* password = "";       //33106705 ou "" sur Wokwi



// --- Broker MQTT ---

const char* mqtt_broker = "broker.hivemq.com"; // ou IP locale

const int mqtt_port = 1883;

const char* mqtt_topic = "esp32tfecarmelfiacre/command";



// --- Broches des LEDs ---
const int devicePins[7] = {4, 26, 21, 19, 18, 16, 17};
const int sourceSolarPin = 33;
const int sourceBattPin = 32;
const int sourceSbeePin = 27;
const int chargingLedPin = 2;

// LCD parallèle
const int lcdRs = 13;
const int lcdEn = 23;
const int lcdD4 = 5;
const int lcdD5 = 14;
const int lcdD6 = 15;
const int lcdD7 = 25;
LiquidCrystal lcd(lcdRs, lcdEn, lcdD4, lcdD5, lcdD6, lcdD7);

// Bouton poussoir
const int buttonPin = 22;
int lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

bool displayFirstPage = true;
int battPercentValue = 0;
String lcdMode = "";
float lcdProduction = 0.0;
float lcdConsumption = 0.0;

// ===================================

WiFiClient espClient;

PubSubClient client(espClient);



unsigned long lastPublish = 0;

const long publishInterval = 10000; // 10 secondes



// ------------------------------------------------------------

// Fonction pour allumer/éteindre les LEDs selon une liste JSON

// ------------------------------------------------------------

void resetAllLeds() {
  for (int i = 0; i < 7; i++) {
    digitalWrite(devicePins[i], LOW);
  }
  digitalWrite(sourceSolarPin, LOW);
  digitalWrite(sourceBattPin, LOW);
  digitalWrite(sourceSbeePin, LOW);
  digitalWrite(chargingLedPin, LOW);
}

void setDeviceLedById(int deviceId, bool state) {
  if (deviceId >= 0 && deviceId < 7) {
    digitalWrite(devicePins[deviceId], state ? HIGH : LOW);
  }
}

void setDeviceLedByName(const String& deviceName, bool state) {
  String name = deviceName;
  name.trim();
  name.toLowerCase();

  if (name == "chauffe-eau") {
    setDeviceLedById(0, state);
  } else if (name == "climatisation chambre") {
    setDeviceLedById(1, state);
  } else if (name == "climatisation salon") {
    setDeviceLedById(2, state);
  } else if (name == "congelateur") {
    setDeviceLedById(3, state);
  } else if (name == "machine à laver" || name == "machine a laver") {
    setDeviceLedById(4, state);
  } else if (name == "micro-ondes" || name == "micro ondes") {
    setDeviceLedById(5, state);
  } else if (name == "réfrigérateur" || name == "refrigerateur") {
    setDeviceLedById(6, state);
  }
}

void setSourceLedByName(const String& sourceName, bool state) {
  String source = sourceName;
  source.trim();
  source.toLowerCase();
  source.replace(" ", "");
  source.replace("-", "");
  source.replace("_", "");

  if (source == "solarpannel" || source == "panneausolaire" || source == "solar") {
    digitalWrite(sourceSolarPin, state ? HIGH : LOW);
  } else if (source == "batt" || source == "battery" || source == "batterie") {
    digitalWrite(sourceBattPin, state ? HIGH : LOW);
  } else if (source == "sbee" || source == "sourcesecours") {
    digitalWrite(sourceSbeePin, state ? HIGH : LOW);
  }
}

void setDevicesFromList(JsonArray deviceList) {
  for (JsonVariant v : deviceList) {
    if (v.is<int>()) {
      int deviceId = v.as<int>();
      Serial.print("   ➡️ Appareil ID : ");
      Serial.println(deviceId);
      setDeviceLedById(deviceId, true);
    } else {
      String device = v.as<String>();
      Serial.print("   ➡️ Appareil : ");
      Serial.println(device);
      setDeviceLedByName(device, true);
    }
  }
}

void setSourcesFromList(JsonArray sourceList) {
  for (JsonVariant v : sourceList) {
    String source = v.as<String>();
    Serial.print("   🔌 Source active : ");
    Serial.println(source);
    setSourceLedByName(source, true);
  }
}

void updateLcdDisplay() {
  lcd.clear();
  if (displayFirstPage) {
    lcd.setCursor(0, 0);
    lcd.print("Batt:");
    lcd.print(battPercentValue);
    lcd.print("%");
    lcd.setCursor(0, 1);
    lcd.print("Mode:");
    lcd.print(lcdMode.substring(0, min((int)lcdMode.length(), 10)));
  } else {
    lcd.setCursor(0, 0);
    lcd.print("Prod:");
    lcd.print(lcdProduction, 1);
    lcd.print("W");
    lcd.setCursor(0, 1);
    lcd.print("Cons:");
    lcd.print(lcdConsumption, 1);
    lcd.print("W");
  }
}

void updateLcdFromPayload(JsonVariant lcdValue) {
  if (lcdValue.isNull()) {
    return;
    Serial.println("null");
  }
  Serial.println("middle");
  if (lcdValue.is<JsonArray>()) {
    Serial.println("lcdValue is a jsonArray");
    JsonArray lcdArray = lcdValue.as<JsonArray>();
    if (lcdArray.size() >= 4) {
      battPercentValue = lcdArray[0] | 0;
      lcdMode = lcdArray[1].as<String>();
      lcdProduction = lcdArray[2] | 0.0;
      lcdConsumption = lcdArray[3] | 0.0;
    }
  } else if (lcdValue.is<JsonObject>()) {
    JsonObject lcdObject = lcdValue.as<JsonObject>();
    battPercentValue = lcdObject["battPercentage"] | lcdObject["battery"] | 0;
    lcdMode = lcdObject["mode"].as<String>();
    lcdProduction = lcdObject["production"] | lcdObject["prod"] | 0.0;
    lcdConsumption = lcdObject["consumption"] | lcdObject["cons"] | 0.0;
  }

  updateLcdDisplay();
  Serial.print("   🖥️ LCD update: ");
  Serial.print(battPercentValue);
  Serial.print("%, ");
  Serial.print(lcdMode);
  Serial.print(", ");
  Serial.print(lcdProduction);
  Serial.print(" W, ");
  Serial.print(lcdConsumption);
  Serial.println(" W");
}

  




// ------------------------------------------------------------

// CALLBACK optimisé (sans String, avec filtre, sans blocage)

// ------------------------------------------------------------

void callback(char* topic, byte* payload, unsigned int length) {

  // --- 1. Détection du "ping" (comparaison directe) ---

  if (length >= 4 && 

      payload[0] == 'p' && payload[1] == 'i' && 

      payload[2] == 'n' && payload[3] == 'g') {

    // On peut afficher rapidement sans bloquer

    Serial.println("📤 Ping reçu (ignoré)");

    return;

  }



  // --- 2. Affichage du message reçu (pour déboguer) ---

  // On itère sur le payload pour gérer les caractères nuls éventuels

  Serial.print("📩 Message reçu (");

  Serial.print(length);

  Serial.print(" octets) : ");

  for (int i = 0; i < length; i++) {

    Serial.print((char)payload[i]);

  }

  Serial.println();



  // --- 3. Filtre JSON (pour ne garder que l'essentiel) ---

  // Cela réduit considérablement la mémoire nécessaire

  StaticJsonDocument<200> filter;
filter["chargerBatt"] = true;
filter["activateMode"]["onDevice"] = true;
filter["activeSource"] = true;
filter["lcd"] = true;


  // --- 4. Document JSON avec capacité adaptée ---

  DynamicJsonDocument doc(4096);



  // --- 5. Parsing direct depuis le payload (sans String) ---

  DeserializationError error = deserializeJson(doc, payload, length, DeserializationOption::Filter(filter));



  if (error) {

    Serial.print("❌ Erreur de parsing JSON : ");

    Serial.println(error.f_str());
    return;
  }



  Serial.println("✅ JSON parsé avec succès !");



  // --- 6. Extraction des données ---
  resetAllLeds();

  JsonObject activateMode = doc["activateMode"];
  if (!activateMode.isNull()) {
    JsonArray onDevice = activateMode["onDevice"];
    if (!onDevice.isNull()) {
      Serial.println("   📋 Liste 'onDevice' reçue :");
      setDevicesFromList(onDevice);
    }
  }

  JsonVariant activeSource = doc["activeSource"];
  if (!activeSource.isNull()) {
    if (activeSource.is<JsonArray>()) {
      JsonArray sources = activeSource.as<JsonArray>();
      setSourcesFromList(sources);
    } else {
      String source = activeSource.as<String>();
      setSourceLedByName(source, true);
      Serial.print("   🔌 Source active : ");
      Serial.println(source);
    }
  }

  bool chargerBatt = doc["chargerBatt"] | false;
  digitalWrite(chargingLedPin, chargerBatt ? HIGH : LOW);
  Serial.print("   🔋 chargerBatt = ");
  Serial.println(chargerBatt ? "true" : "false");

  JsonVariant lcdValue = doc["lcd"];

  updateLcdFromPayload(lcdValue);

}



// ------------------------------------------------------------

// Reconnexion MQTT non bloquante (déjà bonne)

// ------------------------------------------------------------

void reconnectMQTT() {

  while (!client.connected()) {

    Serial.print("🔌 Connexion MQTT...");

    String clientId = "ESP32-" + String(random(0xffff), HEX);

    if (client.connect(clientId.c_str())) {

      Serial.println("✅ Connecté");

      if (client.subscribe(mqtt_topic)) {

        Serial.print("📡 Abonné à ");

        Serial.println(mqtt_topic);

      }

    } else {

      Serial.print("❌ Échec, code ");

      Serial.print(client.state());

      Serial.println(" - nouvel essai dans 5s");

      delay(5000); // Seul délai acceptable (hors loop)

    }

  }

}



// ------------------------------------------------------------

// SETUP

// ------------------------------------------------------------

void setup() {
  // Initialisation des broches
  int pins[] = {devicePins[0], devicePins[1], devicePins[2], devicePins[3],
                devicePins[4], devicePins[5], devicePins[6], sourceSolarPin,
                sourceBattPin, sourceSbeePin, chargingLedPin};

  for (int i = 0; i < 11; i++) {
    pinMode(pins[i], OUTPUT);
    digitalWrite(pins[i], LOW);
  }
  pinMode(buttonPin, INPUT_PULLUP);

  Serial.begin(115200);
  lcd.begin(16, 2);
  updateLcdDisplay();
  delay(100);



  // Connexion Wi-Fi

  Serial.print("📶 Wi-Fi");

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);

    Serial.print(".");

  }

  Serial.println(" ✅ Connecté ! IP : " + WiFi.localIP().toString());



  // Configuration MQTT

  client.setServer(mqtt_broker, mqtt_port);

  client.setCallback(callback);

  client.setKeepAlive(60);

  reconnectMQTT();

}



// ------------------------------------------------------------

// LOOP (non bloquant)

// ------------------------------------------------------------

void loop() {
  // Vérifier et maintenir la connexion MQTT
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();

  int buttonState = digitalRead(buttonPin);
  if (buttonState != lastButtonState) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (buttonState == LOW && lastButtonState == HIGH) {
      displayFirstPage = !displayFirstPage;
      updateLcdDisplay();
    }
  }
  lastButtonState = buttonState;

  // Publication périodique d'un ping (non bloquant)
  unsigned long now = millis();
  if (now - lastPublish >= publishInterval) {
    lastPublish = now;
    if (client.publish(mqtt_topic, "ping depuis ESP32")) {
      Serial.println("📤 Ping envoyé");
    } else {
      Serial.println("❌ Échec envoi ping");
    }
  }
}