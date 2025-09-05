import matplotlib
matplotlib.use('Agg')
import os
import sys
import sqlite3
import hashlib
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
                               QTextEdit, QLineEdit, QComboBox, QMessageBox, QDialog, QFormLayout,
                               QDialogButtonBox, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
                               QFileDialog, QGraphicsOpacityEffect, QSizePolicy, QGraphicsView,
                               QGraphicsScene, QGraphicsEllipseItem, QProgressBar)
from PySide6.QtCore import (Qt, QSize, QPropertyAnimation, QTimer, QEasingCurve, 
                            QParallelAnimationGroup, QSequentialAnimationGroup, QPointF,
                            Signal, QObject, QRectF, QVariantAnimation)
from PySide6.QtGui import QBrush, QColor, QPen, QLinearGradient, QPainter
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import random
import math

# Database Setup (unchanged from original)
DB_NAME = "bdsoil.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nid TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL
        )
    ''')
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'profile_pic' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN profile_pic TEXT')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            location TEXT NOT NULL,
            area REAL NOT NULL,
            soil_type TEXT NOT NULL,
            gps_coords TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully")

init_db()

# Animation Helper Classes
class AnimationHelper:
    """Helper class for creating animations"""
    
    @staticmethod
    def fade_in(widget, duration=500):
        effect = QGraphicsOpacityEffect()
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(0)
        animation.setEndValue(1)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        animation.start()
        return animation
    
    @staticmethod
    def slide_in(widget, start_pos, end_pos, duration=500):
        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(start_pos)
        animation.setEndValue(end_pos)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        return animation
    
    @staticmethod
    def pulse(widget, duration=1000):
        effect = QGraphicsOpacityEffect()
        widget.setGraphicsEffect(effect)
        
        group = QSequentialAnimationGroup()
        
        fade_out = QPropertyAnimation(effect, b"opacity")
        fade_out.setDuration(duration // 2)
        fade_out.setStartValue(1)
        fade_out.setEndValue(0.3)
        
        fade_in = QPropertyAnimation(effect, b"opacity")
        fade_in.setDuration(duration // 2)
        fade_in.setStartValue(0.3)
        fade_in.setEndValue(1)
        
        group.addAnimation(fade_out)
        group.addAnimation(fade_in)
        group.setLoopCount(-1)
        group.start()
        return group

class ParticleWidget(QGraphicsView):
    """Simple particle effect widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setStyleSheet("background: transparent; border: none;")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.particles = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_particles)
        self.timer.start(50)
        
    def emit_particles(self, count=10):
        for _ in range(count):
            x = random.randint(0, 200)
            y = random.randint(0, 100)
            particle = QGraphicsEllipseItem(x, y, 5, 5)
            color = QColor(0, random.randint(100, 200), random.randint(50, 100))
            particle.setBrush(QBrush(color))
            particle.setPen(QPen(Qt.PenStyle.NoPen))
            self.scene.addItem(particle)
            self.particles.append({
                'item': particle,
                'velocity': QPointF(random.uniform(-1, 1), random.uniform(-2, 0)),
                'life': 100
            })
    
    def update_particles(self):
        to_remove = []
        for p in self.particles:
            p['life'] -= 5
            if p['life'] <= 0:
                to_remove.append(p)
                self.scene.removeItem(p['item'])
            else:
                pos = p['item'].pos()
                p['item'].setPos(pos + p['velocity'])
                p['item'].setOpacity(p['life'] / 100)
        for p in to_remove:
            self.particles.remove(p)

# Service Classes (unchanged from original)
class CropService:
    def __init__(self):
        try:
            self.crops_df = pd.read_csv('data/bangladesh_crops.csv')
            self.crops = {row['crop_name']: {
                "season": row['season'], "soil_type": row['soil_type'],
                "yield_per_hectare": float(row['yield_per_acre'].split()[0]) * 2.47105 if row['yield_per_acre'] else 5.0,
                "water_need": "High" if "Monsoon" in row['season'] else "Medium"
            } for _, row in self.crops_df.iterrows()}
            print(f"Loaded {len(self.crops)} crops")
        except Exception as e:
            print(f"Error loading crops: {e}")
            self.crops = {}
    
    def get_crop_info(self, crop_name):
        return self.crops.get(crop_name, {})
    
    def recommend_crop(self, soil_type, season):
        return [c for c, i in self.crops.items() if i["soil_type"].lower() == soil_type.lower() and season.lower() in i["season"].lower()] or ["No suitable crops"]

class PestService:
    def __init__(self):
        try:
            self.pest_df = pd.read_csv('data/pest_disease_data.csv')
            print(f"Loaded {len(self.pest_df)} pest/disease records")
        except FileNotFoundError:
            print("pest_disease_data.csv not found")
            self.pest_df = pd.DataFrame()
    
    def identify_pest(self, description):
        if not description or self.pest_df.empty:
            return "Unknown"
        return next((row['pest_disease'] for _, row in self.pest_df.iterrows() if row['pest_disease'].lower() in description.lower()), "Unknown")

    def get_control(self, pest):
        return self.pest_df[self.pest_df['pest_disease'] == pest]['control_measure'].iloc[0] if not self.pest_df.empty and pest in self.pest_df['pest_disease'].values else "No control measures"

class FertilizerService:
    def __init__(self):
        try:
            self.fertilizers_df = pd.read_csv('data/fertilizer_data.csv')
            self.fertilizers = {row['crop_name']: {
                "nitrogen": row['nitrogen_kg_per_acre'],
                "phosphorus": row['phosphorus_kg_per_acre'],
                "potassium": row['potassium_kg_per_acre'],
                "organic_matter": row['organic_matter_tons_per_acre'],
                "lime": row['lime_kg_per_acre']
            } for _, row in self.fertilizers_df.iterrows()}
            print(f"Loaded fertilizer data for {len(self.fertilizers)} crops")
        except FileNotFoundError:
            print("fertilizer_data.csv not found")
            self.fertilizers = {}
    
    def recommend_fertilizer(self, crop_name):
        fert_data = self.fertilizers.get(crop_name, {})
        return (f"Recommended for {crop_name}:\n"
                f"• Nitrogen: {fert_data.get('nitrogen', 0)} kg/acre\n"
                f"• Phosphorus: {fert_data.get('phosphorus', 0)} kg/acre\n"
                f"• Potassium: {fert_data.get('potassium', 0)} kg/acre\n"
                f"• Organic Matter: {fert_data.get('organic_matter', 0)} tons/acre\n"
                f"• Lime: {fert_data.get('lime', 0)} kg/acre") if fert_data else "No recommendation"

class IrrigationService:
    def recommend_irrigation(self, crop_name, water_availability):
        return ("Drip irrigation, consider mulching" if water_availability == "Low" else
                "Flood irrigation, 5-10cm depth" if "Rice" in crop_name else
                "Sprinkler irrigation" if water_availability == "High" else
                "Furrow irrigation, every 7-10 days")

class MarketService:
    def __init__(self):
        self.market_prices = {
            "Rice (Aman)": 30000, "Rice (Boro)": 35000, "Rice (Aus)": 28000,
            "Wheat": 32000, "Jute": 40000, "Maize": 25000, "Potato": 20000,
            "Onion": 30000, "Garlic": 60000, "Tomato": 25000, "Chili": 50000,
            "Banana": 20000, "Mango": 40000
        }
    
    def get_price(self, crop_name):
        return f"{self.market_prices.get(crop_name, 0):,} BDT/ton" if crop_name in self.market_prices else "Not available"

class WeatherService:
    def get_weather(self):
        return {
            "Temperature": "32°C", "Humidity": "85%", "Rainfall": "15mm",
            "Wind Speed": "10 km/h", "Forecast": "Heavy monsoon rains expected"
        }

class ReportService:
    def __init__(self, crop_service, market_service):
        self.crop_service = crop_service
        self.market_service = market_service
    
    def generate_crop_report(self, user_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM users WHERE id = ?', (user_id,))
        user_name = cursor.fetchone()[0]
        cursor.execute('SELECT * FROM lands WHERE user_id = ?', (user_id,))
        lands = cursor.fetchall()
        data = [{"Crop": c, "Season": i["season"], "Soil Type": i["soil_type"],
                 "Yield (t/ha)": f"{i['yield_per_hectare']:.2f}",
                 "Price (BDT/ton)": self.market_service.get_price(c)}
                for c, i in self.crop_service.crops.items() if any(l[4].lower() == i["soil_type"].lower() for l in lands)]
        conn.close()
        return pd.DataFrame(data).to_csv(index=False), user_name, lands

# Enhanced Login Dialog with Animations
class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BDSoil Login")
        self.setModal(True)
        self.resize(400, 250)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #006a4e, stop:1 #f42a4d);
            }
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.9);
                border: 2px solid #006a4e;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #006a4e;
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f42a4d;
            }
            QLabel {
                color: white;
                font-weight: bold;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Title with animation
        self.title = QLabel("🌱 Welcome to BDSoil 🌱")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-size: 20px; color: white; margin: 10px;")
        layout.addWidget(self.title)
        
        # Particle effect
        self.particles = ParticleWidget()
        self.particles.setFixedHeight(50)
        layout.addWidget(self.particles)
        
        form_layout = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        
        username_label = QLabel("Username:")
        password_label = QLabel("Password:")
        
        form_layout.addRow(username_label, self.username)
        form_layout.addRow(password_label, self.password)
        layout.addLayout(form_layout)
        
        button_layout = QHBoxLayout()
        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.login_clicked)
        self.register_button = QPushButton("Register")
        self.register_button.clicked.connect(self.open_register)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.login_button)
        button_layout.addWidget(self.register_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Animate dialog entrance
        AnimationHelper.fade_in(self)
        self.particles.emit_particles(15)
        
        # Pulse the title
        AnimationHelper.pulse(self.title)
        
        self.username.setFocus()
    
    def login_clicked(self):
        username, password = self.username.text().strip(), self.password.text()
        if not username or not password:
            QMessageBox.warning(self, "Error", "Enter both fields.")
            return
        
        # Show loading animation
        self.login_button.setText("Logging in...")
        self.login_button.setEnabled(False)
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ? AND password = ?', (username, hashed_password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            self.user_id = user[0]
            # Success animation
            self.particles.emit_particles(30)
            QTimer.singleShot(500, self.accept)
        else:
            self.login_button.setText("Login")
            self.login_button.setEnabled(True)
            QMessageBox.warning(self, "Error", "Invalid credentials.")

    def open_register(self):
        register_dialog = RegisterDialog()
        if register_dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Success", "Registration successful! Login now.")

class RegisterDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BDSoil Registration")
        self.setModal(True)
        self.resize(400, 350)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #006a4e, stop:1 #f42a4d);
            }
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.9);
                border: 2px solid #006a4e;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton {
                background-color: #006a4e;
                color: white;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #f42a4d;
            }
            QLabel {
                color: white;
                font-weight: bold;
            }
        """)
        
        layout = QFormLayout()
        self.username, self.password, self.nid, self.name, self.phone = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        
        for field, label in [("username", "Username:"), ("password", "Password:"), ("nid", "NID:"), ("name", "Full Name:"), ("phone", "Phone:")]:
            widget = getattr(self, field)
            layout.addRow(QLabel(label), widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.register_user)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)
        
        # Animate dialog entrance
        AnimationHelper.fade_in(self)
    
    def register_user(self):
        fields = [getattr(self, f).text().strip() for f in ['username', 'password', 'nid', 'name', 'phone']]
        if not all(fields):
            QMessageBox.warning(self, "Error", "All fields required.")
            return
        hashed_password = hashlib.sha256(fields[1].encode()).hexdigest()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password, nid, name, phone) VALUES (?, ?, ?, ?, ?)', 
                          (fields[0], hashed_password, fields[2], fields[3], fields[4]))
            conn.commit()
            self.accept()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Username exists.")
        finally:
            conn.close()

class ProfileDialog(QDialog):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.setWindowTitle("Edit Farmer Profile")
        self.setModal(True)
        self.resize(400, 300)
        layout = QFormLayout()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT username, nid, name, phone, profile_pic FROM users WHERE id = ?', (user_id,))
        data = cursor.fetchone()
        conn.close()
        self.username, self.nid, self.name, self.phone = QLineEdit(data[0]), QLineEdit(data[1]), QLineEdit(data[2]), QLineEdit(data[3])
        self.profile_pic = data[4] or ""
        for field, label in [("username", "Username:"), ("nid", "NID:"), ("name", "Full Name:"), ("phone", "Phone:")]:
            layout.addRow(label, getattr(self, field))
        upload_button = QPushButton("Upload Profile Picture")
        upload_button.clicked.connect(self.upload_picture)
        layout.addRow(upload_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save_profile)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)
    
    def upload_picture(self):
        file, _ = QFileDialog.getOpenFileName(self, "Upload Picture", "", "Images (*.png *.jpg *.jpeg)")
        if file:
            self.profile_pic = file
            QMessageBox.information(self, "Success", "Picture uploaded.")
    
    def save_profile(self):
        fields = [getattr(self, f).text().strip() for f in ['username', 'nid', 'name', 'phone']]
        if not all(fields):
            QMessageBox.warning(self, "Error", "All fields required.")
            return
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET username = ?, nid = ?, name = ?, phone = ?, profile_pic = ? WHERE id = ?',
                          (fields[0], fields[1], fields[2], fields[3], self.profile_pic, self.user_id))
            conn.commit()
            self.accept()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Username exists.")
        finally:
            conn.close()

class LandDialog(QDialog):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.setWindowTitle("Add New Land")
        self.setModal(True)
        self.resize(400, 300)
        layout = QFormLayout()
        self.location = QLineEdit()
        self.area = QLineEdit()
        self.soil_type = QComboBox()
        self.soil_type.addItems(["Clay Loam", "Sandy Loam", "Loam", "Clay", "Sandy"])
        self.gps_coords = QLineEdit()
        self.gps_coords.setPlaceholderText("e.g., 23.6850,90.3563")
        layout.addRow("Location:", self.location)
        layout.addRow("Area (ha):", self.area)
        layout.addRow("Soil Type:", self.soil_type)
        layout.addRow("GPS Coords:", self.gps_coords)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_land)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)

    def save_land(self):
        location = self.location.text().strip()
        try:
            area = float(self.area.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Error", "Area must be a number.")
            return
        soil_type = self.soil_type.currentText()
        gps_coords = self.gps_coords.text().strip()
        if not location or area <= 0 or not soil_type or not gps_coords:
            QMessageBox.warning(self, "Error", "Fill all fields correctly.")
            return
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO lands (user_id, location, area, soil_type, gps_coords) VALUES (?, ?, ?, ?, ?)',
                       (self.user_id, location, area, soil_type, gps_coords))
        conn.commit()
        conn.close()
        self.accept()

class Splitter(QSplitter):
    def __init__(self, parent=None):
        super().__init__(parent)

    def splitterAnimation(self, pos):
        self.moveSplitter(pos, 1)

# Enhanced Main Window with Animations
class MainWindow(QMainWindow):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.setWindowTitle("BDSoil - Smart Agriculture Management")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1000, 700)
        
        # Apply futuristic theme
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #1a1a2e, stop:1 #16213e);
            }
            QListWidget {
                background: rgba(0, 106, 78, 0.8);
                color: white;
                font-size: 14px;
                border-radius: 10px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 12px;
                margin: 2px;
                border-radius: 5px;
            }
            QListWidget::item:hover {
                background: rgba(244, 42, 77, 0.6);
            }
            QListWidget::item:selected {
                background: #f42a4d;
            }
            QTextEdit {
                background: rgba(255, 255, 255, 0.95);
                color: #333;
                border: 2px solid #006a4e;
                border-radius: 10px;
                padding: 10px;
                font-size: 13px;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #006a4e, stop:1 #00a86b);
                color: white;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #f42a4d, stop:1 #ff6b6b);
            }
            QComboBox {
                background: white;
                color: #333;
                border: 2px solid #006a4e;
                border-radius: 5px;
                padding: 5px;
                min-height: 25px;
            }
            QLabel {
                color: white;
            }
        """)

        # Sidebar with enhanced styling
        self.sidebar = QListWidget()
        self.sidebar.setMaximumWidth(220)
        self.sidebar.setMinimumWidth(0)
        self.sidebar.addItems(["🌍 Land Management", "🌱 Crop Recommendations", "💊 Fertilizer Recommendations",
                             "💧 Irrigation Advice", "🐛 Pest Control", "💰 Market Prices", 
                             "☀️ Weather Info", "📊 Reports"])
        self.sidebar.currentRowChanged.connect(self.change_section)

        # Main content area
        self.content = QWidget()
        self.content_layout = QVBoxLayout()
        self.content.setLayout(self.content_layout)

        # Enhanced header with gradient
        self.header = QLabel("BDSoil")
        self.header.setStyleSheet("""
            color: white;
            padding: 10px;
            font-size: 24px;
            font-weight: bold;
            text-align: center;
            background: transparent;
        """)
        
        self.sidebar_toggle = QPushButton("☰")
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        self.sidebar_toggle.setFixedWidth(30)
        
        self.profile_button = QPushButton("👤 Farmer Profile")
        self.logout_button = QPushButton("🚪 Logout")
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(self.sidebar_toggle)
        header_layout.addWidget(self.header)
        header_layout.addStretch()
        header_layout.addWidget(self.profile_button)
        header_layout.addWidget(self.logout_button)
        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        header_widget.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 #f42a4d, stop:0.5 #006a4e, stop:1 #f42a4d);
            border-radius: 10px;
        """)
        header_widget.setFixedHeight(60)  # Fixed height for consistent positioning

        # Footer with animation
        self.footer = QLabel("🌿 BDSoil - Rooted in Heart, Soil, People, and Technology 🌿")
        self.footer.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 #006a4e, stop:0.5 #f42a4d, stop:1 #006a4e);
            color: white;
            padding: 15px;
            text-align: center;
            font-size: 14px;
            font-weight: bold;
            border-radius: 10px;
        """)
        self.footer.setFixedHeight(50)

        # Splitter for sidebar and content
        self.splitter = Splitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.content)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([220, 980])

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(header_widget)
        main_layout.addWidget(self.splitter)
        main_layout.addWidget(self.footer)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Initialize services
        self.crop_service = CropService()
        self.pest_service = PestService()
        self.fertilizer_service = FertilizerService()
        self.irrigation_service = IrrigationService()
        self.market_service = MarketService()
        self.weather_service = WeatherService()
        self.report_service = ReportService(self.crop_service, self.market_service)

        # Create sections
        self.sections = {}
        self.create_land_section()
        self.create_crop_section()
        self.create_fertilizer_section()
        self.create_irrigation_section()
        self.create_pest_section()
        self.create_market_section()
        self.create_weather_section()
        self.create_reports_section()

        self.sidebar.setCurrentRow(0)
        self.show()

        # Connect buttons
        self.profile_button.clicked.connect(self.edit_profile)
        self.logout_button.clicked.connect(self.logout)

        # Animate entrance
        AnimationHelper.fade_in(self)

    def toggle_sidebar(self):
        if self.sidebar.width() > 0:
            self.anim = QVariantAnimation()
            self.anim.setDuration(300)
            self.anim.setStartValue(self.sidebar.width())
            self.anim.setEndValue(0)
            self.anim.setEasingCurve(QEasingCurve.InOutQuad)
            self.anim.valueChanged.connect(self.splitter.splitterAnimation)
            self.anim.start()
            self.sidebar_toggle.setText("☰")
        else:
            self.anim = QVariantAnimation()
            self.anim.setDuration(300)
            self.anim.setStartValue(0)
            self.anim.setEndValue(220)
            self.anim.setEasingCurve(QEasingCurve.InOutQuad)
            self.anim.valueChanged.connect(self.splitter.splitterAnimation)
            self.anim.start()
            self.sidebar_toggle.setText("☰")

    def change_section(self, index):
        if self.content_layout.count() > 0:
            old_widget = self.content_layout.takeAt(0).widget()
            if old_widget:
                old_widget.setParent(None)
        new_section = self.sections[index]
        self.content_layout.addWidget(new_section)
        AnimationHelper.fade_in(new_section)

    def edit_profile(self):
        dialog = ProfileDialog(self.user_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Success", "Profile updated!")

    def logout(self):
        self.close()
        login_dialog = LoginDialog()
        if login_dialog.exec() == QDialog.DialogCode.Accepted and hasattr(login_dialog, 'user_id'):
            new_window = MainWindow(login_dialog.user_id)
            new_window.show()

    def create_land_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>🌍 Land Management</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.land_particles = ParticleWidget()
        self.land_particles.setFixedHeight(100)
        button_add = QPushButton("Add New Land")
        button_view = QPushButton("View My Lands")
        self.land_output = QTextEdit()
        self.land_output.setReadOnly(True)
        layout.addWidget(label)
        layout.addWidget(self.land_particles)
        layout.addWidget(button_add)
        layout.addWidget(button_view)
        layout.addWidget(self.land_output, stretch=1)
        section.setLayout(layout)
        self.sections[0] = section
        button_add.clicked.connect(self.add_land)
        button_view.clicked.connect(self.view_lands)

    def add_land(self):
        dialog = LandDialog(self.user_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Success", "Land added!")
            self.view_lands()
            self.land_particles.emit_particles(20)

    def view_lands(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM lands WHERE user_id = ?', (self.user_id,))
        lands = cursor.fetchall()
        conn.close()
        self.land_output.setText("\n".join([f"📍 {l[2]} - {l[3]} ha, {l[4]}, GPS: {l[5]}" for l in lands]) if lands else "No lands registered.")
        self.land_particles.emit_particles(15)

    def create_crop_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>🌱 Crop Recommendations</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.crop_particles = ParticleWidget()
        self.crop_particles.setFixedHeight(100)
        soil_label = QLabel("Soil Type:")
        self.soil_combo = QComboBox()
        self.soil_combo.addItems(["Clay Loam", "Sandy Loam", "Loam", "Clay", "Sandy"])
        season_label = QLabel("Season:")
        self.season_combo = QComboBox()
        self.season_combo.addItems(["Kharif (Monsoon)", "Rabi (Winter)", "Summer", "Year Round"])
        button = QPushButton("Get Recommendations")
        self.crop_output = QTextEdit()
        self.crop_output.setReadOnly(True)
        layout.addWidget(label)
        layout.addWidget(self.crop_particles)
        layout.addWidget(soil_label)
        layout.addWidget(self.soil_combo)
        layout.addWidget(season_label)
        layout.addWidget(self.season_combo)
        layout.addWidget(button)
        layout.addWidget(self.crop_output, stretch=1)
        section.setLayout(layout)
        self.sections[1] = section
        button.clicked.connect(self.get_crop_recommendations)

    def get_crop_recommendations(self):
        recommendations = self.crop_service.recommend_crop(self.soil_combo.currentText(), self.season_combo.currentText())
        text = "\n".join([f"✓ {c}\n  Yield: {self.crop_service.crops[c]['yield_per_hectare']:.2f} t/ha, Water: {self.crop_service.crops[c]['water_need']}"
                          for c in recommendations])
        self.crop_output.setText(text)
        self.crop_particles.emit_particles(25)
        AnimationHelper.pulse(self.crop_output)

    def create_fertilizer_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>💊 Fertilizer Recommendations</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.fert_particles = ParticleWidget()
        self.fert_particles.setFixedHeight(100)
        crop_label = QLabel("Select Crop:")
        self.fert_crop_combo = QComboBox()
        self.fert_crop_combo.addItems(list(self.crop_service.crops.keys()))
        button = QPushButton("Get Recommendation")
        self.fert_output = QTextEdit()
        self.fert_output.setReadOnly(True)
        layout.addWidget(label)
        layout.addWidget(self.fert_particles)
        layout.addWidget(crop_label)
        layout.addWidget(self.fert_crop_combo)
        layout.addWidget(button)
        layout.addWidget(self.fert_output, stretch=1)
        section.setLayout(layout)
        self.sections[2] = section
        button.clicked.connect(self.get_fertilizer_recommendation)

    def get_fertilizer_recommendation(self):
        self.fert_output.setText(self.fertilizer_service.recommend_fertilizer(self.fert_crop_combo.currentText()))
        self.fert_particles.emit_particles(20)
        AnimationHelper.fade_in(self.fert_output)

    def create_irrigation_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>💧 Irrigation Advice</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.irrig_particles = ParticleWidget()
        self.irrig_particles.setFixedHeight(100)
        crop_label = QLabel("Crop:")
        water_label = QLabel("Water Availability:")
        self.irrig_crop_combo = QComboBox()
        self.irrig_crop_combo.addItems(list(self.crop_service.crops.keys()))
        self.water_combo = QComboBox()
        self.water_combo.addItems(["Low", "Medium", "High"])
        button = QPushButton("Get Advice")
        self.irrig_output = QTextEdit()
        self.irrig_output.setReadOnly(True)
        layout.addWidget(label)
        layout.addWidget(self.irrig_particles)
        layout.addWidget(crop_label)
        layout.addWidget(self.irrig_crop_combo)
        layout.addWidget(water_label)
        layout.addWidget(self.water_combo)
        layout.addWidget(button)
        layout.addWidget(self.irrig_output, stretch=1)
        section.setLayout(layout)
        self.sections[3] = section
        button.clicked.connect(self.get_irrigation_advice)

    def get_irrigation_advice(self):
        self.irrig_output.setText(self.irrigation_service.recommend_irrigation(self.irrig_crop_combo.currentText(), self.water_combo.currentText()))
        self.irrig_particles.emit_particles(20)
        AnimationHelper.pulse(self.irrig_output)

    def create_pest_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>🐛 Pest Control</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.pest_particles = ParticleWidget()
        self.pest_particles.setFixedHeight(100)
        desc_label = QLabel("Describe Pest/Disease:")
        self.pest_input = QLineEdit()
        self.pest_input.setPlaceholderText("e.g., Brown Planthopper")
        button = QPushButton("Identify")
        self.pest_output = QTextEdit()
        self.pest_output.setReadOnly(True)
        layout.addWidget(label)
        layout.addWidget(self.pest_particles)
        layout.addWidget(desc_label)
        layout.addWidget(self.pest_input)
        layout.addWidget(button)
        layout.addWidget(self.pest_output, stretch=1)
        section.setLayout(layout)
        self.sections[4] = section
        button.clicked.connect(self.identify_pest)

    def identify_pest(self):
        description = self.pest_input.text().strip()
        if not description:
            self.pest_output.setText("Enter a description.")
            return
        pest = self.pest_service.identify_pest(description)
        self.pest_output.setText(f"Pest: {pest}\nControl: {self.pest_service.get_control(pest)}")
        self.pest_particles.emit_particles(20)
        AnimationHelper.fade_in(self.pest_output)

    def create_market_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>💰 Market Prices</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.market_particles = ParticleWidget()
        self.market_particles.setFixedHeight(100)
        crop_label = QLabel("Select Crop:")
        self.market_crop_combo = QComboBox()
        self.market_crop_combo.addItems(list(self.market_service.market_prices.keys()))
        button = QPushButton("Get Price")
        self.market_output = QTextEdit()
        self.market_output.setReadOnly(True)
        layout.addWidget(label)
        layout.addWidget(self.market_particles)
        layout.addWidget(crop_label)
        layout.addWidget(self.market_crop_combo)
        layout.addWidget(button)
        layout.addWidget(self.market_output, stretch=1)
        section.setLayout(layout)
        self.sections[5] = section
        button.clicked.connect(self.get_market_price)

    def get_market_price(self):
        crop = self.market_crop_combo.currentText()
        self.market_output.setText(f"Price for {crop}: {self.market_service.get_price(crop)}")
        self.market_particles.emit_particles(20)
        AnimationHelper.pulse(self.market_output)

    def create_weather_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>☀️ Weather Info</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.weather_particles = ParticleWidget()
        self.weather_particles.setFixedHeight(100)
        button = QPushButton("Get Weather")
        self.weather_output = QTextEdit()
        self.weather_output.setReadOnly(True)
        layout.addWidget(label)
        layout.addWidget(self.weather_particles)
        layout.addWidget(button)
        layout.addWidget(self.weather_output, stretch=1)
        section.setLayout(layout)
        self.sections[6] = section
        button.clicked.connect(self.get_weather)

    def get_weather(self):
        self.weather_output.setText("\n".join([f"{k}: {v}" for k, v in self.weather_service.get_weather().items()]))
        self.weather_particles.emit_particles(20)
        AnimationHelper.fade_in(self.weather_output)

    def create_reports_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>📊 Reports</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.report_particles = ParticleWidget()
        self.report_particles.setFixedHeight(100)
        button_pdf = QPushButton("Generate PDF Report")
        button_chart = QPushButton("Profit/Loss Chart")
        self.report_output = QTextEdit()
        self.report_output.setReadOnly(True)
        self.figure = plt.figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.hide()
        layout.addWidget(label)
        layout.addWidget(self.report_particles)
        layout.addWidget(button_pdf)
        layout.addWidget(button_chart)
        layout.addWidget(self.report_output, stretch=1)
        layout.addWidget(self.canvas, stretch=1)
        section.setLayout(layout)
        self.sections[7] = section
        button_pdf.clicked.connect(self.generate_pdf_report)
        button_chart.clicked.connect(self.generate_profit_loss_chart)

    def generate_pdf_report(self):
        csv_data, user_name, lands = self.report_service.generate_crop_report(self.user_id)
        pdf_name = f"{user_name}_BDSoil_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        c = canvas.Canvas(pdf_name, pagesize=letter)
        width, height = letter
        c.setFont("Helvetica-Bold", 18)
        c.drawString(100, height - 100, "BDSoil - Agricultural Data Management Report")
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 130, f"User: {user_name}")
        c.drawString(100, height - 150, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.showPage()

        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, height - 100, "Land Information")
        c.setFont("Helvetica", 12)
        y = height - 130
        for land in lands:
            c.drawString(100, y, f"Location: {land[2]} | Area: {land[3]} ha | Soil: {land[4]} | GPS: {land[5]}")
            y -= 20
            if y < 100:
                c.showPage()
                y = height - 100
        c.showPage()

        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, height - 100, "Crop Recommendations")
        c.setFont("Helvetica", 12)
        y = height - 130
        for crop in self.crop_service.crops:
            if any(land[4].lower() == self.crop_service.crops[crop]["soil_type"].lower() for land in lands):
                c.drawString(100, y, f"Crop: {crop} | Season: {self.crop_service.crops[crop]['season']} | Yield: {self.crop_service.crops[crop]['yield_per_hectare']:.2f} t/ha")
                y -= 20
                if y < 100:
                    c.showPage()
                    y = height - 100
        c.showPage()

        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, height - 100, "Irrigation & Fertilizer Advice")
        c.setFont("Helvetica", 12)
        y = height - 130
        for crop in self.crop_service.crops:
            if any(land[4].lower() == self.crop_service.crops[crop]["soil_type"].lower() for land in lands):
                irr = self.irrigation_service.recommend_irrigation(crop, "Medium")
                fert = self.fertilizer_service.recommend_fertilizer(crop)
                c.drawString(100, y, f"Crop: {crop}")
                y -= 20
                c.drawString(100, y, f"Irrigation: {irr}")
                y -= 20
                c.drawString(100, y, f"Fertilizer: {fert.split('\n')[0]}...")
                y -= 20
                if y < 100:
                    c.showPage()
                    y = height - 100
        c.showPage()

        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, height - 100, "Market Prices")
        c.setFont("Helvetica", 12)
        y = height - 130
        for crop in self.crop_service.crops:
            price = self.market_service.get_price(crop)
            c.drawString(100, y, f"Crop: {crop} | Price: {price}")
            y -= 20
            if y < 100:
                c.showPage()
                y = height - 100
        c.showPage()

        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, height - 100, "Pest & Disease Control")
        c.setFont("Helvetica", 12)
        y = height - 130
        c.drawString(100, y, "No pest data recorded.")
        y -= 20
        c.showPage()

        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, height - 100, "Activity Log")
        c.setFont("Helvetica", 12)
        y = height - 130
        activities = ["Crops recommended", "Reports generated"]
        for activity in activities:
            c.drawString(100, y, f"- {activity}")
            y -= 20
            if y < 100:
                c.showPage()
                y = height - 100
        c.showPage()

        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, height - 100, "Weather Information")
        c.setFont("Helvetica", 12)
        y = height - 130
        weather = self.weather_service.get_weather()
        for k, v in weather.items():
            c.drawString(100, y, f"{k}: {v}")
            y -= 20
            if y < 100:
                c.showPage()
                y = height - 100
        c.save()
        self.report_output.setText(f"✅ PDF generated: {pdf_name}")
        self.report_particles.emit_particles(20)
        AnimationHelper.fade_in(self.report_output)

    def generate_profit_loss_chart(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM lands WHERE user_id = ?', (self.user_id,))
        lands = cursor.fetchall()
        conn.close()
        crops = [c for c in self.crop_service.crops if any(l[4].lower() == self.crop_service.crops[c]["soil_type"].lower() for l in lands)]
        crop_costs = {"Rice (Aman)": 5000, "Rice (Boro)": 6000, "Wheat": 4000, "Maize": 3000, "Tomato": 2500}  # Assumed costs
        yield_data = {c: self.crop_service.crops[c]['yield_per_hectare'] for c in crops}
        profits = [self.market_service.market_prices.get(c, 0) * yield_data.get(c, 0) - crop_costs.get(c, 0) for c in crops]
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        colors = ['green' if p >= 0 else 'red' for p in profits]
        bars = ax.bar(crops, profits, color=colors)
        ax.set_title("Profit/Loss per Crop", fontsize=16)
        ax.set_xlabel("Crops", fontsize=12)
        ax.set_ylabel("Profit/Loss (BDT)", fontsize=12)
        for bar, p in zip(bars, profits):
            ax.text(bar.get_x() + bar.get_width()/2, p + (100 if p >= 0 else -100), f'{p:.2f}', ha='center', va='bottom', color='black')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        self.canvas.draw()
        self.canvas.show()
        self.report_output.setText("📊 Profit/Loss chart generated.")
        self.report_particles.emit_particles(20)
        AnimationHelper.pulse(self.canvas)

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    with open('style.qss', 'w') as f:
        f.write("""
            QMainWindow { background-color: white; color: black; font-family: Arial, Helvetica, sans-serif; }
            QSplitter::handle { background-color: #f42a4d; width: 5px; }
            QPushButton { background-color: #006a4e; color: white; border-radius: 5px; padding: 5px; min-width: 150px; }
            QPushButton:hover { background-color: #f42a4d; }
            QTextEdit { background-color: white; color: black; border: 2px solid #006a4e; border-radius: 3px; padding: 5px; }
            QLineEdit { background-color: white; color: black; border: 2px solid #006a4e; border-radius: 3px; padding: 5px; }
            QLineEdit:focus { border: 2px solid #006a4e; }
            QComboBox { background-color: white; color: black; border: 2px solid #006a4e; border-radius: 3px; padding: 5px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background-color: white; color: black; }
            QDialog { background-color: white; color: black; }
        """)
    with open('style.qss', 'r') as f:
        app.setStyleSheet(f.read())

    login_dialog = LoginDialog()
    if login_dialog.exec() == QDialog.DialogCode.Accepted and hasattr(login_dialog, 'user_id'):
        window = MainWindow(login_dialog.user_id)
        window.show()
    else:
        sys.exit(0)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM lands WHERE user_id = ?', (login_dialog.user_id,))
    if cursor.fetchone()[0] == 0 and QMessageBox.question(None, "No Lands", "Add a land?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
        LandDialog(login_dialog.user_id).exec()
    conn.close()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
