import numpy as np
import threading
import queue
import time
import datetime
import pickle
import serial
import csv
import os
import json

class Fermentor():
    def __init__(self, default_temperature_target=60, default_temperature_hysteresis=2,
                 default_humidity_target=10, default_humidity_hysteresis=1, serial_port_name="COM3",
                 serial_baud_rate=9600, simulate_serial=True):
        self.simulate_serial = simulate_serial
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
            "state": {
                "current": "stopped",
                "default": "stopped"
            },
            "time_left":  datetime.timedelta(seconds=0),
        }
        
        self.num_devices = {
            "temperature": 4,
            "humidity": 4,
            "fan": 4,
            "heater": 1,
            "moisturizer": 1,
        }
        
        self.in_names = {
            "temperature": ["t" + str(i) for i in range(self.num_devices["temperature"])],
            "humidity": ["h" + str(i) for i in range(self.num_devices["humidity"])],
            "fan": ["f" + str(i) for i in range(self.num_devices["fan"])],
            "heater": ["he" + str(i) for i in range(self.num_devices["heater"])],
            "moisturizer": ["mo" + str(i) for i in range(self.num_devices["moisturizer"])],
            "time_left": ["left"],
            "time": ["time"],
            "temperature_hysteresis": ["tHys"],
            "humidity_hysteresis": ["hHys"],
            "temperature_target": ["tTar"],
            "humidity_target": ["hTar"],
            "state": ["state"]
        }
        self.data_to_store = ["temperature", "humidity"]
        self.in_names_reversed = {value: key for key in self.in_names for value in self.in_names[key]}
        self.all_in_names = [value for key in self.in_names for value in self.in_names[key]]
        self.current_data = self.create_empty_current_data()

        self.empty_data_block = self.create_empty_data_block()
        self.parse_functions = {
            "data": self.parse_function_data,
            "info": self.parse_function_info,
            "temperature": lambda x: float(x),
            "humidity": lambda x: float(x),
            "fan": lambda x: bool(int(x)),
            "heater": lambda x: bool(int(x)),
            "moisturizer": lambda x: bool(int(x)),
            "time_left": lambda x: datetime.timedelta(seconds=int(x)),
            "time": lambda x: datetime.datetime.fromisoformat(x),
            "temperature_hysteresis": lambda x: float(x),
            "humidity_hysteresis": lambda x: float(x),
            "temperature_target": lambda x: float(x),
            "humidity_target": lambda x: float(x),
            "state": lambda x: x,
        }
        self.encode_functions = {
            "temperature": lambda x: x,
            "humidity": lambda x: x,
            "fan": lambda x: int(x),
            "heater": lambda x: int(x),
            "moisturizer": lambda x: int(x),
            "time_left": lambda x: x.seconds//60,
            "time": lambda x: x.isoformat(),
            "temperature_hysteresis": lambda x: x,
            "humidity_hysteresis": lambda x: x,
            "temperature_target": lambda x: x,
            "humidity_target": lambda x: x,
            "state": lambda x: x
        }
        self.info_functions = {
            "Initialization completed": self.initialize_arduino
        }
        self.state_functions = {
            "start": lambda x: self.start_fermentation(self.params["time_left"]),
            "pause": self.stop_fermentation,
            "stop": self.stop_fermentation
        }
        self.measurements_unsaved = []
        self.measurements = []

        self.sender_thread = None
        self.receiver_thread = None
        self.io_thread = None
        self.io_active = False
        self.receiver_serial = None
        self.measurement_unsaved_count = 0
        self.measurement_unsaved_limit = 100
        self.save_every_nth_measurement = 5
        self.parse_queue = queue.Queue()
        self.send_queue = queue.Queue()
        self.data_lock = threading.Lock()
        self.database_path = "data/data.csv"
        self.parameters_path = "data/parameters.json"
        self.load_database(self.database_path)
        self.load_parameters(self.parameters_path)
        self.init_io()

    def create_empty_data_block(self):
        data_block = {}
        data_block["time"] = datetime.datetime.min
        for i in self.in_names["temperature"]:
            data_block[i] = 0.0
        for i in self.in_names["humidity"]:
            data_block[i] = 0.0
        # for i in self.in_names["fan"]:
        #     data_block[i] = False
        # for i in self.in_names["heater"]:
        #     data_block[i] = False
        # for i in self.in_names["moisturizer"]:
        #     data_block[i] = False
        # data_block[self.in_names["time_left"][0]] = datetime.timedelta(minutes=0)
        return data_block

    def create_empty_current_data(self):
        data_block = {}
        data_block["time"] = datetime.datetime.min
        for j in ["temperature", "humidity", "temperature_hysteresis", "humidity_hysteresis", "temperature_target", "humidity_target"]:
            for i in self.in_names[j]:
                data_block[i] = 0.0
        for j in ["fan", "heater", "moisturizer"]:
            for i in self.in_names[j]:
                data_block[i] = False
        for i in self.in_names["state"]:
            data_block[i] = ""
        for i in self.in_names["time_left"]:
            data_block[i] = datetime.timedelta(minutes=0)
        for i in self.in_names["time"]:
            data_block[i] = datetime.datetime.utcnow()
        return data_block

    def update_parameters(self, temperature_target=None, humidity_target=None,
                          temperature_hysteresis=None, humidity_hysteresis=None,
                          state=None):
        try:
            temperature_target = float(temperature_target)
            temperature_hysteresis = float(temperature_hysteresis)
            humidity_target = float(humidity_target)
            humidity_hysteresis = float(humidity_hysteresis)
            if temperature_target + temperature_hysteresis > 95:
                return "TOO HOT TO HANDLE!"
            if temperature_target - temperature_hysteresis < 0:
                return "TOO COLD TO HANDLE"
            if humidity_target + humidity_hysteresis > 100:
                return "TOO HUMID TO HANDLE!"
            if humidity_target - humidity_hysteresis < 0:
                return "TOO DRY TO HANDLE"

            if temperature_target is not None:
                self.params["temperature"]["target"]["current"] = temperature_target
            if humidity_target is not None:
                self.params["humidity"]["target"]["current"] = humidity_target
            if temperature_hysteresis is not None:
                self.params["temperature"]["hysteresis"]["current"] = temperature_hysteresis
            if humidity_hysteresis is not None:
                self.params["humidity"]["hysteresis"]["current"] = humidity_hysteresis
            if state is not None:
                self.params["state"]["current"] = state
        except:
            return "INVALID PARAMETERS!"



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
        if not self.simulate_serial:
            self.init_serial("COM3", 9600)
        else:
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
            if key in self.all_in_names:
                try:
                    self.current_data[key] = self.parse_functions[self.in_names_reversed[key]](value)
                except KeyError:
                    print("KEY ERROR: ", key)
            else:
                print("UNKNOWN KEY: ", key)
        for key in self.data_to_store:
            for name in self.in_names[key]:
                data_block[name] = self.current_data[name]
        self.measurements_unsaved.append(data_block)
        self.measurement_unsaved_count += 1
        self.save_parameters(self.parameters_path)
        if self.measurement_unsaved_count == self.measurement_unsaved_limit:
            self.update_database(self.database_path, self.save_every_nth_measurement)
            self.measurement_unsaved_count = 0
        return data_block
        
    def parse_function_info(self, message_list):
        message = message_list[0]
        if message in self.info_functions.keys():
            self.info_functions[message]()

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

    def update_database(self, path, every_nth_measurement=1):
        database_exists = os.path.isfile(path)
        with open(path, 'a', encoding='utf8', newline='') as output_file:
            fc = csv.DictWriter(output_file, fieldnames=self.measurements_unsaved[0].keys())
            if not database_exists:
                fc.writeheader()
            for count, row in enumerate(self.measurements_unsaved):
                if count % every_nth_measurement == 0:
                    fc.writerow(self.process_row_before_saving(row))
                    self.measurements.append(row)
        self.measurements_unsaved = []

    def save_parameters(self, path):
        parameters_exist = os.path.isfile(path)
        data_block = {}
        for name, value in self.current_data.items():
            data_block[name] = self.encode_functions[self.in_names_reversed[name]](value)
        jsonData = json.dumps(data_block)
        with open(path, 'w', encoding='utf8') as output_file:
            output_file.write(jsonData)

    def load_parameters(self, path):
        parameters_exist = os.path.isfile(path)
        if parameters_exist:
            with open(path, 'r', encoding='utf8') as jsonData:
                decodedJson = json.load(jsonData)
            for name, value in decodedJson.items():
                self.current_data[name] = self.parse_functions[self.in_names_reversed[name]](value)
            self.update_parameters(temperature_target=self.current_data[self.in_names["temperature_target"][0]],
                                   temperature_hysteresis=self.current_data[self.in_names["temperature_hysteresis"][0]],
                                   humidity_target=self.current_data[self.in_names["humidity_target"][0]],
                                   humidity_hysteresis=self.current_data[self.in_names["humidity_hysteresis"][0]],
                                   state=self.current_data[self.in_names["state"][0]]
                                   )
        else:
            pass

    def send_parameters(self):

        message = self.get_parameter_string()
        self.send_queue.put(message)

        return "PARAMETERS UPDATED!"

    def start_fermentation(self, n_minutes):
        try:
            int_minutes = int(n_minutes)
            if int_minutes < 0 or int_minutes > 200000:
                return "Invalid fermentation time"
        except:
            return "Invalid fermentation time"
        message = "start|time|" + str(n_minutes)
        self.send_queue.put(message)

    def pause_fermentation(self, foo=None):
        message = "pause\n"
        self.send_queue.put(message)

    def stop_fermentation(self, foo=None):
        message = "stop\n"
        self.send_queue.put(message)

    def resume_fermentation(self, foo=None):
        message = "resume\n"
        self.send_queue.put(message)

    def initialize_arduino(self):
        self.send_parameters()
        self.state_functions[self.params["state"]["current"]]((self.params["time_left"].seconds//60)%60)



    def process_row_before_saving(self, row):
        data_block = self.empty_data_block.copy()
        for name, value in row.items():
            data_block[name] = self.encode_functions[self.in_names_reversed[name]](value)
        return data_block
