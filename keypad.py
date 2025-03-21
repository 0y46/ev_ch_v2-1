# keypad.py
"""
Custom numeric keypad dialog for touchscreen interfaces.
This module provides a touch-friendly numeric keypad as an alternative to using a physical keyboard.
"""

from PyQt5.QtWidgets import (QDialog, QGridLayout, QPushButton, QLineEdit,
                           QVBoxLayout, QHBoxLayout, QSizePolicy, QDialogButtonBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

class NumericKeypad(QDialog):
    """
    A custom numeric keypad dialog designed for touchscreen interfaces.
    
    This dialog provides buttons for digits 0-9, decimal point, sign change,
    backspace, and clear functionality. It can be used to input numeric values
    without requiring a physical keyboard.
    """
    
    valueEntered = pyqtSignal(str)  # Signal emitted when a value is confirmed
    
    def __init__(self, parent=None, title="Enter Value", current_value=""):
        super().__init__(parent)
        # Configure dialog properties
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)  # Keep dialog on top
        self.setModal(True)  # Modal dialog - blocks interaction with parent
        self.setMinimumSize(300, 400)  # Size suitable for touch
        
        # Main layout for the dialog
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Display for showing the entered value
        self.display = QLineEdit(current_value)
        self.display.setAlignment(Qt.AlignRight)
        self.display.setReadOnly(True)  # User can't type directly - must use buttons
        self.display.setMinimumHeight(50)  # Taller for touch friendliness
        self.display.setFont(QFont("Arial", 18))  # Larger font for readability
        layout.addWidget(self.display)
        
        # Grid layout for numeric keys
        keypad_layout = QGridLayout()
        keypad_layout.setSpacing(8)  # Space between buttons
        
        # Create numeric buttons (0-9)
        self.digit_buttons = []
        
        # Add buttons for digits 1-9
        positions = [(i, j) for i in range(3) for j in range(3)]
        for position, digit in zip(positions, range(1, 10)):
            button = self._create_button(str(digit))
            keypad_layout.addWidget(button, *position)
            self.digit_buttons.append(button)
        
        # Additional buttons (0, decimal, +/-, etc.)
        # Zero button spans two columns
        zero_button = self._create_button("0")
        keypad_layout.addWidget(zero_button, 3, 0, 1, 2)
        self.digit_buttons.append(zero_button)
        
        # Decimal point button
        decimal_button = self._create_button(".")
        keypad_layout.addWidget(decimal_button, 3, 2)
        
        # Plus/minus (sign change) button
        sign_button = self._create_button("±")
        keypad_layout.addWidget(sign_button, 0, 3)
        
        # Clear button
        clear_button = self._create_button("C")
        clear_button.setStyleSheet("background-color: #F44336; color: white; font-weight: bold;")
        keypad_layout.addWidget(clear_button, 1, 3)
        
        # Backspace button
        backspace_button = self._create_button("⌫")
        backspace_button.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        keypad_layout.addWidget(backspace_button, 2, 3)
        
        # Enter button
        enter_button = self._create_button("Enter")
        enter_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        keypad_layout.addWidget(enter_button, 3, 3)
        
        # Add keypad grid to main layout
        layout.addLayout(keypad_layout)
        
        # Add some space at the bottom
        layout.addStretch(1)
        
        # Add action button box with Cancel button
        button_box = QDialogButtonBox(QDialogButtonBox.Cancel)
        button_box.rejected.connect(self.reject)  # Connect Cancel to dialog reject
        layout.addWidget(button_box)
        
        # Connect button signals to handlers
        for button in self.digit_buttons:
            button.clicked.connect(self.digit_pressed)
        decimal_button.clicked.connect(self.decimal_pressed)
        sign_button.clicked.connect(self.sign_pressed)
        clear_button.clicked.connect(self.clear_pressed)
        backspace_button.clicked.connect(self.backspace_pressed)
        enter_button.clicked.connect(self.enter_pressed)
    
    def _create_button(self, text):
        """
        Helper method to create a standardized button for the keypad.
        
        Args:
            text (str): The text to display on the button.
            
        Returns:
            QPushButton: A configured button ready to be added to the layout.
        """
        button = QPushButton(text)
        button.setFont(QFont("Arial", 16))  # Larger font for touch
        button.setMinimumSize(60, 60)  # Square buttons are easier to touch
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        button.setCursor(Qt.PointingHandCursor)  # Show hand cursor on hover
        return button
    
    def digit_pressed(self):
        """Handle digit button press by appending the digit to the display."""
        button = self.sender()
        current_text = self.display.text()
        digit = button.text()
        self.display.setText(current_text + digit)
    
    def decimal_pressed(self):
        """
        Handle decimal point button press.
        Only one decimal point is allowed in the number.
        """
        current_text = self.display.text()
        # Only add a decimal point if there isn't one already
        if "." not in current_text:
            self.display.setText(current_text + ".")
    
    def sign_pressed(self):
        """Toggle the sign of the current value (positive/negative)."""
        current_text = self.display.text()
        if not current_text:
            return  # Nothing to change the sign of
            
        if current_text.startswith("-"):
            self.display.setText(current_text[1:])  # Remove negative sign
        else:
            self.display.setText("-" + current_text)  # Add negative sign
    
    def clear_pressed(self):
        """Clear the display (set to empty string)."""
        self.display.setText("")
    
    def backspace_pressed(self):
        """Remove the last character from the display."""
        current_text = self.display.text()
        self.display.setText(current_text[:-1])
    
    def enter_pressed(self):
        """
        Process the entered value when Enter is pressed.
        Emits the valueEntered signal with the current text and accepts the dialog.
        """
        current_text = self.display.text()
        
        # Handle empty input
        if not current_text:
            current_text = "0"
        
        # Handle input with just a decimal point
        if current_text == ".":
            current_text = "0"
        
        # Handle input that begins with a decimal point
        if current_text.startswith("."):
            current_text = "0" + current_text
        
        # Handle input that ends with a decimal point
        if current_text.endswith("."):
            current_text = current_text + "0"
        
        # Emit signal with the processed value
        self.valueEntered.emit(current_text)
        
        # Close the dialog with an "accepted" result
        self.accept()
    
    @staticmethod
    def get_value(parent=None, title="Enter Value", current_value=""):
        """
        Static method to create, show and return the value from a keypad dialog.
        
        This provides a simple interface for other components to request a numeric value.
        
        Args:
            parent: The parent widget for the dialog
            title (str): Title for the dialog window
            current_value (str): Initial value to display
            
        Returns:
            tuple: (value entered as string, boolean indicating if dialog was accepted)
        """
        dialog = NumericKeypad(parent, title, current_value)
        result = dialog.exec_()  # Show modal dialog and wait for result
        
        return dialog.display.text(), result == QDialog.Accepted