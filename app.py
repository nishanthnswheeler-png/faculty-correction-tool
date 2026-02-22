from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from difflib import SequenceMatcher
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ==========================
# DATABASE CONFIG
# ==========================
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ==========================
# DATABASE MODELS
# ==========================

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
    questions = db.Column(db.Text)
    answers = db.Column(db.Text)

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100))
    htno = db.Column(db.String(100))
    test_title = db.Column(db.String(200))
    score = db.Column(db.Float)

# ==========================
# HOME
# ==========================

@app.route("/")
def home():
    return render_template("index.html")

# ==========================
# STUDENT REGISTER
# ==========================

@app.route("/student_register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        htno = request.form["htno"].lower()
        name = request.form["name"].lower()
        password = request.form["password"]

        existing = Student.query.filter_by(htno=htno).first()
        if existing:
            return "Student already registered! Please login."

        new_student = Student(htno=htno, name=name, password=password)
        db.session.add(new_student)
        db.session.commit()

        return redirect(url_for("student_login"))

    return render_template("student_register.html")

# ==========================
# FACULTY REGISTER
# ==========================

@app.route("/faculty_register", methods=["GET", "POST"])
def faculty_register():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]

        existing = Faculty.query.filter_by(username=username).first()
        if existing:
            return "Faculty already registered! Please login."

        new_faculty = Faculty(username=username, password=password)
        db.session.add(new_faculty)
        db.session.commit()

        return redirect(url_for("faculty_login"))

    return render_template("faculty_register.html")

# ==========================
# STUDENT LOGIN
# ==========================

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
        else:
            return "Invalid Credentials"

    return render_template("student_login.html")

# ==========================
# FACULTY LOGIN
# ==========================

@app.route("/faculty_login", methods=["GET", "POST"])
def faculty_login():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]

        faculty = Faculty.query.filter_by(username=username, password=password).first()
        if faculty:
            session["faculty"] = faculty.username
            return redirect(url_for("faculty_dashboard"))
        else:
            return "Invalid Credentials"

    return render_template("faculty_login.html")

# ==========================
# FACULTY DASHBOARD
# ==========================

@app.route("/faculty_dashboard", methods=["GET", "POST"])
def faculty_dashboard():
    if "faculty" not in session:
        return redirect(url_for("faculty_login"))

    if request.method == "POST":
        title = request.form["title"]
        questions = request.form["questions"]
        answers = request.form["answers"]

        new_test = Test(title=title,
                        questions=questions,
                        answers=answers)
        db.session.add(new_test)
        db.session.commit()

    tests = Test.query.all()
    results = Result.query.all()

    return render_template("faculty_dashboard.html",
                           tests=tests,
                           results=results)

# ==========================
# STUDENT DASHBOARD
# ==========================

@app.route("/student_dashboard")
def student_dashboard():
    if "student" not in session:
        return redirect(url_for("student_login"))

    tests = Test.query.all()
    return render_template("student_dashboard.html",
                           tests=tests)

# ==========================
# ATTEMPT TEST
# ==========================

@app.route("/attempt/<int:test_id>", methods=["GET", "POST"])
def attempt(test_id):
    test = Test.query.get(test_id)

    if request.method == "POST":
        student_answers = request.form.getlist("answers")
        correct_answers = test.answers.lower().split("\n")

        score = 0

        for i in range(len(correct_answers)):
            similarity = SequenceMatcher(
                None,
                student_answers[i].lower(),
                correct_answers[i]
            ).ratio()

            if similarity >= 0.9:
                score += 1
            elif similarity >= 0.5:
                score += 0.5

        result = Result(
            student_name=session["student"],
            htno=session["htno"],
            test_title=test.title,
            score=score
        )

        db.session.add(result)
        db.session.commit()

        return redirect(url_for("student_dashboard"))

    questions = test.questions.split("\n")
    return render_template("attempt.html",
                           test=test,
                           questions=questions)

# ==========================
# CREATE TABLES (IMPORTANT)
# ==========================

with app.app_context():
    db.create_all()

# ==========================
# RUN
# ==========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)