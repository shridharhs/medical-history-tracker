import os

from flask import Flask, render_template, request, redirect, session, send_file, url_for
import sqlite3
from datetime import datetime
from fpdf import FPDF
from io import BytesIO
import feedparser
from werkzeug.utils import secure_filename
from flask import jsonify
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DB_NAME = 'database.db'

# Initialize the database
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS patient_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aadhaar TEXT,
            name TEXT,
            age INTEGER,
            gender TEXT,
            mobile TEXT,
            blood_group TEXT,
            doctor TEXT,
            department TEXT,
            illness TEXT,
            prescription TEXT,
            address TEXT,
            date TEXT,
            hospital TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS doctor_blogs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor_name TEXT,
                    hospital_name TEXT,
                    department TEXT,
                    title TEXT,
                    content TEXT,
                    timestamp TEXT
                )''')
        c.execute('''
               CREATE TABLE IF NOT EXISTS doctors (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL,
                   email TEXT UNIQUE NOT NULL,
                   password TEXT NOT NULL,
                   department TEXT,
                   hospital TEXT,
                   photo TEXT
               )
               ''')
        conn.commit()




# Run this once to create a test hospital login
def create_test_hospital():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM hospitals WHERE username = ?", ("hospital1",))
        if not c.fetchone():
            c.execute("INSERT INTO hospitals (username, password) VALUES (?, ?)", ("hospital1", "pass123"))
            conn.commit()

# Initialize DB and test hospital
init_db()
create_test_hospital()

@app.route('/')
def index():
    from datetime import datetime
    return render_template('index.html', current_year=datetime.now().year)


@app.route('/search', methods=['POST', 'GET'])
def search():
    if request.method == 'POST':
        aadhaar = request.form['aadhaar']
        sort = request.form.get('sort', 'desc')  # default to newest first
    else:
        aadhaar = request.args.get('aadhaar')
        sort = request.args.get('sort', 'desc')  # from dropdown GET request

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        order = 'DESC' if sort == 'desc' else 'ASC'
        c.execute(f"SELECT * FROM patient_records WHERE aadhaar = ? ORDER BY date {order}", (aadhaar,))
        records = c.fetchall()

    return render_template("patient_history.html", records=records, aadhaar=aadhaar, sort=sort)



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM hospitals WHERE username = ?", (username,))
            existing = c.fetchone()
            if existing:
                return "Username already exists. <a href='/register'>Try again</a>"

            c.execute("INSERT INTO hospitals (username, password) VALUES (?, ?)", (username, password))
            conn.commit()

        return "Hospital registered successfully! <a href='/login'>Login now</a>"

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM hospitals WHERE username=? AND password=?", (username, password))
            user = c.fetchone()
            if user:
                session['hospital'] = username
                return redirect('/upload')
            else:
                return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('hospital', None)
    return redirect('/')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'hospital' not in session:
        return redirect('/login')

    if request.method == 'POST':
        data = {
            "aadhaar": request.form['aadhaar'],
            "name": request.form['name'],
            "age": request.form['age'],
            "gender": request.form['gender'],
            "mobile": request.form['mobile'],
            "blood_group": request.form['blood_group'],
            "doctor": request.form['doctor'],
            "department": request.form['department'],
            "illness": request.form['illness'],
            "prescription": request.form['prescription'],
            "address": request.form['address'],
            "date": datetime.now().strftime('%Y-%m-%d'),
            "hospital": session['hospital']
        }

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO patient_records 
                (aadhaar, name, age, gender, mobile, blood_group, doctor, department, illness, prescription, address, date, hospital) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (data['aadhaar'], data['name'], data['age'], data['gender'], data['mobile'],
                 data['blood_group'], data['doctor'], data['department'],
                 data['illness'], data['prescription'], data['address'],
                 data['date'], data['hospital'])
            )
            conn.commit()

        return "Record uploaded successfully! <a href='/upload'>Upload another</a>"

    return render_template('upload.html', hospital=session['hospital'])

@app.route('/health_news')
def health_news():
    feed_url = "https://www.thehindu.com/sci-tech/health/feeder/default.rss"  # Replace with WHO or TOI feed if needed
    news_feed = feedparser.parse(feed_url)

    articles = []
    for entry in news_feed.entries[:5]:  # Limit to 5 latest news
        articles.append({
            'title': entry.title,
            'link': entry.link,
            'summary': entry.summary,
            'published': entry.published
        })

    return render_template('health_news.html', articles=articles)
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/doctor_signup', methods=['GET', 'POST'])
def doctor_signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        department = request.form.get('department')
        hospital = request.form.get('hospital')
        file = request.files.get('photo')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute('''
                INSERT INTO doctors (name, email, password, department, hospital, photo)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (name, email, password, department, hospital, filename))
                conn.commit()

            return redirect('/doctor_login')

    return render_template('doctor_signup.html')

