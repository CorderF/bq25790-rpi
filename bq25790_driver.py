#!/usr/bin/env python3
"""
BQ25790 Battery Monitor Driver
"""

import smbus2
import time
from typing import Dict, Optional

class BQ25790:
    """Registers BQ25790"""
    
    # Registros principales del BQ25790
    REG_MINIMAL_SYS_VOLTAGE = 0x00
    REG_CHARGE_VOLTAGE_LIMIT = 0x01
    REG_CHARGE_CURRENT_LIMIT = 0x03
    REG_INPUT_VOLTAGE_LIMIT = 0x05
    REG_INPUT_CURRENT_LIMIT = 0x06
    REG_PRECHARGE_CTRL = 0x08
    REG_TERMINATION_CTRL = 0x09
    REG_CHARGER_CTRL_0 = 0x0F
    REG_CHARGER_CTRL_1 = 0x10
    REG_CHARGER_STATUS_0 = 0x1B
    REG_CHARGER_STATUS_1 = 0x1C
    REG_CHARGER_STATUS_2 = 0x1D
    REG_CHARGER_STATUS_3 = 0x1E
    REG_CHARGER_STATUS_4 = 0x1F
    REG_FAULT_STATUS_0 = 0x20
    REG_FAULT_STATUS_1 = 0x21
    REG_CHARGER_FLAG_0 = 0x22
    REG_CHARGER_FLAG_1 = 0x23
    REG_ADC_CTRL = 0x25
    REG_ADC_FUNCTION_DISABLE_0 = 0x26
    REG_IBUS_ADC = 0x27
    REG_IBAT_ADC = 0x29
    REG_VBUS_ADC = 0x2B
    REG_VAC1_ADC = 0x2D
    REG_VAC2_ADC = 0x2F
    REG_VBAT_ADC = 0x31
    REG_VSYS_ADC = 0x33
    REG_TS_ADC = 0x35
    REG_TDIE_ADC = 0x37
    REG_PART_INFO = 0x38
    
    def __init__(self, bus_number: int = 1, address: int = 0x6B):
        """
        Inicializa el driver del BQ25790
        
        Args:
            bus_number: I2C bus (i2c 1 for Raspberry Pi)
            address: I2C address (0x6B by default)
        """
        self.bus_number = bus_number
        self.address = address
        self.bus = smbus2.SMBus(bus_number)
        
    def read_register(self, register: int) -> int:
        """Read an 8-bit register"""
        return self.bus.read_byte_data(self.address, register)
    
    def read_register_16bit(self, register: int) -> int:
        """Read a 16-bit register (MSB first)"""
        msb = self.bus.read_byte_data(self.address, register)
        lsb = self.bus.read_byte_data(self.address, register + 1)
        return (msb << 8) | lsb
    
    def write_register(self, register: int, value: int):
        """Write an 8-bit register"""
        self.bus.write_byte_data(self.address, register, value)
    
    def enable_adc(self):
        """Enable ADC for voltage/current readings"""
        # Enable continuous ADC
        self.write_register(self.REG_ADC_CTRL, 0x80)
        time.sleep(0.1)  # Esperar a que el ADC se estabilice
    
    def get_battery_voltage(self) -> float:
        """Obtain the battery voltage in volts"""
        raw = self.read_register_16bit(self.REG_VBAT_ADC)
        # VBAT: 1 mV per bit, offset 0V
        return raw / 1000.0
    
    def get_battery_current(self) -> float:
        """Obtain the battery current in amperes (negative = discharge)"""
        raw = self.read_register_16bit(self.REG_IBAT_ADC)
        # IBAT: 1 mA per bit (values > 32767 are negative in two's complement)
        if raw > 32767:
            raw = raw - 65536
        return raw / 1000.0
    
    def get_system_voltage(self) -> float:
        """Obtiene el voltaje del sistema en voltios"""
        raw = self.read_register_16bit(self.REG_VSYS_ADC)
        return raw / 1000.0
    
    def get_bus_voltage(self) -> float:
        """Obtiene el voltaje del bus (entrada) en voltios"""
        raw = self.read_register_16bit(self.REG_VBUS_ADC)
        return raw / 1000.0
    
    def get_bus_current(self) -> float:
        """Obtiene la corriente de entrada en amperios"""
        raw = self.read_register_16bit(self.REG_IBUS_ADC)
        return raw / 1000.0
    
    def get_die_temperature(self) -> float:
        """Obtiene la temperatura del chip en grados Celsius"""
        raw = self.read_register_16bit(self.REG_TDIE_ADC)
        # Temp = raw * 0.5 - 40
        return (raw * 0.5) - 40.0
    
    def get_charger_status(self) -> Dict[str, any]:
        """Obtiene el estado del cargador"""
        status0 = self.read_register(self.REG_CHARGER_STATUS_0)
        status1 = self.read_register(self.REG_CHARGER_STATUS_1)
        status2 = self.read_register(self.REG_CHARGER_STATUS_2)
        
        # Decode charge status
        charge_status = (status1 >> 5) & 0x07
        charge_status_str = {
            0: "Not Charging",
            1: "Trickle Charge",
            2: "Pre-charge",
            3: "Fast Charge (CC)",
            4: "Taper Charge (CV)",
            5: "Reserved",
            6: "Top-off Timer",
            7: "Charge Termination Done"
        }.get(charge_status, "Unknown")
        
        # VBUS status
        vbus_status = (status0 >> 5) & 0x07
        vbus_status_str = {
            0: "No Input",
            1: "USB SDP (500mA)",
            2: "USB CDP (1.5A)",
            3: "USB DCP (3A)",
            4: "Adjustable HV DCP",
            5: "Unknown Adapter",
            6: "Non-Standard Adapter",
            7: "OTG"
        }.get(vbus_status, "Unknown")
        
        return {
            "charging": bool(status1 & 0x10),
            "charge_status": charge_status_str,
            "vbus_present": bool(status0 & 0x80),
            "vbus_status": vbus_status_str,
            "battery_present": not bool(status2 & 0x08),
            "power_good": bool(status0 & 0x04)
        }
    
    def get_fault_status(self) -> Dict[str, bool]:
        """Obtain fault statuses"""
        fault0 = self.read_register(self.REG_FAULT_STATUS_0)
        fault1 = self.read_register(self.REG_FAULT_STATUS_1)
        
        return {
            "vac1_ovp": bool(fault0 & 0x80),
            "vac2_ovp": bool(fault0 & 0x40),
            "conv_ocp": bool(fault0 & 0x20),
            "ibat_reg": bool(fault0 & 0x10),
            "ibus_reg": bool(fault0 & 0x08),
            "vbat_ovp": bool(fault0 & 0x04),
            "vbus_ovp": bool(fault0 & 0x02),
            "vsys_ovp": bool(fault1 & 0x80),
            "tshut": bool(fault1 & 0x40),
            "bat_temp_fault": bool(fault1 & 0x08)
        }
    
    def get_all_data(self) -> Dict[str, any]:
        """Obtain all battery and system data"""
        self.enable_adc()
        
        return {
            "battery": {
                "voltage": round(self.get_battery_voltage(), 3),
                "current": round(self.get_battery_current(), 3),
                "power": round(self.get_battery_voltage() * self.get_battery_current(), 3)
            },
            "system": {
                "voltage": round(self.get_system_voltage(), 3),
                "temperature": round(self.get_die_temperature(), 1)
            },
            "input": {
                "voltage": round(self.get_bus_voltage(), 3),
                "current": round(self.get_bus_current(), 3),
                "power": round(self.get_bus_voltage() * self.get_bus_current(), 3)
            },
            "status": self.get_charger_status(),
            "faults": self.get_fault_status(),
            "timestamp": time.time()
        }
    
    def close(self):
        """Close the I2C connection"""
        self.bus.close()


if __name__ == "__main__":
    # Example usage
    import json
    
    try:
        bq = BQ25790(bus_number=1, address=0x6B)
        data = bq.get_all_data()
        print(json.dumps(data, indent=2))
        bq.close()
    except Exception as e:
        print(f"Error: {e}")