import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import os
import requests
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ================= DATABASE =================
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ================= MODELS =================
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    htno = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100))
    password = db.Column(db.String(100))

class Faculty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100))

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    test_type = db.Column(db.String(20))
    google_form_link = db.Column(db.Text)
    google_csv_link = db.Column(db.Text)

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100))
    htno = db.Column(db.String(100))
    test_title = db.Column(db.String(200))
    score = db.Column(db.Float)

with app.app_context():
    db.create_all()

# ================= HELPERS =================
def normalize(text):
    return text.strip().lower().replace(" ", "").replace("_", "")

def find_column(row, keywords):
    for key in row.keys():
        k = normalize(key)
        for kw in keywords:
            if normalize(kw) in k:
                return key
    return None

# ================= GOOGLE SYNC =================
def sync_google_form_scores():
    tests = Test.query.filter_by(test_type="google").all()

    for test in tests:
        try:
            response = requests.get(test.google_csv_link)
            reader = csv.DictReader(StringIO(response.text))

            for row in reader:
                # 🔍 Find HTNO
                htno_col = find_column(row, ["htno", "hallticket"])
                if not htno_col:
                    print("❌ HTNO not found")
                    continue

                htno = str(row[htno_col]).strip().lower()
                if not htno:
                    continue

                # 🔥 AUTO CREATE STUDENT (CRITICAL FIX)
                student = Student.query.filter_by(htno=htno).first()
                if not student:
                    student = Student(
                        htno=htno,
                        name="Auto Student",
                        password="123"
                    )
                    db.session.add(student)
                    db.session.commit()

                # 🔥 AUTO SCORE CALCULATION
                score = 0

                # Match answers (partial matching for long column names)
                if find_column(row, ["sdlc"]) and row[find_column(row, ["sdlc"])] == "Waterfall Model":
                    score += 1

                if find_column(row, ["document"]) and row[find_column(row, ["document"])] == "SRS":
                    score += 1

                if find_column(row, ["testing"]) and row[find_column(row, ["testing"])] == "Unit Testing":
                    score += 1

                # 🔥 SAVE RESULT (NO FAIL CASE)
                existing = Result.query.filter_by(
                    htno=htno,
                    test_title=test.title
                ).first()

                if existing:
                    existing.score = score
                else:
                    db.session.add(Result(
                        student_name=student.name,
                        htno=htno,
                        test_title=test.title,
                        score=score
                    ))

                print("✅ SAVED:", htno, score)

            db.session.commit()

        except Exception as e:
            print("🔥 ERROR:", e)

# ================= ROUTES =================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/student_register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        htno = request.form["htno"].strip().lower()
        name = request.form["name"]
        password = request.form["password"]

        if not Student.query.filter_by(htno=htno).first():
            db.session.add(Student(htno=htno, name=name, password=password))
            db.session.commit()

        return redirect(url_for("student_login"))

    return render_template("student_register.html")

@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        htno = request.form["htno"].strip().lower()
        password = request.form["password"]

        student = Student.query.filter_by(htno=htno, password=password).first()
        if student:
            session["student"] = student.name
            session["htno"] = student.htno
            return redirect(url_for("student_dashboard"))

        return "Invalid login"

    return render_template("student_login.html")

@app.route("/faculty_login", methods=["GET", "POST"])
def faculty_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        faculty = Faculty.query.filter_by(username=username, password=password).first()
        if faculty:
            session["faculty"] = username
            return redirect(url_for("faculty_dashboard"))

    return render_template("faculty_login.html")

@app.route("/faculty_dashboard", methods=["GET", "POST"])
def faculty_dashboard():
    if "faculty" not in session:
        return redirect(url_for("faculty_login"))

    if request.method == "POST":
        db.session.add(Test(
            title=request.form["google_title"],
            test_type="google",
            google_form_link=request.form["google_form_link"],
            google_csv_link=request.form["google_csv_link"]
        ))
        db.session.commit()

    # 🔥 ALWAYS SYNC BEFORE SHOWING
    sync_google_form_scores()

    results = Result.query.all()

    return render_template("faculty_dashboard.html", results=results)

@app.route("/student_dashboard")
def student_dashboard():
    if "student" not in session:
        return redirect(url_for("student_login"))

    tests = Test.query.all()
    return render_template("student_dashboard.html", tests=tests)

@app.route("/attempt_test/<int:test_id>")
def attempt_test(test_id):
    test = Test.query.get_or_404(test_id)
    return redirect(test.google_form_link)

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)