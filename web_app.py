from flask import Flask, render_template, request, redirect, session, Response, jsonify, send_file
import sqlite3
import csv
from io import StringIO, BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
from openai import OpenAI
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
import os
import psycopg2
import psycopg2.extras

app = Flask(__name__)
openai_api_key = os.getenv("OPENAI_API_KEY")

if openai_api_key:
    client = OpenAI(api_key=openai_api_key)
else:
    client = None
app.secret_key = "secretkey"

DATABASE = "ai_pm_tracker.db"


class PostgresConnectionWrapper:

    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=None):

        cursor = self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        query = query.replace("?", "%s")

        cursor.execute(query, params or ())

        return cursor

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

    def cursor(self, *args, **kwargs):
        return self.conn.cursor(*args, **kwargs)


def get_db_connection():

    database_url = os.environ.get("DATABASE_URL")

    raw_conn = psycopg2.connect(database_url)

    raw_conn.autocommit = True

    return PostgresConnectionWrapper(raw_conn)


def ensure_column(table, column, column_type):
    pass


def init_db():

    conn = get_db_connection()

    cursor = conn.cursor()


    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (

        id SERIAL PRIMARY KEY,

        username TEXT UNIQUE,

        email TEXT,

        password TEXT,

        avatar_initials TEXT

    )
    """)

    try:
        cursor.execute("""
        ALTER TABLE users
        ADD COLUMN avatar_initials TEXT
        """)
    except Exception:
        pass


    # PROJECTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (

        id SERIAL PRIMARY KEY,

        user_id INTEGER,

        name TEXT,

        description TEXT,

        start_date TEXT,

        end_date TEXT,

        status TEXT,

        estimated_budget REAL DEFAULT 0,

        actual_cost REAL DEFAULT 0,

        created_at TEXT,

        client_id INTEGER

    )
    """)

    try:
        cursor.execute("""
        ALTER TABLE projects
        ADD COLUMN client_id INTEGER
        """)
    except Exception:
        pass


    # TASKS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (

        id SERIAL PRIMARY KEY,

        project_id INTEGER,

        title TEXT,

        description TEXT,

        assigned_to TEXT,

        priority TEXT,

        status TEXT,

        due_date TEXT,

        created_at TEXT,

        team_member_id INTEGER,

        attachment_url TEXT,

        estimated_hours REAL DEFAULT 0,

        actual_hours REAL DEFAULT 0,

        hourly_rate REAL DEFAULT 0

    )
    """)

    try:
        cursor.execute("""
        ALTER TABLE tasks
        ADD COLUMN team_member_id INTEGER
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
        ALTER TABLE tasks
        ADD COLUMN attachment_url TEXT
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
        ALTER TABLE tasks
        ADD COLUMN estimated_hours REAL DEFAULT 0
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
        ALTER TABLE tasks
        ADD COLUMN actual_hours REAL DEFAULT 0
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
        ALTER TABLE tasks
        ADD COLUMN hourly_rate REAL DEFAULT 0
        """)
    except Exception:
        pass


    # CLIENTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (

        id SERIAL PRIMARY KEY,

        user_id INTEGER,

        name TEXT,

        company TEXT,

        email TEXT,

        phone TEXT,

        status TEXT DEFAULT 'Lead',

        notes TEXT DEFAULT '',

        estimated_value REAL DEFAULT 0,

        created_at TEXT

    )
    """)


    # ACTIVITIES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activities (

        id SERIAL PRIMARY KEY,

        activity TEXT,

        created_at TEXT

    )
    """)


    # RISKS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS risks (

        id SERIAL PRIMARY KEY,

        user_id INTEGER,

        project_id INTEGER,

        title TEXT,

        description TEXT,

        probability TEXT,

        impact TEXT,

        severity_score INTEGER,

        mitigation TEXT,

        owner TEXT,

        status TEXT,

        created_at TEXT

    )
    """)


    # ISSUES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS issues (

        id SERIAL PRIMARY KEY,

        user_id INTEGER,

        project_id INTEGER,

        title TEXT,

        description TEXT,

        priority TEXT,

        owner TEXT,

        status TEXT,

        resolution TEXT,

        created_at TEXT

    )
    """)


    # CHANGES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS changes (

        id SERIAL PRIMARY KEY,

        user_id INTEGER,

        project_id INTEGER,

        title TEXT,

        description TEXT,

        impact TEXT,

        requested_by TEXT,

        approval_status TEXT,

        implementation_plan TEXT,

        created_at TEXT

    )
    """)


    # BENEFITS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS benefits (

        id SERIAL PRIMARY KEY,

        user_id INTEGER,

        project_id INTEGER,

        title TEXT,

        description TEXT,

        expected_value TEXT,

        measurement_method TEXT,

        owner TEXT,

        status TEXT,

        target_date TEXT,

        created_at TEXT

    )
    """)


    # TEAM MEMBERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS team_members (

        id SERIAL PRIMARY KEY,

        user_id INTEGER,

        name TEXT,

        role TEXT,

        email TEXT,

        phone TEXT,

        skills TEXT,

        status TEXT,

        created_at TEXT

    )
    """)


    # TASK TEAM MEMBERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_team_members (

        id SERIAL PRIMARY KEY,

        task_id INTEGER,

        team_member_id INTEGER

    )
    """)

    # ASSUMPTIONS
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS assumptions
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       title
                       TEXT,

                       description
                       TEXT,

                       owner
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    # DEPENDENCIES
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS dependencies
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       title
                       TEXT,

                       description
                       TEXT,

                       owner
                       TEXT,

                       status
                       TEXT,

                       target_date
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    # ASSUMPTIONS

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS assumptions
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       title
                       TEXT,

                       description
                       TEXT,

                       owner
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    # DEPENDENCIES

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS dependencies
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       title
                       TEXT,

                       description
                       TEXT,

                       owner
                       TEXT,

                       status
                       TEXT,

                       target_date
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    # Stakeholders table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS stakeholders
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       name
                       TEXT,

                       role
                       TEXT,

                       influence
                       TEXT,

                       interest
                       TEXT,

                       communication_plan
                       TEXT,

                       owner
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    # Decisions table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS decisions
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       title
                       TEXT,

                       decision_maker
                       TEXT,

                       impact
                       TEXT,

                       reason
                       TEXT,

                       status
                       TEXT,

                       decision_date
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    # Lessons Learned table

    cursor.execute("""

                   CREATE TABLE IF NOT EXISTS lessons

                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       title
                       TEXT,

                       what_happened
                       TEXT,

                       what_went_well
                       TEXT,

                       what_went_wrong
                       TEXT,

                       recommendation
                       TEXT,

                       owner
                       TEXT,

                       created_at
                       TEXT

                   )

                   """)

    # Actions table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS actions
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       title
                       TEXT,

                       description
                       TEXT,

                       owner
                       TEXT,

                       priority
                       TEXT,

                       status
                       TEXT,

                       due_date
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS budgets
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       budget_amount
                       NUMERIC,

                       actual_cost
                       NUMERIC,

                       forecast_cost
                       NUMERIC,

                       approved_by
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    # Stage Gates table

    cursor.execute("""

                   CREATE TABLE IF NOT EXISTS stage_gates

                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       stage_name
                       TEXT,

                       status
                       TEXT,

                       reviewer
                       TEXT,

                       comments
                       TEXT,

                       review_date
                       TEXT,

                       created_at
                       TEXT

                   )

                   """)

    # Approvals Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS approvals
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       user_id
                       INTEGER,
                       project_id
                       INTEGER,
                       item_type
                       TEXT,
                       item_id
                       INTEGER,
                       submitted_by
                       TEXT,
                       approver
                       TEXT,
                       status
                       TEXT
                       DEFAULT
                       'Draft',
                       submitted_date
                       DATE,
                       decision_date
                       DATE,
                       comments
                       TEXT
                   )
                   """)
    try:
        cursor.execute("""
                       ALTER TABLE approvals
                           ADD COLUMN user_id INTEGER
                       """)
    except:
        pass

    # Governance Reviews Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS governance_reviews
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       review_name
                       TEXT,

                       review_type
                       TEXT,

                       review_date
                       DATE,

                       outcome
                       TEXT,

                       decision
                       TEXT,

                       actions
                       TEXT,

                       owner
                       TEXT,

                       next_review_date
                       DATE,

                       status
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)

    # Project Prioritisation Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS project_prioritisation
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       business_value_score
                       INTEGER,

                       strategic_alignment_score
                       INTEGER,

                       risk_score
                       INTEGER,

                       cost_score
                       INTEGER,

                       priority_score
                       INTEGER,

                       created_at
                       TEXT
                   )
                   """)


    conn.commit()

    conn.close()


init_db()


def create_demo_user():
    pass


create_demo_user()


def is_overdue(due_date, status):
    if not due_date:
        return False

    return due_date < str(date.today()) and status != "Completed"

@app.route("/")
def home():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT
        projects.*,
        clients.name AS client_name,
        clients.company AS client_company
    FROM projects
    LEFT JOIN clients
    ON projects.client_id = clients.id
    WHERE projects.user_id = %s
    ORDER BY projects.id DESC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    cursor.execute("""
    SELECT *
    FROM clients
    WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    clients = cursor.fetchall()

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
    smart_insights = []
    delivery_insights = []
    notifications = []

    for client in clients:
        total_client_value += float(client["estimated_value"] or 0)

    for project in projects:

        estimated_budget = float(project["estimated_budget"] or 0)
        base_actual_cost = float(project["actual_cost"] or 0)

        total_budget += estimated_budget

        if project["client_name"]:
            active_clients.add(project["client_name"])

        cursor.execute("""
        SELECT *
        FROM tasks
        WHERE project_id = %s
        ORDER BY
            CASE
                WHEN due_date IS NULL OR due_date = ''
                THEN '9999-12-31'
                ELSE due_date
            END ASC
        """, (
            project["id"],
        ))

        tasks = cursor.fetchall()

        task_list = []
        task_actual_cost_total = 0

        for task in tasks:

            total_tasks += 1

            task_actual_hours = float(task["actual_hours"] or 0)
            task_hourly_rate = float(task["hourly_rate"] or 0)

            task_actual_cost_total += task_actual_hours * task_hourly_rate

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

            if is_overdue(task["due_date"], task["status"]):
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

        actual_cost = base_actual_cost + task_actual_cost_total
        total_actual_cost += actual_cost

        remaining_budget = estimated_budget - actual_cost

        if estimated_budget > 0 and actual_cost > estimated_budget:
            over_budget_projects += 1

        if estimated_budget > 0:
            budget_used_percent = round((actual_cost / estimated_budget) * 100)
        else:
            budget_used_percent = 0

        if len(tasks) > 0:
            completed_for_project = len([
                task for task in tasks
                if task["status"] == "Completed"
            ])
            completion = round((completed_for_project / len(tasks)) * 100)
        else:
            completion = 0

        risk_score = 0

        if completion < 30:
            risk_score += 25

        if budget_used_percent > 100:
            risk_score += 30
        elif budget_used_percent > 80:
            risk_score += 15

        project_overdue_tasks = len([
            task for task in tasks
            if is_overdue(task["due_date"], task["status"])
        ])

        risk_score += project_overdue_tasks * 10

        project_blocked_tasks = len([
            task for task in tasks
            if task["status"] == "Blocked"
        ])

        risk_score += project_blocked_tasks * 15

        project_high_priority = len([
            task for task in tasks
            if task["priority"] == "High" and task["status"] != "Completed"
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

        ai_recommendation = []

        if project_overdue_tasks > 0:
            ai_recommendation.append("Resolve overdue tasks immediately.")

        if project_blocked_tasks > 0:
            ai_recommendation.append("Blocked tasks require escalation.")

        if budget_used_percent > 90:
            ai_recommendation.append("Budget usage is critically high.")

        if completion < 30:
            ai_recommendation.append("Project delivery pace is behind schedule.")

        if not ai_recommendation:
            ai_recommendation.append("Project performance currently appears stable.")

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


    upcoming_deadlines = sorted(
        upcoming_deadlines,
        key=lambda item: item["due_date"]
    )[:5]

    if total_tasks > 0:
        completion_rate = round((completed_tasks / total_tasks) * 100)
    else:
        completion_rate = 0

    total_remaining_budget = total_budget - total_actual_cost

    if total_budget > 0:
        budget_usage_percent = round((total_actual_cost / total_budget) * 100)
        profitability_score = round((total_remaining_budget / total_budget) * 100)
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

    if overdue_tasks > 0 or blocked_tasks > 0 or over_budget_projects > 0:
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

    if overdue_tasks > 0:
        smart_insights.append(f"You have {overdue_tasks} overdue task(s).")

    if blocked_tasks > 0:
        smart_insights.append(f"{blocked_tasks} task(s) are blocked.")

    if over_budget_projects > 0:
        smart_insights.append(f"{over_budget_projects} project(s) are over budget.")

    if high_priority_tasks > 0:
        smart_insights.append(f"{high_priority_tasks} high-priority task(s) need attention.")

    if upcoming_deadlines:
        smart_insights.append(f"{len(upcoming_deadlines)} upcoming deadline(s) are active.")

    if not smart_insights:
        smart_insights.append("No major delivery risks detected right now.")

    if overdue_tasks > 0:
        delivery_insights.append({
            "title": "Overdue Delivery Risk",
            "message": f"{overdue_tasks} task(s) are overdue and may delay delivery.",
            "level": "High"
        })

    if blocked_tasks > 0:
        delivery_insights.append({
            "title": "Blocked Work",
            "message": f"{blocked_tasks} blocked task(s) need escalation.",
            "level": "High"
        })

    if high_priority_tasks > 0:
        delivery_insights.append({
            "title": "Priority Pressure",
            "message": f"{high_priority_tasks} high-priority task(s) need attention.",
            "level": "Medium"
        })

    if over_budget_projects > 0:
        delivery_insights.append({
            "title": "Budget Pressure",
            "message": f"{over_budget_projects} project(s) are over budget.",
            "level": "High"
        })

    if not delivery_insights:
        delivery_insights.append({
            "title": "Stable Delivery",
            "message": "No major delivery risks detected right now.",
            "level": "Low"
        })

    workload_summary = {
        "active": in_progress_tasks + pending_tasks,
        "completed": completed_tasks,
        "blocked": blocked_tasks,
        "overdue": overdue_tasks
    }

    if overdue_tasks > 0:
        notifications.append(f"You have {overdue_tasks} overdue task(s).")

    if blocked_tasks > 0:
        notifications.append(f"{blocked_tasks} task(s) are blocked.")

    if over_budget_projects > 0:
        notifications.append(f"{over_budget_projects} project(s) are over budget.")

    cursor.execute("""
                   SELECT COUNT(*) AS open_risks
                   FROM risks
                   WHERE user_id = %s
                     AND status != 'Closed'
                   """, (
                       session["user_id"],
                   ))

    open_risks = cursor.fetchone()["open_risks"]

    cursor.execute("""
                   SELECT COUNT(*) AS open_issues
                   FROM issues
                   WHERE user_id = %s
                     AND status != 'Closed'
                   """, (
                       session["user_id"],
                   ))

    open_issues = cursor.fetchone()["open_issues"]

    # Risk card colour
    if open_risks == 0:
        risk_card_class = "green-card"
    elif open_risks <= 3:
        risk_card_class = "amber-card"
    else:
        risk_card_class = "red-card"

    # Issue card colour
    if open_issues == 0:
        issue_card_class = "green-card"
    elif open_issues <= 3:
        issue_card_class = "amber-card"
    else:
        issue_card_class = "red-card"

    health_score = 100

    health_score -= (overdue_tasks * 10)
    health_score -= (blocked_tasks * 5)
    health_score -= (open_risks * 5)
    health_score -= (open_issues * 3)

    health_score = max(0, min(100, health_score))

    if health_score >= 80:
        health_status = "Excellent"
    elif health_score >= 60:
        health_status = "Stable"
    elif health_score >= 40:
        health_status = "At Risk"
    else:
        health_status = "Critical"

    conn.close()

    return render_template(
        "index.html",
        projects=all_projects,
        total_projects=len(projects),
        total_tasks=total_tasks,
        open_risks=open_risks,
        risk_card_class=risk_card_class,
        issue_card_class=issue_card_class,
        open_issues=open_issues,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        in_progress_tasks=in_progress_tasks,
        blocked_tasks=blocked_tasks,
        high_priority_tasks=high_priority_tasks,
        medium_priority_tasks=medium_priority_tasks,
        low_priority_tasks=low_priority_tasks,
        overdue_tasks=overdue_tasks,
        completion_rate=completion_rate,
        project_health_score=health_score,
        project_health_label=health_status,
        smart_insights=smart_insights,
        delivery_insights=delivery_insights,
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
    SELECT
        tasks.*,
        projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    ORDER BY tasks.id DESC
    """, (
        session["user_id"],
    )).fetchall()

    grouped_tasks = {
        "Pending": [],
        "In Progress": [],
        "Completed": []
    }

    for task in tasks:

        members = conn.execute("""
        SELECT
            team_members.name,
            team_members.role
        FROM task_team_members
        JOIN team_members
        ON task_team_members.team_member_id = team_members.id
        WHERE task_team_members.task_id = ?
        """, (
            task["id"],
        )).fetchall()

        team_members = []

        for member in members:

            if member["role"]:

                team_members.append(
                    f"{member['name']} - {member['role']}"
                )

            else:

                team_members.append(
                    member["name"]
                )

        task_data = {
            "task": task,
            "team_members": team_members
        }

        status = task["status"]

        if status in grouped_tasks:
            grouped_tasks[status].append(task_data)

    conn.close()

    return render_template(
        "kanban.html",
        grouped_tasks=grouped_tasks
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

    conn.execute("""
    UPDATE tasks
    SET status = ?
    WHERE id = ?
    """, (
        new_status,
        task_id
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} moved task #{task_id} to {new_status}"
    )

    return jsonify({"success": True})


@app.route("/calendar")
def calendar():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT
        tasks.*,
        projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = %s
    AND tasks.due_date IS NOT NULL
    AND tasks.due_date != ''
    ORDER BY tasks.due_date ASC
    """, (
        session["user_id"],
    ))

    tasks = cursor.fetchall()

    calendar_items = []

    for task in tasks:

        calendar_items.append({
            "title": task["title"],
            "date": task["due_date"],
            "type": "Task",
            "project_name": task["project_name"],
            "status": task["status"]
        })

    conn.close()

    return render_template(
        "calendar.html",
        tasks=tasks,
        calendar_items=calendar_items,
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

    completed_tasks = len([
        task for task in tasks
        if task["status"] == "Completed"
    ])

    overdue_tasks = len([
        task for task in tasks
        if is_overdue(
            task["due_date"],
            task["status"]
        )
    ])

    if total_tasks > 0:
        completion_rate = round(
            (completed_tasks / total_tasks) * 100
        )
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

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    """, (session["user_id"],)).fetchall()

    tasks = conn.execute("""
    SELECT tasks.*, projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    """, (session["user_id"],)).fetchall()

    risks = conn.execute("""
    SELECT *
    FROM risks
    WHERE user_id = ?
    """, (session["user_id"],)).fetchall()

    issues = conn.execute("""
    SELECT *
    FROM issues
    WHERE user_id = ?
    """, (session["user_id"],)).fetchall()

    conn.close()

    total_projects = len(projects)
    total_tasks = len(tasks)

    completed_tasks = len([
        t for t in tasks
        if t["status"] == "Completed"
    ])

    pending_tasks = len([
        t for t in tasks
        if t["status"] == "Pending"
    ])

    open_risks = len(risks)
    open_issues = len(issues)

    completion_rate = 0

    if total_tasks > 0:
        completion_rate = round(
            (completed_tasks / total_tasks) * 100
        )

    buffer = BytesIO()

    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 50

    # TITLE

    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(
        50,
        y,
        "AI Project Management Executive Report"
    )

    y -= 30

    pdf.setFont("Helvetica", 11)
    pdf.drawString(
        50,
        y,
        f"Generated: {date.today()}"
    )

    # EXECUTIVE SUMMARY

    y -= 50

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "Executive Summary")

    y -= 25

    pdf.setFont("Helvetica", 11)

    pdf.drawString(
        50,
        y,
        f"Projects Managed: {total_projects}"
    )

    y -= 18

    pdf.drawString(
        50,
        y,
        f"Total Tasks: {total_tasks}"
    )

    y -= 18

    pdf.drawString(
        50,
        y,
        f"Completion Rate: {completion_rate}%"
    )

    # DELIVERY HEALTH

    y -= 40

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "Delivery Health")

    y -= 25

    pdf.setFont("Helvetica", 11)

    pdf.drawString(
        50,
        y,
        f"Completed Tasks: {completed_tasks}"
    )

    y -= 18

    pdf.drawString(
        50,
        y,
        f"Pending Tasks: {pending_tasks}"
    )

    # RAID SUMMARY

    y -= 40

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "RAID Summary")

    y -= 25

    pdf.setFont("Helvetica", 11)

    pdf.drawString(
        50,
        y,
        f"Open Risks: {open_risks}"
    )

    y -= 18

    pdf.drawString(
        50,
        y,
        f"Open Issues: {open_issues}"
    )

    # PROJECTS

    y -= 40

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "Project Portfolio")

    y -= 25

    pdf.setFont("Helvetica", 10)

    for project in projects:

        if y < 80:
            pdf.showPage()
            y = height - 50

        pdf.drawString(
            60,
            y,
            f"{project['name']} ({project['status']})"
        )

        y -= 18

    # TOP TASKS

    y -= 20

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "Upcoming Tasks")

    y -= 25

    pdf.setFont("Helvetica", 10)

    for task in tasks[:10]:

        if y < 80:
            pdf.showPage()
            y = height - 50

        pdf.drawString(
            60,
            y,
            f"{task['title']} | {task['status']} | {task['project_name']}"
        )

        y -= 18

    pdf.save()

    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={
            "Content-Disposition":
            "attachment; filename=executive_project_report.pdf"
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

    conn = get_db_connection()

    tasks = conn.execute("""
    SELECT
        tasks.*,
        projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    ORDER BY tasks.id DESC
    """, (
        session["user_id"],
    )).fetchall()

    all_tasks = []

    for task in tasks:

        members = conn.execute("""
        SELECT
            team_members.name,
            team_members.role
        FROM task_team_members
        JOIN team_members
        ON task_team_members.team_member_id = team_members.id
        WHERE task_team_members.task_id = ?
        """, (
            task["id"],
        )).fetchall()

        team_members = []

        for member in members:

            if member["role"]:

                team_members.append(
                    f"{member['name']} - {member['role']}"
                )

            else:

                team_members.append(
                    member["name"]
                )

        all_tasks.append({
            "task": task,
            "team_members": team_members
        })

    conn.close()

    return render_template(
        "tasks.html",
        all_tasks=all_tasks
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

        name = request.form.get("name", "")
        description = request.form.get("description", "")
        status = request.form.get("status", "Planning")
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        client_id = request.form.get("client_id")

        estimated_budget = float(
            request.form.get("estimated_budget", 0) or 0
        )

        actual_cost = float(
            request.form.get("actual_cost", 0) or 0
        )

        conn.execute("""
        INSERT INTO projects (
            user_id,
            client_id,
            name,
            description,
            start_date,
            end_date,
            status,
            estimated_budget,
            actual_cost,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            client_id if client_id else None,
            name,
            description,
            start_date,
            end_date,
            status,
            estimated_budget,
            actual_cost,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} added a project"
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

    clients = conn.execute("""
    SELECT *
    FROM clients
    WHERE user_id = ?
    ORDER BY name ASC
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        name = request.form.get("name", "")
        description = request.form.get("description", "")
        status = request.form.get("status", "Planning")
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        client_id = request.form.get("client_id")

        estimated_budget = float(
            request.form.get("estimated_budget", 0) or 0
        )

        actual_cost = float(
            request.form.get("actual_cost", 0) or 0
        )

        conn.execute("""
        UPDATE projects
        SET
            client_id = ?,
            name = ?,
            description = ?,
            start_date = ?,
            end_date = ?,
            status = ?,
            estimated_budget = ?,
            actual_cost = ?
        WHERE id = ?
        AND user_id = ?
        """, (
            client_id if client_id else None,
            name,
            description,
            start_date,
            end_date,
            status,
            estimated_budget,
            actual_cost,
            project_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated a project"
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

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    ORDER BY name ASC
    """, (
        session["user_id"],
    )).fetchall()

    team_members = conn.execute("""
    SELECT *
    FROM team_members
    WHERE user_id = ?
    ORDER BY name ASC
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        assigned_to = request.form.get("assigned_to", "")
        priority = request.form.get("priority", "Medium")
        status = request.form.get("status", "Pending")
        due_date = request.form.get("due_date", "")

        selected_team_members = request.form.getlist("team_member_ids")

        estimated_hours = float(
            request.form.get("estimated_hours", 0) or 0
        )

        actual_hours = float(
            request.form.get("actual_hours", 0) or 0
        )

        hourly_rate = float(
            request.form.get("hourly_rate", 0) or 0
        )

        cursor = conn.execute("""
        INSERT INTO tasks (
            project_id,
            title,
            description,
            assigned_to,
            priority,
            status,
            due_date,
            estimated_hours,
            actual_hours,
            hourly_rate,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id,
            title,
            description,
            assigned_to,
            priority,
            status,
            due_date,
            estimated_hours,
            actual_hours,
            hourly_rate,
            str(date.today())
        ))

        task_id = cursor.lastrowid

        for member_id in selected_team_members:

            conn.execute("""
            INSERT INTO task_team_members (
                task_id,
                team_member_id
            )
            VALUES (?, ?)
            """, (
                task_id,
                member_id
            ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} added a task"
        )

        return redirect("/tasks")

    conn.close()

    return render_template(
        "add_task.html",
        projects=projects,
        team_members=team_members
    )

@app.route("/edit-task/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    task = conn.execute("""
    SELECT
        tasks.*
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
        return redirect("/tasks")

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    ORDER BY name ASC
    """, (
        session["user_id"],
    )).fetchall()

    team_members = conn.execute("""
    SELECT *
    FROM team_members
    WHERE user_id = ?
    ORDER BY name ASC
    """, (
        session["user_id"],
    )).fetchall()

    selected_members = conn.execute("""
    SELECT team_member_id
    FROM task_team_members
    WHERE task_id = ?
    """, (
        task_id,
    )).fetchall()

    selected_member_ids = [
        member["team_member_id"]
        for member in selected_members
    ]

    if request.method == "POST":

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        assigned_to = request.form.get("assigned_to", "")
        priority = request.form.get("priority", "Medium")
        status = request.form.get("status", "Pending")
        due_date = request.form.get("due_date", "")

        selected_team_members = request.form.getlist("team_member_ids")

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
        SET
            project_id = ?,
            title = ?,
            description = ?,
            assigned_to = ?,
            priority = ?,
            status = ?,
            due_date = ?,
            estimated_hours = ?,
            actual_hours = ?,
            hourly_rate = ?
        WHERE id = ?
        """, (
            project_id,
            title,
            description,
            assigned_to,
            priority,
            status,
            due_date,
            estimated_hours,
            actual_hours,
            hourly_rate,
            task_id
        ))

        conn.execute("""
        DELETE FROM task_team_members
        WHERE task_id = ?
        """, (
            task_id,
        ))

        for member_id in selected_team_members:

            conn.execute("""
            INSERT INTO task_team_members (
                task_id,
                team_member_id
            )
            VALUES (?, ?)
            """, (
                task_id,
                member_id
            ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated a task"
        )

        return redirect("/tasks")

    conn.close()

    return render_template(
        "edit_task.html",
        task=task,
        projects=projects,
        team_members=team_members,
        selected_member_ids=selected_member_ids
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

        return redirect("/clients")

    return render_template("add_client.html")

@app.route("/activity")
def activity():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT *
    FROM activities
    ORDER BY id DESC
    LIMIT 100
    """)

    activities = cursor.fetchall()

    conn.close()

    return render_template(
        "activity.html",
        activities=activities
    )

def create_activity(activity_text):

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO activities (
            activity,
            created_at
        )
        VALUES (%s, %s)
        """, (
            activity_text,
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        print("Activity logging failed:", e)


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

        name = request.form.get("name", "")
        company = request.form.get("company", "")
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")
        status = request.form.get("status", "Lead")
        notes = request.form.get("notes", "")

        estimated_value = float(
            request.form.get("estimated_value", 0) or 0
        )

        conn.execute("""
        UPDATE clients
        SET
            name = ?,
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
            f"{session['username']} updated a client"
        )

        return redirect("/clients")

    conn.close()

    return render_template(
        "edit_client.html",
        client=client
    )


@app.route("/delete-client/<int:client_id>")
def delete_client(client_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

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

    create_activity(
        f"{session['username']} deleted a client"
    )

    return redirect("/clients")


@app.route("/advanced-search")
def advanced_search():

    if "user_id" not in session:
        return redirect("/login")

    search = request.args.get("search", "")

    conn = get_db_connection()

    tasks = conn.execute("""
    SELECT
        tasks.*,
        projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    AND (
        tasks.title LIKE ?
        OR projects.name LIKE ?
        OR tasks.status LIKE ?
        OR tasks.priority LIKE ?
    )
    ORDER BY tasks.id DESC
    """, (
        session["user_id"],
        f"%{search}%",
        f"%{search}%",
        f"%{search}%",
        f"%{search}%"
    )).fetchall()

    conn.close()

    return render_template(
        "advanced_search.html",
        tasks=tasks,
        search=search
    )

@app.route("/gantt")
def gantt():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT
        projects.*,
        clients.name AS client_name
    FROM projects
    LEFT JOIN clients
    ON projects.client_id = clients.id
    WHERE projects.user_id = %s
    ORDER BY
        CASE
            WHEN projects.start_date IS NULL OR projects.start_date = ''
            THEN '9999-12-31'
            ELSE projects.start_date
        END ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    gantt_projects = []

    for project in projects:

        cursor.execute("""
        SELECT COUNT(*) AS total_tasks
        FROM tasks
        WHERE project_id = %s
        """, (
            project["id"],
        ))

        total_tasks = cursor.fetchone()["total_tasks"]

        cursor.execute("""
        SELECT COUNT(*) AS completed_tasks
        FROM tasks
        WHERE project_id = %s
        AND status = 'Completed'
        """, (
            project["id"],
        ))

        completed_tasks = cursor.fetchone()["completed_tasks"]

        if total_tasks > 0:
            progress = round((completed_tasks / total_tasks) * 100)
        else:
            progress = 0

        gantt_projects.append({
            "id": project["id"],
            "name": project["name"],
            "status": project["status"],
            "client_name": project["client_name"],
            "start_date": project["start_date"],
            "end_date": project["end_date"],
            "progress": progress
        })

    conn.close()

    return render_template(
        "gantt.html",
        projects=gantt_projects,
        current_date=str(date.today())
    )

@app.route("/analytics")
def analytics():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT
        tasks.*,
        projects.name AS project_name
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = %s
    """, (
        session["user_id"],
    ))

    tasks = cursor.fetchall()

    total_tasks = len(tasks)

    completed_tasks = 0
    pending_tasks = 0
    in_progress_tasks = 0
    blocked_tasks = 0

    high_priority = 0
    medium_priority = 0
    low_priority = 0

    overdue_tasks = 0

    for task in tasks:

        if task["status"] == "Completed":
            completed_tasks += 1

        elif task["status"] == "Pending":
            pending_tasks += 1

        elif task["status"] == "In Progress":
            in_progress_tasks += 1

        elif task["status"] == "Blocked":
            blocked_tasks += 1

        if task["priority"] == "High":
            high_priority += 1

        elif task["priority"] == "Medium":
            medium_priority += 1

        elif task["priority"] == "Low":
            low_priority += 1

        if is_overdue(
            task["due_date"],
            task["status"]
        ):
            overdue_tasks += 1

    if total_tasks > 0:
        completion_rate = round(
            (completed_tasks / total_tasks) * 100
        )
    else:
        completion_rate = 0

    conn.close()

    return render_template(
        "analytics.html",
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        in_progress_tasks=in_progress_tasks,
        blocked_tasks=blocked_tasks,
        high_priority=high_priority,
        medium_priority=medium_priority,
        low_priority=low_priority,
        overdue_tasks=overdue_tasks,
        completion_rate=completion_rate,
        chart_status_data=[
            completed_tasks,
            pending_tasks,
            in_progress_tasks,
            blocked_tasks
        ],
        chart_priority_data=[
            high_priority,
            medium_priority,
            low_priority
        ]
    )

@app.route("/ai-assistant", methods=["GET", "POST"])
def ai_assistant():

    if "user_id" not in session:
        return redirect("/login")

    response_message = ""

    if request.method == "POST":

        prompt = request.form.get("prompt", "")

        conn = get_db_connection()

        total_tasks = conn.execute("""
        SELECT COUNT(*)
        FROM tasks
        """).fetchone()[0]

        completed_tasks = conn.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE status = 'Completed'
        """).fetchone()[0]

        overdue_tasks = conn.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE due_date < ?
        AND status != 'Completed'
        """, (
            str(date.today()),
        )).fetchone()[0]

        blocked_tasks = conn.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE status = 'Blocked'
        """).fetchone()[0]

        high_priority_tasks = conn.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE priority = 'High'
        AND status != 'Completed'
        """).fetchone()[0]

        total_projects = conn.execute("""
        SELECT COUNT(*)
        FROM projects
        """).fetchone()[0]

        over_budget_projects = conn.execute("""
        SELECT COUNT(*)
        FROM projects
        WHERE estimated_budget > 0
        AND actual_cost > estimated_budget
        """).fetchone()[0]

        conn.close()

        if client is None:

            response_message = (
                "AI assistant is not connected yet. "
                "Please add OPENAI_API_KEY "
                "inside Render environment variables."
            )

        else:

            try:

                completion = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an AI project management assistant. "
                                "Help the user understand delivery risks, "
                                "budgets, blockers, task priorities "
                                "and project health."
                            )
                        },
                        {
                            "role": "user",
                            "content": (
                                f"""
User question:
{prompt}

Project statistics:
- Total projects: {total_projects}
- Total tasks: {total_tasks}
- Completed tasks: {completed_tasks}
- Overdue tasks: {overdue_tasks}
- Blocked tasks: {blocked_tasks}
- High priority open tasks: {high_priority_tasks}
- Over-budget projects: {over_budget_projects}

Give practical project management advice.
                                """
                            )
                        }
                    ]
                )

                response_message = (
                    completion.choices[0]
                    .message
                    .content
                )

            except Exception as e:

                response_message = (
                    f"AI assistant error: {str(e)}"
                )

    return render_template(
        "ai_assistant.html",
        response_message=response_message
    )

