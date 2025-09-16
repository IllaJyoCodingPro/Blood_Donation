Quickstart

1) Put your data file next to app.py as 'Blood.xlsx' (or set env BLOOD_DATA_PATH to your file path).
   Expected columns (case-insensitive, flexible names accepted):
     - Name, Age, Gender, Phone, Address, Weight, Hemoglobin, Blood Group, (Email optional for notifications).

2) Create a Gmail App Password (Google Account -> Security -> App passwords) and set environment variables:
   - EMAIL_SENDER=your@gmail.com
   - EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

3) Install and run:
   python -m venv .venv && .venv/bin/pip install -r requirements.txt
   BLOOD_DATA_PATH=Blood.xlsx EMAIL_SENDER=you@gmail.com EMAIL_APP_PASSWORD=app-password      .venv/bin/python app.py

4) Open the UI:
   http://localhost:5000/
