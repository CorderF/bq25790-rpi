#!/usr/bin/env python3
"""
Battery Monitor Service
REST API for querying BQ25790 information
"""

from flask import Flask, jsonify
from bq25790_driver import BQ25790
import logging
from threading import Lock
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Global instance of the driver with lock for thread-safety
bq_lock = Lock()
bq_instance = None
last_error = None
cache = {}
cache_timeout = 1.0  # Cache readings for 1 second

def get_bq_instance():
    """Get or create the BQ25790 instance"""
    global bq_instance, last_error
    
    if bq_instance is None:
        try:
            bq_instance = BQ25790(bus_number=1, address=0x6B)
            last_error = None
            logging.info("BQ25790 initialized successfully")
        except Exception as e:
            last_error = str(e)
            logging.error(f"Error initializing BQ25790: {e}")
            raise
    
    return bq_instance

@app.route('/health', methods=['GET'])
def health():
    """Endpoint for health check"""
    try:
        get_bq_instance()
        return jsonify({
            "status": "healthy",
            "service": "battery-monitor",
            "i2c_address": "0x6B"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 503

@app.route('/battery', methods=['GET'])
def get_battery_info():
    """Get complete battery information"""
    global cache
    
    # Check cache
    now = time.time()
    if 'data' in cache and (now - cache.get('timestamp', 0)) < cache_timeout:
        return jsonify(cache['data']), 200
    
    try:
        with bq_lock:
            bq = get_bq_instance()
            data = bq.get_all_data()
            
        # Update cache
        cache = {
            'data': data,
            'timestamp': now
        }
        
        return jsonify(data), 200
        
    except Exception as e:
        logging.error(f"Error getting data: {e}")
        return jsonify({
            "error": "Failed to read battery data",
            "details": str(e)
        }), 500

@app.route('/battery/voltage', methods=['GET'])
def get_voltage():
    """Get battery voltage only"""
    try:
        with bq_lock:
            bq = get_bq_instance()
            voltage = bq.get_battery_voltage()
        
        return jsonify({
            "voltage": round(voltage, 3),
            "unit": "V"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/battery/current', methods=['GET'])
def get_current():
    """Get battery current only"""
    try:
        with bq_lock:
            bq = get_bq_instance()
            current = bq.get_battery_current()
        
        return jsonify({
            "current": round(current, 3),
            "unit": "A",
            "note": "Positive = charging, Negative = discharging"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/battery/status', methods=['GET'])
def get_status():
    """Get charger status"""
    try:
        with bq_lock:
            bq = get_bq_instance()
            status = bq.get_charger_status()
        
        return jsonify(status), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/battery/temperature', methods=['GET'])
def get_temperature():
    """Get chip temperature"""
    try:
        with bq_lock:
            bq = get_bq_instance()
            temp = bq.get_die_temperature()
        
        return jsonify({
            "temperature": round(temp, 1),
            "unit": "°C"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/battery/faults', methods=['GET'])
def get_faults():
    """Get fault statuses"""
    try:
        with bq_lock:
            bq = get_bq_instance()
            faults = bq.get_fault_status()
        
        # Contar fallos activos
        active_faults = [k for k, v in faults.items() if v]
        
        return jsonify({
            "faults": faults,
            "active_count": len(active_faults),
            "active_faults": active_faults
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with service information"""
    
    return jsonify({
        "service": "BQ25790 Battery Monitor",
        "version": "1.0",
        "endpoints": {
            "/health": "Health check",
            "/battery": "Complete battery information",
            "/battery/voltage": "Battery voltage only",
            "/battery/current": "Battery current only",
            "/battery/status": "Charger status",
            "/battery/temperature": "Chip temperature",
            "/battery/faults": "Fault status"
        }
    }), 200

def cleanup():
    """Cleanup on service shutdown"""
    global bq_instance
    if bq_instance:
        try:
            bq_instance.close()
            logging.info("BQ25790 closed successfully")
        except:
            pass

if __name__ == '__main__':
    import atexit
    atexit.register(cleanup)
    
    # Ejecutar servidor
    app.run(host='0.0.0.0', port=5000, debug=False)