#   @file RigolDS7034.py
#   @brief Establishes a connection to the Rigol DS7034 Oscilloscope
#       and provides methods for interacting with the device.
#   @date 21-May-2023
#   @author Stefan Damkjar
#
#   Licensed to the Apache Software Foundation (ASF) under one
#   or more contributor license agreements.  See the NOTICE file
#   distributed with this work for additional information
#   regarding copyright ownership.  The ASF licenses this file
#   to you under the Apache License, Version 2.0 (the
#   "License"); you may not use this file except in compliance
#   with the License.  You may obtain a copy of the License at
#   
#     http://www.apache.org/licenses/LICENSE-2.0
#   
#   Unless required by applicable law or agreed to in writing,
#   software distributed under the License is distributed on an
#   "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#   KIND, either express or implied.  See the License for the
#   specific language governing permissions and limitations
#   under the License. 

# Imports
import pyvisa
import time
import numpy
import os
from colorama import init, Fore, Back, Style
from .loading import *

# Constants and global variables
_ERROR_STYLE = Fore.RED + Style.BRIGHT + "\rError! "
_WARNING_STYLE = Fore.YELLOW + Style.BRIGHT + "\rWarning! "
_SUCCESS_STYLE = Fore.GREEN + Style.BRIGHT  + "\r"
_MAX_FILENAMES = 100
_DELAY = 0.1 #seconds

class RigolDS7034:

    """
    Initializes an instance of the RigolDS7034 class.
    """
    def __init__(self, auto_connect=True):
        
        init(autoreset=True)

        self.rm = pyvisa.ResourceManager()
        self.address = None
        self.instrument = None
        self.loading = loading()
        self.screenshot_filename = None
        self.screenshot_filename_warning_given = False

        self.status = "Not Connected"
        
        if auto_connect:
            self.connect()

    """
    Establishes a connection to the Rigol DS7034 Oscilloscope.

    Raises:
        ConnectionError: If unable to connect to Rigol DS7034 Oscilloscope.
    
    Example usage:
        oscilloscope.connect()
    """
    def connect(self):

        resources = self.rm.list_resources()
        for resource in resources:
            if 'DS7' in resource:
                self.address = resource
                break

        if self.address is None:
            error_message = "Rigol DS7034 Oscilloscope not found."
            raise ConnectionError(_ERROR_STYLE + error_message)

        try:
            self.instrument = self.rm.open_resource(self.address)
            self.instrument.read_termination = '\n'
            self.status = "Connected"
            success_message = f"Connected to Rigol DS7034 Oscilloscope at {self.address}"
            print(_SUCCESS_STYLE + success_message)

        except pyvisa.Error as e:
            error_message = f"Error! Failed to connect to Rigol DS7034 Oscilloscope at {self.address}: {e}"
            raise ConnectionError(_ERROR_STYLE + error_message)

    
    """
    Disconnects from the Rigol DS7034 Oscilloscope.
    
    Example usage:
        oscilloscope.disconnect()
    """
    def disconnect(self):
        
        if self.instrument is not None:
            self.instrument.close()
            print(f"\rDisconnected from Rigol DS7034 Oscilloscope at {self.address}")
            self.status = "Not Connected"

    """
    Retrieves the specified value.
    
    Args:
        item (str): The measurement item to retrieve.
        channel (int, optional): The channel number for the measurement.
           Defaults to 1.
    
    Returns:
        The measurement result corresponding to the specified item and channel.

    Raises:
        ValueError: If an invalid item is requested.
    
    Example usage:
        measurement = oscilloscope.get("VAVG", channel=2)
        print(f"Measurement for VAVG on channel 2: {measurement}")
    """
    def get(self,item,channel=1):

        items = { "VAVG"        :self.measure_item,
                  "VMAX"        :self.measure_item,
                  "VMIN"        :self.measure_item,
                  "VAVG_STAT"   :self.measure_statistic_item,
                  "VMAX_STAT"   :self.measure_statistic_item,
                  "VPP_STAT"    :self.measure_statistic_item,
                  "PDUT_STAT"   :self.measure_statistic_item,
                  "FREQ_STAT"   :self.measure_statistic_item,
                  "RFD_STAT"    :self.measure_statistic_item,
                  "RRD_STAT"    :self.measure_statistic_item,
                  "VMIN_STAT"   :self.measure_statistic_item,
                  "PSL_STAT"    :self.measure_statistic_item,
                  "NSL_STAT"    :self.measure_statistic_item,
                  "VTOP_STAT"   :self.measure_statistic_item,
                  "VBAS_STAT"   :self.measure_statistic_item,
                  "SCREENSHOT"  :self.save_screenshot,
        }

        if item in items:
            if "_STAT" in item:
                item_x = item[:item.find("_STAT")]
                result = items[item](item_x, f'CHAN{channel}')
            elif item == "SCREENSHOT":
                result = items[item]()
            else:
                result = items[item](item, f'CHAN{channel}')
            return result
        else:
            error_message = f"Invalid item: {item} request to Rigol DS7034 oscilloscope"
            raise ValueError(_ERROR_STYLE + error_message)
        

    """
    Determines if the specified item is a valid measurement item.

    Args:
        item (str): The measurement item to check. Valid items are:
            +----------+-----------------------+    +---------+--------------------------+
            |   Item   |      Description      |    |  Item   |       Description        |
            +==========+=======================+    +=========+==========================+
            |   VMAX   | Maximum voltage       |    | RRDelay | Rising-to-rising delay   |
            |   VMIN   | Minimum voltage       |    | RFDelay | Rising-to-falling delay  |
            |   VPP    | Peak-to-peak voltage  |    | FRDelay | Falling-to-rising delay  |
            |   VTOP   | Top voltage           |    | FFDelay | Falling-to-falling delay |
            |   VBASE  | Base voltage          |    | RRPHase | Rising-to-rising phase   |
            |   VAMP   | Amplitude voltage     |    | RFPHase | Rising-to-falling phase  |
            |   VAVG   | Average voltage       |    | FRPHase | Falling-to-rising phase  |
            |   VRMS   | RMS voltage           |    | FFPHase | Falling-to-falling phase |
            +----------+-----------------------+    +---------+--------------------------+

    Returns:
        True if the item is valid, False otherwise.
    """
    def __is_valid_item(self,item):

        valid_items = ["VMAX", "VMIN", "VPP", "VTOP", "VBASE", "VAMP", "VAVG", "VRMS",
                    "OVERshoot", "PREShoot", "MARea", "MPARea", "PERiod", "FREQuency",
                    "RTIMe", "FTIMe", "PWIDth", "NWIDth", "PDUTy", "NDUTy", "TVMax",
                    "TVMin", "PSLewrate", "NSLewrate", "VUPPer", "VMID", "VLOWer",
                    "VARiance", "PVRMs", "PPULses", "NPULses", "PEDGes", "NEDGes",
                    "RRDelay", "RFDelay", "FRDelay", "FFDelay", "RRPHase", "RFPHase",
                    "FRPHase", "FFPHase"]
        
        item_upper = item.upper()
        
        # Check if the item is a valid item or its alias
        for valid_item in valid_items:
            if item_upper == valid_item.upper() or (valid_item.startswith(item_upper) and valid_item[len(item_upper)].islower() ): 
                return True

        return False

    """
    Determines if the specified source is a valid source.

    Args:
        source (str): The source to check. Valid sources are:
            +----------+-----------------------+
            |  Source  |      Description      |
            +----------+-----------------------+
            | D0       | Digital 0             |
            | D1       | Digital 1             |
            | D2       | Digital 2             |
            | ...      | ...                   |
            | D15      | Digital 15            |
            | CHANnel1 | Channel 1             |
            | CHANnel2 | Channel 2             |
            | CHANnel3 | Channel 3             |
            | CHANnel4 | Channel 4             |
            | MATH1    | Math 1                |
            | MATH2    | Math 2                |
            | MATH3    | Math 3                |
            | MATH4    | Math 4                |
            +----------+-----------------------+
    Returns:
        True if the source is valid, False otherwise.
    """
    def __is_valid_source(self, source):
        valid_sources = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9",
                        "D10", "D11", "D12", "D13", "D14", "D15", "CHANNEL1","CHAN1", "CHANNEL2","CHAN2",
                        "CHANNEL3","CHAN3", "CHANNEL4","CHAN4", "MATH1", "MATH2", "MATH3", "MATH4"]

        if source.upper() in valid_sources:
            return True
        return False        

    """
    Measures the waveform parameter of the specified source.

    Args:
        item (str): The measurement item to retrieve.
        source (str): The source to measure.

    Returns:
        The measurement result corresponding to the specified item and source.

    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
        ValueError: If an invalid item or source is requested.

    Example usage:
        voltage = oscilloscope.measure_item()
        print(f"Voltage: {voltage} V")
    """
    def measure_item(self, item, source):

        if not self.status == "Connected":
            error_message = "Not connected to Rigol DS7034 Oscilloscope."
            raise ConnectionError(_ERROR_STYLE + error_message)

        if isinstance(source, int) and 1 <= source <= 4:
            source = f"CHANnel{source}"
        
        if not self.__is_valid_item(item):
            error_message = f"Invalid item: \"{item}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        if not self.__is_valid_source(source):
            error_message = f"Invalid source: \"{source}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)


        command = f"MEASURE:ITEM? {item},{source}"
        value = self.instrument.query(command)
        self.loading.delay_with_loading_indicator(_DELAY)
        return float(value)

        
    """
    Returns the specified measurement statistics of the specified waveform parameter.

    Args:
        item (str): The measurement item to retrieve.
            source (str): The source to measure.
            types (list): The list of statistic types to retrieve. Valid statistic types are:
            +-----------+-----------------------+
            |  Type     |      Description      |
            +-----------+-----------------------+
            | MAXimum   | Maximum               |
            | MINimum   | Minimum               |
            | CURRent   | Current               |
            | AVERages  | Average               |
            | DEViation | Standard deviation    |
            +-----------+-----------------------+

    Returns:
        The measurement result corresponding to the specified item and source.

    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
        ValueError: If an invalid item, source, or statistic type is requested.
    """
    def measure_statistic_item(self, item, source, types = ["AVERages","DEViation"]):
            
            if not self.status == "Connected":
                error_message = "Not connected to Rigol DS7034 Oscilloscope."
                raise ConnectionError(_ERROR_STYLE + error_message)
            
            if isinstance(source, int) and 1 <= source <= 4:
                source = f"CHANnel{source}"
            
            if not self.__is_valid_item(item):
                error_message = f"Invalid item: \"{item}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
                raise ValueError(_ERROR_STYLE + error_message)
            
            if not self.__is_valid_source(source):
                error_message = f"Invalid source: \"{source}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
                raise ValueError(_ERROR_STYLE + error_message)


            values = []
            for type in types:
                if not type in {"MAXimum", "MINimum", "CURRent", "AVERages", "DEViation", "MAX", "MIN", "CURR", "AVER", "DEV"}:
                    error_message = f"Invalid statistic type: \"{type}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
                    raise ValueError(_ERROR_STYLE + error_message)

                command = f"MEASURE:STAT:ITEM? {type},{item},{source}"
                value = self.instrument.query(command)
                self.loading.delay_with_loading_indicator(_DELAY)
                values.append(float(value))
            return values



    """
    Enables statistics for the specified waveform parameter of the specified source.

    Args:
        item (str): The measurement item to retrieve.
        source (str): The source to measure.

    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
        ValueError: If an invalid item or source is requested.
    """
    def enable_statistic_item(self, item, source):

        if not self.status == "Connected":
            error_message = "Not connected to Rigol DS7034 Oscilloscope."
            raise ConnectionError(_ERROR_STYLE + error_message)

        if isinstance(source, int) and 1 <= source <= 4:
            source = f"CHANnel{source}"
        
        if not self.__is_valid_item(item):
            error_message = f"Invalid item: \"{item}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        if not self.__is_valid_source(source):
            error_message = f"Invalid source: \"{source}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)

        command = f"MEASURE:STAT:ITEM {item},{source}"
        self.instrument.write(command)
        self.loading.delay_with_loading_indicator(_DELAY)


    """
    Resets the statistics for all measurement items.

    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
    """
    def reset_statistics(self):

        if not self.status == "Connected":
            error_message = "Not connected to Rigol DS7034 Oscilloscope."
            raise ConnectionError(_ERROR_STYLE + error_message)

        command = "MEASURE:STAT:RESET"
        self.instrument.write(command)
        self.loading.delay_with_loading_indicator(_DELAY)

        
    """
    Clears any one or all 10 of the measurement items that have been turned on.

    Args:
        item_n (str): The measurement item to clear.
    
    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
        ValueError: If an invalid item is requested.
    """
    def clear_measure_item(self, item_n):
        
        if not self.status == "Connected":
            error_message = "Not connected to Rigol DS7034 Oscilloscope."
            raise ConnectionError(_ERROR_STYLE + error_message)

        if isinstance(item_n, int) and 1 <= item_n <= 10:
            item_n = f"ITEM{item_n}"
        item_n_upper = item_n.upper()

        if not item_n_upper in {"ITEM1","ITEM2","ITEM3","ITEM4","ITEM5","ITEM6","ITEM7","ITEM8","ITEM9","ITEM10","ALL"}:
            error_message = f"Invalid item: \"{item_n}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        command = f"MEASURE:CLE {item_n}"
        self.instrument.write(command)
        self.loading.delay_with_loading_indicator(_DELAY)

    """
    Configures the probe input impedance, attenuation factor, coupling mode, and bandwidth limit for the specified channel.

    Args:
        channel (str): The channel to configure. Valid values are {CHANnel1|CHANnel2|CHANnel3|CHANnel4}.
        impedance (str): The input impedance to configure. Valid values are {OMEG|FIFTY}. Default is OMEG.
        gain (float): The attenuation factor to configure. Valid values are {0.01|0.02|0.05|0.1|0.2|0.5|1|2|5|10|20|50|100|200|500|1000}. Default is 10.
        coupling (str): The coupling mode to configure. Valid values are {AC|DC}. Default is DC.
        bwlimit (str): The bandwidth limit to configure. Valid values are {20M|250M|OFF}. Default is OFF.

    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
        ValueError: If an invalid channel, impedance, gain, coupling, or bandwidth limit is requested.
    """
    def configure_probe(self, channel, impedance = 'OMEG', gain = 10, coupling = 'DC', bwlimit = 'OFF'):

        if not self.status == "Connected":
            error_message = "Not connected to Rigol DS7034 Oscilloscope."
            raise ConnectionError(_ERROR_STYLE + error_message)

        if isinstance(channel, int) and 1 <= channel <= 4:
            channel = f"CHANnel{channel}"

        if not channel.upper() in {"CHANNEL1","CHANNEL2","CHANNEL3","CHANNEL4","CHAN1","CHAN2","CHAN3","CHAN4"}:
            error_message = f"Invalid channel: \"{channel}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        if not impedance.upper() in {"OMEG","FIFTY","FIFT"}:
            error_message = f"Invalid impedance: \"{impedance}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        if not gain in {0.01,0.02,0.05,0.1,0.2,0.5,1,2,5,10,20,50,100,200,500,1000}:
            error_message = f"Invalid gain: \"{gain}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        if not coupling.upper() in {"AC","DC"}:
            error_message = f"Invalid coupling: \"{coupling}\" request to Rigol DS7034 Oscilloscope. Check the documentation."  
            raise ValueError(_ERROR_STYLE + error_message)
        
        if not bwlimit.upper() in {"20M","250M","OFF"}:
            error_message = f"Invalid bandwidth limit: \"{bwlimit}\" request to Rigol DS7034 Oscilloscope. Check the documentation."    
            raise ValueError(_ERROR_STYLE + error_message)
        
        settings = ["IMPedance","PROBe","COUPling","BWLimit"]
        probes = ["\033[93mProbe 1\033[39m", # yellow
                    "\033[96mProbe 2\033[39m", # cyan
                    "\033[95mProbe 3\033[39m", # magenta
                    "\033[94mProbe 4\033[39m"] # blue

        for value in [impedance, gain, coupling, bwlimit]:
            command = f":{channel}:{settings.pop(0)}"
            self.instrument.write(command+f" {value}")
            self.loading.delay_with_loading_indicator(_DELAY)
            result = self.instrument.query(command+"?")
            self.loading.delay_with_loading_indicator(_DELAY)
            if not result == str(value):
                if value == bwlimit:
                    warning_message = f"Failed to configure bandwidth limit on {probes[int(channel[-1])-1]} because scale < 20mV/div."   
                else:
                    warning_message = f"Failed to configure {probes[int(channel[-1])-1]}. Try reconnecting the probe."
                print(_WARNING_STYLE + warning_message)
                input("Press Enter to continue (CTRL+C to QUIT)...\n")
                return False


        if impedance == "OMEG": impedance = "1Mohm"
        else: impedance = "50ohm"
        print(f"\r{probes[int(channel[-1])-1]}: Impedance:{impedance}, Gain:{gain}, Coupling:{coupling}, Bandwidth Limit:{bwlimit}")
        
        return True
    
    """
    Configure the timebase scale.

    Args:
        scale (float): Value to set the timebase scale to. Default is 1E-6 seconds.

    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
        ValueError: If an invalid timebase scale is requested.
    """
    def configure_time_scale(self, scale = 1E-6):
        if not self.status == "Connected":
            error_message = "Not connected to Rigol DS7034 Oscilloscope."
            raise ConnectionError(_ERROR_STYLE + error_message)
        
        if not isinstance(scale, (int, float)):
            error_message = f"Invalid timebase scale: \"{scale}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        command = f":TIMebase:SCALe {scale}"
        self.instrument.write(command)
        self.loading.delay_with_loading_indicator(_DELAY)

    """
    Configure the timebase offset.

    Args:
        offset (float): Value to set the timebase offset to. Default is 0 seconds.

    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
        ValueError: If an invalid timebase offset is requested.
    """
    def configure_time_offset(self, offset = 0):
        if not self.status == "Connected":
            error_message = "Not connected to Rigol DS7034 Oscilloscope."
            raise ConnectionError(_ERROR_STYLE + error_message)
        
        if not isinstance(offset, (int, float)):
            error_message = f"Invalid timebase offset: \"{offset}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        command = f":TIMebase:OFFSet {offset}"
        self.instrument.write(command)
        self.loading.delay_with_loading_indicator(_DELAY)
    
    """
    Configure the vertical scale of the specified channel.

    Args:
        channel (int or str): Channel to configure the vertical scale of.
        value (float): Value to set the vertical scale to. Default is 0.1 volts/div.

    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
        ValueError: If an invalid channel or vertical scale is requested.
    """
    def set_vertical_scale(self, channel, value=0.1):
        if not self.status == "Connected":
            error_message = "Not connected to Rigol DS7034 Oscilloscope."
            raise ConnectionError(_ERROR_STYLE + error_message)
        
        if isinstance(channel, int) and 1 <= channel <= 4:
            channel = f"CHANnel{channel}"

        if not channel.upper() in {"CHANNEL1","CHANNEL2","CHANNEL3","CHANNEL4","CHAN1","CHAN2","CHAN3","CHAN4"}:
            error_message = f"Invalid channel: \"{channel}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        if not isinstance(value, (int, float)):
            error_message = f"Invalid vertical scale: \"{value}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        command = f":{channel}:SCALe {value}"
        self.instrument.write(command)
        self.loading.delay_with_loading_indicator(_DELAY)


    """
    Configure the vertical offset of the specified channel.

    Args:
        channel (int or str): Channel to configure the vertical offset of.
        value (float): Value to set the vertical offset to. Default is 0 volts.

    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
        ValueError: If an invalid channel or vertical offset is requested.
    """
    def set_vertical_offset(self, channel, value=0):
        if not self.status == "Connected":
            error_message = "Not connected to Rigol DS7034 Oscilloscope."
            raise ConnectionError(_ERROR_STYLE + error_message)
        
        if isinstance(channel, int) and 1 <= channel <= 4:
            channel = f"CHANnel{channel}"

        if not channel.upper() in {"CHANNEL1","CHANNEL2","CHANNEL3","CHANNEL4","CHAN1","CHAN2","CHAN3","CHAN4"}:
            error_message = f"Invalid channel: \"{channel}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        if not isinstance(value, (int, float)):
            error_message = f"Invalid vertical offset: \"{value}\" request to Rigol DS7034 Oscilloscope. Check the documentation."
            raise ValueError(_ERROR_STYLE + error_message)
        
        command = f":{channel}:OFFSet {value}"
        self.instrument.write(command)
        self.loading.delay_with_loading_indicator(_DELAY)


    """
    Finds the next available filename by appending a number to the base filename.

    Args:
        name (str): The base filename.
        max_tries (int, optional): The maximum number of tries to find an available filename. Defaults to _MAX_FILENAMES.

    Returns:
        str: The next available filename.

    Raises:
        FileExistsError: If an available filename cannot be found after the maximum number of tries.
    """
    def __find_next_filename(self, name, max_tries=_MAX_FILENAMES):


        root, ext = os.path.splitext(name)
        for i in range(max_tries):
            test_name = f"{root}{i+1}{ext}"
            if not os.path.exists(test_name):
                return test_name

        # If an available filename is not found after the maximum number of tries, raise an exception
        error_message = (
            f"Failed to find an available filename after {max_tries} tries. "
            "Please clean up the output files or increase 'max_tries' value."
        )
        raise FileExistsError(_ERROR_STYLE + error_message)
    

    """
    Saves a screenshot from the oscilloscope.

    Args:
        filename (str): The filename to save the screenshot as.
            If not provided, the filename will be generated based on the current timestamp.
            Use "path/to/save/*" to specify a directory to save the screenshot in.

    Raises:
        ConnectionError: If not connected to Rigol DS7034 Oscilloscope.
        FileNotFoundError: If the screenshot could not be saved.
    """
    def save_screenshot(self, filename=None):

        if not self.status == "Connected":
            error_message = "Not connected to Rigol DS7034 Oscilloscope."
            raise ConnectionError(_ERROR_STYLE + error_message)
        
        if filename==None:
            filename = self.screenshot_filename
        else:
            self.screenshot_filename = filename            

        if filename is None:
            if self.screenshot_filename_warning_given is False:
                self.screenshot_filename_warning_given = True
                warning_message = (
                    "No path provided for screenshot. "
                    "The screenshot will be saved in the current directory with a timestamped filename. Use 'set_screenshot_path(\"path/to/save/*\")' to specify a directory to save the screenshot in."
                )
                print(_WARNING_STYLE + warning_message)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"DS7034_screenshot_{timestamp}.png"
        elif filename.endswith("*"):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = filename.replace("*", f"DS7034_screenshot_{timestamp}.png")
        else:
            if not filename.endswith(".png"):
                filename += ".png"
            filename = self.__find_next_filename(filename)

        command = "DISPlay:DATA? PNG, COLor, SCReen"
        image_data = self.instrument.query_binary_values(command, datatype='B', container=numpy.array)
        self.loading.delay_with_loading_indicator(_DELAY)

        directory = os.path.dirname(filename)
        if not os.path.exists(directory) and not directory == "":
            # Directory doesn't exist, ask the user if they want to create it
            create_directory = input(f"The directory "{directory}/" does not exist. Create it? (y/n): ")
            if create_directory.lower() == "y":
                os.makedirs(directory)
            else:
                raise FileNotFoundError(_ERROR_STYLE + "Directory does not exist.")

        with open(filename, "wb") as file:
            file.write(image_data)

        #print(_SUCCESS_STYLE + f"Screenshot saved as: {filename}")

        return filename
    
    """
    Sets the filename to save the screenshot as.
    """
    def set_screenshot_path(self, filename):
        self.screenshot_filename = filename