@app.route('/doctor_login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM doctors WHERE email=? AND password=?", (email, password))
            doctor = c.fetchone()
            if doctor:
                session['doctor_id'] = doctor[0]
                return redirect('/write_blog')
            else:
                return "Invalid credentials", 401

    return render_template('doctor_login.html')


def clean_text(text):
    if text:
        return (text.replace('–', '-')
                    .replace('—', '-')
                    .replace('’', "'")
                    .replace('‘', "'")
                    .replace('“', '"')
                    .replace('”', '"')
                    .encode('ascii', 'ignore')
                    .decode())
    return ""

@app.route('/get_patient_details', methods=['GET'])
def get_patient_details():
    aadhaar = request.args.get('aadhaar')
    conn = sqlite3.connect('database.db')  # or DB_NAME
    c = conn.cursor()
    c.execute("""
        SELECT name, mobile, blood_group, age, gender, address
        FROM patient_records
        WHERE aadhaar = ?
        ORDER BY id DESC LIMIT 1
    """, (aadhaar,))
    result = c.fetchone()
    conn.close()

    if result:
        return jsonify({
            'name': result[0],
            'mobile': result[1],
            'blood_group': result[2],
            'age': result[3],
            'gender': result[4],
            'address': result[5]
        })
    else:
        return jsonify({'error': 'not_found'})


@app.route('/medicine_lookup')
def medicine_lookup():
    term = request.args.get('term', '').strip()
    if not term:
        return jsonify({'term': term, 'description': 'Please enter a medicine name.'})

    resp = requests.get("https://rxnav.nlm.nih.gov/REST/approximateTerm.json",
                        params={"term": term, "maxEntries": 1})
    cand = resp.json().get("approximateGroup", {}).get("candidate", [])
    if not cand:
        return jsonify({'term': term, 'description': 'No info found.'})

    rxcui = cand[0].get('rxcui')
    if not rxcui:
        return jsonify({'term': term, 'description': 'No RxCUI found.'})

    all_prop = requests.get(f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/allproperties.json").json()
    groups = all_prop.get("propConceptGroup", {})
    descs = []
    for group in groups.values():
        if isinstance(group, list):
            for item in group:
                if 'propValue' in item:
                    descs.append(item['propValue'])
    description = descs[0] if descs else 'No detailed info available.'

    return jsonify({'term': cand[0].get('name', term), 'description': description})

@app.route('/download_single_pdf/<int:record_id>')
def download_single_pdf(record_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM patient_records WHERE id = ?", (record_id,))
        record = c.fetchone()

    if not record:
        return "Record not found."

    pdf = FPDF()
    pdf.add_page()

    # Logos
    pdf.image("static/india_logo.png", x=10, y=12, w=45, h=30)
    pdf.image("static/health_logo.png", x=175, y=12, w=25)
    pdf.image("static/indian_flag.png", x=50, y=1, w=110, h=50)
    pdf.ln(30)

    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text("REPUBLIC OF INDIA"), ln=True, align="C")
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, clean_text("Ministry of Health and Family Welfare"), ln=True, align="C")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, clean_text("National Medical Digital Health Record System (NMDHRS)"), ln=True, align="C")
    pdf.ln(10)

    # Title
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 10, clean_text("Certified Medical Visit Report"), ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    # Intro
    pdf.set_font("Arial", '', 12)
    pdf.multi_cell(0, 8, clean_text(
        "This is to certify that the individual with the following credentials has visited an authorized "
        "healthcare center registered under the Government of India on the date mentioned below.\n"
    ))
    pdf.ln(2)

    # Info Table
    info = [
        ("Aadhaar Number", record[1]),
        ("Name", record[2]),
        ("Age", f"{record[3]} years"),
        ("Gender", record[4]),
        ("Mobile", record[5]),
        ("Blood Group", record[6]),
        ("Doctor", record[7]),
        ("Department", record[8]),
        ("Illness", record[9]),
        ("Prescription", record[10]),
        ("Address", record[11]),
        ("Date of Visit", record[12]),
        ("Hospital", record[13]),
    ]

    label_width = 50
    value_width = 140

    for label, value in info:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(label_width, 8, clean_text(f"{label}:"), border=0)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(value_width, 8, clean_text(str(value)))

    pdf.ln(5)

    # Verification
    pdf.set_fill_color(230, 230, 250)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, clean_text("This document has been digitally verified and authenticated by the Ministry of Health"),
             ln=True, fill=True)
    pdf.ln(5)

    # Disclaimer
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 8, clean_text(
        "Disclaimer:\n"
        "- This document is valid for digital reference only.\n"
        "- Verification can be done through the NMDHRS portal.\n"
        "- Forging or modifying this report is a criminal offense under Indian Cyber Law (IT Act Sec 66C).\n"
        "- Confidential: To be used only by authorized personnel or agencies."
    ))

    # Footer
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, clean_text(f"Issued on: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}"), ln=True, align="R")
    pdf.cell(0, 10, clean_text("This is a system-generated official report and does not require signature."),
             ln=True, align="R")

    # Generate PDF
    buffer = BytesIO()
    pdf_bytes = pdf.output(dest='S').encode('latin1')  # safe now
    buffer.write(pdf_bytes)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True,
                     download_name=f"Gov_Medical_Report_{record[0]}.pdf",
                     mimetype='application/pdf')
