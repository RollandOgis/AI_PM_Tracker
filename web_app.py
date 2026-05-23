from flask import Flask, render_template, request, redirect, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secretkey"

DATABASE = "ai_pm_tracker.db"


# ---------------- DATABASE ---------------- #

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
        description TEXT,
        priority TEXT,
        status TEXT,
        due_date TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ---------------- HOME ---------------- #

@app.route("/")
def home():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    projects = conn.execute(
        "SELECT * FROM projects WHERE user_id = ?",
        (session["user_id"],)
    ).fetchall()

    tasks = conn.execute(
        "SELECT * FROM tasks"
    ).fetchall()

    total_projects = len(projects)
    total_tasks = len(tasks)

    completed_tasks = len(
        [task for task in tasks if task["status"] == "Completed"]
    )

    high_tasks = len(
        [task for task in tasks if task["priority"] == "High"]
    )

    medium_tasks = len(
        [task for task in tasks if task["priority"] == "Medium"]
    )

    low_tasks = len(
        [task for task in tasks if task["priority"] == "Low"]
    )

    in_progress_tasks = len(
        [task for task in tasks if task["status"] == "In Progress"]
    )

    conn.close()

    return render_template(
        "index.html",
        total_projects=total_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        high_tasks=high_tasks,
        medium_tasks=medium_tasks,
        low_tasks=low_tasks,
        in_progress_tasks=in_progress_tasks
    )


# ---------------- REGISTER ---------------- #

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()

        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )

            conn.commit()

        except:
            conn.close()
            return "User already exists"

        conn.close()

        return redirect("/login")

    return render_template("register.html")


# ---------------- LOGIN ---------------- #

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()

        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password)
        ).fetchone()

        conn.close()

        if user:
            session["user_id"] = user["id"]
            return redirect("/")

        return "Invalid username or password"

    return render_template("login.html")


# ---------------- LOGOUT ---------------- #

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ---------------- ADD PROJECT ---------------- #

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


# ---------------- TASKS ---------------- #

@app.route("/tasks")
def tasks():

    conn = get_db_connection()

    tasks = conn.execute("""
        SELECT tasks.*, projects.name AS project_name
        FROM tasks
        LEFT JOIN projects
        ON tasks.project_id = projects.id
    """).fetchall()

    conn.close()

    return render_template("tasks.html", tasks=tasks)


# ---------------- ADD TASK ---------------- #

@app.route("/add-task", methods=["GET", "POST"])
def add_task():

    conn = get_db_connection()

    projects = conn.execute(
        "SELECT * FROM projects"
    ).fetchall()

    if request.method == "POST":

        project_id = request.form["project_id"]
        title = request.form["title"]
        description = request.form["description"]
        priority = request.form["priority"]
        status = request.form["status"]
        due_date = request.form["due_date"]

        conn.execute("""
            INSERT INTO tasks
            (project_id, title, description, priority, status, due_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            project_id,
            title,
            description,
            priority,
            status,
            due_date
        ))

        conn.commit()
        conn.close()

        return redirect("/tasks")

    conn.close()

    return render_template(
        "add_task.html",
        projects=projects
    )


# ---------------- RUN ---------------- #

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )