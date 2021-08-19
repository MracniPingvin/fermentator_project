import numpy as np
import threading
import queue
import time
import datetime
import pickle
import serial
import csv
import os

class Fermentor():
    def __init__(self, default_temperature_target=80, default_temperature_hysteresis=5,
                 default_humidity_target=85, default_humidity_hysteresis=5, serial_port_name="COM3", serial_baud_rate=9600):
        self.params = {
            "temperature": {
                "target": {
                    "current": default_temperature_target,
                    "default": default_temperature_target,
                    "name": "temp_tar"
                },
                "hysteresis": {
                    "current": default_temperature_hysteresis,
                    "default": default_temperature_hysteresis,
                    "name": "temp_hys"
                },
            },
            "humidity": {
                "target": {
                    "current": default_humidity_target,
                    "default": default_humidity_target,
                    "name": "hum_tar"
                },
                "hysteresis": {
                    "current": default_humidity_hysteresis,
                    "default": default_humidity_hysteresis,
                    "name": "hum_hys"
                },
            },
        }
        
        self.num_devices = {
            "temperature": 4,
            "humidity": 4,
            "fan": 4,
            "heater": 1,
            "moisturizer": 1,
        }
        
        self.in_names = {
            "temperature": ["temp" + str(i) for i in range(self.num_devices["temperature"])],
            "humidity": ["hum" + str(i) for i in range(self.num_devices["humidity"])],
            "fan": ["fan" + str(i) for i in range(self.num_devices["fan"])],
            "heater": ["heat" + str(i) for i in range(self.num_devices["heater"])],
            "moisturizer": ["moist" + str(i) for i in range(self.num_devices["moisturizer"])],
            "time_left": ["timeLeft"],
            "time": ["time"]
        }
        self.in_names_reversed = {value: key for key in self.in_names for value in self.in_names[key]}
        
        self.empty_data_block = self.create_empty_data_block()
        self.parse_functions = {
            "data": self.parse_function_data,
            "info": self.parse_function_info,
            "temperature": lambda x: float(x),
            "humidity": lambda x: float(x),
            "fan": lambda x: bool(int(x)),
            "heater": lambda x: bool(int(x)),
            "moisturizer": lambda x: bool(int(x)),
            "time_left": lambda x: datetime.timedelta(minutes=int(x)),
            "time": self.parse_function_time
        }
        self.encode_functions = {
            "temperature": lambda x: x,
            "humidity": lambda x: x,
            "fan": lambda x: int(x),
            "heater": lambda x: int(x),
            "moisturizer": lambda x: int(x),
            "time_left": lambda x: x.seconds//60,
            "time": lambda x: x
        }

        self.measurements = []

        self.sender_thread = None
        self.receiver_thread = None
        self.io_thread = None
        self.io_active = False
        self.receiver_serial = None
        self.count = 0
        self.parse_queue = queue.Queue()
        self.send_queue = queue.Queue()
        self.data_lock = threading.Lock()
        self.database_path = "data/data.csv"
        self.load_database(self.database_path)
        self.init_io()

    def create_empty_data_block(self):
        data_block = {}
        data_block["time"] = datetime.datetime.min
        for i in self.in_names["temperature"]:
            data_block[i] = 0.0
        for i in self.in_names["humidity"]:
            data_block[i] = 0.0
        for i in self.in_names["fan"]:
            data_block[i] = False
        for i in self.in_names["heater"]:
            data_block[i] = False
        for i in self.in_names["moisturizer"]:
            data_block[i] = False
        data_block[self.in_names["time_left"][0]] = datetime.timedelta(minutes=0)
        return data_block

    def update_parameters(self, temperature_target=None, humidity_target=None,
                          temperature_hysteresis=None, humidity_hysteresis=None):
        if temperature_target is not None:
            self.params["temperature"]["target"]["current"] = temperature_target
        if humidity_target is not None:
            self.params["humidity"]["target"]["current"] = humidity_target
        if temperature_hysteresis is not None:
            self.params["temperature"]["hysteresis"]["current"] = temperature_hysteresis
        if humidity_hysteresis is not None:
            self.params["humidity"]["hysteresis"]["current"] = humidity_hysteresis

    def get_parameter_string(self):
        head = "params"
        body = ""
        for i in [self.params["temperature"]["target"],
                  self.params["temperature"]["hysteresis"],
                  self.params["humidity"]["target"],
                  self.params["humidity"]["hysteresis"]]:
            body = "{}|{}|{:.2f}".format(body, i["name"], i["current"])
        return head+body
        
    def init_io(self):
        self.io_thread = threading.Thread(target=self.io_function, daemon=True)
        self.io_thread.start()
    
    def io_function(self):
        self.init_serial("COM3", 9600)
        self.init_parser()
        self.init_sender()
        self.init_receiver()
        while(1):
            time.sleep(5)
            if not self.io_active:
                self.close_serial()
                self.init_io()
                break
                
    def init_serial(self, serial_port_name, serial_baud_rate):
        while(1):
            try:
                self.receiver_serial = serial.Serial(port=serial_port_name, baudrate=serial_baud_rate)
                print("Serial port " + serial_port_name + " opened | baud_rate: " + str(serial_baud_rate))
                self.receiver_serial.flush()
                self.io_active = True
                break
            except Exception as e:
                print("can't connect to serial: exception=", e)
            time.sleep(2)
            
    def close_serial(self):
        self.receiver_serial.close()
        
    def init_receiver(self):
        self.receiver_thread = threading.Thread(target=self.receiver_function, daemon=True)
        self.receiver_thread.start()
        print("receiver_thread_started")

    def init_parser(self):
        self.parser_thread = threading.Thread(target=self.parser_function, daemon=True)
        self.parser_thread.start()
        print("parser_thread_started")

    def init_sender(self):
        self.sender_thread = threading.Thread(target=self.sender_function, daemon=True)
        self.sender_thread.start()
        print("sender_thread_started")

    def receiver_function(self):
        try:
            while(self.io_active):
                if self.receiver_serial.in_waiting > 0:
                    line = self.receiver_serial.readline().decode('utf-8').rstrip()
                else:
                    line = None
                #line = self.generate_fake_message()
                if line is not None:
                    self.parse_queue.put(line)
                    print("received: ", line)
        except Exception as e:
            print("receiver error", e)
            self.io_active = False

    def parser_function(self):
        try:
            while(self.io_active):
                try:
                    data = self.parse_queue.get()
                except queue.Empty:
                    data = None
                    print("KAOOOS")
                message_list = data.split('|')
                head = message_list.pop(0)
                try:
                    parsed = self.parse_functions[head](message_list)
                except KeyError:
                    print("KEY ERROR: head=", head)
                #print("parsed: ", parsed)
        except Exception as e:
            print("parser_error", e)
            self.io_active = False
            raise e

    def sender_function(self):
        try:
            while(self.io_active):
                try:
                    data = self.send_queue.get()
                    self.receiver_serial.write(bytes(data, 'utf-8'))
                except queue.Empty:
                    data = None
                    print("KAOOOS")
                print("sent: ", data)
        except Exception as e:
            print("sender error", e)
            self.io_active = False

    def generate_fake_message(self):
        temperature_string = ""
        for i in range(self.num_devices["temperature"]):
            foo = np.random.uniform(50, 90)
            temperature_string += "|{}|{:.2f}".format(self.in_names["temperature"][i], foo)
        humidity_string = ""
        for i in range(self.num_devices["humidity"]):
            foo = np.random.uniform(70, 100)
            humidity_string += "|{}|{:.2f}".format(self.in_names["humidity"][i], foo)
        fan_string = ""
        for i in range(self.num_devices["fan"]):
            foo = np.random.randint(0,2)
            fan_string += "|{}|{}".format(self.in_names["fan"][i], foo)
        heater_string = ""
        for i in range(self.num_devices["heater"]):
            foo = np.random.randint(0,2)
            heater_string += "|{}|{}".format(self.in_names["heater"][i], foo)
        moisturizer_string = ""
        for i in range(self.num_devices["moisturizer"]):
            foo = np.random.randint(0,2)
            moisturizer_string += "|{}|{}".format(self.in_names["moisturizer"][i], foo)
        message = "data" + temperature_string + humidity_string + fan_string + heater_string + moisturizer_string
        return message

    def parse_function_data(self, message_list):
        data_block = self.empty_data_block.copy()
        data_block["time"] = datetime.datetime.utcnow()
        for i in range(0, len(message_list), 2):
            key = message_list[i]
            value = message_list[i + 1]
            found = False
            for property in ["temperature", "humidity", "fan", "heater", "moisturizer", "time_left"]:
                if key in self.in_names[property]:
                    data_block[key] = self.parse_functions[property](value)
                    found = True
            if not found:
                print("UNKNOWN KEY: ", key)
        self.measurements.append(data_block)
        return data_block
        
    def parse_function_info(self, message_list):
        pass
    def parse_function_time(self, timestamp):
        t = datetime.datetime.fromisoformat(timestamp)
        return t



    def load_database(self, path):
        try:
            with open(path, "r") as f:
                reader = csv.reader(f, skipinitialspace=True)
                header = next(reader)
                for row in reader:
                    data_block = self.empty_data_block.copy()
                    for name, value in zip(header, row):
                        data_block[name] = self.parse_functions[self.in_names_reversed[name]](value)
                    self.measurements.append(data_block)
        except IOError:
            print("Database file missing")

    def update_database(self, path):
        database_exists = os.path.isfile(path)
        with open(path, 'a', encoding='utf8', newline='') as output_file:
            fc = csv.DictWriter(output_file, fieldnames=self.measurements[0].keys())
            if not database_exists:
                fc.writeheader()
            for row in self.measurements:
                fc.writerow(self.process_row_before_saving(row))

    def process_row_before_saving(self, row):
        data_block = self.empty_data_block.copy()
        for name, value in row.items():
            data_block[name] = self.encode_functions[self.in_names_reversed[name]](value)
        return data_block