@app.route("/export-report")
def export_report():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT COUNT(*) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (session["user_id"],))
    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS total_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
    """, (session["user_id"],))
    total_tasks = cursor.fetchone()["total_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS completed_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Completed'
    """, (session["user_id"],))
    completed_tasks = cursor.fetchone()["completed_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS total_risks
        FROM risks
        WHERE user_id = %s
    """, (session["user_id"],))
    total_risks = cursor.fetchone()["total_risks"]

    cursor.execute("""
        SELECT COUNT(*) AS total_issues
        FROM issues
        WHERE user_id = %s
    """, (session["user_id"],))
    total_issues = cursor.fetchone()["total_issues"]

    cursor.execute("""
        SELECT COUNT(*) AS total_changes
        FROM changes
        WHERE user_id = %s
    """, (session["user_id"],))
    total_changes = cursor.fetchone()["total_changes"]

    cursor.execute("""
        SELECT COUNT(*) AS total_benefits
        FROM benefits
        WHERE user_id = %s
    """, (session["user_id"],))
    total_benefits = cursor.fetchone()["total_benefits"]

    cursor.execute("""
        SELECT COUNT(*) AS realised_benefits
        FROM benefits
        WHERE user_id = %s
        AND status = 'Realised'
    """, (session["user_id"],))
    realised_benefits = cursor.fetchone()["realised_benefits"]

    cursor.execute("""
        SELECT COUNT(*) AS in_progress_benefits
        FROM benefits
        WHERE user_id = %s
        AND status = 'In Progress'
    """, (session["user_id"],))
    in_progress_benefits = cursor.fetchone()["in_progress_benefits"]

    cursor.execute("""
        SELECT COUNT(*) AS at_risk_benefits
        FROM benefits
        WHERE user_id = %s
        AND status = 'At Risk'
    """, (session["user_id"],))
    at_risk_benefits = cursor.fetchone()["at_risk_benefits"]

    cursor.execute("""
        SELECT COUNT(*) AS total_team_members
        FROM team_members
        WHERE user_id = %s
    """, (session["user_id"],))
    total_team_members = cursor.fetchone()["total_team_members"]

    cursor.execute("""
                   SELECT COUNT(*) AS total_stakeholders
                   FROM stakeholders
                   WHERE user_id = %s
                   """, (session["user_id"],))

    total_stakeholders = cursor.fetchone()["total_stakeholders"]

    cursor.execute("""
                   SELECT COUNT(*) AS high_influence
                   FROM stakeholders
                   WHERE user_id = %s
                     AND influence = 'High'
                   """, (session["user_id"],))

    high_influence = cursor.fetchone()["high_influence"]

    cursor.execute("""
                   SELECT COUNT(*) AS medium_influence
                   FROM stakeholders
                   WHERE user_id = %s
                     AND influence = 'Medium'
                   """, (session["user_id"],))

    medium_influence = cursor.fetchone()["medium_influence"]

    cursor.execute("""
                   SELECT COUNT(*) AS low_influence
                   FROM stakeholders
                   WHERE user_id = %s
                     AND influence = 'Low'
                   """, (session["user_id"],))

    low_influence = cursor.fetchone()["low_influence"]

    cursor.execute("""
                   SELECT title
                   FROM risks
                   WHERE user_id = %s
                   ORDER BY id DESC LIMIT 3
                   """, (session["user_id"],))

    top_risks = cursor.fetchall()

    cursor.execute("""
                   SELECT title
                   FROM issues
                   WHERE user_id = %s
                   ORDER BY id DESC LIMIT 3
                   """, (session["user_id"],))

    top_issues = cursor.fetchall()



    conn.close()

    completion_percentage = 0

    if total_tasks > 0:
        completion_percentage = round(
            (completed_tasks / total_tasks) * 100
        )

    if completion_percentage >= 75:
        portfolio_health = "Green"
    elif completion_percentage >= 40:
        portfolio_health = "Amber"
    else:
        portfolio_health = "Red"

    pdf_buffer = BytesIO()

    doc = SimpleDocTemplate(pdf_buffer)

    styles = getSampleStyleSheet()

    content = []

    content.append(
        Paragraph(
            "AI PM Tracker Executive Portfolio Report",
            styles["Title"]
        )
    )

    content.append(
        Paragraph(
            f"Generated: {date.today()}",
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 20))

    content.append(
        Paragraph(
            "Portfolio Summary",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            f"Total Projects: {total_projects}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"Total Tasks: {total_tasks}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"Completed Tasks: {completed_tasks}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"Completion Rate: {completion_percentage}%",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"Portfolio Health: {portfolio_health}",
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 15))

    content.append(
        Paragraph(
            "Governance Summary",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            f"Risk Register Items: {total_risks}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"Issue Register Items: {total_issues}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"Change Register Items: {total_changes}",
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 15))

    content.append(
        Paragraph(
            "Benefits Summary",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            f"Benefits Logged: {total_benefits}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"Realised Benefits: {realised_benefits}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"In Progress Benefits: {in_progress_benefits}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"At Risk Benefits: {at_risk_benefits}",
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 15))

    content.append(
        Paragraph(
            "Team Summary",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            f"Team Members: {total_team_members}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"Available Resources: {total_team_members}",
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 15))

    content.append(
        Paragraph(
            "Stakeholder Summary",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            f"Total Stakeholders: {total_stakeholders}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"High Influence: {high_influence}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"Medium Influence: {medium_influence}",
            styles["BodyText"]
        )
    )

    content.append(
        Paragraph(
            f"Low Influence: {low_influence}",
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 15))

    content.append(
        Paragraph(
            "Top Issues",
            styles["Heading2"]
        )
    )

    if top_issues:

        for issue in top_issues:
            content.append(
                Paragraph(
                    f"- {issue['title']}",
                    styles["BodyText"]
                )
            )

    else:

        content.append(
            Paragraph(
                "No issues recorded.",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 15))

    content.append(
        Paragraph(
            "Top Risks",
            styles["Heading2"]
        )
    )

    if top_risks:

        for risk in top_risks:
            content.append(
                Paragraph(
                    f"- {risk['title']}",
                    styles["BodyText"]
                )
            )

    else:

        content.append(
            Paragraph(
                "No risks recorded.",
                styles["BodyText"]
            )
        )

    content.append(
        Paragraph(
            "Executive Commentary",
            styles["Heading2"]
        )
    )

    if completion_percentage >= 75:
        commentary = (
            "Portfolio performance is healthy. "
            "Project delivery is progressing well with a strong completion rate."
        )
    elif completion_percentage >= 40:
        commentary = (
            "Portfolio delivery is progressing steadily. "
            "Management attention should focus on risks, issues and upcoming milestones."
        )
    else:
        commentary = (
            "Portfolio performance requires attention. "
            "Project delivery and governance controls should be reviewed."
        )

    content.append(
        Paragraph(
            commentary,
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 20))

    content.append(
        Paragraph(
            "Generated by AI PM Tracker",
            styles["Italic"]
        )
    )

    content.append(
        Paragraph(
            "Governance Foundation Executive Report",
            styles["Italic"]
        )
    )

    doc.build(content)

    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="Executive_Portfolio_Report.pdf",
        mimetype="application/pdf"
    )

@app.route("/risks")
def risks():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    risks = conn.execute("""
    SELECT
        risks.*,
        projects.name AS project_name
    FROM risks
    LEFT JOIN projects
    ON risks.project_id = projects.id
    WHERE risks.user_id = ?
    ORDER BY severity_score DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    return render_template(
        "risks.html",
        risks=risks
    )

@app.route("/add-risk", methods=["GET", "POST"])
def add_risk():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        project_id = request.form["project_id"]

        title = request.form["title"]

        description = request.form["description"]

        probability = request.form["probability"]

        impact = request.form["impact"]

        mitigation = request.form["mitigation"]

        owner = request.form["owner"]

        status = request.form["status"]

        probability_map = {
            "Low": 1,
            "Medium": 2,
            "High": 3
        }

        impact_map = {
            "Low": 1,
            "Medium": 2,
            "High": 3
        }

        severity_score = (
            probability_map[probability]
            *
            impact_map[impact]
        )

        conn.execute("""
        INSERT INTO risks (
            user_id,
            project_id,
            title,
            description,
            probability,
            impact,
            severity_score,
            mitigation,
            owner,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            project_id,
            title,
            description,
            probability,
            impact,
            severity_score,
            mitigation,
            owner,
            status,
            str(date.today())
        ))

        conn.commit()

        conn.close()

        create_activity(
            f"{session['username']} added a new project risk"
        )

        return redirect("/risks")

    conn.close()

    return render_template(
        "add_risk.html",
        projects=projects
    )

@app.route("/issues")
def issues():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    issues = conn.execute("""
    SELECT
        issues.*,
        projects.name AS project_name
    FROM issues
    LEFT JOIN projects
    ON issues.project_id = projects.id
    WHERE issues.user_id = ?
    ORDER BY
        CASE
            WHEN issues.status IN ('Resolved', 'Closed') THEN 2
            ELSE 1
        END,
        CASE
            WHEN issues.priority = 'High' THEN 1
            WHEN issues.priority = 'Medium' THEN 2
            ELSE 3
        END,
        issues.created_at DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    return render_template(
        "issues.html",
        issues=issues
    )

@app.route("/add-issue", methods=["GET", "POST"])
def add_issue():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        project_id = request.form["project_id"]

        title = request.form["title"]

        description = request.form["description"]

        priority = request.form["priority"]

        owner = request.form["owner"]

        status = request.form["status"]

        resolution = request.form["resolution"]

        conn.execute("""
        INSERT INTO issues (
            user_id,
            project_id,
            title,
            description,
            priority,
            owner,
            status,
            resolution,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            project_id,
            title,
            description,
            priority,
            owner,
            status,
            resolution,
            str(date.today())
        ))

        conn.commit()

        conn.close()

        create_activity(
            f"{session['username']} added a new issue"
        )

        return redirect("/issues")

    conn.close()

    return render_template(
        "add_issue.html",
        projects=projects
    )

@app.route("/changes")
def changes():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    changes = conn.execute("""
    SELECT
        changes.*,
        projects.name AS project_name
    FROM changes
    LEFT JOIN projects
    ON changes.project_id = projects.id
    WHERE changes.user_id = ?
    ORDER BY
        CASE
            WHEN changes.approval_status = 'Pending' THEN 1
            WHEN changes.approval_status = 'Approved' THEN 2
            WHEN changes.approval_status = 'Rejected' THEN 3
            ELSE 4
        END,
        changes.created_at DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    return render_template(
        "changes.html",
        changes=changes
    )

@app.route("/add-change", methods=["GET", "POST"])
def add_change():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        project_id = request.form["project_id"]

        title = request.form["title"]

        description = request.form["description"]

        impact = request.form["impact"]

        requested_by = request.form["requested_by"]

        approval_status = request.form["approval_status"]

        implementation_plan = request.form["implementation_plan"]

        conn.execute("""
        INSERT INTO changes (
            user_id,
            project_id,
            title,
            description,
            impact,
            requested_by,
            approval_status,
            implementation_plan,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            project_id,
            title,
            description,
            impact,
            requested_by,
            approval_status,
            implementation_plan,
            str(date.today())
        ))

        conn.commit()

        conn.close()

        create_activity(
            f"{session['username']} submitted a change request"
        )

        return redirect("/changes")

    conn.close()

    return render_template(
        "add_change.html",
        projects=projects
    )

@app.route("/benefits")
def benefits():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    benefits = conn.execute("""
    SELECT
        benefits.*,
        projects.name AS project_name
    FROM benefits
    LEFT JOIN projects
    ON benefits.project_id = projects.id
    WHERE benefits.user_id = %s
    ORDER BY benefits.created_at DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    def clean_value(value):
        if not value:
            return 0

        value = str(value)
        value = value.replace("£", "")
        value = value.replace(",", "")
        value = value.strip()

        try:
            return float(value)
        except:
            return 0

    if benefits:
        top_benefit = max(
            benefits,
            key=lambda benefit: clean_value(benefit["expected_value"])
        )
    else:
        top_benefit = None

    return render_template(
        "benefits.html",
        benefits=benefits,
        top_benefit=top_benefit
    )

@app.route("/add-benefit", methods=["GET", "POST"])
def add_benefit():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        project_id = request.form["project_id"]
        title = request.form["title"]
        description = request.form["description"]
        expected_value = request.form["expected_value"]
        measurement_method = request.form["measurement_method"]
        owner = request.form["owner"]
        status = request.form["status"]
        target_date = request.form["target_date"]

        conn.execute("""
        INSERT INTO benefits (
            user_id,
            project_id,
            title,
            description,
            expected_value,
            measurement_method,
            owner,
            status,
            target_date,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            project_id,
            title,
            description,
            expected_value,
            measurement_method,
            owner,
            status,
            target_date,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} added a new benefit"
        )

        return redirect("/benefits")

    conn.close()

    return render_template(
        "add_benefit.html",
        projects=projects
    )

@app.route("/edit-risk/<int:risk_id>", methods=["GET", "POST"])
def edit_risk(risk_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    risk = conn.execute("""
    SELECT *
    FROM risks
    WHERE id = ?
    """, (
        risk_id,
    )).fetchone()

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        project_id = request.form["project_id"]

        title = request.form["title"]

        description = request.form["description"]

        probability = request.form["probability"]

        impact = request.form["impact"]

        mitigation = request.form["mitigation"]

        owner = request.form["owner"]

        status = request.form["status"]

        probability_map = {
            "Low": 1,
            "Medium": 2,
            "High": 3
        }

        impact_map = {
            "Low": 1,
            "Medium": 2,
            "High": 3
        }

        severity_score = (
            probability_map[probability]
            *
            impact_map[impact]
        )

        conn.execute("""
        UPDATE risks
        SET
            project_id = ?,
            title = ?,
            description = ?,
            probability = ?,
            impact = ?,
            severity_score = ?,
            mitigation = ?,
            owner = ?,
            status = ?
        WHERE id = ?
        """, (
            project_id,
            title,
            description,
            probability,
            impact,
            severity_score,
            mitigation,
            owner,
            status,
            risk_id
        ))

        conn.commit()

        conn.close()

        create_activity(
            f"{session['username']} updated a risk"
        )

        return redirect("/risks")

    conn.close()

    return render_template(
        "edit_risk.html",
        risk=risk,
        projects=projects
    )

@app.route("/delete-risk/<int:risk_id>")
def delete_risk(risk_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    conn.execute("""
    DELETE FROM risks
    WHERE id = ?
    """, (
        risk_id,
    ))

    conn.commit()

    conn.close()

    create_activity(
        f"{session['username']} deleted a risk"
    )

    return redirect("/risks")

@app.route("/edit-issue/<int:issue_id>", methods=["GET", "POST"])
def edit_issue(issue_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    issue = conn.execute("""
    SELECT *
    FROM issues
    WHERE id = ?
    AND user_id = ?
    """, (
        issue_id,
        session["user_id"]
    )).fetchone()

    if not issue:
        conn.close()
        return redirect("/issues")

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    ORDER BY name ASC
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        priority = request.form.get("priority", "Medium")
        owner = request.form.get("owner", "")
        status = request.form.get("status", "Open")
        resolution = request.form.get("resolution", "")

        conn.execute("""
        UPDATE issues
        SET
            project_id = ?,
            title = ?,
            description = ?,
            priority = ?,
            owner = ?,
            status = ?,
            resolution = ?
        WHERE id = ?
        AND user_id = ?
        """, (
            project_id,
            title,
            description,
            priority,
            owner,
            status,
            resolution,
            issue_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated an issue"
        )

        return redirect("/issues")

    conn.close()

    return render_template(
        "edit_issue.html",
        issue=issue,
        projects=projects
    )


@app.route("/delete-issue/<int:issue_id>")
def delete_issue(issue_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    issue = conn.execute("""
    SELECT *
    FROM issues
    WHERE id = ?
    AND user_id = ?
    """, (
        issue_id,
        session["user_id"]
    )).fetchone()

    if not issue:
        conn.close()
        return redirect("/issues")

    conn.execute("""
    DELETE FROM issues
    WHERE id = ?
    AND user_id = ?
    """, (
        issue_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} deleted an issue"
    )

    return redirect("/issues")

@app.route("/edit-change/<int:change_id>", methods=["GET", "POST"])
def edit_change(change_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    change = conn.execute("""
    SELECT *
    FROM changes
    WHERE id = ?
    AND user_id = ?
    """, (
        change_id,
        session["user_id"]
    )).fetchone()

    if not change:
        conn.close()
        return redirect("/changes")

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    ORDER BY name ASC
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        conn.execute("""
        UPDATE changes
        SET
            project_id = ?,
            title = ?,
            description = ?,
            impact = ?,
            requested_by = ?,
            approval_status = ?,
            implementation_plan = ?
        WHERE id = ?
        AND user_id = ?
        """, (
            request.form.get("project_id"),
            request.form.get("title", ""),
            request.form.get("description", ""),
            request.form.get("impact", "Medium"),
            request.form.get("requested_by", ""),
            request.form.get("approval_status", "Pending"),
            request.form.get("implementation_plan", ""),
            change_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated a change request"
        )

        return redirect("/changes")

    conn.close()

    return render_template(
        "edit_change.html",
        change=change,
        projects=projects
    )


@app.route("/delete-change/<int:change_id>")
def delete_change(change_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    conn.execute("""
    DELETE FROM changes
    WHERE id = ?
    AND user_id = ?
    """, (
        change_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} deleted a change request"
    )

    return redirect("/changes")

@app.route("/edit-benefit/<int:benefit_id>", methods=["GET", "POST"])
def edit_benefit(benefit_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    benefit = conn.execute("""
    SELECT *
    FROM benefits
    WHERE id = ?
    AND user_id = ?
    """, (
        benefit_id,
        session["user_id"]
    )).fetchone()

    if not benefit:
        conn.close()
        return redirect("/benefits")

    projects = conn.execute("""
    SELECT *
    FROM projects
    WHERE user_id = ?
    ORDER BY name ASC
    """, (
        session["user_id"],
    )).fetchall()

    if request.method == "POST":

        conn.execute("""
        UPDATE benefits
        SET
            project_id = ?,
            title = ?,
            description = ?,
            expected_value = ?,
            measurement_method = ?,
            owner = ?,
            status = ?,
            target_date = ?
        WHERE id = ?
        AND user_id = ?
        """, (
            request.form.get("project_id"),
            request.form.get("title", ""),
            request.form.get("description", ""),
            request.form.get("expected_value", ""),
            request.form.get("measurement_method", ""),
            request.form.get("owner", ""),
            request.form.get("status", "Planned"),
            request.form.get("target_date", ""),
            benefit_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated a benefit"
        )

        return redirect("/benefits")

    conn.close()

    return render_template(
        "edit_benefit.html",
        benefit=benefit,
        projects=projects
    )


@app.route("/delete-benefit/<int:benefit_id>")
def delete_benefit(benefit_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    conn.execute("""
    DELETE FROM benefits
    WHERE id = ?
    AND user_id = ?
    """, (
        benefit_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} deleted a benefit"
    )

    return redirect("/benefits")

@app.route("/team")
def team():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT *
    FROM team_members
    WHERE user_id = %s
    ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    members = cursor.fetchall()

    team_data = []

    for member in members:

        cursor.execute("""
        SELECT COUNT(DISTINCT tasks.id) AS total_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        LEFT JOIN task_team_members
        ON task_team_members.task_id = tasks.id
        WHERE projects.user_id = %s
        AND (
            tasks.assigned_to = %s
            OR task_team_members.team_member_id = %s
        )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        total_tasks = cursor.fetchone()["total_tasks"]

        cursor.execute("""
        SELECT COUNT(DISTINCT tasks.id) AS completed_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        LEFT JOIN task_team_members
        ON task_team_members.task_id = tasks.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Completed'
        AND (
            tasks.assigned_to = %s
            OR task_team_members.team_member_id = %s
        )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        completed_tasks = cursor.fetchone()["completed_tasks"]

        cursor.execute("""
        SELECT COUNT(DISTINCT tasks.id) AS active_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        LEFT JOIN task_team_members
        ON task_team_members.task_id = tasks.id
        WHERE projects.user_id = %s
        AND tasks.status != 'Completed'
        AND (
            tasks.assigned_to = %s
            OR task_team_members.team_member_id = %s
        )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        active_tasks = cursor.fetchone()["active_tasks"]

        cursor.execute("""
        SELECT COUNT(DISTINCT tasks.id) AS blocked_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        LEFT JOIN task_team_members
        ON task_team_members.task_id = tasks.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Blocked'
        AND (
            tasks.assigned_to = %s
            OR task_team_members.team_member_id = %s
        )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        blocked_tasks = cursor.fetchone()["blocked_tasks"]

        if total_tasks > 0:
            utilisation = round((active_tasks / total_tasks) * 100)
        else:
            utilisation = 0

        team_data.append({
            "member": member,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "active_tasks": active_tasks,
            "blocked_tasks": blocked_tasks,
            "utilisation": utilisation
        })

    conn.close()

    return render_template(
        "team.html",
        team_data=team_data
    )

@app.route("/add-team-member", methods=["GET", "POST"])
def add_team_member():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        conn = get_db_connection()

        conn.execute("""
        INSERT INTO team_members (
            user_id,
            name,
            role,
            email,
            phone,
            skills,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            request.form.get("name", ""),
            request.form.get("role", ""),
            request.form.get("email", ""),
            request.form.get("phone", ""),
            request.form.get("skills", ""),
            request.form.get("status", "Active"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} added a team member"
        )

        return redirect("/team")

    return render_template("add_team_member.html")

@app.route("/edit-team-member/<int:member_id>", methods=["GET", "POST"])
def edit_team_member(member_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    member = conn.execute("""
    SELECT *
    FROM team_members
    WHERE id = ?
    AND user_id = ?
    """, (
        member_id,
        session["user_id"]
    )).fetchone()

    if not member:
        conn.close()
        return redirect("/team")

    if request.method == "POST":

        conn.execute("""
        UPDATE team_members
        SET
            name = ?,
            role = ?,
            email = ?,
            phone = ?,
            skills = ?,
            status = ?
        WHERE id = ?
        AND user_id = ?
        """, (
            request.form.get("name", ""),
            request.form.get("role", ""),
            request.form.get("email", ""),
            request.form.get("phone", ""),
            request.form.get("skills", ""),
            request.form.get("status", "Active"),
            member_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated a team member"
        )

        return redirect("/team")

    conn.close()

    return render_template(
        "edit_team_member.html",
        member=member
    )


@app.route("/delete-team-member/<int:member_id>")
def delete_team_member(member_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    conn.execute("""
    DELETE FROM team_members
    WHERE id = ?
    AND user_id = ?
    """, (
        member_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} deleted a team member"
    )

    return redirect("/team")

@app.route("/raid")
def raid():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT *
    FROM risks
    WHERE user_id = %s
    ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    risks = cursor.fetchall()

    cursor.execute("""
    SELECT *
    FROM assumptions
    WHERE user_id = %s
    ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    assumptions = cursor.fetchall()

    cursor.execute("""
    SELECT *
    FROM issues
    WHERE user_id = %s
    ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    issues = cursor.fetchall()

    cursor.execute("""
    SELECT *
    FROM dependencies
    WHERE user_id = %s
    ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    dependencies = cursor.fetchall()

    conn.close()

    return render_template(
        "raid.html",
        risks=risks,
        assumptions=assumptions,
        issues=issues,
        dependencies=dependencies
    )

@app.route("/add-assumption", methods=["GET", "POST"])
def add_assumption():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT *
    FROM projects
    WHERE user_id = %s
    ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
        INSERT INTO assumptions (
            user_id,
            project_id,
            title,
            description,
            owner,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("description"),
            request.form.get("owner"),
            request.form.get("status"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/raid")

    conn.close()

    return render_template(
        "add_assumption.html",
        projects=projects
    )

@app.route("/add-dependency", methods=["GET", "POST"])
def add_dependency():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT *
    FROM projects
    WHERE user_id = %s
    ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
        INSERT INTO dependencies (
            user_id,
            project_id,
            title,
            description,
            owner,
            status,
            target_date,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("description"),
            request.form.get("owner"),
            request.form.get("status"),
            request.form.get("target_date"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/raid")

    conn.close()

    return render_template(
        "add_dependency.html",
        projects=projects
    )

@app.route("/team-utilisation")
def team_utilisation():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    members = cursor.fetchall()

    utilisation_data = []

    for member in members:

        cursor.execute("""
            SELECT COUNT(DISTINCT tasks.id) AS total_tasks
            FROM tasks
            JOIN projects
            ON tasks.project_id = projects.id
            LEFT JOIN task_team_members
            ON task_team_members.task_id = tasks.id
            WHERE projects.user_id = %s
            AND (
                tasks.assigned_to = %s
                OR task_team_members.team_member_id = %s
            )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        total_tasks = cursor.fetchone()["total_tasks"]

        utilisation = min(total_tasks * 10, 100)

        utilisation_data.append({
            "name": member["name"],
            "role": member["role"],
            "total_tasks": total_tasks,
            "utilisation": utilisation
        })

    if utilisation_data:

        average_utilisation = round(
            sum(item["utilisation"] for item in utilisation_data)
            / len(utilisation_data)
        )

        most_loaded = max(
            utilisation_data,
            key=lambda item: item["utilisation"]
        )

    else:

        average_utilisation = 0

        most_loaded = {
            "name": "N/A",
            "utilisation": 0
        }

    overloaded_count = len([
        item for item in utilisation_data
        if item["utilisation"] >= 80
    ])

    balanced_count = len([
        item for item in utilisation_data
        if 40 <= item["utilisation"] < 80
    ])

    available_count = len([
        item for item in utilisation_data
        if item["utilisation"] < 40
    ])

    average_capacity = 100 - average_utilisation

    smart_insights = []

    if overloaded_count > 0:
        smart_insights.append(
            f"Attention required: {overloaded_count} resource(s) are overloaded and may require workload redistribution."
        )

    if balanced_count > 0:
        smart_insights.append(
            "Team workload is currently well balanced."
        )

    if available_count > 0:
        smart_insights.append(
            f"{available_count} team member(s) have spare delivery capacity available."
        )

    smart_insights.append(
        f"Average team utilisation is currently {average_utilisation}%."
    )

    if average_capacity > 50:

        smart_insights.append(
            "The team currently has significant capacity available for additional project work."
        )

    elif average_capacity > 25:

        smart_insights.append(
            "The team has moderate spare capacity available for upcoming project demand."
        )

    else:

        smart_insights.append(
            "The team is approaching full utilisation and resource planning should be reviewed."
        )

    if average_utilisation < 40:

        smart_insights.append(
            "Opportunity: Additional projects can be onboarded without increasing headcount."
        )

    elif average_utilisation >= 80:

        smart_insights.append(
            "Risk: Current utilisation levels may impact delivery performance and team wellbeing."
        )



    conn.close()

    return render_template(
        "team_utilisation.html",
        utilisation_data=utilisation_data,
        average_utilisation=average_utilisation,
        average_capacity=average_capacity,
        overloaded_count=overloaded_count,
        balanced_count=balanced_count,
        available_count=available_count,
        most_loaded=most_loaded,
        smart_insights=smart_insights
    )

@app.route("/stakeholders")
def stakeholders():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    stakeholders = conn.execute("""
    SELECT
        stakeholders.*,
        projects.name AS project_name
    FROM stakeholders
    LEFT JOIN projects
    ON stakeholders.project_id = projects.id
    WHERE stakeholders.user_id = %s
    ORDER BY stakeholders.created_at DESC
    """, (
        session["user_id"],
    )).fetchall()

    conn.close()

    return render_template(
        "stakeholders.html",
        stakeholders=stakeholders
    )

@app.route("/add-stakeholder", methods=["GET", "POST"])
def add_stakeholder():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
    SELECT *
    FROM projects
    WHERE user_id = %s
    ORDER BY name ASC
    """, (session["user_id"],))

    projects = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
        INSERT INTO stakeholders (
            user_id,
            project_id,
            name,
            role,
            influence,
            interest,
            communication_plan,
            owner,
            status,
            created_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("name"),
            request.form.get("role"),
            request.form.get("influence"),
            request.form.get("interest"),
            request.form.get("communication_plan"),
            request.form.get("owner"),
            request.form.get("status"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/stakeholders")

    conn.close()

    return render_template(
        "add_stakeholder.html",
        projects=projects
    )

@app.route("/decisions")
def decisions():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT
        decisions.*,
        projects.name AS project_name
    FROM decisions
    LEFT JOIN projects
    ON decisions.project_id = projects.id
    WHERE decisions.user_id = %s
    ORDER BY decisions.decision_date DESC
    """, (
        session["user_id"],
    ))

    decisions = cursor.fetchall()

    conn.close()

    return render_template(
        "decisions.html",
        decisions=decisions
    )

@app.route("/add-decision", methods=["GET", "POST"])
def add_decision():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT *
    FROM projects
    WHERE user_id = %s
    ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
        INSERT INTO decisions (
            user_id,
            project_id,
            title,
            decision_maker,
            impact,
            reason,
            status,
            decision_date,
            created_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("decision_maker"),
            request.form.get("impact"),
            request.form.get("reason"),
            request.form.get("status"),
            request.form.get("decision_date"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/decisions")

    conn.close()

    return render_template(
        "add_decision.html",
        projects=projects
    )

@app.route("/actions")
def actions():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT
        actions.*,
        projects.name AS project_name
    FROM actions
    LEFT JOIN projects
    ON actions.project_id = projects.id
    WHERE actions.user_id = %s
    ORDER BY
        CASE
            WHEN actions.status = 'Completed' THEN 4
            WHEN actions.status = 'Blocked' THEN 1
            WHEN actions.priority = 'High' THEN 2
            WHEN actions.status = 'In Progress' THEN 3
            ELSE 5
        END,
        actions.due_date ASC
    """, (
        session["user_id"],
    ))

    actions = cursor.fetchall()

    conn.close()

    return render_template(
        "actions.html",
        actions=actions
    )

@app.route("/add-action", methods=["GET", "POST"])
def add_action():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT *
    FROM projects
    WHERE user_id = %s
    ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
        INSERT INTO actions (
            user_id,
            project_id,
            title,
            description,
            owner,
            priority,
            status,
            due_date,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("description"),
            request.form.get("owner"),
            request.form.get("priority"),
            request.form.get("status"),
            request.form.get("due_date"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/actions")

    conn.close()

    return render_template(
        "add_action.html",
        projects=projects
    )

@app.route("/lessons")
def lessons():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT
        lessons.*,
        projects.name AS project_name
    FROM lessons
    LEFT JOIN projects
    ON lessons.project_id = projects.id
    WHERE lessons.user_id = %s
    ORDER BY lessons.created_at DESC
    """, (
        session["user_id"],
    ))

    lessons = cursor.fetchall()

    conn.close()

    return render_template(
        "lessons.html",
        lessons=lessons
    )

@app.route("/add-lesson", methods=["GET", "POST"])
def add_lesson():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
    SELECT *
    FROM projects
    WHERE user_id = %s
    ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
        INSERT INTO lessons (
            user_id,
            project_id,
            title,
            what_happened,
            what_went_well,
            what_went_wrong,
            recommendation,
            owner,
            status,
            created_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("what_happened"),
            request.form.get("what_went_well"),
            request.form.get("what_went_wrong"),
            request.form.get("recommendation"),
            request.form.get("owner"),
            request.form.get("status"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/lessons")

    conn.close()

    return render_template(
        "add_lesson.html",
        projects=projects
    )

@app.route("/budgets")
def budgets():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            budgets.*,
            projects.name AS project_name
        FROM budgets
        LEFT JOIN projects
        ON budgets.project_id = projects.id
        WHERE budgets.user_id = %s
        ORDER BY budgets.id DESC
    """, (
        session["user_id"],
    ))

    budgets = cursor.fetchall()

    total_budget = 0
    total_actual_cost = 0
    total_forecast_cost = 0
    over_budget_count = 0

    for budget in budgets:

        budget_amount = float(budget["budget_amount"] or 0)
        actual_cost = float(budget["actual_cost"] or 0)
        forecast_cost = float(budget["forecast_cost"] or 0)

        total_budget += budget_amount
        total_actual_cost += actual_cost
        total_forecast_cost += forecast_cost

        if actual_cost > budget_amount:
            over_budget_count += 1

    remaining_budget = total_budget - total_actual_cost

    if total_budget > 0:
        budget_usage = round((total_actual_cost / total_budget) * 100)
    else:
        budget_usage = 0

    if budget_usage <= 70:
        financial_health = "Green"
        financial_health_message = "Financial position is healthy."

    elif budget_usage <= 90:
        financial_health = "Amber"
        financial_health_message = "Budget usage requires monitoring."

    else:
        financial_health = "Red"
        financial_health_message = "Budget usage is high and requires attention."

    forecast_variance = total_budget - total_forecast_cost

    if total_budget > 0:
        forecast_usage = round((total_forecast_cost / total_budget) * 100)
    else:
        forecast_usage = 0

    if over_budget_count > 0:
        financial_risk_level = "High"
        financial_recommendation = "Review overspending and reduce non-critical project costs."
    elif budget_usage >= 80:
        financial_risk_level = "Medium"
        financial_recommendation = "Monitor project spend closely as budget usage is increasing."
    else:
        financial_risk_level = "Low"
        financial_recommendation = "Financial position is currently stable."

    conn.close()

    return render_template(
        "budgets.html",
        budgets=budgets,
        total_budget=total_budget,
        total_actual_cost=total_actual_cost,
        total_forecast_cost=total_forecast_cost,
        remaining_budget=remaining_budget,
        budget_usage=budget_usage,
        over_budget_count=over_budget_count,
        financial_health=financial_health,
        financial_health_message=financial_health_message,
        forecast_variance=forecast_variance,
        forecast_usage=forecast_usage,
        financial_risk_level=financial_risk_level,
        financial_recommendation=financial_recommendation
    )

@app.route("/add-budget", methods=["GET", "POST"])
def add_budget():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO budgets
            (
                user_id,
                project_id,
                budget_amount,
                actual_cost,
                forecast_cost,
                approved_by,
                status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form["project_id"],
            request.form["budget_amount"],
            request.form["actual_cost"],
            request.form["forecast_cost"],
            request.form["approved_by"],
            request.form["status"],
            str(date.today())
        ))

        conn.commit()

        conn.close()

        return redirect("/budgets")

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    conn.close()

    return render_template(
        "add_budget.html",
        projects=projects
    )

@app.route("/project-health")
def project_health():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    project_scores = []

    for project in projects:

        project_id = project["id"]

        # Tasks

        cursor.execute("""
            SELECT COUNT(*) AS total_tasks
            FROM tasks
            WHERE project_id = %s
        """, (project_id,))

        total_tasks = cursor.fetchone()["total_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS completed_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Completed'
        """, (project_id,))

        completed_tasks = cursor.fetchone()["completed_tasks"]

        # Risks

        cursor.execute("""
            SELECT COUNT(*) AS risk_count
            FROM risks
            WHERE project_id = %s
        """, (project_id,))

        risk_count = cursor.fetchone()["risk_count"]

        # Budget

        cursor.execute("""
            SELECT *
            FROM budgets
            WHERE project_id = %s
            LIMIT 1
        """, (project_id,))

        budget = cursor.fetchone()

        schedule_score = 100

        if total_tasks > 0:
            schedule_score = round(
                (completed_tasks / total_tasks) * 100
            )

        risk_score = max(
            100 - (risk_count * 10),
            0
        )

        budget_score = 100

        if budget:

            budget_amount = float(
                budget["budget_amount"] or 0
            )

            actual_cost = float(
                budget["actual_cost"] or 0
            )

            if budget_amount > 0:

                budget_score = max(
                    100 - round(
                        (actual_cost / budget_amount) * 100
                    ),
                    0
                )

        overall_health = round(
            (
                schedule_score +
                risk_score +
                budget_score
            ) / 3
        )

        if overall_health >= 75:
            status = "Green"

        elif overall_health >= 50:
            status = "Amber"

        else:
            status = "Red"

        project_scores.append({

            "project_name": project["name"],

            "schedule_score": schedule_score,

            "risk_score": risk_score,

            "budget_score": budget_score,

            "overall_health": overall_health,

            "status": status

        })

        total_projects = len(project_scores)

        healthy_projects = len([
            project for project in project_scores
            if project["status"] == "Green"
        ])

        monitor_projects = len([
            project for project in project_scores
            if project["status"] == "Amber"
        ])

        at_risk_projects = len([
            project for project in project_scores
            if project["status"] == "Red"
        ])

        if total_projects > 0:

            average_health_score = round(
                sum(
                    project["overall_health"]
                    for project in project_scores
                ) / total_projects
            )

        else:

            average_health_score = 0

        conn.close()

        return render_template(
            "project_health.html",
            project_scores=project_scores,
            total_projects=total_projects,
            healthy_projects=healthy_projects,
            monitor_projects=monitor_projects,
            at_risk_projects=at_risk_projects,
            average_health_score=average_health_score
        )

@app.route("/executive-dashboard")
def executive_dashboard():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT COUNT(*) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (session["user_id"],))
    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS total_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
    """, (session["user_id"],))
    total_tasks = cursor.fetchone()["total_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS completed_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Completed'
    """, (session["user_id"],))
    completed_tasks = cursor.fetchone()["completed_tasks"]

    if total_tasks > 0:
        portfolio_health = round((completed_tasks / total_tasks) * 100)
    else:
        portfolio_health = 0

    cursor.execute("""
        SELECT COUNT(*) AS total_risks
        FROM risks
        WHERE user_id = %s
    """, (session["user_id"],))
    total_risks = cursor.fetchone()["total_risks"]

    cursor.execute("""
                   SELECT COUNT(*) AS total_issues
                   FROM issues
                   WHERE user_id = %s
                   """, (session["user_id"],))

    total_issues = cursor.fetchone()["total_issues"]

    cursor.execute("""
        SELECT COUNT(*) AS high_risks
        FROM risks
        WHERE user_id = %s
        AND severity_score >= 6
    """, (session["user_id"],))
    high_risks = cursor.fetchone()["high_risks"]

    risk_health = max(100 - (high_risks * 20), 0)

    cursor.execute("""
        SELECT COUNT(*) AS total_benefits
        FROM benefits
        WHERE user_id = %s
    """, (session["user_id"],))
    total_benefits = cursor.fetchone()["total_benefits"]

    cursor.execute("""
        SELECT COUNT(*) AS realised_benefits
        FROM benefits
        WHERE user_id = %s
        AND status = 'Realised'
    """, (session["user_id"],))
    realised_benefits = cursor.fetchone()["realised_benefits"]

    if total_benefits > 0:
        benefits_health = round((realised_benefits / total_benefits) * 100)
    else:
        benefits_health = 0

    cursor.execute("""
        SELECT
            SUM(budget_amount) AS total_budget,
            SUM(actual_cost) AS total_actual
        FROM budgets
        WHERE user_id = %s
    """, (session["user_id"],))
    budget_data = cursor.fetchone()

    total_budget = float(budget_data["total_budget"] or 0)
    total_actual = float(budget_data["total_actual"] or 0)

    if total_budget > 0:
        financial_health = max(100 - round((total_actual / total_budget) * 100), 0)
    else:
        financial_health = 0

    cursor.execute("""
        SELECT COUNT(*) AS total_team_members
        FROM team_members
        WHERE user_id = %s
    """, (session["user_id"],))
    total_team_members = cursor.fetchone()["total_team_members"]

    resource_health = 100

    if total_team_members == 0:
        resource_health = 0

    overall_executive_health = round(
        (
            portfolio_health +
            financial_health +
            resource_health +
            risk_health +
            benefits_health
        ) / 5
    )

    if overall_executive_health >= 75:
        executive_status = "Green"
    elif overall_executive_health >= 50:
        executive_status = "Amber"
    else:
        executive_status = "Red"

    cursor.execute("""
                   SELECT COUNT(*) AS total_assumptions
                   FROM assumptions
                   WHERE user_id = %s
                   """, (session["user_id"],))
    total_assumptions = cursor.fetchone()["total_assumptions"]

    cursor.execute("""
                   SELECT COUNT(*) AS total_dependencies
                   FROM dependencies
                   WHERE user_id = %s
                   """, (session["user_id"],))
    total_dependencies = cursor.fetchone()["total_dependencies"]

    raid_total = (
            total_risks +
            total_assumptions +
            total_issues +
            total_dependencies
    )

    if raid_total <= 5:
        raid_health = "Green"
    elif raid_total <= 12:
        raid_health = "Amber"
    else:
        raid_health = "Red"

    cursor.execute("""
                   SELECT COUNT(*) AS healthy_projects
                   FROM projects
                   WHERE user_id = %s
                     AND status = 'Completed'
                   """, (session["user_id"],))

    healthy_projects = cursor.fetchone()["healthy_projects"]

    cursor.execute("""
                   SELECT COUNT(*) AS active_projects
                   FROM projects
                   WHERE user_id = %s
                     AND status = 'In Progress'
                   """, (session["user_id"],))

    active_projects = cursor.fetchone()["active_projects"]

    conn.close()

    return render_template(
        "executive_dashboard.html",
        total_projects=total_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        total_risks=total_risks,
        total_issues=total_issues,
        high_risks=high_risks,
        total_benefits=total_benefits,
        realised_benefits=realised_benefits,
        portfolio_health=portfolio_health,
        financial_health=financial_health,
        resource_health=resource_health,
        risk_health=risk_health,
        benefits_health=benefits_health,
        total_assumptions=total_assumptions,
        total_dependencies=total_dependencies,
        raid_total=raid_total,
        raid_health=raid_health,
        healthy_projects=healthy_projects,
        active_projects=active_projects,
        overall_executive_health=overall_executive_health,
        executive_status=executive_status
    )

@app.route("/resource-heatmap")
def resource_heatmap():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    members = cursor.fetchall()

    heatmap_data = []

    for member in members:

        cursor.execute("""
            SELECT COUNT(DISTINCT tasks.id) AS total_tasks
            FROM tasks
            JOIN projects
            ON tasks.project_id = projects.id
            LEFT JOIN task_team_members
            ON task_team_members.task_id = tasks.id
            WHERE projects.user_id = %s
            AND (
                tasks.assigned_to = %s
                OR task_team_members.team_member_id = %s
            )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        total_tasks = cursor.fetchone()["total_tasks"]

        utilisation = min(total_tasks * 10, 100)

        if utilisation >= 80:

            status = "Overloaded"
            colour = "red"

        elif utilisation >= 50:

            status = "Busy"
            colour = "amber"

        else:

            status = "Available"
            colour = "green"

        heatmap_data.append({

            "name": member["name"],
            "role": member["role"],
            "total_tasks": total_tasks,
            "utilisation": utilisation,
            "status": status,
            "colour": colour

        })

    overloaded_count = len([
        item for item in heatmap_data
        if item["status"] == "Overloaded"
    ])

    busy_count = len([
        item for item in heatmap_data
        if item["status"] == "Busy"
    ])

    available_count = len([
        item for item in heatmap_data
        if item["status"] == "Available"
    ])

    conn.close()

    return render_template(
        "resource_heatmap.html",
        heatmap_data=heatmap_data,
        overloaded_count=overloaded_count,
        busy_count=busy_count,
        available_count=available_count
    )

@app.route("/capacity-forecast")
def capacity_forecast():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    members = cursor.fetchall()

    forecast_data = []

    for member in members:

        cursor.execute("""
            SELECT COUNT(DISTINCT tasks.id) AS total_tasks
            FROM tasks
            JOIN projects
            ON tasks.project_id = projects.id
            LEFT JOIN task_team_members
            ON task_team_members.task_id = tasks.id
            WHERE projects.user_id = %s
            AND (
                tasks.assigned_to = %s
                OR task_team_members.team_member_id = %s
            )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        total_tasks = cursor.fetchone()["total_tasks"]

        current_utilisation = min(total_tasks * 10, 100)

        forecasted_utilisation = min(current_utilisation + 15, 100)

        available_capacity = 100 - current_utilisation

        if forecasted_utilisation >= 80:
            forecast_risk = "High"
        elif forecasted_utilisation >= 50:
            forecast_risk = "Medium"
        else:
            forecast_risk = "Low"

        forecast_data.append({
            "name": member["name"],
            "role": member["role"],
            "total_tasks": total_tasks,
            "current_utilisation": current_utilisation,
            "forecasted_utilisation": forecasted_utilisation,
            "available_capacity": available_capacity,
            "forecast_risk": forecast_risk
        })

    conn.close()

    return render_template(
        "capacity_forecast.html",
        forecast_data=forecast_data
    )

@app.route("/skills-matrix")
def skills_matrix():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    team_members = cursor.fetchall()

    conn.close()

    return render_template(
        "skills_matrix.html",
        team_members=team_members
    )

@app.route("/stage-gates")
def stage_gates():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            stage_gates.*,
            projects.name AS project_name
        FROM stage_gates
        LEFT JOIN projects
        ON stage_gates.project_id = projects.id
        WHERE stage_gates.user_id = %s
        ORDER BY stage_gates.created_at DESC
    """, (
        session["user_id"],
    ))

    stage_gates = cursor.fetchall()

    conn.close()

    return render_template(
        "stage_gates.html",
        stage_gates=stage_gates
    )

@app.route("/add-stage-gate", methods=["GET", "POST"])
def add_stage_gate():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO stage_gates
            (
                user_id,
                project_id,
                stage_name,
                status,
                reviewer,
                comments,
                review_date,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form["project_id"],
            request.form["stage_name"],
            request.form["status"],
            request.form["reviewer"],
            request.form["comments"],
            request.form["review_date"],
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/stage-gates")

    conn.close()

    return render_template(
        "add_stage_gate.html",
        projects=projects
    )

@app.route("/edit-stage-gate/<int:gate_id>", methods=["GET", "POST"])
def edit_stage_gate(gate_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM stage_gates
        WHERE id = %s
        AND user_id = %s
    """, (
        gate_id,
        session["user_id"]
    ))

    gate = cursor.fetchone()

    if request.method == "POST":

        cursor.execute("""
            UPDATE stage_gates
            SET
                stage_name = %s,
                status = %s,
                reviewer = %s,
                comments = %s,
                review_date = %s
            WHERE id = %s
        """, (
            request.form.get("stage_name"),
            request.form.get("status"),
            request.form.get("reviewer"),
            request.form.get("comments"),
            request.form.get("review_date"),
            gate_id
        ))

        conn.commit()
        conn.close()

        return redirect("/stage-gates")

    conn.close()

    return render_template(
        "edit_stage_gate.html",
        gate=gate
    )

@app.route("/delete-stage-gate/<int:gate_id>")
def delete_stage_gate(gate_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        DELETE FROM stage_gates
        WHERE id = %s
        AND user_id = %s
    """, (
        gate_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/stage-gates")

@app.route("/approvals")
def approvals():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            approvals.*,
            projects.name AS project_name
        FROM approvals
        LEFT JOIN projects
        ON approvals.project_id = projects.id
        WHERE approvals.user_id = %s
        ORDER BY approvals.id DESC
    """, (
        session["user_id"],
    ))

    approvals = cursor.fetchall()

    conn.close()

    return render_template(
        "approvals.html",
        approvals=approvals
    )


@app.route("/add-approval", methods=["GET", "POST"])
def add_approval():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO approvals
            (
                user_id,
                project_id,
                item_type,
                item_id,
                submitted_by,
                approver,
                status,
                submitted_date,
                comments
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE,%s)
        """, (
            session["user_id"],
            request.form["project_id"],
            request.form["item_type"],
            request.form["item_id"],
            request.form["submitted_by"],
            request.form["approver"],
            request.form["status"],
            request.form["comments"]
        ))

        conn.commit()
        conn.close()

        return redirect("/approvals")

    conn.close()

    return render_template(
        "add_approval.html",
        projects=projects
    )


@app.route("/edit-approval/<int:id>", methods=["GET", "POST"])
def edit_approval(id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM approvals
        WHERE id = %s
        AND user_id = %s
    """, (
        id,
        session["user_id"]
    ))

    approval = cursor.fetchone()

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            UPDATE approvals
            SET
                project_id = %s,
                item_type = %s,
                item_id = %s,
                submitted_by = %s,
                approver = %s,
                status = %s,
                comments = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form["project_id"],
            request.form["item_type"],
            request.form["item_id"],
            request.form["submitted_by"],
            request.form["approver"],
            request.form["status"],
            request.form["comments"],
            id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        return redirect("/approvals")

    conn.close()

    return render_template(
        "edit_approval.html",
        approval=approval,
        projects=projects
    )


@app.route("/approve-approval/<int:id>")
def approve_approval(id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        UPDATE approvals
        SET status = 'Approved',
            decision_date = CURRENT_DATE
        WHERE id = %s
        AND user_id = %s
    """, (
        id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/approvals")


@app.route("/reject-approval/<int:id>")
def reject_approval(id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        UPDATE approvals
        SET status = 'Rejected',
            decision_date = CURRENT_DATE
        WHERE id = %s
        AND user_id = %s
    """, (
        id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/approvals")


@app.route("/delete-approval/<int:id>")
def delete_approval(id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        DELETE FROM approvals
        WHERE id = %s
        AND user_id = %s
    """, (
        id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/approvals")

@app.route("/governance-reviews")
def governance_reviews():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            governance_reviews.*,
            projects.name AS project_name
        FROM governance_reviews
        LEFT JOIN projects
        ON governance_reviews.project_id = projects.id
        WHERE governance_reviews.user_id = %s
        ORDER BY governance_reviews.created_at DESC
    """, (
        session["user_id"],
    ))

    reviews = cursor.fetchall()

    conn.close()

    return render_template(
        "governance_reviews.html",
        reviews=reviews
    )


@app.route("/add-governance-review", methods=["GET", "POST"])
def add_governance_review():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO governance_reviews
            (
                user_id,
                project_id,
                review_name,
                review_type,
                review_date,
                outcome,
                decision,
                actions,
                owner,
                next_review_date,
                status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form["project_id"],
            request.form["review_name"],
            request.form["review_type"],
            request.form["review_date"],
            request.form["outcome"],
            request.form["decision"],
            request.form["actions"],
            request.form["owner"],
            request.form["next_review_date"],
            request.form["status"],
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/governance-reviews")

    conn.close()

    return render_template(
        "add_governance_review.html",
        projects=projects
    )

@app.route("/project-prioritisation")
def project_prioritisation():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            project_prioritisation.*,
            projects.name AS project_name
        FROM project_prioritisation
        LEFT JOIN projects
        ON project_prioritisation.project_id = projects.id
        WHERE project_prioritisation.user_id = %s
        ORDER BY project_prioritisation.priority_score DESC
    """, (
        session["user_id"],
    ))

    priorities = cursor.fetchall()

    conn.close()

    return render_template(
        "project_prioritisation.html",
        priorities=priorities
    )


@app.route("/add-project-prioritisation", methods=["GET", "POST"])
def add_project_prioritisation():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        business_value_score = int(request.form["business_value_score"])
        strategic_alignment_score = int(request.form["strategic_alignment_score"])
        risk_score = int(request.form["risk_score"])
        cost_score = int(request.form["cost_score"])

        priority_score = (
            business_value_score
            + strategic_alignment_score
            + risk_score
            + cost_score
        )

        cursor.execute("""
            INSERT INTO project_prioritisation
            (
                user_id,
                project_id,
                business_value_score,
                strategic_alignment_score,
                risk_score,
                cost_score,
                priority_score,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form["project_id"],
            business_value_score,
            strategic_alignment_score,
            risk_score,
            cost_score,
            priority_score,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/project-prioritisation")

    conn.close()

    return render_template(
        "add_project_prioritisation.html",
        projects=projects
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )