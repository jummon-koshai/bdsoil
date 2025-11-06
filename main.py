import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(stored_hash: str, provided_password: str) -> bool:
    return stored_hash == hash_password(provided_password)

import os
import sys
import re
import sqlite3
import random
import math
import json
import requests
from datetime import datetime

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QFileDialog, QGraphicsOpacityEffect, QSizePolicy, QGraphicsView,
    QGraphicsScene, QGraphicsEllipseItem, QProgressBar, QInputDialog,
    QScrollArea,
)

from PySide6.QtCore import (
    Qt, QSize, QPropertyAnimation, QTimer, QEasingCurve,
    QParallelAnimationGroup, QSequentialAnimationGroup, QPointF,
    Signal, QObject, QRectF, QVariantAnimation, QUrl, Slot,
)

from PySide6.QtGui import QBrush, QColor, QPen, QLinearGradient, QPainter

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


# Database Setup
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

from PySide6.QtCore import QObject, Signal, Slot
import json

class Bridge(QObject):
    locationPicked = Signal(float, float, str)

    @Slot(str)
    def receive(self, message):
        try:
            data = json.loads(message)
            lat = float(data['lat'])
            lng = float(data['lng'])
            addr = str(data['address'])
            print(f"JS to Python: {lat}, {lng} to {addr}")
            self.locationPicked.emit(lat, lng, addr)
        except Exception as e:
            print("Bridge error:", e)

# ==============================================================
#   Bridge
# ==============================================================
class Bridge(QObject):
    locationPicked = Signal(float, float, str)

    @Slot(str)
    def receive(self, message):
        try:
            data = json.loads(message)
            lat = float(data['lat'])
            lng = float(data['lng'])
            addr = str(data['address'])
            print(f"JS to Python: {lat}, {lng} to {addr}")
            self.locationPicked.emit(lat, lng, addr)
        except Exception as e:
            print("Bridge error:", e)

# ==============================================================
#   LandDialog (UNCHANGED)
# ==============================================================
class LandDialog(QDialog):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.setWindowTitle("Add New Land")
        self.setModal(True)
        self.resize(560, 650)

        # === 1. BRIDGE FIRST ===
        self.bridge = Bridge()
        self.bridge.locationPicked.connect(self.on_map_pick)
        self.bridge.locationPicked.connect(lambda lat, lng, addr: print(f"RECEIVED FROM JS: {lat}, {lng} to {addr}"))

        # === 2. GEOLOCATOR (optional) ===
        try:
            from geopy.geocoders import Nominatim
            self.geolocator = Nominatim(user_agent="bdsoil-app-v1")
        except ImportError:
            self.geolocator = None
            print("geopy not installed — reverse geocoding disabled")

        layout = QFormLayout()

        # Location
        self.location = QLineEdit()
        self.location.setPlaceholderText("Auto-filled from map...")
        layout.addRow("Location:", self.location)

        # Area
        self.area = QLineEdit()
        self.area.setPlaceholderText("e.g. 2.5")
        layout.addRow("Area (ha):", self.area)

        # Soil Type
        self.soil_type = QComboBox()
        self.soil_type.addItems(["Clay Loam", "Sandy Loam", "Loam", "Clay", "Sandy"])
        layout.addRow("Soil Type:", self.soil_type)

        # GPS Coords
        self.gps_coords = QLineEdit()
        self.gps_coords.setPlaceholderText("e.g. 23.8103, 90.4125")
        self.gps_coords.textChanged.connect(self.on_gps_changed)
        layout.addRow("GPS Coords:", self.gps_coords)

        # Fetch from GPS
        self.fetch_btn = QPushButton("Fetch address from GPS")
        self.fetch_btn.clicked.connect(self.fetch_from_gps)
        self.fetch_btn.setEnabled(False)
        layout.addRow("", self.fetch_btn)

        # Map Label
        map_label = QLabel("<b>Click on map to select location</b>")
        map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addRow(map_label)

        # Map Container
        map_container = QWidget()
        map_container.setFixedHeight(300)
        map_layout = QVBoxLayout(map_container)

        self.map_status = QLabel("Loading map...")
        self.map_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        map_layout.addWidget(self.map_status)

        # === 3. WEBVIEW + BRIDGE SETUP (FIXED ORDER!) ===
        self.webview = QWebEngineView()
        self.webview.loadFinished.connect(self.on_map_loaded)

        # UNLOCK WEBENGINE
        settings = self.webview.page().settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)

        # DEBUG JS CONSOLE
        def log_js(level, msg, line, src):
            print(f"JS: {msg} (line {line})")
        self.webview.page().javaScriptConsoleMessage = log_js

        # === CRITICAL: REGISTER BRIDGE BEFORE setWebChannel ===
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.webview.page().setWebChannel(self.channel)

        # LOAD HTML
        html_path = os.path.join(os.path.dirname(__file__), "map_picker.html")
        if not os.path.exists(html_path):
            self.map_status.setText("map_picker.html missing!")
            self.map_status.setStyleSheet("color: red;")
        else:
            self.webview.setUrl(QUrl.fromLocalFile(html_path))

        map_layout.addWidget(self.webview)
        layout.addRow(map_container)

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addRow("", self.progress)

        # Current Location
        self.auto_gps_btn = QPushButton("Use My Current Location")
        self.auto_gps_btn.clicked.connect(self.fetch_current_location)
        layout.addRow("", self.auto_gps_btn)

        # OK/Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_land)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

        # GPS Timer
        self.gps_timer = QTimer(self)
        self.gps_timer.setSingleShot(True)
        self.gps_timer.timeout.connect(self.fetch_from_gps)

    def on_map_pick(self, lat, lng, address):
        print(f"AUTO-FILL: {lat}, {lng} to {address}")
        self.gps_coords.setText(f"{lat:.6f}, {lng:.6f}")
        self.location.setText(address)
        self.location.setStyleSheet("color: green; font-weight: bold;")

    def on_gps_changed(self, text):
        valid = self.is_valid_gps(text.strip())
        self.fetch_btn.setEnabled(valid)
        if valid:
            self.gps_timer.start(800)
        else:
            self.gps_timer.stop()

    @staticmethod
    def is_valid_gps(txt):
        return bool(re.fullmatch(r'^[-+]?\d*\.?\d+,\s*[-+]?\d*\.?\d+$', txt))

    def fetch_from_gps(self):
        txt = self.gps_coords.text().strip()
        if not self.is_valid_gps(txt) or not self.geolocator:
            return
        self.progress.show()
        self.fetch_btn.setEnabled(False)
        self.gps_timer.stop()
        try:
            lat, lng = map(float, [p.strip() for p in txt.split(',')])
            loc = self.geolocator.reverse((lat, lng), timeout=10)
            addr = loc.address if loc else f"{lat}, {lng}"
            self.location.setText(addr)
            self.location.setStyleSheet("color: green; font-weight: bold;")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Geocode failed:\n{e}")
        finally:
            self.progress.hide()
            self.fetch_btn.setEnabled(True)

    def fetch_current_location(self):
        self.progress.show()
        self.auto_gps_btn.setEnabled(False)
        try:
            r = requests.get('https://ipapi.co/json/', timeout=10)
            if r.status_code == 200:
                d = r.json()
                lat, lng = d.get('latitude'), d.get('longitude')
                addr = f"{d.get('city')}, {d.get('region')}, {d.get('country_name')}".strip(", ")
                if lat and lng:
                    self.gps_coords.setText(f"{lat}, {lng}")
                    self.location.setText(addr or f"{lat}, {lng}")
                    self.location.setStyleSheet("color: green; font-weight: bold;")
                    return
        except: pass
        try:
            r = requests.get('https://ipinfo.io/json', timeout=10)
            d = r.json()
            loc = d.get('loc', '').split(',')
            if len(loc) == 2:
                lat, lng = float(loc[0]), float(loc[1])
                self.gps_coords.setText(f"{lat}, {lng}")
                self.location.setText(f"{d.get('city')}, {d.get('country')}")
                self.location.setStyleSheet("color: green; font-weight: bold;")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Location failed:\n{e}")
        finally:
            self.progress.hide()
            self.auto_gps_btn.setEnabled(True)

    def on_map_loaded(self, ok):
        self.map_status.setText("Map ready – click to select!" if ok else "Map failed")
        self.map_status.setStyleSheet("color: green;" if ok else "color: red;")

    def save_land(self):
        loc = self.location.text().strip()
        if not loc:
            QMessageBox.warning(self, "Error", "Location required.")
            return
        try:
            area = float(self.area.text().strip())
            if area <= 0: raise ValueError
        except:
            QMessageBox.warning(self, "Error", "Area must be positive.")
            return
        soil = self.soil_type.currentText()
        gps = self.gps_coords.text().strip()
        if gps and not self.is_valid_gps(gps):
            QMessageBox.warning(self, "Error", "Invalid GPS format.")
            return

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO lands (user_id, location, area, soil_type, gps_coords) VALUES (?,?,?,?,?)",
                (self.user_id, loc, area, soil, gps or None)
            )
            conn.commit()
            QMessageBox.information(self, "Success", "Land added!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()

# ==============================================================
#   MainWindow — FULLY FIXED
# ==============================================================
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
            QScrollArea {
                background: transparent;
                border: none;
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

        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setMaximumWidth(220)
        self.sidebar.addItems([
            "Land Management", "Crop Recommendations", "Fertilizer Recommendations",
            "Irrigation Advice", "Pest Control", "Market Prices", 
            "Weather Info", "Reports"
        ])
        self.sidebar.currentRowChanged.connect(self.change_section)

        # Content area
        self.content = QWidget()
        self.content_layout = QVBoxLayout()
        self.content.setLayout(self.content_layout)

        # Header
        self.header = QLabel("BDSoil")
        self.header.setStyleSheet("color: white; padding: 10px; font-size: 24px; font-weight: bold;")
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.sidebar_toggle = QPushButton("Menu")
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        self.sidebar_toggle.setFixedWidth(30)

        self.profile_button = QPushButton("Farmer Profile")
        self.logout_button = QPushButton("Logout")

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
        header_widget.setFixedHeight(60)

        # Footer
        self.footer = QLabel("BDSoil - Rooted in Heart, Soil, People, and Technology")
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

        # Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
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

        # Connect buttons
        self.profile_button.clicked.connect(self.edit_profile)
        self.logout_button.clicked.connect(self.logout)

        # Animate entrance
        AnimationHelper.fade_in(self)

    def toggle_sidebar(self):
        current = self.splitter.sizes()[0]
        target = 0 if current > 0 else 220
        self.anim = QVariantAnimation()
        self.anim.setDuration(300)
        self.anim.setStartValue(current)
        self.anim.setEndValue(target)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.valueChanged.connect(lambda v: self.splitter.setSizes([v, 1200 - v]))
        self.anim.start()

    def change_section(self, index):
        if self.content_layout.count() > 0:
            old = self.content_layout.takeAt(0).widget()
            if old:
                old.setParent(None)
        new_section = self.sections.get(index)
        if new_section:
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

    # ==================== SECTIONS ====================

    def create_land_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>Land Management</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.land_particles = ParticleWidget()
        self.land_particles.setFixedHeight(100)
        btn_add = QPushButton("Add New Land")
        btn_view = QPushButton("View My Lands")

        # === REPLACE QTextEdit WITH QScrollArea ===
        self.land_output = QScrollArea()
        self.land_output.setWidgetResizable(True)
        self.land_output.setStyleSheet("background: transparent; border: none;")

        layout.addWidget(label)
        layout.addWidget(self.land_particles)
        layout.addWidget(btn_add)
        layout.addWidget(btn_view)
        layout.addWidget(self.land_output, stretch=1)
        section.setLayout(layout)
        self.sections[0] = section
        btn_add.clicked.connect(self.add_land)
        btn_view.clicked.connect(self.view_lands)

    def add_land(self):
        dialog = LandDialog(self.user_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Success", "Land added!")
            self.view_lands()
            self.land_particles.emit_particles(20)

    # ==============================================================
    #   FINAL: view_lands() — NATIVE WIDGETS, SCROLLAREA, DELETE WORKS
    # ==============================================================
    def view_lands(self):
        # Clear old content
        if self.land_output.widget():
            self.land_output.widget().deleteLater()

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, location, area, soil_type, gps_coords FROM lands WHERE user_id = ? ORDER BY id",
            (self.user_id,)
        )
        lands = cur.fetchall()
        conn.close()

        # Create container
        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setSpacing(12)
        container_layout.setContentsMargins(15, 15, 15, 15)

        if not lands:
            no_land = QLabel("No lands registered yet.")
            no_land.setStyleSheet("color: #aaa; font-style: italic; text-align: center;")
            no_land.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.addWidget(no_land)
        else:
            for idx, (land_id, location, area, soil, gps) in enumerate(lands, 1):
                ordinal = self.ordinal_suffix(idx)
                gps_str = f"<br><small style='color: #ccc;'>GPS: {gps}</small>" if gps else ""

                # Land card
                card = QWidget()
                card.setStyleSheet("""
                    background: rgba(0, 106, 78, 0.3);
                    border-left: 5px solid #00a86b;
                    border-radius: 10px;
                    padding: 14px;
                    margin: 4px 0;
                """)
                card_layout = QHBoxLayout()

                # Info
                info = QLabel(
                    f"<b style='color: #f42a4d; font-size: 17px;'>{ordinal} Land</b><br>"
                    f"<b>Location:</b> {location}<br>"
                    f"<b>Area:</b> {area} ha | <b>Soil:</b> {soil}{gps_str}"
                )
                info.setStyleSheet("color: white;")
                info.setWordWrap(True)
                card_layout.addWidget(info, 1)

                # Delete button
                del_btn = QPushButton("Delete")
                del_btn.setStyleSheet("""
                    background: #d32f2f; color: white; border: none;
                    padding: 8px 16px; border-radius: 6px; font-weight: bold;
                    min-width: 80px;
                """)
                del_btn.clicked.connect(lambda _, lid=land_id, pos=idx: self.confirm_delete_land(lid, pos))
                card_layout.addWidget(del_btn)

                card.setLayout(card_layout)
                container_layout.addWidget(card)

        container_layout.addStretch()
        container.setLayout(container_layout)

        # Set to scroll area
        self.land_output.setWidget(container)

    def ordinal_suffix(self, n):
        if 11 <= n % 100 <= 13:
            return f"{n}th"
        return {1: "1st", 2: "2nd", 3: "3rd"}.get(n % 10, f"{n}th")

    def confirm_delete_land(self, land_id, position):
        ordinal = self.ordinal_suffix(position)
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"<b>Delete {ordinal} Land?</b><br><br>ID: {land_id}<br>This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        password, ok = QInputDialog.getText(
            self, "Verify Identity",
            f"Enter <b>your login password</b> to delete {ordinal} land:",
            QLineEdit.Password
        )
        if not ok or not password:
            return

        # Verify password
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE id = ?", (self.user_id,))
        row = cur.fetchone()
        conn.close()

        if not row or not verify_password(row[0], password):
            QMessageBox.critical(self, "Access Denied", "Incorrect password!")
            return

        # Delete
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM lands WHERE id = ? AND user_id = ?", (land_id, self.user_id))
            if cur.rowcount > 0:
                conn.commit()
                QMessageBox.information(self, "Success", f"{ordinal} land deleted!")
                self.view_lands()  # Refresh + reorder
            else:
                QMessageBox.warning(self, "Not Found", "Land not found.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Delete failed:\n{e}")
        finally:
            conn.close()

    # (rest of your methods: create_crop_section, etc. — UNCHANGED)

    def create_crop_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>Crop Recommendations</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.crop_particles = ParticleWidget()
        self.crop_particles.setFixedHeight(100)
        layout.addWidget(label)
        layout.addWidget(self.crop_particles)
        layout.addWidget(QLabel("Soil Type:"))
        self.soil_combo = QComboBox()
        self.soil_combo.addItems(["Clay Loam", "Sandy Loam", "Loam", "Clay", "Sandy"])
        layout.addWidget(self.soil_combo)
        layout.addWidget(QLabel("Season:"))
        self.season_combo = QComboBox()
        self.season_combo.addItems(["Kharif (Monsoon)", "Rabi (Winter)", "Summer", "Year Round"])
        layout.addWidget(self.season_combo)
        btn = QPushButton("Get Recommendations")
        self.crop_output = QTextEdit()
        self.crop_output.setReadOnly(True)
        layout.addWidget(btn)
        layout.addWidget(self.crop_output, stretch=1)
        section.setLayout(layout)
        self.sections[1] = section
        btn.clicked.connect(self.get_crop_recommendations)

    def get_crop_recommendations(self):
        recs = self.crop_service.recommend_crop(self.soil_combo.currentText(), self.season_combo.currentText())
        if not recs:
            self.crop_output.setText("No crops found for this soil/season.")
            return
        text = ""
        for c in recs:
            crop = self.crop_service.crops[c]
            text += f"{c}\n  Yield: {crop['yield_per_hectare']:.2f} t/ha\n  Water: {crop['water_need']}\n\n"
        self.crop_output.setText(text.strip())
        self.crop_particles.emit_particles(25)
        AnimationHelper.pulse(self.crop_output)

    def create_fertilizer_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>Fertilizer Recommendations</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.fert_particles = ParticleWidget()
        self.fert_particles.setFixedHeight(100)
        layout.addWidget(label)
        layout.addWidget(self.fert_particles)
        layout.addWidget(QLabel("Select Crop:"))
        self.fert_crop_combo = QComboBox()
        self.fert_crop_combo.addItems(list(self.crop_service.crops.keys()))
        layout.addWidget(self.fert_crop_combo)
        btn = QPushButton("Get Recommendation")
        self.fert_output = QTextEdit()
        self.fert_output.setReadOnly(True)
        layout.addWidget(btn)
        layout.addWidget(self.fert_output, stretch=1)
        section.setLayout(layout)
        self.sections[2] = section
        btn.clicked.connect(self.get_fertilizer_recommendation)

    def get_fertilizer_recommendation(self):
        text = self.fertilizer_service.recommend_fertilizer(self.fert_crop_combo.currentText())
        self.fert_output.setText(text)
        self.fert_particles.emit_particles(20)
        AnimationHelper.fade_in(self.fert_output)

    def create_irrigation_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>Irrigation Advice</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.irrig_particles = ParticleWidget()
        self.irrig_particles.setFixedHeight(100)
        layout.addWidget(label)
        layout.addWidget(self.irrig_particles)
        layout.addWidget(QLabel("Crop:"))
        self.irrig_crop_combo = QComboBox()
        self.irrig_crop_combo.addItems(list(self.crop_service.crops.keys()))
        layout.addWidget(self.irrig_crop_combo)
        layout.addWidget(QLabel("Water Availability:"))
        self.water_combo = QComboBox()
        self.water_combo.addItems(["Low", "Medium", "High"])
        layout.addWidget(self.water_combo)
        btn = QPushButton("Get Advice")
        self.irrig_output = QTextEdit()
        self.irrig_output.setReadOnly(True)
        layout.addWidget(btn)
        layout.addWidget(self.irrig_output, stretch=1)
        section.setLayout(layout)
        self.sections[3] = section
        btn.clicked.connect(self.get_irrigation_advice)

    def get_irrigation_advice(self):
        text = self.irrigation_service.recommend_irrigation(
            self.irrig_crop_combo.currentText(), self.water_combo.currentText()
        )
        self.irrig_output.setText(text)
        self.irrig_particles.emit_particles(20)
        AnimationHelper.pulse(self.irrig_output)

    def create_pest_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>Pest Control</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.pest_particles = ParticleWidget()
        self.pest_particles.setFixedHeight(100)
        layout.addWidget(label)
        layout.addWidget(self.pest_particles)
        layout.addWidget(QLabel("Describe Pest/Disease:"))
        self.pest_input = QLineEdit()
        self.pest_input.setPlaceholderText("e.g., Brown Planthopper")
        layout.addWidget(self.pest_input)
        btn = QPushButton("Identify")
        self.pest_output = QTextEdit()
        self.pest_output.setReadOnly(True)
        layout.addWidget(btn)
        layout.addWidget(self.pest_output, stretch=1)
        section.setLayout(layout)
        self.sections[4] = section
        btn.clicked.connect(self.identify_pest)

    def identify_pest(self):
        desc = self.pest_input.text().strip()
        if not desc:
            self.pest_output.setText("Please enter a description.")
            return
        pest = self.pest_service.identify_pest(desc)
        control = self.pest_service.get_control(pest)
        self.pest_output.setText(f"Pest: {pest}\n\nControl Measures:\n{control}")
        self.pest_particles.emit_particles(20)
        AnimationHelper.fade_in(self.pest_output)

    def create_market_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>Market Prices</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.market_particles = ParticleWidget()
        self.market_particles.setFixedHeight(100)
        layout.addWidget(label)
        layout.addWidget(self.market_particles)
        layout.addWidget(QLabel("Select Crop:"))
        self.market_crop_combo = QComboBox()
        self.market_crop_combo.addItems(list(self.market_service.market_prices.keys()))
        layout.addWidget(self.market_crop_combo)
        btn = QPushButton("Get Price")
        self.market_output = QTextEdit()
        self.market_output.setReadOnly(True)
        layout.addWidget(btn)
        layout.addWidget(self.market_output, stretch=1)
        section.setLayout(layout)
        self.sections[5] = section
        btn.clicked.connect(self.get_market_price)

    def get_market_price(self):
        crop = self.market_crop_combo.currentText()
        price = self.market_service.get_price(crop)
        self.market_output.setText(f"Current Market Price:\n\n{crop}\n{price}")
        self.market_particles.emit_particles(20)
        AnimationHelper.pulse(self.market_output)

    def create_weather_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>Weather Info</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.weather_particles = ParticleWidget()
        self.weather_particles.setFixedHeight(100)
        layout.addWidget(label)
        layout.addWidget(self.weather_particles)
        btn = QPushButton("Get Current Weather")
        self.weather_output = QTextEdit()
        self.weather_output.setReadOnly(True)
        layout.addWidget(btn)
        layout.addWidget(self.weather_output, stretch=1)
        section.setLayout(layout)
        self.sections[6] = section
        btn.clicked.connect(self.get_weather)

    def get_weather(self):
        weather = self.weather_service.get_weather()
        text = "\n".join([f"{k}: {v}" for k, v in weather.items()])
        self.weather_output.setText(text)
        self.weather_particles.emit_particles(20)
        AnimationHelper.fade_in(self.weather_output)

    def create_reports_section(self):
        section = QWidget()
        layout = QVBoxLayout()
        label = QLabel("<h2>Reports</h2>")
        label.setStyleSheet("color: white; font-size: 20px;")
        self.report_particles = ParticleWidget()
        self.report_particles.setFixedHeight(100)
        btn_pdf = QPushButton("Generate PDF Report")
        btn_chart = QPushButton("Profit/Loss Chart")
        self.report_output = QTextEdit()
        self.report_output.setReadOnly(True)
        layout.addWidget(label)
        layout.addWidget(self.report_particles)
        layout.addWidget(btn_pdf)
        layout.addWidget(btn_chart)
        layout.addWidget(self.report_output, stretch=1)
        section.setLayout(layout)
        self.sections[7] = section

        # Lazy init for matplotlib
        self.figure = None
        self.canvas = None

        btn_pdf.clicked.connect(self.generate_pdf_report)
        btn_chart.clicked.connect(self.generate_profit_loss_chart)

    def generate_pdf_report(self):
        # Safe DB read
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute('SELECT * FROM lands WHERE user_id = ?', (self.user_id,))
        lands = cur.fetchall()
        conn.close()

        if not lands:
            self.report_output.setText("No lands found. Add land first.")
            return

        csv_data, user_name, _ = self.report_service.generate_crop_report(self.user_id)
        pdf_name = f"{user_name}_BDSoil_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        c = canvas.Canvas(pdf_name, pagesize=letter)
        width, height = letter

        # Header
        c.setFont("Helvetica-Bold", 18)
        c.drawString(100, height - 100, "BDSoil - Agricultural Report")
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 130, f"User: {user_name}")
        c.drawString(100, height - 150, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.showPage()

        # Land Info
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, height - 100, "Land Information")
        c.setFont("Helvetica", 12)
        y = height - 130
        for land in lands:
            c.drawString(100, y, f"Location: {land[2]} | Area: {land[3]} ha | Soil: {land[4]} | GPS: {land[5] or '—'}")
            y -= 20
            if y < 100:
                c.showPage()
                y = height - 100
        c.showPage()

        # Crop Recommendations
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, height - 100, "Crop Recommendations")
        c.setFont("Helvetica", 12)
        y = height - 130
        for crop in self.crop_service.crops:
            if any(land[4].lower() == self.crop_service.crops[crop]["soil_type"].lower() for land in lands):
                c.drawString(100, y, f"Crop: {crop} | Yield: {self.crop_service.crops[crop]['yield_per_hectare']:.2f} t/ha")
                y -= 20
                if y < 100:
                    c.showPage()
                    y = height - 100
        c.showPage()

        c.save()
        self.report_output.setText(f"PDF generated: {pdf_name}")
        self.report_particles.emit_particles(20)
        AnimationHelper.fade_in(self.report_output)

    def generate_profit_loss_chart(self):
        # Lazy init matplotlib
        if self.figure is None:
            self.figure = plt.figure(figsize=(10, 6))
            self.canvas = FigureCanvas(self.figure)
            layout = self.sections[7].layout()
            layout.addWidget(self.canvas, stretch=1)

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute('SELECT * FROM lands WHERE user_id = ?', (self.user_id,))
        lands = cur.fetchall()
        conn.close()

        if not lands:
            self.report_output.setText("No lands to analyze.")
            return

        crops = [c for c in self.crop_service.crops 
                if any(l[4].lower() == self.crop_service.crops[c]["soil_type"].lower() for l in lands)]
        if not crops:
            self.report_output.setText("No matching crops for your soil.")
            return

        crop_costs = {"Rice (Aman)": 5000, "Rice (Boro)": 6000, "Wheat": 4000, "Maize": 3000, "Tomato": 2500}
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
            ax.text(bar.get_x() + bar.get_width()/2, p + (100 if p >= 0 else -100), f'{p:.0f}', 
                    ha='center', va='bottom' if p >= 0 else 'top', color='black', fontweight='bold')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        self.canvas.draw()
        self.canvas.setVisible(True)
        self.report_output.setText("Profit/Loss chart generated.")
        self.report_particles.emit_particles(20)
        AnimationHelper.pulse(self.canvas)


# --------------------------------------------------------------
#   main() – SAFE, FAST, CLEAN
# --------------------------------------------------------------
def main():
    print("BDSoil Starting...")
    init_db()

    os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'  
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--no-sandbox --disable-web-security --allow-file-access-from-files'

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    qss_file = 'style.qss'
    if not os.path.exists(qss_file):
        with open(qss_file, 'w', encoding='utf-8') as f:
            f.write("QMainWindow { background: white; }")
    app.setStyleSheet(open(qss_file, 'r', encoding='utf-8').read())

    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted or not hasattr(login, 'user_id'):
        sys.exit(0)

    window = MainWindow(login.user_id)
    window.show()
    print("Dashboard loaded!")

    def check_lands():
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM lands WHERE user_id = ?', (login.user_id,))
        if cur.fetchone()[0] == 0:
            if QMessageBox.question(window, "No Land", "Add your first land?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                LandDialog(login.user_id).exec()
        conn.close()

    QTimer.singleShot(600, check_lands)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
