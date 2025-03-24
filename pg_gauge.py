# pg_gauge.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter, QFont
import pyqtgraph as pg
import numpy as np
from PyQt5.QtWidgets import QGraphicsLineItem, QGraphicsEllipseItem

class PyQtGraphGauge(QWidget):
    """
    Custom gauge widget using PyQtGraph for better accuracy
    """
    
    def __init__(self, parent=None, title="Gauge", min_value=0, max_value=100, 
                 units="", widget_id=None):
        super().__init__(parent)
        
        # Store configuration
        self.title = title
        self.min_value = min_value
        self.max_value = max_value
        self.units = units
        self.widget_id = widget_id
        self.value = min_value
        
        # Set fixed size to match original gauge
        self.setFixedSize(165, 110)
        
        # Set white background explicitly
        self.setStyleSheet("background-color: white;")
        
        # Set up layout
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 1, 2, 5)  # Small margins
        layout.setSpacing(2)  # Minimal spacing
        self.setLayout(layout)
        
        # Add title label
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 15px; background-color: white;")
        self.title_label.setMaximumHeight(15)
        layout.addWidget(self.title_label)
        
        # Add value label
        self.value_label = QLabel(f"{self.value:.2f} {self.units}")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 12px; font-weight: bold; color: blue; background-color: white;")
        self.value_label.setMaximumHeight(15)
        layout.addWidget(self.value_label)
        
        # Create a PyQtGraph PlotWidget for the gauge
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')  # Explicitly set white background
        self.plot_widget.getPlotItem().hideAxis('left')
        self.plot_widget.getPlotItem().hideAxis('bottom')
        self.plot_widget.setMouseEnabled(x=False, y=False)  # Disable mouse interactions
        self.plot_widget.setMenuEnabled(False)  # Disable context menu
        
        # Add plot to layout
        layout.addWidget(self.plot_widget, 1)  # Give plot more space with stretch factor
        
        # Create the gauge elements
        self._create_gauge()
        
        # Determine colors based on gauge type
        self._configure_colors()
        
        # Set initial value to ensure pointer is positioned correctly
        self.set_value((self.min_value + self.max_value) / 2)  # Start in the middle
    
    def _create_gauge(self):
        """Create the base gauge elements"""
        # Clear the plot
        self.plot_widget.clear()
        
        # Set fixed range for consistent display
        self.plot_widget.setXRange(-1.2, 1.2)
        self.plot_widget.setYRange(-1.2, 1.2)
        
        # Create arc for gauge background (225° to -45°, counterclockwise)
        # Arc is drawn with 100 points for smoothness
        theta = np.linspace(225 * np.pi/180, -45 * np.pi/180, 100)
        x = np.cos(theta)
        y = np.sin(theta)
        
        # Create the main arc
        self.arc = self.plot_widget.plot(x, y, pen=pg.mkPen('gray', width=10))
        
        # Create the pointer - store as instance variable for updates
        # Note: We'll position it in set_value method
        self.pointer_line = QGraphicsLineItem(0, 0, 0.8, 0)
        self.pointer_line.setPen(pg.mkPen('black', width=3))
        self.plot_widget.addItem(self.pointer_line)
        
        # Add center dot for pointer pivot
        self.center_dot = QGraphicsEllipseItem(-0.05, -0.05, 0.1, 0.1)
        self.center_dot.setBrush(pg.mkBrush('black'))
        self.plot_widget.addItem(self.center_dot)
        
        # Add min/max labels
        min_text = pg.TextItem(text=str(self.min_value), color='black', anchor=(0.5, 0))
        min_text.setPos(np.cos(225 * np.pi/180) * 0.9, np.sin(225 * np.pi/180) * 0.9)
        self.plot_widget.addItem(min_text)
        
        max_text = pg.TextItem(text=str(self.max_value), color='black', anchor=(0.5, 0))
        max_text.setPos(np.cos(-45 * np.pi/180) * 0.9, np.sin(-45 * np.pi/180) * 0.9)
        self.plot_widget.addItem(max_text)
    
    def _configure_colors(self):
        """Configure gauge colors based on type"""
        # Define standard colors
        red = (231, 76, 60)      # Red
        yellow = (241, 196, 15)  # Yellow
        green = (46, 204, 113)   # Green
        orange = (230, 126, 34)  # Orange
        
        # Remove any existing color segments
        for item in self.plot_widget.items():
            if isinstance(item, pg.PlotDataItem) and item != self.arc:
                self.plot_widget.removeItem(item)
        
        # Create color gradient
        if "Frequency" in self.title or "Voltage" in self.title:
            # Red → Yellow → Green → Yellow → Red
            segments = 100  # Number of segments for smooth gradient
            colors = []
            for i in range(segments):
                pos = i / (segments - 1.0)
                if pos < 0.25:
                    # Red to yellow
                    r = int(red[0] + pos * 4 * (yellow[0] - red[0]))
                    g = int(red[1] + pos * 4 * (yellow[1] - red[1]))
                    b = int(red[2] + pos * 4 * (yellow[2] - red[2]))
                elif pos < 0.5:
                    # Yellow to green
                    p = (pos - 0.25) * 4
                    r = int(yellow[0] + p * (green[0] - yellow[0]))
                    g = int(yellow[1] + p * (green[1] - yellow[1]))
                    b = int(yellow[2] + p * (green[2] - yellow[2]))
                elif pos < 0.75:
                    # Green to yellow
                    p = (pos - 0.5) * 4
                    r = int(green[0] + p * (yellow[0] - green[0]))
                    g = int(green[1] + p * (yellow[1] - green[1]))
                    b = int(green[2] + p * (yellow[2] - green[2]))
                else:
                    # Yellow to red
                    p = (pos - 0.75) * 4
                    r = int(yellow[0] + p * (red[0] - yellow[0]))
                    g = int(yellow[1] + p * (red[1] - yellow[1]))
                    b = int(yellow[2] + p * (red[2] - yellow[2]))
                colors.append(pg.mkColor(r, g, b))
            
            # Draw multiple segments with different colors
            theta = np.linspace(225 * np.pi/180, -45 * np.pi/180, segments)
            for i in range(segments - 1):
                segment_pen = pg.mkPen(colors[i], width=10)
                segment_x = [np.cos(theta[i]), np.cos(theta[i+1])]
                segment_y = [np.sin(theta[i]), np.sin(theta[i+1])]
                self.plot_widget.plot(segment_x, segment_y, pen=segment_pen)
                
        elif "THD" in self.title:
            # Green → Yellow → Orange → Red
            segments = 100  # Number of segments for smooth gradient
            colors = []
            for i in range(segments):
                pos = i / (segments - 1.0)
                if pos < 0.5:
                    # Green to yellow
                    p = pos * 2
                    r = int(green[0] + p * (yellow[0] - green[0]))
                    g = int(green[1] + p * (yellow[1] - green[1]))
                    b = int(green[2] + p * (yellow[2] - green[2]))
                else:
                    # Yellow to red
                    p = (pos - 0.5) * 2
                    r = int(yellow[0] + p * (red[0] - yellow[0]))
                    g = int(yellow[1] + p * (red[1] - yellow[1]))
                    b = int(yellow[2] + p * (red[2] - yellow[2]))
                colors.append(pg.mkColor(r, g, b))
            
            # Draw multiple segments with different colors
            theta = np.linspace(225 * np.pi/180, -45 * np.pi/180, segments)
            for i in range(segments - 1):
                segment_pen = pg.mkPen(colors[i], width=10)
                segment_x = [np.cos(theta[i]), np.cos(theta[i+1])]
                segment_y = [np.sin(theta[i]), np.sin(theta[i+1])]
                self.plot_widget.plot(segment_x, segment_y, pen=segment_pen)
        
        else:  # Current, Power
            # Yellow → Green
            segments = 100  # Number of segments for smooth gradient
            colors = []
            for i in range(segments):
                pos = i / (segments - 1.0)
                r = int(yellow[0] + pos * (green[0] - yellow[0]))
                g = int(yellow[1] + pos * (green[1] - yellow[1]))
                b = int(yellow[2] + pos * (green[2] - yellow[2]))
                colors.append(pg.mkColor(r, g, b))
            
            # Draw multiple segments with different colors
            theta = np.linspace(225 * np.pi/180, -45 * np.pi/180, segments)
            for i in range(segments - 1):
                segment_pen = pg.mkPen(colors[i], width=10)
                segment_x = [np.cos(theta[i]), np.cos(theta[i+1])]
                segment_y = [np.sin(theta[i]), np.sin(theta[i+1])]
                self.plot_widget.plot(segment_x, segment_y, pen=segment_pen)
    
    def set_value(self, value):
        """Set the gauge value and update pointer"""
        # Ensure value is within range
        self.value = max(self.min_value, min(value, self.max_value))
        
        # Update value label with 2 decimal places
        self.value_label.setText(f"{self.value:.2f} {self.units}")
        
        # Calculate normalized position (0.0 to 1.0)
        normalized = (self.value - self.min_value) / (self.max_value - self.min_value)
        
        # Calculate angle in radians (225° to -45°)
        angle_deg = 225 - normalized * 270
        angle_rad = angle_deg * np.pi / 180
        
        # Update pointer position using trigonometry
        # Calculate the endpoint of the pointer line
        end_x = 0.8 * np.cos(angle_rad)
        end_y = 0.8 * np.sin(angle_rad)
        
        # Update the pointer line
        self.pointer_line.setLine(0, 0, end_x, end_y)