def clean_text(text):
    if text:
        return (text.replace('–', '-')
                    .replace('—', '-')
                    .replace('’', "'")
                    .replace('‘', "'")
                    .replace('“', '"')
                    .replace('”', '"'))
    return ""
@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    aadhaar = request.form['aadhaar']

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM patient_records WHERE aadhaar = ?", (aadhaar,))
        records = c.fetchall()

    if not records:
        return "No records found."

    pdf = FPDF()
    pdf.add_page()

    # Top Logos
    pdf.image("static/india_logo.png", x=10, y=12, w=45, h=30)
    pdf.image("static/health_logo.png", x=175, y=12, w=25)
    pdf.image("static/indian_flag.png", x=50, y=1, w=110, h=50)
    pdf.ln(30)

    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text("REPUBLIC OF INDIA"), ln=True, align="C")
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, clean_text("Ministry of Health and Family Welfare"), ln=True, align="C")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, clean_text("National Medical Digital Health Record System (NMDHRS)"), ln=True, align="C")
    pdf.ln(10)

    # Title
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(0, 0, 128)
    pdf.cell(0, 10, clean_text("Complete Medical History Report"), ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, clean_text(f"Aadhaar Number: {aadhaar}"), ln=True)
    pdf.ln(5)

    for r in records:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, clean_text(f"Visit Date: {r[12]} | Hospital: {r[13]}"), ln=True)

        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 8,
            clean_text(
                f"Name         : {r[2]}\n"
                f"Age          : {r[3]}\n"
                f"Gender       : {r[4]}\n"
                f"Mobile       : {r[5]}\n"
                f"Blood Group  : {r[6]}\n"
                f"Doctor       : {r[7]}\n"
                f"Department   : {r[8]}\n"
                f"Illness      : {r[9]}\n"
                f"Prescription : {r[10]}\n"
                f"Address      : {r[11]}"
            )
        )
        pdf.ln(6)

    # Verification Section
    pdf.set_fill_color(230, 230, 250)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10,
             clean_text("This report has been digitally verified and authenticated by the Ministry of Health"),
             ln=True, fill=True)
    pdf.ln(5)

    # Disclaimer
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 8,
        clean_text(
            "Disclaimer:\n"
            "- This document is valid for digital reference only.\n"
            "- Verification can be done through the NMDHRS portal.\n"
            "- Forging or modifying this report is a criminal offense under Indian Cyber Law (IT Act Sec 66C).\n"
            "- Confidential: To be used only by authorized personnel or agencies."
        )
    )

    # Footer
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, clean_text(f"Issued on: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}"), ln=True, align="R")
    pdf.cell(0, 10, clean_text("This is a system-generated official report and does not require signature."),
             ln=True, align="R")

    # Send PDF
    buffer = BytesIO()
    pdf_bytes = pdf.output(dest='S').encode('latin1')  # now safe to encode
    buffer.write(pdf_bytes)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True,
                     download_name=f"NMDHRS_Full_Report_{aadhaar}.pdf",
                     mimetype='application/pdf')


