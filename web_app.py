from flask import Flask, render_template, request, redirect, session, Response, jsonify
import sqlite3
import csv
from io import StringIO, BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "secretkey"

DATABASE = "ai_pm_tracker.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(table, column, column_type):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row["name"] for row in cursor.fetchall()]

    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    conn.commit()
    conn.close()


def init_db():

    conn = get_db_connection()
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        avatar_initials TEXT
    )
    """)

    # PROJECTS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        status TEXT,
        start_date TEXT,
        end_date TEXT,
        estimated_budget REAL DEFAULT 0,
        actual_cost REAL DEFAULT 0,
        client_id INTEGER,
        user_id INTEGER
    )
    """)

    # TASKS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        title TEXT,
        priority TEXT,
        status TEXT,
        due_date TEXT,
        assigned_to TEXT,
        attachment_url TEXT,
        estimated_hours REAL DEFAULT 0,
        actual_hours REAL DEFAULT 0,
        hourly_rate REAL DEFAULT 0
    )
    """)

    # ACTIVITY LOGS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity TEXT,
        created_at TEXT
    )
    """)

    # CLIENTS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        company TEXT,
        email TEXT,
        phone TEXT,
        status TEXT,
        notes TEXT,
        estimated_value REAL DEFAULT 0,
        user_id INTEGER
    )
    """)

    conn.commit()
    conn.close()


init_db()

ensure_column("tasks", "assigned_to", "TEXT")
ensure_column("tasks", "attachment_url", "TEXT")
ensure_column("tasks", "estimated_hours", "REAL DEFAULT 0")
ensure_column("tasks", "actual_hours", "REAL DEFAULT 0")
ensure_column("tasks", "hourly_rate", "REAL DEFAULT 0")

ensure_column("users", "avatar_initials", "TEXT")

ensure_column("projects", "estimated_budget", "REAL DEFAULT 0")
ensure_column("projects", "actual_cost", "REAL DEFAULT 0")
ensure_column("projects", "client_id", "INTEGER")


def create_demo_user():
    conn = get_db_connection()

    hashed_password = generate_password_hash("demo123")

    existing_user = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        ("demo",)
    ).fetchone()

    if existing_user:
        conn.execute("""
        UPDATE users
        SET password = ?,
            avatar_initials = ?
        WHERE username = ?
        """, (
            hashed_password,
            "DE",
            "demo"
        ))
    else:
        conn.execute("""
        INSERT INTO users (username, password, avatar_initials)
        VALUES (?, ?, ?)
        """, (
            "demo",
            hashed_password,
            "DE"
        ))

    conn.commit()
    conn.close()


create_demo_user()

def create_activity(message):
    conn = get_db_connection()

    conn.execute("""
    INSERT INTO activities (message, created_at)
    VALUES (?, ?)
    """, (
        message,
        str(date.today())
    ))

    conn.commit()
    conn.close()


def is_overdue(due_date, status):
    if not due_date:
        return False

    return due_date < str(date.today()) and status != "Completed"

@app.route("/")
def home():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    projects = conn.execute("""
    SELECT
        projects.*,
        clients.name AS client_name,
        clients.company AS client_company
    FROM projects
    LEFT JOIN clients
    ON projects.client_id = clients.id
    WHERE projects.user_id = ?
    ORDER BY projects.id DESC
    """, (
        session["user_id"],
    )).fetchall()

    clients = conn.execute("""
    SELECT *
    FROM clients
    WHERE user_id = ?
    """, (
        session["user_id"],
    )).fetchall()

    all_projects = []

    total_tasks = 0
    completed_tasks = 0
    pending_tasks = 0
    in_progress_tasks = 0
    blocked_tasks = 0

    high_priority_tasks = 0
    medium_priority_tasks = 0
    low_priority_tasks = 0
    overdue_tasks = 0

    total_budget = 0
    total_actual_cost = 0
    over_budget_projects = 0

    total_clients = len(clients)
    total_client_value = 0
    active_clients = set()

    upcoming_deadlines = []

    for client in clients:

        total_client_value += float(
            client["estimated_value"] or 0
        )

    for project in projects:

        estimated_budget = float(
            project["estimated_budget"] or 0
        )

        base_actual_cost = float(
            project["actual_cost"] or 0
        )

        total_budget += estimated_budget

        if project["client_name"]:
            active_clients.add(
                project["client_name"]
            )

        tasks = conn.execute("""
        SELECT *
        FROM tasks
        WHERE project_id = ?
        ORDER BY
            CASE
                WHEN due_date IS NULL
                OR due_date = ''
                THEN '9999-12-31'
                ELSE due_date
            END ASC
        """, (
            project["id"],
        )).fetchall()

        task_list = []
        task_actual_cost_total = 0

        for task in tasks:

            total_tasks += 1

            task_actual_hours = float(
                task["actual_hours"] or 0
            )

            task_hourly_rate = float(
                task["hourly_rate"] or 0
            )

            task_actual_cost_total += (
                task_actual_hours
                * task_hourly_rate
            )

            if task["status"] == "Completed":
                completed_tasks += 1

            elif task["status"] == "Pending":
                pending_tasks += 1

            elif task["status"] == "In Progress":
                in_progress_tasks += 1

            elif task["status"] == "Blocked":
                blocked_tasks += 1

            if task["priority"] == "High":
                high_priority_tasks += 1

            elif task["priority"] == "Medium":
                medium_priority_tasks += 1

            elif task["priority"] == "Low":
                low_priority_tasks += 1

            if is_overdue(
                task["due_date"],
                task["status"]
            ):
                overdue_tasks += 1

            if (
                task["due_date"]
                and task["status"] != "Completed"
                and task["due_date"] >= str(date.today())
            ):

                upcoming_deadlines.append({
                    "title": task["title"],
                    "project_name": project["name"],
                    "due_date": task["due_date"],
                    "priority": task["priority"],
                    "status": task["status"]
                })

            task_list.append((
                task["title"],
                task["priority"],
                task["status"],
                task["due_date"]
            ))

        actual_cost = (
            base_actual_cost
            + task_actual_cost_total
        )

        total_actual_cost += actual_cost

        remaining_budget = (
            estimated_budget
            - actual_cost
        )

        if (
            estimated_budget > 0
            and actual_cost > estimated_budget
        ):
            over_budget_projects += 1

        if estimated_budget > 0:

            budget_used_percent = round(
                (
                    actual_cost
                    / estimated_budget
                ) * 100
            )

        else:
            budget_used_percent = 0

        if len(tasks) > 0:

            completed_for_project = len([
                task for task in tasks
                if task["status"] == "Completed"
            ])

            completion = round(
                (
                    completed_for_project
                    / len(tasks)
                ) * 100
            )

        else:
            completion = 0


        # AI RISK SCORING

        risk_score = 0

        if completion < 30:
            risk_score += 25

        if budget_used_percent > 100:

            risk_score += 30

        elif budget_used_percent > 80:

            risk_score += 15

        project_overdue_tasks = len([
            task for task in tasks
            if is_overdue(
                task["due_date"],
                task["status"]
            )
        ])

        risk_score += project_overdue_tasks * 10

        project_blocked_tasks = len([
            task for task in tasks
            if task["status"] == "Blocked"
        ])

        risk_score += project_blocked_tasks * 15

        project_high_priority = len([
            task for task in tasks
            if (
                task["priority"] == "High"
                and task["status"] != "Completed"
            )
        ])

        risk_score += project_high_priority * 5


        if risk_score >= 70:

            risk_label = "Critical Risk"

        elif risk_score >= 45:

            risk_label = "High Risk"

        elif risk_score >= 20:

            risk_label = "Medium Risk"

        else:

            risk_label = "Low Risk"


        # AI RECOMMENDATIONS

        ai_recommendation = []

        if project_overdue_tasks > 0:

            ai_recommendation.append(
                "Resolve overdue tasks immediately."
            )

        if project_blocked_tasks > 0:

            ai_recommendation.append(
                "Blocked tasks require escalation."
            )

        if budget_used_percent > 90:

            ai_recommendation.append(
                "Budget usage is critically high."
            )

        if completion < 30:

            ai_recommendation.append(
                "Project delivery pace is behind schedule."
            )

        if not ai_recommendation:

            ai_recommendation.append(
                "Project performance currently appears stable."
            )


        all_projects.append({
            "project": (
                project["id"],
                project["name"],
                project["status"],
                project["start_date"],
                project["end_date"]
            ),
            "tasks": task_list,
            "completion": completion,
            "estimated_budget": estimated_budget,
            "actual_cost": actual_cost,
            "remaining_budget": remaining_budget,
            "budget_used_percent": budget_used_percent,
            "client_name": project["client_name"],
            "client_company": project["client_company"],
            "risk_score": risk_score,
            "risk_label": risk_label,
            "ai_recommendation": ai_recommendation
        })

    conn.close()

    upcoming_deadlines = sorted(
        upcoming_deadlines,
        key=lambda item: item["due_date"]
    )[:5]

    if total_tasks > 0:

        completion_rate = round(
            (
                completed_tasks
                / total_tasks
            ) * 100
        )

    else:
        completion_rate = 0

    total_remaining_budget = (
        total_budget
        - total_actual_cost
    )

    if total_budget > 0:

        budget_usage_percent = round(
            (
                total_actual_cost
                / total_budget
            ) * 100
        )

        profitability_score = round(
            (
                total_remaining_budget
                / total_budget
            ) * 100
        )

    else:

        budget_usage_percent = 0
        profitability_score = 0

    if profitability_score >= 50:

        financial_health_label = "Strong"

    elif profitability_score >= 20:

        financial_health_label = "Stable"

    elif profitability_score >= 0:

        financial_health_label = "At Risk"

    else:

        financial_health_label = "Over Budget"

    if (
        overdue_tasks > 0
        or blocked_tasks > 0
        or over_budget_projects > 0
    ):

        project_health_score = max(
            0,
            100
            - (overdue_tasks * 15)
            - (blocked_tasks * 10)
            - (over_budget_projects * 15)
        )

        project_health_label = "Needs Attention"

    elif completion_rate >= 70:

        project_health_score = 90
        project_health_label = "Healthy"

    elif total_tasks == 0:

        project_health_score = 0
        project_health_label = "No Data Yet"

    else:

        project_health_score = 65
        project_health_label = "Stable"

    smart_insights = []

    if overdue_tasks > 0:

        smart_insights.append(
            f"You have {overdue_tasks} overdue task(s)."
        )

    if blocked_tasks > 0:

        smart_insights.append(
            f"{blocked_tasks} task(s) are blocked."
        )

    if over_budget_projects > 0:

        smart_insights.append(
            f"{over_budget_projects} project(s) are over budget."
        )

    if high_priority_tasks > 0:

        smart_insights.append(
            f"{high_priority_tasks} high-priority task(s) need attention."
        )

    if upcoming_deadlines:

        smart_insights.append(
            f"{len(upcoming_deadlines)} upcoming deadline(s) are active."
        )

    workload_summary = {
        "active": (
            in_progress_tasks
            + pending_tasks
        ),
        "completed": completed_tasks,
        "blocked": blocked_tasks,
        "overdue": overdue_tasks
    }

    notifications = []

    if overdue_tasks > 0:

        notifications.append(
            f"You have {overdue_tasks} overdue task(s)."
        )

    if blocked_tasks > 0:

        notifications.append(
            f"{blocked_tasks} task(s) are blocked."
        )

    if over_budget_projects > 0:

        notifications.append(
            f"{over_budget_projects} project(s) are over budget."
        )

    return render_template(
        "index.html",
        projects=all_projects,
        total_projects=len(projects),
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        in_progress_tasks=in_progress_tasks,
        blocked_tasks=blocked_tasks,
        high_priority_tasks=high_priority_tasks,
        medium_priority_tasks=medium_priority_tasks,
        low_priority_tasks=low_priority_tasks,
        overdue_tasks=overdue_tasks,
        completion_rate=completion_rate,
        project_health_score=project_health_score,
        project_health_label=project_health_label,
        smart_insights=smart_insights,
        upcoming_deadlines=upcoming_deadlines,
        workload_summary=workload_summary,
        total_budget=total_budget,
        total_actual_cost=total_actual_cost,
        total_remaining_budget=total_remaining_budget,
        over_budget_projects=over_budget_projects,
        budget_usage_percent=budget_usage_percent,
        profitability_score=profitability_score,
        financial_health_label=financial_health_label,
        total_clients=total_clients,
        total_client_value=total_client_value,
        active_clients_count=len(active_clients),
        chart_status_data=[
            completed_tasks,
            pending_tasks,
            in_progress_tasks,
            blocked_tasks
        ],
        chart_priority_data=[
            high_priority_tasks,
            medium_priority_tasks,
            low_priority_tasks
        ],
        notifications=notifications,
        current_date=str(date.today())
    )

@app.route("/kanban")
def kanban():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    tasks = conn.execute("""
    SELECT tasks.*, projects.name AS project_name
    FROM tasks
    JOIN projects ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    ORDER BY tasks.due_date ASC
    """, (session["user_id"],)).fetchall()

    conn.close()

    columns = {
        "Pending": [],
        "In Progress": [],
        "Completed": [],
        "Blocked": []
    }

    for task in tasks:
        status = task["status"] if task["status"] in columns else "Pending"
        columns[status].append(task)

    return render_template(
        "kanban.html",
        tasks=tasks,
        columns=columns,
        current_date=str(date.today())
    )


@app.route("/update-task-status", methods=["POST"])
def update_task_status():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    data = request.get_json()

    task_id = data.get("task_id")
    new_status = data.get("status")

    allowed_statuses = [
        "Pending",
        "In Progress",
        "Completed",
        "Blocked"
    ]

    if new_status not in allowed_statuses:
        return jsonify({"success": False, "message": "Invalid status"}), 400

    conn = get_db_connection()

    task = conn.execute("""
    SELECT tasks.id, tasks.title
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE tasks.id = ?
    AND projects.user_id = ?
    """, (
        task_id,
        session["user_id"]
    )).fetchone()

    if not task:
        conn.close()
        return jsonify({"success": False, "message": "Task not found"}), 404

    conn.execute(
        "UPDATE tasks SET status = ? WHERE id = ?",
        (
            new_status,
            task_id
        )
    )

    conn.commit()
    conn.close()

    create_activity(
        f"{session.get('username', 'User')} moved task {task['title']} to {new_status}"
    )

    return jsonify({"success": True})


@app.route("/calendar")
def calendar():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    tasks = conn.execute("""
    SELECT tasks.*, projects.name AS project_name
    FROM tasks
    JOIN projects ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    AND tasks.due_date IS NOT NULL
    AND tasks.due_date != ''
    ORDER BY tasks.due_date ASC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "calendar.html",
        tasks=tasks,
        current_date=str(date.today())
    )

@app.route("/report")
def report():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    projects = conn.execute(
        "SELECT * FROM projects WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()

    tasks = conn.execute("""
    SELECT tasks.*, projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    ORDER BY
        CASE
            WHEN tasks.due_date IS NULL OR tasks.due_date = '' THEN 1
            ELSE 0
        END,
        tasks.due_date ASC
    """, (session["user_id"],)).fetchall()

    total_tasks = len(tasks)
    completed_tasks = len([task for task in tasks if task["status"] == "Completed"])
    overdue_tasks = len([task for task in tasks if is_overdue(task["due_date"], task["status"])])

    if total_tasks > 0:
        completion_rate = round((completed_tasks / total_tasks) * 100)
    else:
        completion_rate = 0

    conn.close()

    return render_template(
        "report.html",
        projects=projects,
        tasks=tasks,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        completion_rate=completion_rate,
        current_date=str(date.today())
    )

@app.route("/pdf-report")
def pdf_report():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    tasks = conn.execute("""
    SELECT tasks.*, projects.name AS project_name
    FROM tasks
    JOIN projects ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    ORDER BY tasks.due_date ASC
    """, (session["user_id"],)).fetchall()

    conn.close()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 50

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "AI PM Tracker Report")

    y -= 35
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Generated: {str(date.today())}")

    y -= 35
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Tasks")

    y -= 25
    pdf.setFont("Helvetica", 10)

    if not tasks:
        pdf.drawString(50, y, "No tasks found.")
    else:
        for task in tasks:
            if y < 70:
                pdf.showPage()
                y = height - 50
                pdf.setFont("Helvetica", 10)

            line = f"{task['project_name']} | {task['title']} | {task['priority']} | {task['status']} | Due: {task['due_date']}"
            pdf.drawString(50, y, line[:115])
            y -= 18

    pdf.save()
    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=ai_pm_tracker_report.pdf"
        }
    )

@app.route("/insights")
def insights():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    tasks = conn.execute("""
    SELECT tasks.*, projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    """, (session["user_id"],)).fetchall()

    conn.close()

    total = len(tasks)
    completed = len([task for task in tasks if task["status"] == "Completed"])
    in_progress = len([task for task in tasks if task["status"] == "In Progress"])
    pending = len([task for task in tasks if task["status"] == "Pending"])
    blocked = len([task for task in tasks if task["status"] == "Blocked"])
    high_priority = len([task for task in tasks if task["priority"] == "High"])
    overdue = len([task for task in tasks if is_overdue(task["due_date"], task["status"])])

    insights_list = []

    if total == 0:
        insights_list.append("You do not have any tasks yet. Start by creating tasks under your projects.")

    if overdue > 0:
        insights_list.append(f"You have {overdue} overdue task(s). Review deadlines and update priorities.")

    if high_priority > 0:
        insights_list.append(f"You have {high_priority} high-priority task(s). Focus on these first.")

    if blocked > 0:
        insights_list.append(f"{blocked} task(s) are blocked. These may need escalation or support.")

    if total > 0 and completed == total:
        insights_list.append("All current tasks are completed. Great progress.")

    if total > 0 and completed < total and overdue == 0 and blocked == 0:
        insights_list.append("Your workload looks healthy. Keep reviewing progress regularly.")

    if total > 0:
        completion_rate = round((completed / total) * 100)
    else:
        completion_rate = 0

    return render_template(
        "insights.html",
        insights=insights_list,
        total=total,
        completed=completed,
        in_progress=in_progress,
        pending=pending,
        blocked=blocked,
        overdue=overdue,
        high_priority=high_priority,
        completion_rate=completion_rate
    )


@app.route("/export-tasks")
def export_tasks():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    tasks = conn.execute("""
    SELECT tasks.title,
           tasks.priority,
           tasks.status,
           tasks.due_date,
           tasks.assigned_to,
           tasks.attachment_url,
           projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    """, (session["user_id"],)).fetchall()

    conn.close()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Project",
        "Task",
        "Priority",
        "Status",
        "Due Date",
        "Assigned To",
        "Attachment URL"
    ])

    for task in tasks:
        writer.writerow([
            task["project_name"],
            task["title"],
            task["priority"],
            task["status"],
            task["due_date"],
            task["assigned_to"] or "Unassigned",
            task["attachment_url"] or ""
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=ai_pm_tasks.csv"
        }
    )


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    if request.method == "POST":
        avatar_initials = request.form["avatar_initials"]

        conn.execute(
            "UPDATE users SET avatar_initials = ? WHERE id = ?",
            (
                avatar_initials,
                session["user_id"]
            )
        )

        conn.commit()
        session["avatar_initials"] = avatar_initials

        conn.close()

        return redirect("/")

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    return render_template(
        "profile.html",
        user=user
    )


@app.route("/activity")
def activity():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    activities = conn.execute("""
    SELECT *
    FROM activities
    ORDER BY id DESC
    LIMIT 50
    """).fetchall()

    conn.close()

    return render_template(
        "activity.html",
        activities=activities
    )


