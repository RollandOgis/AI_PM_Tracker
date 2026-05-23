from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session
)

import sqlite3

from datetime import date

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from functools import wraps


app = Flask(__name__)

app.secret_key = "supersecretkey"


def login_required(route_function):

    @wraps(route_function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect("/login")

        return route_function(*args, **kwargs)

    return wrapper


@app.route("/")
@login_required
def home():

    conn = sqlite3.connect("ai_pm_tracker.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id,
           name,
           status,
           start_date,
           end_date
    FROM projects
    WHERE user_id = ?
    """, (session["user_id"],))

    projects = cursor.fetchall()

    cursor.execute("""
    SELECT COUNT(*)
    FROM projects
    WHERE user_id = ?
    """, (session["user_id"],))

    total_projects = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.user_id = ?
    """, (session["user_id"],))

    total_tasks = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE tasks.status = 'Completed'
    AND projects.user_id = ?
    """, (session["user_id"],))

    completed_tasks = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE tasks.status = 'In Progress'
    AND projects.user_id = ?
    """, (session["user_id"],))

    in_progress_tasks = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE tasks.status = 'Pending'
    AND projects.user_id = ?
    """, (session["user_id"],))

    pending_tasks = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE tasks.status = 'Blocked'
    AND projects.user_id = ?
    """, (session["user_id"],))

    blocked_tasks = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE tasks.priority = 'High'
    AND projects.user_id = ?
    """, (session["user_id"],))

    high_priority_tasks = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE tasks.priority = 'Medium'
    AND projects.user_id = ?
    """, (session["user_id"],))

    medium_priority_tasks = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE tasks.priority = 'Low'
    AND projects.user_id = ?
    """, (session["user_id"],))

    low_priority_tasks = cursor.fetchone()[0]

    all_projects = []

    for project in projects:

        cursor.execute("""
        SELECT title,
               priority,
               status,
               due_date
        FROM tasks
        WHERE project_id = ?
        """, (project[0],))

        tasks = cursor.fetchall()

        cursor.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE project_id = ?
        """, (project[0],))

        total_project_tasks = cursor.fetchone()[0]

        cursor.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE project_id = ?
        AND status = 'Completed'
        """, (project[0],))

        completed_project_tasks = cursor.fetchone()[0]

        if total_project_tasks > 0:

            completion_percentage = round(
                (completed_project_tasks / total_project_tasks) * 100
            )

        else:

            completion_percentage = 0

        all_projects.append({
            "project": project,
            "tasks": tasks,
            "completion": completion_percentage
        })

    conn.close()

    return render_template(
        "index.html",
        projects=all_projects,
        total_projects=total_projects,
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
@login_required
def tasks():

    search = request.args.get("search", "")
    sort = request.args.get("sort", "")

    conn = sqlite3.connect("ai_pm_tracker.db")
    cursor = conn.cursor()

    base_query = """
    SELECT tasks.id,
           tasks.title,
           tasks.priority,
           tasks.status,
           tasks.due_date,
           projects.name
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
        base_query += " ORDER BY tasks.due_date ASC"

    elif sort == "priority":
        base_query += " ORDER BY tasks.priority ASC"

    elif sort == "status":
        base_query += " ORDER BY tasks.status ASC"

    cursor.execute(base_query, (
        session["user_id"],
        "%" + search + "%",
        "%" + search + "%",
        "%" + search + "%",
        "%" + search + "%"
    ))

    all_tasks = cursor.fetchall()

    conn.close()

    return render_template(
        "tasks.html",
        tasks=all_tasks,
        current_date=str(date.today()),
        search=search,
        sort=sort
    )


@app.route("/add-task", methods=["GET", "POST"])
@login_required
def add_task_page():

    conn = sqlite3.connect("ai_pm_tracker.db")
    cursor = conn.cursor()

    if request.method == "POST":

        project_id = request.form["project_id"]
        title = request.form["title"]
        priority = request.form["priority"]
        status = request.form["status"]
        due_date = request.form["due_date"]

        cursor.execute("""
        INSERT INTO tasks (
            project_id,
            title,
            priority,
            status,
            due_date
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            project_id,
            title,
            priority,
            status,
            due_date
        ))

        conn.commit()

    cursor.execute("""
    SELECT id, name
    FROM projects
    WHERE user_id = ?
    """, (session["user_id"],))

    projects = cursor.fetchall()

    conn.close()

    return render_template(
        "add_task.html",
        projects=projects
    )


@app.route("/delete-task/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):

    conn = sqlite3.connect("ai_pm_tracker.db")
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM tasks
    WHERE id = ?
    """, (task_id,))

    conn.commit()
    conn.close()

    return redirect("/tasks")


@app.route("/edit-task/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit_task(task_id):

    conn = sqlite3.connect("ai_pm_tracker.db")
    cursor = conn.cursor()

    if request.method == "POST":

        title = request.form["title"]
        priority = request.form["priority"]
        status = request.form["status"]
        due_date = request.form["due_date"]

        cursor.execute("""
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

    cursor.execute("""
    SELECT id,
           title,
           priority,
           status,
           due_date
    FROM tasks
    WHERE id = ?
    """, (task_id,))

    task = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_task.html",
        task=task
    )


@app.route("/add-project", methods=["GET", "POST"])
@login_required
def add_project_page():

    if request.method == "POST":

        name = request.form["name"]
        description = request.form["description"]
        status = request.form["status"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]

        conn = sqlite3.connect("ai_pm_tracker.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO projects (
            name,
            description,
            status,
            start_date,
            end_date,
            user_id
        )
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


@app.route("/project/<int:project_id>")
@login_required
def project_detail(project_id):

    conn = sqlite3.connect("ai_pm_tracker.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id,
           name,
           description,
           status,
           start_date,
           end_date
    FROM projects
    WHERE id = ?
    AND user_id = ?
    """, (
        project_id,
        session["user_id"]
    ))

    project = cursor.fetchone()

    cursor.execute("""
    SELECT title,
           priority,
           status,
           due_date
    FROM tasks
    WHERE project_id = ?
    """, (project_id,))

    tasks = cursor.fetchall()

    conn.close()

    return render_template(
        "project_detail.html",
        project=project,
        tasks=tasks,
        current_date=str(date.today())
    )


@app.route("/register", methods=["GET", "POST"])
def register():

    error = None

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("ai_pm_tracker.db")
        cursor = conn.cursor()

        try:
            cursor.execute("""
            INSERT INTO users (
                username,
                password
            )
            VALUES (?, ?)
            """, (
                username,
                hashed_password
            ))

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:

            conn.close()

            error = "Username already exists. Please choose another username."

    return render_template(
        "register.html",
        error=error
    )


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("ai_pm_tracker.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT id,
               username,
               password
        FROM users
        WHERE username = ?
        """, (username,))

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[2], password):

            session["user_id"] = user[0]
            session["username"] = user[1]

            return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)