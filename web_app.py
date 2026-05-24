from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///tracker.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default="Pending")
    priority = db.Column(db.String(50), default="Medium")
    due_date = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    time = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()


@app.route("/")
def dashboard():
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status="Completed").count()
    pending_tasks = Task.query.filter_by(status="Pending").count()
    in_progress_tasks = Task.query.filter_by(status="In Progress").count()
    blocked_tasks = Task.query.filter_by(status="Blocked").count()

    return render_template(
        "dashboard.html",
        tasks=tasks,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        in_progress_tasks=in_progress_tasks,
        blocked_tasks=blocked_tasks,
    )


@app.route("/add-task", methods=["POST"])
def add_task():
    title = request.form.get("title")
    description = request.form.get("description")
    status = request.form.get("status", "Pending")
    priority = request.form.get("priority", "Medium")
    due_date = request.form.get("due_date")

    if title:
        task = Task(
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
        )
        db.session.add(task)
        db.session.commit()

    return redirect(url_for("dashboard"))


@app.route("/delete-task/<int:task_id>", methods=["POST", "GET"])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for("dashboard"))


@app.route("/update-task/<int:task_id>", methods=["POST"])
def update_task(task_id):
    task = Task.query.get_or_404(task_id)

    task.title = request.form.get("title", task.title)
    task.description = request.form.get("description", task.description)
    task.status = request.form.get("status", task.status)
    task.priority = request.form.get("priority", task.priority)
    task.due_date = request.form.get("due_date", task.due_date)

    db.session.commit()
    return redirect(url_for("dashboard"))


@app.route("/kanban")
def kanban():
    tasks = Task.query.order_by(Task.created_at.desc()).all()

    grouped_tasks = {
        "Pending": [],
        "In Progress": [],
        "Completed": [],
        "Blocked": [],
    }

    for task in tasks:
        if task.status in grouped_tasks:
            grouped_tasks[task.status].append(task)
        else:
            grouped_tasks["Pending"].append(task)

    return render_template("kanban.html", grouped_tasks=grouped_tasks)


@app.route("/api/tasks")
def api_tasks():
    tasks = Task.query.order_by(Task.created_at.desc()).all()

    return jsonify([
        {
            "id": task.id,
            "title": task.title,
            "description": task.description or "",
            "status": task.status or "Pending",
            "priority": task.priority or "Medium",
            "due_date": task.due_date or "",
            "created_at": task.created_at.strftime("%Y-%m-%d %H:%M") if task.created_at else "",
        }
        for task in tasks
    ])


@app.route("/api/tasks/<int:task_id>/status", methods=["POST"])
def update_task_status(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()

    new_status = data.get("status")

    if new_status not in ["Pending", "In Progress", "Completed", "Blocked"]:
        return jsonify({"error": "Invalid status"}), 400

    task.status = new_status
    db.session.commit()

    return jsonify({"success": True, "status": task.status})


@app.route("/calendar")
def calendar():
    events = CalendarEvent.query.order_by(CalendarEvent.date.asc()).all()
    tasks = Task.query.filter(Task.due_date.isnot(None)).order_by(Task.due_date.asc()).all()

    return render_template("calendar.html", events=events, tasks=tasks)


@app.route("/add-event", methods=["POST"])
def add_event():
    title = request.form.get("title")
    date = request.form.get("date")
    time = request.form.get("time")
    description = request.form.get("description")

    if title and date:
        event = CalendarEvent(
            title=title,
            date=date,
            time=time,
            description=description,
        )
        db.session.add(event)
        db.session.commit()

    return redirect(url_for("calendar"))


@app.route("/delete-event/<int:event_id>", methods=["POST", "GET"])
def delete_event(event_id):
    event = CalendarEvent.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for("calendar"))


@app.route("/pdf-report")
def pdf_report():
    tasks = Task.query.order_by(Task.created_at.desc()).all()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 50

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "AI PM Tracker Report")

    y -= 40
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    y -= 40
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Task Summary")

    y -= 25
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Total Tasks: {Task.query.count()}")

    y -= 20
    pdf.drawString(50, y, f"Pending: {Task.query.filter_by(status='Pending').count()}")

    y -= 20
    pdf.drawString(50, y, f"In Progress: {Task.query.filter_by(status='In Progress').count()}")

    y -= 20
    pdf.drawString(50, y, f"Completed: {Task.query.filter_by(status='Completed').count()}")

    y -= 20
    pdf.drawString(50, y, f"Blocked: {Task.query.filter_by(status='Blocked').count()}")

    y -= 40
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Tasks")

    y -= 25
    pdf.setFont("Helvetica", 10)

    if not tasks:
        pdf.drawString(50, y, "No tasks found.")
    else:
        for task in tasks:
            if y < 80:
                pdf.showPage()
                y = height - 50
                pdf.setFont("Helvetica", 10)

            title = task.title or "Untitled Task"
            status = task.status or "Pending"
            priority = task.priority or "Medium"
            due_date = task.due_date or "No due date"

            line = f"{task.id}. {title} | Status: {status} | Priority: {priority} | Due: {due_date}"
            pdf.drawString(50, y, line[:110])
            y -= 18

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="ai_pm_tracker_report.pdf",
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    app.run(debug=True)