@app.route("/project-comments/<int:project_id>", methods=["GET", "POST"])
def project_comments(project_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    project = conn.execute("""
    SELECT *
    FROM projects
    WHERE id = ?
    AND user_id = ?
    """, (
        project_id,
        session["user_id"]
    )).fetchone()

    if not project:
        conn.close()
        return redirect("/")

    if request.method == "POST":
        comment = request.form["comment"]

        conn.execute("""
        INSERT INTO comments (
            project_id,
            username,
            comment,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """, (
            project_id,
            session.get("username", "User"),
            comment,
            str(date.today())
        ))

        conn.commit()

        create_activity(
            f"{session.get('username', 'User')} commented on project {project['name']}"
        )

    comments = conn.execute("""
    SELECT *
    FROM comments
    WHERE project_id = ?
    ORDER BY id DESC
    """, (
        project_id,
    )).fetchall()

    conn.close()

    return render_template(
        "comments.html",
        comments=comments,
        project=project
    )


@app.route("/sprint-planner")
def sprint_planner():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    tasks = conn.execute("""
    SELECT tasks.*, projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    AND tasks.status != 'Completed'
    ORDER BY
        CASE tasks.priority
            WHEN 'High' THEN 1
            WHEN 'Medium' THEN 2
            WHEN 'Low' THEN 3
            ELSE 4
        END,
        tasks.due_date ASC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    sprint_tasks = []
    recommendations = []

    for task in tasks:
        sprint_tasks.append(task)

        if task["priority"] == "High":
            recommendations.append(
                f"Prioritize '{task['title']}' because it is high priority."
            )

        if task["status"] == "Blocked":
            recommendations.append(
                f"Resolve blockers for '{task['title']}' before sprint execution."
            )

        if is_overdue(task["due_date"], task["status"]):
            recommendations.append(
                f"Review '{task['title']}' because it is overdue."
            )

    if len(sprint_tasks) == 0:
        recommendations.append(
            "No active tasks available for sprint planning."
        )

    return render_template(
        "sprint_planner.html",
        sprint_tasks=sprint_tasks,
        recommendations=recommendations
    )


@app.route("/advanced-search")
def advanced_search():
    if "user_id" not in session:
        return redirect("/login")

    status = request.args.get("status", "")
    priority = request.args.get("priority", "")

    conn = get_db_connection()

    query = """
    SELECT tasks.*, projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    """

    params = [session["user_id"]]

    if status:
        query += " AND tasks.status = ?"
        params.append(status)

    if priority:
        query += " AND tasks.priority = ?"
        params.append(priority)

    query += " ORDER BY tasks.due_date ASC"

    tasks = conn.execute(
        query,
        params
    ).fetchall()

    conn.close()

    return render_template(
        "advanced_search.html",
        tasks=tasks,
        selected_status=status,
        selected_priority=priority
    )


@app.route("/project/<int:project_id>")
def project_detail(project_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    project = conn.execute("""
    SELECT *
    FROM projects
    WHERE id = ?
    AND user_id = ?
    """, (
        project_id,
        session["user_id"]
    )).fetchone()

    if not project:
        conn.close()
        return redirect("/")

    tasks = conn.execute("""
    SELECT *
    FROM tasks
    WHERE project_id = ?
    ORDER BY
        CASE
            WHEN due_date IS NULL OR due_date = '' THEN 1
            ELSE 0
        END,
        due_date ASC
    """, (
        project_id,
    )).fetchall()

    task_list = []
    completed_tasks = 0

    for task in tasks:
        overdue = is_overdue(task["due_date"], task["status"])

        if task["status"] == "Completed":
            completed_tasks += 1

        task_list.append((
            task["id"],
            task["title"],
            task["priority"],
            task["status"],
            task["due_date"],
            overdue
        ))

    total_tasks = len(tasks)

    if total_tasks > 0:
        completion = round((completed_tasks / total_tasks) * 100)
    else:
        completion = 0

    conn.close()

    return render_template(
        "project_detail.html",
        project=(
            project["id"],
            project["name"],
            project["description"],
            project["status"],
            project["start_date"],
            project["end_date"]
        ),
        tasks=task_list,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        completion=completion
    )


@app.route("/tasks")
def tasks():
    if "user_id" not in session:
        return redirect("/login")

    search = request.args.get("search", "")
    sort = request.args.get("sort", "")

    conn = get_db_connection()

    query = """
    SELECT tasks.*, projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    AND (
        tasks.title LIKE ?
        OR tasks.priority LIKE ?
        OR tasks.status LIKE ?
        OR tasks.assigned_to LIKE ?
        OR projects.name LIKE ?
    )
    """

    if sort == "due_date":
        query += " ORDER BY tasks.due_date ASC"
    elif sort == "priority":
        query += """
        ORDER BY
            CASE tasks.priority
                WHEN 'High' THEN 1
                WHEN 'Medium' THEN 2
                WHEN 'Low' THEN 3
                ELSE 4
            END
        """
    elif sort == "status":
        query += " ORDER BY tasks.status ASC"
    else:
        query += " ORDER BY tasks.id DESC"

    task_rows = conn.execute(
        query,
        (
            session["user_id"],
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%"
        )
    ).fetchall()

    all_tasks = []

    for task in task_rows:
        all_tasks.append((
            task["id"],
            task["title"],
            task["priority"],
            task["status"],
            task["due_date"],
            task["project_name"]
        ))

    conn.close()

    return render_template(
        "tasks.html",
        tasks=all_tasks,
        current_date=str(date.today()),
        search=search,
        sort=sort
    )


@app.route("/add-project", methods=["GET", "POST"])
def add_project():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    clients = conn.execute("""
    SELECT *
    FROM clients
    WHERE user_id = ?
    ORDER BY name ASC
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        name = request.form["name"]
        description = request.form["description"]
        status = request.form["status"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        client_id = request.form.get("client_id") or None

        estimated_budget = float(
            request.form.get("estimated_budget", 0) or 0
        )

        actual_cost = float(
            request.form.get("actual_cost", 0) or 0
        )

        conn.execute("""
        INSERT INTO projects (
            name,
            description,
            status,
            start_date,
            end_date,
            estimated_budget,
            actual_cost,
            client_id,
            user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            description,
            status,
            start_date,
            end_date,
            estimated_budget,
            actual_cost,
            client_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} created project {name}"
        )

        return redirect("/")

    conn.close()

    return render_template(
        "add_project.html",
        clients=clients
    )


@app.route("/edit-project/<int:project_id>", methods=["GET", "POST"])
def edit_project(project_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    project = conn.execute(
        "SELECT * FROM projects WHERE id = ? AND user_id = ?",
        (project_id, session["user_id"])
    ).fetchone()

    if not project:
        conn.close()
        return redirect("/")

    clients = conn.execute("""
    SELECT *
    FROM clients
    WHERE user_id = ?
    ORDER BY name ASC
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        name = request.form["name"]
        description = request.form["description"]
        status = request.form["status"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        client_id = request.form.get("client_id") or None

        estimated_budget = float(
            request.form.get("estimated_budget", 0) or 0
        )

        actual_cost = float(
            request.form.get("actual_cost", 0) or 0
        )

        conn.execute("""
        UPDATE projects
        SET name = ?,
            description = ?,
            status = ?,
            start_date = ?,
            end_date = ?,
            estimated_budget = ?,
            actual_cost = ?,
            client_id = ?
        WHERE id = ?
        AND user_id = ?
        """, (
            name,
            description,
            status,
            start_date,
            end_date,
            estimated_budget,
            actual_cost,
            client_id,
            project_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated project {name}"
        )

        return redirect("/")

    conn.close()

    return render_template(
        "edit_project.html",
        project=project,
        clients=clients
    )

@app.route("/delete-project/<int:project_id>", methods=["POST"])
def delete_project(project_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    project = conn.execute(
        "SELECT * FROM projects WHERE id = ? AND user_id = ?",
        (
            project_id,
            session["user_id"]
        )
    ).fetchone()

    conn.execute(
        "DELETE FROM tasks WHERE project_id = ?",
        (project_id,)
    )

    conn.execute(
        "DELETE FROM projects WHERE id = ? AND user_id = ?",
        (
            project_id,
            session["user_id"]
        )
    )

    conn.commit()
    conn.close()

    if project:
        create_activity(
            f"{session.get('username', 'User')} deleted project {project['name']}"
        )

    return redirect("/")


@app.route("/add-task", methods=["GET", "POST"])
def add_task():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    projects = conn.execute(
        "SELECT * FROM projects WHERE user_id = ?",
        (session["user_id"],)
    ).fetchall()

    if request.method == "POST":

        project_id = request.form["project_id"]
        title = request.form["title"]
        priority = request.form["priority"]
        status = request.form["status"]
        due_date = request.form["due_date"]
        assigned_to = request.form["assigned_to"]
        attachment_url = request.form["attachment_url"]

        estimated_hours = float(
            request.form.get("estimated_hours", 0) or 0
        )

        actual_hours = float(
            request.form.get("actual_hours", 0) or 0
        )

        hourly_rate = float(
            request.form.get("hourly_rate", 0) or 0
        )

        conn.execute("""
        INSERT INTO tasks (
            project_id,
            title,
            priority,
            status,
            due_date,
            assigned_to,
            attachment_url,
            estimated_hours,
            actual_hours,
            hourly_rate
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id,
            title,
            priority,
            status,
            due_date,
            assigned_to,
            attachment_url,
            estimated_hours,
            actual_hours,
            hourly_rate
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} created task {title}"
        )

        return redirect("/tasks")

    conn.close()

    return render_template(
        "add_task.html",
        projects=projects
    )


@app.route("/edit-task/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if not task:
        conn.close()
        return redirect("/tasks")

    if request.method == "POST":

        title = request.form["title"]
        priority = request.form["priority"]
        status = request.form["status"]
        due_date = request.form["due_date"]
        assigned_to = request.form["assigned_to"]
        attachment_url = request.form["attachment_url"]

        estimated_hours = float(
            request.form.get("estimated_hours", 0) or 0
        )

        actual_hours = float(
            request.form.get("actual_hours", 0) or 0
        )

        hourly_rate = float(
            request.form.get("hourly_rate", 0) or 0
        )

        conn.execute("""
        UPDATE tasks
        SET title = ?,
            priority = ?,
            status = ?,
            due_date = ?,
            assigned_to = ?,
            attachment_url = ?,
            estimated_hours = ?,
            actual_hours = ?,
            hourly_rate = ?
        WHERE id = ?
        """, (
            title,
            priority,
            status,
            due_date,
            assigned_to,
            attachment_url,
            estimated_hours,
            actual_hours,
            hourly_rate,
            task_id
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated task {title}"
        )

        return redirect("/tasks")

    conn.close()

    return render_template(
        "edit_task.html",
        task=task
    )

@app.route("/delete-task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    conn.commit()
    conn.close()

    if task:
        create_activity(
            f"{session.get('username', 'User')} deleted task {task['title']}"
        )

    return redirect("/tasks")


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)
        avatar_initials = username[:2].upper()

        conn = get_db_connection()

        try:
            conn.execute("""
            INSERT INTO users (
                username,
                password,
                avatar_initials
            )
            VALUES (?, ?, ?)
            """, (
                username,
                hashed_password,
                avatar_initials
            ))

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:
            conn.close()
            error = "Username already exists"

    return render_template(
        "register.html",
        error=error
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if user:
            stored_password = user["password"]

            if check_password_hash(stored_password, password) or stored_password == password:
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["avatar_initials"] = user["avatar_initials"] or user["username"][:2].upper()

                return redirect("/")

        return "Invalid username or password"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()

    return redirect("/login")

@app.route("/clients")
def clients():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    clients = conn.execute("""
    SELECT *
    FROM clients
    WHERE user_id = ?
    ORDER BY id DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    return render_template(
        "clients.html",
        clients=clients
    )

@app.route("/add-client", methods=["GET", "POST"])
def add_client():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        name = request.form.get("name", "")
        company = request.form.get("company", "")
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")
        status = request.form.get("status", "Lead")
        notes = request.form.get("notes", "")

        estimated_value = float(
            request.form.get("estimated_value", 0) or 0
        )

        conn = get_db_connection()

        conn.execute("""
        INSERT INTO clients (
            name,
            company,
            email,
            phone,
            status,
            notes,
            estimated_value,
            user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            company,
            email,
            phone,
            status,
            notes,
            estimated_value,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} added client {name}"
        )

        return redirect("/clients")

    return render_template("add_client.html")


@app.route("/edit-client/<int:client_id>", methods=["GET", "POST"])
def edit_client(client_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    client = conn.execute("""
    SELECT *
    FROM clients
    WHERE id = ?
    AND user_id = ?
    """, (
        client_id,
        session["user_id"]
    )).fetchone()

    if not client:
        conn.close()
        return redirect("/clients")

    if request.method == "POST":

        name = request.form["name"]
        company = request.form["company"]
        email = request.form["email"]
        phone = request.form["phone"]
        status = request.form["status"]
        notes = request.form["notes"]
        estimated_value = float(
            request.form.get("estimated_value", 0) or 0
        )

        conn.execute("""
        UPDATE clients
        SET name = ?,
            company = ?,
            email = ?,
            phone = ?,
            status = ?,
            notes = ?,
            estimated_value = ?
        WHERE id = ?
        AND user_id = ?
        """, (
            name,
            company,
            email,
            phone,
            status,
            notes,
            estimated_value,
            client_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated client {name}"
        )

        return redirect("/clients")

    conn.close()

    return render_template(
        "edit_client.html",
        client=client
    )


@app.route("/delete-client/<int:client_id>", methods=["POST"])
def delete_client(client_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    client = conn.execute("""
    SELECT *
    FROM clients
    WHERE id = ?
    AND user_id = ?
    """, (
        client_id,
        session["user_id"]
    )).fetchone()

    conn.execute("""
    DELETE FROM clients
    WHERE id = ?
    AND user_id = ?
    """, (
        client_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    if client:
        create_activity(
            f"{session['username']} deleted client {client['name']}"
        )

    return redirect("/clients")

@app.route("/activity")
def activity():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    activities = conn.execute("""
    SELECT *
    FROM activity_logs
    ORDER BY id DESC
    LIMIT 50
    """).fetchall()

    conn.close()

    return render_template(
        "activity.html",
        activities=activities
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )