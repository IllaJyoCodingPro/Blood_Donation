from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import os, smtplib, ssl
from email.message import EmailMessage

# ---------- Config ----------
DATA_PATH = os.environ.get("BLOOD_DATA_PATH", "data/Blood.xlsx")  # dataset path
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")                     # Gmail address
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")         # Gmail App Password

# ---------- App ----------
app = Flask(__name__, template_folder="templates")
CORS(app)

# ---------- Data Loading ----------
def load_data():
    df = pd.read_excel(DATA_PATH)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    col_map = {
        "name": ["name", "full_name", "donor_name"],
        "age": ["age"],
        "gender": ["gender", "sex"],
        "phone": ["phone", "phone_number", "mobile", "mobile_number", "contact"],
        "address": ["address", "street_address", "location", "area"],
        "weight": ["weight", "body_weight", "weight_(kg)"],
        "hemoglobin": ["hemoglobin", "hb", "hemoglobin_g_dl", "hemoglobin_(g/dl)"],
        "blood_group": ["blood_group", "bloodtype", "blood_type", "group"],
        "email": ["email", "email_id", "mail"]
    }

    selected = {}
    for key, options in col_map.items():
        for opt in options:
            if opt in df.columns:
                selected[key] = opt
                break

    required = ["name", "age", "gender", "phone", "address", "weight", "hemoglobin", "blood_group"]
    missing_required = [k for k in required if k not in selected]
    if missing_required:
        raise RuntimeError(f"Missing required columns: {missing_required}. Found: {list(df.columns)}")

    keep_cols = [selected[k] for k in required] + ([selected["email"]] if "email" in selected else [])
    dfx = df[keep_cols].copy()
    rename_map = {selected[k]: k for k in selected}
    dfx.rename(columns=rename_map, inplace=True)

    dfx.reset_index(inplace=True)
    dfx.rename(columns={"index": "id"}, inplace=True)

    for col in ["age", "weight", "hemoglobin"]:
        if col in dfx.columns:
            dfx[col] = pd.to_numeric(dfx[col], errors="coerce")

    dfx["blood_group"] = dfx["blood_group"].astype(str).str.upper().str.replace(" ", "", regex=False)
    return dfx

DATAFRAME = None
def ensure_data_loaded():
    global DATAFRAME
    if DATAFRAME is None:
        DATAFRAME = load_data()
    return DATAFRAME

# ---------- Routes (Pages) ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Get form inputs
        name = request.form.get("name")
        age = request.form.get("age")
        gender = request.form.get("gender")
        phone = request.form.get("phone")
        email = request.form.get("email")
        blood_group = request.form.get("blood_group")
        area = request.form.get("area")
        weight = request.form.get("weight")
        hemoglobin = request.form.get("hemoglobin")

        # Load or create Excel
        if os.path.exists(DATA_PATH):
            df = pd.read_excel(DATA_PATH)
        else:
            df = pd.DataFrame(columns=[
                "Sno", "Name", "Age", "Gender", "PHONE NUMBER",
                "Email", "Blood group", "Area", "Weight (kg)", "Hemoglobin (g/dl)"
            ])

        # Prepare new row
        new_row = {
            "Sno": len(df) + 1,
            "Name": name,
            "Age": int(age),
            "Gender": gender,
            "PHONE NUMBER": phone,
            "Email": email,
            "Blood group": blood_group,
            "Area": area,
            "Weight (kg)": float(weight),
            "Hemoglobin (g/dl)": float(hemoglobin)
        }

        # Append and save
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(DATA_PATH, index=False)

        # Also refresh global dataframe
        global DATAFRAME
        DATAFRAME = None  

        # Show success message
        return render_template("register.html", success=True)

    return render_template("register.html", success=False)

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/eligibility")
def eligibility():
    return render_template("eligibility.html")

@app.route("/accept")
def accept():
    return render_template("accept.html")

@app.route("/donate")
def donate():
    return render_template("donate.html")

@app.route("/help")
def help_page():
    return render_template("help.html")

@app.route("/find_donour")
def find_donour():
    return render_template("find_donour.html")

# ---------- API Routes ----------
@app.get("/api/predict")
def predict():
    df = ensure_data_loaded()
    bg = request.args.get("blood_group", "").upper().replace(" ", "")
    if not bg:
        return jsonify({"ok": False, "error": "blood_group query parameter is required"}), 400

    subset = df[df["blood_group"] == bg].copy()

    cols = ["id", "name", "age", "gender", "phone", "address", "weight", "hemoglobin", "blood_group"]
    if "email" in df.columns:
        cols.append("email")

    records = subset[cols].to_dict(orient="records")
    return jsonify({"ok": True, "count": len(subset), "blood_group": bg, "records": records})

@app.post("/api/notify")
def notify():
    df = ensure_data_loaded()
    payload = request.get_json(force=True, silent=True) or {}
    ids = payload.get("ids", [])
    subject = payload.get("subject") or "Blood Donation Request"
    message_body = payload.get("message") or "Hello, this is a request for blood donation. Please reply if available."

    if "email" not in df.columns:
        return jsonify({"ok": False, "error": "Email column missing in dataset. Cannot notify."}), 400
    if not isinstance(ids, list) or not ids:
        return jsonify({"ok": False, "error": "Please provide non-empty 'ids' array."}), 400

    emails = df[df["id"].isin(ids)]["email"].dropna().astype(str).unique().tolist()
    if not emails:
        return jsonify({"ok": False, "error": "No valid emails found for selected donors."}), 400
    if not EMAIL_SENDER or not EMAIL_APP_PASSWORD:
        return jsonify({"ok": False, "error": "Email not configured. Set EMAIL_SENDER and EMAIL_APP_PASSWORD env vars."}), 500

    msg = EmailMessage()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_SENDER
    msg["Bcc"] = ", ".join(emails)
    msg["Subject"] = subject
    msg.set_content(message_body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=context)
            server.login(EMAIL_SENDER, EMAIL_APP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to send email: {e}"}), 500

    return jsonify({"ok": True, "sent": len(emails)})

# ---------- Main ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    try:
        ensure_data_loaded()
    except Exception as e:
        print("Data load error:", e)
    app.run(host="0.0.0.0", port=port, debug=True)