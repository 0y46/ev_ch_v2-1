# ui_components.py
# This file contains custom UI components for the EV Charging Station monitor

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QTableWidget, QTableWidgetItem, QPushButton,
                            QLineEdit, QRadioButton, QButtonGroup, QFrame,
                            QSizePolicy, QHeaderView, QGridLayout, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QRect
import pyqtgraph as pg
import numpy as np
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont, QMovie, QPixmap, QIcon
from keypad import NumericKeypad
from pg_gauge import PyQtGraphGauge


class FixedWidget(QFrame):
    """
    Base class for fixed-position, non-draggable widgets.
    This replaces the DraggableWidget class for applications where
    widgets should stay in a fixed location.
    """
    
    def __init__(self, parent=None, widget_id=None):
        super().__init__(parent)
        self.widget_id = widget_id
        
        # Set frame and background - keep the visual style
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(2)
        
        # Set minimum size
        self.setMinimumSize(100, 100)

class ColorLabel(QLabel):
    """
    Custom label with colored line indicator for graph legends.
    Displays a small colored line followed by text.
    Clicking toggles visibility of associated plot line.
    """

    # Signal to emit when clicked, passing the index of this label and new visibility state
    visibility_toggled = pyqtSignal(int, bool)

    def __init__(self, text, color, index=0, parent=None):
        super().__init__(text, parent)
        
        self.color = color
        self.index = index  # Store index to identify which line this label controls
        self.visible = True  # Track visibility state
        self.inactive_color = (128, 128, 128)  # Gray color for inactive state

        # Add some margins to better separate the color indicator from text
        self.setContentsMargins(15, 0, 5, 0)
    
        # Set cursor to indicate it's clickable
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        # Custom paint event to draw colored line indicator
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw color line indicator - with active or inactive color
        pen = QPen(QColor(*self.color if self.visible else self.inactive_color))
        pen.setWidth(4)  # Line thickness - increase for thicker indicator
        painter.setPen(pen)
        # Draw horizontal line at vertical center of label
        painter.drawLine(2, self.height() // 2, 12, self.height() // 2)
        
        # Draw text (parent's paint event)
        super().paintEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press to toggle visibility"""
        if event.button() == Qt.LeftButton:
            # Toggle visibility state
            self.visible = not self.visible
            
            # Update appearance
            self.update()
            
            # Emit signal with index and new visibility state
            self.visibility_toggled.emit(self.index, self.visible)
            
        # Call the parent class implementation
        super().mousePressEvent(event)

class GraphWidget(FixedWidget):
    """
    Widget for displaying real-time graphs with centered title and 
    right-aligned horizontal legends.
    
    This widget combines a title, legend, and plot area in a 
    vertically stacked layout.
    """
    
    def __init__(self, parent=None, title="Graph", widget_id=None):
        super().__init__(parent, widget_id)
        
        # Main layout - Contains header (title+legend) and plot
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # Adjust widget margins here

        # Add paused state tracking
        self.is_paused = False
        
        # Store the last data received when paused
        self.last_data = {
            'time': None,
            'values': []  # Will hold lists of values for each line
        }

        #----------------------------------------
        # Header Section (Title + Legend)
        #----------------------------------------
        
        # Create header layout with title and legend
        header_layout = QHBoxLayout()
        # Reduce padding around the header layout 
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(5)  # Space between title and legend area
        
        # Left spacer - pushes title to center
        header_layout.addStretch(1)
        
        # Title label - centered in middle of header
        self.title_label = QLabel(title)
        # This line controls the title style and size
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")  # <-- CHANGE TITLE SIZE HERE
        self.title_label.setAlignment(Qt.AlignCenter)  # Center align the text
        # Add title to header with stretch factor 2 (middle section)
        header_layout.addWidget(self.title_label, 2)
        
        # Right section with legends - pushed to right side
        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 5, 0)  # Small right margin
        
        # Add right-side spacer to push legends to far right
        right_layout.addStretch(1)
        
        # Legends container - holds all legend labels
        self.legend_container = QWidget()
        self.legend_layout = QHBoxLayout(self.legend_container)
        # Reduce space around legends
        self.legend_layout.setContentsMargins(0, 0, 0, 0)
        # This line controls the space between legend items
        self.legend_layout.setSpacing(10)  # <-- CHANGE SPACING BETWEEN LEGEND ITEMS
        # Right-align and vertically center the legends
        self.legend_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # Add legend container to right section layout
        right_layout.addWidget(self.legend_container)
        
        # Add the right container to header with stretch factor 2
        header_layout.addWidget(right_container, 2)
        
        # Add header section to main layout
        layout.addLayout(header_layout)
        
        #----------------------------------------
        # Plot Section
        #----------------------------------------
        
        # Create PyQtGraph PlotWidget for data visualization
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')  # White background
        self.plot_widget.showGrid(x=True, y=True)  # Show grid lines
        
        # Add plot widget to main layout with stretch factor
        # This makes the plot expand to fill available space
        layout.addWidget(self.plot_widget, stretch=1)
        
        # Set the assembled layout for this widget
        self.setLayout(layout)
        
        # Plot lines and colors setup
        self.lines = []  # Will store plot line references
        # Color definitions for different line types (R,G,B) format
        # Change these values to adjust plot line colors
        self.colors = [(255, 0, 0),    # Red
                       (0, 0, 255),    # Blue
                       (0, 200, 0),    # Green
                       (0, 0, 0)]  # Yellow-ish

    def pause_graph(self):
        """Pause the graph updates"""
        self.is_paused = True
    
    def resume_graph(self):
        """Resume the graph updates"""
        self.is_paused = False
    
    def setup_voltage_graph(self):
        """
        Configure widget for voltage graph.
        Sets up title, axes, range, and creates plot lines with legend.
        """
        # Set the widget title
        self.title_label.setText("Grid Voltage")
        self.title_label.setStyleSheet("font-weight: bold; color: black; font-size: 16px;")

        # Configure the plot widget
        self.plot_widget.setTitle("")  # Clear default title (we use our custom title)
        voltage_axis = self.plot_widget.getAxis("left")
        voltage_axis.setLabel("Voltage", units="V", **{'font-size': '10pt', 'font-weight': 'bold'})
        time_axis = self.plot_widget.getAxis("bottom")
        time_axis.setLabel("Time", units="s", **{'font-size': '10pt', 'font-weight': 'bold'})
        self.plot_widget.setYRange(-250, 250)  # Set Y-axis limits
        
        # Clear any existing legend items from previous configurations
        for i in reversed(range(self.legend_layout.count())): 
            widget = self.legend_layout.itemAt(i).widget()
            if widget:  # Check if it's a widget (not a spacer)
                widget.setParent(None)
        
        # Clear existing plot lines
        self.plot_widget.clear()
        self.lines = []
        # Track line visibility state
        self.line_visibility = []

        # Add custom legend labels for voltage phases
        phase_names = ['Vg,a', 'Vg,b', 'Vg,c']
        legend_items = []
        for i, name in enumerate(phase_names):
            # Create legend with index i
            legend_item = ColorLabel(name, self.colors[i], i)
            # This line controls the legend item text style and size
            legend_item.setStyleSheet("font-weight: bold; color: black; font-size: 16px;")
            # Connect toggle signal to our handler
            legend_item.visibility_toggled.connect(self.toggle_line_visibility)
            self.legend_layout.addWidget(legend_item)
            legend_items.append(legend_item)
        
        # Add plot lines for each phase
        for i in range(len(phase_names)):
            # Create a pen with the appropriate color and width
            pen = pg.mkPen(color=self.colors[i], width=2)
            # Add an empty line series to the plot
            line = self.plot_widget.plot([], [], pen=pen)
            # Store reference to the line for later data updates
            self.lines.append(line)
            # All lines visible initially
            self.line_visibility.append(True)
    
    def setup_current_graph(self):
        """
        Configure widget for current graph.
        Sets up title, axes, range, and creates plot lines with legend.
        """
        # Set the widget title
        self.title_label.setText("Grid Current")
        self.title_label.setStyleSheet("font-weight: bold; color: black; font-size: 16px;")

        # Configure the plot widget
        self.plot_widget.setTitle("")  # Clear default title
        current_axis = self.plot_widget.getAxis("left")
        current_axis.setLabel("Current", units="A", **{'font-size': '10pt', 'font-weight': 'bold'})
        time_axis = self.plot_widget.getAxis("bottom")
        time_axis.setLabel("Time", units="s", **{'font-size': '10pt', 'font-weight': 'bold'})
        self.plot_widget.setYRange(-10, 10)  # Set Y-axis limits for current
        
        # Clear any existing legend items
        for i in reversed(range(self.legend_layout.count())): 
            widget = self.legend_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        # Clear existing plot lines
        self.plot_widget.clear()
        self.lines = []
        # Track line visibility state
        self.line_visibility = []

        # Add custom legend labels for current phases
        phase_names = ['Ig,a', 'Ig,b', 'Ig,c']
        legend_items = []
        for i, name in enumerate(phase_names):
            legend_item = ColorLabel(name, self.colors[i], i)
            # Legend style and size
            legend_item.setStyleSheet("font-weight: bold; color: black; font-size: 16px;")  # <-- CHANGE LEGEND SIZE HERE
            legend_item.visibility_toggled.connect(self.toggle_line_visibility)
            self.legend_layout.addWidget(legend_item)
            legend_items.append(legend_item)

        # Add plot lines for each phase
        for i in range(len(phase_names)):
            pen = pg.mkPen(color=self.colors[i], width=2)
            line = self.plot_widget.plot([], [], pen=pen)
            # Store reference to the line for later data updates
            self.lines.append(line)
            # All lines visible initially
            self.line_visibility.append(True)
    
    def setup_power_graph(self):
        """
        Configure widget for power graph.
        Sets up title, axes, range, and creates plot lines with legend.
        """
        # Set the widget title
        self.title_label.setText("Power Distribution")
        self.title_label.setStyleSheet("font-weight: bold; color: black; font-size: 16px;")

        # Configure the plot widget
        self.plot_widget.setTitle("")  # Clear default title
        power_axis = self.plot_widget.getAxis("left")
        power_axis.setLabel("Power", units="W", **{'font-size': '10pt', 'font-weight': 'bold'})
        time_axis = self.plot_widget.getAxis("bottom")
        time_axis.setLabel("Time", units="s", **{'font-size': '10pt', 'font-weight': 'bold'})
        self.plot_widget.setYRange(-5000, 3000)  # Set Y-axis limits for power
        
        # Clear any existing legend items from previous configurations
        for i in reversed(range(self.legend_layout.count())): 
            widget = self.legend_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        # Clear existing plot lines
        self.plot_widget.clear()
        self.lines = []
        self.line_visibility = []

        # Add custom legend labels for power sources
        power_names = ['P_grid', 'P_pv', 'P_ev', 'P_battery']
        legend_items = []
        for i, name in enumerate(power_names):
            legend_item = ColorLabel(name, self.colors[i], i)
            # Legend style and size
            legend_item.setStyleSheet("font-weight: bold; color: black; font-size: 16px;")  # <-- CHANGE LEGEND SIZE HERE
            legend_item.visibility_toggled.connect(self.toggle_line_visibility)
            self.legend_layout.addWidget(legend_item)
            legend_items.append(legend_item)
        
        # Add plot lines for each power source
        for i in range(len(power_names)):
            pen = pg.mkPen(color=self.colors[i], width=2)
            line = self.plot_widget.plot([], [], pen=pen)
            self.lines.append(line)
            self.line_visibility.append(True)
    
    def update_voltage_data(self, time_data, va_data, vb_data, vc_data):
        """Update the voltage graph with new data"""
        # Store the latest data regardless of pause state
        values = [va_data, vb_data, vc_data]
        self.last_data['time'] = time_data
        self.last_data['values'] = values
        
        # If paused, don't update the graph
        if self.is_paused:
            return
        
        # Check if lines have been initialized
        if len(self.lines) >= 3:
            # Update only visible lines
            for i, line in enumerate(self.lines[:3]):
                if self.line_visibility[i]:
                    line.setData(time_data, values[i])
    
    def update_current_data(self, time_data, ia_data, ib_data, ic_data):
        """Update the current graph with new data"""
        # Store the latest data regardless of pause state
        values = [ia_data, ib_data, ic_data]
        self.last_data['time'] = time_data
        self.last_data['values'] = values
        
        # If paused, don't update the graph
        if self.is_paused:
            return
        
        # Check if lines have been initialized
        if len(self.lines) >= 3:
            # Update only visible lines
            for i, line in enumerate(self.lines[:3]):
                if self.line_visibility[i]:
                    line.setData(time_data, values[i])
                else:
                    line.setData([], [])

    def update_power_data(self, time_data, p_grid, p_pv, p_ev, p_battery):
        """Update the power graph with new data"""
        # Store the latest data regardless of pause state
        values = [p_grid, p_pv, p_ev, p_battery]
        self.last_data['time'] = time_data
        self.last_data['values'] = values
        
        # If paused, don't update the graph
        if self.is_paused:
            return
        
        # Check if lines have been initialized
        if len(self.lines) >= 4:
            # Update only visible lines
            for i, line in enumerate(self.lines[:4]):
                if self.line_visibility[i]:
                    line.setData(time_data, values[i])
                else:
                    line.setData([], [])

    def toggle_line_visibility(self, index, visible):
        """
        Toggle the visibility of a plot line
        
        Args:
            index (int): The index of the line to toggle
            visible (bool): The new visibility state
        """
        # Make sure we have valid indices
        if index < 0 or index >= len(self.lines):
            return
        
        # Store the visibility state
        self.line_visibility[index] = visible
        
        # If the graph is paused, we need to handle it differently
        if self.is_paused:
            # When paused, we need to update the current view without new data
            if visible:
                # Make line visible again with last known data
                if (self.last_data['time'] is not None and 
                    self.last_data['values'] and 
                    index < len(self.last_data['values'])):
                    self.lines[index].setData(self.last_data['time'], self.last_data['values'][index])
            else:
                # Hide the line by setting it to empty data
                self.lines[index].setData([], [])
        else:
            # When not paused, visibility is handled in the next update
            if not visible:
                # Hide immediately by setting to empty data
                self.lines[index].setData([], [])
        
class GaugeGridWidget(QFrame):
    """
    Fixed position widget that contains multiple gauges arranged in a grid layout.
    This widget is designed to display system measurements in an organized, non-movable container.
    """
    
    def __init__(self, parent=None, widget_id="gauge_grid"):
            super().__init__(parent)
            self.widget_id = widget_id
            
            # Set fixed position and size as specified
            self.setGeometry(749, 408, 581, 290)
            self.setFixedSize(581, 290)  # Prevent resizing
            
            # Match the frame style of other widgets (like GraphWidget)
            self.setFrameStyle(QFrame.Box | QFrame.Raised)  # Changed from Panel to Box
            self.setLineWidth(2)  # Changed from 1 to 2 to match other widgets
            
            # Set the background color on the widget itself, not on the layout
            self.setStyleSheet('background-color: #FFFFFF')

            # Use a grid layout to arrange gauges in rows and columns
            self.layout = QGridLayout(self)
            self.layout.setContentsMargins(0, 0, 0, 0)  # title margin
            # Set different horizontal and vertical spacing
            self.layout.setHorizontalSpacing(5)  # Reduced horizontal spacing (make gauges closer side-by-side)
            self.layout.setVerticalSpacing(20)  # Keep increased vertical spacing
            
            # Add a title at the top of the gauge grid
            self.title_label = QLabel("System Measurements")
            self.title_label.setAlignment(Qt.AlignCenter)
            self.title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
            
            # Position the title at the top, spanning all columns
            self.layout.addWidget(self.title_label, 0, 0, 1, 3)
            
            # Store references to individual gauges for later access
            self.gauges = []

    def add_gauge(self, title, min_value, max_value, units, gauge_id=None):
        """
        Add a new gauge to the grid layout.
        
        Returns:
            The created gauge widget for reference
        """
        # Calculate position in grid (2 rows, 3 columns)
        row = (len(self.gauges) // 3) + 1  # +1 because row 0 is title
        col = len(self.gauges) % 3
        
        # Create a gauge widget using the PyQtGraph implementation
        gauge = PyQtGraphGauge(self, title, min_value, max_value, units, gauge_id)
        
        # Add gauge to layout with alignment for better positioning
        self.layout.addWidget(gauge, row, col, Qt.AlignCenter)
        
        # Store reference to gauge
        self.gauges.append(gauge)
        
        return gauge
    

class TableWidget(FixedWidget):  # Assuming you changed from DraggableWidget to FixedWidget
    """Widget for displaying editable parameter tables with optimized layout"""
    
    save_clicked = pyqtSignal(str, dict)  # Signal to emit when save button is clicked
    
    def __init__(self, parent=None, title="Parameters", widget_id=None):
        super().__init__(parent, widget_id)
        
        # Main layout with minimal margins
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # Minimal margins
        layout.setSpacing(2)  # Minimal spacing between components
        
        # Title with proper size
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 16px;")  # 16px as requested
        self.title_label.setFixedHeight(30)  # Fixed height for title
        layout.addWidget(self.title_label)
        
        # Create table with optimal settings
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Parameter", "Value", "Input"])
        
        # Explicitly disable scrollbars 
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Center-align the headers
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        
        # Configure fixed column widths based on container size
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        
        # Set header style
        self.table.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: #E0E0E0; font-weight: bold; }")
        
        # Additional table settings
        self.table.verticalHeader().hide()  # Remove row numbers
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        
        # Center all text in the table
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #D0D0D0;
                background-color: white;
                font-size: 15px;  /* 10px as requested */
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 0px;
                margin: 0px;
                border: none;
                text-align: center;
            }
        """)
        
        layout.addWidget(self.table)
        
        # Save button with better styling
        self.save_button = QPushButton("Save")
        self.save_button.setFixedHeight(25)  # Fixed height for button
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 0px 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.save_button.clicked.connect(self.on_save_clicked)
        self.save_button.setCursor(Qt.PointingHandCursor)  # Hand cursor on hover
        
        # Button container for centering
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()
        
        layout.addWidget(button_container)
        
        self.setLayout(layout)
        self.table_type = None  # Will be set during setup
        self.radio_groups = {}  # For radio button groups
        self.input_widgets = {}  # Store references to input widgets by parameter name
    
       # Add this method to handle showing the keypad
    def create_keypad_input_field(self, default_value="0"):
        """
        Create a touch-friendly input field that shows keypad when clicked.
        
        Args:
            default_value (str): Default value for the input field
            
        Returns:
            QLineEdit: Configured input field
        """
        input_widget = QLineEdit(default_value)
        input_widget.setAlignment(Qt.AlignCenter)
        input_widget.setStyleSheet("""
            padding: 2px; 
            margin: 1px; 
            font-size: 15px;
            font-weight: bold;
            background-color: #F8F8F8;
            border: 1px solid #CCCCCC;
        """)
        
        # Make it read-only to prevent keyboard from showing up on touch devices
        input_widget.setReadOnly(True)
        
        # Store the current value separately since the field is read-only
        input_widget.setProperty("actual_value", default_value)
        
        # Add click event to show keypad
        input_widget.mousePressEvent = lambda event, widget=input_widget: self.show_keypad(widget)
        
        return input_widget
    
    def show_keypad(self, input_widget):
        """
        Show numeric keypad when an input field is clicked.
        
        Args:
            input_widget (QLineEdit): The input widget that was clicked
        """
        # Get parameter name from the same row
        row = -1
        for i in range(self.table.rowCount()):
            if self.table.cellWidget(i, 2) == input_widget:
                row = i
                break
        
        if row == -1:
            return  # Widget not found in table
        
        # Get parameter name from first column
        param_name = self.table.item(row, 0).text()
        
        # Get current value from the widget's property
        current_value = input_widget.property("actual_value") or ""
        
        # Show keypad dialog
        value, accepted = NumericKeypad.get_value(
            self, 
            f"Enter {param_name} Value", 
            str(current_value)
        )
        
        if accepted:
            try:
                # Update both the display and actual value
                float_value = float(value)  # Convert to make sure it's a valid number
                input_widget.setText(value)
                input_widget.setProperty("actual_value", value)
            except ValueError:
                # Invalid number input, leave unchanged
                pass

    def setup_charging_setting_table(self):
        """Configure table for Charging Setting"""
        self.title_label.setText("Charging Setting")
        self.table_type = "charging_setting"
        
        # Define parameters
        parameters = [
            {"name": "PV power", "type": "number", "default": 2000},
            {"name": "EV power", "type": "number", "default": -4000},
            {"name": "Battery power", "type": "number", "default": 0},
            {"name": "V_dc", "type": "readonly", "default": 80.19}
        ]
        
        self.table.setRowCount(len(parameters))
        
        # Calculate and set optimal column widths
        table_width = self.width() - 10  # Account for margins
        self.table.setColumnWidth(0, int(table_width * 0.35))  # Parameter column
        self.table.setColumnWidth(1, int(table_width * 0.30))  # Value column
        self.table.setColumnWidth(2, int(table_width * 0.35))  # Input column
        
        # Calculate optimal row height to fit all rows without scrollbar
        available_height = self.height() - self.title_label.height() - self.save_button.height() - 40
        header_height = self.table.horizontalHeader().height()
        row_height = (available_height - header_height) / len(parameters)
        
        # Clear input widgets dictionary
        self.input_widgets = {}

        # Populate table
        for i, param in enumerate(parameters):
            # Parameter name - center aligned
            item = QTableWidgetItem(param["name"])
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, item)
            
            # Current value - center aligned
            value_item = QTableWidgetItem(str(param["default"]))
            value_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 1, value_item)
            
            # Input field - custom centered widget
            if param["type"] == "readonly":
                input_widget = QLabel("--")
                input_widget.setAlignment(Qt.AlignCenter)
                input_widget.setStyleSheet("background-color: #F0F0F0; color: #808080;")
            else:
                # Create touchscreen-friendly input field with keypad
                input_widget = self.create_keypad_input_field("0")
                # Store reference to this input widget
                self.input_widgets[param["name"]] = input_widget
            
            # Set the row height
            self.table.setRowHeight(i, int(row_height))
            self.table.setCellWidget(i, 2, input_widget)
    
    def setup_ev_charging_setting_table(self):
        """Configure table for EV Charging Setting"""
        self.title_label.setText("EV Charging Setting")
        self.table_type = "ev_charging_setting"
        
        # Define parameters
        parameters = [
            {"name": "EV voltage", "type": "number", "default": 58.66},
            {"name": "EV SoC", "type": "number", "default": 0},
            {"name": "Demand Response", "type": "radio", "default": True},
            {"name": "V2G", "type": "radio", "default": True}
        ]
        
        self.table.setRowCount(len(parameters))
        
        # Calculate and set optimal column widths
        table_width = self.width() - 10  # Account for margins
        self.table.setColumnWidth(0, int(table_width * 0.35))  # Parameter column
        self.table.setColumnWidth(1, int(table_width * 0.30))  # Value column
        self.table.setColumnWidth(2, int(table_width * 0.35))  # Input column
        
        # Calculate optimal row height to fit all rows without scrollbar
        available_height = self.height() - self.title_label.height() - self.save_button.height() - 40
        header_height = self.table.horizontalHeader().height()
        row_height = (available_height - header_height) / len(parameters)
        
        # Clear input widgets dictionary
        self.input_widgets = {}

        # Populate table
        for i, param in enumerate(parameters):
            # Parameter name - center aligned
            item = QTableWidgetItem(param["name"])
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, item)
            
            # Current value - center aligned
            if param["type"] == "radio":
                value = "On" if param["default"] else "Off"
            else:
                value = str(param["default"])
                
            value_item = QTableWidgetItem(value)
            value_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 1, value_item)
            
            # Input field - depending on type
            if param["type"] == "number":
                # Create touchscreen-friendly input field with keypad
                input_widget = self.create_keypad_input_field("0")
                # Store reference to this input widget
                self.input_widgets[param["name"]] = input_widget
                self.table.setCellWidget(i, 2, input_widget)
            elif param["type"] == "radio":
                radio_widget = QWidget()
                radio_layout = QHBoxLayout(radio_widget)
                radio_layout.setContentsMargins(2, 0, 2, 0)
                radio_layout.setSpacing(5)
                
                # Create radio button group
                radio_on = QRadioButton("On")
                radio_on.setStyleSheet("font-weight: bold;")
                radio_off = QRadioButton("Off")
                radio_off.setStyleSheet("font-weight: bold;")
                
                # Center the radio buttons
                radio_layout.addStretch(1)
                radio_layout.addWidget(radio_on)
                radio_layout.addWidget(radio_off)
                radio_layout.addStretch(1)
                
                
                # Set default selection
                if param["default"]:
                    radio_on.setChecked(True)
                else:
                    radio_off.setChecked(True)
                
                # Add to button group
                button_group = QButtonGroup(radio_widget)
                button_group.addButton(radio_on)
                button_group.addButton(radio_off)

                # Store reference to button group
                self.radio_groups[param["name"]] = button_group
                self.table.setCellWidget(i, 2, radio_widget)
            
            # Set the row height
            self.table.setRowHeight(i, int(row_height))

    def setup_grid_settings_table(self):
        """Configure table for Grid Settings"""
        self.title_label.setText("Grid Settings")
        self.table_type = "grid_settings"
        # Define parameters
        parameters = [
            {"name": "Vg_rms", "type": "number", "default": 155},
            {"name": "Ig_rms", "type": "number", "default": 9},
            {"name": "Frequency", "type": "number", "default": 50},
            {"name": "THD", "type": "number", "default": 3},
            {"name": "Power factor", "type": "number", "default": 0.99}
        ]
        
        self.table.setRowCount(len(parameters))
        
        # Calculate and set optimal column widths
        table_width = self.width() - 10  # Account for margins
        self.table.setColumnWidth(0, int(table_width * 0.35))  # Parameter column
        self.table.setColumnWidth(1, int(table_width * 0.30))  # Value column
        self.table.setColumnWidth(2, int(table_width * 0.35))  # Input column
        
        # Calculate optimal row height to fit all rows without scrollbar
        available_height = self.height() - self.title_label.height() - self.save_button.height() - 40
        header_height = self.table.horizontalHeader().height()
        row_height = (available_height - header_height) / len(parameters)
        
        # Clear input widgets dictionary
        self.input_widgets = {}

        # Populate table
        for i, param in enumerate(parameters):
            # Parameter name - center aligned
            item = QTableWidgetItem(param["name"])
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, item)
            
            # Current value - center aligned
            value_item = QTableWidgetItem(str(param["default"]))
            value_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 1, value_item)
            
            # Create touchscreen-friendly input field with keypad
            input_widget = self.create_keypad_input_field("0")
            # Store reference to this input widget
            self.input_widgets[param["name"]] = input_widget
            self.table.setCellWidget(i, 2, input_widget)
            
            # Set the row height
            self.table.setRowHeight(i, int(row_height))

    def update_values(self, data_dict):
        """Update the values column in the table"""
        if not data_dict:
            return
            
        for row in range(self.table.rowCount()):
            param_name = self.table.item(row, 0).text()
            if param_name in data_dict:
                value = data_dict[param_name]
                if isinstance(value, bool):
                    display_value = "On" if value else "Off"
                elif isinstance(value, (int, float)):
                    # Format numbers to two decimal places
                    display_value = f"{value:.2f}"
                else:
                    display_value = str(value)
                    
                # Update with center alignment
                value_item = QTableWidgetItem(display_value)
                value_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 1, value_item)
    
    def on_save_clicked(self):
            """Handle save button click - collect input values, update table and send via UDP"""
            input_values = {}
            
            for row in range(self.table.rowCount()):
                param_name = self.table.item(row, 0).text()
                cell_widget = self.table.cellWidget(row, 2)
                
                # Skip read-only fields (QLabel)
                if isinstance(cell_widget, QLabel):
                    continue
                    
                # Get values from keypad input fields
                if isinstance(cell_widget, QLineEdit):
                    # Get value from the property we set
                    value_str = cell_widget.property("actual_value") or "0"
                    try:
                        value = float(value_str)
                        input_values[param_name] = value
                    except ValueError:
                        # Invalid input, ignore
                        pass
                
                # Handle radio button groups
                if param_name in self.radio_groups:
                    # Get button group
                    button_group = self.radio_groups[param_name]
                    # Check if first button (On) is selected
                    if button_group.buttons()[0].isChecked():
                        input_values[param_name] = True
                    else:
                        input_values[param_name] = False
            
            # Update values in the table immediately
            self.update_from_input_values(input_values)
            
            # Emit signal with table type and values
            self.save_clicked.emit(self.table_type, input_values)

    def update_from_input_values(self, input_values):
        """Update the value column directly from input values"""
        for row in range(self.table.rowCount()):
            param_name = self.table.item(row, 0).text()
            if param_name in input_values:
                value = input_values[param_name]
                if isinstance(value, bool):
                    display_value = "On" if value else "Off"
                elif isinstance(value, (int, float)):
                    display_value = f"{value:.2f}"
                else:
                    display_value = str(value)
                    
                # Update with center alignment
                value_item = QTableWidgetItem(display_value)
                value_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 1, value_item)

class FixedButtonWidget(QFrame):
    """
    Non-draggable, fixed-position widget for displaying buttons.
    This widget has a visible border but minimal internal margins.
    """
    
    def __init__(self, parent=None, widget_id=None, horizontal=True):
        super().__init__(parent)
        self.widget_id = widget_id
        
        # Set frame appearance - thin visible border
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(2)  # Thin border
        
        # Explicitly disable size adjustments
        self.setFixedSize(240, 40)  # Fixed size - will adjust this later
        
        # Use horizontal layout for buttons by default
        layout = QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)  # Absolute minimal margins
        layout.setSpacing(30)  # Minimal space between buttons
        
        self.setLayout(layout)
        self.buttons = []
    
    def add_button(self, text, color="default", callback=None):
        """Add a button with minimal padding"""
        button = QPushButton(text)
        button.setFont(QFont("Arial", 10))  # Smaller font size
        
        # Set fixed button size
        button_width = max(100, len(text) * 7)
        button_height = 30
        button.setFixedSize(button_width, button_height)
        
        # Set cursor to pointing hand when hovering over button
        button.setCursor(Qt.PointingHandCursor)  # Add this line
        
        # Apply styling with no padding
        if color == "green":
            button.setStyleSheet("""
                background-color: #4CAF50; 
                color: white; 
                padding: 0px;
                margin: 0px;
                border: 1px solid #388E3C;
                }
                QPushButton:hover {
                background-color: rgba(60, 60, 60, 180);
            """)
        elif color == "red":
            button.setStyleSheet("""
                background-color: #F44336; 
                color: white; 
                padding: 0px;
                margin: 0px;
                border: 1px solid #D32F2F;
                }
                QPushButton:hover {
                background-color: rgba(60, 60, 60, 180);
            """)
        else:
            button.setStyleSheet("""
                padding: 0px;
                margin: 0px;
                border: 1px solid #BDBDBD;
            """)
        
        # Connect callback if provided
        if callback:
            button.clicked.connect(callback)
        
        # Add to layout and store reference
        self.layout().addWidget(button)
        self.buttons.append(button)
        
        return button
    
    def get_button(self, index):
        """Get button by index"""
        if 0 <= index < len(self.buttons):
            return self.buttons[index]
        return None

class EnergyHubWidget(FixedWidget):
    """Widget for displaying the Smart Energy Hub visualization optimized for 948×290 pixels"""
    
    def __init__(self, parent=None, widget_id="energy_hub"):
        super().__init__(parent, widget_id)
        
        # Set fixed size to match your specifications
        self.setFixedSize(948, 290)
        
        # Main layout with minimal margins
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title label with reduced height
        self.title_label = QLabel("Smart Energy Hub")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("background-color: #FFFFFF; font-weight: bold; font-size: 16px; margin-bottom: 0px;")
        self.title_label.setMaximumHeight(25)  # Keep title compact
        layout.addWidget(self.title_label)
        
        # Container for the hub visualization - optimized for remaining space
        self.hub_container = QWidget()
        self.hub_container.setStyleSheet('background-color: #FFFFFF')

        # Grid layout with minimal padding
        self.hub_layout = QGridLayout(self.hub_container)
        self.hub_layout.setContentsMargins(5, 5, 5, 5)
        self.hub_layout.setSpacing(0)
        self.hub_layout.setAlignment(Qt.AlignCenter)  # Center the grid content
        
        # Load all required images
        self.images = {
            'transformer': QPixmap("imgs/4core-b.png"),
            'pv': QPixmap("imgs/pv_panel.png"),
            'ev': QPixmap("imgs/EV.png"),
            'grid': QPixmap("imgs/grid.png"),
            'battery': QPixmap("imgs/Battery.png"),
            'off': QPixmap("imgs/off.PNG"),
            'on': QPixmap("imgs/on.PNG")
        }
        
        # Load GIFs
        self.right_gif = QMovie("imgs/right.gif")
        self.left_gif = QMovie("imgs/left.gif")
        
        # Create and arrange all hub components
        self.setup_hub_components()
        
        layout.addWidget(self.hub_container)
        self.setLayout(layout)
        
        # Initialize status values
        self.s1_status = 0  # PV panel status
        self.s2_status = 0  # EV status
        self.s3_status = 0  # Grid status
        self.s4_status = 0  # Battery status
        self.ev_soc = 0     # EV state of charge
        self.battery_soc = 0  # Battery state of charge
        
        # Update initial statuses
        self.update_all_statuses()
    
    def setup_hub_components(self):
        """Set up all the components of the energy hub with proper z-ordering and sizing"""
        
        # 1. Increase spacing to prevent clipping
        self.hub_layout.setSpacing(0)  # Add some space between cells
        self.hub_layout.setContentsMargins(0, 0, 0, 0)  # Add margins around the grid
        
        # Load the AC and DC line images
        self.images['ac_line'] = QPixmap("imgs/AC-line.png")
        self.images['dc_line'] = QPixmap("imgs/DC-line.png")
        
        # 2. Set up components - order matters for z-ordering
        # Place background components first, status indicators last
        
        # Middle transformer (add this FIRST since it should be in the background)
        self.transformer_label = QLabel()
        self.transformer_label.setPixmap(self.images['transformer'].scaled(350, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.transformer_label.setAlignment(Qt.AlignCenter)
        self.transformer_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.hub_layout.addWidget(self.transformer_label, 1, 9, 2, 6)
        
        # Add connection lines BEFORE adding components
        # PV to Transformer (DC line)
        self.pv_line = QLabel()
        self.pv_line.setPixmap(self.images['dc_line'].scaled(200, 20, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.pv_line.setAlignment(Qt.AlignVCenter)
        self.pv_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.hub_layout.addWidget(self.pv_line, 1, 4, 1, 5)

        # EV to Transformer (DC line)
        self.ev_line = QLabel()
        self.ev_line.setPixmap(self.images['dc_line'].scaled(200, 20, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.ev_line.setAlignment(Qt.AlignVCenter)
        self.ev_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.hub_layout.addWidget(self.ev_line, 2, 4, 1, 5)
        
        # Transformer to Grid (AC line)
        self.grid_line = QLabel()
        self.grid_line.setPixmap(self.images['ac_line'].scaled(200, 30, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.grid_line.setAlignment(Qt.AlignVCenter)
        self.grid_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.hub_layout.addWidget(self.grid_line, 1, 15, 1, 5)
        
        # Transformer to Battery (DC line)
        self.battery_line = QLabel()
        self.battery_line.setPixmap(self.images['dc_line'].scaled(200, 20, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.battery_line.setAlignment(Qt.AlignVCenter)
        self.battery_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.hub_layout.addWidget(self.battery_line, 2, 15, 1, 5)

        # 3. Component images - add these BEFORE status indicators
        
        # Left side - PV Panel
        self.pv_label = QLabel()
        self.pv_label.setPixmap(self.images['pv'].scaled(160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.pv_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pv_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.hub_layout.addWidget(self.pv_label, 1, 0, 1, 4)
        
        # Left side - EV
        self.ev_label = QLabel()
        self.ev_label.setPixmap(self.images['ev'].scaled(160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.ev_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ev_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.hub_layout.addWidget(self.ev_label, 2, 0, 1, 4)
        
        # Right side - Grid
        self.grid_label = QLabel()
        self.grid_label.setPixmap(self.images['grid'].scaled(160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.grid_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.grid_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.hub_layout.addWidget(self.grid_label, 1, 20, 1, 4)
        
        # Right side - Battery
        self.battery_label = QLabel()
        self.battery_label.setPixmap(self.images['battery'].scaled(160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.battery_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.battery_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.hub_layout.addWidget(self.battery_label, 2, 20, 1, 4)
        
        # 4. Create status indicator widgets LAST (so they appear on top)
        # Use adjacent columns that don't overlap with the transformer
        
        # PV Status indicator - move further left to avoid transformer overlap
        self.pv_status_label = QLabel()
        self.pv_status_label.setAlignment(Qt.AlignCenter)
        self.pv_status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.pv_status_label.setMinimumSize(80, 80)
        self.hub_layout.addWidget(self.pv_status_label, 1, 6, 1, 2)
        # Raise to front
        self.pv_status_label.raise_()
        
        # EV Status indicator - move further left to avoid transformer overlap
        self.ev_status_label = QLabel()
        self.ev_status_label.setAlignment(Qt.AlignCenter)
        self.ev_status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.ev_status_label.setMinimumSize(80, 80)
        self.hub_layout.addWidget(self.ev_status_label, 2, 6, 1, 2)
        # Raise to front
        self.ev_status_label.raise_()
        
        # Grid Status indicator - move further right to avoid transformer overlap
        self.grid_status_label = QLabel()
        self.grid_status_label.setAlignment(Qt.AlignCenter)
        self.grid_status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.grid_status_label.setMinimumSize(80, 80)
        self.hub_layout.addWidget(self.grid_status_label, 1, 16, 1, 2)
        # Raise to front
        self.grid_status_label.raise_()
        
        # Battery Status indicator - move further right to avoid transformer overlap
        self.battery_status_label = QLabel()
        self.battery_status_label.setAlignment(Qt.AlignCenter)
        self.battery_status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.battery_status_label.setMinimumSize(80, 80)
        self.hub_layout.addWidget(self.battery_status_label, 2, 16, 1, 2)
        # Raise to front
        self.battery_status_label.raise_()
        
        # SoC Labels 
        self.ev_soc_label = QLabel("EV SoC: 0%")
        self.ev_soc_label.setAlignment(Qt.AlignCenter)
        self.ev_soc_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-top: 5px; background-color: rgba(255, 255, 255, 180);")
        self.hub_layout.addWidget(self.ev_soc_label, 3, 0, 1, 6)
        
        self.battery_soc_label = QLabel("Battery SoC: 0%")
        self.battery_soc_label.setAlignment(Qt.AlignCenter)
        self.battery_soc_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-top: 5px; background-color: rgba(255, 255, 255, 180);")
        self.hub_layout.addWidget(self.battery_soc_label, 3, 18, 1, 6)
        
        # Make all columns equal width to ensure proper distribution
        for i in range(21):
            self.hub_layout.setColumnStretch(i, 1)
    
    def showEvent(self, event):
        """Handle show events to adjust container size"""
        super().showEvent(event)
        
        # Adjust hub container to its minimum size
        QTimer.singleShot(0, self.adjustContainerSize)
    
    def adjustContainerSize(self):
        """Adjust container size to fit contents"""
        self.hub_container.adjustSize()
    
    def update_pv_status(self, status):
        """Update PV panel status indicator"""
        self.s1_status = status
        self._update_status_label(self.pv_status_label, status)
    
    def update_ev_status(self, status):
        """Update EV status indicator"""
        self.s2_status = status
        self._update_status_label(self.ev_status_label, status)
    
    def update_grid_status(self, status):
        """Update grid status indicator"""
        self.s3_status = status
        self._update_status_label(self.grid_status_label, status)
    
    def update_battery_status(self, status):
        """Update battery status indicator"""
        self.s4_status = status
        self._update_status_label(self.battery_status_label, status)
    
    def _update_status_label(self, label, status):
        """Update a status indicator label based on status value"""
        # Stop any existing movie
        if label.movie():
            label.movie().stop()
            label.setMovie(None)
        
        # Make sure images don't get cut off by giving them appropriate margins
        # The 80x80 size leaves room for the image within the 100x100 allocation
        if status == 0:  # Off
            label.setPixmap(self.images['off'].scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        elif status == 1:  # On
            label.setPixmap(self.images['on'].scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        elif status == 2:  # Right direction
            movie = QMovie("imgs/right.gif")
            label.setMovie(movie)
            movie.setScaledSize(QSize(80, 80))
            movie.start()
        elif status == 3:  # Left direction
            movie = QMovie("imgs/left.gif")
            label.setMovie(movie)
            movie.setScaledSize(QSize(80, 80))
            movie.start()
        
        # Ensure the label is visible and on top
        label.raise_()
    
    def update_ev_soc(self, soc):
        """Update EV state of charge display"""
        self.ev_soc = soc
        self.ev_soc_label.setText(f"EV SoC: {soc:.2f}%")
    
    def update_battery_soc(self, soc):
        """Update battery state of charge display"""
        self.battery_soc = soc
        self.battery_soc_label.setText(f"Battery SoC: {soc:.2f}%")
    
    def update_all_statuses(self):
        """Update all status indicators to current values"""
        self.update_pv_status(self.s1_status)
        self.update_ev_status(self.s2_status)
        self.update_grid_status(self.s3_status)
        self.update_battery_status(self.s4_status)
        self.update_ev_soc(self.ev_soc)
        self.update_battery_soc(self.battery_soc)
