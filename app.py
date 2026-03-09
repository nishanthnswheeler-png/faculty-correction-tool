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
    test_type = db.Column(db.String(20))  # "manual" or "google"

    # Manual test fields
    questions = db.Column(db.Text)   # one per line
    keywords = db.Column(db.Text)    # one per line
    marks = db.Column(db.Text)       # one per line

    # Google form fields
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
def find_column(row_dict, possible_names):
    """Find a column by matching normalized names."""
    for key in row_dict.keys():
        normalized = key.strip().lower().replace(" ", "").replace("_", "")
        for name in possible_names:
            if normalized == name.strip().lower().replace(" ", "").replace("_", ""):
                return key
    return None

def sync_google_form_scores():
    """Read Google Sheet CSV and use the Score column directly."""
    google_tests = Test.query.filter_by(test_type="google").all()

    for test in google_tests:
        if not test.google_csv_link:
            continue

        try:
            response = requests.get(test.google_csv_link, timeout=20)
            response.raise_for_status()

            csv_data = response.text
            reader = csv.DictReader(StringIO(csv_data))

            for row in reader:
                htno_col = find_column(row, ["HTNO", "HT NO", "hallticket", "hall ticket", "htno"])
                score_col = find_column(row, ["Score", "score"])

                if not htno_col or not score_col:
                    continue

                htno = (row.get(htno_col) or "").strip().lower()
                score_raw = (row.get(score_col) or "").strip()

                if not htno or not score_raw:
                    continue

                try:
                    score_value = float(score_raw)
                except ValueError:
                    continue

                student = Student.query.filter_by(htno=htno).first()
                if not student:
                    continue

                existing = Result.query.filter_by(
                    htno=htno,
                    test_title=test.title
                ).first()

                if existing:
                    existing.score = score_value
                else:
                    db.session.add(Result(
                        student_name=student.name,
                        htno=htno,
                        test_title=test.title,
                        score=score_value
                    ))

            db.session.commit()

        except Exception as e:
            print(f"Google sync error for test '{test.title}': {e}")

# ================= HOME =================
@app.route("/")
def home():
    return render_template("index.html")

# ================= STUDENT REGISTER =================
@app.route("/student_register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        htno = request.form["htno"].strip().lower()
        name = request.form["name"].strip()
        password = request.form["password"].strip()

        if Student.query.filter_by(htno=htno).first():
            return "Student already exists"

        db.session.add(Student(htno=htno, name=name, password=password))
        db.session.commit()
        return redirect(url_for("student_login"))

    return render_template("student_register.html")

# ================= STUDENT LOGIN =================
@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        htno = request.form["htno"].strip().lower()
        password = request.form["password"].strip()

        student = Student.query.filter_by(htno=htno, password=password).first()
        if student:
            session["student"] = student.name
            session["htno"] = student.htno
            return redirect(url_for("student_dashboard"))

        return "Invalid credentials"

    return render_template("student_login.html")

# ================= FACULTY REGISTER =================
@app.route("/faculty_register", methods=["GET", "POST"])
def faculty_register():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"].strip()

        if Faculty.query.filter_by(username=username).first():
            return "Faculty already exists"

        db.session.add(Faculty(username=username, password=password))
        db.session.commit()
        return redirect(url_for("faculty_login"))

    return render_template("faculty_register.html")

# ================= FACULTY LOGIN =================
@app.route("/faculty_login", methods=["GET", "POST"])
def faculty_login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"].strip()

        faculty = Faculty.query.filter_by(username=username, password=password).first()
        if faculty:
            session["faculty"] = faculty.username
            return redirect(url_for("faculty_dashboard"))

        return "Invalid credentials"

    return render_template("faculty_login.html")

# ================= FACULTY DASHBOARD =================
@app.route("/faculty_dashboard", methods=["GET", "POST"])
def faculty_dashboard():
    if "faculty" not in session:
        return redirect(url_for("faculty_login"))

    if request.method == "POST":
        test_type = request.form["test_type"]

        if test_type == "manual":
            title = request.form["manual_title"].strip()
            questions = request.form["manual_questions"].strip()
            keywords = request.form["manual_keywords"].strip()
            marks = request.form["manual_marks"].strip()

            db.session.add(Test(
                title=title,
                test_type="manual",
                questions=questions,
                keywords=keywords,
                marks=marks
            ))

        elif test_type == "google":
            title = request.form["google_title"].strip()
            google_form_link = request.form["google_form_link"].strip()
            google_csv_link = request.form["google_csv_link"].strip()

            db.session.add(Test(
                title=title,
                test_type="google",
                google_form_link=google_form_link,
                google_csv_link=google_csv_link
            ))

        db.session.commit()

    sync_google_form_scores()

    tests = Test.query.all()
    results = Result.query.all()

    return render_template(
        "faculty_dashboard.html",
        tests=tests,
        results=results
    )

# ================= STUDENT DASHBOARD =================
@app.route("/student_dashboard")
def student_dashboard():
    if "student" not in session:
        return redirect(url_for("student_login"))

    tests = Test.query.all()
    return render_template("student_dashboard.html", tests=tests)

# ================= ATTEMPT TEST =================
@app.route("/attempt_test/<int:test_id>")
def attempt_test(test_id):
    if "student" not in session:
        return redirect(url_for("student_login"))

    test = Test.query.get_or_404(test_id)

    if test.test_type == "google":
        if not test.google_form_link:
            return "Google Form link not available"
        return redirect(test.google_form_link)

    return redirect(url_for("manual_test", test_id=test.id))

# ================= MANUAL TEST PAGE =================
@app.route("/manual_test/<int:test_id>", methods=["GET", "POST"])
def manual_test(test_id):
    if "student" not in session:
        return redirect(url_for("student_login"))

    test = Test.query.get_or_404(test_id)

    if test.test_type != "manual":
        return redirect(url_for("attempt_test", test_id=test.id))

    questions = [q.strip() for q in test.questions.split("\n") if q.strip()]
    keywords = [k.strip().lower() for k in test.keywords.split("\n") if k.strip()]
    marks = [float(m.strip()) for m in test.marks.split("\n") if m.strip()]

    if request.method == "POST":
        total_score = 0

        for i, keyword in enumerate(keywords):
            answer = request.form.get(f"answer_{i}", "").strip().lower()

            # Full marks if keyword appears anywhere in answer, otherwise zero
            if keyword in answer:
                total_score += marks[i]

        existing = Result.query.filter_by(
            htno=session["htno"],
            test_title=test.title
        ).first()

        if existing:
            existing.score = total_score
        else:
            db.session.add(Result(
                student_name=session["student"],
                htno=session["htno"],
                test_title=test.title,
                score=total_score
            ))

        db.session.commit()
        return redirect(url_for("student_dashboard"))

    return render_template(
        "manual_test.html",
        test=test,
        questions=questions
    )

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)