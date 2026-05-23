

DROP TABLE IF EXISTS risks;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS projects;

CREATE TABLE projects (
                          id INTEGER PRIMARY KEY,
                          name TEXT NOT NULL,
                          description TEXT,
                          status TEXT,
                          start_date DATE,
                          end_date DATE
);

CREATE TABLE tasks (
                       id INTEGER PRIMARY KEY,
                       project_id INTEGER,
                       title TEXT NOT NULL,
                       priority TEXT,
                       status TEXT,
                       due_date DATE,
                       FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE risks (
                       id INTEGER PRIMARY KEY,
                       project_id INTEGER,
                       risk_title TEXT,
                       impact TEXT,
                       mitigation TEXT,
                       FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);

ALTER TABLE projects
ADD COLUMN user_id INTEGER;
