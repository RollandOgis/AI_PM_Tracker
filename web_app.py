from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secretkey"

DATABASE = "ai_pm_tracker.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        status TEXT,
        start_date TEXT,
        end_date TEXT,
        user_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        title TEXT,
        priority TEXT,
        status TEXT,
        due_date TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    projects = conn.execute(
        "SELECT * FROM projects WHERE user_id = ?",
        (session["user_id"],)
    ).fetchall()

    all_projects = []

    total_tasks = 0
    completed_tasks = 0
    in_progress_tasks = 0
    pending_tasks = 0
    blocked_tasks = 0

    high_priority_tasks = 0
    medium_priority_tasks = 0
    low_priority_tasks = 0

    for project in projects:
        tasks = conn.execute(
            "SELECT * FROM tasks WHERE project_id = ?",
            (project["id"],)
        ).fetchall()

        task_list = []

        for task in tasks:
            total_tasks += 1

            if task["status"] == "Completed":
                completed_tasks += 1
            elif task["status"] == "In Progress":
                in_progress_tasks += 1
            elif task["status"] == "Pending":
                pending_tasks += 1
            elif task["status"] == "Blocked":
                blocked_tasks += 1

            if task["priority"] == "High":
                high_priority_tasks += 1
            elif task["priority"] == "Medium":
                medium_priority_tasks += 1
            elif task["priority"] == "Low":
                low_priority_tasks += 1

            task_list.append((
                task["title"],
                task["priority"],
                task["status"],
                task["due_date"]
            ))

        if len(tasks) > 0:
            completed_for_project = len(
                [task for task in tasks if task["status"] == "Completed"]
            )
            completion = round((completed_for_project / len(tasks)) * 100)
        else:
            completion = 0

        all_projects.append({
            "project": (
                project["id"],
                project["name"],
                project["status"],
                project["start_date"],
                project["end_date"]
            ),
            "tasks": task_list,
            "completion": completion
        })

    conn.close()

    return render_template(
        "index.html",
        projects=all_projects,
        total_projects=len(projects),
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        in_progress_tasks=in_progress_tasks,
        pending_tasks=pending_tasks,
        blocked_tasks=blocked_tasks,
        high_priority_tasks=high_priority_tasks,
        medium_priority_tasks=medium_priority_tasks,
        low_priority_tasks=low_priority_tasks,
        current_date=str(date.today())
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
        OR projects.name LIKE ?
    )
    """

    if sort == "due_date":
        query += " ORDER BY tasks.due_date ASC"
    elif sort == "priority":
        query += " ORDER BY tasks.priority ASC"
    elif sort == "status":
        query += " ORDER BY tasks.status ASC"

    task_rows = conn.execute(
        query,
        (
            session["user_id"],
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

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        status = request.form["status"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]

        conn = get_db_connection()

        conn.execute("""
        INSERT INTO projects
        (name, description, status, start_date, end_date, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name,
            description,
            status,
            start_date,
            end_date,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("add_project.html")


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

        conn.execute("""
        INSERT INTO tasks
        (project_id, title, priority, status, due_date)
        VALUES (?, ?, ?, ?, ?)
        """, (
            project_id,
            title,
            priority,
            status,
            due_date
        ))

        conn.commit()
        conn.close()

        return redirect("/tasks")

    conn.close()

    return render_template("add_task.html", projects=projects)


@app.route("/edit-task/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    if request.method == "POST":
        title = request.form["title"]
        priority = request.form["priority"]
        status = request.form["status"]
        due_date = request.form["due_date"]

        conn.execute("""
        UPDATE tasks
        SET title = ?,
            priority = ?,
            status = ?,
            due_date = ?
        WHERE id = ?
        """, (
            title,
            priority,
            status,
            due_date,
            task_id
        ))

        conn.commit()
        conn.close()

        return redirect("/tasks")

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()

    return render_template(
        "edit_task.html",
        task=(
            task["id"],
            task["title"],
            task["priority"],
            task["status"],
            task["due_date"]
        )
    )


@app.route("/delete-task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/tasks")


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()

        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:
            conn.close()
            error = "Username already exists. Please choose another username."

    return render_template("register.html", error=error)


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
                return redirect("/")

        return "Invalid username or password"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

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

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        status = request.form["status"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]

        conn.execute("""
        UPDATE projects
        SET name = ?,
            description = ?,
            status = ?,
            start_date = ?,
            end_date = ?
        WHERE id = ?
        AND user_id = ?
        """, (
            name,
            description,
            status,
            start_date,
            end_date,
            project_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        return redirect("/")

    conn.close()

    return render_template(
        "edit_project.html",
        project=project
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)