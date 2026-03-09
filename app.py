from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import os
import requests
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = "supersecretkey"

# DATABASE
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

# ================= HOME =================
@app.route("/")
def home():
    return render_template("index.html")

# ================= STUDENT LOGIN =================
@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        htno = request.form["htno"].lower()
        password = request.form["password"]

        student = Student.query.filter_by(htno=htno, password=password).first()
        if student:
            session["student"] = student.name
            session["htno"] = student.htno
            return redirect(url_for("student_dashboard"))

        return "Invalid credentials"

    return render_template("student_login.html")

# ================= FACULTY LOGIN =================
@app.route("/faculty_login", methods=["GET", "POST"])
def faculty_login():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]

        faculty = Faculty.query.filter_by(username=username, password=password).first()
        if faculty:
            session["faculty"] = faculty.username
            return redirect(url_for("faculty_dashboard"))

        return "Invalid credentials"

    return render_template("faculty_login.html")

# ================= GOOGLE SCORE READER =================
def fetch_google_scores(test):
    try:
        response = requests.get(test.google_csv_link)
        csv_data = response.text
        reader = csv.DictReader(StringIO(csv_data))

        for row in reader:
            htno = row.get("htno") or row.get("HTNO") or row.get("Htno")
            score = row.get("Score")

            if not htno or not score:
                continue

            htno = htno.lower()
            student = Student.query.filter_by(htno=htno).first()
            if not student:
                continue

            existing = Result.query.filter_by(
                htno=htno,
                test_title=test.title
            ).first()

            if existing:
                existing.score = float(score)
            else:
                db.session.add(Result(
                    student_name=student.name,
                    htno=htno,
                    test_title=test.title,
                    score=float(score)
                ))

        db.session.commit()

    except Exception as e:
        print("Google fetch error:", e)

# ================= FACULTY DASHBOARD =================
@app.route("/faculty_dashboard", methods=["GET", "POST"])
def faculty_dashboard():
    if "faculty" not in session:
        return redirect(url_for("faculty_login"))

    if request.method == "POST":
        title = request.form["title"]
        form_link = request.form["form_link"]
        csv_link = request.form["csv_link"]

        new_test = Test(
            title=title,
            google_form_link=form_link,
            google_csv_link=csv_link
        )

        db.session.add(new_test)
        db.session.commit()

    tests = Test.query.all()

    # Auto update scores
    for test in tests:
        if test.google_csv_link:
            fetch_google_scores(test)

    results = Result.query.all()

    return render_template("faculty_dashboard.html",
                           tests=tests,
                           results=results)

# ================= STUDENT DASHBOARD =================
@app.route("/student_dashboard")
def student_dashboard():
    if "student" not in session:
        return redirect(url_for("student_login"))

    tests = Test.query.all()
    return render_template("student_dashboard.html", tests=tests)

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)