# config_manager.py
# This file handles saving and loading layout configurations

import json
import os
from PyQt5.QtCore import QPoint, QSize, QSettings

class ConfigManager:
    def __init__(self, app_name="EVChargingStation"):
        """Initialize config manager"""
        self.app_name = app_name
        self.settings = QSettings(self.app_name, "Layout")
        
        # Create a directory for config files
        self.config_dir = "config"
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        
        self.config_file = os.path.join(self.config_dir, "layout_config.json")
    
    def save_widget_config(self, widget_id, pos, size):
        """Save position and size for a widget"""
        self.settings.beginGroup(widget_id)
        self.settings.setValue("pos", pos)
        self.settings.setValue("size", size)
        self.settings.endGroup()
    
    def load_widget_config(self, widget_id):
        """Load position and size for a widget"""
        self.settings.beginGroup(widget_id)
        pos = self.settings.value("pos")
        size = self.settings.value("size")
        self.settings.endGroup()
        return pos, size
    
    def load_all_configs(self):
        """Load configurations for all widgets from file"""
        if not os.path.exists(self.config_file):
            return {}
        
        with open(self.config_file, 'r') as f:
            config_data = json.load(f)
        
        return config_data
    
    def apply_config_to_widget(self, widget, widget_id, configs=None):
        """Apply stored configuration to a widget"""
        if configs is None:
            configs = self.load_all_configs()
        
        if widget_id in configs:
            widget_config = configs[widget_id]
            pos = QPoint(widget_config["pos"]["x"], widget_config["pos"]["y"])
            size = QSize(widget_config["size"]["width"], widget_config["size"]["height"])
            
            widget.move(pos)
            widget.resize(size)
            return True
        
        return False