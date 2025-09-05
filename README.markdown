<img width="393" height="112" alt="image" src="https://github.com/user-attachments/assets/54c9e498-6b2e-42ce-9331-6a78b9cf1320" />







# BDSoil: Rooted in Heart, Soil, People, and Technology

[![Python Version](https://img.shields.io/badge/python-3.13.7-blue.svg)](https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Windows/Linux/macOS](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://qt.io/)
[![Dependencies: PySide6](https://img.shields.io/badge/dependencies-PySide6-green.svg)](https://pypi.org/project/PySide6/)

## Overview

BDSoil is a comprehensive, user-centric desktop application designed to empower farmers in Bangladesh with data-driven insights for sustainable agriculture. Built using PySide6 (Qt for Python), it integrates advanced features such as crop recommendations, pest control, fertilizer advice, and real-time market analytics. The application leverages a SQLite database for user and land management, incorporates animated UI elements for an engaging experience, and generates professional reports in PDF format.

Inspired by Bangladesh's rich agricultural heritage, BDSoil bridges traditional farming practices with modern technology, focusing on soil health, crop yield optimization, and economic viability. It features a futuristic theme with gradient designs, particle animations, and smooth transitions to enhance usability.

## Key Features

- **User Authentication & Profile Management**: Secure login/registration system with hashed passwords. Farmers can edit profiles, including uploading profile pictures.
- **Land Management**: Add, view, and manage agricultural lands with details like location, area (in hectares), soil type, and GPS coordinates.
- **Crop Recommendations**: AI-driven suggestions based on soil type and season, including yield estimates and water needs. Data sourced from a curated Bangladesh-specific crop dataset.
- **Fertilizer & Irrigation Advice**: Personalized recommendations for fertilizers (NPK, organic matter, lime) and irrigation methods tailored to crop and water availability.
- **Pest & Disease Control**: Identify pests from descriptions and provide control measures using a predefined pest database.
- **Market Prices & Weather Insights**: Real-time-like market prices for key crops and weather forecasts (simulated for demo purposes).
- **Reporting & Analytics**: Generate detailed PDF reports on crops, lands, and recommendations. Visualize profit/loss charts using Matplotlib.
- **Enhanced UI/UX**: 
  - Sidebar navigation with animated toggling.
  - Particle effects and fade-in animations for interactive feedback.
  - Gradient themes reflecting Bangladesh's national colors (green and red).
- **Data Integrity**: Uses Pandas for data handling, ReportLab for PDF generation, and Matplotlib for charts.
- **Extensibility**: Modular service classes (e.g., CropService, PestService) for easy integration of real APIs (e.g., weather or market data).

## Tech Stack

- **Framework**: PySide6 (Qt6-based GUI)
- **Database**: SQLite3
- **Data Processing**: Pandas, NumPy
- **Visualization**: Matplotlib
- **PDF Generation**: ReportLab
- **Security**: SHA-256 hashing for passwords
- **Animations**: Qt's QPropertyAnimation, QGraphicsOpacityEffect, and custom particle systems
- **Other Libraries**: Datetime, Hashlib, Random, Math

## Installation

### Prerequisites
- Python 3.12+
- Pip (Python package manager)

### Steps
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/bdsoil.git
   cd bdsoil
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Linux/macOS
   venv\Scripts\activate     # On Windows
   ```

3. Install dependencies:
   ```
   pip install PySide6 pandas reportlab matplotlib numpy
   ```

4. Prepare data files (place in a `data/` directory):
   - `bangladesh_crops.csv`: Crop data (columns: crop_name, season, soil_type, yield_per_acre)
   - `pest_disease_data.csv`: Pest data (columns: pest_disease, control_measure)
   - `fertilizer_data.csv`: Fertilizer data (columns: crop_name, nitrogen_kg_per_acre, etc.)

   *Note*: Sample CSVs are assumed; customize as needed.

5. Run the application:
   ```
   python main.py  # Assuming the script is named main.py
   ```

## Usage

1. **Launch the App**: Execute the main script to open the login dialog.
2. **Register/Login**: Create an account or log in with credentials.
3. **Dashboard Navigation**: Use the sidebar to access sections like Land Management or Crop Recommendations.
4. **Add Land**: In Land Management, add new lands with soil and GPS details.
5. **Get Recommendations**: Select parameters (e.g., soil type, crop) in respective sections for insights.
6. **Generate Reports**: In the Reports section, create PDF reports or view profit/loss charts.
7. **Logout/Profile**: Edit profile or logout via header buttons.

### Example Workflow
- Register as a farmer.
- Add a land parcel (e.g., "Dhaka Farm", 2.5 ha, Clay Loam).
- Navigate to Crop Recommendations: Select "Clay Loam" and "Kharif" for suggestions like Rice (Aman).
- View fertilizer needs and generate a PDF report for planning.

<h2>Screenshots</h2>

<img src="https://github.com/user-attachments/assets/37b8bfea-135b-4fc7-bf4b-add62787bc0e" alt="Login Screen" width="400" style="margin-bottom: 40px;"/>
<img src="https://github.com/user-attachments/assets/68175282-7e95-47bf-a70e-9399cd01e6de" alt="Dashboard" width="400" style="margin-bottom: 40px;"/>

<ul>
  <li><strong>Login Screen</strong>: Features a welcoming animated UI with particle effects and modern input styling.</li>
  <li><strong>Main Dashboard</strong>: Displays a clean sidebar navigation system and a modern gradient UI reflecting Bangladesh's national colors.</li>
</ul>

## Contributing

Contributions are welcome! To get started:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

Please adhere to the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by Bangladesh's agricultural sector and tools like Qt for intuitive UIs.
- Data sources: Hypothetical CSVs; in production, integrate with government APIs (e.g., Bangladesh Agricultural Research Council).
- Built with ❤️ for sustainable farming.

For issues or suggestions, open a GitHub issue or contact the maintainer.
