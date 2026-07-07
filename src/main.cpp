// ============================================================
// 1. AUGMENTER LA TAILLE MAX DES PAQUETS MQTT (AVANT l'include)
// ============================================================
#define MQTT_MAX_PACKET_SIZE 2048   // 2 Ko

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <LiquidCrystal_I2C.h>

// ========== CONFIGURATION ==========

// --- Wi-Fi ---
//const char* ssid = "Wokwi-GUEST"; //M022_052F ou Wokwi-GUEST
//const char* password = ""; //33106705

const char* ssid = "M022_052F";
const char* password = "33106705"; 

// --- Broker MQTT ---
const char* mqtt_broker = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* mqtt_topic = "esp32tfecarmelfiacre/command";

// --- Broches des LEDs ---
const int devicePins[7] = {4, 26, 21, 19, 18, 16, 17};
const int sourceSolarPin = 33;
const int sourceBattPin = 32;
const int sourceSbeePin = 27;
const int chargingLedPin = 2;

// ============================================================
// LCD I2C (SDA=GPIO23, SCL=GPIO25)
// ============================================================
#define LCD_I2C_ADDR 0x27
LiquidCrystal_I2C lcd(LCD_I2C_ADDR, 16, 2);
// ============================================================

// Bouton poussoir
const int buttonPin = 22;
int lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

bool displayFirstPage = true;

// ------------------------------------------------------------
// ÉTATS GLOBAUX (pour éviter les clignotements)
// ------------------------------------------------------------
bool deviceStates[7] = {false};    // état des 7 LEDs d'appareils
bool sourceStates[3] = {false};    // [0]solar, [1]batt, [2]sbee
bool chargingState = false;

// Dernières valeurs affichées sur le LCD (pour comparaison)
int lastBattPercent = -1;
String lastMode = "";
float lastProduction = -1.0;
float lastConsumption = -1.0;

// ===================================
WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastPublish = 0;
const long publishInterval = 10000;

// ------------------------------------------------------------
// Fonctions de mise à jour sans clignotement
// ------------------------------------------------------------

// Met à jour une LED d'appareil uniquement si son état change
void setDeviceState(int id, bool state) {
  if (id < 0 || id >= 7) return;
  if (deviceStates[id] != state) {
    digitalWrite(devicePins[id], state ? HIGH : LOW);
    deviceStates[id] = state;
  }
}

// Met à jour une source uniquement si son état change
void setSourceState(int idx, bool state) {
  if (idx < 0 || idx >= 3) return;
  if (sourceStates[idx] != state) {
    int pin;
    switch(idx) {
      case 0: pin = sourceSolarPin; break;
      case 1: pin = sourceBattPin; break;
      case 2: pin = sourceSbeePin; break;
    }
    digitalWrite(pin, state ? HIGH : LOW);
    sourceStates[idx] = state;
  }
}

// Met à jour le voyant de charge uniquement si changement
void setChargingState(bool state) {
  if (chargingState != state) {
    digitalWrite(chargingLedPin, state ? HIGH : LOW);
    chargingState = state;
  }
}

// Convertit un nom d'appareil en ID (0..6)
int deviceNameToId(const String& name) {
  String n = name;
  n.trim();
  n.toLowerCase();
  if (n == "chauffe-eau") return 0;
  if (n == "climatisation chambre") return 1;
  if (n == "climatisation salon") return 2;
  if (n == "congelateur") return 3;
  if (n == "machine à laver" || n == "machine a laver") return 4;
  if (n == "micro-ondes" || n == "micro ondes") return 5;
  if (n == "réfrigérateur" || n == "refrigerateur") return 6;
  return -1;
}

// Convertit un nom de source en index (0..2)
int sourceNameToIndex(const String& name) {
  String s = name;
  s.trim();
  s.toLowerCase();
  s.replace(" ", "");
  s.replace("-", "");
  s.replace("_", "");
  if (s == "solarpannel" || s == "panneausolaire" || s == "solar") return 0;
  if (s == "batt" || s == "battery" || s == "batterie") return 1;
  if (s == "sbee" || s == "sourcesecours") return 2;
  return -1;
}

// ------------------------------------------------------------
// Mise à jour de l'écran LCD (seulement si changement)
// ------------------------------------------------------------
void updateLcdIfNeeded(int battPercent, const String& mode, float prod, float cons,bool change = false) {
  bool changed = change;
  if (battPercent != lastBattPercent) { lastBattPercent = battPercent; changed = true; }
  if (mode != lastMode) { lastMode = mode; changed = true; }
  if (prod != lastProduction) { lastProduction = prod; changed = true; }
  if (cons != lastConsumption) { lastConsumption = cons; changed = true; }

  if (!changed) return;  // rien de nouveau → on ne rafraîchit pas

  lcd.clear();
  if (displayFirstPage) {
    Serial.print("Affichage page 1");
    lcd.setCursor(0, 0);
    lcd.print("Batt:");
    lcd.print(battPercent);
    lcd.print("%");
    lcd.setCursor(0, 1);
    lcd.print("Mode:");
    lcd.print(mode.substring(0, min((int)mode.length(), 10)));
  } else {
    Serial.print("Affichage page 2");
    lcd.setCursor(0, 0);
    lcd.print("Prod:");
    lcd.print(prod, 1);
    lcd.print("W");
    lcd.setCursor(0, 1);
    lcd.print("Conso:");
    lcd.print(cons, 1);
    lcd.print("W");
  }
}

// ------------------------------------------------------------
// CALLBACK optimisé (sans resetAllLeds)
// ------------------------------------------------------------
void callback(char* topic, byte* payload, unsigned int length) {
  // --- 1. Détection du "ping" ---

  // --- 2. Affichage du message reçu ---

  // --- 3. Filtre JSON ---
  StaticJsonDocument<200> filter;
  filter["chargerBatt"] = true;
  filter["activateMode"]["onDevice"] = true;
  filter["activeSource"] = true;
  filter["lcd"] = true;

  // --- 4. Document JSON ---
  DynamicJsonDocument doc(4096);

  // --- 5. Parsing ---
  DeserializationError error = deserializeJson(doc, payload, length, DeserializationOption::Filter(filter));

  if (error) {
    Serial.print("❌ Erreur de parsing JSON : ");
    Serial.println(error.f_str());
    return;
  }

  // --- 6. Construire les états souhaités (tous éteints par défaut) ---
  bool newDeviceStates[7] = {false};
  bool newSourceStates[3] = {false};
  bool newCharging = false;

  // --- 7. Extraire les appareils ---
  JsonObject activateMode = doc["activateMode"];
  if (!activateMode.isNull()) {
    JsonArray onDevice = activateMode["onDevice"];
    if (!onDevice.isNull()) {
      for (JsonVariant v : onDevice) {
        if (v.is<int>()) {
          int id = v.as<int>();
          if (id >= 0 && id < 7) {
            newDeviceStates[id] = true;
          }
        } else {
          String name = v.as<String>();
          int id = deviceNameToId(name);
          if (id >= 0) {
            newDeviceStates[id] = true;
          }
        }
      }
    }
  }

  // --- 8. Extraire les sources ---
  JsonVariant activeSource = doc["activeSource"];
  if (!activeSource.isNull()) {
    if (activeSource.is<JsonArray>()) {
      JsonArray sources = activeSource.as<JsonArray>();
      for (JsonVariant v : sources) {
        String name = v.as<String>();
        int idx = sourceNameToIndex(name);
        if (idx >= 0) {
          newSourceStates[idx] = true;
        }
      }
    } else {
      String name = activeSource.as<String>();
      int idx = sourceNameToIndex(name);
      if (idx >= 0) {
        newSourceStates[idx] = true;
      }
    }
  }

  // --- 9. Chargement batterie ---
  newCharging = doc["chargerBatt"] | false;

  // --- 10. Appliquer les nouveaux états (uniquement les changements) ---
  for (int i = 0; i < 7; i++) {
    setDeviceState(i, newDeviceStates[i]);
  }
  for (int i = 0; i < 3; i++) {
    setSourceState(i, newSourceStates[i]);
  }
  setChargingState(newCharging);

  // --- 11. Mise à jour de l'écran LCD (avec comparaison) ---
  JsonVariant lcdValue = doc["lcd"];
  if (!lcdValue.isNull()) {
    int batt = 0;
    String mode = "";
    float prod = 0.0, cons = 0.0;

    if (lcdValue.is<JsonArray>()) {
      JsonArray arr = lcdValue.as<JsonArray>();
      if (arr.size() >= 4) {
        batt = arr[0] | 0;
        mode = arr[1].as<String>();
        prod = arr[2] | 0.0;
        cons = arr[3] | 0.0;
      }
    } else if (lcdValue.is<JsonObject>()) {
      JsonObject obj = lcdValue.as<JsonObject>();
      batt = obj["battPercentage"] | obj["battery"] | 0;
      mode = obj["mode"].as<String>();
      prod = obj["production"] | obj["prod"] | 0.0;
      cons = obj["consumption"] | obj["cons"] | 0.0;
    }

    updateLcdIfNeeded(batt, mode, prod, cons);
  }
}

// ------------------------------------------------------------
// Reconnexion MQTT
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
      delay(5000);
    }
  }
}

// ------------------------------------------------------------
// SETUP
// ------------------------------------------------------------
void setup() {
  // Initialisation des broches LED
  int pins[] = {devicePins[0], devicePins[1], devicePins[2], devicePins[3],
                devicePins[4], devicePins[5], devicePins[6], sourceSolarPin,
                sourceBattPin, sourceSbeePin, chargingLedPin};

  for (int i = 0; i < 11; i++) {
    pinMode(pins[i], OUTPUT);
    digitalWrite(pins[i], LOW);
  }
  pinMode(buttonPin, INPUT_PULLUP);

  Serial.begin(115200);
  
  // ============================================================
  // INITIALISATION LCD I2C (SDA=GPIO23, SCL=GPIO25)
  // ============================================================
  Wire.begin(23, 25);
  lcd.init();
  lcd.backlight();
  // ============================================================
  
  // Initialiser les états globaux
  for (int i = 0; i < 7; i++) deviceStates[i] = false;
  for (int i = 0; i < 3; i++) sourceStates[i] = false;
  chargingState = false;
  lastBattPercent = -1;
  lastMode = "";
  lastProduction = -1.0;
  lastConsumption = -1.0;

  // Afficher une première page (par défaut)
  updateLcdIfNeeded(0, "Init", 0.0, 0.0);
  delay(100);

  // Connexion Wi-Fi
  Serial.print("📶 Wi-Fi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" ✅ Connecté ! IP : " + WiFi.localIP().toString());

  // ConfigurSerialation MQTT
  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(callback);
  client.setKeepAlive(60);
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
  static unsigned long lastDebounceTime = 0;
  static int lastButtonState = HIGH;
  static int currentButtonState = HIGH;

  int reading = digitalRead(buttonPin);

  if (reading != lastButtonState) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > debounceDelay) {
    // Le signal est stable
    if (reading != currentButtonState) {
      currentButtonState = reading;
      if (currentButtonState == LOW) {  // Appui détecté
        displayFirstPage = !displayFirstPage;
        updateLcdIfNeeded(lastBattPercent, lastMode, lastProduction, lastConsumption,true);
        Serial.println("🔘 Bouton pressé - page changée");
      }
    }
  }
    lastButtonState = reading;
}