@app.route("/history")
def history():
    aadhaar = request.args.get("aadhaar")
    selected_date = request.args.get("date")
    sort_order = request.args.get("sort", "desc")  # Default to 'desc'
    records = []

    if aadhaar:
        conn = sqlite3.connect("patients.db")
        c = conn.cursor()

        query = "SELECT * FROM patient_records WHERE aadhaar = ?"
        params = [aadhaar]

        if selected_date:
            query += " AND date = ?"
            params.append(selected_date)

        # Sort clause
        if sort_order == "asc":
            query += " ORDER BY date ASC"
        else:
            query += " ORDER BY date DESC"

        c.execute(query, tuple(params))
        records = c.fetchall()
        conn.close()

    return render_template("history.html", records=records, aadhaar=aadhaar, sort=sort_order)

@app.route('/write_blog', methods=['GET', 'POST'])
def write_blog():
    if 'doctor_id' not in session:
        return redirect(url_for('doctor_login'))

    if request.method == 'POST':
        doctor_id = session['doctor_id']

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            # Get doctor's name, hospital, department, and photo from doctor table
            c.execute("SELECT name, hospital, department, photo FROM doctors WHERE id = ?", (doctor_id,))
            doctor = c.fetchone()
            if not doctor:
                return "Doctor not found", 404

            doctor_name, hospital_name, department, photo = doctor
            title = request.form['title']
            content = request.form['content']
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            c.execute('''
                INSERT INTO doctor_blogs 
                (doctor_name, hospital_name, department, title, content, created_at, photo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (doctor_name, hospital_name, department, title, content, created_at, photo))
            conn.commit()

        return redirect(url_for('list_blogs'))

    return render_template('write_blog.html')

@app.route('/doctor_logout')
def doctor_logout():
    session.clear()
    return redirect(url_for('doctor_login'))  # Redirect to login after logout


# 📚 Route to view all blogs
@app.route('/blogs')
def list_blogs():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT id, doctor_name, hospital_name, department, title, content, created_at, photo
            FROM doctor_blogs
            ORDER BY created_at DESC
        ''')
        all_blogs = c.fetchall()
    return render_template('view_blogs.html', blogs=all_blogs)



# 🔍 Route to view a single blog by ID
@app.route('/blogs/<int:blog_id>')
def view_single_blog(blog_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT doctor_name, hospital_name, department, title, content, created_at 
            FROM doctor_blogs WHERE id = ?
        ''', (blog_id,))
        blog = c.fetchone()

    if not blog:
        return "Blog not found", 404

    return render_template('single_blog.html', blog=blog)
@app.route('/')
def home():
    return render_template('home.html')  # or whatever your homepage is


@app.route('/about_us')
def about_us():
    return render_template('about.html')


if __name__ == '__main__':
    app.run(debug=True)
