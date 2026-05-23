import sqlite3

conn = sqlite3.connect("ai_pm_tracker.db")
cursor = conn.cursor()


def print_task(task):
    print(f"ID: {task[0]}")
    print(f"Project: {task[1]}")
    print(f"Title: {task[2]}")
    print(f"Priority: {task[3]}")
    print(f"Status: {task[4]}")
    print(f"Due Date: {task[5]}")
    print("-" * 30)


def show_projects():

    cursor.execute("SELECT id, name FROM projects")
    projects = cursor.fetchall()

    print("\nAvailable Projects:")

    for project in projects:
        print(project)


def get_tasks_by_project(project_id):

    cursor.execute("""
    SELECT tasks.id,
           projects.name,
           tasks.title,
           tasks.priority,
           tasks.status,
           tasks.due_date
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE projects.id = ?
    """, (project_id,))

    return cursor.fetchall()


def add_task():

    show_projects()

    project_id = input("Enter project ID from the list above: ")
    title = input("Enter task title: ")
    priority = input("Enter priority: ")
    status = input("Enter status: ")
    due_date = input("Enter due date: ")

    cursor.execute("""
    INSERT INTO tasks (project_id, title, priority, status, due_date)
    VALUES (?, ?, ?, ?, ?)
    """, (project_id, title, priority, status, due_date))

    conn.commit()

    print("Task added successfully.")


def update_task_status():

    task_id = input("Enter the task ID you want to update: ")
    new_status = input("Enter new status: ")

    cursor.execute("""
    UPDATE tasks
    SET status = ?
    WHERE id = ?
    """, (new_status, task_id))

    conn.commit()

    print("Task status updated successfully.")


def delete_task():

    task_id = input("Enter the task ID you want to delete: ")

    cursor.execute("""
    DELETE FROM tasks
    WHERE id = ?
    """, (task_id,))

    conn.commit()

    print("Task deleted successfully.")


def add_project():

    name = input("Enter project name: ")
    description = input("Enter project description: ")
    status = input("Enter project status: ")
    start_date = input("Enter start date: ")
    end_date = input("Enter end date: ")

    cursor.execute("""
    INSERT INTO projects (name, description, status, start_date, end_date)
    VALUES (?, ?, ?, ?, ?)
    """, (name, description, status, start_date, end_date))

    conn.commit()

    print("Project added successfully.")


def view_projects():

    cursor.execute("SELECT * FROM projects")

    projects = cursor.fetchall()

    print("\nProjects:")

    for project in projects:
        print(project)


def show_task_count():

    cursor.execute("""
    SELECT projects.name, COUNT(tasks.id) AS task_count
    FROM projects
    LEFT JOIN tasks ON tasks.project_id = projects.id
    GROUP BY projects.id, projects.name
    """)

    results = cursor.fetchall()

    print("\nTask Count Per Project:")

    for row in results:
        print(row)


def search_tasks():

    keyword = input("Enter keyword to search: ")

    cursor.execute("""
    SELECT tasks.id,
           projects.name,
           tasks.title,
           tasks.priority,
           tasks.status,
           tasks.due_date
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE tasks.title LIKE ?
    """, ("%" + keyword + "%",))

    results = cursor.fetchall()

    print("\nSearch Results:")

    for row in results:
        print_task(row)


def view_overdue_tasks():

    cursor.execute("""
    SELECT tasks.id,
           projects.name,
           tasks.title,
           tasks.priority,
           tasks.status,
           tasks.due_date
    FROM tasks
    JOIN projects
    ON tasks.project_id = projects.id
    WHERE tasks.due_date < DATE('now')
    AND tasks.status != 'Completed'
    """)

    results = cursor.fetchall()

    print("\nOverdue Tasks:")

    for row in results:
        print_task(row)


running = True

while running:

    print("\nAI PM Tracker")
    print("1. Add a new task")
    print("2. View tasks by project")
    print("3. Update task status")
    print("4. Delete a task")
    print("5. Add a new project")
    print("6. View all projects")
    print("7. Exit")
    print("8. Show task count per project")
    print("9. Search tasks")
    print("10. View overdue tasks")

    choice = input("Choose an option: ")

    if choice == "1":
        add_task()

    elif choice == "2":

        show_projects()

        project_id = input("Enter project ID to view tasks: ")

        tasks = get_tasks_by_project(project_id)

        print("\nProject Tasks:")

        for task in tasks:
            print_task(task)

    elif choice == "3":
        update_task_status()

    elif choice == "4":
        delete_task()

    elif choice == "5":
        add_project()

    elif choice == "6":
        view_projects()

    elif choice == "7":

        running = False
        print("Exiting AI PM Tracker...")

    elif choice == "8":
        show_task_count()

    elif choice == "9":
        search_tasks()

    elif choice == "10":
        view_overdue_tasks()

    else:
        print("Invalid option.")

conn.close()