/******************* Imports **********************/
#include <Arduino.h>
#include <Wire.h>
#include "Adafruit_SHT31.h"
#include <String.h>

/************ Globalne spremenljivke ***************/
float temperatura1;
float temperatura2;
float temperatura3;
float temperatura4;
float vlaga1;
float vlaga2;
float vlaga3;
float vlaga4;

Adafruit_SHT31 sht31 = Adafruit_SHT31();

String fermentation_state = "stop";

bool on_fan0 = false;           //initial state = false
bool on_fan1 = false;           //initial state = false
bool on_fan2 = false;           //initial state = false
bool on_fan3 = false;           //initial state = false
bool on_heater = false;         //initial state = false
bool on_humidity = false;       //initial state = false

float zel_temp = 20;            //[°C], default: 20°C
float histereza_temp = 2;       //[°C], default: 2°C
float zelena_vlaga = 40;        //[%],  default: 40%
float histereza_vlaga = 5;      //[%],  default: 5%

bool system_on_off = false;     //vklop/izklop razvrščevalnika
bool system_on_pause = false;   //default: true. True = sistem ni pavziran
bool system_on_resume = true;
float ferment_time = 0;         //čas poteka fermentacije
uint32_t zacetna_ferment = 0;
uint32_t trenutna_ferment = 0;
uint32_t ciljni_cas;
uint32_t time_left = 0;

/****************** Makroti **********************/
#define MAIN_ADDRESS LOW        //Nivo pina za glavni naslov pri i2c
#define SIDE_ADDRESS HIGH       //Nivo pina za pomožni naslov pri i2c
#define FANS_PIN_PWM 11
#define FANS_PIN 10             //Številka digitalnega pina za rele ventilatorjev
#define HEATER_PIN 9            //Številka digitalnega pina za rele grelec
#define HUMIDITY_PIN 8          //Številka digitalnega pina za rele vlažilec


/************************************************/

void setup() {
  uint16_t rezina = 100;
  uint16_t st_opravil = 10;

  if(rtos_init(rezina,st_opravil) != 0){
    Serial.println("info|Rtos init failed");
    while(true);
  }
   //Serial.println("Starting");
  if(rtos_start(0,rezina, st_opravil) != 0){
    Serial.println("info|Run time error");
  }
}

void loop() {
  // Only suckers use loop()
}


uint8_t rtos_init(uint16_t time_slice, uint16_t st_opravil){
  Serial.begin(9600);
  Serial.println("info|Initializing scheduler");
  if(rtos_start(1, time_slice, st_opravil) != 0){
    Serial.println("info|RtOS fail");
    return 1;
  }
  if(temp_humid(time_slice*st_opravil,2000,1,0) != 0){
    Serial.println("info|RtOS fail");
    return 1;
  }
  if(serial_comunication(time_slice*st_opravil,2000,1,0) != 0){
    Serial.println("info|Serial fail");
    return 1;
  }
  if(serial_read(time_slice*st_opravil,2000,1,0) != 0){
    Serial.println("info|Serial read fail");
    return 1;
  }
  if(on_condition_setup(time_slice*st_opravil,2000,1,0) != 0){
    Serial.println("info|on_condition fail");
    return 1;
  }
  if(fans(time_slice*st_opravil,2000,1,0,false) != 0){
    Serial.println("info|fans fail");
    return 1;
  }
  if(heater(time_slice*st_opravil,2000,1,0,false) != 0){
    Serial.println("info|heater fail");
    return 1;
  }
  if(humidity(time_slice*st_opravil,2000,1,0,false) != 0){
    Serial.println("info|humidity fail");
    return 1;
  }
  if(stej_cas(time_slice*st_opravil,1000, 1, 0) != 0){
    Serial.println("info|RtOS fail");
    return 1;
  }
  Serial.println("info|Initialization completed");
  Serial.println("info|Starting scheduler");
  return 0;
}

uint8_t rtos_start(uint8_t init_s, uint16_t time_slice_lenght, uint16_t st_opravil){
  if(init_s != 0){

   return 0;
  }else{
    unsigned long stari_cas = 0;
    uint32_t interval = 0;
    uint16_t flags = 0x0000;
    while(true){

      interval = millis() - stari_cas;
      if(interval<0) stari_cas=millis();
      if((interval >= time_slice_lenght)&&(interval < 3*time_slice_lenght)){
        if(!(flags & 0x0001)){
          temp_humid(time_slice_lenght*st_opravil,1000,0,0);
          flags = flags | 0x0001;
        }
      }
      if((interval >= 3*time_slice_lenght)&&(interval < 4*time_slice_lenght)){
        if(!((flags>>1) & 0x0001)){
          serial_comunication(time_slice_lenght*st_opravil,2000,0,0);
          flags = flags | 0x0002;
        }
      }
      if((interval >= 4*time_slice_lenght)&&(interval < 5*time_slice_lenght)){
        if(!((flags>>2) & 0x0001)){
          fans(time_slice_lenght*st_opravil,1000,0,0,on_fan0);
          flags = flags | 0x0004;
        }
      }
      if((interval >= 5*time_slice_lenght)&&(interval < 6*time_slice_lenght)){
        if(!((flags>>3) & 0x0001)){
          heater(time_slice_lenght*st_opravil,2000,0,0,on_heater);
          flags = flags | 0x0008;
        }
      }
      if((interval >= 6*time_slice_lenght)&&(interval < 7*time_slice_lenght)){
        if(!((flags>>4) & 0x0001)){
          humidity(time_slice_lenght*st_opravil,2000,0,0,on_humidity);
          flags = flags | 0x0010;
        }
      }
      if((interval >= 7*time_slice_lenght)&&(interval < 8*time_slice_lenght)){
        if(!((flags>>5) & 0x0001)){
          on_condition_setup(time_slice_lenght*st_opravil,2000,0,0);
          flags = flags | 0x0020;
        }
      }
      if((interval >= 8*time_slice_lenght)&&(interval < 9*time_slice_lenght)){
        if(!((flags>>6) & 0x0001)){
          serial_read(time_slice_lenght*st_opravil,2000,0,0);
          flags = flags | 0x0040;
        }
      }
      if(interval >= 9*time_slice_lenght){
        if(!((flags>>7) & 0x0001)){
          stej_cas(time_slice_lenght*st_opravil,1000, 0, 0);
          flags = flags | 0x0080;
        }
      }


      if(flags == 0x00FF){
        stari_cas = millis();
        flags = 0;
      }
    }
  }
}


/********** OPRAVILA **********/
uint8_t temp_humid(uint16_t cikel_ms, uint32_t perioda_ms, uint8_t init_s, uint8_t zacetni_pogoj){

  static uint32_t stevec_cilj;
  static uint32_t stevec;

  if(init_s == 1){
    if(perioda_ms<cikel_ms){
      return 1;
    }
    stevec_cilj = perioda_ms/cikel_ms;
    stevec = zacetni_pogoj * stevec_cilj;

    //inicializacija hardwera
    for(int i=4;i<=7;i++){
      pinMode(i,OUTPUT);
    }
    sht31.begin(0x44);

    return 0;

  }else{
      if(stevec >= stevec_cilj){
        //izvedi opravilo
        for(int i=1;i<=4;i++){
          switch(i){
            case 1:
              digitalWrite(4,MAIN_ADDRESS);
              digitalWrite(5,SIDE_ADDRESS);
              digitalWrite(6,SIDE_ADDRESS);
              digitalWrite(7,SIDE_ADDRESS);
              temperatura1 = sht31.readTemperature();
              vlaga1 = sht31.readHumidity();
              break;
            case 2:
              digitalWrite(4,SIDE_ADDRESS);
              digitalWrite(5,MAIN_ADDRESS);
              digitalWrite(6,SIDE_ADDRESS);
              digitalWrite(7,SIDE_ADDRESS);
              temperatura2 = sht31.readTemperature();
              vlaga2 = sht31.readHumidity();
              break;
            case 3:
              digitalWrite(4,SIDE_ADDRESS);
              digitalWrite(5,SIDE_ADDRESS);
              digitalWrite(6,MAIN_ADDRESS);
              digitalWrite(7,SIDE_ADDRESS);
              temperatura3 = sht31.readTemperature();
              vlaga3 = sht31.readHumidity();
              break;
            case 4:
              digitalWrite(4,SIDE_ADDRESS);
              digitalWrite(5,SIDE_ADDRESS);
              digitalWrite(6,SIDE_ADDRESS);
              digitalWrite(7,MAIN_ADDRESS);
              temperatura4 = sht31.readTemperature();
              vlaga4 = sht31.readHumidity();
              break;
            default:
              return 1;
              break;
          }
        }
        stevec = 0;
      }else{
        stevec++;
      }
  }
}


uint8_t serial_comunication(uint16_t cikel_ms, uint32_t perioda_ms, uint8_t init_s, uint8_t zacetni_pogoj){

  static uint32_t stevec_cilj;
  static uint32_t stevec;
    String data = "data|";
    String temp0 = "t0|";
    String temp1 = "t1|";
    String temp2 = "t2|";
    String temp3 = "t3|";
    String hum0 = "h0|";
    String hum1 = "h1|";
    String hum2 = "h2|";
    String hum3 = "h3|";
    String fan0 = "f0|";
    String fan1 = "f1|";
    String fan2 = "f2|";
    String fan3 = "f3|";
    String heat0 = "he0|";
    String moist0 = "mo0|";
    String timeLeft = "tl|";
    String t_hyst = "tH|";
    String h_hyst = "hH|";
    String t_target = "tT|";
    String h_target = "hT|";
    String state = "st|";
    String sep = "|";

  if(init_s == 1){
    if(perioda_ms<cikel_ms){
      return 1;
    }
    stevec_cilj = perioda_ms/cikel_ms;
    stevec = zacetni_pogoj * stevec_cilj;



    return 0;

  }else{
      if(stevec >= stevec_cilj){
        //izvedi opravilo
        String sporocilo = String(data +temp0+temperatura1+sep
                                  +temp1+temperatura2+sep
                                  +temp2+temperatura3+sep
                                  +temp3+temperatura4+sep
                                  +hum0+vlaga1+sep
                                  +hum1+vlaga2+sep
                                  +hum2+vlaga3+sep
                                  +hum3+vlaga4+sep
                                  +fan0+on_fan0+sep
                                  +fan1+on_fan1+sep
                                  +fan2+on_fan2+sep
                                  +fan3+on_fan3+sep
                                  +heat0+on_heater+sep
                                  +moist0+on_humidity+sep
                                  +timeLeft+time_left+sep
                                  +t_hyst+histereza_temp+sep
                                  +h_hyst+histereza_vlaga+sep
                                  +t_target+zel_temp+sep
                                  +h_target+zelena_vlaga+sep
                                  +state+fermentation_state);

          Serial.println(sporocilo);
        stevec = 0;
      }else{
        stevec++;
      }
  }
}

uint8_t serial_read(uint16_t cikel_ms, uint32_t perioda_ms, uint8_t init_s, uint8_t zacetni_pogoj){

  static uint32_t stevec_cilj;
  static uint32_t stevec;
  String sep = "|";

  if(init_s == 1){
    if(perioda_ms<cikel_ms){
      return 1;
    }
    stevec_cilj = perioda_ms/cikel_ms;
    stevec = zacetni_pogoj * stevec_cilj;

    return 0;

  }else{
    if(stevec >= stevec_cilj){
      String parametri = Serial.readString();
      if(parametri != NULL){
        /*Head parsing*/
        String head = parametri.substring(0,parametri.indexOf(sep));

        /*Parameters parsing*/
        if(parametri.indexOf(sep)!= -1){
          int star_poz = parametri.indexOf(sep);
          int nov_poz = parametri.indexOf(sep,parametri.indexOf(sep)+1);
          String temp_string1 = "none", temp_string2 = "none";
          int i = 0;
          while(star_poz != -1){
            temp_string1 = parametri.substring(star_poz+1,nov_poz);
            star_poz = nov_poz;
            nov_poz = parametri.indexOf(sep,star_poz+1);

            if(i == 0){
              temp_string2 = temp_string1;
              i++;
            }else{
              assign_values(temp_string2, temp_string1, head);
              i--;
            }
          }
        }else{
          assign_values("none", "none", head);
        }
        Serial.println("info|done");
    }
      stevec = 0;
    }else{
      stevec++;
    }
  }
}

uint8_t on_condition_setup(uint16_t cikel_ms, uint32_t perioda_ms, uint8_t init_s, uint8_t zacetni_pogoj){

  static uint32_t stevec_cilj;
  static uint32_t stevec;
  static float povprecna_temperatura, trenutna_meja_T, zgornja_meja_T, spodnja_meja_T;
  static float povprecna_vlaga, trenutna_meja_V, zgornja_meja_V, spodnja_meja_V;

  if(init_s == 1){
    if(perioda_ms<cikel_ms){
      return 1;
    }
    stevec_cilj = perioda_ms/cikel_ms;
    stevec = zacetni_pogoj * stevec_cilj;

    /*Parametri temperaturne histereze*/
    zgornja_meja_T = zel_temp+histereza_temp;
    spodnja_meja_T = zel_temp-histereza_temp;
    trenutna_meja_T = spodnja_meja_T;

    /*Parametri vlažnostne histereze*/
    zgornja_meja_V = zelena_vlaga+histereza_vlaga;
    spodnja_meja_V = zelena_vlaga-histereza_vlaga;
    trenutna_meja_V = spodnja_meja_V;

    return 0;

  }else{
    if(system_on_off==true){
      if(stevec >= stevec_cilj){

        /*Parametri temperaturne histereze*/
        zgornja_meja_T = zel_temp+histereza_temp;
        spodnja_meja_T = zel_temp-histereza_temp;

        /*Parametri vlažnostne histereze*/
        zgornja_meja_V = zelena_vlaga+histereza_vlaga;
        spodnja_meja_V = zelena_vlaga-histereza_vlaga;

        /*Histereza temperature*/
        if (isnan(temperatura1)) {
          povprecna_temperatura = (temperatura2+temperatura3+temperatura4)/3.0;
        }else if (isnan(temperatura2)){
          povprecna_temperatura = (temperatura1+temperatura3+temperatura4)/3.0;
        }else if (isnan(temperatura3)){
          povprecna_temperatura = (temperatura1+temperatura2+temperatura4)/3.0;
        }else if (isnan(temperatura4)){
          povprecna_temperatura = (temperatura1+temperatura2+temperatura3)/3.0;
        }else{
          povprecna_temperatura = (temperatura1+temperatura2+temperatura3+temperatura4)/4.0;
        }
        
        if(povprecna_temperatura < trenutna_meja_T){
          trenutna_meja_T = zgornja_meja_T;
          on_heater = true;
        }else{
          trenutna_meja_T = spodnja_meja_T;
          on_heater = false;
        }

        /*Histereza vlage*/
        if (isnan(vlaga1)) {
          povprecna_vlaga = (vlaga2+vlaga3+vlaga4)/3.0;
        }else if (isnan(vlaga2)){
          povprecna_vlaga = (vlaga1+vlaga3+vlaga4)/3.0;
        }else if (isnan(vlaga3)){
          povprecna_vlaga = (vlaga1+vlaga2+vlaga4)/3.0;
        }else if (isnan(vlaga4)){
          povprecna_vlaga = (vlaga1+vlaga2+vlaga3)/3.0;
        }else{
          povprecna_vlaga = (vlaga1+vlaga2+vlaga3+vlaga4)/4.0;
        }
        
        if(povprecna_vlaga < trenutna_meja_V){
          trenutna_meja_V = zgornja_meja_V;
          on_humidity = true;
        }else{
          trenutna_meja_V = spodnja_meja_V;
          on_humidity = false;
        }

        if (on_heater){
          on_fan0 = true;
          on_fan1 = true;
          on_fan2 = true;
          on_fan3 = true;
        }else{
          on_fan0 = false;
          on_fan1 = false;
          on_fan2 = false;
          on_fan3 = false;
        }

        stevec = 0;
      }else{
        stevec++;
      }
    }
  }
}

uint8_t fans(uint16_t cikel_ms, uint32_t perioda_ms, uint8_t init_s, uint8_t zacetni_pogoj, bool on_condition){

  static uint32_t stevec_cilj;
  static uint32_t stevec;

  if(init_s == 1){
    if(perioda_ms<cikel_ms){
      return 1;
    }
    stevec_cilj = perioda_ms/cikel_ms;
    stevec = zacetni_pogoj * stevec_cilj;

    pinMode(FANS_PIN,OUTPUT);
    pinMode(FANS_PIN_PWM,OUTPUT);
    analogWrite(FANS_PIN_PWM, 255);
    digitalWrite(FANS_PIN, HIGH);
    return 0;

  }else{
    if(system_on_off==true){
      if(stevec >= stevec_cilj){
        /*Rele bo vklopil ventilatorje, ko bo on_condition == true*/
        if(on_condition == true){
          analogWrite(FANS_PIN_PWM, 0);
        }else{
          //digitalWrite(FANS_PIN, LOW);
          analogWrite(FANS_PIN_PWM, 170);
        }
        stevec = 0;
      }else{
        stevec++;
      }
    }
  }
}

uint8_t heater(uint16_t cikel_ms, uint32_t perioda_ms, uint8_t init_s, uint8_t zacetni_pogoj, bool on_condition){

  static uint32_t stevec_cilj;
  static uint32_t stevec;

  if(init_s == 1){
    if(perioda_ms<cikel_ms){
      return 1;
    }
    stevec_cilj = perioda_ms/cikel_ms;
    stevec = zacetni_pogoj * stevec_cilj;

    pinMode(HEATER_PIN,OUTPUT);
    return 0;

  }else{
    if(system_on_off==true){
      if(stevec >= stevec_cilj){
        /*Rele bo vklopil grelec, ko bo on_condition == true*/
        if(on_condition == true){
          digitalWrite(HEATER_PIN, HIGH);
        }else{
          digitalWrite(HEATER_PIN, LOW);
        }

        stevec = 0;
      }else{
        stevec++;
      }
    }
  }
}

uint8_t humidity(uint16_t cikel_ms, uint32_t perioda_ms, uint8_t init_s, uint8_t zacetni_pogoj, bool on_condition){

  static uint32_t stevec_cilj;
  static uint32_t stevec;

  if(init_s == 1){
    if(perioda_ms<cikel_ms){
      return 1;
    }
    stevec_cilj = perioda_ms/cikel_ms;
    stevec = zacetni_pogoj * stevec_cilj;

    pinMode(HUMIDITY_PIN,OUTPUT);
    return 0;

  }else{
    if(system_on_off==true){
      if(stevec >= stevec_cilj){
        /*Rele bo vklopil vlažilec, ko bo on_condition == true*/
        if(on_condition == true){
          digitalWrite(HUMIDITY_PIN, HIGH);
        }else{
          digitalWrite(HUMIDITY_PIN, LOW);
        }

        stevec = 0;
      }else{
        stevec++;
      }
    }
  }
}


uint8_t stej_cas(uint16_t cikel_ms, uint32_t perioda_ms, uint8_t init_s, uint8_t zacetni_pogoj){
  /*Kliči enkrat na cikel*/

  static uint32_t stevec_cilj;
  static uint32_t stevec;
  static uint32_t cas_fermentacije_ms;

  if(init_s == 1){
    if(perioda_ms<cikel_ms){
      return 1;
    }
    stevec_cilj = perioda_ms/cikel_ms;
    stevec = zacetni_pogoj * stevec_cilj;


    return 0;

  }else{
    if(system_on_off==true){
      if(stevec >= stevec_cilj){
        cas_fermentacije_ms = ferment_time*60*1000;
        ciljni_cas = cas_fermentacije_ms+zacetna_ferment;

        time_left = (ciljni_cas - millis())/1000;
        if(millis()>=ciljni_cas){
          ciljni_cas = 0;
          Serial.println("info|Time is up. Fermentation stopped.");
          assign_values("", "", "stop\n");
        }


        stevec = 0;
      }else{
        stevec++;
      }
    }
  }
}




/*Splošne funkcije*/
int assign_values(String oznaka, String vrednost, String head){
  String temp = "";
  if (head == "params"){
    temp = temp + "info|Parameter updated: "+oznaka+" = "+vrednost;
    if(oznaka == "temp_tar"){
      zel_temp = vrednost.toFloat();
    }
    if(oznaka == "temp_hys"){
      histereza_temp = vrednost.toFloat();
    }
    if(oznaka == "hum_tar"){
      zelena_vlaga = vrednost.toFloat();
    }
    if(oznaka == "hum_hys"){
      histereza_vlaga = vrednost.toFloat();
    }
  }
  if(head == "stop\n"){
    fermentation_state = "stop";
    temp = temp + "info|Stop state assigned";
    ferment_time = 0.0;
    time_left = 0.0;

    system_on_off = false;
    izklp_sistema();
  }
  if(head == "start"){
    fermentation_state = "start";
    temp = temp + "info|Start state assigned";
    if(oznaka == "time"){
      ferment_time = vrednost.toFloat();
      zacetna_ferment = millis();
      temp = temp + " for [min] " + vrednost;
    }
    system_on_off = true;
  }
  if(head == "pause\n"){
    fermentation_state = "pause";
    temp = temp + "info|Pause state assigned";
    trenutna_ferment = ciljni_cas - millis();
    system_on_off = false;
    izklp_sistema();
  }
  if(head == "resume\n"){
    fermentation_state = "start";
    temp = temp + "info|Resume state assigned";
    ferment_time = ((trenutna_ferment)/1000.0)/60.0;
    zacetna_ferment = millis();
    system_on_off = true;
  }

   Serial.println(temp);
  return 0;
}

void izklp_sistema(){
  digitalWrite(HUMIDITY_PIN, LOW);
  digitalWrite(FANS_PIN, LOW);
  digitalWrite(HEATER_PIN, LOW);
}
