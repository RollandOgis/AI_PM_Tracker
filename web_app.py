from flask import Flask, render_template, request, redirect, session, Response, jsonify, send_file, make_response

import csv
import os
import uuid
from io import StringIO, BytesIO
from datetime import date, datetime, timedelta

import psycopg2
import psycopg2.extras

from werkzeug.security import generate_password_hash, check_password_hash

from openai import OpenAI

from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

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



# =====================================

# BENEFITS HELPER

# =====================================

def clean_money_value(value):

    if not value:

        return 0

    value = str(value)

    value = value.replace("£", "")

    value = value.replace(",", "")

    value = value.strip()

    try:

        return float(value)

    except Exception:

        return 0


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

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS business_case TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS project_priority TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS risk_rating TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS governance_category TEXT
                   """)


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

    cursor.execute("""
                   ALTER TABLE tasks
                       ADD COLUMN IF NOT EXISTS attachment_name TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE tasks
                       ADD COLUMN IF NOT EXISTS attachment_url TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE tasks
                       ADD COLUMN IF NOT EXISTS acceptance_criteria TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE tasks
                       ADD COLUMN IF NOT EXISTS checklist TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE tasks
                       ADD COLUMN IF NOT EXISTS is_recurring BOOLEAN DEFAULT FALSE
                   """)

    cursor.execute("""
                   ALTER TABLE tasks
                       ADD COLUMN IF NOT EXISTS recurring_frequency TEXT
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS task_dependencies
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       task_id
                       INTEGER,
                       depends_on_task_id
                       INTEGER,
                       created_at
                       TEXT
                   )
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS task_comments
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       task_id
                       INTEGER,
                       user_id
                       INTEGER,
                       comment
                       TEXT,
                       created_at
                       TEXT
                   )
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS task_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       task_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       created_at
                       TEXT
                   )
                   """)


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

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS project_manager_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS sponsor_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS project_type TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS programme TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS portfolio TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE
                   """)

    try:
        cursor.execute("""
                       ALTER TABLE projects
                           ADD COLUMN client_id INTEGER
                       """)
    except Exception:
        pass


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

    cursor.execute("""
                   ALTER TABLE risks
                       ADD COLUMN IF NOT EXISTS category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE risks
                       ADD COLUMN IF NOT EXISTS risk_appetite TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE risks
                       ADD COLUMN IF NOT EXISTS residual_probability TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE risks
                       ADD COLUMN IF NOT EXISTS residual_impact TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE risks
                       ADD COLUMN IF NOT EXISTS residual_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE risks
                       ADD COLUMN IF NOT EXISTS target_probability TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE risks
                       ADD COLUMN IF NOT EXISTS target_impact TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE risks
                       ADD COLUMN IF NOT EXISTS target_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE risks
                       ADD COLUMN IF NOT EXISTS escalation_level TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE risks
                       ADD COLUMN IF NOT EXISTS escalation_required BOOLEAN DEFAULT FALSE
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS risk_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       risk_id
                       INTEGER,
                       user_id
                       INTEGER,
                       severity_score
                       INTEGER,
                       residual_score
                       INTEGER,
                       target_score
                       INTEGER,
                       status
                       TEXT,
                       action
                       TEXT,
                       created_at
                       TEXT
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

    cursor.execute("""
                   ALTER TABLE issues
                       ADD COLUMN IF NOT EXISTS issue_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE issues
                       ADD COLUMN IF NOT EXISTS sla_target_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE issues
                       ADD COLUMN IF NOT EXISTS escalation_status TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE issues
                       ADD COLUMN IF NOT EXISTS escalation_owner TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE issues
                       ADD COLUMN IF NOT EXISTS escalation_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE issues
                       ADD COLUMN IF NOT EXISTS root_cause TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE issues
                       ADD COLUMN IF NOT EXISTS closure_validation TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE issues
                       ADD COLUMN IF NOT EXISTS resolved_date TEXT
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS issue_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       issue_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       previous_status
                       TEXT,
                       new_status
                       TEXT,
                       created_at
                       TEXT
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

    cursor.execute("""
                   ALTER TABLE changes
                       ADD COLUMN IF NOT EXISTS cost_impact NUMERIC DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE changes
                       ADD COLUMN IF NOT EXISTS schedule_impact_days INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE changes
                       ADD COLUMN IF NOT EXISTS resource_impact TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE changes
                       ADD COLUMN IF NOT EXISTS benefit_impact TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE changes
                       ADD COLUMN IF NOT EXISTS cab_required TEXT DEFAULT 'No'
                   """)

    cursor.execute("""
                   ALTER TABLE changes
                       ADD COLUMN IF NOT EXISTS cab_decision TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE changes
                       ADD COLUMN IF NOT EXISTS implementation_status TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE changes
                       ADD COLUMN IF NOT EXISTS implementation_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE changes
                       ADD COLUMN IF NOT EXISTS rollback_plan TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE changes
                       ADD COLUMN IF NOT EXISTS linked_approval_id INTEGER
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS change_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       change_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       previous_status
                       TEXT,
                       new_status
                       TEXT,
                       created_at
                       TEXT
                   )
                   """)

    # BUSINESS CASES

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS business_cases
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       project_id
                       INTEGER,

                       programme_id
                       INTEGER,

                       title
                       TEXT,

                       strategic_objective
                       TEXT,

                       business_driver
                       TEXT,

                       problem_statement
                       TEXT,

                       proposed_solution
                       TEXT,

                       options_considered
                       TEXT,

                       preferred_option
                       TEXT,

                       expected_benefits
                       TEXT,

                       disbenefits
                       TEXT,

                       estimated_cost
                       NUMERIC,

                       expected_roi
                       NUMERIC,

                       payback_period
                       TEXT,

                       investment_category
                       TEXT,

                       sponsor
                       TEXT,

                       benefit_owner
                       TEXT,

                       approval_status
                       TEXT,

                       review_date
                       TEXT,

                       approval_date
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS project_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS programme_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS strategic_objective TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS business_driver TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS problem_statement TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS proposed_solution TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS options_considered TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS preferred_option TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS expected_benefits TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS disbenefits TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS estimated_cost NUMERIC
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS expected_roi NUMERIC
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS payback_period TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS investment_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS sponsor TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS benefit_owner TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS approval_status TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS review_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS approval_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE business_cases
                       ADD COLUMN IF NOT EXISTS status TEXT
                   """)

    # BUSINESS CASE BENEFITS

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS business_case_benefits
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       business_case_id
                       INTEGER,

                       benefit_name
                       TEXT,

                       benefit_type
                       TEXT,

                       owner
                       TEXT,

                       target_value
                       TEXT,

                       actual_value
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    # BUSINESS CASE APPROVALS

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS business_case_approvals
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       business_case_id
                       INTEGER,

                       approver
                       TEXT,

                       decision
                       TEXT,

                       comments
                       TEXT,

                       decision_date
                       TEXT

                   )
                   """)

    # BUSINESS CASE HISTORY

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS business_case_history
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       business_case_id
                       INTEGER,

                       user_id
                       INTEGER,

                       action
                       TEXT,

                       previous_status
                       TEXT,

                       new_status
                       TEXT,

                       created_at
                       TEXT

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

    cursor.execute("""
                   ALTER TABLE benefits
                       ADD COLUMN IF NOT EXISTS benefit_type TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE benefits
                       ADD COLUMN IF NOT EXISTS realised_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE benefits
                       ADD COLUMN IF NOT EXISTS benefit_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE benefits
                       ADD COLUMN IF NOT EXISTS actual_value NUMERIC DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE benefits
                       ADD COLUMN IF NOT EXISTS forecast_value NUMERIC DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE benefits
                       ADD COLUMN IF NOT EXISTS realization_percentage INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE benefits
                       ADD COLUMN IF NOT EXISTS review_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE benefits
                       ADD COLUMN IF NOT EXISTS review_status TEXT
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS benefit_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       benefit_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       previous_status
                       TEXT,
                       new_status
                       TEXT,
                       created_at
                       TEXT
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

    cursor.execute("""
                   ALTER TABLE assumptions
                       ADD COLUMN IF NOT EXISTS assumption_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE assumptions
                       ADD COLUMN IF NOT EXISTS review_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE assumptions
                       ADD COLUMN IF NOT EXISTS validation_status TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE assumptions
                       ADD COLUMN IF NOT EXISTS validation_notes TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE assumptions
                       ADD COLUMN IF NOT EXISTS converted_to_risk TEXT DEFAULT 'No'
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS assumption_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       assumption_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       previous_status
                       TEXT,
                       new_status
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

    cursor.execute("""
                   ALTER TABLE dependencies
                       ADD COLUMN IF NOT EXISTS dependency_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE dependencies
                       ADD COLUMN IF NOT EXISTS criticality TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE dependencies
                       ADD COLUMN IF NOT EXISTS dependency_type TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE dependencies
                       ADD COLUMN IF NOT EXISTS source_project_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE dependencies
                       ADD COLUMN IF NOT EXISTS dependent_project_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE dependencies
                       ADD COLUMN IF NOT EXISTS alert_status TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE dependencies
                       ADD COLUMN IF NOT EXISTS resolution_plan TEXT
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS dependency_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       dependency_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       previous_status
                       TEXT,
                       new_status
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

    cursor.execute("""
                   ALTER TABLE stakeholders
                       ADD COLUMN IF NOT EXISTS stakeholder_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE stakeholders
                       ADD COLUMN IF NOT EXISTS stakeholder_group TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE stakeholders
                       ADD COLUMN IF NOT EXISTS engagement_level TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE stakeholders
                       ADD COLUMN IF NOT EXISTS sentiment TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE stakeholders
                       ADD COLUMN IF NOT EXISTS engagement_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS stakeholder_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       stakeholder_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       previous_status
                       TEXT,
                       new_status
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

    # Decision Log v2 upgrades

    cursor.execute("""
                   ALTER TABLE decisions
                       ADD COLUMN IF NOT EXISTS decision_category TEXT DEFAULT 'General'
                   """)

    cursor.execute("""
                   ALTER TABLE decisions
                       ADD COLUMN IF NOT EXISTS decision_source TEXT DEFAULT 'Manual'
                   """)

    cursor.execute("""
                   ALTER TABLE decisions
                       ADD COLUMN IF NOT EXISTS effectiveness_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE decisions
                       ADD COLUMN IF NOT EXISTS effectiveness_notes TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE decisions
                       ADD COLUMN IF NOT EXISTS linked_risk_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE decisions
                       ADD COLUMN IF NOT EXISTS linked_change_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE decisions
                       ADD COLUMN IF NOT EXISTS linked_governance_review_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE decisions
                       ADD COLUMN IF NOT EXISTS auto_created TEXT DEFAULT 'No'
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS decision_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       decision_id
                       INTEGER,
                       user_id
                       INTEGER,
                       old_status
                       TEXT,
                       new_status
                       TEXT,
                       change_note
                       TEXT,
                       changed_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
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

    cursor.execute("""
                   ALTER TABLE lessons
                       ADD COLUMN IF NOT EXISTS category TEXT
                   """)

    # Lessons Learned v2 upgrades

    cursor.execute("""
                   ALTER TABLE lessons
                       ADD COLUMN IF NOT EXISTS root_cause TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE lessons
                       ADD COLUMN IF NOT EXISTS actions_taken TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE lessons
                       ADD COLUMN IF NOT EXISTS implementation_status TEXT DEFAULT 'Not Started'
                   """)

    cursor.execute("""
                   ALTER TABLE lessons
                       ADD COLUMN IF NOT EXISTS reusable TEXT DEFAULT 'No'
                   """)

    cursor.execute("""
                   ALTER TABLE lessons
                       ADD COLUMN IF NOT EXISTS knowledge_area TEXT DEFAULT 'General'
                   """)

    cursor.execute("""
                   ALTER TABLE lessons
                       ADD COLUMN IF NOT EXISTS effectiveness_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE lessons
                       ADD COLUMN IF NOT EXISTS effectiveness_notes TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE lessons
                       ADD COLUMN IF NOT EXISTS review_date DATE
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS lesson_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       lesson_id
                       INTEGER,
                       user_id
                       INTEGER,
                       old_status
                       TEXT,
                       new_status
                       TEXT,
                       change_note
                       TEXT,
                       changed_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
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

    # Action Log v2 upgrades

    cursor.execute("""
                   ALTER TABLE actions
                       ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'General'
                   """)

    cursor.execute("""
                   ALTER TABLE actions
                       ADD COLUMN IF NOT EXISTS reminder_date DATE
                   """)

    cursor.execute("""
                   ALTER TABLE actions
                       ADD COLUMN IF NOT EXISTS escalation_level TEXT DEFAULT 'None'
                   """)

    cursor.execute("""
                   ALTER TABLE actions
                       ADD COLUMN IF NOT EXISTS recurring TEXT DEFAULT 'No'
                   """)

    cursor.execute("""
                   ALTER TABLE actions
                       ADD COLUMN IF NOT EXISTS governance_review_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE actions
                       ADD COLUMN IF NOT EXISTS completed_date DATE
                   """)


    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS action_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       action_id
                       INTEGER,
                       user_id
                       INTEGER,
                       change_note
                       TEXT,
                       old_status
                       TEXT,
                       new_status
                       TEXT,
                       changed_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   """)

    # Budgets table
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

    # Stage Gates v2 upgrades

    cursor.execute("""
                   ALTER TABLE stage_gates
                       ADD COLUMN IF NOT EXISTS stage_name TEXT DEFAULT 'Initiation'
                   """)

    cursor.execute("""
                   ALTER TABLE stage_gates
                       ADD COLUMN IF NOT EXISTS gate_template TEXT DEFAULT 'Standard Gate'
                   """)

    cursor.execute("""
                   ALTER TABLE stage_gates
                       ADD COLUMN IF NOT EXISTS evidence_required TEXT DEFAULT 'Yes'
                   """)

    cursor.execute("""
                   ALTER TABLE stage_gates
                       ADD COLUMN IF NOT EXISTS evidence_status TEXT DEFAULT 'Pending'
                   """)

    cursor.execute("""
                   ALTER TABLE stage_gates
                       ADD COLUMN IF NOT EXISTS evidence_notes TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE stage_gates
                       ADD COLUMN IF NOT EXISTS progression_status TEXT DEFAULT 'Not Started'
                   """)

    cursor.execute("""
                   ALTER TABLE stage_gates
                       ADD COLUMN IF NOT EXISTS approval_reference TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE stage_gates
                       ADD COLUMN IF NOT EXISTS decision_created TEXT DEFAULT 'No'
                   """)

    cursor.execute("""
                   ALTER TABLE stage_gates
                       ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS stage_gate_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       gate_id
                       INTEGER,
                       user_id
                       INTEGER,
                       old_status
                       TEXT,
                       new_status
                       TEXT,
                       change_note
                       TEXT,
                       changed_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
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

    # Approval Workflows v2 upgrades

    cursor.execute("""
                   ALTER TABLE approvals
                       ADD COLUMN IF NOT EXISTS approval_category TEXT DEFAULT 'General'
                   """)

    cursor.execute("""
                   ALTER TABLE approvals
                       ADD COLUMN IF NOT EXISTS approval_stage TEXT DEFAULT 'Stage 1'
                   """)

    cursor.execute("""
                   ALTER TABLE approvals
                       ADD COLUMN IF NOT EXISTS delegated_to TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE approvals
                       ADD COLUMN IF NOT EXISTS reminder_date DATE
                   """)

    cursor.execute("""
                   ALTER TABLE approvals
                       ADD COLUMN IF NOT EXISTS sla_due_date DATE
                   """)

    cursor.execute("""
                   ALTER TABLE approvals
                       ADD COLUMN IF NOT EXISTS decision_created TEXT DEFAULT 'No'
                   """)

    cursor.execute("""
                   ALTER TABLE approvals
                       ADD COLUMN IF NOT EXISTS approval_reference TEXT
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS approval_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       approval_id
                       INTEGER,
                       user_id
                       INTEGER,
                       old_status
                       TEXT,
                       new_status
                       TEXT,
                       change_note
                       TEXT,
                       changed_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   """)

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

    # Governance Reviews v2 upgrades

    cursor.execute("""
                   ALTER TABLE governance_reviews
                       ADD COLUMN IF NOT EXISTS review_frequency TEXT DEFAULT 'Monthly'
                   """)

    cursor.execute("""
                   ALTER TABLE governance_reviews
                       ADD COLUMN IF NOT EXISTS governance_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE governance_reviews
                       ADD COLUMN IF NOT EXISTS maturity_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE governance_reviews
                       ADD COLUMN IF NOT EXISTS risk_trend TEXT DEFAULT 'Stable'
                   """)

    cursor.execute("""
                   ALTER TABLE governance_reviews
                       ADD COLUMN IF NOT EXISTS executive_summary TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE governance_reviews
                       ADD COLUMN IF NOT EXISTS auto_schedule_next TEXT DEFAULT 'No'
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS governance_review_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       review_id
                       INTEGER,
                       user_id
                       INTEGER,
                       old_status
                       TEXT,
                       new_status
                       TEXT,
                       change_note
                       TEXT,
                       changed_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
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

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS roi_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS benefits_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS resource_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS strategic_objective TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS weighted_priority_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS investment_category TEXT
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS prioritisation_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       prioritisation_id
                       INTEGER,
                       user_id
                       INTEGER,
                       project_id
                       INTEGER,
                       priority_score
                       INTEGER,
                       weighted_priority_score
                       INTEGER,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   """)

    # Project Prioritisation Table v2

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS roi_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS benefits_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS resource_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS weighted_priority_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS priority_band TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS investment_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE project_prioritisation
                       ADD COLUMN IF NOT EXISTS strategic_objective TEXT
                   """)


    # Programmes Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS programmes
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       programme_name
                       TEXT,

                       description
                       TEXT,

                       sponsor
                       TEXT,

                       manager
                       TEXT,

                       status
                       TEXT,

                       start_date
                       DATE,

                       end_date
                       DATE,

                       budget
                       NUMERIC,

                       benefits
                       TEXT,

                       risks
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)

    # Programmes Table v2
    cursor.execute("""
                   ALTER TABLE programmes
                       ADD COLUMN IF NOT EXISTS health_score INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE programmes
                       ADD COLUMN IF NOT EXISTS health_status TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE programmes
                       ADD COLUMN IF NOT EXISTS linked_projects INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE programmes
                       ADD COLUMN IF NOT EXISTS milestone_count INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE programmes
                       ADD COLUMN IF NOT EXISTS open_risks INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE programmes
                       ADD COLUMN IF NOT EXISTS open_issues INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE programmes
                       ADD COLUMN IF NOT EXISTS lessons_count INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE programmes
                       ADD COLUMN IF NOT EXISTS archived BOOLEAN DEFAULT FALSE
                   """)

    # Programmes Performance History

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS programme_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       programme_id
                       INTEGER,

                       user_id
                       INTEGER,

                       health_score
                       INTEGER,

                       open_risks
                       INTEGER,

                       open_issues
                       INTEGER,

                       linked_projects
                       INTEGER,

                       action
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)

    # Programmes Milestones

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS programme_milestones
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       programme_id
                       INTEGER,

                       title
                       TEXT,

                       milestone_date
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)


    # Programmes Register

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS programme_benefits
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       programme_id
                       INTEGER,

                       benefit_name
                       TEXT,

                       owner
                       TEXT,

                       target_value
                       TEXT,

                       actual_value
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)


    # Portfolio Board v2 upgrades

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS portfolio_sponsor TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS portfolio_manager TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS strategic_objective TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS expected_benefits TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS benefits_status TEXT DEFAULT 'Not Started'
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS portfolio_archived BOOLEAN DEFAULT FALSE
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS portfolio_performance_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       user_id
                       INTEGER,
                       total_projects
                       INTEGER,
                       total_budget
                       NUMERIC,
                       total_actual
                       NUMERIC,
                       total_open_risks
                       INTEGER,
                       total_open_issues
                       INTEGER,
                       average_completion
                       INTEGER,
                       average_health_score
                       INTEGER,
                       portfolio_status
                       TEXT,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   """)

    # Portfolio Roadmap v2 upgrades

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS roadmap_milestone TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS roadmap_dependency TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS strategic_initiative TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS baseline_start_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS baseline_end_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS roadmap_status TEXT DEFAULT 'On Track'
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS portfolio_roadmap_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       user_id
                       INTEGER,
                       project_id
                       INTEGER,
                       project_name
                       TEXT,
                       start_date
                       TEXT,
                       end_date
                       TEXT,
                       baseline_start_date
                       TEXT,
                       baseline_end_date
                       TEXT,
                       progress
                       INTEGER,
                       roadmap_status
                       TEXT,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   """)

    # Portfolio Health Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS portfolio_health
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       health_score
                       INTEGER,

                       risk_exposure
                       INTEGER,

                       financial_health
                       INTEGER,

                       performance_score
                       INTEGER,

                       trend
                       TEXT,

                       commentary
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS project_health_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       project_id
                       INTEGER,
                       health_score
                       INTEGER,
                       risk_score
                       INTEGER,
                       budget_usage_percent
                       INTEGER,
                       created_at
                       TEXT
                   )
                   """)

    cursor.execute("""
                   ALTER TABLE project_health_history
                       ADD COLUMN IF NOT EXISTS overdue_tasks INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE project_health_history
                       ADD COLUMN IF NOT EXISTS blocked_tasks INTEGER DEFAULT 0
                   """)



    # Audit Logs Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS audit_logs
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       action
                       TEXT,

                       module
                       TEXT,

                       details
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)

    # User Roles Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS user_roles
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       role
                       TEXT,

                       created_at
                       TEXT

                   )
                   """)



    cursor.execute("""

        ALTER TABLE users

        ADD COLUMN IF NOT EXISTS timezone TEXT

    """)

    cursor.execute("""

        ALTER TABLE users

        ADD COLUMN IF NOT EXISTS language TEXT

    """)

    cursor.execute("""

        ALTER TABLE users

        ADD COLUMN IF NOT EXISTS theme_preference TEXT

    """)

    cursor.execute("""

        ALTER TABLE users

        ADD COLUMN IF NOT EXISTS notifications_enabled TEXT

    """)

    cursor.execute("""

        ALTER TABLE users

        ADD COLUMN IF NOT EXISTS mfa_enabled TEXT

    """)

    # User Roles v2 upgrades

    cursor.execute("""
                   ALTER TABLE user_roles
                       ADD COLUMN IF NOT EXISTS role_description TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE user_roles
                       ADD COLUMN IF NOT EXISTS parent_role TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE user_roles
                       ADD COLUMN IF NOT EXISTS role_owner TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE user_roles
                       ADD COLUMN IF NOT EXISTS role_template TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE user_roles
                       ADD COLUMN IF NOT EXISTS custom_role BOOLEAN DEFAULT FALSE
                   """)

    cursor.execute("""
                   ALTER TABLE user_roles
                       ADD COLUMN IF NOT EXISTS updated_at TEXT
                   """)

    # Permissions Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS permissions
                   (

                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       role
                       TEXT,

                       module
                       TEXT,

                       can_view
                       BOOLEAN,

                       can_create
                       BOOLEAN,

                       can_edit
                       BOOLEAN,

                       can_delete
                       BOOLEAN

                   )
                   """)

    # Organisations Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS organisations
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       organisation_name
                       TEXT,

                       industry
                       TEXT,

                       plan
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)

    # Workspaces Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS workspaces
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       organisation_id
                       INTEGER,

                       workspace_name
                       TEXT,

                       workspace_type
                       TEXT,

                       owner
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)

    # Subscription Plans Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS subscription_plans
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       plan_name
                       TEXT,

                       price
                       NUMERIC,

                       billing_cycle
                       TEXT,

                       max_projects
                       INTEGER,

                       max_users
                       INTEGER,

                       features
                       TEXT,

                       status
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)

    # Customer Subscriptions Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS customer_subscriptions
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       organisation_id
                       INTEGER,

                       plan_id
                       INTEGER,

                       start_date
                       DATE,

                       end_date
                       DATE,

                       status
                       TEXT,

                       payment_status
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)

    # Notification Settings Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS notification_settings
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       notification_type
                       TEXT,

                       channel
                       TEXT,

                       enabled
                       TEXT,

                       frequency
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)

    # Comments Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS comments
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       project_id
                       INTEGER,

                       username
                       TEXT,

                       comment
                       TEXT,

                       created_at
                       TEXT
                   )
                   """)

    cursor.execute("""
                   ALTER TABLE lessons
                       ADD COLUMN IF NOT EXISTS status TEXT
                   """)

    # User Invitations

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS user_invitations
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       organisation_id
                       INTEGER,

                       workspace_id
                       INTEGER,

                       invited_email
                       TEXT,

                       role
                       TEXT,

                       status
                       TEXT,

                       invitation_token
                       TEXT,

                       invited_by
                       INTEGER,

                       created_at
                       TEXT
                   )
                   """)

    # Billing History Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS billing_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       organisation_id
                       INTEGER,

                       plan
                       TEXT,

                       amount
                       NUMERIC
                   (
                       10,
                       2
                   ),

                       status TEXT,

                       reference_number TEXT,

                       billing_date TEXT,

                       created_at TEXT
                       )
                   """)

    # Invoices Table

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS invoices
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,

                       user_id
                       INTEGER,

                       organisation_id
                       INTEGER,

                       invoice_number
                       TEXT,

                       plan
                       TEXT,

                       amount
                       NUMERIC
                   (
                       10,
                       2
                   ),

                       status TEXT,

                       invoice_date TEXT,

                       created_at TEXT
                       )
                   """)



    cursor.execute("""
                   ALTER TABLE user_roles
                       ADD COLUMN IF NOT EXISTS organisation_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE user_roles
                       ADD COLUMN IF NOT EXISTS workspace_id INTEGER
                   """)

    try:
        cursor.execute("""
                       ALTER TABLE users
                           ADD COLUMN reset_token TEXT
                       """)
    except:
        pass

    try:
        cursor.execute("""
                       ALTER TABLE users
                           ADD COLUMN reset_token_created_at TEXT
                       """)
    except:
        pass

    try:
        cursor.execute("""
                       ALTER TABLE users
                           ADD COLUMN is_verified BOOLEAN DEFAULT FALSE
                       """)
    except:
        pass

    try:
        cursor.execute("""
                       ALTER TABLE users
                           ADD COLUMN verification_token TEXT
                       """)
    except:
        pass

    try:
        cursor.execute("""
                       ALTER TABLE users
                           ADD COLUMN verification_token_created_at TEXT
                       """)
    except:
        pass

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS email_notifications
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       user_id
                       INTEGER,
                       recipient_email
                       TEXT,
                       subject
                       TEXT,
                       message
                       TEXT,
                       status
                       TEXT,
                       created_at
                       TEXT
                   )
                   """)

    try:
        cursor.execute("""
                       ALTER TABLE organisations
                           ADD COLUMN trial_start_date TEXT
                       """)
    except:
        pass

    try:
        cursor.execute("""
                       ALTER TABLE organisations
                           ADD COLUMN trial_end_date TEXT
                       """)
    except:
        pass

    try:
        cursor.execute("""
                       ALTER TABLE organisations
                           ADD COLUMN subscription_status TEXT DEFAULT 'Trial'
                       """)
    except:
        pass

    try:
        cursor.execute("""
                       ALTER TABLE organisations
                           ADD COLUMN stripe_customer_id TEXT
                       """)
    except:
        pass

    try:
        cursor.execute("""
                       ALTER TABLE organisations
                           ADD COLUMN stripe_subscription_id TEXT
                       """)
    except:
        pass

    try:
        cursor.execute("""
                       ALTER TABLE organisations
                           ADD COLUMN stripe_checkout_session_id TEXT
                       """)
    except:
        pass

    # Budget Management v2 upgrades

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS budget_owner TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS budget_approver TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS budget_baseline NUMERIC DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS budget_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS funding_source TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS capex_opex TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS approval_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS budget_notes TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS cost_centre TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS programme_link TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS portfolio_link TEXT
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS budget_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       budget_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       old_budget_amount
                       NUMERIC,
                       new_budget_amount
                       NUMERIC,
                       old_actual_cost
                       NUMERIC,
                       new_actual_cost
                       NUMERIC,
                       old_forecast_cost
                       NUMERIC,
                       new_forecast_cost
                       NUMERIC,
                       change_note
                       TEXT,
                       created_at
                       TEXT
                   )
                   """)

    # Forecast vs Actual v2 upgrades

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS forecast_owner TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS forecast_approver TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS baseline_forecast NUMERIC DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS forecast_assumptions TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS forecast_version TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS forecast_confidence TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE budgets
                       ADD COLUMN IF NOT EXISTS forecast_approval_status TEXT DEFAULT 'Draft'
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS forecast_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       budget_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       old_forecast_cost
                       NUMERIC,
                       new_forecast_cost
                       NUMERIC,
                       old_actual_cost
                       NUMERIC,
                       new_actual_cost
                       NUMERIC,
                       forecast_version
                       TEXT,
                       change_note
                       TEXT,
                       created_at
                       TEXT
                   )
                   """)

    # Profitability Dashboard v2 upgrades

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS revenue NUMERIC DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS profit_forecast NUMERIC DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS cost_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE projects
                       ADD COLUMN IF NOT EXISTS benefits_realisation_value NUMERIC DEFAULT 0
                   """)

    # Invoices v2 upgrades

    cursor.execute("""
                   ALTER TABLE invoices
                       ADD COLUMN IF NOT EXISTS due_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE invoices
                       ADD COLUMN IF NOT EXISTS payment_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE invoices
                       ADD COLUMN IF NOT EXISTS vat_amount NUMERIC DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE invoices
                       ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'GBP'
                   """)

    cursor.execute("""
                   ALTER TABLE invoices
                       ADD COLUMN IF NOT EXISTS invoice_notes TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE invoices
                       ADD COLUMN IF NOT EXISTS payment_terms TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE invoices
                       ADD COLUMN IF NOT EXISTS stripe_invoice_reference TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE invoices
                       ADD COLUMN IF NOT EXISTS invoice_attachment_url TEXT
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS invoice_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       invoice_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       previous_status
                       TEXT,
                       new_status
                       TEXT,
                       amount
                       NUMERIC,
                       notes
                       TEXT,
                       created_at
                       TEXT
                   )
                   """)

    # Billing History v2 upgrades

    cursor.execute("""
                   ALTER TABLE billing_history
                       ADD COLUMN IF NOT EXISTS payment_gateway TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE billing_history
                       ADD COLUMN IF NOT EXISTS transaction_id TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE billing_history
                       ADD COLUMN IF NOT EXISTS billing_cycle TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE billing_history
                       ADD COLUMN IF NOT EXISTS renewal_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE billing_history
                       ADD COLUMN IF NOT EXISTS refund_amount NUMERIC DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE billing_history
                       ADD COLUMN IF NOT EXISTS chargeback_status TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE billing_history
                       ADD COLUMN IF NOT EXISTS invoice_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE billing_history
                       ADD COLUMN IF NOT EXISTS stripe_payment_reference TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE billing_history
                       ADD COLUMN IF NOT EXISTS billing_notes TEXT
                   """)

    # Resource Allocation v2 upgrades

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS allocation_percentage INTEGER DEFAULT 100
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS planned_allocation INTEGER DEFAULT 100
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS actual_allocation INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS resource_capacity INTEGER DEFAULT 100
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS resource_allocation_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       team_member_id
                       INTEGER,
                       user_id
                       INTEGER,
                       active_tasks
                       INTEGER,
                       completed_tasks
                       INTEGER,
                       utilisation
                       INTEGER,
                       allocation_status
                       TEXT,
                       planned_allocation
                       INTEGER,
                       actual_allocation
                       INTEGER,
                       notes
                       TEXT,
                       created_at
                       TEXT
                   )
                   """)

    # Team Members v2 upgrades

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS manager TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS department TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS employment_status TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS availability TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS certifications TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS training_records TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS performance_notes TEXT
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS team_member_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       team_member_id
                       INTEGER,
                       user_id
                       INTEGER,
                       action
                       TEXT,
                       total_tasks
                       INTEGER,
                       active_tasks
                       INTEGER,
                       completed_tasks
                       INTEGER,
                       blocked_tasks
                       INTEGER,
                       utilisation
                       INTEGER,
                       notes
                       TEXT,
                       created_at
                       TEXT
                   )
                   """)

    # Skills Matrix v2 upgrades

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS skill_proficiency TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS skill_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS competency_level TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS training_required TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS succession_candidate TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE team_members
                       ADD COLUMN IF NOT EXISTS skills_gap_notes TEXT
                   """)

    # Clients v2 upgrades

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS client_owner TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS account_manager TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS client_health_score INTEGER DEFAULT 70
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS client_risk_rating TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS opportunity_stage TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS renewal_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS contract_expiry_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS satisfaction_score INTEGER DEFAULT 0
                   """)

    # Clients v2 upgrades

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS client_owner TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS account_manager TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS client_health_score INTEGER DEFAULT 70
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS client_risk_rating TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS opportunity_stage TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS renewal_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS contract_expiry_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE clients
                       ADD COLUMN IF NOT EXISTS satisfaction_score INTEGER DEFAULT 0
                   """)

    # User Management v2 upgrades

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Active'
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS organisation TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS last_login TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS password_reset_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS failed_login_count INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS mfa_enabled TEXT DEFAULT 'No'
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS created_at TEXT
                   """)

    # User Invitations v2 upgrades

    cursor.execute("""
                   ALTER TABLE user_invitations
                       ADD COLUMN IF NOT EXISTS expiry_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE user_invitations
                       ADD COLUMN IF NOT EXISTS resend_count INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE user_invitations
                       ADD COLUMN IF NOT EXISTS last_reminder_sent TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE user_invitations
                       ADD COLUMN IF NOT EXISTS invitation_notes TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE user_invitations
                       ADD COLUMN IF NOT EXISTS accepted_at TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE user_invitations
                       ADD COLUMN IF NOT EXISTS revoked_at TEXT
                   """)

    # Permissions v2 upgrades

    cursor.execute("""
                   ALTER TABLE permissions
                       ADD COLUMN IF NOT EXISTS permission_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE permissions
                       ADD COLUMN IF NOT EXISTS permission_template TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE permissions
                       ADD COLUMN IF NOT EXISTS inherits_from TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE permissions
                       ADD COLUMN IF NOT EXISTS risk_level TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE permissions
                       ADD COLUMN IF NOT EXISTS permission_notes TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE permissions
                       ADD COLUMN IF NOT EXISTS last_reviewed_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE permissions
                       ADD COLUMN IF NOT EXISTS created_at TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE permissions
                       ADD COLUMN IF NOT EXISTS updated_at TEXT
                   """)

    # Activity Feed v2 upgrades

    cursor.execute("""
                   ALTER TABLE activities
                       ADD COLUMN IF NOT EXISTS user_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE activities
                       ADD COLUMN IF NOT EXISTS activity_type TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE activities
                       ADD COLUMN IF NOT EXISTS module TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE activities
                       ADD COLUMN IF NOT EXISTS project_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE activities
                       ADD COLUMN IF NOT EXISTS severity TEXT
                   """)

    # ==================================================
    # USER SECURITY & PASSWORD RESET
    # ==================================================

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS reset_token TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS reset_token_created_at TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS password_reset_date TEXT
                   """)

    # ==================================================
    # SAAS USAGE ANALYTICS
    # ==================================================

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS ai_usage
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       user_id
                       INTEGER,
                       organisation_id
                       INTEGER,
                       workspace_id
                       INTEGER,
                       usage_type
                       TEXT,
                       usage_count
                       INTEGER
                       DEFAULT
                       0,
                       created_at
                       TEXT
                   )
                   """)

    # Organisations v2 upgrades

    cursor.execute("""
                   ALTER TABLE organisations
                       ADD COLUMN IF NOT EXISTS account_status TEXT DEFAULT 'Active'
                   """)

    cursor.execute("""
                   ALTER TABLE organisations
                       ADD COLUMN IF NOT EXISTS organisation_owner TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE organisations
                       ADD COLUMN IF NOT EXISTS contact_email TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE organisations
                       ADD COLUMN IF NOT EXISTS organisation_size TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE organisations
                       ADD COLUMN IF NOT EXISTS region TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE organisations
                       ADD COLUMN IF NOT EXISTS updated_at TEXT
                   """)

    # Workspaces v2 upgrades

    cursor.execute("""
                   ALTER TABLE workspaces
                       ADD COLUMN IF NOT EXISTS workspace_description TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE workspaces
                       ADD COLUMN IF NOT EXISTS workspace_health_score INTEGER DEFAULT 80
                   """)

    cursor.execute("""
                   ALTER TABLE workspaces
                       ADD COLUMN IF NOT EXISTS updated_at TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE user_roles
                       ADD COLUMN IF NOT EXISTS organisation_id INTEGER
                   """)

    cursor.execute("""
                   ALTER TABLE user_roles
                       ADD COLUMN IF NOT EXISTS workspace_id INTEGER
                   """)

    # Subscription v2 upgrades

    cursor.execute("""
                   ALTER TABLE subscription_plans
                       ADD COLUMN IF NOT EXISTS max_workspaces INTEGER DEFAULT 1
                   """)

    cursor.execute("""
                   ALTER TABLE subscription_plans
                       ADD COLUMN IF NOT EXISTS ai_enabled TEXT DEFAULT 'No'
                   """)

    cursor.execute("""
                   ALTER TABLE subscription_plans
                       ADD COLUMN IF NOT EXISTS plan_description TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE subscription_plans
                       ADD COLUMN IF NOT EXISTS updated_at TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE customer_subscriptions
                       ADD COLUMN IF NOT EXISTS renewal_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE customer_subscriptions
                       ADD COLUMN IF NOT EXISTS subscription_notes TEXT
                   """)

    # ==================================================
    # NOTIFICATION SETTINGS V2
    # ==================================================

    cursor.execute("""
                   ALTER TABLE notification_settings
                       ADD COLUMN IF NOT EXISTS notification_category TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE notification_settings
                       ADD COLUMN IF NOT EXISTS description TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE notification_settings
                       ADD COLUMN IF NOT EXISTS priority TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE notification_settings
                       ADD COLUMN IF NOT EXISTS updated_at TEXT
                   """)

    # ==================================================
    # EMAIL NOTIFICATIONS V2
    # ==================================================

    cursor.execute("""
                   ALTER TABLE email_notifications
                       ADD COLUMN IF NOT EXISTS email_template TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE email_notifications
                       ADD COLUMN IF NOT EXISTS notification_type TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE email_notifications
                       ADD COLUMN IF NOT EXISTS scheduled_date TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE email_notifications
                       ADD COLUMN IF NOT EXISTS sent_at TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE email_notifications
                       ADD COLUMN IF NOT EXISTS failure_reason TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE email_notifications
                       ADD COLUMN IF NOT EXISTS priority TEXT
                   """)

    # ==================================================
    # ACCOUNT & AUTHENTICATION V2
    # ==================================================

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS verification_token TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS verification_token_created_at TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS last_login TEXT
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0
                   """)

    cursor.execute("""
                   ALTER TABLE users
                       ADD COLUMN IF NOT EXISTS failed_login_count INTEGER DEFAULT 0
                   """)

    # ==================================================
    # AI ASSISTANT CHAT HISTORY
    # ==================================================

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS ai_chat_history
                   (
                       id
                       SERIAL
                       PRIMARY
                       KEY,
                       user_id
                       INTEGER,
                       prompt
                       TEXT,
                       response
                       TEXT,
                       confidence_score
                       INTEGER,
                       source_summary
                       TEXT,
                       mode
                       TEXT,
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

def calculate_weighted_progress(tasks):

    if not tasks:
        return 0

    progress_points = 0

    for task in tasks:

        status = task["status"]

        if status == "Completed":
            progress_points += 100

        elif status == "In Progress":
            progress_points += 50

        elif status == "Blocked":
            progress_points += 25

        else:
            progress_points += 0

    return round(progress_points / len(tasks))


def calculate_financial_health(budget_amount, actual_cost, forecast_cost=0):

    budget_amount = float(budget_amount or 0)
    actual_cost = float(actual_cost or 0)
    forecast_cost = float(forecast_cost or 0)

    if budget_amount <= 0:
        return {
            "score": 50,
            "status": "No Budget",
            "risk": "Medium",
            "message": "No approved budget has been set."
        }

    actual_usage = round((actual_cost / budget_amount) * 100)
    forecast_usage = round((forecast_cost / budget_amount) * 100)

    score = 100

    if actual_usage > 100:
        score -= 40
    elif actual_usage > 90:
        score -= 25
    elif actual_usage > 70:
        score -= 10

    if forecast_usage > 100:
        score -= 25
    elif forecast_usage > 90:
        score -= 15

    score = max(0, min(100, score))

    if score >= 80:
        status = "Healthy"
        risk = "Low"
        message = "Financial position is healthy."
    elif score >= 60:
        status = "Monitor"
        risk = "Medium"
        message = "Financial position requires monitoring."
    else:
        status = "At Risk"
        risk = "High"
        message = "Financial position requires immediate review."

    return {
        "score": score,
        "status": status,
        "risk": risk,
        "message": message
    }



def calculate_risk_health(high_risks, medium_risks, low_risks, open_issues):

    risk_health = 100

    risk_health -= high_risks * 10
    risk_health -= medium_risks * 5
    risk_health -= low_risks * 2
    risk_health -= open_issues * 4

    return max(0, min(100, round(risk_health)))


def get_health_status(score):

    if score >= 75:
        return "Green"

    elif score >= 50:
        return "Amber"

    else:
        return "Red"

# PASTE HERE

def get_current_user_role():

    if "user_id" not in session:
        return None

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    organisation_id = session.get("organisation_id")
    workspace_id = session.get("workspace_id")

    if organisation_id and workspace_id:

        cursor.execute("""
            SELECT role
            FROM user_roles
            WHERE user_id = %s
            AND organisation_id = %s
            AND workspace_id = %s
            ORDER BY id DESC
            LIMIT 1
        """, (
            session["user_id"],
            organisation_id,
            workspace_id
        ))

    elif organisation_id:

        cursor.execute("""
            SELECT role
            FROM user_roles
            WHERE user_id = %s
            AND organisation_id = %s
            ORDER BY id DESC
            LIMIT 1
        """, (
            session["user_id"],
            organisation_id
        ))

    else:

        cursor.execute("""
            SELECT role
            FROM user_roles
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 1
        """, (
            session["user_id"],
        ))

    role = cursor.fetchone()

    conn.close()

    if role:
        return role["role"]

    return "Admin"


def has_permission(
    module,
    permission_type
):

    role = get_current_user_role()

    if role == "Admin":
        return True

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM permissions
        WHERE role = %s
        AND module = %s
        LIMIT 1
    """, (
        role,
        module
    ))

    permission = cursor.fetchone()

    conn.close()

    if not permission:
        return False

    if permission_type == "view":
        return permission["can_view"]

    if permission_type == "create":
        return permission["can_create"]

    if permission_type == "edit":
        return permission["can_edit"]

    if permission_type == "delete":
        return permission["can_delete"]

    return False

def is_subscription_active(organisation):

    if organisation.get("subscription_status") == "Active":
        return True

    if organisation.get("subscription_status") == "Trial":

        trial_end = organisation.get("trial_end_date")

        if trial_end:

            end_date = datetime.strptime(
                trial_end,
                "%Y-%m-%d"
            ).date()

            if date.today() <= end_date:
                return True

    return False

def get_plan_limits(plan):

    limits = {
        "Free": {
            "max_projects": 3,
            "max_users": 1,
            "max_workspaces": 1,
            "ai_enabled": False
        },
        "Basic": {
            "max_projects": 10,
            "max_users": 3,
            "max_workspaces": 1,
            "ai_enabled": False
        },
        "Professional": {
            "max_projects": 50,
            "max_users": 10,
            "max_workspaces": 5,
            "ai_enabled": True
        },
        "Enterprise": {
            "max_projects": 9999,
            "max_users": 9999,
            "max_workspaces": 9999,
            "ai_enabled": True
        }
    }

    return limits.get(plan, limits["Free"])

def get_user_current_organisation():

    organisation_id = session.get("organisation_id")

    if not organisation_id:
        return None

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE id = %s
        AND user_id = %s
    """, (
        organisation_id,
        session["user_id"]
    ))

    organisation = cursor.fetchone()

    conn.close()

    return organisation


def can_create_project():

    organisation = get_user_current_organisation()

    if not organisation:
        return True

    limits = get_plan_limits(
        organisation["plan"]
    )

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM projects
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    project_count = cursor.fetchone()[0]

    conn.close()

    if project_count >= limits["max_projects"]:
        return False

    return True

def can_invite_user():

    organisation = get_user_current_organisation()

    if not organisation:
        return True

    limits = get_plan_limits(
        organisation["plan"]
    )

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM user_roles
        WHERE organisation_id = %s
    """, (
        organisation["id"],
    ))

    user_count = cursor.fetchone()[0]

    conn.close()

    if user_count >= limits["max_users"]:
        return False

    return True

def can_create_workspace():

    organisation = get_user_current_organisation()

    if not organisation:
        return True

    limits = get_plan_limits(
        organisation["plan"]
    )

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM workspaces
        WHERE organisation_id = %s
    """, (
        organisation["id"],
    ))

    workspace_count = cursor.fetchone()[0]

    conn.close()

    if workspace_count >= limits["max_workspaces"]:
        return False

    return True

def can_use_ai_features():

    organisation = get_user_current_organisation()

    if not organisation:
        return True

    limits = get_plan_limits(
        organisation["plan"]
    )

    return limits["ai_enabled"]



@app.route("/")
def home():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
                   SELECT projects.*,
                          clients.name      AS client_name,
                          clients.company   AS client_company,
                          team_members.name AS project_manager_name,
                          team_members.role AS project_manager_role,
                          stakeholders.name AS sponsor_name,
                          stakeholders.role AS sponsor_role
                   FROM projects
                            LEFT JOIN clients
                                      ON projects.client_id = clients.id
                            LEFT JOIN team_members
                                      ON projects.project_manager_id = team_members.id
                            LEFT JOIN stakeholders
                                      ON projects.sponsor_id = stakeholders.id
                   WHERE projects.user_id = %s
                     AND COALESCE(projects.is_archived, FALSE) = FALSE
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

            progress_points = 0

            for task in tasks:
                if task["status"] == "Completed":
                    progress_points += 100
                elif task["status"] == "In Progress":
                    progress_points += 50
                elif task["status"] == "Blocked":
                    progress_points += 25
                else:
                    progress_points += 0

            completion = round(progress_points / len(tasks))

        else:
            completion = 0

        if project["status"] == "Completed":
            completion = 100

        if project["status"] == "Planning" and completion == 0 and budget_used_percent > 0:
            completion = min(25, max(10, budget_used_percent))

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

        project_health_score = 100

        project_health_score -= min(project_overdue_tasks * 15, 30)
        project_health_score -= min(project_blocked_tasks * 15, 30)

        if budget_used_percent > 100:
            project_health_score -= 25
        elif budget_used_percent > 80:
            project_health_score -= 10

        if completion < 30 and project["status"] != "Planning":
            project_health_score -= 20

        project_health_score = max(0, min(100, project_health_score))

        cursor.execute("""
                       INSERT INTO project_health_history
                       (project_id,
                        health_score,
                        risk_score,
                        budget_usage_percent,
                        overdue_tasks,
                        blocked_tasks,
                        created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       """, (
                           project["id"],
                           project_health_score,
                           risk_score,
                           budget_used_percent,
                           project_overdue_tasks,
                           project_blocked_tasks,
                           str(date.today())
                       ))

        cursor.execute("""
                       SELECT health_score
                       FROM project_health_history
                       WHERE project_id = %s
                       ORDER BY id DESC LIMIT 2
                       """, (
                           project["id"],
                       ))

        health_history = cursor.fetchall()

        trend = "Stable"

        if len(health_history) >= 2:

            latest_score = health_history[0]["health_score"]
            previous_score = health_history[1]["health_score"]

            if latest_score > previous_score:
                trend = "Improving"

            elif latest_score < previous_score:
                trend = "Declining"

        recovery_plan = []

        if project_overdue_tasks > 0:
            recovery_plan.append(
                f"Resolve {project_overdue_tasks} overdue task(s)"
            )

        if project_blocked_tasks > 0:
            recovery_plan.append(
                f"Unblock {project_blocked_tasks} blocked task(s)"
            )

        if budget_used_percent > 100:
            recovery_plan.append(
                "Reduce project spending"
            )

        if completion < 50:
            recovery_plan.append(
                "Increase delivery velocity"
            )

        if len(recovery_plan) == 0:
            recovery_plan.append(
                "No recovery actions required"
            )

        predictive_health_score = project_health_score

        if project_overdue_tasks > 0:
            predictive_health_score -= min(project_overdue_tasks * 5, 15)

        if project_blocked_tasks > 0:
            predictive_health_score -= min(project_blocked_tasks * 5, 15)

        if budget_used_percent > 90:
            predictive_health_score -= 10

        if completion < 50 and project["status"] == "In Progress":
            predictive_health_score -= 10

        predictive_health_score = max(0, min(100, predictive_health_score))

        if predictive_health_score >= 80:
            predictive_health_label = "Likely Healthy"
        elif predictive_health_score >= 60:
            predictive_health_label = "Likely Stable"
        elif predictive_health_score >= 40:
            predictive_health_label = "Likely At Risk"
        else:
            predictive_health_label = "Likely Critical"

        risk_trend = "Stable"
        budget_trend = "Stable"
        schedule_trend = "Stable"

        cursor.execute("""
                       SELECT risk_score,
                              budget_usage_percent,
                              overdue_tasks,
                              blocked_tasks
                       FROM project_health_history
                       WHERE project_id = %s
                       ORDER BY id DESC LIMIT 2
                       """, (
                           project["id"],
                       ))

        trend_history = cursor.fetchall()

        if len(trend_history) >= 2:

            latest = trend_history[0]
            previous = trend_history[1]

            if latest["risk_score"] > previous["risk_score"]:
                risk_trend = "Increasing Risk"
            elif latest["risk_score"] < previous["risk_score"]:
                risk_trend = "Reducing Risk"

            if latest["budget_usage_percent"] > previous["budget_usage_percent"]:
                budget_trend = "Increasing Spend"
            elif latest["budget_usage_percent"] < previous["budget_usage_percent"]:
                budget_trend = "Reducing Spend"

            latest_schedule_pressure = (
                    (latest["overdue_tasks"] or 0)
                    + (latest["blocked_tasks"] or 0)
            )

            previous_schedule_pressure = (
                    (previous["overdue_tasks"] or 0)
                    + (previous["blocked_tasks"] or 0)
            )

            if latest_schedule_pressure > previous_schedule_pressure:
                schedule_trend = "Deteriorating"
            elif latest_schedule_pressure < previous_schedule_pressure:
                schedule_trend = "Improving"

        ai_recommendation = []

        if project_overdue_tasks >= 3:
            ai_recommendation.append(
                f"Resolve {project_overdue_tasks} overdue tasks immediately."
            )

        if project_blocked_tasks >= 2:
            ai_recommendation.append(
                f"Escalate {project_blocked_tasks} blocked activities."
            )

        if budget_used_percent >= 90:
            ai_recommendation.append(
                "Budget consumption exceeds 90%. Review spending."
            )

        if (
                project_high_priority >= 5
                and completion < 50
        ):
            ai_recommendation.append(
                "High-priority workload threatens delivery dates."
            )

        if (
                completion >= 80
                and project_overdue_tasks == 0
                and project_blocked_tasks == 0
        ):
            if project["status"] == "Completed":
                ai_recommendation.append(
                    "Project successfully delivered. Closure and benefits tracking are underway."
                )
            else:
                ai_recommendation.append(
                    "Delivery healthy. Continue current execution plan."
                )

        if (
                completion < 30
                and project_overdue_tasks == 0
        ):
            if project["status"] == "Planning":
                ai_recommendation.append(
                    "Planning activities are underway. Delivery mobilisation is progressing."
                )
            else:
                ai_recommendation.append(
                    "Project delivery pace is behind schedule."
                )

        if len(ai_recommendation) == 0:
            ai_recommendation.append(
                "No major delivery risks detected."
            )

        all_projects.append({
            "project": (
                project["id"],
                project["name"],
                project["status"],
                project["start_date"],
                project["end_date"]
            ),
            "description": project["description"],
            "tasks": task_list,
            "completion": completion,
            "estimated_budget": estimated_budget,
            "actual_cost": actual_cost,
            "remaining_budget": remaining_budget,
            "budget_used_percent": budget_used_percent,
            "client_name": project["client_name"],
            "client_company": project["client_company"],
            "project_manager_name": project["project_manager_name"],
            "project_manager_role": project["project_manager_role"],
            "sponsor_name": project["sponsor_name"],
            "sponsor_role": project["sponsor_role"],
            "project_type": project["project_type"],
            "programme": project["programme"],
            "portfolio": project["portfolio"],
            "is_archived": project["is_archived"],
            "risk_score": risk_score,
            "risk_label": risk_label,
            "project_health_score": project_health_score,
            "trend": trend,
            "recovery_plan": recovery_plan,
            "predictive_health_score": predictive_health_score,
            "predictive_health_label": predictive_health_label,
            "risk_trend": risk_trend,
            "budget_trend": budget_trend,
            "schedule_trend": schedule_trend,
            "ai_recommendation": ai_recommendation
        })

    status_priority = {
        "In Progress": 1,
        "Planning": 2,
        "Completed": 3
    }

    all_projects = sorted(
        all_projects,
        key=lambda item: (
            0 if item["completion"] >= 20 else 1,
            status_priority.get(item["project"][2], 4),
            -item["completion"]
        )
    )

    status_showcase_priority = {
        "Planning": 1,
        "In Progress": 2,
        "Completed": 3
    }

    all_projects = sorted(
        all_projects,
        key=lambda item: (
            status_showcase_priority.get(
                item["project"][2],
                4
            ),
            -item["completion"]
        )
    )

    planning_projects = [
        item for item in all_projects
        if item["project"][2] == "Planning"
    ]

    in_progress_projects = [
        item for item in all_projects
        if item["project"][2] == "In Progress"
    ]

    completed_projects = [
        item for item in all_projects
        if item["project"][2] == "Completed"
    ]

    planning_projects = sorted(planning_projects, key=lambda item: -item["completion"])
    in_progress_projects = sorted(in_progress_projects, key=lambda item: -item["completion"])
    completed_projects = sorted(completed_projects, key=lambda item: -item["completion"])

    showcase_projects = []

    if planning_projects:
        showcase_projects.append(planning_projects[0])

    if in_progress_projects:
        showcase_projects.append(in_progress_projects[0])

    if completed_projects:
        showcase_projects.append(completed_projects[0])

    remaining_projects = [
        item for item in all_projects
        if item not in showcase_projects
    ]

    remaining_projects = sorted(
        remaining_projects,
        key=lambda item: -item["completion"]
    )

    all_projects = showcase_projects + remaining_projects

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

    # Overall dashboard health score
    health_score = 100

    # Delivery pressure
    health_score -= min(overdue_tasks * 4, 20)
    health_score -= min(blocked_tasks * 3, 20)

    # Governance pressure
    health_score -= min(open_risks * 1, 20)
    health_score -= min(open_issues * 1, 15)

    # Financial pressure
    health_score -= min(over_budget_projects * 5, 15)

    # Completion pressure
    if total_tasks > 0 and completion_rate < 30:
        health_score -= 10

    health_score = max(0, min(100, health_score))

    if health_score >= 80:
        health_status = "Excellent"
    elif health_score >= 60:
        health_status = "Stable"
    elif health_score >= 40:
        health_status = "At Risk"
    else:
        health_status = "Critical"

    portfolio_heatmap = []

    for item in all_projects:

        score = item["project_health_score"]

        if score >= 80:
            heatmap_status = "Green"
        elif score >= 50:
            heatmap_status = "Amber"
        else:
            heatmap_status = "Red"

        portfolio_heatmap.append({
            "project_name": item["project"][1],
            "score": score,
            "status": heatmap_status
        })

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
        portfolio_heatmap=portfolio_heatmap,
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

    if not has_permission("Tasks", "view"):
        return "Access denied"

    selected_project = request.args.get("project_id", "")
    selected_team = request.args.get("team_member", "")
    selected_priority = request.args.get("priority", "")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    query = """
        SELECT
            tasks.*,
            projects.name AS project_name
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
    """

    params = [session["user_id"]]

    if selected_project:
        query += " AND tasks.project_id = %s"
        params.append(selected_project)

    if selected_priority:
        query += " AND tasks.priority = %s"
        params.append(selected_priority)

    query += " ORDER BY tasks.id DESC"

    cursor.execute(query, params)

    tasks = cursor.fetchall()

    cursor.execute("""
        SELECT id,name
        FROM projects
        WHERE user_id = %s
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    cursor.execute("""
        SELECT id,name
        FROM team_members
        WHERE user_id = %s
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    all_team_members = cursor.fetchall()

    grouped_tasks = {
        "Pending": [],
        "In Progress": [],
        "Completed": [],
        "Blocked": []
    }

    wip_limits = {
        "Pending": 20,
        "In Progress": 10,
        "Completed": 999,
        "Blocked": 5
    }

    for task in tasks:

        cursor.execute("""
            SELECT
                team_members.id,
                team_members.name,
                team_members.role
            FROM task_team_members
            JOIN team_members
            ON task_team_members.team_member_id = team_members.id
            WHERE task_team_members.task_id = %s
        """, (
            task["id"],
        ))

        members = cursor.fetchall()

        team_members = []

        member_ids = []

        for member in members:

            member_ids.append(str(member["id"]))

            if member["role"]:
                team_members.append(
                    f"{member['name']} - {member['role']}"
                )
            else:
                team_members.append(
                    member["name"]
                )

        if selected_team:

            if selected_team not in member_ids:
                continue

        swimlane = "Unassigned"

        if team_members:

            swimlane = team_members[0]

        elif task["assigned_to"]:

            swimlane = task["assigned_to"]

        task_data = {
            "task": task,
            "team_members": team_members,
            "swimlane": swimlane
        }

        status = task["status"]

        if status in grouped_tasks:
            grouped_tasks[status].append(task_data)

    conn.close()

    return render_template(
        "kanban.html",
        grouped_tasks=grouped_tasks,
        projects=projects,
        all_team_members=all_team_members,
        selected_project=selected_project,
        selected_team=selected_team,
        selected_priority=selected_priority,
        wip_limits=wip_limits
    )


@app.route("/update-task-status", methods=["POST"])
def update_task_status():

    if "user_id" not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    if not has_permission("Tasks", "edit"):
        return jsonify({"success": False, "message": "Access denied"}), 403

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

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tasks
        SET status = %s
        WHERE id = %s
        AND project_id IN (
            SELECT id
            FROM projects
            WHERE user_id = %s
        )
    """, (
        new_status,
        task_id,
        session["user_id"]
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

    if not has_permission("Tasks", "view"):
        return "Access denied"

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

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY id DESC
    """, (session["user_id"],))
    projects = cursor.fetchall()

    cursor.execute("""
        SELECT
            tasks.*,
            projects.name AS project_name
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        ORDER BY
            CASE
                WHEN tasks.due_date IS NULL OR tasks.due_date = '' THEN 1
                ELSE 0
            END,
            tasks.due_date ASC
    """, (session["user_id"],))
    tasks = cursor.fetchall()

    cursor.execute("SELECT * FROM risks WHERE user_id = %s", (session["user_id"],))
    risks = cursor.fetchall()

    cursor.execute("SELECT * FROM issues WHERE user_id = %s", (session["user_id"],))
    issues = cursor.fetchall()

    cursor.execute("SELECT * FROM changes WHERE user_id = %s", (session["user_id"],))
    changes = cursor.fetchall()

    conn.close()

    total_tasks = len(tasks)
    completed_tasks = len([task for task in tasks if task["status"] == "Completed"])
    overdue_tasks = len([task for task in tasks if is_overdue(task["due_date"], task["status"])])
    active_projects = len([project for project in projects if project["status"] != "Completed"])

    completion_rate = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    open_risks = len(risks)
    open_issues = len(issues)
    open_changes = len(changes)

    delivery_confidence = max(
        0,
        min(
            100,
            completion_rate
            - (overdue_tasks * 2)
            - (open_risks * 1)
            - (open_issues * 1)
        )
    )

    if delivery_confidence >= 75:
        executive_summary = (
            f"Portfolio delivery confidence is strong at {delivery_confidence}%. "
            f"The portfolio contains {len(projects)} projects and {total_tasks} tasks, "
            f"with {completion_rate}% completion and {overdue_tasks} overdue tasks."
        )
    elif delivery_confidence >= 50:
        executive_summary = (
            f"Portfolio delivery confidence is moderate at {delivery_confidence}%. "
            f"Leadership should monitor {open_risks} risks, {open_issues} issues, "
            f"and {overdue_tasks} overdue tasks."
        )
    else:
        executive_summary = (
            f"Portfolio delivery confidence is low at {delivery_confidence}%. "
            f"Immediate management attention is recommended due to governance pressure, "
            f"open risks, issues and overdue delivery items."
        )

    return render_template(
        "report.html",
        projects=projects,
        tasks=tasks,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        completion_rate=completion_rate,
        active_projects=active_projects,
        open_risks=open_risks,
        open_issues=open_issues,
        open_changes=open_changes,
        delivery_confidence=delivery_confidence,
        executive_summary=executive_summary,
        current_date=str(date.today())
    )


@app.route("/pdf-report")
@app.route("/export-report")
def pdf_report():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT * FROM projects WHERE user_id = %s ORDER BY id DESC", (session["user_id"],))
    projects = cursor.fetchall()

    cursor.execute("""
        SELECT tasks.*, projects.name AS project_name
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        ORDER BY tasks.id DESC
    """, (session["user_id"],))
    tasks = cursor.fetchall()

    cursor.execute("SELECT * FROM risks WHERE user_id = %s", (session["user_id"],))
    risks = cursor.fetchall()

    cursor.execute("SELECT * FROM issues WHERE user_id = %s", (session["user_id"],))
    issues = cursor.fetchall()

    cursor.execute("SELECT * FROM changes WHERE user_id = %s", (session["user_id"],))
    changes = cursor.fetchall()

    conn.close()

    total_projects = len(projects)
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t["status"] == "Completed"])
    pending_tasks = len([t for t in tasks if t["status"] == "Pending"])
    overdue_tasks = len([t for t in tasks if is_overdue(t["due_date"], t["status"])])

    open_risks = len(risks)
    open_issues = len(issues)
    open_changes = len(changes)

    completion_rate = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    delivery_confidence = max(
        0,
        min(
            100,
            completion_rate
            - (overdue_tasks * 2)
            - open_risks
            - open_issues
        )
    )

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 50

    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(50, y, "AI PM Tracker Executive Report")

    y -= 30

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Generated: {date.today()}")

    y -= 45

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "Executive Summary")

    y -= 25
    pdf.setFont("Helvetica", 11)

    summary_lines = [
        f"Portfolio contains {total_projects} projects and {total_tasks} tasks.",
        f"Completion rate is {completion_rate}% with {overdue_tasks} overdue task(s).",
        f"Governance pressure includes {open_risks} risks, {open_issues} issues and {open_changes} changes.",
        f"Delivery confidence score is {delivery_confidence}%."
    ]

    for line in summary_lines:
        pdf.drawString(50, y, line)
        y -= 18

    y -= 25

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "Delivery Health")

    y -= 25
    pdf.setFont("Helvetica", 11)

    delivery_lines = [
        f"Completed Tasks: {completed_tasks}",
        f"Pending Tasks: {pending_tasks}",
        f"Overdue Tasks: {overdue_tasks}",
        f"Completion Rate: {completion_rate}%"
    ]

    for line in delivery_lines:
        pdf.drawString(50, y, line)
        y -= 18

    y -= 25

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "Governance Summary")

    y -= 25
    pdf.setFont("Helvetica", 11)

    governance_lines = [
        f"Open Risks: {open_risks}",
        f"Open Issues: {open_issues}",
        f"Open Changes: {open_changes}"
    ]

    for line in governance_lines:
        pdf.drawString(50, y, line)
        y -= 18

    y -= 25

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "Project Portfolio")

    y -= 25
    pdf.setFont("Helvetica", 10)

    for project in projects:

        if y < 80:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 10)

        pdf.drawString(
            60,
            y,
            f"{project['name']} | Status: {project['status']}"
        )

        y -= 18

    y -= 20

    if y < 120:
        pdf.showPage()
        y = height - 50

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "Upcoming / Recent Tasks")

    y -= 25
    pdf.setFont("Helvetica", 10)

    for task in tasks[:15]:

        if y < 80:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 10)

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
            "Content-Disposition": "attachment; filename=executive_project_report.pdf"
        }
    )


@app.route("/portfolio-pdf-report")
def portfolio_pdf_report():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT COUNT(*) AS total_projects FROM projects WHERE user_id = %s", (session["user_id"],))
    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("SELECT COUNT(*) AS total_risks FROM risks WHERE user_id = %s", (session["user_id"],))
    total_risks = cursor.fetchone()["total_risks"]

    cursor.execute("SELECT COUNT(*) AS total_issues FROM issues WHERE user_id = %s", (session["user_id"],))
    total_issues = cursor.fetchone()["total_issues"]

    cursor.execute("SELECT COUNT(*) AS total_changes FROM changes WHERE user_id = %s", (session["user_id"],))
    total_changes = cursor.fetchone()["total_changes"]

    cursor.execute("""
        SELECT *
        FROM portfolio_health
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (session["user_id"],))
    latest_health = cursor.fetchone()

    cursor.execute("""
        SELECT project_prioritisation.*, projects.name AS project_name
        FROM project_prioritisation
        LEFT JOIN projects ON project_prioritisation.project_id = projects.id
        WHERE project_prioritisation.user_id = %s
        ORDER BY project_prioritisation.priority_score DESC
        LIMIT 5
    """, (session["user_id"],))
    top_priorities = cursor.fetchall()

    conn.close()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "AI PM Tracker - Portfolio Report")

    y -= 30
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Generated: {date.today()}")

    y -= 40
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Portfolio Summary")

    y -= 25
    pdf.setFont("Helvetica", 11)

    for line in [
        f"Total Projects: {total_projects}",
        f"Total Risks: {total_risks}",
        f"Total Issues: {total_issues}",
        f"Total Changes: {total_changes}"
    ]:
        pdf.drawString(50, y, line)
        y -= 20

    y -= 25
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Latest Portfolio Health")

    y -= 25
    pdf.setFont("Helvetica", 11)

    if latest_health:
        health_lines = [
            f"Health Score: {latest_health['health_score']}%",
            f"Risk Exposure: {latest_health['risk_exposure']}%",
            f"Financial Health: {latest_health['financial_health']}%",
            f"Performance Score: {latest_health['performance_score']}%",
            f"Trend: {latest_health['trend']}"
        ]

        for line in health_lines:
            pdf.drawString(50, y, line)
            y -= 20
    else:
        pdf.drawString(50, y, "No portfolio health record found.")
        y -= 20

    y -= 25
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Top Priority Projects")

    y -= 25
    pdf.setFont("Helvetica", 11)

    if top_priorities:
        rank = 1

        for item in top_priorities:

            if y < 80:
                pdf.showPage()
                y = height - 50
                pdf.setFont("Helvetica", 11)

            pdf.drawString(
                50,
                y,
                f"#{rank} {item['project_name'] or 'No Project'} - Priority Score: {item['priority_score']}"
            )

            y -= 20
            rank += 1
    else:
        pdf.drawString(50, y, "No project prioritisation records found.")

    pdf.save()
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=portfolio_report.pdf"

    return response


@app.route("/executive-charts")
def executive_charts():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT COUNT(*) AS total_projects FROM projects WHERE user_id = %s", (session["user_id"],))
    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("SELECT COUNT(*) AS total_tasks FROM tasks JOIN projects ON tasks.project_id = projects.id WHERE projects.user_id = %s", (session["user_id"],))
    total_tasks = cursor.fetchone()["total_tasks"]

    cursor.execute("SELECT COUNT(*) AS completed_tasks FROM tasks JOIN projects ON tasks.project_id = projects.id WHERE projects.user_id = %s AND tasks.status = 'Completed'", (session["user_id"],))
    completed_tasks = cursor.fetchone()["completed_tasks"]

    cursor.execute("SELECT COUNT(*) AS total_risks FROM risks WHERE user_id = %s", (session["user_id"],))
    total_risks = cursor.fetchone()["total_risks"]

    cursor.execute("SELECT COUNT(*) AS total_issues FROM issues WHERE user_id = %s", (session["user_id"],))
    total_issues = cursor.fetchone()["total_issues"]

    cursor.execute("SELECT COUNT(*) AS total_changes FROM changes WHERE user_id = %s", (session["user_id"],))
    total_changes = cursor.fetchone()["total_changes"]

    cursor.execute("""
                   SELECT COALESCE(SUM(budget_amount), 0) AS total_budget,
                          COALESCE(SUM(actual_cost), 0)   AS total_actual,
                          COALESCE(SUM(forecast_cost), 0) AS total_forecast
                   FROM budgets
                   WHERE user_id = %s
                   """, (
                       session["user_id"],
                   ))

    financials = cursor.fetchone()

    conn.close()

    completion_rate = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    governance_pressure_score = min(
        100,
        (total_risks * 2) + (total_issues * 2) + total_changes
    )

    risk_exposure = min(100, total_risks * 3)

    total_budget = float(financials["total_budget"] or 0)
    total_actual = float(financials["total_actual"] or 0)

    if total_budget > 0:
        financial_health = max(
            0,
            min(100, round((1 - (total_actual / total_budget)) * 100))
        )
    else:
        financial_health = 75

    performance_score = max(
        0,
        min(
            100,
            round(
                (completion_rate * 0.6)
                + ((100 - governance_pressure_score) * 0.25)
                + (financial_health * 0.15)
            )
        )
    )

    health_score = max(
        0,
        min(
            100,
            round(
                (performance_score * 0.5)
                + (financial_health * 0.25)
                + ((100 - risk_exposure) * 0.25)
            )
        )
    )

    if governance_pressure_score >= 80:
        governance_severity = "Critical"
        governance_commentary = "Governance pressure is critical and requires leadership intervention."
    elif governance_pressure_score >= 60:
        governance_severity = "High"
        governance_commentary = "Governance pressure is high and should be reviewed by senior management."
    elif governance_pressure_score >= 30:
        governance_severity = "Medium"
        governance_commentary = "Governance pressure is moderate and should be monitored."
    else:
        governance_severity = "Low"
        governance_commentary = "Governance pressure is currently low."

    if health_score >= 75:
        executive_commentary = (
            "Portfolio is broadly healthy. Delivery performance, financial position "
            "and governance exposure are within an acceptable range."
        )
    elif health_score >= 50:
        executive_commentary = (
            "Portfolio health is moderate. Leadership should review open risks, issues, "
            "changes and delivery confidence."
        )
    else:
        executive_commentary = (
            "Portfolio health is weak. Immediate executive attention is recommended."
        )

    score_explanations = {
        "health_score": "Health Score combines performance, financial health and risk exposure.",
        "risk_exposure": "Risk Exposure is based on the number of open risks.",
        "financial_health": "Financial Health compares total budget against actual cost.",
        "performance_score": "Performance Score combines completion rate, governance pressure and financial health.",
        "governance_pressure": "Governance Pressure combines risks, issues and changes."
    }

    latest_health = {
        "health_score": health_score,
        "risk_exposure": risk_exposure,
        "financial_health": financial_health,
        "performance_score": performance_score,
        "trend": "Calculated"
    }

    return render_template(
        "executive_charts.html",
        total_projects={"total_projects": total_projects},
        total_risks={"total_risks": total_risks},
        total_issues={"total_issues": total_issues},
        total_changes={"total_changes": total_changes},
        latest_health=latest_health,
        completion_rate=completion_rate,
        governance_pressure_score=governance_pressure_score,
        governance_severity=governance_severity,
        governance_commentary=governance_commentary,
        executive_commentary=executive_commentary,
        score_explanations=score_explanations
    )


@app.route("/insights")
@app.route("/ai-insights")
def ai_insights():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

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
        ORDER BY tasks.id DESC
    """, (
        session["user_id"],
    ))

    tasks = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS total_risks
        FROM risks
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_risks = cursor.fetchone()["total_risks"]

    cursor.execute("""
        SELECT COUNT(*) AS total_issues
        FROM issues
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_issues = cursor.fetchone()["total_issues"]

    cursor.execute("""
        SELECT
            COALESCE(SUM(budget_amount), 0) AS total_budget,
            COALESCE(SUM(actual_cost), 0) AS total_actual_cost,
            COALESCE(SUM(forecast_cost), 0) AS total_forecast_cost
        FROM budgets
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    budget_data = cursor.fetchone()

    conn.close()

    total = len(tasks)

    completed = len([
        task for task in tasks
        if task["status"] == "Completed"
    ])

    in_progress = len([
        task for task in tasks
        if task["status"] == "In Progress"
    ])

    pending = len([
        task for task in tasks
        if task["status"] == "Pending"
    ])

    blocked = len([
        task for task in tasks
        if task["status"] == "Blocked"
    ])

    high_priority = len([
        task for task in tasks
        if task["priority"] == "High"
        and task["status"] != "Completed"
    ])

    overdue = len([
        task for task in tasks
        if is_overdue(
            task["due_date"],
            task["status"]
        )
    ])

    if total > 0:
        completion_rate = round((completed / total) * 100)
        blocked_rate = round((blocked / total) * 100)
        overdue_rate = round((overdue / total) * 100)
        high_priority_rate = round((high_priority / total) * 100)
    else:
        completion_rate = 0
        blocked_rate = 0
        overdue_rate = 0
        high_priority_rate = 0

    total_budget = float(budget_data["total_budget"] or 0)
    total_actual_cost = float(budget_data["total_actual_cost"] or 0)
    total_forecast_cost = float(budget_data["total_forecast_cost"] or 0)

    if total_budget > 0:
        budget_usage = round((total_actual_cost / total_budget) * 100)
        forecast_usage = round((total_forecast_cost / total_budget) * 100)
    else:
        budget_usage = 0
        forecast_usage = 0

    delivery_health_score = max(
        0,
        min(
            100,
            completion_rate
            - overdue_rate
            - blocked_rate
            - round(high_priority_rate / 2)
        )
    )

    risk_pressure_score = min(
        100,
        (total_risks * 2) + (total_issues * 2) + blocked
    )

    if delivery_health_score >= 75:
        delivery_status = "Healthy"
    elif delivery_health_score >= 50:
        delivery_status = "Monitor"
    else:
        delivery_status = "At Risk"

    if risk_pressure_score >= 70:
        risk_status = "High"
    elif risk_pressure_score >= 35:
        risk_status = "Medium"
    else:
        risk_status = "Low"

    insights_list = []

    if total == 0:
        insights_list.append(
            "No task data is available yet. Add tasks to generate meaningful AI insights."
        )

    if completion_rate < 30 and total > 0:
        insights_list.append(
            f"Completion rate is low at {completion_rate}%. Review delivery blockers and task ownership."
        )

    if high_priority > 0:
        insights_list.append(
            f"There are {high_priority} open high-priority task(s). These should be reviewed first."
        )

    if overdue > 0:
        insights_list.append(
            f"There are {overdue} overdue task(s). Deadline review is recommended."
        )

    if blocked > 0:
        insights_list.append(
            f"{blocked} task(s) are blocked. Escalation or dependency review may be required."
        )

    if total_risks > 0:
        insights_list.append(
            f"There are {total_risks} open risk(s). Risk ownership and mitigation should be checked."
        )

    if total_issues > 0:
        insights_list.append(
            f"There are {total_issues} open issue(s). Active resolution tracking is recommended."
        )

    if budget_usage > 90:
        insights_list.append(
            f"Budget usage is high at {budget_usage}%. Financial control should be reviewed."
        )
    elif forecast_usage > 90:
        insights_list.append(
            f"Forecast usage is high at {forecast_usage}%. Cost forecasting should be reviewed."
        )

    if (
        total > 0
        and overdue == 0
        and blocked == 0
        and risk_pressure_score < 35
    ):
        insights_list.append(
            "Portfolio delivery appears stable based on current task, risk and issue data."
        )

    ai_explanations = [
        "Delivery Health Score uses completion rate, overdue rate, blocked rate and high-priority workload.",
        "Risk Pressure Score uses open risks, open issues and blocked tasks.",
        "Budget Usage compares actual cost against approved budget.",
        "Forecast Usage compares forecast cost against approved budget.",
        "Recommendations are rule-based at this milestone and will become more predictive later."
    ]

    anomaly_flags = []

    if total > 0 and overdue == 0 and completion_rate < 30:
        anomaly_flags.append(
            "Completion is low but overdue tasks are zero. Check whether due dates are missing."
        )

    if high_priority > total * 0.4 and total > 0:
        anomaly_flags.append(
            "High-priority workload is unusually high. Priority classifications may need review."
        )

    if total_projects > 0 and total == 0:
        anomaly_flags.append(
            "Projects exist but no tasks are linked. Project delivery metrics may be incomplete."
        )

    if total_budget > 0 and total_actual_cost == 0:
        anomaly_flags.append(
            "Budget exists but actual cost is zero. Financial data may be incomplete."
        )

    trend_notes = [
        "Trend analysis will compare current metrics against future historical snapshots.",
        "Forecast charts will be added once reporting history is captured.",
        "Portfolio heatmaps will use project, risk, issue and budget data."
    ]

    return render_template(
        "ai_insights.html",
        insights=insights_list,
        ai_explanations=ai_explanations,
        anomaly_flags=anomaly_flags,
        trend_notes=trend_notes,
        total_projects=total_projects,
        total=total,
        completed=completed,
        in_progress=in_progress,
        pending=pending,
        blocked=blocked,
        overdue=overdue,
        high_priority=high_priority,
        completion_rate=completion_rate,
        blocked_rate=blocked_rate,
        overdue_rate=overdue_rate,
        high_priority_rate=high_priority_rate,
        total_risks=total_risks,
        total_issues=total_issues,
        total_budget=total_budget,
        total_actual_cost=total_actual_cost,
        total_forecast_cost=total_forecast_cost,
        budget_usage=budget_usage,
        forecast_usage=forecast_usage,
        delivery_health_score=delivery_health_score,
        risk_pressure_score=risk_pressure_score,
        delivery_status=delivery_status,
        risk_status=risk_status
    )


@app.route("/export-tasks")
def export_tasks():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            tasks.title,
            tasks.priority,
            tasks.status,
            tasks.due_date,
            tasks.assigned_to,
            tasks.attachment_url,
            projects.name AS project_name
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
    """, (
        session["user_id"],
    ))

    tasks = cursor.fetchall()

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

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    if request.method == "POST":

        cursor.execute("""
            UPDATE users
            SET
                avatar_initials = %s,
                timezone = %s,
                language = %s,
                theme_preference = %s,
                notifications_enabled = %s
            WHERE id = %s
        """, (
            request.form.get("avatar_initials"),
            request.form.get("timezone"),
            request.form.get("language"),
            request.form.get("theme_preference"),
            request.form.get("notifications_enabled"),
            session["user_id"]
        ))

        conn.commit()

        session["avatar_initials"] = (
            request.form.get("avatar_initials")
        )

        return redirect("/profile")

    cursor.execute("""
        SELECT *
        FROM users
        WHERE id = %s
    """, (
        session["user_id"],
    ))

    user = cursor.fetchone()

    profile_score = 0

    fields = [
        user.get("username"),
        user.get("email"),
        user.get("avatar_initials"),
        user.get("timezone"),
        user.get("language"),
        user.get("theme_preference")
    ]

    for field in fields:
        if field:
            profile_score += 15

    profile_score = min(profile_score, 100)

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        profile_score=profile_score
    )


@app.route("/project-comments/<int:project_id>", methods=["GET", "POST"])
def project_comments(project_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE id = %s
        AND user_id = %s
    """, (
        project_id,
        session["user_id"]
    ))

    project = cursor.fetchone()

    if not project:
        conn.close()
        return redirect("/")

    if request.method == "POST":

        if not has_permission("Projects", "edit"):
            conn.close()
            return "Access denied"

        comment = request.form["comment"]

        cursor.execute("""
            INSERT INTO comments
            (
                project_id,
                username,
                comment,
                created_at
            )
            VALUES (%s,%s,%s,%s)
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

    cursor.execute("""
        SELECT *
        FROM comments
        WHERE project_id = %s
        ORDER BY id DESC
    """, (
        project_id,
    ))

    comments = cursor.fetchall()

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

    if not has_permission("Tasks", "view"):
        return "Access denied"

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
    ))

    tasks = cursor.fetchall()

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

    if not has_permission("Projects", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE id = %s
        AND user_id = %s
    """, (
        project_id,
        session["user_id"]
    ))

    project = cursor.fetchone()

    if not project:
        conn.close()
        return redirect("/")

    cursor.execute("""
        SELECT *
        FROM tasks
        WHERE project_id = %s
        ORDER BY
            CASE
                WHEN due_date IS NULL OR due_date = '' THEN 1
                ELSE 0
            END,
            due_date ASC
    """, (
        project_id,
    ))

    tasks = cursor.fetchall()

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

    if not has_permission("Tasks", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
            tasks.*,
            projects.name AS project_name
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        ORDER BY tasks.id DESC
    """, (session["user_id"],))

    tasks = cursor.fetchall()

    all_tasks = []

    for task in tasks:

        cursor.execute("""
            SELECT
                team_members.name,
                team_members.role
            FROM task_team_members
            JOIN team_members
            ON task_team_members.team_member_id = team_members.id
            WHERE task_team_members.task_id = %s
        """, (task["id"],))

        members = cursor.fetchall()

        team_members = []

        for member in members:
            if member["role"]:
                team_members.append(f"{member['name']} - {member['role']}")
            else:
                team_members.append(member["name"])

        cursor.execute("""
            SELECT
                dependency_tasks.title AS dependency_title
            FROM task_dependencies
            JOIN tasks AS dependency_tasks
            ON task_dependencies.depends_on_task_id = dependency_tasks.id
            WHERE task_dependencies.task_id = %s
        """, (task["id"],))

        dependencies = cursor.fetchall()

        cursor.execute("""
            SELECT *
            FROM task_comments
            WHERE task_id = %s
            ORDER BY id DESC
            LIMIT 3
        """, (task["id"],))

        comments = cursor.fetchall()

        cursor.execute("""
            SELECT *
            FROM task_history
            WHERE task_id = %s
            ORDER BY id DESC
            LIMIT 3
        """, (task["id"],))

        history = cursor.fetchall()

        all_tasks.append({
            "task": task,
            "team_members": team_members,
            "dependencies": dependencies,
            "comments": comments,
            "history": history
        })

    conn.close()

    return render_template(
        "tasks.html",
        all_tasks=all_tasks
    )

@app.route("/add-task", methods=["GET", "POST"])
def add_task():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Tasks", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (session["user_id"],))

    projects = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name ASC
    """, (session["user_id"],))

    team_members = cursor.fetchall()

    cursor.execute("""
        SELECT
            tasks.*,
            projects.name AS project_name
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        ORDER BY tasks.title ASC
    """, (session["user_id"],))

    existing_tasks = cursor.fetchall()

    if request.method == "POST":

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        assigned_to = request.form.get("assigned_to", "")
        priority = request.form.get("priority", "Medium")
        status = request.form.get("status", "Pending")
        due_date = request.form.get("due_date", "")

        selected_team_members = request.form.getlist("team_member_ids")
        selected_dependencies = request.form.getlist("depends_on_task_ids")

        estimated_hours = float(request.form.get("estimated_hours", 0) or 0)
        actual_hours = float(request.form.get("actual_hours", 0) or 0)
        hourly_rate = float(request.form.get("hourly_rate", 0) or 0)

        attachment_name = request.form.get("attachment_name", "")
        attachment_url = request.form.get("attachment_url", "")
        acceptance_criteria = request.form.get("acceptance_criteria", "")
        checklist = request.form.get("checklist", "")
        is_recurring = True if request.form.get("is_recurring") == "on" else False
        recurring_frequency = request.form.get("recurring_frequency", "")

        cursor.execute("""
            INSERT INTO tasks
            (
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
                attachment_name,
                attachment_url,
                acceptance_criteria,
                checklist,
                is_recurring,
                recurring_frequency,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
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
            attachment_name,
            attachment_url,
            acceptance_criteria,
            checklist,
            is_recurring,
            recurring_frequency,
            str(date.today())
        ))

        task_id = cursor.fetchone()["id"]

        for member_id in selected_team_members:
            cursor.execute("""
                INSERT INTO task_team_members
                (
                    task_id,
                    team_member_id
                )
                VALUES (%s,%s)
            """, (
                task_id,
                member_id
            ))

        for dependency_id in selected_dependencies:
            cursor.execute("""
                INSERT INTO task_dependencies
                (
                    task_id,
                    depends_on_task_id,
                    created_at
                )
                VALUES (%s,%s,%s)
            """, (
                task_id,
                dependency_id,
                str(date.today())
            ))

        cursor.execute("""
            INSERT INTO task_history
            (
                task_id,
                user_id,
                action,
                created_at
            )
            VALUES (%s,%s,%s,%s)
        """, (
            task_id,
            session["user_id"],
            "Task created",
            str(date.today())
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
        team_members=team_members,
        existing_tasks=existing_tasks
    )

@app.route("/edit-task/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Tasks", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
                   SELECT tasks.*
                   FROM tasks
                            JOIN projects
                                 ON tasks.project_id = projects.id
                   WHERE tasks.id = %s
                     AND projects.user_id = %s
                   """, (
                       task_id,
                       session["user_id"]
                   ))

    task = cursor.fetchone()

    if not task:
        conn.close()
        return redirect("/tasks")

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (session["user_id"],))

    projects = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name ASC
    """, (session["user_id"],))

    team_members = cursor.fetchall()

    cursor.execute("""
                   SELECT tasks.*,
                          projects.name AS project_name
                   FROM tasks
                            JOIN projects
                                 ON tasks.project_id = projects.id
                   WHERE projects.user_id = %s
                     AND tasks.project_id = %s
                     AND tasks.id != %s
                   ORDER BY tasks.title ASC
                   """, (
                       session["user_id"],
                       task["project_id"],
                       task_id
                   ))

    existing_tasks = cursor.fetchall()

    cursor.execute("""
        SELECT team_member_id
        FROM task_team_members
        WHERE task_id = %s
    """, (task_id,))

    selected_members = cursor.fetchall()

    selected_member_ids = [
        member["team_member_id"]
        for member in selected_members
    ]

    cursor.execute("""
        SELECT depends_on_task_id
        FROM task_dependencies
        WHERE task_id = %s
    """, (task_id,))

    selected_dependencies = cursor.fetchall()

    selected_dependency_ids = [
        dependency["depends_on_task_id"]
        for dependency in selected_dependencies
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
        selected_dependencies = request.form.getlist("depends_on_task_ids")

        estimated_hours = float(request.form.get("estimated_hours", 0) or 0)
        actual_hours = float(request.form.get("actual_hours", 0) or 0)
        hourly_rate = float(request.form.get("hourly_rate", 0) or 0)

        attachment_name = request.form.get("attachment_name", "")
        attachment_url = request.form.get("attachment_url", "")
        acceptance_criteria = request.form.get("acceptance_criteria", "")
        checklist = request.form.get("checklist", "")
        is_recurring = True if request.form.get("is_recurring") == "on" else False
        recurring_frequency = request.form.get("recurring_frequency", "")

        cursor.execute("""
            UPDATE tasks
            SET
                project_id = %s,
                title = %s,
                description = %s,
                assigned_to = %s,
                priority = %s,
                status = %s,
                due_date = %s,
                estimated_hours = %s,
                actual_hours = %s,
                hourly_rate = %s,
                attachment_name = %s,
                attachment_url = %s,
                acceptance_criteria = %s,
                checklist = %s,
                is_recurring = %s,
                recurring_frequency = %s
            WHERE id = %s
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
            attachment_name,
            attachment_url,
            acceptance_criteria,
            checklist,
            is_recurring,
            recurring_frequency,
            task_id
        ))

        cursor.execute("""
            DELETE FROM task_team_members
            WHERE task_id = %s
        """, (task_id,))

        for member_id in selected_team_members:
            cursor.execute("""
                INSERT INTO task_team_members
                (
                    task_id,
                    team_member_id
                )
                VALUES (%s,%s)
            """, (
                task_id,
                member_id
            ))

        cursor.execute("""
            DELETE FROM task_dependencies
            WHERE task_id = %s
        """, (task_id,))

        for dependency_id in selected_dependencies:
            cursor.execute("""
                INSERT INTO task_dependencies
                (
                    task_id,
                    depends_on_task_id,
                    created_at
                )
                VALUES (%s,%s,%s)
            """, (
                task_id,
                dependency_id,
                str(date.today())
            ))

        cursor.execute("""
            INSERT INTO task_history
            (
                task_id,
                user_id,
                action,
                created_at
            )
            VALUES (%s,%s,%s,%s)
        """, (
            task_id,
            session["user_id"],
            "Task updated",
            str(date.today())
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
        existing_tasks=existing_tasks,
        selected_member_ids=selected_member_ids,
        selected_dependency_ids=selected_dependency_ids
    )



@app.route("/delete-task/<int:task_id>", methods=["POST"])
def delete_task(task_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Tasks", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
            tasks.*
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE tasks.id = %s
        AND projects.user_id = %s
    """, (
        task_id,
        session["user_id"]
    ))

    task = cursor.fetchone()

    cursor.execute("""
        DELETE FROM task_team_members
        WHERE task_id = %s
    """, (task_id,))

    cursor.execute("""
        DELETE FROM tasks
        WHERE id = %s
    """, (task_id,))

    conn.commit()
    conn.close()

    if task:
        create_activity(
            f"{session.get('username', 'User')} deleted task {task['title']}"
        )

    return redirect("/tasks")

@app.route("/add-task-comment/<int:task_id>", methods=["POST"])
def add_task_comment(task_id):

    if "user_id" not in session:
        return redirect("/login")

    comment = request.form.get("comment", "").strip()

    if comment:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO task_comments
            (
                task_id,
                user_id,
                comment,
                created_at
            )
            VALUES (%s,%s,%s,%s)
        """, (
            task_id,
            session["user_id"],
            comment,
            str(date.today())
        ))

        cursor.execute("""
            INSERT INTO task_history
            (
                task_id,
                user_id,
                action,
                created_at
            )
            VALUES (%s,%s,%s,%s)
        """, (
            task_id,
            session["user_id"],
            "Comment added",
            str(date.today())
        ))

        conn.commit()
        conn.close()

    return redirect("/tasks")

@app.route("/bulk-update-tasks", methods=["POST"])
def bulk_update_tasks():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Tasks", "edit"):
        return "Access denied"

    selected_tasks = request.form.getlist("task_ids")
    bulk_action = request.form.get("bulk_action")

    if not selected_tasks:
        return redirect("/tasks")

    conn = get_db_connection()
    cursor = conn.cursor()

    for task_id in selected_tasks:

        if bulk_action == "complete":
            cursor.execute("""
                UPDATE tasks
                SET status = 'Completed'
                WHERE id = %s
                AND project_id IN (
                    SELECT id FROM projects WHERE user_id = %s
                )
            """, (
                task_id,
                session["user_id"]
            ))

            history_action = "Task marked as completed"

        elif bulk_action == "in_progress":
            cursor.execute("""
                UPDATE tasks
                SET status = 'In Progress'
                WHERE id = %s
                AND project_id IN (
                    SELECT id FROM projects WHERE user_id = %s
                )
            """, (
                task_id,
                session["user_id"]
            ))

            history_action = "Task moved to in progress"

        elif bulk_action == "blocked":
            cursor.execute("""
                UPDATE tasks
                SET status = 'Blocked'
                WHERE id = %s
                AND project_id IN (
                    SELECT id FROM projects WHERE user_id = %s
                )
            """, (
                task_id,
                session["user_id"]
            ))

            history_action = "Task marked as blocked"

        elif bulk_action == "delete":
            cursor.execute("""
                DELETE FROM tasks
                WHERE id = %s
                AND project_id IN (
                    SELECT id FROM projects WHERE user_id = %s
                )
            """, (
                task_id,
                session["user_id"]
            ))

            history_action = "Task deleted by bulk action"

        else:
            continue

        if bulk_action != "delete":
            cursor.execute("""
                INSERT INTO task_history
                (
                    task_id,
                    user_id,
                    action,
                    created_at
                )
                VALUES (%s,%s,%s,%s)
            """, (
                task_id,
                session["user_id"],
                history_action,
                str(date.today())
            ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} performed a bulk task update"
    )

    return redirect("/tasks")


@app.route("/add-project", methods=["GET", "POST"])
def add_project():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "create"):
        return "Access denied"

    if not can_create_project():

        return """
        <h2>Plan Limit Reached</h2>

        <p>
            You have reached the maximum number of projects
            allowed by your subscription plan.
        </p>

        <p>
            Please upgrade your plan to create more projects.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM clients
        WHERE user_id = %s
        ORDER BY name ASC
    """, (session["user_id"],))

    clients = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name ASC
    """, (session["user_id"],))

    team_members = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM stakeholders
        WHERE user_id = %s
        ORDER BY name ASC
    """, (session["user_id"],))

    stakeholders = cursor.fetchall()

    if request.method == "POST":

        name = request.form.get("name", "")
        description = request.form.get("description", "")
        status = request.form.get("status", "Planning")
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        client_id = request.form.get("client_id")

        project_manager_id = request.form.get("project_manager_id")
        sponsor_id = request.form.get("sponsor_id")
        project_type = request.form.get("project_type", "")
        programme = request.form.get("programme", "")
        portfolio = request.form.get("portfolio", "")

        business_case = request.form.get("business_case", "")
        project_priority = request.form.get("project_priority", "Medium")
        risk_rating = request.form.get("risk_rating", "Medium")
        governance_category = request.form.get("governance_category", "Standard")

        estimated_budget = float(request.form.get("estimated_budget", 0) or 0)
        actual_cost = float(request.form.get("actual_cost", 0) or 0)

        cursor.execute("""
                       INSERT INTO projects
                       (user_id,
                        client_id,
                        project_manager_id,
                        sponsor_id,
                        name,
                        description,
                        start_date,
                        end_date,
                        status,
                        project_type,
                        programme,
                        portfolio,
                        business_case,
                        project_priority,
                        risk_rating,
                        governance_category,
                        estimated_budget,
                        actual_cost,
                        is_archived,
                        created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, (
                           session["user_id"],
                           client_id if client_id else None,
                           project_manager_id if project_manager_id else None,
                           sponsor_id if sponsor_id else None,
                           name,
                           description,
                           start_date,
                           end_date,
                           status,
                           project_type,
                           programme,
                           portfolio,
                           business_case,
                           project_priority,
                           risk_rating,
                           governance_category,
                           estimated_budget,
                           actual_cost,
                           False,
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
        clients=clients,
        team_members=team_members,
        stakeholders=stakeholders
    )


@app.route("/edit-project/<int:project_id>", methods=["GET", "POST"])
def edit_project(project_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE id = %s
        AND user_id = %s
    """, (
        project_id,
        session["user_id"]
    ))

    project = cursor.fetchone()

    if not project:
        conn.close()
        return redirect("/")

    cursor.execute("""
        SELECT *
        FROM clients
        WHERE user_id = %s
        ORDER BY name ASC
    """, (session["user_id"],))

    clients = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name ASC
    """, (session["user_id"],))

    team_members = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM stakeholders
        WHERE user_id = %s
        ORDER BY name ASC
    """, (session["user_id"],))

    stakeholders = cursor.fetchall()

    if request.method == "POST":

        name = request.form.get("name", "")
        description = request.form.get("description", "")
        status = request.form.get("status", "Planning")
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        client_id = request.form.get("client_id")

        project_manager_id = request.form.get("project_manager_id")
        sponsor_id = request.form.get("sponsor_id")
        project_type = request.form.get("project_type", "")
        programme = request.form.get("programme", "")
        portfolio = request.form.get("portfolio", "")

        business_case = request.form.get("business_case", "")
        project_priority = request.form.get("project_priority", "Medium")
        risk_rating = request.form.get("risk_rating", "Medium")
        governance_category = request.form.get("governance_category", "Standard")

        estimated_budget = float(request.form.get("estimated_budget", 0) or 0)
        actual_cost = float(request.form.get("actual_cost", 0) or 0)

        cursor.execute("""
                       UPDATE projects
                       SET client_id           = %s,
                           project_manager_id  = %s,
                           sponsor_id          = %s,
                           name                = %s,
                           description         = %s,
                           start_date          = %s,
                           end_date            = %s,
                           status              = %s,
                           project_type        = %s,
                           programme           = %s,
                           portfolio           = %s,
                           business_case       = %s,
                           project_priority    = %s,
                           risk_rating         = %s,
                           governance_category = %s,
                           estimated_budget    = %s,
                           actual_cost         = %s
                       WHERE id = %s
                         AND user_id = %s
                       """, (
                           client_id if client_id else None,
                           project_manager_id if project_manager_id else None,
                           sponsor_id if sponsor_id else None,
                           name,
                           description,
                           start_date,
                           end_date,
                           status,
                           project_type,
                           programme,
                           portfolio,
                           business_case,
                           project_priority,
                           risk_rating,
                           governance_category,
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
        clients=clients,
        team_members=team_members,
        stakeholders=stakeholders
    )


@app.route("/delete-project/<int:project_id>", methods=["POST"])
def delete_project(project_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE id = %s
        AND user_id = %s
    """, (
        project_id,
        session["user_id"]
    ))

    project = cursor.fetchone()

    cursor.execute("""
        DELETE FROM tasks
        WHERE project_id = %s
    """, (project_id,))

    cursor.execute("""
        DELETE FROM projects
        WHERE id = %s
        AND user_id = %s
    """, (
        project_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    if project:
        create_activity(
            f"{session.get('username', 'User')} deleted project {project['name']}"
        )

    return redirect("/")

@app.route("/archive-project/<int:project_id>", methods=["POST"])
def archive_project(project_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE projects
        SET is_archived = TRUE
        WHERE id = %s
        AND user_id = %s
    """, (
        project_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} archived a project"
    )

    return redirect("/")


@app.route("/restore-project/<int:project_id>", methods=["POST"])
def restore_project(project_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE projects
        SET is_archived = FALSE
        WHERE id = %s
        AND user_id = %s
    """, (
        project_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} restored a project"
    )

    return redirect("/archived-projects")

@app.route("/archived-projects")
def archived_projects():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            projects.*,
            clients.name AS client_name,
            clients.company AS client_company,
            team_members.name AS project_manager_name,
            stakeholders.name AS sponsor_name
        FROM projects
        LEFT JOIN clients
        ON projects.client_id = clients.id
        LEFT JOIN team_members
        ON projects.project_manager_id = team_members.id
        LEFT JOIN stakeholders
        ON projects.sponsor_id = stakeholders.id
        WHERE projects.user_id = %s
        AND COALESCE(projects.is_archived, FALSE) = TRUE
        ORDER BY projects.id DESC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    conn.close()

    return render_template(
        "archived_projects.html",
        projects=projects
    )


@app.route("/register", methods=["GET", "POST"])
def register():

    error = None

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not password:
            error = "Username and password are required."
            return render_template(
                "register.html",
                error=error
            )

        conn = get_db_connection()

        cursor = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        cursor.execute("""
            SELECT id
            FROM users
            WHERE LOWER(username) = LOWER(%s)
            LIMIT 1
        """, (
            username,
        ))

        existing_username = cursor.fetchone()

        if existing_username:
            conn.close()
            error = "Username already exists."
            return render_template(
                "register.html",
                error=error
            )

        if email:

            cursor.execute("""
                SELECT id
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1
            """, (
                email,
            ))

            existing_email = cursor.fetchone()

            if existing_email:
                conn.close()
                error = "Email already exists."
                return render_template(
                    "register.html",
                    error=error
                )

        hashed_password = generate_password_hash(password)
        avatar_initials = username[:2].upper()
        verification_token = str(uuid.uuid4())

        try:

            cursor.execute("""
                INSERT INTO users
                (
                    username,
                    email,
                    password,
                    avatar_initials,
                    is_verified,
                    verification_token,
                    verification_token_created_at,
                    status,
                    created_at,
                    login_count,
                    failed_login_count
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                username,
                email,
                hashed_password,
                avatar_initials,
                False if email else True,
                verification_token if email else None,
                str(datetime.now()) if email else None,
                "Active",
                str(datetime.now()),
                0,
                0
            ))

            conn.commit()
            conn.close()

            if email:

                return f"""
                <h2>Account Created</h2>

                <p>Your account was created successfully.</p>

                <p>Please verify your email before logging in.</p>

                <p><strong>Verification Token:</strong> {verification_token}</p>

                <p>
                    <a href="/verify-email/{verification_token}">
                        Verify Email
                    </a>
                </p>
                """

            return redirect("/login")

        except Exception as e:

            conn.close()
            error = f"Registration failed: {str(e)}"

    return render_template(
        "register.html",
        error=error
    )

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()

        cursor = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        cursor.execute("""
            SELECT *
            FROM users
            WHERE LOWER(username) = LOWER(%s)
            LIMIT 1
        """, (
            username,
        ))

        user = cursor.fetchone()

        if user:

            stored_password = user["password"]

            password_valid = False

            try:

                password_valid = check_password_hash(
                    stored_password,
                    password
                )

            except Exception:

                password_valid = False

            if not password_valid and stored_password == password:

                password_valid = True

            if password_valid:

                if user.get("status") in [
                    "Inactive",
                    "Suspended"
                ]:

                    conn.close()

                    return """
                    <h2>Account Disabled</h2>
                    <p>Your account is inactive or suspended.</p>
                    """

                if (
                    user.get("email")
                    and user.get("is_verified") is False
                ):

                    conn.close()

                    return """
                    <h2>Email Not Verified</h2>
                    <p>Please verify your email before logging in.</p>
                    """

                cursor.execute("""
                    UPDATE users
                    SET
                        last_login = %s,
                        login_count = COALESCE(login_count, 0) + 1
                    WHERE id = %s
                """, (
                    str(datetime.now()),
                    user["id"]
                ))

                conn.commit()
                conn.close()

                session["user_id"] = user["id"]
                session["username"] = user["username"]

                session["avatar_initials"] = (
                    user["avatar_initials"]
                    or user["username"][:2].upper()
                )

                try:

                    create_activity(
                        f"{user['username']} logged in",
                        user_id=user["id"],
                        activity_type="Login",
                        module="Account",
                        severity="Low"
                    )

                except:

                    pass

                return redirect("/")

            else:

                cursor.execute("""
                    UPDATE users
                    SET
                        failed_login_count =
                        COALESCE(failed_login_count, 0) + 1
                    WHERE id = %s
                """, (
                    user["id"],
                ))

                conn.commit()

        conn.close()

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template(
        "login.html",
        error=None
    )


@app.route("/verify-email/<token>")
def verify_email(token):

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM users
        WHERE verification_token = %s
    """, (
        token,
    ))

    user = cursor.fetchone()

    if not user:
        conn.close()

        return """
        <h2>Invalid Verification Link</h2>
        <p>The verification token is invalid.</p>
        <p><a href="/login">Back to Login</a></p>
        """

    try:

        if user["verification_token_created_at"]:

            token_date = datetime.fromisoformat(
                str(user["verification_token_created_at"])
            )

            hours_passed = (
                datetime.now() - token_date
            ).total_seconds() / 3600

            if hours_passed > 24:

                conn.close()

                return """
                <h2>Verification Link Expired</h2>
                <p>Your verification link has expired.</p>
                <p>Please register again or request a new verification email.</p>
                """

    except Exception:
        pass

    cursor.execute("""
        UPDATE users
        SET
            is_verified = TRUE,
            verification_token = NULL,
            verification_token_created_at = NULL
        WHERE id = %s
    """, (
        user["id"],
    ))

    conn.commit()
    conn.close()

    try:

        create_activity(
            f"{user['username']} verified email",
            user_id=user["id"],
            activity_type="Verification",
            module="Account",
            severity="Low"
        )

    except:
        pass

    return """
    <h2>Email Verified</h2>

    <p>Your email has been verified successfully.</p>

    <p>
        <a href="/login">
            Go to Login
        </a>
    </p>
    """


@app.route("/accept-invitation/<token>", methods=["GET", "POST"])
def accept_invitation(token):

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM user_invitations
        WHERE invitation_token = %s
        AND status = 'Pending'
    """, (
        token,
    ))

    invitation = cursor.fetchone()

    if not invitation:
        conn.close()
        return """
        <h2>Invalid or Expired Invitation</h2>
        <p>This invitation is no longer valid.</p>
        <p><a href="/login">Back to Login</a></p>
        """

    if invitation.get("expiry_date"):

        try:
            expiry_date = datetime.strptime(
                str(invitation["expiry_date"]),
                "%Y-%m-%d"
            ).date()

            if date.today() > expiry_date:

                cursor.execute("""
                    UPDATE user_invitations
                    SET status = 'Expired'
                    WHERE id = %s
                """, (
                    invitation["id"],
                ))

                conn.commit()
                conn.close()

                return """
                <h2>Invitation Expired</h2>
                <p>This invitation has expired.</p>
                <p>Please contact your administrator for a new invitation.</p>
                """

        except Exception:
            pass

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            conn.close()
            return "Username and password are required"

        cursor.execute("""
            SELECT id
            FROM users
            WHERE LOWER(username) = LOWER(%s)
            LIMIT 1
        """, (
            username,
        ))

        existing_username = cursor.fetchone()

        if existing_username:
            conn.close()
            return "Username already exists"

        cursor.execute("""
            SELECT id
            FROM users
            WHERE LOWER(email) = LOWER(%s)
            LIMIT 1
        """, (
            invitation["invited_email"].lower(),
        ))

        existing_email = cursor.fetchone()

        if existing_email:
            conn.close()
            return "A user with this invited email already exists"

        hashed_password = generate_password_hash(password)
        avatar_initials = username[:2].upper()

        cursor.execute("""
            INSERT INTO users
            (
                username,
                email,
                password,
                avatar_initials,
                is_verified,
                status,
                created_at,
                login_count,
                failed_login_count
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            username,
            invitation["invited_email"],
            hashed_password,
            avatar_initials,
            True,
            "Active",
            str(datetime.now()),
            0,
            0
        ))

        new_user = cursor.fetchone()
        new_user_id = new_user["id"]

        cursor.execute("""
            SELECT id
            FROM user_roles
            WHERE user_id = %s
            AND role = %s
            AND organisation_id = %s
            AND workspace_id = %s
            LIMIT 1
        """, (
            new_user_id,
            invitation["role"],
            invitation["organisation_id"],
            invitation["workspace_id"]
        ))

        existing_role = cursor.fetchone()

        if not existing_role:

            cursor.execute("""
                INSERT INTO user_roles
                (
                    user_id,
                    role,
                    organisation_id,
                    workspace_id,
                    created_at,
                    updated_at
                )
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                new_user_id,
                invitation["role"],
                invitation["organisation_id"],
                invitation["workspace_id"],
                str(datetime.now()),
                str(datetime.now())
            ))

        cursor.execute("""
            UPDATE user_invitations
            SET
                status = 'Accepted',
                accepted_at = %s
            WHERE id = %s
        """, (
            str(datetime.now()),
            invitation["id"]
        ))

        conn.commit()
        conn.close()

        try:
            create_activity(
                f"{username} accepted an invitation",
                user_id=new_user_id,
                activity_type="Invitation",
                module="Account",
                severity="Low"
            )
        except:
            pass

        return redirect("/login")

    conn.close()

    return render_template(
        "accept_invitation.html",
        invitation=invitation
    )


@app.route("/logout")
def logout():

    if "user_id" in session:

        try:

            create_activity(
                f"{session.get('username', 'Unknown User')} logged out",
                user_id=session["user_id"],
                activity_type="Logout",
                module="Account",
                severity="Low"
            )

        except:
            pass

    session.clear()

    return redirect("/login")@app.route("/logout")
def logout():

    if "user_id" in session:

        try:

            create_activity(
                f"{session.get('username', 'Unknown User')} logged out",
                user_id=session["user_id"],
                activity_type="Logout",
                module="Account",
                severity="Low"
            )

        except:
            pass

    session.clear()

    return redirect("/login")


@app.route("/clients")
def clients():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Clients", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM clients
        WHERE user_id = %s
        ORDER BY company ASC
    """, (
        session["user_id"],
    ))

    clients = cursor.fetchall()

    total_clients = len(clients)

    active_clients = 0
    lead_clients = 0
    at_risk_clients = 0

    total_pipeline_value = 0

    clients_data = []

    for client in clients:

        estimated_value = float(
            client.get("estimated_value") or 0
        )

        total_pipeline_value += estimated_value

        status = client.get("status") or "Lead"

        if status == "Active":
            active_clients += 1

        elif status == "Lead":
            lead_clients += 1

        elif status == "At Risk":
            at_risk_clients += 1

        linked_projects = 0
        linked_invoices = 0

        health_score = 90

        if status == "Lead":
            health_score = 70

        elif status == "At Risk":
            health_score = 40

        elif status == "Inactive":
            health_score = 20

        clients_data.append({

            "client": client,
            "health_score": health_score,
            "linked_projects": linked_projects,
            "linked_invoices": linked_invoices

        })

    executive_insights = []

    if active_clients > 0:
        executive_insights.append(
            f"{active_clients} active client(s) generating delivery work."
        )

    if lead_clients > 0:
        executive_insights.append(
            f"{lead_clients} lead client(s) available for conversion."
        )

    if at_risk_clients > 0:
        executive_insights.append(
            f"{at_risk_clients} client(s) require relationship attention."
        )

    if total_clients == 0:
        executive_insights.append(
            "No client records currently available."
        )

    conn.close()

    return render_template(
        "clients.html",
        clients_data=clients_data,
        total_clients=total_clients,
        active_clients=active_clients,
        lead_clients=lead_clients,
        at_risk_clients=at_risk_clients,
        total_pipeline_value=total_pipeline_value,
        executive_insights=executive_insights
    )


@app.route("/add-client", methods=["GET", "POST"])
def add_client():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Clients", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO clients
            (
                name,
                company,
                email,
                phone,
                status,
                notes,
                estimated_value,
                client_owner,
                account_manager,
                opportunity_stage,
                client_health_score,
                client_risk_rating,
                renewal_date,
                contract_expiry_date,
                satisfaction_score,
                user_id
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (

            request.form.get("name"),
            request.form.get("company"),
            request.form.get("email"),
            request.form.get("phone"),
            request.form.get("status"),
            request.form.get("notes"),
            float(request.form.get("estimated_value") or 0),

            request.form.get("client_owner"),
            request.form.get("account_manager"),
            request.form.get("opportunity_stage"),

            int(
                request.form.get(
                    "client_health_score"
                ) or 70
            ),

            request.form.get("client_risk_rating"),
            request.form.get("renewal_date"),
            request.form.get("contract_expiry_date"),

            int(
                request.form.get(
                    "satisfaction_score"
                ) or 0
            ),

            session["user_id"]

        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} added a client"
        )

        return redirect("/clients")

    return render_template(
        "add_client.html"
    )

@app.route("/edit-client/<int:client_id>", methods=["GET", "POST"])
def edit_client(client_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Clients", "edit"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM clients
        WHERE id = %s
        AND user_id = %s
    """, (
        client_id,
        session["user_id"]
    ))

    client = cursor.fetchone()

    if not client:

        conn.close()
        return redirect("/clients")

    if request.method == "POST":

        cursor.execute("""
            UPDATE clients
            SET

                name = %s,
                company = %s,
                email = %s,
                phone = %s,
                status = %s,
                notes = %s,
                estimated_value = %s,

                client_owner = %s,
                account_manager = %s,
                opportunity_stage = %s,
                client_health_score = %s,
                client_risk_rating = %s,
                renewal_date = %s,
                contract_expiry_date = %s,
                satisfaction_score = %s

            WHERE id = %s
            AND user_id = %s
        """, (

            request.form.get("name"),
            request.form.get("company"),
            request.form.get("email"),
            request.form.get("phone"),
            request.form.get("status"),
            request.form.get("notes"),

            float(
                request.form.get(
                    "estimated_value"
                ) or 0
            ),

            request.form.get("client_owner"),
            request.form.get("account_manager"),
            request.form.get("opportunity_stage"),

            int(
                request.form.get(
                    "client_health_score"
                ) or 70
            ),

            request.form.get("client_risk_rating"),
            request.form.get("renewal_date"),
            request.form.get("contract_expiry_date"),

            int(
                request.form.get(
                    "satisfaction_score"
                ) or 0
            ),

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

    if not has_permission("Clients", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM clients
        WHERE id = %s
        AND user_id = %s
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


@app.route("/activity")
def activity():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Activity", "view"):
        return "Access denied"

    user_filter = request.args.get("user_id")
    type_filter = request.args.get("activity_type")
    module_filter = request.args.get("module")
    date_filter = request.args.get("created_at")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    query = """
        SELECT DISTINCT ON (activities.activity, activities.created_at)
            activities.*,
            users.username
        FROM activities
        LEFT JOIN users
        ON activities.user_id = users.id
        WHERE 1 = 1
    """

    params = []

    if user_filter:
        query += " AND activities.user_id = %s"
        params.append(user_filter)

    if type_filter:
        query += " AND activities.activity_type = %s"
        params.append(type_filter)

    if module_filter:
        query += " AND activities.module = %s"
        params.append(module_filter)

    if date_filter:
        query += " AND activities.created_at LIKE %s"
        params.append(f"{date_filter}%")

    query += """
        ORDER BY activities.activity, activities.created_at, activities.id DESC
        LIMIT 100
    """

    cursor.execute(query, params)
    activities = cursor.fetchall()

    cursor.execute("""
        SELECT id, username
        FROM users
        ORDER BY username ASC
    """)
    users = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT activity_type
        FROM activities
        WHERE activity_type IS NOT NULL
        ORDER BY activity_type ASC
    """)
    activity_types = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT module
        FROM activities
        WHERE module IS NOT NULL
        ORDER BY module ASC
    """)
    modules = cursor.fetchall()

    total_activities = len(activities)

    high_severity_count = len([
        activity for activity in activities
        if activity["severity"] == "High"
    ])

    conn.close()

    return render_template(
        "activity.html",
        activities=activities,
        users=users,
        activity_types=activity_types,
        modules=modules,
        total_activities=total_activities,
        high_severity_count=high_severity_count,
        user_filter=user_filter,
        type_filter=type_filter,
        module_filter=module_filter,
        date_filter=date_filter
    )


def create_activity(
    activity_text,
    user_id=None,
    activity_type="General",
    module="System",
    project_id=None,
    severity="Low"
):

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO activities
            (
                activity,
                user_id,
                activity_type,
                module,
                project_id,
                severity,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            activity_text,
            user_id,
            activity_type,
            module,
            project_id,
            severity,
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

    except Exception as e:

        print("Activity logging failed:", e)


@app.route("/advanced-search")
def advanced_search():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Tasks", "view"):
        return "Access denied"

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    project_filter = request.args.get("project", "").strip()

    has_searched = bool(
        search or status_filter or priority_filter or project_filter
    )

    tasks = []

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT name
        FROM projects
        WHERE user_id = %s
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if has_searched:

        query = """
            SELECT
                tasks.*,
                projects.name AS project_name
            FROM tasks
            JOIN projects
            ON tasks.project_id = projects.id
            WHERE projects.user_id = %s
        """

        params = [session["user_id"]]

        if search:
            query += """
                AND (
                    tasks.title ILIKE %s
                    OR projects.name ILIKE %s
                    OR tasks.status ILIKE %s
                    OR tasks.priority ILIKE %s
                    OR tasks.assigned_to ILIKE %s
                )
            """

            params.extend([
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            ])

        if status_filter:
            query += " AND tasks.status = %s"
            params.append(status_filter)

        if priority_filter:
            query += " AND tasks.priority = %s"
            params.append(priority_filter)

        if project_filter:
            query += " AND projects.name = %s"
            params.append(project_filter)

        query += " ORDER BY tasks.id DESC"

        cursor.execute(query, params)

        tasks = cursor.fetchall()

    result_count = len(tasks)

    conn.close()

    return render_template(
        "advanced_search.html",
        tasks=tasks,
        search=search,
        status_filter=status_filter,
        priority_filter=priority_filter,
        project_filter=project_filter,
        projects=projects,
        has_searched=has_searched,
        result_count=result_count
    )

@app.route("/gantt")
def gantt():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "view"):
        return "Access denied"

    selected_project = request.args.get("project_id", "")
    selected_status = request.args.get("status", "")
    selected_client = request.args.get("client", "")
    zoom = request.args.get("zoom", "Monthly")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    query = """
        SELECT
            projects.*,
            clients.name AS client_name
        FROM projects
        LEFT JOIN clients
        ON projects.client_id = clients.id
        WHERE projects.user_id = %s
        AND COALESCE(projects.is_archived, FALSE) = FALSE
    """

    params = [session["user_id"]]

    if selected_project:
        query += " AND projects.id = %s"
        params.append(selected_project)

    if selected_status:
        query += " AND projects.status = %s"
        params.append(selected_status)

    if selected_client:
        query += " AND clients.name = %s"
        params.append(selected_client)

    query += """
        ORDER BY
            CASE
                WHEN projects.start_date IS NULL OR projects.start_date = ''
                THEN '9999-12-31'
                ELSE projects.start_date
            END ASC
    """

    cursor.execute(query, params)

    projects = cursor.fetchall()

    cursor.execute("""
        SELECT id, name
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    filter_projects = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT clients.name
        FROM clients
        JOIN projects
        ON projects.client_id = clients.id
        WHERE projects.user_id = %s
        AND clients.name IS NOT NULL
        ORDER BY clients.name ASC
    """, (
        session["user_id"],
    ))

    filter_clients = cursor.fetchall()

    gantt_projects = []

    for project in projects:

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

        total_tasks = len(tasks)

        completed_tasks = len([
            task for task in tasks
            if task["status"] == "Completed"
        ])

        if total_tasks > 0:
            progress = round((completed_tasks / total_tasks) * 100)
        else:
            progress = 0

        if project["status"] == "Completed":
            progress = 100

        milestones = []

        if project["start_date"]:
            milestones.append({
                "name": "Kickoff",
                "date": project["start_date"]
            })

        if project["end_date"]:
            milestones.append({
                "name": "Target Finish",
                "date": project["end_date"]
            })

        for task in tasks:
            if task["status"] == "Completed":
                milestones.append({
                    "name": f"Completed: {task['title']}",
                    "date": task["due_date"]
                })

        dependency_lines = []

        for task in tasks:

            cursor.execute("""
                SELECT
                    task_dependencies.task_id,
                    task_dependencies.depends_on_task_id,
                    dependency_task.title AS dependency_title,
                    current_task.title AS current_title
                FROM task_dependencies
                JOIN tasks AS dependency_task
                ON task_dependencies.depends_on_task_id = dependency_task.id
                JOIN tasks AS current_task
                ON task_dependencies.task_id = current_task.id
                WHERE task_dependencies.task_id = %s
            """, (
                task["id"],
            ))

            dependencies = cursor.fetchall()

            for dependency in dependencies:
                dependency_lines.append({
                    "from": dependency["dependency_title"],
                    "to": dependency["current_title"]
                })

        critical_path = []

        for task in tasks:
            if (
                task["priority"] == "High"
                or task["status"] == "Blocked"
                or is_overdue(task["due_date"], task["status"])
            ):
                critical_path.append(task["title"])

        baseline_start = project["start_date"]
        baseline_end = project["end_date"]

        schedule_variance = "On Track"

        if project["end_date"] and project["status"] != "Completed":
            if project["end_date"] < str(date.today()):
                schedule_variance = "Behind Schedule"

        if progress == 100:
            schedule_variance = "Completed"

        gantt_projects.append({
            "id": project["id"],
            "name": project["name"],
            "status": project["status"],
            "client_name": project["client_name"],
            "start_date": project["start_date"],
            "end_date": project["end_date"],
            "baseline_start": baseline_start,
            "baseline_end": baseline_end,
            "progress": progress,
            "milestones": milestones,
            "dependency_lines": dependency_lines,
            "critical_path": critical_path,
            "schedule_variance": schedule_variance
        })

    conn.close()

    return render_template(
        "gantt.html",
        projects=gantt_projects,
        filter_projects=filter_projects,
        filter_clients=filter_clients,
        selected_project=selected_project,
        selected_status=selected_status,
        selected_client=selected_client,
        zoom=zoom,
        current_date=str(date.today())
    )

@app.route("/export-gantt")
def export_gantt():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
            projects.name,
            projects.status,
            projects.start_date,
            projects.end_date,
            clients.name AS client_name
        FROM projects
        LEFT JOIN clients
        ON projects.client_id = clients.id
        WHERE projects.user_id = %s
        AND COALESCE(projects.is_archived, FALSE) = FALSE
        ORDER BY projects.start_date ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    conn.close()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Project",
        "Client",
        "Status",
        "Start Date",
        "End Date"
    ])

    for project in projects:
        writer.writerow([
            project["name"],
            project["client_name"] or "",
            project["status"],
            project["start_date"],
            project["end_date"]
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=gantt_timeline.csv"
        }
    )

@app.route("/analytics")
def analytics():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

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

    if not has_permission("AI", "view"):
        return "Access denied"

    response_message = ""
    confidence_score = 0
    source_summary = ""
    mode = "General"

    prompt_suggestions = [
        "Summarise my current project delivery risks.",
        "Which tasks need urgent attention?",
        "Are any projects likely to be delayed?",
        "Give me a budget and cost risk summary.",
        "Which blockers should I escalate?",
        "Create an executive summary for my portfolio."
    ]

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT COUNT(*) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS total_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
    """, (
        session["user_id"],
    ))

    total_tasks = cursor.fetchone()["total_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS completed_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Completed'
    """, (
        session["user_id"],
    ))

    completed_tasks = cursor.fetchone()["completed_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS overdue_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.due_date IS NOT NULL
        AND tasks.due_date != ''
        AND tasks.due_date < %s
        AND tasks.status != 'Completed'
    """, (
        session["user_id"],
        str(date.today())
    ))

    overdue_tasks = cursor.fetchone()["overdue_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS blocked_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Blocked'
    """, (
        session["user_id"],
    ))

    blocked_tasks = cursor.fetchone()["blocked_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS high_priority_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.priority = 'High'
        AND tasks.status != 'Completed'
    """, (
        session["user_id"],
    ))

    high_priority_tasks = cursor.fetchone()["high_priority_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS total_risks
        FROM risks
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_risks = cursor.fetchone()["total_risks"]

    cursor.execute("""
        SELECT COUNT(*) AS total_issues
        FROM issues
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_issues = cursor.fetchone()["total_issues"]

    cursor.execute("""
        SELECT COUNT(*) AS total_changes
        FROM changes
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_changes = cursor.fetchone()["total_changes"]

    cursor.execute("""
        SELECT
            COALESCE(SUM(budget_amount), 0) AS total_budget,
            COALESCE(SUM(actual_cost), 0) AS total_actual_cost,
            COALESCE(SUM(forecast_cost), 0) AS total_forecast_cost
        FROM budgets
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    budget_data = cursor.fetchone()

    total_budget = float(budget_data["total_budget"] or 0)
    total_actual_cost = float(budget_data["total_actual_cost"] or 0)
    total_forecast_cost = float(budget_data["total_forecast_cost"] or 0)

    if total_tasks > 0:
        completion_rate = round((completed_tasks / total_tasks) * 100)
    else:
        completion_rate = 0

    if total_budget > 0:
        budget_usage = round((total_actual_cost / total_budget) * 100)
    else:
        budget_usage = 0

    source_summary = (
        f"Projects: {total_projects}, Tasks: {total_tasks}, "
        f"Completed: {completed_tasks}, Overdue: {overdue_tasks}, "
        f"Blocked: {blocked_tasks}, High Priority: {high_priority_tasks}, "
        f"Risks: {total_risks}, Issues: {total_issues}, Changes: {total_changes}, "
        f"Budget Usage: {budget_usage}%"
    )

    cursor.execute("""
        SELECT *
        FROM ai_chat_history
        WHERE user_id = %s
        ORDER BY id DESC
        LIMIT 8
    """, (
        session["user_id"],
    ))

    chat_history = cursor.fetchall()

    if request.method == "POST":

        prompt = request.form.get("prompt", "").strip()
        mode = request.form.get("mode", "General")

        if not prompt:

            response_message = "Please enter a question for the AI Assistant."

        elif client is None:

            response_message = (
                "AI assistant is not connected yet. "
                "Please add OPENAI_API_KEY inside Render environment variables."
            )

            confidence_score = 0

        else:

            try:

                completion = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an AI project management assistant for an enterprise PM platform. "
                                "Answer using the user's project data only. "
                                "Be practical, clear and structured. "
                                "When giving recommendations, mention the data points used. "
                                "If data is weak or incomplete, say so clearly."
                            )
                        },
                        {
                            "role": "user",
                            "content": f"""
Mode:
{mode}

User question:
{prompt}

Current portfolio context:
- Total projects: {total_projects}
- Total tasks: {total_tasks}
- Completed tasks: {completed_tasks}
- Completion rate: {completion_rate}%
- Overdue tasks: {overdue_tasks}
- Blocked tasks: {blocked_tasks}
- High priority open tasks: {high_priority_tasks}
- Open risks: {total_risks}
- Open issues: {total_issues}
- Open changes: {total_changes}
- Total budget: £{total_budget:,.2f}
- Actual cost: £{total_actual_cost:,.2f}
- Forecast cost: £{total_forecast_cost:,.2f}
- Budget usage: {budget_usage}%

Give useful project management advice.
                            """
                        }
                    ]
                )

                response_message = completion.choices[0].message.content

                confidence_score = 75

                if total_tasks > 0:
                    confidence_score += 10

                if total_risks > 0 or total_issues > 0:
                    confidence_score += 5

                if total_budget > 0:
                    confidence_score += 5

                confidence_score = min(confidence_score, 95)

            except Exception as e:

                response_message = f"AI assistant error: {str(e)}"
                confidence_score = 0

        cursor.execute("""
            INSERT INTO ai_chat_history
            (
                user_id,
                prompt,
                response,
                confidence_score,
                source_summary,
                mode,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            prompt,
            response_message,
            confidence_score,
            source_summary,
            mode,
            str(datetime.now())
        ))

        conn.commit()

        cursor.execute("""
            SELECT *
            FROM ai_chat_history
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 8
        """, (
            session["user_id"],
        ))

        chat_history = cursor.fetchall()

    conn.close()

    return render_template(
        "ai_assistant.html",
        response_message=response_message,
        prompt_suggestions=prompt_suggestions,
        chat_history=chat_history,
        confidence_score=confidence_score,
        source_summary=source_summary,
        mode=mode,
        total_projects=total_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        completion_rate=completion_rate,
        overdue_tasks=overdue_tasks,
        blocked_tasks=blocked_tasks,
        high_priority_tasks=high_priority_tasks,
        total_risks=total_risks,
        total_issues=total_issues,
        total_changes=total_changes,
        budget_usage=budget_usage
    )

@app.route("/risks")
def risks():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Risks", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            risks.*,
            projects.name AS project_name
        FROM risks
        LEFT JOIN projects
        ON risks.project_id = projects.id
        WHERE risks.user_id = %s
        ORDER BY risks.severity_score DESC
    """, (
        session["user_id"],
    ))

    risks = cursor.fetchall()

    enriched_risks = []

    for risk in risks:

        cursor.execute("""
            SELECT
                severity_score,
                residual_score,
                target_score,
                status,
                created_at
            FROM risk_history
            WHERE risk_id = %s
            ORDER BY id DESC
            LIMIT 2
        """, (
            risk["id"],
        ))

        history = cursor.fetchall()

        risk_trend = "Stable"

        if len(history) >= 2:

            latest = history[0]["severity_score"] or 0
            previous = history[1]["severity_score"] or 0

            if latest > previous:
                risk_trend = "Increasing"

            elif latest < previous:
                risk_trend = "Reducing"

        enriched_risks.append({
            "risk": risk,
            "risk_trend": risk_trend
        })

    total_risks = len(risks)

    open_risks = len([
        risk for risk in risks
        if risk["status"] not in ["Closed", "Resolved"]
    ])

    critical_risks = len([
        risk for risk in risks
        if (risk["severity_score"] or 0) >= 12
    ])

    escalated_risks = len([
        risk for risk in risks
        if risk.get("escalation_required") is True
        or risk.get("escalation_level") in ["High", "Critical", "Escalated"]
    ])

    conn.close()

    return render_template(
        "risks.html",
        risks=enriched_risks,
        total_risks=total_risks,
        open_risks=open_risks,
        critical_risks=critical_risks,
        escalated_risks=escalated_risks
    )


@app.route("/add-risk", methods=["GET", "POST"])
def add_risk():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Risks", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        probability = request.form.get("probability", "Medium")
        impact = request.form.get("impact", "Medium")
        mitigation = request.form.get("mitigation", "")
        owner = request.form.get("owner", "")
        status = request.form.get("status", "Open")

        category = request.form.get("category", "Delivery")
        risk_appetite = request.form.get("risk_appetite", "Medium")

        residual_probability = request.form.get("residual_probability", probability)
        residual_impact = request.form.get("residual_impact", impact)

        target_probability = request.form.get("target_probability", "Low")
        target_impact = request.form.get("target_impact", "Low")

        escalation_level = request.form.get("escalation_level", "None")

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

        appetite_map = {
            "Low": 3,
            "Medium": 6,
            "High": 9
        }

        severity_score = probability_map[probability] * impact_map[impact]
        residual_score = probability_map[residual_probability] * impact_map[residual_impact]
        target_score = probability_map[target_probability] * impact_map[target_impact]

        appetite_threshold = appetite_map.get(risk_appetite, 6)

        escalation_required = False

        if severity_score > appetite_threshold or residual_score > appetite_threshold:
            escalation_required = True

        cursor.execute("""
            INSERT INTO risks
            (
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
                category,
                risk_appetite,
                residual_probability,
                residual_impact,
                residual_score,
                target_probability,
                target_impact,
                target_score,
                escalation_level,
                escalation_required,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            session["user_id"],
            project_id if project_id else None,
            title,
            description,
            probability,
            impact,
            severity_score,
            mitigation,
            owner,
            status,
            category,
            risk_appetite,
            residual_probability,
            residual_impact,
            residual_score,
            target_probability,
            target_impact,
            target_score,
            escalation_level,
            escalation_required,
            str(date.today())
        ))

        risk_id = cursor.fetchone()["id"]

        cursor.execute("""
            INSERT INTO risk_history
            (
                risk_id,
                user_id,
                severity_score,
                residual_score,
                target_score,
                status,
                action,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            risk_id,
            session["user_id"],
            severity_score,
            residual_score,
            target_score,
            status,
            "Risk created",
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


@app.route("/edit-risk/<int:risk_id>", methods=["GET", "POST"])
def edit_risk(risk_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Risks", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM risks
        WHERE id = %s
        AND user_id = %s
    """, (
        risk_id,
        session["user_id"],
    ))

    risk = cursor.fetchone()

    if not risk:
        conn.close()
        return redirect("/risks")

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        probability = request.form.get("probability", "Medium")
        impact = request.form.get("impact", "Medium")
        mitigation = request.form.get("mitigation", "")
        owner = request.form.get("owner", "")
        status = request.form.get("status", "Open")

        category = request.form.get("category", "Delivery")
        risk_appetite = request.form.get("risk_appetite", "Medium")

        residual_probability = request.form.get("residual_probability", probability)
        residual_impact = request.form.get("residual_impact", impact)

        target_probability = request.form.get("target_probability", "Low")
        target_impact = request.form.get("target_impact", "Low")

        escalation_level = request.form.get("escalation_level", "None")

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

        appetite_map = {
            "Low": 3,
            "Medium": 6,
            "High": 9
        }

        severity_score = probability_map[probability] * impact_map[impact]
        residual_score = probability_map[residual_probability] * impact_map[residual_impact]
        target_score = probability_map[target_probability] * impact_map[target_impact]

        appetite_threshold = appetite_map.get(risk_appetite, 6)

        escalation_required = False

        if severity_score > appetite_threshold or residual_score > appetite_threshold:
            escalation_required = True

        cursor.execute("""
            UPDATE risks
            SET
                project_id = %s,
                title = %s,
                description = %s,
                probability = %s,
                impact = %s,
                severity_score = %s,
                mitigation = %s,
                owner = %s,
                status = %s,
                category = %s,
                risk_appetite = %s,
                residual_probability = %s,
                residual_impact = %s,
                residual_score = %s,
                target_probability = %s,
                target_impact = %s,
                target_score = %s,
                escalation_level = %s,
                escalation_required = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            project_id if project_id else None,
            title,
            description,
            probability,
            impact,
            severity_score,
            mitigation,
            owner,
            status,
            category,
            risk_appetite,
            residual_probability,
            residual_impact,
            residual_score,
            target_probability,
            target_impact,
            target_score,
            escalation_level,
            escalation_required,
            risk_id,
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO risk_history
            (
                risk_id,
                user_id,
                severity_score,
                residual_score,
                target_score,
                status,
                action,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            risk_id,
            session["user_id"],
            severity_score,
            residual_score,
            target_score,
            status,
            "Risk updated",
            str(date.today())
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

    if not has_permission("Risks", "delete"):
        return "Access denied"

    conn = get_db_connection()

    conn.execute("""
    DELETE FROM risks
    WHERE id = ?
    AND user_id = ?
    """, (
        risk_id,
        session["user_id"],
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} deleted a risk"
    )

    return redirect("/risks")


@app.route("/issues")
def issues():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Issues", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            issues.*,
            projects.name AS project_name
        FROM issues
        LEFT JOIN projects
        ON issues.project_id = projects.id
        WHERE issues.user_id = %s
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
    ))

    issues = cursor.fetchall()

    enriched_issues = []

    today = date.today()

    for issue in issues:

        issue_age = 0

        try:

            if issue["created_at"]:

                created_date = datetime.strptime(
                    issue["created_at"],
                    "%Y-%m-%d"
                ).date()

                issue_age = (today - created_date).days

        except Exception:

            issue_age = 0

        sla_status = "No SLA"

        try:

            if issue["sla_target_date"]:

                sla_date = datetime.strptime(
                    issue["sla_target_date"],
                    "%Y-%m-%d"
                ).date()

                if issue["status"] in ["Resolved", "Closed"]:
                    sla_status = "Met / Closed"

                elif sla_date < today:
                    sla_status = "Breached"

                else:
                    sla_status = "On Track"

        except Exception:

            sla_status = "No SLA"

        cursor.execute("""
            SELECT
                previous_status,
                new_status,
                created_at
            FROM issue_history
            WHERE issue_id = %s
            ORDER BY id DESC
            LIMIT 2
        """, (
            issue["id"],
        ))

        history = cursor.fetchall()

        issue_trend = "Stable"

        if len(history) >= 2:

            latest = history[0]["new_status"]
            previous = history[1]["new_status"]

            if (
                latest in ["Resolved", "Closed"]
                and previous not in ["Resolved", "Closed"]
            ):
                issue_trend = "Improving"

            elif latest == "Escalated":
                issue_trend = "Escalating"

        enriched_issues.append({

            "issue": issue,

            "issue_age": issue_age,

            "sla_status": sla_status,

            "issue_trend": issue_trend

        })

    total_issues = len(issues)

    open_issues = len([
        issue for issue in issues
        if issue["status"] not in ["Resolved", "Closed"]
    ])

    breached_sla = len([
        item for item in enriched_issues
        if item["sla_status"] == "Breached"
    ])

    escalated_issues = len([
        issue for issue in issues
        if issue["escalation_status"] == "Escalated"
    ])

    conn.close()

    return render_template(
        "issues.html",
        issues=enriched_issues,
        total_issues=total_issues,
        open_issues=open_issues,
        breached_sla=breached_sla,
        escalated_issues=escalated_issues
    )


@app.route("/add-issue", methods=["GET", "POST"])
def add_issue():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Issues", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        priority = request.form.get("priority", "Medium")
        owner = request.form.get("owner", "")
        status = request.form.get("status", "Open")
        resolution = request.form.get("resolution", "")

        issue_category = request.form.get("issue_category", "Delivery")
        sla_target_date = request.form.get("sla_target_date", "")
        escalation_status = request.form.get("escalation_status", "Not Escalated")
        escalation_owner = request.form.get("escalation_owner", "")
        escalation_date = request.form.get("escalation_date", "")
        root_cause = request.form.get("root_cause", "")
        closure_validation = request.form.get("closure_validation", "")

        resolved_date = ""

        if status in ["Resolved", "Closed"]:
            resolved_date = str(date.today())

        cursor.execute("""
            INSERT INTO issues
            (
                user_id,
                project_id,
                title,
                description,
                priority,
                owner,
                status,
                resolution,
                issue_category,
                sla_target_date,
                escalation_status,
                escalation_owner,
                escalation_date,
                root_cause,
                closure_validation,
                resolved_date,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            session["user_id"],
            project_id if project_id else None,
            title,
            description,
            priority,
            owner,
            status,
            resolution,
            issue_category,
            sla_target_date,
            escalation_status,
            escalation_owner,
            escalation_date,
            root_cause,
            closure_validation,
            resolved_date,
            str(date.today())
        ))

        issue_id = cursor.fetchone()["id"]

        cursor.execute("""
            INSERT INTO issue_history
            (
                issue_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            issue_id,
            session["user_id"],
            "Issue created",
            "",
            status,
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


@app.route("/edit-issue/<int:issue_id>", methods=["GET", "POST"])
def edit_issue(issue_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Issues", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM issues
        WHERE id = %s
        AND user_id = %s
    """, (
        issue_id,
        session["user_id"]
    ))

    issue = cursor.fetchone()

    if not issue:
        conn.close()
        return redirect("/issues")

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        previous_status = issue["status"]

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        priority = request.form.get("priority", "Medium")
        owner = request.form.get("owner", "")
        status = request.form.get("status", "Open")
        resolution = request.form.get("resolution", "")

        issue_category = request.form.get("issue_category", "Delivery")
        sla_target_date = request.form.get("sla_target_date", "")
        escalation_status = request.form.get("escalation_status", "Not Escalated")
        escalation_owner = request.form.get("escalation_owner", "")
        escalation_date = request.form.get("escalation_date", "")
        root_cause = request.form.get("root_cause", "")
        closure_validation = request.form.get("closure_validation", "")

        resolved_date = issue["resolved_date"]

        if status in ["Resolved", "Closed"] and not resolved_date:
            resolved_date = str(date.today())

        cursor.execute("""
            UPDATE issues
            SET
                project_id = %s,
                title = %s,
                description = %s,
                priority = %s,
                owner = %s,
                status = %s,
                resolution = %s,
                issue_category = %s,
                sla_target_date = %s,
                escalation_status = %s,
                escalation_owner = %s,
                escalation_date = %s,
                root_cause = %s,
                closure_validation = %s,
                resolved_date = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            project_id if project_id else None,
            title,
            description,
            priority,
            owner,
            status,
            resolution,
            issue_category,
            sla_target_date,
            escalation_status,
            escalation_owner,
            escalation_date,
            root_cause,
            closure_validation,
            resolved_date,
            issue_id,
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO issue_history
            (
                issue_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            issue_id,
            session["user_id"],
            "Issue updated",
            previous_status,
            status,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated an issue"
        )

        return redirect("/issues")

    cursor.execute("""
        SELECT *
        FROM issue_history
        WHERE issue_id = %s
        ORDER BY id DESC
    """, (
        issue_id,
    ))

    issue_history = cursor.fetchall()

    conn.close()

    return render_template(
        "edit_issue.html",
        issue=issue,
        projects=projects,
        issue_history=issue_history
    )


@app.route("/delete-issue/<int:issue_id>")
def delete_issue(issue_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Issues", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM issues
        WHERE id = %s
        AND user_id = %s
    """, (
        issue_id,
        session["user_id"]
    ))

    issue = cursor.fetchone()

    if not issue:
        conn.close()
        return redirect("/issues")

    cursor.execute("""
        DELETE FROM issues
        WHERE id = %s
        AND user_id = %s
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

@app.route("/changes")
def changes():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Changes", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
            changes.*,
            projects.name AS project_name
        FROM changes
        LEFT JOIN projects
        ON changes.project_id = projects.id
        WHERE changes.user_id = %s
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
    ))

    changes = cursor.fetchall()

    total_changes = len(changes)
    pending_changes = len([
        change for change in changes
        if change["approval_status"] == "Pending"
    ])
    approved_changes = len([
        change for change in changes
        if change["approval_status"] == "Approved"
    ])
    rejected_changes = len([
        change for change in changes
        if change["approval_status"] == "Rejected"
    ])
    cab_required_count = len([
        change for change in changes
        if change["cab_required"] == "Yes"
    ])

    conn.close()

    return render_template(
        "changes.html",
        changes=changes,
        total_changes=total_changes,
        pending_changes=pending_changes,
        approved_changes=approved_changes,
        rejected_changes=rejected_changes,
        cab_required_count=cab_required_count
    )


@app.route("/add-change", methods=["GET", "POST"])
def add_change():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Changes", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM approvals
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    approvals = cursor.fetchall()

    if request.method == "POST":

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        impact = request.form.get("impact", "Medium")
        requested_by = request.form.get("requested_by", "")
        approval_status = request.form.get("approval_status", "Pending")
        implementation_plan = request.form.get("implementation_plan", "")

        cost_impact = float(request.form.get("cost_impact", 0) or 0)
        schedule_impact_days = int(request.form.get("schedule_impact_days", 0) or 0)
        resource_impact = request.form.get("resource_impact", "")
        benefit_impact = request.form.get("benefit_impact", "")

        cab_required = request.form.get("cab_required", "No")
        cab_decision = request.form.get("cab_decision", "")

        implementation_status = request.form.get("implementation_status", "Not Started")
        implementation_date = request.form.get("implementation_date", "")
        rollback_plan = request.form.get("rollback_plan", "")

        linked_approval_id = request.form.get("linked_approval_id")

        cursor.execute("""
            INSERT INTO changes
            (
                user_id,
                project_id,
                title,
                description,
                impact,
                requested_by,
                approval_status,
                implementation_plan,
                cost_impact,
                schedule_impact_days,
                resource_impact,
                benefit_impact,
                cab_required,
                cab_decision,
                implementation_status,
                implementation_date,
                rollback_plan,
                linked_approval_id,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            session["user_id"],
            project_id if project_id else None,
            title,
            description,
            impact,
            requested_by,
            approval_status,
            implementation_plan,
            cost_impact,
            schedule_impact_days,
            resource_impact,
            benefit_impact,
            cab_required,
            cab_decision,
            implementation_status,
            implementation_date,
            rollback_plan,
            linked_approval_id if linked_approval_id else None,
            str(date.today())
        ))

        change_id = cursor.fetchone()["id"]

        cursor.execute("""
            INSERT INTO change_history
            (
                change_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            change_id,
            session["user_id"],
            "Change request created",
            "",
            approval_status,
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
        projects=projects,
        approvals=approvals
    )


@app.route("/edit-change/<int:change_id>", methods=["GET", "POST"])
def edit_change(change_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Changes", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM changes
        WHERE id = %s
        AND user_id = %s
    """, (
        change_id,
        session["user_id"]
    ))

    change = cursor.fetchone()

    if not change:
        conn.close()
        return redirect("/changes")

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM approvals
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    approvals = cursor.fetchall()

    if request.method == "POST":

        previous_status = change["approval_status"]

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        impact = request.form.get("impact", "Medium")
        requested_by = request.form.get("requested_by", "")
        approval_status = request.form.get("approval_status", "Pending")
        implementation_plan = request.form.get("implementation_plan", "")

        cost_impact = float(request.form.get("cost_impact", 0) or 0)
        schedule_impact_days = int(request.form.get("schedule_impact_days", 0) or 0)
        resource_impact = request.form.get("resource_impact", "")
        benefit_impact = request.form.get("benefit_impact", "")

        cab_required = request.form.get("cab_required", "No")
        cab_decision = request.form.get("cab_decision", "")

        implementation_status = request.form.get("implementation_status", "Not Started")
        implementation_date = request.form.get("implementation_date", "")
        rollback_plan = request.form.get("rollback_plan", "")

        linked_approval_id = request.form.get("linked_approval_id")

        cursor.execute("""
            UPDATE changes
            SET
                project_id = %s,
                title = %s,
                description = %s,
                impact = %s,
                requested_by = %s,
                approval_status = %s,
                implementation_plan = %s,
                cost_impact = %s,
                schedule_impact_days = %s,
                resource_impact = %s,
                benefit_impact = %s,
                cab_required = %s,
                cab_decision = %s,
                implementation_status = %s,
                implementation_date = %s,
                rollback_plan = %s,
                linked_approval_id = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            project_id if project_id else None,
            title,
            description,
            impact,
            requested_by,
            approval_status,
            implementation_plan,
            cost_impact,
            schedule_impact_days,
            resource_impact,
            benefit_impact,
            cab_required,
            cab_decision,
            implementation_status,
            implementation_date,
            rollback_plan,
            linked_approval_id if linked_approval_id else None,
            change_id,
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO change_history
            (
                change_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            change_id,
            session["user_id"],
            "Change request updated",
            previous_status,
            approval_status,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated a change request"
        )

        return redirect("/changes")

    cursor.execute("""
        SELECT *
        FROM change_history
        WHERE change_id = %s
        ORDER BY id DESC
    """, (
        change_id,
    ))

    change_history = cursor.fetchall()

    conn.close()

    return render_template(
        "edit_change.html",
        change=change,
        projects=projects,
        approvals=approvals,
        change_history=change_history
    )


@app.route("/delete-change/<int:change_id>")
def delete_change(change_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Changes", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM change_history
        WHERE change_id = %s
    """, (
        change_id,
    ))

    cursor.execute("""
        DELETE FROM changes
        WHERE id = %s
        AND user_id = %s
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


@app.route("/business-cases")
def business_cases():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Business Cases", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            business_cases.*,
            projects.name AS project_name
        FROM business_cases
        LEFT JOIN projects
        ON business_cases.project_id = projects.id
        WHERE business_cases.user_id = %s
        ORDER BY business_cases.created_at DESC
    """, (
        session["user_id"],
    ))

    business_cases = cursor.fetchall()

    total_cases = len(business_cases)

    approved_cases = len([
        case for case in business_cases
        if case["approval_status"] == "Approved"
    ])

    pending_cases = len([
        case for case in business_cases
        if case["approval_status"] == "Pending"
    ])

    rejected_cases = len([
        case for case in business_cases
        if case["approval_status"] == "Rejected"
    ])

    total_investment = sum(
        float(case["estimated_cost"] or 0)
        for case in business_cases
    )

    total_roi = sum(
        float(case["expected_roi"] or 0)
        for case in business_cases
    )

    benefits_realised = 0

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM business_case_benefits
        WHERE status = 'Realised'
    """)

    result = cursor.fetchone()

    if result:
        benefits_realised = result["total"]

    conn.close()

    return render_template(
        "business_cases.html",
        business_cases=business_cases,
        total_cases=total_cases,
        approved_cases=approved_cases,
        pending_cases=pending_cases,
        rejected_cases=rejected_cases,
        total_investment=total_investment,
        total_roi=total_roi,
        benefits_realised=benefits_realised
    )

@app.route("/add-business-case", methods=["GET", "POST"])
def add_business_case():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Business Cases", "create"):
        return "Access denied"

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
            INSERT INTO business_cases
            (
                user_id,
                project_id,
                programme_id,
                title,
                strategic_objective,
                business_driver,
                problem_statement,
                proposed_solution,
                options_considered,
                preferred_option,
                expected_benefits,
                disbenefits,
                estimated_cost,
                expected_roi,
                payback_period,
                investment_category,
                sponsor,
                benefit_owner,
                approval_status,
                review_date,
                approval_date,
                status,
                created_at
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("programme_id"),
            request.form.get("title"),
            request.form.get("strategic_objective"),
            request.form.get("business_driver"),
            request.form.get("problem_statement"),
            request.form.get("proposed_solution"),
            request.form.get("options_considered"),
            request.form.get("preferred_option"),
            request.form.get("expected_benefits"),
            request.form.get("disbenefits"),
            request.form.get("estimated_cost") or 0,
            request.form.get("expected_roi") or 0,
            request.form.get("payback_period"),
            request.form.get("investment_category"),
            request.form.get("sponsor"),
            request.form.get("benefit_owner"),
            request.form.get("approval_status"),
            request.form.get("review_date"),
            request.form.get("approval_date"),
            request.form.get("status"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/business-cases")

    conn.close()

    return render_template(
        "add_business_case.html",
        projects=projects
    )

@app.route("/edit-business-case/<int:case_id>", methods=["GET", "POST"])
def edit_business_case(case_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Business Cases", "edit"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM business_cases
        WHERE id = %s
        AND user_id = %s
    """, (
        case_id,
        session["user_id"]
    ))

    business_case = cursor.fetchone()

    if not business_case:
        conn.close()
        return redirect("/business-cases")

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

        previous_status = business_case["status"]

        cursor.execute("""
            UPDATE business_cases
            SET
                project_id = %s,
                programme_id = %s,
                title = %s,
                strategic_objective = %s,
                business_driver = %s,
                problem_statement = %s,
                proposed_solution = %s,
                options_considered = %s,
                preferred_option = %s,
                expected_benefits = %s,
                disbenefits = %s,
                estimated_cost = %s,
                expected_roi = %s,
                payback_period = %s,
                investment_category = %s,
                sponsor = %s,
                benefit_owner = %s,
                approval_status = %s,
                review_date = %s,
                approval_date = %s,
                status = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            request.form.get("programme_id"),
            request.form.get("title"),
            request.form.get("strategic_objective"),
            request.form.get("business_driver"),
            request.form.get("problem_statement"),
            request.form.get("proposed_solution"),
            request.form.get("options_considered"),
            request.form.get("preferred_option"),
            request.form.get("expected_benefits"),
            request.form.get("disbenefits"),
            request.form.get("estimated_cost") or 0,
            request.form.get("expected_roi") or 0,
            request.form.get("payback_period"),
            request.form.get("investment_category"),
            request.form.get("sponsor"),
            request.form.get("benefit_owner"),
            request.form.get("approval_status"),
            request.form.get("review_date"),
            request.form.get("approval_date"),
            request.form.get("status"),
            case_id,
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO business_case_history
            (
                business_case_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            case_id,
            session["user_id"],
            "Business Case Updated",
            previous_status,
            request.form.get("status"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/business-cases")

    conn.close()

    return render_template(
        "edit_business_case.html",
        business_case=business_case,
        projects=projects
    )

@app.route("/delete-business-case/<int:case_id>")
def delete_business_case(case_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Business Cases", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM business_cases
        WHERE id = %s
        AND user_id = %s
    """, (
        case_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/business-cases")

@app.route("/business-case-history/<int:case_id>")
def business_case_history(case_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM business_case_history
        WHERE business_case_id = %s
        ORDER BY id DESC
    """, (
        case_id,
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "business_case_history.html",
        history=history
    )

@app.route("/business-case-benefits/<int:case_id>")
def business_case_benefits(case_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM business_case_benefits
        WHERE business_case_id = %s
        ORDER BY id DESC
    """, (
        case_id,
    ))

    benefits = cursor.fetchall()

    conn.close()

    return render_template(
        "business_case_benefits.html",
        benefits=benefits,
        case_id=case_id
    )

@app.route("/add-business-case-benefit/<int:case_id>", methods=["GET", "POST"])
def add_business_case_benefit(case_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor()

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO business_case_benefits
            (
                business_case_id,
                benefit_name,
                benefit_type,
                owner,
                target_value,
                actual_value,
                status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            case_id,
            request.form.get("benefit_name"),
            request.form.get("benefit_type"),
            request.form.get("owner"),
            request.form.get("target_value"),
            request.form.get("actual_value"),
            request.form.get("status"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect(
            f"/business-case-benefits/{case_id}"
        )

    conn.close()

    return render_template(
        "add_business_case_benefit.html",
        case_id=case_id
    )
@app.route("/business-case-approvals/<int:case_id>")
def business_case_approvals(case_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM business_case_approvals
        WHERE business_case_id = %s
        ORDER BY id DESC
    """, (
        case_id,
    ))

    approvals = cursor.fetchall()

    conn.close()

    return render_template(
        "business_case_approvals.html",
        approvals=approvals,
        case_id=case_id
    )

@app.route("/add-business-case-approval/<int:case_id>", methods=["GET", "POST"])
def add_business_case_approval(case_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor()

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO business_case_approvals
            (
                business_case_id,
                approver,
                decision,
                comments,
                decision_date
            )
            VALUES (%s,%s,%s,%s,%s)
        """, (
            case_id,
            request.form.get("approver"),
            request.form.get("decision"),
            request.form.get("comments"),
            request.form.get("decision_date")
        ))

        conn.commit()
        conn.close()

        return redirect(
            f"/business-case-approvals/{case_id}"
        )

    conn.close()

    return render_template(
        "add_business_case_approval.html",
        case_id=case_id
    )


@app.route("/benefits")
def benefits():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Benefits", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
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
    ))

    benefits = cursor.fetchall()

    today = date.today()

    enriched_benefits = []

    for benefit in benefits:

        expected_value = clean_money_value(benefit["expected_value"])
        actual_value = clean_money_value(benefit["actual_value"])
        forecast_value = clean_money_value(benefit["forecast_value"])

        realization_percentage = 0

        if expected_value > 0:
            realization_percentage = round(
                (actual_value / expected_value) * 100
            )

        review_status = "No Review Date"

        try:
            if benefit["review_date"]:

                review_date = datetime.strptime(
                    benefit["review_date"],
                    "%Y-%m-%d"
                ).date()

                if review_date < today:
                    review_status = "Review Overdue"
                elif review_date == today:
                    review_status = "Review Due Today"
                else:
                    review_status = "Review Scheduled"

        except Exception:
            review_status = "No Review Date"

        enriched_benefits.append({
            "benefit": benefit,
            "expected_value_clean": expected_value,
            "actual_value_clean": actual_value,
            "forecast_value_clean": forecast_value,
            "realization_percentage": realization_percentage,
            "review_status": review_status
        })

    if benefits:
        top_benefit = max(
            enriched_benefits,
            key=lambda item: item["expected_value_clean"]
        )
    else:
        top_benefit = None

    total_expected_value = sum([
        item["expected_value_clean"]
        for item in enriched_benefits
    ])

    total_actual_value = sum([
        item["actual_value_clean"]
        for item in enriched_benefits
    ])

    total_forecast_value = sum([
        item["forecast_value_clean"]
        for item in enriched_benefits
    ])

    if total_expected_value > 0:
        portfolio_realization = round(
            (total_actual_value / total_expected_value) * 100
        )
    else:
        portfolio_realization = 0

    overdue_reviews = len([
        item for item in enriched_benefits
        if item["review_status"] == "Review Overdue"
    ])

    conn.close()

    return render_template(
        "benefits.html",
        benefits=enriched_benefits,
        top_benefit=top_benefit,
        total_expected_value=total_expected_value,
        total_actual_value=total_actual_value,
        total_forecast_value=total_forecast_value,
        portfolio_realization=portfolio_realization,
        overdue_reviews=overdue_reviews
    )


@app.route("/add-benefit", methods=["GET", "POST"])
def add_benefit():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Benefits", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        expected_value = clean_money_value(
            request.form.get("expected_value", 0)
        )

        actual_value = clean_money_value(
            request.form.get("actual_value", 0)
        )

        forecast_value = clean_money_value(
            request.form.get("forecast_value", 0)
        )

        realization_percentage = 0

        if expected_value > 0:
            realization_percentage = round(
                (actual_value / expected_value) * 100
            )

        status = request.form.get("status", "Planned")

        cursor.execute("""
            INSERT INTO benefits
            (
                user_id,
                project_id,
                title,
                description,
                benefit_type,
                benefit_category,
                expected_value,
                actual_value,
                forecast_value,
                realization_percentage,
                measurement_method,
                owner,
                status,
                target_date,
                realised_date,
                review_date,
                review_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("title", ""),
            request.form.get("description", ""),
            request.form.get("benefit_type", ""),
            request.form.get("benefit_category", "Financial"),
            expected_value,
            actual_value,
            forecast_value,
            realization_percentage,
            request.form.get("measurement_method", ""),
            request.form.get("owner", ""),
            status,
            request.form.get("target_date", ""),
            request.form.get("realised_date", ""),
            request.form.get("review_date", ""),
            "Scheduled",
            str(date.today())
        ))

        benefit_id = cursor.fetchone()["id"]

        cursor.execute("""
            INSERT INTO benefit_history
            (
                benefit_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            benefit_id,
            session["user_id"],
            "Benefit created",
            "",
            status,
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


@app.route("/edit-benefit/<int:benefit_id>", methods=["GET", "POST"])
def edit_benefit(benefit_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Benefits", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM benefits
        WHERE id = %s
        AND user_id = %s
    """, (
        benefit_id,
        session["user_id"]
    ))

    benefit = cursor.fetchone()

    if not benefit:
        conn.close()
        return redirect("/benefits")

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        previous_status = benefit["status"]

        expected_value = clean_money_value(
            request.form.get("expected_value", 0)
        )

        actual_value = clean_money_value(
            request.form.get("actual_value", 0)
        )

        forecast_value = clean_money_value(
            request.form.get("forecast_value", 0)
        )

        realization_percentage = 0

        if expected_value > 0:
            realization_percentage = round(
                (actual_value / expected_value) * 100
            )

        status = request.form.get("status", "Planned")

        cursor.execute("""
            UPDATE benefits
            SET
                project_id = %s,
                title = %s,
                description = %s,
                benefit_type = %s,
                benefit_category = %s,
                expected_value = %s,
                actual_value = %s,
                forecast_value = %s,
                realization_percentage = %s,
                measurement_method = %s,
                owner = %s,
                status = %s,
                target_date = %s,
                realised_date = %s,
                review_date = %s,
                review_status = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            request.form.get("title", ""),
            request.form.get("description", ""),
            request.form.get("benefit_type", ""),
            request.form.get("benefit_category", "Financial"),
            expected_value,
            actual_value,
            forecast_value,
            realization_percentage,
            request.form.get("measurement_method", ""),
            request.form.get("owner", ""),
            status,
            request.form.get("target_date", ""),
            request.form.get("realised_date", ""),
            request.form.get("review_date", ""),
            "Scheduled",
            benefit_id,
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO benefit_history
            (
                benefit_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            benefit_id,
            session["user_id"],
            "Benefit updated",
            previous_status,
            status,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated a benefit"
        )

        return redirect("/benefits")

    cursor.execute("""
        SELECT *
        FROM benefit_history
        WHERE benefit_id = %s
        ORDER BY id DESC
    """, (
        benefit_id,
    ))

    benefit_history = cursor.fetchall()

    conn.close()

    return render_template(
        "edit_benefit.html",
        benefit=benefit,
        projects=projects,
        benefit_history=benefit_history
    )


@app.route("/delete-benefit/<int:benefit_id>")
def delete_benefit(benefit_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Benefits", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM benefit_history
        WHERE benefit_id = %s
    """, (
        benefit_id,
    ))

    cursor.execute("""
        DELETE FROM benefits
        WHERE id = %s
        AND user_id = %s
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

    if not has_permission("Team", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT DISTINCT ON (LOWER(TRIM(name)), LOWER(TRIM(email)))
            *
        FROM team_members
        WHERE user_id = %s
        ORDER BY LOWER(TRIM(name)), LOWER(TRIM(email)), id DESC
    """, (
        session["user_id"],
    ))

    members = cursor.fetchall()

    team_data = []

    total_members = len(members)
    active_members = 0
    unavailable_members = 0
    inactive_members = 0
    high_workload_count = 0
    blocked_work_count = 0

    for member in members:

        cursor.execute("""
            SELECT COUNT(DISTINCT tasks.id) AS total_tasks
            FROM tasks
            JOIN projects ON tasks.project_id = projects.id
            LEFT JOIN task_team_members ON task_team_members.task_id = tasks.id
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
            JOIN projects ON tasks.project_id = projects.id
            LEFT JOIN task_team_members ON task_team_members.task_id = tasks.id
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
            JOIN projects ON tasks.project_id = projects.id
            LEFT JOIN task_team_members ON task_team_members.task_id = tasks.id
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
            JOIN projects ON tasks.project_id = projects.id
            LEFT JOIN task_team_members ON task_team_members.task_id = tasks.id
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

        utilisation = min(active_tasks * 10, 100)

        workload_warning = ""

        if active_tasks >= 8:
            workload_warning = "High workload detected."
            high_workload_count += 1

        blocked_warning = ""

        if blocked_tasks > 0:
            blocked_warning = "Blocked work needs attention."
            blocked_work_count += 1

        if member["status"] == "Active":
            active_members += 1
        elif member["status"] == "Unavailable":
            unavailable_members += 1
        elif member["status"] == "Inactive":
            inactive_members += 1

        cursor.execute("""
            INSERT INTO team_member_history
            (
                team_member_id,
                user_id,
                action,
                total_tasks,
                active_tasks,
                completed_tasks,
                blocked_tasks,
                utilisation,
                notes,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            member["id"],
            session["user_id"],
            "Team member workload snapshot",
            total_tasks,
            active_tasks,
            completed_tasks,
            blocked_tasks,
            utilisation,
            "Automatic team workload snapshot",
            str(date.today())
        ))

        team_data.append({
            "member": member,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "active_tasks": active_tasks,
            "blocked_tasks": blocked_tasks,
            "utilisation": utilisation,
            "workload_warning": workload_warning,
            "blocked_warning": blocked_warning
        })

    conn.commit()
    conn.close()

    return render_template(
        "team.html",
        team_data=team_data,
        total_members=total_members,
        active_members=active_members,
        unavailable_members=unavailable_members,
        inactive_members=inactive_members,
        high_workload_count=high_workload_count,
        blocked_work_count=blocked_work_count
    )


@app.route("/add-team-member", methods=["GET", "POST"])
def add_team_member():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Team", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT id
            FROM team_members
            WHERE user_id = %s
            AND LOWER(TRIM(name)) = LOWER(TRIM(%s))
            AND LOWER(TRIM(email)) = LOWER(TRIM(%s))
            LIMIT 1
        """, (
            session["user_id"],
            request.form.get("name", ""),
            request.form.get("email", "")
        ))

        existing = cursor.fetchone()

        if existing:
            conn.close()
            return redirect("/team")

        cursor.execute("""
            INSERT INTO team_members
            (
                user_id,
                name,
                role,
                email,
                phone,
                skills,
                status,
                manager,
                department,
                employment_status,
                availability,
                certifications,
                training_records,
                performance_notes,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("name", ""),
            request.form.get("role", ""),
            request.form.get("email", ""),
            request.form.get("phone", ""),
            request.form.get("skills", ""),
            request.form.get("status", "Active"),
            request.form.get("manager", ""),
            request.form.get("department", ""),
            request.form.get("employment_status", ""),
            request.form.get("availability", ""),
            request.form.get("certifications", ""),
            request.form.get("training_records", ""),
            request.form.get("performance_notes", ""),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(f"{session['username']} added a team member")

        return redirect("/team")

    return render_template("add_team_member.html")


@app.route("/edit-team-member/<int:member_id>", methods=["GET", "POST"])
def edit_team_member(member_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Team", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM team_members
        WHERE id = %s
        AND user_id = %s
    """, (
        member_id,
        session["user_id"]
    ))

    member = cursor.fetchone()

    if not member:
        conn.close()
        return redirect("/team")

    if request.method == "POST":

        cursor.execute("""
            UPDATE team_members
            SET
                name = %s,
                role = %s,
                email = %s,
                phone = %s,
                skills = %s,
                status = %s,
                manager = %s,
                department = %s,
                employment_status = %s,
                availability = %s,
                certifications = %s,
                training_records = %s,
                performance_notes = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("name", ""),
            request.form.get("role", ""),
            request.form.get("email", ""),
            request.form.get("phone", ""),
            request.form.get("skills", ""),
            request.form.get("status", "Active"),
            request.form.get("manager", ""),
            request.form.get("department", ""),
            request.form.get("employment_status", ""),
            request.form.get("availability", ""),
            request.form.get("certifications", ""),
            request.form.get("training_records", ""),
            request.form.get("performance_notes", ""),
            member_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        create_activity(f"{session['username']} updated a team member")

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

    if not has_permission("Team", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM team_members
        WHERE id = %s
        AND user_id = %s
    """, (
        member_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(f"{session['username']} deleted a team member")

    return redirect("/team")


@app.route("/team-member-history/<int:member_id>")
def team_member_history(member_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Team", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM team_member_history
        WHERE team_member_id = %s
        AND user_id = %s
        ORDER BY id DESC
    """, (
        member_id,
        session["user_id"]
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "team_member_history.html",
        history=history
    )

@app.route("/raid")
def raid():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("RAID", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM risks
        WHERE user_id = %s
        ORDER BY id ASC
    """, (
        session["user_id"],
    ))
    risks = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM assumptions
        WHERE user_id = %s
        ORDER BY id ASC
    """, (
        session["user_id"],
    ))
    assumptions = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM issues
        WHERE user_id = %s
        ORDER BY id ASC
    """, (
        session["user_id"],
    ))
    issues = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM dependencies
        WHERE user_id = %s
        ORDER BY id ASC
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

@app.route("/assumptions")
def assumptions():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("RAID", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
            assumptions.*,
            projects.name AS project_name
        FROM assumptions
        LEFT JOIN projects
        ON assumptions.project_id = projects.id
        WHERE assumptions.user_id = %s
        ORDER BY assumptions.id DESC
    """, (
        session["user_id"],
    ))

    assumptions = cursor.fetchall()

    today = date.today()

    enriched_assumptions = []

    for assumption in assumptions:

        review_status = "No Review Date"

        try:
            if assumption["review_date"]:

                review_date = datetime.strptime(
                    assumption["review_date"],
                    "%Y-%m-%d"
                ).date()

                if review_date < today:
                    review_status = "Review Overdue"
                elif review_date == today:
                    review_status = "Review Due Today"
                else:
                    review_status = "Review Scheduled"

        except Exception:
            review_status = "No Review Date"

        enriched_assumptions.append({
            "assumption": assumption,
            "review_status": review_status
        })

    total_assumptions = len(assumptions)
    validated_assumptions = len([
        assumption for assumption in assumptions
        if assumption["validation_status"] == "Validated"
    ])
    overdue_reviews = len([
        item for item in enriched_assumptions
        if item["review_status"] == "Review Overdue"
    ])
    converted_to_risk = len([
        assumption for assumption in assumptions
        if assumption["converted_to_risk"] == "Yes"
    ])

    conn.close()

    return render_template(
        "assumptions.html",
        assumptions=enriched_assumptions,
        total_assumptions=total_assumptions,
        validated_assumptions=validated_assumptions,
        overdue_reviews=overdue_reviews,
        converted_to_risk=converted_to_risk
    )




@app.route("/edit-assumption/<int:assumption_id>", methods=["GET", "POST"])
def edit_assumption(assumption_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("RAID", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM assumptions
        WHERE id = %s
        AND user_id = %s
    """, (
        assumption_id,
        session["user_id"]
    ))

    assumption = cursor.fetchone()

    if not assumption:
        conn.close()
        return redirect("/assumptions")

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        previous_status = assumption["status"]

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        owner = request.form.get("owner", "")
        status = request.form.get("status", "Open")

        assumption_category = request.form.get("assumption_category", "Delivery")
        review_date = request.form.get("review_date", "")
        validation_status = request.form.get("validation_status", "Unvalidated")
        validation_notes = request.form.get("validation_notes", "")
        converted_to_risk = request.form.get("converted_to_risk", "No")

        cursor.execute("""
            UPDATE assumptions
            SET
                project_id = %s,
                title = %s,
                description = %s,
                owner = %s,
                status = %s,
                assumption_category = %s,
                review_date = %s,
                validation_status = %s,
                validation_notes = %s,
                converted_to_risk = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            project_id if project_id else None,
            title,
            description,
            owner,
            status,
            assumption_category,
            review_date,
            validation_status,
            validation_notes,
            converted_to_risk,
            assumption_id,
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO assumption_history
            (
                assumption_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            assumption_id,
            session["user_id"],
            "Assumption updated",
            previous_status,
            status,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated an assumption"
        )

        return redirect("/assumptions")

    cursor.execute("""
        SELECT *
        FROM assumption_history
        WHERE assumption_id = %s
        ORDER BY id DESC
    """, (
        assumption_id,
    ))

    assumption_history = cursor.fetchall()

    conn.close()

    return render_template(
        "edit_assumption.html",
        assumption=assumption,
        projects=projects,
        assumption_history=assumption_history
    )


@app.route("/delete-assumption/<int:assumption_id>")
def delete_assumption(assumption_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("RAID", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM assumption_history
        WHERE assumption_id = %s
    """, (
        assumption_id,
    ))

    cursor.execute("""
        DELETE FROM assumptions
        WHERE id = %s
        AND user_id = %s
    """, (
        assumption_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} deleted an assumption"
    )

    return redirect("/assumptions")


@app.route("/dependencies")
def dependencies():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("RAID", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
            dependencies.*,
            projects.name AS project_name
        FROM dependencies
        LEFT JOIN projects
        ON dependencies.project_id = projects.id
        WHERE dependencies.user_id = %s
        ORDER BY dependencies.id DESC
    """, (
        session["user_id"],
    ))

    dependencies = cursor.fetchall()

    today = date.today()
    enriched_dependencies = []

    for dependency in dependencies:

        timeline_status = "No Target Date"

        try:
            if dependency["target_date"]:

                target_date = datetime.strptime(
                    dependency["target_date"],
                    "%Y-%m-%d"
                ).date()

                if dependency["status"] in ["Completed", "Closed"]:
                    timeline_status = "Completed"
                elif target_date < today:
                    timeline_status = "Overdue"
                elif target_date == today:
                    timeline_status = "Due Today"
                else:
                    timeline_status = "On Track"

        except Exception:
            timeline_status = "No Target Date"

        enriched_dependencies.append({
            "dependency": dependency,
            "timeline_status": timeline_status
        })

    total_dependencies = len(dependencies)
    critical_dependencies = len([
        dependency for dependency in dependencies
        if dependency["criticality"] == "Critical"
    ])
    overdue_dependencies = len([
        item for item in enriched_dependencies
        if item["timeline_status"] == "Overdue"
    ])
    blocked_dependencies = len([
        dependency for dependency in dependencies
        if dependency["status"] == "Blocked"
    ])

    conn.close()

    return render_template(
        "dependencies.html",
        dependencies=enriched_dependencies,
        total_dependencies=total_dependencies,
        critical_dependencies=critical_dependencies,
        overdue_dependencies=overdue_dependencies,
        blocked_dependencies=blocked_dependencies
    )


@app.route("/add-dependency", methods=["GET", "POST"])
def add_dependency():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("RAID", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        owner = request.form.get("owner", "")
        status = request.form.get("status", "Open")
        target_date = request.form.get("target_date", "")

        dependency_category = request.form.get("dependency_category", "Delivery")
        criticality = request.form.get("criticality", "Medium")
        dependency_type = request.form.get("dependency_type", "Internal")
        source_project_id = request.form.get("source_project_id")
        dependent_project_id = request.form.get("dependent_project_id")
        alert_status = request.form.get("alert_status", "No Alert")
        resolution_plan = request.form.get("resolution_plan", "")

        cursor.execute("""
            INSERT INTO dependencies
            (
                user_id,
                project_id,
                title,
                description,
                owner,
                status,
                target_date,
                dependency_category,
                criticality,
                dependency_type,
                source_project_id,
                dependent_project_id,
                alert_status,
                resolution_plan,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            session["user_id"],
            project_id if project_id else None,
            title,
            description,
            owner,
            status,
            target_date,
            dependency_category,
            criticality,
            dependency_type,
            source_project_id if source_project_id else None,
            dependent_project_id if dependent_project_id else None,
            alert_status,
            resolution_plan,
            str(date.today())
        ))

        dependency_id = cursor.fetchone()["id"]

        cursor.execute("""
            INSERT INTO dependency_history
            (
                dependency_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            dependency_id,
            session["user_id"],
            "Dependency created",
            "",
            status,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} added a dependency"
        )

        return redirect("/dependencies")

    conn.close()

    return render_template(
        "add_dependency.html",
        projects=projects
    )


@app.route("/edit-dependency/<int:dependency_id>", methods=["GET", "POST"])
def edit_dependency(dependency_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("RAID", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM dependencies
        WHERE id = %s
        AND user_id = %s
    """, (
        dependency_id,
        session["user_id"]
    ))

    dependency = cursor.fetchone()

    if not dependency:
        conn.close()
        return redirect("/dependencies")

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        previous_status = dependency["status"]

        project_id = request.form.get("project_id")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        owner = request.form.get("owner", "")
        status = request.form.get("status", "Open")
        target_date = request.form.get("target_date", "")

        dependency_category = request.form.get("dependency_category", "Delivery")
        criticality = request.form.get("criticality", "Medium")
        dependency_type = request.form.get("dependency_type", "Internal")
        source_project_id = request.form.get("source_project_id")
        dependent_project_id = request.form.get("dependent_project_id")
        alert_status = request.form.get("alert_status", "No Alert")
        resolution_plan = request.form.get("resolution_plan", "")

        cursor.execute("""
            UPDATE dependencies
            SET
                project_id = %s,
                title = %s,
                description = %s,
                owner = %s,
                status = %s,
                target_date = %s,
                dependency_category = %s,
                criticality = %s,
                dependency_type = %s,
                source_project_id = %s,
                dependent_project_id = %s,
                alert_status = %s,
                resolution_plan = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            project_id if project_id else None,
            title,
            description,
            owner,
            status,
            target_date,
            dependency_category,
            criticality,
            dependency_type,
            source_project_id if source_project_id else None,
            dependent_project_id if dependent_project_id else None,
            alert_status,
            resolution_plan,
            dependency_id,
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO dependency_history
            (
                dependency_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            dependency_id,
            session["user_id"],
            "Dependency updated",
            previous_status,
            status,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated a dependency"
        )

        return redirect("/dependencies")

    cursor.execute("""
        SELECT *
        FROM dependency_history
        WHERE dependency_id = %s
        ORDER BY id DESC
    """, (
        dependency_id,
    ))

    dependency_history = cursor.fetchall()

    conn.close()

    return render_template(
        "edit_dependency.html",
        dependency=dependency,
        projects=projects,
        dependency_history=dependency_history
    )


@app.route("/delete-dependency/<int:dependency_id>")
def delete_dependency(dependency_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("RAID", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM dependency_history
        WHERE dependency_id = %s
    """, (
        dependency_id,
    ))

    cursor.execute("""
        DELETE FROM dependencies
        WHERE id = %s
        AND user_id = %s
    """, (
        dependency_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} deleted a dependency"
    )

    return redirect("/dependencies")

@app.route("/team-utilisation")
def team_utilisation():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Team", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (LOWER(TRIM(name)), LOWER(TRIM(email)))
            *
        FROM team_members
        WHERE user_id = %s
        ORDER BY LOWER(TRIM(name)), LOWER(TRIM(email)), id DESC
    """, (
        session["user_id"],
    ))

    members = cursor.fetchall()

    utilisation_data = []

    overloaded_count = 0
    balanced_count = 0
    available_count = 0
    burnout_risk_count = 0

    for member in members:

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

        resource_capacity = int(
            member.get("resource_capacity") or 100
        )

        workload_points = active_tasks * 10

        if resource_capacity > 0:
            utilisation = round(
                (workload_points / resource_capacity) * 100
            )
        else:
            utilisation = 0

        utilisation = min(utilisation, 150)

        if utilisation >= 90:

            status = "Overloaded"
            overloaded_count += 1
            burnout_risk = "High"
            burnout_risk_count += 1

        elif utilisation >= 60:

            status = "Balanced"
            balanced_count += 1
            burnout_risk = "Medium"

        else:

            status = "Available"
            available_count += 1
            burnout_risk = "Low"

        utilisation_trend = "Stable"

        if utilisation >= 90:
            utilisation_trend = "Increasing"

        elif utilisation <= 30:
            utilisation_trend = "Underutilised"

        redistribution_recommendation = "No action required."

        if status == "Overloaded":
            redistribution_recommendation = (
                "Redistribute workload immediately."
            )

        elif status == "Available":
            redistribution_recommendation = (
                "Candidate for additional work allocation."
            )

        utilisation_data.append({

            "name": member["name"],
            "role": member.get("role"),
            "department": member.get("department"),
            "active_tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "utilisation": utilisation,
            "status": status,
            "burnout_risk": burnout_risk,
            "utilisation_trend": utilisation_trend,
            "redistribution_recommendation": redistribution_recommendation

        })

    total_members = len(utilisation_data)

    if total_members > 0:

        average_utilisation = round(
            sum(item["utilisation"] for item in utilisation_data)
            / total_members
        )

    else:
        average_utilisation = 0

    average_capacity = max(
        0,
        100 - average_utilisation
    )

    smart_insights = []

    if overloaded_count > 0:
        smart_insights.append(
            f"{overloaded_count} resource(s) require workload reduction."
        )

    if available_count > 0:
        smart_insights.append(
            f"{available_count} resource(s) can absorb additional work."
        )

    if burnout_risk_count > 0:
        smart_insights.append(
            f"{burnout_risk_count} resource(s) have elevated burnout risk."
        )

    if average_utilisation < 50:

        smart_insights.append(
            "Overall team capacity remains healthy."
        )

    elif average_utilisation < 80:

        smart_insights.append(
            "Team utilisation is balanced."
        )

    else:

        smart_insights.append(
            "Team utilisation is approaching critical levels."
        )

    conn.close()

    return render_template(
        "team_utilisation.html",
        utilisation_data=utilisation_data,
        total_members=total_members,
        average_utilisation=average_utilisation,
        average_capacity=average_capacity,
        overloaded_count=overloaded_count,
        balanced_count=balanced_count,
        available_count=available_count,
        burnout_risk_count=burnout_risk_count,
        smart_insights=smart_insights
    )


@app.route("/stakeholders")
def stakeholders():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Stakeholders", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
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
    ))

    stakeholders = cursor.fetchall()

    total_stakeholders = len(stakeholders)
    high_influence = len([
        stakeholder for stakeholder in stakeholders
        if stakeholder["influence"] == "High"
    ])
    high_interest = len([
        stakeholder for stakeholder in stakeholders
        if stakeholder["interest"] == "High"
    ])
    negative_sentiment = len([
        stakeholder for stakeholder in stakeholders
        if stakeholder["sentiment"] == "Negative"
    ])

    conn.close()

    return render_template(
        "stakeholders.html",
        stakeholders=stakeholders,
        total_stakeholders=total_stakeholders,
        high_influence=high_influence,
        high_interest=high_interest,
        negative_sentiment=negative_sentiment
    )


@app.route("/add-stakeholder", methods=["GET", "POST"])
def add_stakeholder():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Stakeholders", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        influence = request.form.get("influence", "Medium")
        interest = request.form.get("interest", "Medium")
        engagement_level = request.form.get("engagement_level", "Neutral")

        score = 0

        if influence == "High":
            score += 30
        elif influence == "Medium":
            score += 20
        else:
            score += 10

        if interest == "High":
            score += 30
        elif interest == "Medium":
            score += 20
        else:
            score += 10

        if engagement_level == "Supportive":
            score += 30
        elif engagement_level == "Neutral":
            score += 20
        else:
            score += 10

        status = request.form.get("status", "Active")

        cursor.execute("""
            INSERT INTO stakeholders
            (
                user_id,
                project_id,
                name,
                role,
                influence,
                interest,
                communication_plan,
                owner,
                status,
                stakeholder_category,
                stakeholder_group,
                engagement_level,
                sentiment,
                engagement_score,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("name"),
            request.form.get("role"),
            influence,
            interest,
            request.form.get("communication_plan"),
            request.form.get("owner"),
            status,
            request.form.get("stakeholder_category", "Internal"),
            request.form.get("stakeholder_group", "Delivery"),
            engagement_level,
            request.form.get("sentiment", "Neutral"),
            score,
            str(date.today())
        ))

        stakeholder_id = cursor.fetchone()["id"]

        cursor.execute("""
            INSERT INTO stakeholder_history
            (
                stakeholder_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            stakeholder_id,
            session["user_id"],
            "Stakeholder created",
            "",
            status,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} added a stakeholder"
        )

        return redirect("/stakeholders")

    conn.close()

    return render_template(
        "add_stakeholder.html",
        projects=projects
    )


@app.route("/edit-stakeholder/<int:stakeholder_id>", methods=["GET", "POST"])
def edit_stakeholder(stakeholder_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Stakeholders", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM stakeholders
        WHERE id = %s
        AND user_id = %s
    """, (
        stakeholder_id,
        session["user_id"]
    ))

    stakeholder = cursor.fetchone()

    if not stakeholder:
        conn.close()
        return redirect("/stakeholders")

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        AND COALESCE(is_archived, FALSE) = FALSE
        ORDER BY name ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    if request.method == "POST":

        previous_status = stakeholder["status"]

        influence = request.form.get("influence", "Medium")
        interest = request.form.get("interest", "Medium")
        engagement_level = request.form.get("engagement_level", "Neutral")

        score = 0

        if influence == "High":
            score += 30
        elif influence == "Medium":
            score += 20
        else:
            score += 10

        if interest == "High":
            score += 30
        elif interest == "Medium":
            score += 20
        else:
            score += 10

        if engagement_level == "Supportive":
            score += 30
        elif engagement_level == "Neutral":
            score += 20
        else:
            score += 10

        status = request.form.get("status", "Active")

        cursor.execute("""
            UPDATE stakeholders
            SET
                project_id = %s,
                name = %s,
                role = %s,
                influence = %s,
                interest = %s,
                communication_plan = %s,
                owner = %s,
                status = %s,
                stakeholder_category = %s,
                stakeholder_group = %s,
                engagement_level = %s,
                sentiment = %s,
                engagement_score = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            request.form.get("name"),
            request.form.get("role"),
            influence,
            interest,
            request.form.get("communication_plan"),
            request.form.get("owner"),
            status,
            request.form.get("stakeholder_category", "Internal"),
            request.form.get("stakeholder_group", "Delivery"),
            engagement_level,
            request.form.get("sentiment", "Neutral"),
            score,
            stakeholder_id,
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO stakeholder_history
            (
                stakeholder_id,
                user_id,
                action,
                previous_status,
                new_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            stakeholder_id,
            session["user_id"],
            "Stakeholder updated",
            previous_status,
            status,
            str(date.today())
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated a stakeholder"
        )

        return redirect("/stakeholders")

    cursor.execute("""
        SELECT *
        FROM stakeholder_history
        WHERE stakeholder_id = %s
        ORDER BY id DESC
    """, (
        stakeholder_id,
    ))

    stakeholder_history = cursor.fetchall()

    conn.close()

    return render_template(
        "edit_stakeholder.html",
        stakeholder=stakeholder,
        projects=projects,
        stakeholder_history=stakeholder_history
    )


@app.route("/delete-stakeholder/<int:stakeholder_id>")
def delete_stakeholder(stakeholder_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Stakeholders", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM stakeholder_history
        WHERE stakeholder_id = %s
    """, (
        stakeholder_id,
    ))

    cursor.execute("""
        DELETE FROM stakeholders
        WHERE id = %s
        AND user_id = %s
    """, (
        stakeholder_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} deleted a stakeholder"
    )

    return redirect("/stakeholders")


@app.route("/decisions")
def decisions():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Decisions", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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

    cursor.execute("""
        SELECT
            COUNT(*) AS total_decisions,

            COUNT(*) FILTER (
                WHERE status = 'Approved'
            ) AS approved_decisions,

            COUNT(*) FILTER (
                WHERE status = 'Pending'
            ) AS pending_decisions,

            COUNT(*) FILTER (
                WHERE status = 'Rejected'
            ) AS rejected_decisions,

            COUNT(*) FILTER (
                WHERE impact = 'High'
            ) AS high_impact_decisions,

            COUNT(*) FILTER (
                WHERE auto_created = 'Yes'
            ) AS auto_created_decisions,

            ROUND(AVG(effectiveness_score), 1) AS avg_effectiveness_score

        FROM decisions
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    stats = cursor.fetchone()

    conn.close()

    return render_template(
        "decisions.html",
        decisions=decisions,
        stats=stats
    )


@app.route("/add-decision", methods=["GET", "POST"])
def add_decision():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Decisions", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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
            INSERT INTO decisions
            (
                user_id,
                project_id,
                title,
                decision_maker,
                impact,
                reason,
                status,
                decision_date,
                decision_category,
                decision_source,
                effectiveness_score,
                effectiveness_notes,
                linked_risk_id,
                linked_change_id,
                linked_governance_review_id,
                auto_created,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("decision_maker"),
            request.form.get("impact"),
            request.form.get("reason"),
            request.form.get("status"),
            request.form.get("decision_date") or None,
            request.form.get("decision_category"),
            request.form.get("decision_source"),
            request.form.get("effectiveness_score") or 0,
            request.form.get("effectiveness_notes"),
            request.form.get("linked_risk_id") or None,
            request.form.get("linked_change_id") or None,
            request.form.get("linked_governance_review_id") or None,
            request.form.get("auto_created")
        ))

        conn.commit()
        conn.close()

        return redirect("/decisions")

    conn.close()

    return render_template(
        "add_decision.html",
        projects=projects
    )


@app.route("/edit-decision/<int:decision_id>", methods=["GET", "POST"])
def edit_decision(decision_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Decisions", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM decisions
        WHERE id = %s
        AND user_id = %s
    """, (
        decision_id,
        session["user_id"]
    ))

    decision = cursor.fetchone()

    if not decision:
        conn.close()
        return redirect("/decisions")

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

        old_status = decision["status"]
        new_status = request.form.get("status")

        cursor.execute("""
            UPDATE decisions
            SET
                project_id = %s,
                title = %s,
                decision_maker = %s,
                impact = %s,
                reason = %s,
                status = %s,
                decision_date = %s,
                decision_category = %s,
                decision_source = %s,
                effectiveness_score = %s,
                effectiveness_notes = %s,
                linked_risk_id = %s,
                linked_change_id = %s,
                linked_governance_review_id = %s,
                auto_created = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("decision_maker"),
            request.form.get("impact"),
            request.form.get("reason"),
            new_status,
            request.form.get("decision_date") or None,
            request.form.get("decision_category"),
            request.form.get("decision_source"),
            request.form.get("effectiveness_score") or 0,
            request.form.get("effectiveness_notes"),
            request.form.get("linked_risk_id") or None,
            request.form.get("linked_change_id") or None,
            request.form.get("linked_governance_review_id") or None,
            request.form.get("auto_created"),
            decision_id,
            session["user_id"]
        ))

        if old_status != new_status:
            cursor.execute("""
                INSERT INTO decision_history
                (
                    decision_id,
                    user_id,
                    old_status,
                    new_status,
                    change_note
                )
                VALUES (%s,%s,%s,%s,%s)
            """, (
                decision_id,
                session["user_id"],
                old_status,
                new_status,
                "Decision status changed"
            ))

        conn.commit()
        conn.close()

        return redirect("/decisions")

    conn.close()

    return render_template(
        "edit_decision.html",
        decision=decision,
        projects=projects
    )


@app.route("/decision-history/<int:decision_id>")
def decision_history(decision_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Decisions", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM decisions
        WHERE id = %s
        AND user_id = %s
    """, (
        decision_id,
        session["user_id"]
    ))

    decision = cursor.fetchone()

    if not decision:
        conn.close()
        return redirect("/decisions")

    cursor.execute("""
        SELECT *
        FROM decision_history
        WHERE decision_id = %s
        AND user_id = %s
        ORDER BY changed_at DESC
    """, (
        decision_id,
        session["user_id"]
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "decision_history.html",
        decision=decision,
        history=history
    )


@app.route("/delete-decision/<int:decision_id>")
def delete_decision(decision_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Decisions", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM decision_history
        WHERE decision_id = %s
        AND user_id = %s
    """, (
        decision_id,
        session["user_id"]
    ))

    cursor.execute("""
        DELETE FROM decisions
        WHERE id = %s
        AND user_id = %s
    """, (
        decision_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/decisions")


@app.route("/actions")
def actions():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Actions", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            actions.*,
            projects.name AS project_name,

            CASE
                WHEN actions.status != 'Completed'
                AND actions.due_date IS NOT NULL
                AND actions.due_date != ''
                AND TO_DATE(actions.due_date, 'YYYY-MM-DD') < CURRENT_DATE
                THEN 'Yes'
                ELSE 'No'
            END AS is_overdue,

            CASE
                WHEN actions.status != 'Completed'
                AND actions.reminder_date IS NOT NULL
                AND actions.reminder_date <= CURRENT_DATE
                THEN 'Yes'
                ELSE 'No'
            END AS reminder_due

        FROM actions
        LEFT JOIN projects
        ON actions.project_id = projects.id

        WHERE actions.user_id = %s

        ORDER BY
            CASE
                WHEN actions.status = 'Completed' THEN 6
                WHEN actions.due_date IS NOT NULL
                AND actions.due_date != ''
                AND TO_DATE(actions.due_date, 'YYYY-MM-DD') < CURRENT_DATE THEN 1
                WHEN actions.escalation_level = 'High' THEN 2
                WHEN actions.status = 'Blocked' THEN 3
                WHEN actions.priority = 'High' THEN 4
                WHEN actions.status = 'In Progress' THEN 5
                ELSE 7
            END,
            actions.due_date ASC
    """, (
        session["user_id"],
    ))

    actions = cursor.fetchall()

    cursor.execute("""
        SELECT
            COUNT(*) AS total_actions,

            COUNT(*) FILTER (
                WHERE status = 'Completed'
            ) AS completed_actions,

            COUNT(*) FILTER (
                WHERE status != 'Completed'
                AND due_date IS NOT NULL
                AND due_date != ''
                AND TO_DATE(due_date, 'YYYY-MM-DD') < CURRENT_DATE
            ) AS overdue_actions,

            COUNT(*) FILTER (
                WHERE status = 'Blocked'
            ) AS blocked_actions,

            COUNT(*) FILTER (
                WHERE priority = 'High'
            ) AS high_priority_actions,

            COUNT(*) FILTER (
                WHERE status != 'Completed'
                AND reminder_date IS NOT NULL
                AND reminder_date <= CURRENT_DATE
            ) AS reminders_due,

            COUNT(*) FILTER (
                WHERE escalation_level != 'None'
            ) AS escalated_actions

        FROM actions
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    stats = cursor.fetchone()

    conn.close()

    return render_template(
        "actions.html",
        actions=actions,
        stats=stats
    )



@app.route("/add-action", methods=["GET", "POST"])
def add_action():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Actions", "create"):
        return "Access denied"

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
            INSERT INTO actions
            (
                user_id,
                project_id,
                title,
                description,
                owner,
                priority,
                status,
                due_date,
                category,
                reminder_date,
                escalation_level,
                recurring,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("description"),
            request.form.get("owner"),
            request.form.get("priority"),
            request.form.get("status"),
            request.form.get("due_date"),
            request.form.get("category"),
            request.form.get("reminder_date") or None,
            request.form.get("escalation_level"),
            request.form.get("recurring")
        ))

        conn.commit()
        conn.close()

        return redirect("/actions")

    conn.close()

    return render_template(
        "add_action.html",
        projects=projects
    )

@app.route("/edit-action/<int:action_id>", methods=["GET", "POST"])
def edit_action(action_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Actions", "edit"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM actions
        WHERE id = %s
        AND user_id = %s
    """, (
        action_id,
        session["user_id"]
    ))

    action = cursor.fetchone()

    if not action:
        conn.close()
        return "Action not found"

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

        old_status = action["status"]
        new_status = request.form.get("status")

        cursor.execute("""
            UPDATE actions
            SET
                project_id = %s,
                title = %s,
                description = %s,
                owner = %s,
                priority = %s,
                status = %s,
                due_date = %s,
                category = %s,
                reminder_date = %s,
                escalation_level = %s,
                recurring = %s,
                completed_date = CASE
                    WHEN %s = 'Completed' THEN CURRENT_DATE
                    ELSE completed_date
                END
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("description"),
            request.form.get("owner"),
            request.form.get("priority"),
            new_status,
            request.form.get("due_date"),
            request.form.get("category"),
            request.form.get("reminder_date") or None,
            request.form.get("escalation_level"),
            request.form.get("recurring"),
            new_status,
            action_id,
            session["user_id"]
        ))

        if old_status != new_status:
            cursor.execute("""
                INSERT INTO action_history
                (
                    action_id,
                    user_id,
                    change_note,
                    old_status,
                    new_status
                )
                VALUES (%s,%s,%s,%s,%s)
            """, (
                action_id,
                session["user_id"],
                "Action status changed",
                old_status,
                new_status
            ))

        conn.commit()
        conn.close()

        return redirect("/actions")

    conn.close()

    return render_template(
        "edit_action.html",
        action=action,
        projects=projects
    )


@app.route("/delete-action/<int:action_id>")
def delete_action(action_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Actions", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM action_history
        WHERE action_id = %s
        AND user_id = %s
    """, (
        action_id,
        session["user_id"]
    ))

    cursor.execute("""
        DELETE FROM actions
        WHERE id = %s
        AND user_id = %s
    """, (
        action_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/actions")

@app.route("/action-history/<int:action_id>")
def action_history(action_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Actions", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM actions
        WHERE id = %s
        AND user_id = %s
    """, (
        action_id,
        session["user_id"]
    ))

    action = cursor.fetchone()

    if not action:
        conn.close()
        return "Action not found"

    cursor.execute("""
        SELECT *
        FROM action_history
        WHERE action_id = %s
        AND user_id = %s
        ORDER BY changed_at DESC
    """, (
        action_id,
        session["user_id"]
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "action_history.html",
        action=action,
        history=history
    )

@app.route("/lessons")
def lessons():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Lessons", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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

    cursor.execute("""
        SELECT
            COUNT(*) AS total_lessons,

            COUNT(*) FILTER (
                WHERE status = 'Open'
            ) AS open_lessons,

            COUNT(*) FILTER (
                WHERE status = 'In Progress'
            ) AS in_progress_lessons,

            COUNT(*) FILTER (
                WHERE status = 'Completed'
            ) AS completed_lessons,

            COUNT(*) FILTER (
                WHERE implementation_status = 'Implemented'
            ) AS implemented_lessons,

            COUNT(*) FILTER (
                WHERE reusable = 'Yes'
            ) AS reusable_lessons,

            ROUND(AVG(effectiveness_score), 1) AS avg_effectiveness_score

        FROM lessons
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    stats = cursor.fetchone()

    conn.close()

    return render_template(
        "lessons.html",
        lessons=lessons,
        stats=stats
    )


@app.route("/add-lesson", methods=["GET", "POST"])
def add_lesson():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Lessons", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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
            INSERT INTO lessons
            (
                user_id,
                project_id,
                title,
                category,
                what_happened,
                what_went_well,
                what_went_wrong,
                recommendation,
                owner,
                status,
                root_cause,
                actions_taken,
                implementation_status,
                reusable,
                knowledge_area,
                effectiveness_score,
                effectiveness_notes,
                review_date,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("category"),
            request.form.get("what_happened"),
            request.form.get("what_went_well"),
            request.form.get("what_went_wrong"),
            request.form.get("recommendation"),
            request.form.get("owner"),
            request.form.get("status"),
            request.form.get("root_cause"),
            request.form.get("actions_taken"),
            request.form.get("implementation_status"),
            request.form.get("reusable"),
            request.form.get("knowledge_area"),
            request.form.get("effectiveness_score") or 0,
            request.form.get("effectiveness_notes"),
            request.form.get("review_date") or None
        ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} added a lesson learned"
        )

        return redirect("/lessons")

    conn.close()

    return render_template(
        "add_lesson.html",
        projects=projects
    )


@app.route("/edit-lesson/<int:lesson_id>", methods=["GET", "POST"])
def edit_lesson(lesson_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Lessons", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM lessons
        WHERE id = %s
        AND user_id = %s
    """, (
        lesson_id,
        session["user_id"]
    ))

    lesson = cursor.fetchone()

    if not lesson:
        conn.close()
        return redirect("/lessons")

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

        old_status = lesson["status"]
        new_status = request.form.get("status")

        cursor.execute("""
            UPDATE lessons
            SET
                project_id = %s,
                title = %s,
                category = %s,
                what_happened = %s,
                what_went_well = %s,
                what_went_wrong = %s,
                recommendation = %s,
                owner = %s,
                status = %s,
                root_cause = %s,
                actions_taken = %s,
                implementation_status = %s,
                reusable = %s,
                knowledge_area = %s,
                effectiveness_score = %s,
                effectiveness_notes = %s,
                review_date = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            request.form.get("title"),
            request.form.get("category"),
            request.form.get("what_happened"),
            request.form.get("what_went_well"),
            request.form.get("what_went_wrong"),
            request.form.get("recommendation"),
            request.form.get("owner"),
            new_status,
            request.form.get("root_cause"),
            request.form.get("actions_taken"),
            request.form.get("implementation_status"),
            request.form.get("reusable"),
            request.form.get("knowledge_area"),
            request.form.get("effectiveness_score") or 0,
            request.form.get("effectiveness_notes"),
            request.form.get("review_date") or None,
            lesson_id,
            session["user_id"]
        ))

        if old_status != new_status:
            cursor.execute("""
                INSERT INTO lesson_history
                (
                    lesson_id,
                    user_id,
                    old_status,
                    new_status,
                    change_note
                )
                VALUES (%s,%s,%s,%s,%s)
            """, (
                lesson_id,
                session["user_id"],
                old_status,
                new_status,
                "Lesson status changed"
            ))

        conn.commit()
        conn.close()

        create_activity(
            f"{session['username']} updated a lesson learned"
        )

        return redirect("/lessons")

    conn.close()

    return render_template(
        "edit_lesson.html",
        lesson=lesson,
        projects=projects
    )


@app.route("/lesson-history/<int:lesson_id>")
def lesson_history(lesson_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Lessons", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM lessons
        WHERE id = %s
        AND user_id = %s
    """, (
        lesson_id,
        session["user_id"]
    ))

    lesson = cursor.fetchone()

    if not lesson:
        conn.close()
        return redirect("/lessons")

    cursor.execute("""
        SELECT *
        FROM lesson_history
        WHERE lesson_id = %s
        AND user_id = %s
        ORDER BY changed_at DESC
    """, (
        lesson_id,
        session["user_id"]
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "lesson_history.html",
        lesson=lesson,
        history=history
    )


@app.route("/delete-lesson/<int:lesson_id>")
def delete_lesson(lesson_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Lessons", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM lesson_history
        WHERE lesson_id = %s
        AND user_id = %s
    """, (
        lesson_id,
        session["user_id"]
    ))

    cursor.execute("""
        DELETE FROM lessons
        WHERE id = %s
        AND user_id = %s
    """, (
        lesson_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    create_activity(
        f"{session['username']} deleted a lesson learned"
    )

    return redirect("/lessons")


@app.route("/budgets")
def budgets():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Budgets", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (budgets.id)
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

    enriched_budgets = []

    total_budget = 0
    total_actual_cost = 0
    total_forecast_cost = 0
    total_baseline = 0

    over_budget_count = 0
    over_forecast_count = 0
    under_budget_count = 0

    approved_count = 0
    pending_count = 0
    rejected_count = 0

    capex_total = 0
    opex_total = 0

    for budget in budgets:

        budget_amount = float(budget["budget_amount"] or 0)
        actual_cost = float(budget["actual_cost"] or 0)
        forecast_cost = float(budget["forecast_cost"] or 0)
        budget_baseline = float(budget.get("budget_baseline") or 0)

        total_budget += budget_amount
        total_actual_cost += actual_cost
        total_forecast_cost += forecast_cost
        total_baseline += budget_baseline

        remaining_budget = budget_amount - actual_cost
        variance = budget_amount - actual_cost
        forecast_variance = budget_amount - forecast_cost
        baseline_variance = budget_amount - budget_baseline

        if budget_amount > 0:
            usage_percent = round((actual_cost / budget_amount) * 100)
            forecast_usage_percent = round((forecast_cost / budget_amount) * 100)
        else:
            usage_percent = 0
            forecast_usage_percent = 0

        if actual_cost > budget_amount:
            budget_status = "Over Budget"
            over_budget_count += 1
        elif forecast_cost > budget_amount:
            budget_status = "Forecast Risk"
            over_forecast_count += 1
        elif actual_cost < budget_amount:
            budget_status = "Under Budget"
            under_budget_count += 1
        else:
            budget_status = "On Budget"

        if budget.get("status") == "Approved":
            approved_count += 1
        elif budget.get("status") == "Pending":
            pending_count += 1
        elif budget.get("status") == "Rejected":
            rejected_count += 1

        if budget.get("capex_opex") == "CAPEX":
            capex_total += budget_amount
        elif budget.get("capex_opex") == "OPEX":
            opex_total += budget_amount

        approver = (
            budget.get("budget_approver")
            or budget.get("approved_by")
            or "Not assigned"
        )

        owner = budget.get("budget_owner") or "Not assigned"

        enriched_budgets.append({
            "budget": budget,
            "budget_amount": budget_amount,
            "actual_cost": actual_cost,
            "forecast_cost": forecast_cost,
            "budget_baseline": budget_baseline,
            "remaining_budget": remaining_budget,
            "variance": variance,
            "forecast_variance": forecast_variance,
            "baseline_variance": baseline_variance,
            "usage_percent": usage_percent,
            "forecast_usage_percent": forecast_usage_percent,
            "budget_status": budget_status,
            "approver": approver,
            "owner": owner
        })

    total_remaining_budget = total_budget - total_actual_cost
    total_variance = total_budget - total_actual_cost
    total_forecast_variance = total_budget - total_forecast_cost
    total_baseline_variance = total_budget - total_baseline

    if total_budget > 0:
        budget_usage = round((total_actual_cost / total_budget) * 100)
        forecast_usage = round((total_forecast_cost / total_budget) * 100)
    else:
        budget_usage = 0
        forecast_usage = 0

    if over_budget_count > 0 or budget_usage > 90:
        financial_health = "Red"
        financial_health_message = "Budget usage is high and requires immediate attention."
    elif budget_usage > 70 or over_forecast_count > 0:
        financial_health = "Amber"
        financial_health_message = "Budget usage requires monitoring."
    else:
        financial_health = "Green"
        financial_health_message = "Financial position is currently healthy."

    if over_budget_count > 0:
        financial_risk_level = "High"
        financial_recommendation = "Review overspending, validate forecasts and reduce non-critical costs."
    elif over_forecast_count > 0 or budget_usage >= 80:
        financial_risk_level = "Medium"
        financial_recommendation = "Monitor forecast pressure and review budget owners."
    else:
        financial_risk_level = "Low"
        financial_recommendation = "Financial position is currently stable."

    conn.close()

    return render_template(
        "budgets.html",
        budgets=enriched_budgets,
        total_budget=total_budget,
        total_actual_cost=total_actual_cost,
        total_forecast_cost=total_forecast_cost,
        total_baseline=total_baseline,
        total_remaining_budget=total_remaining_budget,
        remaining_budget=total_remaining_budget,
        total_variance=total_variance,
        total_forecast_variance=total_forecast_variance,
        total_baseline_variance=total_baseline_variance,
        budget_usage=budget_usage,
        forecast_usage=forecast_usage,
        over_budget_count=over_budget_count,
        over_forecast_count=over_forecast_count,
        under_budget_count=under_budget_count,
        approved_count=approved_count,
        pending_count=pending_count,
        rejected_count=rejected_count,
        capex_total=capex_total,
        opex_total=opex_total,
        financial_health=financial_health,
        financial_health_message=financial_health_message,
        forecast_variance=total_forecast_variance,
        financial_risk_level=financial_risk_level,
        financial_recommendation=financial_recommendation
    )

@app.route("/add-budget", methods=["GET", "POST"])
def add_budget():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Budgets", "create"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    if request.method == "POST":

        budget_amount = float(request.form.get("budget_amount") or 0)
        actual_cost = float(request.form.get("actual_cost") or 0)
        forecast_cost = float(request.form.get("forecast_cost") or 0)
        budget_baseline = float(request.form.get("budget_baseline") or 0)
        baseline_forecast = float(request.form.get("baseline_forecast") or 0)

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
                budget_owner,
                budget_approver,
                budget_baseline,
                budget_category,
                funding_source,
                capex_opex,
                approval_date,
                budget_notes,
                cost_centre,
                programme_link,
                portfolio_link,
                baseline_forecast,
                forecast_owner,
                forecast_approver,
                forecast_assumptions,
                forecast_version,
                forecast_confidence,
                forecast_approval_status,
                created_at
            )
            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s
            )
            RETURNING id
        """, (
            session["user_id"],
            request.form.get("project_id"),
            budget_amount,
            actual_cost,
            forecast_cost,
            request.form.get("approved_by"),
            request.form.get("status"),
            request.form.get("budget_owner"),
            request.form.get("budget_approver"),
            budget_baseline,
            request.form.get("budget_category"),
            request.form.get("funding_source"),
            request.form.get("capex_opex"),
            request.form.get("approval_date"),
            request.form.get("budget_notes"),
            request.form.get("cost_centre"),
            request.form.get("programme_link"),
            request.form.get("portfolio_link"),
            baseline_forecast,
            request.form.get("forecast_owner"),
            request.form.get("forecast_approver"),
            request.form.get("forecast_assumptions"),
            request.form.get("forecast_version"),
            request.form.get("forecast_confidence"),
            request.form.get("forecast_approval_status"),
            str(date.today())
        ))

        budget_id = cursor.fetchone()["id"]

        cursor.execute("""
            INSERT INTO budget_history
            (
                budget_id,
                user_id,
                action,
                old_budget_amount,
                new_budget_amount,
                old_actual_cost,
                new_actual_cost,
                old_forecast_cost,
                new_forecast_cost,
                change_note,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            budget_id,
            session["user_id"],
            "Budget created",
            0,
            budget_amount,
            0,
            actual_cost,
            0,
            forecast_cost,
            "Initial budget record created",
            str(date.today())
        ))

        cursor.execute("""
            INSERT INTO forecast_history
            (
                budget_id,
                user_id,
                action,
                old_forecast_cost,
                new_forecast_cost,
                old_actual_cost,
                new_actual_cost,
                forecast_version,
                change_note,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            budget_id,
            session["user_id"],
            "Forecast created",
            0,
            forecast_cost,
            0,
            actual_cost,
            request.form.get("forecast_version"),
            "Initial forecast record created",
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

@app.route("/edit-budget/<int:budget_id>", methods=["GET", "POST"])
def edit_budget(budget_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Budgets", "edit"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM budgets
        WHERE id = %s
        AND user_id = %s
    """, (
        budget_id,
        session["user_id"]
    ))

    budget = cursor.fetchone()

    if not budget:
        conn.close()
        return redirect("/budgets")

    if request.method == "POST":

        old_budget_amount = float(budget["budget_amount"] or 0)
        old_actual_cost = float(budget["actual_cost"] or 0)
        old_forecast_cost = float(budget["forecast_cost"] or 0)

        new_budget_amount = float(
            request.form.get("budget_amount") or 0
        )

        new_actual_cost = float(
            request.form.get("actual_cost") or 0
        )

        new_forecast_cost = float(
            request.form.get("forecast_cost") or 0
        )

        cursor.execute("""
            UPDATE budgets
            SET
                project_id = %s,
                budget_amount = %s,
                actual_cost = %s,
                forecast_cost = %s,
                approved_by = %s,
                status = %s,
                budget_owner = %s,
                budget_approver = %s,
                budget_baseline = %s,
                budget_category = %s,
                funding_source = %s,
                capex_opex = %s,
                approval_date = %s,
                budget_notes = %s,
                cost_centre = %s,
                programme_link = %s,
                portfolio_link = %s,

                baseline_forecast = %s,
                forecast_owner = %s,
                forecast_approver = %s,
                forecast_assumptions = %s,
                forecast_version = %s,
                forecast_confidence = %s,
                forecast_approval_status = %s

            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            new_budget_amount,
            new_actual_cost,
            new_forecast_cost,
            request.form.get("approved_by"),
            request.form.get("status"),
            request.form.get("budget_owner"),
            request.form.get("budget_approver"),
            request.form.get("budget_baseline") or 0,
            request.form.get("budget_category"),
            request.form.get("funding_source"),
            request.form.get("capex_opex"),
            request.form.get("approval_date"),
            request.form.get("budget_notes"),
            request.form.get("cost_centre"),
            request.form.get("programme_link"),
            request.form.get("portfolio_link"),

            request.form.get("baseline_forecast") or 0,
            request.form.get("forecast_owner"),
            request.form.get("forecast_approver"),
            request.form.get("forecast_assumptions"),
            request.form.get("forecast_version"),
            request.form.get("forecast_confidence"),
            request.form.get("forecast_approval_status"),

            budget_id,
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO budget_history
            (
                budget_id,
                user_id,
                action,
                old_budget_amount,
                new_budget_amount,
                old_actual_cost,
                new_actual_cost,
                old_forecast_cost,
                new_forecast_cost,
                change_note,
                created_at
            )
            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
        """, (
            budget_id,
            session["user_id"],
            "Budget Updated",
            old_budget_amount,
            new_budget_amount,
            old_actual_cost,
            new_actual_cost,
            old_forecast_cost,
            new_forecast_cost,
            request.form.get("change_note"),
            str(date.today())
        ))

        cursor.execute("""
            INSERT INTO forecast_history
            (
                budget_id,
                user_id,
                action,
                old_forecast_cost,
                new_forecast_cost,
                old_actual_cost,
                new_actual_cost,
                forecast_version,
                change_note,
                created_at
            )
            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
        """, (
            budget_id,
            session["user_id"],
            "Forecast Updated",
            old_forecast_cost,
            new_forecast_cost,
            old_actual_cost,
            new_actual_cost,
            request.form.get("forecast_version"),
            request.form.get("change_note"),
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
        "edit_budget.html",
        budget=budget,
        projects=projects
    )


@app.route("/delete-budget/<int:budget_id>")
def delete_budget(budget_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Budgets", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM budgets
        WHERE id = %s
        AND user_id = %s
    """, (
        budget_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/budgets")


@app.route("/budget-history/<int:budget_id>")
def budget_history(budget_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Budgets", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM budget_history
        WHERE budget_id = %s
        ORDER BY id DESC
    """, (
        budget_id,
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "budget_history.html",
        history=history
    )


@app.route("/project-health")
def project_health():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Project Health", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    user_id = session["user_id"]

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY name
    """, (
        user_id,
    ))

    projects = cursor.fetchall()

    project_scores = []

    for project in projects:

        project_id = project["id"]

        cursor.execute("""
            SELECT *
            FROM tasks
            WHERE project_id = %s
        """, (
            project_id,
        ))

        tasks = cursor.fetchall()

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

        blocked_tasks = len([
            task for task in tasks
            if task["status"] == "Blocked"
        ])

        if project["status"] == "Planning":
            schedule_score = 70

        else:
            schedule_score = calculate_weighted_progress(tasks)

            if overdue_tasks > 0:
                schedule_score -= overdue_tasks * 8

            if blocked_tasks > 0:
                schedule_score -= blocked_tasks * 6

        schedule_score = max(
            0,
            min(100, schedule_score)
        )

        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE severity_score >= 6 AND status != 'Closed') AS high_risks,
                COUNT(*) FILTER (WHERE severity_score >= 3 AND severity_score < 6 AND status != 'Closed') AS medium_risks,
                COUNT(*) FILTER (WHERE severity_score < 3 AND status != 'Closed') AS low_risks
            FROM risks
            WHERE project_id = %s
        """, (
            project_id,
        ))

        risk_data = cursor.fetchone()

        high_risks = risk_data["high_risks"] or 0
        medium_risks = risk_data["medium_risks"] or 0
        low_risks = risk_data["low_risks"] or 0

        cursor.execute("""
            SELECT COUNT(*) AS open_issues
            FROM issues
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project_id,
        ))

        open_issues = cursor.fetchone()["open_issues"] or 0

        risk_score = calculate_risk_health(
            high_risks,
            medium_risks,
            low_risks,
            open_issues
        )

        cursor.execute("""
            SELECT *
            FROM budgets
            WHERE project_id = %s
            LIMIT 1
        """, (
            project_id,
        ))

        budget = cursor.fetchone()

        if budget:
            budget_score = calculate_financial_health(
                budget["budget_amount"],
                budget["actual_cost"]
            )
        else:
            budget_score = 50

        overall_health = round(
            (
                schedule_score * 0.4 +
                risk_score * 0.35 +
                budget_score * 0.25
            )
        )

        status = get_health_status(overall_health)

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

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    user_id = session["user_id"]

    cursor.execute("""
        SELECT COUNT(*) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (user_id,))
    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS total_tasks
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
    """, (user_id,))
    total_tasks = cursor.fetchone()["total_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS completed_tasks
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Completed'
    """, (user_id,))
    completed_tasks = cursor.fetchone()["completed_tasks"]

    cursor.execute("""
                   SELECT COUNT(*) AS in_progress_tasks
                   FROM tasks
                            JOIN projects ON tasks.project_id = projects.id
                   WHERE projects.user_id = %s
                     AND tasks.status = 'In Progress'
                   """, (user_id,))
    in_progress_tasks = cursor.fetchone()["in_progress_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS overdue_tasks
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status != 'Completed'
        AND tasks.due_date IS NOT NULL
        AND tasks.due_date != ''
        AND TO_DATE(tasks.due_date, 'YYYY-MM-DD') < CURRENT_DATE
    """, (user_id,))
    overdue_tasks = cursor.fetchone()["overdue_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS blocked_tasks
        FROM tasks
        JOIN projects ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Blocked'
    """, (user_id,))
    blocked_tasks = cursor.fetchone()["blocked_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS over_budget_projects
        FROM budgets
        WHERE user_id = %s
        AND actual_cost > budget_amount
    """, (user_id,))
    over_budget_projects = cursor.fetchone()["over_budget_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS total_risks
        FROM risks
        WHERE user_id = %s
        AND status != 'Closed'
    """, (user_id,))
    total_risks = cursor.fetchone()["total_risks"]

    cursor.execute("""
        SELECT COUNT(*) AS total_issues
        FROM issues
        WHERE user_id = %s
        AND status != 'Closed'
    """, (user_id,))
    total_issues = cursor.fetchone()["total_issues"]

    cursor.execute("""
        SELECT COUNT(*) AS high_risks
        FROM risks
        WHERE user_id = %s
        AND severity_score >= 6
        AND status != 'Closed'
    """, (user_id,))
    high_risks = cursor.fetchone()["high_risks"]

    cursor.execute("""
        SELECT COUNT(*) AS total_benefits
        FROM benefits
        WHERE user_id = %s
    """, (user_id,))
    total_benefits = cursor.fetchone()["total_benefits"]

    cursor.execute("""
        SELECT COUNT(*) AS realised_benefits
        FROM benefits
        WHERE user_id = %s
        AND status = 'Realised'
    """, (user_id,))
    realised_benefits = cursor.fetchone()["realised_benefits"]

    if total_benefits > 0:
        benefits_health = round((realised_benefits / total_benefits) * 100)
    else:
        benefits_health = 50

    cursor.execute("""
        SELECT
            COALESCE(SUM(budget_amount), 0) AS total_budget,
            COALESCE(SUM(actual_cost), 0) AS total_actual
        FROM budgets
        WHERE user_id = %s
    """, (user_id,))

    budget_data = cursor.fetchone()

    total_budget = float(budget_data["total_budget"] or 0)
    total_actual = float(budget_data["total_actual"] or 0)

    if total_budget > 0:
        budget_usage = round((total_actual / total_budget) * 100)
    else:
        budget_usage = 0

    financial_health = calculate_financial_health(
        total_budget,
        total_actual
    )

    if total_tasks > 0:
        completion_rate = round((completed_tasks / total_tasks) * 100)
    else:
        completion_rate = 0

    # Stable Risk Health Formula
    medium_risks = max(total_risks - high_risks, 0)
    low_risks = 0

    risk_health = calculate_risk_health(
        high_risks,
        medium_risks,
        low_risks,
        total_issues
    )

    # Stable Portfolio Health Formula
    delivery_score = completion_rate
    governance_score = risk_health
    finance_score = financial_health

    portfolio_health = round(
        (
            delivery_score * 0.4 +
            governance_score * 0.35 +
            finance_score * 0.25
        )
    )

    portfolio_health -= overdue_tasks * 5
    portfolio_health -= blocked_tasks * 7
    portfolio_health -= over_budget_projects * 8
    portfolio_health = max(0, min(100, portfolio_health))

    cursor.execute("""
        SELECT COUNT(*) AS total_team_members
        FROM team_members
        WHERE user_id = %s
    """, (user_id,))
    total_team_members = cursor.fetchone()["total_team_members"]

    active_tasks = total_tasks - completed_tasks

    if total_team_members > 0:
        tasks_per_person = round(active_tasks / total_team_members, 1)

        if tasks_per_person <= 3:
            resource_health = 90
        elif tasks_per_person <= 6:
            resource_health = 75
        elif tasks_per_person <= 10:
            resource_health = 60
        else:
            resource_health = 40
    else:
        tasks_per_person = 0
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

    executive_status = get_health_status(
        overall_executive_health
    )

    executive_recommendations = []

    if portfolio_health < 60:
        executive_recommendations.append(
            "Portfolio delivery needs closer management attention."
        )

    if risk_health < 70:
        executive_recommendations.append(
            f"Review {high_risks} high-severity risk(s)."
        )

    if financial_health < 70:
        executive_recommendations.append(
            "Budget usage requires monitoring."
        )

    if resource_health < 70:
        executive_recommendations.append(
            "Resource workload should be reviewed."
        )

    if benefits_health < 50:
        executive_recommendations.append(
            "Benefits realisation is below target."
        )

    if overdue_tasks > 0:
        executive_recommendations.append(
            f"Resolve {overdue_tasks} overdue task(s)."
        )

    if blocked_tasks > 0:
        executive_recommendations.append(
            f"Escalate {blocked_tasks} blocked task(s)."
        )

    if over_budget_projects > 0:
        executive_recommendations.append(
            f"Review {over_budget_projects} over-budget project(s)."
        )

    if not executive_recommendations:
        executive_recommendations.append(
            "Portfolio is stable. Continue monitoring delivery, risks and financial controls."
        )

    executive_recommendation = " ".join(executive_recommendations)

    cursor.execute("""
        SELECT COUNT(*) AS total_assumptions
        FROM assumptions
        WHERE user_id = %s
    """, (user_id,))
    total_assumptions = cursor.fetchone()["total_assumptions"]

    cursor.execute("""
        SELECT COUNT(*) AS total_dependencies
        FROM dependencies
        WHERE user_id = %s
    """, (user_id,))
    total_dependencies = cursor.fetchone()["total_dependencies"]

    raid_total = (
        total_risks +
        total_assumptions +
        total_issues +
        total_dependencies
    )

    if raid_total <= 8:
        raid_health = "Green"
    elif raid_total <= 16:
        raid_health = "Amber"
    else:
        raid_health = "Red"

    cursor.execute("""
        SELECT COUNT(*) AS healthy_projects
        FROM projects
        WHERE user_id = %s
        AND status = 'Completed'
    """, (user_id,))
    healthy_projects = cursor.fetchone()["healthy_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS active_projects
        FROM projects
        WHERE user_id = %s
        AND status = 'In Progress'
    """, (user_id,))
    active_projects = cursor.fetchone()["active_projects"]

    if total_projects > 0:
        portfolio_completion = round((healthy_projects / total_projects) * 100)
    else:
        portfolio_completion = 0

    if portfolio_health >= 75:
        portfolio_trend = "▲ Healthy"
    elif portfolio_health >= 50:
        portfolio_trend = "► Watch"
    else:
        portfolio_trend = "▼ Declining"

    if risk_health >= 75:
        risk_trend = "▲ Controlled"
    elif risk_health >= 50:
        risk_trend = "► Watch"
    else:
        risk_trend = "▼ High Risk"

    if resource_health >= 75:
        resource_trend = "▲ Stable"
    elif resource_health >= 50:
        resource_trend = "► Moderate"
    else:
        resource_trend = "▼ Pressure"

    if completion_rate < 40:
        forecast_status = "Behind Plan"
    elif completion_rate < 70:
        forecast_status = "Needs Monitoring"
    else:
        forecast_status = "On Track"

    if tasks_per_person > 10:
        workload_status = "High"
    elif tasks_per_person > 6:
        workload_status = "Moderate"
    else:
        workload_status = "Healthy"

    conn.close()

    return render_template(
        "executive_dashboard.html",
        total_projects=total_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        in_progress_tasks=in_progress_tasks,
        overdue_tasks=overdue_tasks,
        blocked_tasks=blocked_tasks,
        over_budget_projects=over_budget_projects,
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
        executive_status=executive_status,
        executive_recommendation=executive_recommendation,
        total_team_members=total_team_members,
        active_tasks=active_tasks,
        tasks_per_person=tasks_per_person,
        portfolio_completion=portfolio_completion,
        completion_rate=completion_rate,
        budget_usage=budget_usage,
        portfolio_trend=portfolio_trend,
        risk_trend=risk_trend,
        resource_trend=resource_trend,
        forecast_status=forecast_status,
        workload_status=workload_status
    )

@app.route("/resource-heatmap")
def resource_heatmap():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Team", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (LOWER(TRIM(name)), LOWER(TRIM(email)))
            *
        FROM team_members
        WHERE user_id = %s
        ORDER BY LOWER(TRIM(name)), LOWER(TRIM(email)), id DESC
    """, (
        session["user_id"],
    ))

    members = cursor.fetchall()

    heatmap_data = []

    overloaded_count = 0
    busy_count = 0
    available_count = 0

    department_heatmap = {}
    role_heatmap = {}

    for member in members:

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

        resource_capacity = int(
            member.get("resource_capacity") or 100
        )

        workload_points = active_tasks * 10

        if resource_capacity > 0:
            utilisation = round(
                (workload_points / resource_capacity) * 100
            )
        else:
            utilisation = 0

        department = (
            member.get("department")
            or "Unassigned"
        )

        role = (
            member.get("role")
            or "Unknown"
        )

        if utilisation >= 90:

            status = "Overloaded"
            colour = "red"
            overloaded_count += 1

        elif utilisation >= 60:

            status = "Busy"
            colour = "amber"
            busy_count += 1

        else:

            status = "Available"
            colour = "green"
            available_count += 1

        department_heatmap[department] = (
            department_heatmap.get(department, 0) + 1
        )

        role_heatmap[role] = (
            role_heatmap.get(role, 0) + 1
        )

        workload_trend = "Stable"

        if utilisation >= 90:
            workload_trend = "Increasing"

        elif utilisation <= 40:
            workload_trend = "Underutilised"

        heatmap_data.append({

            "name": member["name"],
            "role": role,
            "department": department,
            "skills": member.get("skills"),
            "active_tasks": active_tasks,
            "utilisation": utilisation,
            "status": status,
            "colour": colour,
            "workload_trend": workload_trend

        })

    executive_summary = []

    if overloaded_count > 0:
        executive_summary.append(
            f"{overloaded_count} overloaded resource(s) require attention."
        )

    if busy_count > available_count:
        executive_summary.append(
            "Team workload is trending high."
        )

    if available_count > busy_count:
        executive_summary.append(
            "Spare capacity exists within the team."
        )

    if not executive_summary:
        executive_summary.append(
            "Resource heat map currently stable."
        )

    conn.close()

    return render_template(
        "resource_heatmap.html",
        heatmap_data=heatmap_data,
        overloaded_count=overloaded_count,
        busy_count=busy_count,
        available_count=available_count,
        department_heatmap=department_heatmap,
        role_heatmap=role_heatmap,
        executive_summary=executive_summary
    )

@app.route("/capacity-forecast")
def capacity_forecast():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Team", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (LOWER(TRIM(name)), LOWER(TRIM(email)))
            *
        FROM team_members
        WHERE user_id = %s
        ORDER BY LOWER(TRIM(name)), LOWER(TRIM(email)), id DESC
    """, (
        session["user_id"],
    ))

    members = cursor.fetchall()

    forecast_data = []

    total_resources = len(members)
    high_risk_count = 0
    medium_risk_count = 0
    low_risk_count = 0
    hiring_required_count = 0

    for member in members:

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

        resource_capacity = int(member.get("resource_capacity") or 100)

        current_demand = active_tasks * 10

        if resource_capacity > 0:
            current_utilisation = round((current_demand / resource_capacity) * 100)
        else:
            current_utilisation = 0

        current_utilisation = min(current_utilisation, 150)

        monthly_forecast = min(current_utilisation + 10, 150)
        quarterly_forecast = min(current_utilisation + 25, 150)

        available_capacity = max(0, resource_capacity - current_demand)

        skills = member.get("skills") or ""
        role = member.get("role") or "Unassigned"

        if quarterly_forecast >= 100:
            forecast_risk = "High"
            high_risk_count += 1
            hiring_forecast = "Hiring or workload redistribution required."
            hiring_required_count += 1
        elif quarterly_forecast >= 75:
            forecast_risk = "Medium"
            medium_risk_count += 1
            hiring_forecast = "Monitor workload and prepare backup capacity."
        else:
            forecast_risk = "Low"
            low_risk_count += 1
            hiring_forecast = "No immediate hiring requirement."

        if not skills.strip():
            skills_demand = "Skills not recorded. Update skills profile."
        elif active_tasks >= 5:
            skills_demand = f"Demand increasing for {role} capability."
        else:
            skills_demand = "Skills demand currently manageable."

        recruitment_recommendation = hiring_forecast

        forecast_data.append({
            "name": member["name"],
            "role": role,
            "department": member.get("department"),
            "skills": skills,
            "active_tasks": active_tasks,
            "resource_capacity": resource_capacity,
            "current_utilisation": current_utilisation,
            "monthly_forecast": monthly_forecast,
            "quarterly_forecast": quarterly_forecast,
            "available_capacity": available_capacity,
            "forecast_risk": forecast_risk,
            "hiring_forecast": hiring_forecast,
            "skills_demand": skills_demand,
            "recruitment_recommendation": recruitment_recommendation
        })

    conn.close()

    return render_template(
        "capacity_forecast.html",
        forecast_data=forecast_data,
        total_resources=total_resources,
        high_risk_count=high_risk_count,
        medium_risk_count=medium_risk_count,
        low_risk_count=low_risk_count,
        hiring_required_count=hiring_required_count
    )


@app.route("/skills-matrix")
def skills_matrix():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Team", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (LOWER(TRIM(name)), LOWER(TRIM(email)))
            *
        FROM team_members
        WHERE user_id = %s
        ORDER BY LOWER(TRIM(name)), LOWER(TRIM(email)), id DESC
    """, (
        session["user_id"],
    ))

    team_members = cursor.fetchall()

    total_members = len(team_members)
    active_members = 0
    skills_recorded = 0
    certification_count = 0
    training_required_count = 0
    skills_gap_count = 0

    skill_categories = {}

    enriched_members = []

    for member in team_members:

        if member["status"] == "Active":
            active_members += 1

        skills = member["skills"] or ""
        certifications = member.get("certifications") or ""
        training_required = member.get("training_required") or ""
        skills_gap_notes = member.get("skills_gap_notes") or ""
        category = member.get("skill_category") or "Uncategorised"

        if skills.strip():
            skills_recorded += 1

        if certifications.strip():
            certification_count += 1

        if training_required.strip():
            training_required_count += 1

        if skills_gap_notes.strip():
            skills_gap_count += 1

        if category not in skill_categories:
            skill_categories[category] = 0

        skill_categories[category] += 1

        recommendation = "No recommendation required."

        if not skills.strip():
            recommendation = "Add skills to improve resource matching."
        elif training_required.strip():
            recommendation = "Training required. Review development plan."
        elif skills_gap_notes.strip():
            recommendation = "Skills gap identified. Review capability coverage."

        enriched_members.append({
            "member": member,
            "recommendation": recommendation
        })

    conn.close()

    return render_template(
        "skills_matrix.html",
        team_members=enriched_members,
        total_members=total_members,
        active_members=active_members,
        skills_recorded=skills_recorded,
        certification_count=certification_count,
        training_required_count=training_required_count,
        skills_gap_count=skills_gap_count,
        skill_categories=skill_categories
    )


@app.route("/stage-gates")
def stage_gates():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Stage Gates", "view"):
        return "Access denied"

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
        ORDER BY
            CASE
                WHEN stage_gates.status = 'Rejected' THEN 1
                WHEN stage_gates.status = 'Pending' THEN 2
                WHEN stage_gates.evidence_status = 'Pending' THEN 3
                WHEN stage_gates.progression_status = 'In Progress' THEN 4
                WHEN stage_gates.status = 'Approved' THEN 5
                ELSE 6
            END,
            stage_gates.review_date ASC
    """, (
        session["user_id"],
    ))

    stage_gates = cursor.fetchall()

    cursor.execute("""
        SELECT
            COUNT(*) AS total_gates,

            COUNT(*) FILTER (
                WHERE status = 'Approved'
            ) AS approved_gates,

            COUNT(*) FILTER (
                WHERE status = 'Pending'
            ) AS pending_gates,

            COUNT(*) FILTER (
                WHERE status = 'Rejected'
            ) AS rejected_gates,

            COUNT(*) FILTER (
                WHERE evidence_status = 'Pending'
            ) AS pending_evidence,

            COUNT(*) FILTER (
                WHERE progression_status = 'In Progress'
            ) AS in_progress_gates,

            COUNT(*) FILTER (
                WHERE progression_status = 'Ready for Next Stage'
            ) AS ready_for_next_stage,

            COUNT(*) FILTER (
                WHERE decision_created = 'Yes'
            ) AS decisions_created

        FROM stage_gates
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    stats = cursor.fetchone()

    conn.close()

    return render_template(
        "stage_gates.html",
        stage_gates=stage_gates,
        stats=stats
    )


@app.route("/add-stage-gate", methods=["GET", "POST"])
def add_stage_gate():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Stage Gates", "create"):
        return "Access denied"

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

        status = request.form.get("status")
        decision_created = "Yes" if status in ["Approved", "Rejected"] else "No"

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
                gate_template,
                evidence_required,
                evidence_status,
                evidence_notes,
                progression_status,
                approval_reference,
                decision_created,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("stage_name"),
            status,
            request.form.get("reviewer"),
            request.form.get("comments"),
            request.form.get("review_date") or None,
            request.form.get("gate_template"),
            request.form.get("evidence_required"),
            request.form.get("evidence_status"),
            request.form.get("evidence_notes"),
            request.form.get("progression_status"),
            request.form.get("approval_reference"),
            decision_created
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

    if not has_permission("Stage Gates", "edit"):
        return "Access denied"

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

    if not gate:
        conn.close()
        return redirect("/stage-gates")

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

        old_status = gate["status"]
        new_status = request.form.get("status")
        decision_created = gate["decision_created"] or "No"

        if new_status in ["Approved", "Rejected"]:
            decision_created = "Yes"

        cursor.execute("""
            UPDATE stage_gates
            SET
                project_id = %s,
                stage_name = %s,
                status = %s,
                reviewer = %s,
                comments = %s,
                review_date = %s,
                gate_template = %s,
                evidence_required = %s,
                evidence_status = %s,
                evidence_notes = %s,
                progression_status = %s,
                approval_reference = %s,
                decision_created = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            request.form.get("stage_name"),
            new_status,
            request.form.get("reviewer"),
            request.form.get("comments"),
            request.form.get("review_date") or None,
            request.form.get("gate_template"),
            request.form.get("evidence_required"),
            request.form.get("evidence_status"),
            request.form.get("evidence_notes"),
            request.form.get("progression_status"),
            request.form.get("approval_reference"),
            decision_created,
            gate_id,
            session["user_id"]
        ))

        if old_status != new_status:
            cursor.execute("""
                INSERT INTO stage_gate_history
                (
                    gate_id,
                    user_id,
                    old_status,
                    new_status,
                    change_note
                )
                VALUES (%s,%s,%s,%s,%s)
            """, (
                gate_id,
                session["user_id"],
                old_status,
                new_status,
                "Stage gate status changed"
            ))

        conn.commit()
        conn.close()

        return redirect("/stage-gates")

    conn.close()

    return render_template(
        "edit_stage_gate.html",
        gate=gate,
        projects=projects
    )


@app.route("/delete-stage-gate/<int:gate_id>")
def delete_stage_gate(gate_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Stage Gates", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM stage_gate_history
        WHERE gate_id = %s
        AND user_id = %s
    """, (
        gate_id,
        session["user_id"]
    ))

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


@app.route("/stage-gate-history/<int:gate_id>")
def stage_gate_history(gate_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Stage Gates", "view"):
        return "Access denied"

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

    if not gate:
        conn.close()
        return redirect("/stage-gates")

    cursor.execute("""
        SELECT *
        FROM stage_gate_history
        WHERE gate_id = %s
        AND user_id = %s
        ORDER BY changed_at DESC
    """, (
        gate_id,
        session["user_id"]
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "stage_gate_history.html",
        gate=gate,
        history=history
    )

@app.route("/approvals")
def approvals():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Approvals", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            approvals.*,
            projects.name AS project_name,

            CASE
                WHEN approvals.status = 'Pending'
                AND approvals.sla_due_date IS NOT NULL
                AND approvals.sla_due_date < CURRENT_DATE
                THEN 'Yes'
                ELSE 'No'
            END AS sla_overdue,

            CASE
                WHEN approvals.status = 'Pending'
                AND approvals.reminder_date IS NOT NULL
                AND approvals.reminder_date <= CURRENT_DATE
                THEN 'Yes'
                ELSE 'No'
            END AS reminder_due

        FROM approvals
        LEFT JOIN projects
        ON approvals.project_id = projects.id
        WHERE approvals.user_id = %s
        ORDER BY
            CASE
                WHEN approvals.status = 'Pending'
                AND approvals.sla_due_date IS NOT NULL
                AND approvals.sla_due_date < CURRENT_DATE THEN 1
                WHEN approvals.status = 'Pending' THEN 2
                WHEN approvals.status = 'Rejected' THEN 3
                WHEN approvals.status = 'Approved' THEN 4
                ELSE 5
            END,
            approvals.id DESC
    """, (
        session["user_id"],
    ))

    approvals = cursor.fetchall()

    cursor.execute("""
        SELECT
            COUNT(*) AS total_approvals,

            COUNT(*) FILTER (
                WHERE status = 'Pending'
            ) AS pending_approvals,

            COUNT(*) FILTER (
                WHERE status = 'Approved'
            ) AS approved_approvals,

            COUNT(*) FILTER (
                WHERE status = 'Rejected'
            ) AS rejected_approvals,

            COUNT(*) FILTER (
                WHERE status = 'Pending'
                AND sla_due_date IS NOT NULL
                AND sla_due_date < CURRENT_DATE
            ) AS sla_overdue,

            COUNT(*) FILTER (
                WHERE status = 'Pending'
                AND reminder_date IS NOT NULL
                AND reminder_date <= CURRENT_DATE
            ) AS reminders_due,

            COUNT(*) FILTER (
                WHERE delegated_to IS NOT NULL
                AND delegated_to != ''
            ) AS delegated_approvals,

            COUNT(*) FILTER (
                WHERE decision_created = 'Yes'
            ) AS decisions_created

        FROM approvals
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    stats = cursor.fetchone()

    conn.close()

    return render_template(
        "approvals.html",
        approvals=approvals,
        stats=stats
    )


@app.route("/add-approval", methods=["GET", "POST"])
def add_approval():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Approvals", "create"):
        return "Access denied"

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

        status = request.form.get("status")
        decision_created = "Yes" if status in ["Approved", "Rejected"] else "No"

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
                comments,
                approval_category,
                approval_stage,
                delegated_to,
                reminder_date,
                sla_due_date,
                approval_reference,
                decision_created
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("item_type"),
            request.form.get("item_id"),
            request.form.get("submitted_by"),
            request.form.get("approver"),
            status,
            request.form.get("comments"),
            request.form.get("approval_category"),
            request.form.get("approval_stage"),
            request.form.get("delegated_to"),
            request.form.get("reminder_date") or None,
            request.form.get("sla_due_date") or None,
            request.form.get("approval_reference"),
            decision_created
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

    if not has_permission("Approvals", "edit"):
        return "Access denied"

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

    if not approval:
        conn.close()
        return redirect("/approvals")

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

        old_status = approval["status"]
        new_status = request.form.get("status")
        decision_created = approval["decision_created"] or "No"

        if new_status in ["Approved", "Rejected"]:
            decision_created = "Yes"

        cursor.execute("""
            UPDATE approvals
            SET
                project_id = %s,
                item_type = %s,
                item_id = %s,
                submitted_by = %s,
                approver = %s,
                status = %s,
                comments = %s,
                approval_category = %s,
                approval_stage = %s,
                delegated_to = %s,
                reminder_date = %s,
                sla_due_date = %s,
                approval_reference = %s,
                decision_created = %s,
                decision_date = CASE
                    WHEN %s IN ('Approved', 'Rejected') THEN CURRENT_DATE
                    ELSE decision_date
                END
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            request.form.get("item_type"),
            request.form.get("item_id"),
            request.form.get("submitted_by"),
            request.form.get("approver"),
            new_status,
            request.form.get("comments"),
            request.form.get("approval_category"),
            request.form.get("approval_stage"),
            request.form.get("delegated_to"),
            request.form.get("reminder_date") or None,
            request.form.get("sla_due_date") or None,
            request.form.get("approval_reference"),
            decision_created,
            new_status,
            id,
            session["user_id"]
        ))

        if old_status != new_status:
            cursor.execute("""
                INSERT INTO approval_history
                (
                    approval_id,
                    user_id,
                    old_status,
                    new_status,
                    change_note
                )
                VALUES (%s,%s,%s,%s,%s)
            """, (
                id,
                session["user_id"],
                old_status,
                new_status,
                "Approval status changed"
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

    if not has_permission("Approvals", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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

    if not approval:
        conn.close()
        return redirect("/approvals")

    cursor.execute("""
        UPDATE approvals
        SET status = 'Approved',
            decision_date = CURRENT_DATE,
            decision_created = 'Yes'
        WHERE id = %s
        AND user_id = %s
    """, (
        id,
        session["user_id"]
    ))

    cursor.execute("""
        INSERT INTO approval_history
        (
            approval_id,
            user_id,
            old_status,
            new_status,
            change_note
        )
        VALUES (%s,%s,%s,%s,%s)
    """, (
        id,
        session["user_id"],
        approval["status"],
        "Approved",
        "Approval approved"
    ))

    conn.commit()
    conn.close()

    return redirect("/approvals")


@app.route("/reject-approval/<int:id>")
def reject_approval(id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Approvals", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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

    if not approval:
        conn.close()
        return redirect("/approvals")

    cursor.execute("""
        UPDATE approvals
        SET status = 'Rejected',
            decision_date = CURRENT_DATE,
            decision_created = 'Yes'
        WHERE id = %s
        AND user_id = %s
    """, (
        id,
        session["user_id"]
    ))

    cursor.execute("""
        INSERT INTO approval_history
        (
            approval_id,
            user_id,
            old_status,
            new_status,
            change_note
        )
        VALUES (%s,%s,%s,%s,%s)
    """, (
        id,
        session["user_id"],
        approval["status"],
        "Rejected",
        "Approval rejected"
    ))

    conn.commit()
    conn.close()

    return redirect("/approvals")


@app.route("/approval-history/<int:id>")
def approval_history(id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Approvals", "view"):
        return "Access denied"

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

    if not approval:
        conn.close()
        return redirect("/approvals")

    cursor.execute("""
        SELECT *
        FROM approval_history
        WHERE approval_id = %s
        AND user_id = %s
        ORDER BY changed_at DESC
    """, (
        id,
        session["user_id"]
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "approval_history.html",
        approval=approval,
        history=history
    )


@app.route("/delete-approval/<int:id>")
def delete_approval(id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Approvals", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM approval_history
        WHERE approval_id = %s
        AND user_id = %s
    """, (
        id,
        session["user_id"]
    ))

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

    if not has_permission("Governance Reviews", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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

    cursor.execute("""
        SELECT
            COUNT(*) AS total_reviews,
            COUNT(*) FILTER (WHERE status = 'Completed') AS completed_reviews,
            COUNT(*) FILTER (WHERE status = 'Open') AS open_reviews,
            COUNT(*) FILTER (WHERE status = 'In Progress') AS in_progress_reviews,
            COUNT(*) FILTER (WHERE next_review_date < CURRENT_DATE AND status != 'Completed') AS overdue_reviews,
            ROUND(AVG(governance_score), 1) AS avg_governance_score,
            ROUND(AVG(maturity_score), 1) AS avg_maturity_score
        FROM governance_reviews
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    stats = cursor.fetchone()

    conn.close()

    return render_template(
        "governance_reviews.html",
        reviews=reviews,
        stats=stats
    )


@app.route("/add-governance-review", methods=["GET", "POST"])
def add_governance_review():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Governance Reviews", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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
                review_frequency,
                governance_score,
                maturity_score,
                risk_trend,
                executive_summary,
                auto_schedule_next,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            request.form.get("review_name"),
            request.form.get("review_type"),
            request.form.get("review_date") or None,
            request.form.get("outcome"),
            request.form.get("decision"),
            request.form.get("actions"),
            request.form.get("owner"),
            request.form.get("next_review_date") or None,
            request.form.get("status"),
            request.form.get("review_frequency"),
            request.form.get("governance_score") or 0,
            request.form.get("maturity_score") or 0,
            request.form.get("risk_trend"),
            request.form.get("executive_summary"),
            request.form.get("auto_schedule_next")
        ))

        conn.commit()
        conn.close()

        return redirect("/governance-reviews")

    conn.close()

    return render_template(
        "add_governance_review.html",
        projects=projects
    )


@app.route("/edit-governance-review/<int:review_id>", methods=["GET", "POST"])
def edit_governance_review(review_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Governance Reviews", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM governance_reviews
        WHERE id = %s
        AND user_id = %s
    """, (
        review_id,
        session["user_id"]
    ))

    review = cursor.fetchone()

    if not review:
        conn.close()
        return redirect("/governance-reviews")

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

        old_status = review["status"]
        new_status = request.form.get("status")

        cursor.execute("""
            UPDATE governance_reviews
            SET
                project_id = %s,
                review_name = %s,
                review_type = %s,
                review_date = %s,
                outcome = %s,
                decision = %s,
                actions = %s,
                owner = %s,
                next_review_date = %s,
                status = %s,
                review_frequency = %s,
                governance_score = %s,
                maturity_score = %s,
                risk_trend = %s,
                executive_summary = %s,
                auto_schedule_next = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            request.form.get("review_name"),
            request.form.get("review_type"),
            request.form.get("review_date") or None,
            request.form.get("outcome"),
            request.form.get("decision"),
            request.form.get("actions"),
            request.form.get("owner"),
            request.form.get("next_review_date") or None,
            new_status,
            request.form.get("review_frequency"),
            request.form.get("governance_score") or 0,
            request.form.get("maturity_score") or 0,
            request.form.get("risk_trend"),
            request.form.get("executive_summary"),
            request.form.get("auto_schedule_next"),
            review_id,
            session["user_id"]
        ))

        if old_status != new_status:
            cursor.execute("""
                INSERT INTO governance_review_history
                (
                    review_id,
                    user_id,
                    old_status,
                    new_status,
                    change_note
                )
                VALUES (%s,%s,%s,%s,%s)
            """, (
                review_id,
                session["user_id"],
                old_status,
                new_status,
                "Governance review status changed"
            ))

        conn.commit()
        conn.close()

        return redirect("/governance-reviews")

    conn.close()

    return render_template(
        "edit_governance_review.html",
        review=review,
        projects=projects
    )


@app.route("/governance-review-history/<int:review_id>")
def governance_review_history(review_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Governance Reviews", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM governance_reviews
        WHERE id = %s
        AND user_id = %s
    """, (
        review_id,
        session["user_id"]
    ))

    review = cursor.fetchone()

    if not review:
        conn.close()
        return redirect("/governance-reviews")

    cursor.execute("""
        SELECT *
        FROM governance_review_history
        WHERE review_id = %s
        AND user_id = %s
        ORDER BY changed_at DESC
    """, (
        review_id,
        session["user_id"]
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "governance_review_history.html",
        review=review,
        history=history
    )


@app.route("/delete-governance-review/<int:review_id>")
def delete_governance_review(review_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Governance Reviews", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM governance_review_history
        WHERE review_id = %s
        AND user_id = %s
    """, (
        review_id,
        session["user_id"]
    ))

    cursor.execute("""
        DELETE FROM governance_reviews
        WHERE id = %s
        AND user_id = %s
    """, (
        review_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/governance-reviews")


@app.route("/project-prioritisation")
def project_prioritisation():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Project Prioritisation", "view"):
        return "Access denied"

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
        ORDER BY
            project_prioritisation.weighted_priority_score DESC,
            project_prioritisation.priority_score DESC
    """, (
        session["user_id"],
    ))

    priorities = cursor.fetchall()

    total_projects = len(priorities)
    high_priority = 0
    medium_priority = 0
    low_priority = 0
    total_score = 0

    for item in priorities:

        weighted_score = item["weighted_priority_score"] or 0

        if weighted_score == 0:
            weighted_score = (
                (item["business_value_score"] or 0) * 3
                + (item["strategic_alignment_score"] or 0) * 3
                + (item["benefits_score"] or 0) * 2
                + (item["roi_score"] or 0) * 2
                + (item["resource_score"] or 0)
                + (item["risk_score"] or 0)
                + (item["cost_score"] or 0)
            )

        item["weighted_priority_score"] = weighted_score
        total_score += weighted_score

        if weighted_score >= 60:
            item["priority_band"] = "High"
            high_priority += 1
        elif weighted_score >= 35:
            item["priority_band"] = "Medium"
            medium_priority += 1
        else:
            item["priority_band"] = "Low"
            low_priority += 1

        cursor.execute("""
            INSERT INTO prioritisation_history
            (
                prioritisation_id,
                user_id,
                project_id,
                priority_score,
                weighted_priority_score
            )
            VALUES (%s,%s,%s,%s,%s)
        """, (
            item["id"],
            session["user_id"],
            item["project_id"],
            item["priority_score"],
            weighted_score
        ))

    average_score = round(total_score / total_projects) if total_projects > 0 else 0

    conn.commit()
    conn.close()

    return render_template(
        "project_prioritisation.html",
        priorities=priorities,
        total_projects=total_projects,
        high_priority=high_priority,
        medium_priority=medium_priority,
        low_priority=low_priority,
        average_score=average_score
    )


@app.route("/add-project-prioritisation", methods=["GET", "POST"])
def add_project_prioritisation():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Project Prioritisation", "create"):
        return "Access denied"

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

        business_value_score = int(request.form.get("business_value_score") or 0)
        strategic_alignment_score = int(request.form.get("strategic_alignment_score") or 0)
        risk_score = int(request.form.get("risk_score") or 0)
        cost_score = int(request.form.get("cost_score") or 0)
        roi_score = int(request.form.get("roi_score") or 0)
        benefits_score = int(request.form.get("benefits_score") or 0)
        resource_score = int(request.form.get("resource_score") or 0)

        priority_score = (
            business_value_score
            + strategic_alignment_score
            + risk_score
            + cost_score
        )

        weighted_priority_score = (
            (business_value_score * 3)
            + (strategic_alignment_score * 3)
            + (benefits_score * 2)
            + (roi_score * 2)
            + resource_score
            + risk_score
            + cost_score
        )

        if weighted_priority_score >= 60:
            investment_category = "Strategic Investment"
        elif weighted_priority_score >= 35:
            investment_category = "Recommended Investment"
        else:
            investment_category = "Low Priority Investment"

        cursor.execute("""
            INSERT INTO project_prioritisation
            (
                user_id,
                project_id,
                business_value_score,
                strategic_alignment_score,
                risk_score,
                cost_score,
                roi_score,
                benefits_score,
                resource_score,
                strategic_objective,
                priority_score,
                weighted_priority_score,
                investment_category,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("project_id"),
            business_value_score,
            strategic_alignment_score,
            risk_score,
            cost_score,
            roi_score,
            benefits_score,
            resource_score,
            request.form.get("strategic_objective"),
            priority_score,
            weighted_priority_score,
            investment_category,
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

@app.route("/edit-project-prioritisation/<int:priority_id>", methods=["GET", "POST"])
def edit_project_prioritisation(priority_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Project Prioritisation", "edit"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM project_prioritisation
        WHERE id = %s
        AND user_id = %s
    """, (
        priority_id,
        session["user_id"]
    ))

    priority = cursor.fetchone()

    if not priority:
        conn.close()
        return redirect("/project-prioritisation")

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

        business_value_score = int(request.form.get("business_value_score") or 0)
        strategic_alignment_score = int(request.form.get("strategic_alignment_score") or 0)
        risk_score = int(request.form.get("risk_score") or 0)
        cost_score = int(request.form.get("cost_score") or 0)
        roi_score = int(request.form.get("roi_score") or 0)
        benefits_score = int(request.form.get("benefits_score") or 0)
        resource_score = int(request.form.get("resource_score") or 0)

        priority_score = (
            business_value_score
            + strategic_alignment_score
            + risk_score
            + cost_score
        )

        weighted_priority_score = (
            (business_value_score * 3)
            + (strategic_alignment_score * 3)
            + (benefits_score * 2)
            + (roi_score * 2)
            + resource_score
            + risk_score
            + cost_score
        )

        if weighted_priority_score >= 60:
            investment_category = "Strategic Investment"
        elif weighted_priority_score >= 35:
            investment_category = "Recommended Investment"
        else:
            investment_category = "Low Priority Investment"

        cursor.execute("""
            UPDATE project_prioritisation
            SET
                project_id = %s,
                business_value_score = %s,
                strategic_alignment_score = %s,
                risk_score = %s,
                cost_score = %s,
                roi_score = %s,
                benefits_score = %s,
                resource_score = %s,
                strategic_objective = %s,
                priority_score = %s,
                weighted_priority_score = %s,
                investment_category = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("project_id"),
            business_value_score,
            strategic_alignment_score,
            risk_score,
            cost_score,
            roi_score,
            benefits_score,
            resource_score,
            request.form.get("strategic_objective"),
            priority_score,
            weighted_priority_score,
            investment_category,
            priority_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        return redirect("/project-prioritisation")

    conn.close()

    return render_template(
        "edit_project_prioritisation.html",
        priority=priority,
        projects=projects
    )

@app.route("/delete-project-prioritisation/<int:priority_id>")
def delete_project_prioritisation(priority_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Project Prioritisation", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM project_prioritisation
        WHERE id = %s
        AND user_id = %s
    """, (
        priority_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/project-prioritisation")


@app.route("/programmes")
def programmes():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Programmes", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM programmes
        WHERE user_id = %s
        AND COALESCE(archived, FALSE) = FALSE
        ORDER BY created_at DESC
    """, (
        session["user_id"],
    ))

    programmes = cursor.fetchall()

    enriched_programmes = []

    total_programmes = len(programmes)
    active_programmes = 0
    planning_programmes = 0
    at_risk_programmes = 0
    completed_programmes = 0

    for programme in programmes:

        programme_name = programme["programme_name"]

        cursor.execute("""
            SELECT COUNT(*) AS linked_projects
            FROM projects
            WHERE user_id = %s
            AND programme = %s
        """, (
            session["user_id"],
            programme_name
        ))

        linked_projects = cursor.fetchone()["linked_projects"]

        cursor.execute("""
            SELECT COUNT(*) AS milestone_count
            FROM programme_milestones
            WHERE programme_id = %s
        """, (
            programme["id"],
        ))

        milestone_count = cursor.fetchone()["milestone_count"]

        cursor.execute("""
            SELECT COUNT(*) AS benefits_count
            FROM programme_benefits
            WHERE programme_id = %s
        """, (
            programme["id"],
        ))

        benefits_count = cursor.fetchone()["benefits_count"]

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

        health_score = 100
        health_score -= min(open_risks * 5, 25)
        health_score -= min(open_issues * 5, 25)

        if linked_projects == 0:
            health_score -= 20

        if programme["status"] == "At Risk":
            health_score -= 20

        health_score = max(0, min(100, health_score))

        if health_score >= 80:
            health_status = "Green"
        elif health_score >= 50:
            health_status = "Amber"
        else:
            health_status = "Red"

        cursor.execute("""
            UPDATE programmes
            SET
                health_score = %s,
                health_status = %s,
                linked_projects = %s,
                milestone_count = %s,
                open_risks = %s,
                open_issues = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            health_score,
            health_status,
            linked_projects,
            milestone_count,
            open_risks,
            open_issues,
            programme["id"],
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO programme_history
            (
                programme_id,
                user_id,
                health_score,
                open_risks,
                open_issues,
                linked_projects,
                action,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            programme["id"],
            session["user_id"],
            health_score,
            open_risks,
            open_issues,
            linked_projects,
            "Programme health snapshot",
            str(date.today())
        ))

        programme["health_score"] = health_score
        programme["health_status"] = health_status
        programme["linked_projects"] = linked_projects
        programme["milestone_count"] = milestone_count
        programme["benefits_count"] = benefits_count
        programme["open_risks"] = open_risks
        programme["open_issues"] = open_issues

        enriched_programmes.append(programme)

        if programme["status"] == "Active":
            active_programmes += 1
        elif programme["status"] == "Planning":
            planning_programmes += 1
        elif programme["status"] == "At Risk":
            at_risk_programmes += 1
        elif programme["status"] == "Completed":
            completed_programmes += 1

    conn.commit()
    conn.close()

    return render_template(
        "programmes.html",
        programmes=enriched_programmes,
        total_programmes=total_programmes,
        active_programmes=active_programmes,
        planning_programmes=planning_programmes,
        at_risk_programmes=at_risk_programmes,
        completed_programmes=completed_programmes
    )


@app.route("/add-programme", methods=["GET", "POST"])
def add_programme():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Programmes", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO programmes
            (
                user_id,
                programme_name,
                description,
                sponsor,
                manager,
                status,
                start_date,
                end_date,
                budget,
                benefits,
                risks,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("programme_name"),
            request.form.get("description"),
            request.form.get("sponsor"),
            request.form.get("manager"),
            request.form.get("status"),
            request.form.get("start_date"),
            request.form.get("end_date"),
            request.form.get("budget") or 0,
            request.form.get("benefits"),
            request.form.get("risks"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/programmes")

    conn.close()

    return render_template("add_programme.html")


@app.route("/edit-programme/<int:programme_id>", methods=["GET", "POST"])
def edit_programme(programme_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Programmes", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM programmes
        WHERE id = %s
        AND user_id = %s
    """, (
        programme_id,
        session["user_id"]
    ))

    programme = cursor.fetchone()

    if not programme:
        conn.close()
        return redirect("/programmes")

    if request.method == "POST":

        cursor.execute("""
            UPDATE programmes
            SET
                programme_name = %s,
                description = %s,
                sponsor = %s,
                manager = %s,
                status = %s,
                start_date = %s,
                end_date = %s,
                budget = %s,
                benefits = %s,
                risks = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("programme_name"),
            request.form.get("description"),
            request.form.get("sponsor"),
            request.form.get("manager"),
            request.form.get("status"),
            request.form.get("start_date"),
            request.form.get("end_date"),
            request.form.get("budget") or 0,
            request.form.get("benefits"),
            request.form.get("risks"),
            programme_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        return redirect("/programmes")

    conn.close()

    return render_template(
        "edit_programme.html",
        programme=programme
    )


@app.route("/delete-programme/<int:programme_id>")
def delete_programme(programme_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Programmes", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE programmes
        SET archived = TRUE
        WHERE id = %s
        AND user_id = %s
    """, (
        programme_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/programmes")


@app.route("/portfolio-health")
def portfolio_health():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Portfolio Health", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM portfolio_health
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (session["user_id"],))

    health_records = cursor.fetchall()
    conn.close()

    return render_template(
        "portfolio_health.html",
        health_records=health_records
    )


@app.route("/add-portfolio-health", methods=["GET", "POST"])
def add_portfolio_health():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Portfolio Health", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO portfolio_health
            (
                user_id,
                health_score,
                risk_exposure,
                financial_health,
                performance_score,
                trend,
                commentary,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form["health_score"],
            request.form["risk_exposure"],
            request.form["financial_health"],
            request.form["performance_score"],
            request.form["trend"],
            request.form["commentary"],
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/portfolio-health")

    conn.close()

    return render_template("add_portfolio_health.html")


@app.route("/portfolio-trends")
def portfolio_trends():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM portfolio_health
        WHERE user_id = %s
        ORDER BY created_at ASC
    """, (
        session["user_id"],
    ))

    trends = cursor.fetchall()

    total_records = len(trends)

    latest_health = 0
    previous_health = 0

    health_trend = "No Data"

    latest_risk = 0
    previous_risk = 0

    risk_trend = "No Data"

    latest_financial = 0
    previous_financial = 0

    financial_trend = "No Data"

    latest_delivery = 0
    previous_delivery = 0

    delivery_trend = "No Data"

    if total_records >= 1:

        latest = trends[-1]

        latest_health = latest["health_score"] or 0
        latest_risk = latest["risk_exposure"] or 0
        latest_financial = latest["financial_health"] or 0
        latest_delivery = latest["performance_score"] or 0

    if total_records >= 2:

        previous = trends[-2]

        previous_health = previous["health_score"] or 0
        previous_risk = previous["risk_exposure"] or 0
        previous_financial = previous["financial_health"] or 0
        previous_delivery = previous["performance_score"] or 0

        if latest_health > previous_health:
            health_trend = "Improving"
        elif latest_health < previous_health:
            health_trend = "Declining"
        else:
            health_trend = "Stable"

        if latest_risk < previous_risk:
            risk_trend = "Improving"
        elif latest_risk > previous_risk:
            risk_trend = "Declining"
        else:
            risk_trend = "Stable"

        if latest_financial > previous_financial:
            financial_trend = "Improving"
        elif latest_financial < previous_financial:
            financial_trend = "Declining"
        else:
            financial_trend = "Stable"

        if latest_delivery > previous_delivery:
            delivery_trend = "Improving"
        elif latest_delivery < previous_delivery:
            delivery_trend = "Declining"
        else:
            delivery_trend = "Stable"

    conn.close()

    return render_template(
        "portfolio_trends.html",

        trends=trends,

        total_records=total_records,

        latest_health=latest_health,
        latest_risk=latest_risk,
        latest_financial=latest_financial,
        latest_delivery=latest_delivery,

        health_trend=health_trend,
        risk_trend=risk_trend,
        financial_trend=financial_trend,
        delivery_trend=delivery_trend
    )


@app.route("/financial-trends")
def financial_trends():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (budgets.id)
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
    total_actual = 0
    total_forecast = 0
    total_variance = 0

    over_budget_projects = 0
    under_budget_projects = 0

    financial_cards = []

    for budget in budgets:

        budget_amount = float(
            budget["budget_amount"] or 0
        )

        actual_cost = float(
            budget["actual_cost"] or 0
        )

        forecast_cost = float(
            budget["forecast_cost"] or 0
        )

        variance = budget_amount - actual_cost

        total_budget += budget_amount
        total_actual += actual_cost
        total_forecast += forecast_cost
        total_variance += variance

        if variance < 0:
            over_budget_projects += 1
            status = "Over Budget"
        else:
            under_budget_projects += 1
            status = "On Track"

        financial_cards.append({
            "project_name": budget["project_name"],
            "budget_amount": budget_amount,
            "actual_cost": actual_cost,
            "forecast_cost": forecast_cost,
            "variance": variance,
            "status": status,
            "created_at": budget["created_at"]
        })

    if total_budget > 0:
        financial_health = round(
            ((total_budget - total_actual) / total_budget) * 100
        )
    else:
        financial_health = 0

    conn.close()

    return render_template(
        "financial_trends.html",
        budgets=budgets,
        financial_cards=financial_cards,
        total_budget=total_budget,
        total_actual=total_actual,
        total_forecast=total_forecast,
        total_variance=total_variance,
        financial_health=financial_health,
        over_budget_projects=over_budget_projects,
        under_budget_projects=under_budget_projects
    )

@app.route("/financial-health")
def financial_health():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Budgets", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (budgets.id)
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

    health_cards = []

    healthy_count = 0
    monitor_count = 0
    at_risk_count = 0

    for budget in budgets:

        budget_amount = float(budget["budget_amount"] or 0)
        actual_cost = float(budget["actual_cost"] or 0)
        forecast_cost = float(budget["forecast_cost"] or 0)

        result = calculate_financial_health(
            budget_amount,
            actual_cost,
            forecast_cost
        )

        remaining_budget = budget_amount - actual_cost
        forecast_variance = budget_amount - forecast_cost

        if result["status"] == "Healthy":
            healthy_count += 1
        elif result["status"] == "Monitor":
            monitor_count += 1
        else:
            at_risk_count += 1

        cursor.execute("""
            SELECT COUNT(*) AS linked_risks
            FROM risks
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            budget["project_id"],
        ))

        linked_risks = cursor.fetchone()["linked_risks"]

        health_cards.append({
            "budget_id": budget["id"],
            "project_name": budget["project_name"],
            "budget_amount": budget_amount,
            "actual_cost": actual_cost,
            "forecast_cost": forecast_cost,
            "remaining_budget": remaining_budget,
            "forecast_variance": forecast_variance,
            "health_score": result["score"],
            "health_status": result["status"],
            "risk_level": result["risk"],
            "message": result["message"],
            "budget_owner": budget.get("budget_owner"),
            "financial_approver": budget.get("budget_approver"),
            "last_review_date": budget.get("approval_date"),
            "financial_comments": budget.get("budget_notes"),
            "linked_risks": linked_risks
        })

    conn.close()

    return render_template(
        "financial_health.html",
        health_cards=health_cards,
        healthy_count=healthy_count,
        monitor_count=monitor_count,
        at_risk_count=at_risk_count,
        total_cards=len(health_cards)
    )


@app.route("/forecast-vs-actual")
def forecast_vs_actual():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Budgets", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (budgets.id)
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

    forecast_items = []

    total_budget = 0
    total_actual = 0
    total_forecast = 0
    total_baseline_forecast = 0

    over_forecast_count = 0
    under_forecast_count = 0
    on_forecast_count = 0
    forecast_risk_count = 0

    for item in budgets:

        budget_amount = float(item["budget_amount"] or 0)
        actual_cost = float(item["actual_cost"] or 0)
        forecast_cost = float(item["forecast_cost"] or 0)
        baseline_forecast = float(item.get("baseline_forecast") or 0)

        total_budget += budget_amount
        total_actual += actual_cost
        total_forecast += forecast_cost
        total_baseline_forecast += baseline_forecast

        variance = forecast_cost - actual_cost
        budget_forecast_variance = budget_amount - forecast_cost
        baseline_variance = forecast_cost - baseline_forecast

        if forecast_cost > 0:
            forecast_accuracy = round((1 - abs(forecast_cost - actual_cost) / forecast_cost) * 100)
            forecast_accuracy = max(0, min(100, forecast_accuracy))
        else:
            forecast_accuracy = 0

        if actual_cost > forecast_cost:
            status = "Over Forecast"
            over_forecast_count += 1
        elif actual_cost < forecast_cost:
            status = "Under Forecast"
            under_forecast_count += 1
        else:
            status = "On Forecast"
            on_forecast_count += 1

        if budget_amount > 0 and forecast_cost > budget_amount:
            forecast_risk = "High"
            forecast_risk_count += 1
        elif forecast_accuracy < 70:
            forecast_risk = "Medium"
        else:
            forecast_risk = "Low"

        forecast_items.append({
            "id": item["id"],
            "project_name": item["project_name"],
            "budget_amount": budget_amount,
            "actual_cost": actual_cost,
            "forecast_cost": forecast_cost,
            "baseline_forecast": baseline_forecast,
            "variance": variance,
            "budget_forecast_variance": budget_forecast_variance,
            "baseline_variance": baseline_variance,
            "forecast_accuracy": forecast_accuracy,
            "status": status,
            "forecast_risk": forecast_risk,
            "forecast_owner": item.get("forecast_owner"),
            "forecast_approver": item.get("forecast_approver"),
            "forecast_assumptions": item.get("forecast_assumptions"),
            "forecast_version": item.get("forecast_version"),
            "forecast_confidence": item.get("forecast_confidence"),
            "forecast_approval_status": item.get("forecast_approval_status")
        })

    total_variance = total_forecast - total_actual
    total_budget_forecast_variance = total_budget - total_forecast

    if total_forecast > 0:
        overall_accuracy = round((1 - abs(total_forecast - total_actual) / total_forecast) * 100)
        overall_accuracy = max(0, min(100, overall_accuracy))
    else:
        overall_accuracy = 0

    if forecast_risk_count > 0:
        forecast_health = "Red"
        forecast_message = "One or more forecasts exceed approved budget. Review forecast assumptions."
    elif overall_accuracy < 70:
        forecast_health = "Amber"
        forecast_message = "Forecast accuracy requires monitoring."
    else:
        forecast_health = "Green"
        forecast_message = "Forecast performance is currently stable."

    conn.close()

    return render_template(
        "forecast_vs_actual.html",
        forecast_items=forecast_items,
        total_budget=total_budget,
        total_actual=total_actual,
        total_forecast=total_forecast,
        total_baseline_forecast=total_baseline_forecast,
        total_variance=total_variance,
        total_budget_forecast_variance=total_budget_forecast_variance,
        overall_accuracy=overall_accuracy,
        over_forecast_count=over_forecast_count,
        under_forecast_count=under_forecast_count,
        on_forecast_count=on_forecast_count,
        forecast_risk_count=forecast_risk_count,
        forecast_health=forecast_health,
        forecast_message=forecast_message
    )

@app.route("/forecast-history/<int:budget_id>")
def forecast_history(budget_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Budgets", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM forecast_history
        WHERE budget_id = %s
        ORDER BY id DESC
    """, (
        budget_id,
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "forecast_history.html",
        history=history
    )

@app.route("/profitability-dashboard")
def profitability_dashboard():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Budgets", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (projects.id)
            projects.id,
            projects.name,
            projects.estimated_budget,
            projects.actual_cost,
            projects.revenue,
            projects.profit_forecast,
            projects.cost_category,
            projects.benefits_realisation_value
        FROM projects
        WHERE projects.user_id = %s
        AND COALESCE(projects.is_archived, FALSE) = FALSE
        ORDER BY projects.id DESC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    profitability_data = []

    total_budget = 0
    total_actual = 0
    total_revenue = 0
    total_profit = 0
    total_forecast_profit = 0
    total_benefits_value = 0

    profitable_projects = 0
    loss_projects = 0
    high_profit_projects = 0

    for project in projects:

        budget = float(project["estimated_budget"] or 0)
        actual = float(project["actual_cost"] or 0)
        revenue = float(project["revenue"] or 0)
        profit_forecast = float(project["profit_forecast"] or 0)
        benefits_value = float(project["benefits_realisation_value"] or 0)

        if revenue == 0:
            revenue = budget

        profit = revenue - actual

        total_budget += budget
        total_actual += actual
        total_revenue += revenue
        total_profit += profit
        total_forecast_profit += profit_forecast
        total_benefits_value += benefits_value

        if actual > 0:
            roi_percent = round((profit / actual) * 100)
        else:
            roi_percent = 0

        if revenue > 0:
            profitability_percent = round((profit / revenue) * 100)
        else:
            profitability_percent = 0

        if profit > 0 and roi_percent >= 30:
            status = "High Profit"
            high_profit_projects += 1
            profitable_projects += 1
        elif profit >= 0:
            status = "Profitable"
            profitable_projects += 1
        else:
            status = "Loss"
            loss_projects += 1

        profitability_data.append({
            "project_name": project["name"],
            "budget": budget,
            "actual": actual,
            "revenue": revenue,
            "profit": profit,
            "profit_forecast": profit_forecast,
            "benefits_value": benefits_value,
            "roi_percent": roi_percent,
            "profitability_percent": profitability_percent,
            "cost_category": project["cost_category"] or "Not Categorised",
            "status": status
        })

    if total_actual > 0:
        portfolio_roi = round((total_profit / total_actual) * 100)
    else:
        portfolio_roi = 0

    profitability_data = sorted(
        profitability_data,
        key=lambda item: item["profit"],
        reverse=True
    )

    conn.close()

    return render_template(
        "profitability_dashboard.html",
        profitability_data=profitability_data,
        total_budget=total_budget,
        total_actual=total_actual,
        total_revenue=total_revenue,
        total_profit=total_profit,
        total_forecast_profit=total_forecast_profit,
        total_benefits_value=total_benefits_value,
        portfolio_roi=portfolio_roi,
        profitable_projects=profitable_projects,
        loss_projects=loss_projects,
        high_profit_projects=high_profit_projects
    )

@app.route("/resource-allocation")
def resource_allocation():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Team", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (team_members.id)
            *
        FROM team_members
        WHERE user_id = %s
        ORDER BY team_members.id DESC
    """, (
        session["user_id"],
    ))

    team_members = cursor.fetchall()

    allocation_data = []

    total_resources = len(team_members)
    available_count = 0
    allocated_count = 0
    overallocated_count = 0

    for member in team_members:

        cursor.execute("""
            SELECT DISTINCT ON (tasks.id)
                tasks.id,
                tasks.title,
                tasks.status,
                tasks.priority,
                tasks.due_date,
                projects.name AS project_name,
                projects.id AS project_id
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
            ORDER BY tasks.id, tasks.due_date ASC
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        tasks = cursor.fetchall()

        active_tasks = [
            task for task in tasks
            if task["status"] != "Completed"
        ]

        completed_tasks = [
            task for task in tasks
            if task["status"] == "Completed"
        ]

        project_split = {}

        for task in active_tasks:
            project_name = task["project_name"] or "No Project"

            if project_name not in project_split:
                project_split[project_name] = 0

            project_split[project_name] += 1

        resource_capacity = int(member.get("resource_capacity") or 100)
        planned_allocation = int(member.get("planned_allocation") or 100)

        actual_allocation = min(
            len(active_tasks) * 10,
            150
        )

        if resource_capacity > 0:
            utilisation = round(
                (actual_allocation / resource_capacity) * 100
            )
        else:
            utilisation = 0

        if utilisation >= 100:
            allocation_status = "Overallocated"
            overallocated_count += 1
        elif utilisation >= 60:
            allocation_status = "Allocated"
            allocated_count += 1
        else:
            allocation_status = "Available"
            available_count += 1

        allocation_gap = planned_allocation - actual_allocation

        cursor.execute("""
            UPDATE team_members
            SET
                actual_allocation = %s,
                allocation_percentage = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            actual_allocation,
            utilisation,
            member["id"],
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO resource_allocation_history
            (
                team_member_id,
                user_id,
                active_tasks,
                completed_tasks,
                utilisation,
                allocation_status,
                planned_allocation,
                actual_allocation,
                notes,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            member["id"],
            session["user_id"],
            len(active_tasks),
            len(completed_tasks),
            utilisation,
            allocation_status,
            planned_allocation,
            actual_allocation,
            "Resource allocation snapshot",
            str(date.today())
        ))

        allocation_data.append({
            "member": member,
            "tasks": tasks,
            "active_tasks": len(active_tasks),
            "completed_tasks": len(completed_tasks),
            "utilisation": utilisation,
            "allocation_status": allocation_status,
            "planned_allocation": planned_allocation,
            "actual_allocation": actual_allocation,
            "allocation_gap": allocation_gap,
            "resource_capacity": resource_capacity,
            "project_split": project_split
        })

    conn.commit()
    conn.close()

    return render_template(
        "resource_allocation.html",
        allocation_data=allocation_data,
        total_resources=total_resources,
        available_count=available_count,
        allocated_count=allocated_count,
        overallocated_count=overallocated_count
    )


@app.route("/resource-allocation-history/<int:team_member_id>")
def resource_allocation_history(team_member_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Team", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM resource_allocation_history
        WHERE team_member_id = %s
        AND user_id = %s
        ORDER BY id DESC
    """, (
        team_member_id,
        session["user_id"]
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "resource_allocation_history.html",
        history=history
    )


@app.route("/ai-risk-engine")
def ai_risk_engine():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            risks.*,
            projects.name AS project_name
        FROM risks
        LEFT JOIN projects
        ON risks.project_id = projects.id
        WHERE risks.user_id = %s
        ORDER BY risks.id DESC
    """, (
        session["user_id"],
    ))

    risks = cursor.fetchall()

    ai_risks = []

    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0
    escalation_count = 0

    for risk in risks:

        severity = int(risk.get("severity_score") or 0)
        status = risk.get("status") or "Open"

        probability = int(risk.get("probability") or 0) if risk.get("probability") else 0
        impact = int(risk.get("impact") or 0) if risk.get("impact") else 0

        if probability == 0:
            probability = min(5, max(1, round(severity / 2)))

        if impact == 0:
            impact = min(5, max(1, round(severity / 2)))

        predictive_score = min(
            100,
            (probability * impact * 4) + (severity * 5)
        )

        if status == "Closed":
            ai_level = "Closed"
            recommendation = "Risk is closed. No active escalation required."
            escalation_warning = "No Escalation Required"
            confidence_score = 90

        elif predictive_score >= 80:
            ai_level = "Critical"
            recommendation = (
                "Escalate immediately, confirm ownership, create a mitigation plan "
                "and review this risk in the next governance meeting."
            )
            escalation_warning = "Escalation Recommended"
            confidence_score = 85
            critical_count += 1
            escalation_count += 1

        elif predictive_score >= 60:
            ai_level = "High"
            recommendation = (
                "Assign a clear owner, review mitigation progress weekly "
                "and monitor trigger conditions."
            )
            escalation_warning = "Escalation Recommended"
            confidence_score = 80
            high_count += 1
            escalation_count += 1

        elif predictive_score >= 30:
            ai_level = "Medium"
            recommendation = (
                "Monitor regularly, keep mitigation actions updated "
                "and review during project status meetings."
            )
            escalation_warning = "Monitor Closely"
            confidence_score = 75
            medium_count += 1

        else:
            ai_level = "Low"
            recommendation = (
                "Keep under observation during normal project reviews."
            )
            escalation_warning = "No Escalation Required"
            confidence_score = 70
            low_count += 1

        risk_explanation = (
            f"Predictive score uses severity ({severity}), "
            f"probability ({probability}) and impact ({impact})."
        )

        mitigation_status = (
            risk.get("mitigation")
            or risk.get("mitigation_plan")
            or risk.get("response_plan")
            or "No mitigation recorded"
        )

        ai_risks.append({
            "id": risk["id"],
            "title": risk["title"],
            "project_name": risk["project_name"] or "No Project",
            "owner": risk.get("owner") or "Not assigned",
            "status": status,
            "severity_score": severity,
            "probability": probability,
            "impact": impact,
            "predictive_score": predictive_score,
            "ai_level": ai_level,
            "escalation_warning": escalation_warning,
            "recommendation": recommendation,
            "confidence_score": confidence_score,
            "risk_explanation": risk_explanation,
            "mitigation_status": mitigation_status
        })

    total_risks = len(ai_risks)

    open_risks = len([
        item for item in ai_risks
        if item["status"] != "Closed"
    ])

    if total_risks > 0:
        critical_percentage = round((critical_count / total_risks) * 100)
    else:
        critical_percentage = 0

    if escalation_count > 0:
        executive_risk_summary = (
            f"{escalation_count} risk(s) require escalation. "
            f"Critical risk concentration is {critical_percentage}%."
        )
    else:
        executive_risk_summary = (
            "No immediate AI escalation is required based on current risk scoring."
        )

    model_notes = [
        "Risk scoring uses severity, probability and impact.",
        "Where probability or impact is missing, the model estimates them from severity.",
        "Closed risks are excluded from active escalation pressure.",
        "Recommendations are rule-based at this milestone and will become more predictive later.",
        "Future risk trends will compare current scores against historical snapshots."
    ]

    pipe_cleaning_notes = [
        "Add dedicated probability and impact fields if missing from the Risk Register.",
        "Add risk trend history for movement over time.",
        "Add risk heatmaps by project and portfolio.",
        "Add mitigation progress tracking.",
        "Add AI confidence scoring history.",
        "Add escalation outcome tracking."
    ]

    conn.close()

    return render_template(
        "ai_risk_engine.html",
        ai_risks=ai_risks,
        total_risks=total_risks,
        open_risks=open_risks,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        escalation_count=escalation_count,
        critical_percentage=critical_percentage,
        executive_risk_summary=executive_risk_summary,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )

@app.route("/ai-project-intelligence")
def ai_project_intelligence():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    project_intelligence = []

    healthy_count = 0
    watch_count = 0
    at_risk_count = 0
    incomplete_data_count = 0

    for project in projects:

        project_id = project["id"]

        cursor.execute("""
            SELECT COUNT(*) AS total_tasks
            FROM tasks
            WHERE project_id = %s
        """, (
            project_id,
        ))
        total_tasks = cursor.fetchone()["total_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS completed_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Completed'
        """, (
            project_id,
        ))
        completed_tasks = cursor.fetchone()["completed_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS blocked_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Blocked'
        """, (
            project_id,
        ))
        blocked_tasks = cursor.fetchone()["blocked_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS overdue_tasks
            FROM tasks
            WHERE project_id = %s
            AND due_date IS NOT NULL
            AND due_date != ''
            AND due_date < %s
            AND status != 'Completed'
        """, (
            project_id,
            str(date.today())
        ))
        overdue_tasks = cursor.fetchone()["overdue_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS open_risks
            FROM risks
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project_id,
        ))
        open_risks = cursor.fetchone()["open_risks"]

        cursor.execute("""
            SELECT COUNT(*) AS open_issues
            FROM issues
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project_id,
        ))
        open_issues = cursor.fetchone()["open_issues"]

        cursor.execute("""
            SELECT
                COALESCE(SUM(budget_amount), 0) AS total_budget,
                COALESCE(SUM(actual_cost), 0) AS actual_cost,
                COALESCE(SUM(forecast_cost), 0) AS forecast_cost
            FROM budgets
            WHERE project_id = %s
            AND user_id = %s
        """, (
            project_id,
            session["user_id"]
        ))

        budget_data = cursor.fetchone()

        total_budget = float(budget_data["total_budget"] or 0)
        actual_cost = float(budget_data["actual_cost"] or 0)
        forecast_cost = float(budget_data["forecast_cost"] or 0)

        if total_tasks > 0:
            completion_rate = round((completed_tasks / total_tasks) * 100)
        else:
            completion_rate = 0

        if total_budget > 0:
            budget_usage = round((actual_cost / total_budget) * 100)
            forecast_usage = round((forecast_cost / total_budget) * 100)
        else:
            budget_usage = 0
            forecast_usage = 0

        data_quality_flags = []

        if total_tasks == 0:
            data_quality_flags.append("No tasks linked")

        if open_risks == 0:
            data_quality_flags.append("No open risks recorded")

        if open_issues == 0:
            data_quality_flags.append("No open issues recorded")

        if total_budget == 0:
            data_quality_flags.append("No budget data")

        data_quality_score = 100

        if total_tasks == 0:
            data_quality_score -= 35

        if total_budget == 0:
            data_quality_score -= 20

        if open_risks == 0 and open_issues == 0:
            data_quality_score -= 10

        data_quality_score = max(0, data_quality_score)

        risk_points = (
            overdue_tasks * 8
            + blocked_tasks * 10
            + open_risks * 6
            + open_issues * 6
        )

        budget_pressure = 0

        if budget_usage > 100:
            budget_pressure = 20
        elif budget_usage > 85:
            budget_pressure = 10

        forecast_pressure = 0

        if forecast_usage > 100:
            forecast_pressure = 15
        elif forecast_usage > 85:
            forecast_pressure = 8

        health_prediction = max(
            0,
            min(
                100,
                100
                - risk_points
                - budget_pressure
                - forecast_pressure
                + round(completion_rate * 0.2)
            )
        )

        if data_quality_score < 50:
            ai_status = "Insufficient Data"
            forecast = (
                "Project intelligence is limited because key delivery data is missing."
            )
            incomplete_data_count += 1

        elif health_prediction >= 75:
            ai_status = "Healthy"
            forecast = "Project is likely to stay on track based on current delivery, risk and budget data."
            healthy_count += 1

        elif health_prediction >= 50:
            ai_status = "Watch"
            forecast = "Project may need management attention. Review blockers, risks, issues and budget pressure."
            watch_count += 1

        else:
            ai_status = "At Risk"
            forecast = "Project has a high chance of delay, escalation or financial pressure."
            at_risk_count += 1

        if data_quality_score >= 80:
            confidence_score = 85
        elif data_quality_score >= 50:
            confidence_score = 65
        else:
            confidence_score = 40

        prediction_explanation = (
            f"Health prediction uses completion rate ({completion_rate}%), "
            f"overdue tasks ({overdue_tasks}), blocked tasks ({blocked_tasks}), "
            f"risks ({open_risks}), issues ({open_issues}), "
            f"budget usage ({budget_usage}%) and forecast usage ({forecast_usage}%)."
        )

        project_intelligence.append({
            "project_name": project["name"],
            "status": project["status"],
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": completion_rate,
            "overdue_tasks": overdue_tasks,
            "blocked_tasks": blocked_tasks,
            "open_risks": open_risks,
            "open_issues": open_issues,
            "total_budget": total_budget,
            "actual_cost": actual_cost,
            "forecast_cost": forecast_cost,
            "budget_usage": budget_usage,
            "forecast_usage": forecast_usage,
            "data_quality_score": data_quality_score,
            "data_quality_flags": data_quality_flags,
            "health_prediction": health_prediction,
            "ai_status": ai_status,
            "forecast": forecast,
            "confidence_score": confidence_score,
            "prediction_explanation": prediction_explanation
        })

    total_projects = len(project_intelligence)

    if total_projects > 0:
        average_health = round(
            sum(item["health_prediction"] for item in project_intelligence)
            / total_projects
        )
    else:
        average_health = 0

    executive_summary = (
        f"AI analysed {total_projects} project(s). "
        f"Average predicted project health is {average_health}%. "
        f"{at_risk_count} project(s) are at risk, "
        f"{watch_count} require monitoring, "
        f"and {incomplete_data_count} have insufficient data."
    )

    model_notes = [
        "Project Health Prediction uses delivery progress, overdue work, blockers, risks, issues and budget pressure.",
        "Projects with no tasks or no budget data receive a lower data quality score.",
        "100% health is no longer given automatically where project data is incomplete.",
        "Confidence score is based on data completeness.",
        "Recommendations are rule-based at this milestone and will become more predictive later."
    ]

    pipe_cleaning_notes = [
        "Add milestone prediction.",
        "Add delay prediction history.",
        "Add success probability trend.",
        "Add schedule forecasting integration.",
        "Add budget forecasting integration.",
        "Add portfolio intelligence roll-up.",
        "Add confidence score history.",
        "Add project-specific AI commentary."
    ]

    conn.close()

    return render_template(
        "ai_project_intelligence.html",
        project_intelligence=project_intelligence,
        total_projects=total_projects,
        healthy_count=healthy_count,
        watch_count=watch_count,
        at_risk_count=at_risk_count,
        incomplete_data_count=incomplete_data_count,
        average_health=average_health,
        executive_summary=executive_summary,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )


@app.route("/ai-sprint-management")
def ai_sprint_management():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

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
        AND tasks.status != 'Completed'
        ORDER BY
            CASE
                WHEN tasks.priority = 'High' THEN 1
                WHEN tasks.priority = 'Medium' THEN 2
                ELSE 3
            END,
            tasks.due_date ASC
    """, (
        session["user_id"],
    ))

    tasks = cursor.fetchall()

    sprint_recommendations = []

    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0
    blocked_count = 0
    overdue_count = 0
    unassigned_count = 0

    workload_by_person = {}

    for task in tasks:

        priority = task["priority"] or "Low"
        status = task["status"] or "Pending"
        due_date = task["due_date"]
        assigned_to = task["assigned_to"] or "Unassigned"

        if assigned_to not in workload_by_person:
            workload_by_person[assigned_to] = 0

        workload_by_person[assigned_to] += 1

        ai_priority_score = 0
        score_reasons = []

        if priority == "High":
            ai_priority_score += 30
            score_reasons.append("High priority")
        elif priority == "Medium":
            ai_priority_score += 18
            score_reasons.append("Medium priority")
        else:
            ai_priority_score += 8
            score_reasons.append("Low priority")

        if status == "Blocked":
            ai_priority_score += 25
            blocked_count += 1
            score_reasons.append("Blocked work")

        if due_date and str(due_date) < str(date.today()):
            ai_priority_score += 30
            overdue_count += 1
            score_reasons.append("Overdue task")

        elif due_date and str(due_date) == str(date.today()):
            ai_priority_score += 15
            score_reasons.append("Due today")

        if assigned_to == "Unassigned":
            ai_priority_score += 10
            unassigned_count += 1
            score_reasons.append("Unassigned task")

        ai_priority_score = min(ai_priority_score, 100)

        if ai_priority_score >= 80:
            sprint_action = "Move into the current sprint immediately and review in daily stand-up."
            sprint_level = "Critical"
            critical_count += 1
        elif ai_priority_score >= 60:
            sprint_action = "Prioritise in the next sprint and assign clear ownership."
            sprint_level = "High"
            high_count += 1
        elif ai_priority_score >= 35:
            sprint_action = "Schedule after critical and high-priority work."
            sprint_level = "Medium"
            medium_count += 1
        else:
            sprint_action = "Keep in backlog for later planning."
            sprint_level = "Low"
            low_count += 1

        if assigned_to != "Unassigned" and workload_by_person.get(assigned_to, 0) > 5:
            capacity_warning = "Assigned person may have high workload."
        elif assigned_to == "Unassigned":
            capacity_warning = "Task needs an owner before sprint commitment."
        else:
            capacity_warning = "No immediate capacity warning."

        sprint_recommendations.append({
            "title": task["title"],
            "project_name": task["project_name"],
            "priority": priority,
            "status": status,
            "due_date": due_date,
            "assigned_to": assigned_to,
            "ai_priority_score": ai_priority_score,
            "sprint_level": sprint_level,
            "sprint_action": sprint_action,
            "score_reasons": score_reasons,
            "capacity_warning": capacity_warning
        })

    sprint_recommendations = sorted(
        sprint_recommendations,
        key=lambda item: item["ai_priority_score"],
        reverse=True
    )

    total_items = len(sprint_recommendations)

    if total_items > 0:
        average_sprint_score = round(
            sum(item["ai_priority_score"] for item in sprint_recommendations)
            / total_items
        )
    else:
        average_sprint_score = 0

    recommended_current_sprint = [
        item for item in sprint_recommendations
        if item["sprint_level"] in ["Critical", "High"]
    ]

    executive_sprint_summary = (
        f"AI reviewed {total_items} open task(s). "
        f"{critical_count} are critical, {high_count} are high priority, "
        f"{blocked_count} are blocked and {overdue_count} are overdue."
    )

    model_notes = [
        "Sprint score uses priority, blocked status, due date urgency and assignment status.",
        "Critical sprint items are now based on a 0-100 score instead of a small static score.",
        "Unassigned work increases sprint planning risk.",
        "Blocked and overdue work receive higher sprint urgency.",
        "Recommendations are rule-based at this milestone and will become more predictive later."
    ]

    pipe_cleaning_notes = [
        "Add sprint velocity tracking.",
        "Add team capacity linkage.",
        "Add blocker prediction.",
        "Add sprint burn-down charts.",
        "Add sprint planning assistant.",
        "Add auto sprint generation.",
        "Add workload optimisation.",
        "Add sprint history and forecast accuracy tracking."
    ]

    conn.close()

    return render_template(
        "ai_sprint_management.html",
        sprint_recommendations=sprint_recommendations,
        recommended_current_sprint=recommended_current_sprint,
        total_items=total_items,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        blocked_count=blocked_count,
        overdue_count=overdue_count,
        unassigned_count=unassigned_count,
        average_sprint_score=average_sprint_score,
        executive_sprint_summary=executive_sprint_summary,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )


@app.route("/ai-executive-assistant")
def ai_executive_assistant():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT COUNT(*) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))
    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS total_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
    """, (
        session["user_id"],
    ))
    total_tasks = cursor.fetchone()["total_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS completed_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Completed'
    """, (
        session["user_id"],
    ))
    completed_tasks = cursor.fetchone()["completed_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS overdue_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.due_date IS NOT NULL
        AND tasks.due_date != ''
        AND tasks.due_date < %s
        AND tasks.status != 'Completed'
    """, (
        session["user_id"],
        str(date.today())
    ))
    overdue_tasks = cursor.fetchone()["overdue_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS blocked_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Blocked'
    """, (
        session["user_id"],
    ))
    blocked_tasks = cursor.fetchone()["blocked_tasks"]

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

    cursor.execute("""
        SELECT COUNT(*) AS pending_changes
        FROM changes
        WHERE user_id = %s
        AND status != 'Approved'
    """, (
        session["user_id"],
    ))
    pending_changes = cursor.fetchone()["pending_changes"]

    cursor.execute("""
        SELECT
            COALESCE(SUM(budget_amount), 0) AS total_budget,
            COALESCE(SUM(actual_cost), 0) AS total_actual_cost,
            COALESCE(SUM(forecast_cost), 0) AS total_forecast_cost
        FROM budgets
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))
    budget_data = cursor.fetchone()

    total_budget = float(budget_data["total_budget"] or 0)
    total_actual_cost = float(budget_data["total_actual_cost"] or 0)
    total_forecast_cost = float(budget_data["total_forecast_cost"] or 0)

    cursor.execute("""
        SELECT DISTINCT ON (project_prioritisation.project_id)
            project_prioritisation.*,
            projects.name AS project_name
        FROM project_prioritisation
        LEFT JOIN projects
        ON project_prioritisation.project_id = projects.id
        WHERE project_prioritisation.user_id = %s
        ORDER BY
            project_prioritisation.project_id,
            project_prioritisation.priority_score DESC,
            project_prioritisation.id DESC
        LIMIT 5
    """, (
        session["user_id"],
    ))
    top_priorities = cursor.fetchall()

    conn.close()

    if total_tasks > 0:
        completion_rate = round((completed_tasks / total_tasks) * 100)
    else:
        completion_rate = 0

    if total_budget > 0:
        budget_usage = round((total_actual_cost / total_budget) * 100)
        forecast_usage = round((total_forecast_cost / total_budget) * 100)
    else:
        budget_usage = 0
        forecast_usage = 0

    governance_pressure = min(
        100,
        (open_risks * 2)
        + (open_issues * 2)
        + pending_changes
        + blocked_tasks
    )

    delivery_pressure = min(
        100,
        (overdue_tasks * 3)
        + (blocked_tasks * 4)
        + max(0, 60 - completion_rate)
    )

    financial_pressure = max(
        budget_usage,
        forecast_usage
    )

    health_score = max(
        0,
        min(
            100,
            100
            - round(governance_pressure * 0.35)
            - round(delivery_pressure * 0.35)
            - round(financial_pressure * 0.30)
            + round(completion_rate * 0.20)
        )
    )

    risk_exposure = min(
        100,
        (open_risks * 3)
        + (open_issues * 2)
        + blocked_tasks
    )

    financial_health = max(
        0,
        min(
            100,
            100 - financial_pressure
        )
    )

    if health_score >= 75:
        portfolio_status = "Healthy"
        executive_summary = (
            "Portfolio position is healthy. Current delivery, governance and financial indicators "
            "suggest the portfolio is broadly under control."
        )
        board_recommendation = (
            "Continue monitoring priority projects and maintain the current governance rhythm."
        )

    elif health_score >= 50:
        portfolio_status = "Monitor"
        executive_summary = (
            "Portfolio position requires attention. Delivery, governance or financial indicators "
            "show pressure that should be reviewed."
        )
        board_recommendation = (
            "Review open risks, issues, blocked work, budget exposure and priority projects "
            "in the next governance meeting."
        )

    else:
        portfolio_status = "At Risk"
        executive_summary = (
            "Portfolio position is at risk. Current indicators suggest that leadership intervention "
            "may be required."
        )
        board_recommendation = (
            "Escalate portfolio health, review recovery plans and assign owners for urgent corrective actions."
        )

    strategic_actions = []

    if open_risks > 0:
        strategic_actions.append(
            f"Review ownership and mitigation plans for {open_risks} open risk(s)."
        )

    if open_issues > 0:
        strategic_actions.append(
            f"Confirm resolution plans for {open_issues} open issue(s)."
        )

    if blocked_tasks > 0:
        strategic_actions.append(
            f"Escalate {blocked_tasks} blocked task(s) affecting delivery flow."
        )

    if overdue_tasks > 0:
        strategic_actions.append(
            f"Review delivery dates for {overdue_tasks} overdue task(s)."
        )

    if budget_usage > 85:
        strategic_actions.append(
            f"Review budget usage at {budget_usage}% and agree financial controls."
        )

    if forecast_usage > 85:
        strategic_actions.append(
            f"Review forecast usage at {forecast_usage}% before cost pressure increases."
        )

    if not strategic_actions:
        strategic_actions.append(
            "No urgent strategic actions detected from current indicators."
        )

    confidence_score = 70

    if total_projects > 0:
        confidence_score += 5

    if total_tasks > 0:
        confidence_score += 10

    if total_budget > 0:
        confidence_score += 5

    if open_risks > 0 or open_issues > 0:
        confidence_score += 5

    confidence_score = min(confidence_score, 95)

    model_notes = [
        "Portfolio health is calculated from governance pressure, delivery pressure, financial pressure and completion rate.",
        "Duplicate project rankings are reduced using one prioritisation record per project.",
        "Board recommendations are generated from risk, issue, blocked work, overdue work and budget indicators.",
        "Confidence score is based on available project, task, governance and budget data.",
        "Recommendations are rule-based at this milestone and will become more predictive later."
    ]

    pipe_cleaning_notes = [
        "Add board pack generation.",
        "Add executive dashboard comparison.",
        "Add strategic objective tracking.",
        "Add benefits realisation tracking.",
        "Add executive action register.",
        "Add governance reporting pack.",
        "Add AI briefing pack export.",
        "Add portfolio forecasting."
    ]

    return render_template(
        "ai_executive_assistant.html",
        total_projects=total_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        completion_rate=completion_rate,
        overdue_tasks=overdue_tasks,
        blocked_tasks=blocked_tasks,
        open_risks=open_risks,
        open_issues=open_issues,
        pending_changes=pending_changes,
        health_score=health_score,
        risk_exposure=risk_exposure,
        financial_health=financial_health,
        budget_usage=budget_usage,
        forecast_usage=forecast_usage,
        governance_pressure=governance_pressure,
        delivery_pressure=delivery_pressure,
        portfolio_status=portfolio_status,
        top_priorities=top_priorities,
        executive_summary=executive_summary,
        board_recommendation=board_recommendation,
        strategic_actions=strategic_actions,
        confidence_score=confidence_score,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )


@app.route("/ai-predictive-risk-scoring")
def ai_predictive_risk_scoring():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    risk_predictions = []

    for project in projects:

        project_id = project["id"]

        cursor.execute("""
            SELECT COUNT(*) AS total_tasks
            FROM tasks
            WHERE project_id = %s
        """, (
            project_id,
        ))
        total_tasks = cursor.fetchone()["total_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS completed_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Completed'
        """, (
            project_id,
        ))
        completed_tasks = cursor.fetchone()["completed_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS blocked_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Blocked'
        """, (
            project_id,
        ))
        blocked_tasks = cursor.fetchone()["blocked_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS overdue_tasks
            FROM tasks
            WHERE project_id = %s
            AND due_date IS NOT NULL
            AND due_date != ''
            AND due_date < %s
            AND status != 'Completed'
        """, (
            project_id,
            str(date.today())
        ))
        overdue_tasks = cursor.fetchone()["overdue_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS open_risks
            FROM risks
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project_id,
        ))
        open_risks = cursor.fetchone()["open_risks"]

        cursor.execute("""
            SELECT COUNT(*) AS open_issues
            FROM issues
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project_id,
        ))
        open_issues = cursor.fetchone()["open_issues"]

        if total_tasks > 0:
            completion_rate = round(
                (completed_tasks / total_tasks) * 100
            )
        else:
            completion_rate = 0

        risk_score = 0

        risk_score += overdue_tasks * 15
        risk_score += blocked_tasks * 15
        risk_score += open_risks * 10
        risk_score += open_issues * 8

        if completion_rate < 30 and total_tasks > 0:
            risk_score += 20

        risk_score = min(risk_score, 100)

        if risk_score >= 70:
            prediction = "High Risk"
            recommendation = (
                "Immediate management attention is required."
            )

        elif risk_score >= 40:
            prediction = "Medium Risk"
            recommendation = (
                "Monitor closely and review delivery blockers."
            )

        else:
            prediction = "Low Risk"
            recommendation = (
                "Project currently appears stable."
            )

        risk_drivers = []

        if overdue_tasks > 0:
            risk_drivers.append(
                f"{overdue_tasks} overdue task(s)"
            )

        if blocked_tasks > 0:
            risk_drivers.append(
                f"{blocked_tasks} blocked task(s)"
            )

        if open_risks > 0:
            risk_drivers.append(
                f"{open_risks} open risk(s)"
            )

        if open_issues > 0:
            risk_drivers.append(
                f"{open_issues} open issue(s)"
            )

        if completion_rate < 30 and total_tasks > 0:
            risk_drivers.append(
                "Low completion rate"
            )

        if total_tasks == 0:

            prediction = "Insufficient Data"

            recommendation = (
                "Add tasks, risks and issues before risk prediction can be trusted."
            )

        confidence_score = 40

        if total_tasks > 0:
            confidence_score += 20

        if open_risks > 0:
            confidence_score += 15

        if open_issues > 0:
            confidence_score += 15

        confidence_score = min(
            confidence_score,
            100
        )

        escalation_forecast = "No"

        if risk_score >= 70:
            escalation_forecast = "Likely"

        elif risk_score >= 40:
            escalation_forecast = "Possible"

        risk_predictions.append({

            "project_name": project["name"],
            "status": project["status"],

            "completion_rate": completion_rate,

            "overdue_tasks": overdue_tasks,
            "blocked_tasks": blocked_tasks,
            "open_risks": open_risks,
            "open_issues": open_issues,

            "risk_score": risk_score,

            "prediction": prediction,
            "recommendation": recommendation,

            "confidence_score": confidence_score,

            "risk_drivers": risk_drivers,

            "escalation_forecast": escalation_forecast

        })

    risk_predictions = sorted(
        risk_predictions,
        key=lambda x: x["risk_score"],
        reverse=True
    )

    conn.close()

    high_risk_count = len([
        x for x in risk_predictions
        if x["prediction"] == "High Risk"
    ])

    medium_risk_count = len([
        x for x in risk_predictions
        if x["prediction"] == "Medium Risk"
    ])

    low_risk_count = len([
        x for x in risk_predictions
        if x["prediction"] == "Low Risk"
    ])

    model_notes = [

        "Risk score uses overdue tasks, blocked work, open risks, open issues and completion performance.",

        "Projects with no delivery data are marked as Insufficient Data.",

        "Confidence score reflects available evidence.",

        "Escalation forecasts are generated from risk severity.",

        "Current model is rules-based and will become predictive later."

    ]

    pipe_cleaning_notes = [

        "Risk trend analysis",

        "Escalation forecasting",

        "Risk heatmaps",

        "Portfolio risk ranking",

        "Predictive risk engine",

        "Confidence percentages",

        "Risk learning models",

        "Future risk forecasting"

    ]

    return render_template(
        "ai_predictive_risk_scoring.html",

        risk_predictions=risk_predictions,

        high_risk_count=high_risk_count,
        medium_risk_count=medium_risk_count,
        low_risk_count=low_risk_count,

        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )


@app.route("/ai-budget-forecasting")
def ai_budget_forecasting():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    forecasts = []

    over_budget_count = 0
    under_budget_count = 0
    on_budget_count = 0
    insufficient_data_count = 0

    total_budget_value = 0
    total_actual_value = 0
    total_forecast_value = 0

    for project in projects:

        project_id = project["id"]

        cursor.execute("""
            SELECT
                COALESCE(SUM(budget_amount), 0) AS estimated_budget,
                COALESCE(SUM(actual_cost), 0) AS actual_cost,
                COALESCE(SUM(forecast_cost), 0) AS stored_forecast_cost
            FROM budgets
            WHERE project_id = %s
            AND user_id = %s
        """, (
            project_id,
            session["user_id"]
        ))

        budget_data = cursor.fetchone()

        estimated_budget = float(
            budget_data["estimated_budget"] or 0
        )

        actual_cost = float(
            budget_data["actual_cost"] or 0
        )

        stored_forecast_cost = float(
            budget_data["stored_forecast_cost"] or 0
        )

        cursor.execute("""
            SELECT COUNT(*) AS total_tasks
            FROM tasks
            WHERE project_id = %s
        """, (
            project_id,
        ))

        total_tasks = cursor.fetchone()["total_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS completed_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Completed'
        """, (
            project_id,
        ))

        completed_tasks = cursor.fetchone()["completed_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS overdue_tasks
            FROM tasks
            WHERE project_id = %s
            AND due_date IS NOT NULL
            AND due_date != ''
            AND due_date < %s
            AND status != 'Completed'
        """, (
            project_id,
            str(date.today())
        ))

        overdue_tasks = cursor.fetchone()["overdue_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS blocked_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Blocked'
        """, (
            project_id,
        ))

        blocked_tasks = cursor.fetchone()["blocked_tasks"]

        if total_tasks > 0:
            completion_rate = round(
                (completed_tasks / total_tasks) * 100
            )
        else:
            completion_rate = 0

        data_quality_flags = []

        if estimated_budget == 0:
            data_quality_flags.append("No approved budget")

        if actual_cost == 0:
            data_quality_flags.append("No actual cost recorded")

        if total_tasks == 0:
            data_quality_flags.append("No tasks linked")

        data_quality_score = 100

        if estimated_budget == 0:
            data_quality_score -= 35

        if actual_cost == 0:
            data_quality_score -= 25

        if total_tasks == 0:
            data_quality_score -= 25

        data_quality_score = max(0, data_quality_score)

        if estimated_budget == 0 or actual_cost == 0 or total_tasks == 0:

            forecast_cost = stored_forecast_cost or actual_cost
            forecast_status = "Insufficient Data"
            variance = forecast_cost - estimated_budget
            forecast_method = "Forecast limited because budget, actual cost or task progress data is incomplete."

            insufficient_data_count += 1

        else:

            progress_decimal = completion_rate / 100

            if progress_decimal > 0:
                eac_forecast = round(
                    actual_cost / progress_decimal,
                    2
                )
            else:
                eac_forecast = actual_cost

            pressure_adjustment = 0

            if overdue_tasks > 0:
                pressure_adjustment += overdue_tasks * 250

            if blocked_tasks > 0:
                pressure_adjustment += blocked_tasks * 300

            if stored_forecast_cost > 0:
                forecast_cost = max(
                    eac_forecast,
                    stored_forecast_cost,
                    actual_cost + pressure_adjustment
                )
            else:
                forecast_cost = max(
                    eac_forecast,
                    actual_cost + pressure_adjustment
                )

            variance = round(
                forecast_cost - estimated_budget,
                2
            )

            if variance > 0:
                forecast_status = "Over Budget"
                over_budget_count += 1
            elif variance < 0:
                forecast_status = "Under Budget"
                under_budget_count += 1
            else:
                forecast_status = "On Budget"
                on_budget_count += 1

            forecast_method = (
                "Forecast uses Estimate At Completion logic based on actual cost, "
                "completion rate, stored forecast cost, overdue work and blocked work."
            )

        if estimated_budget > 0:
            forecast_usage = round(
                (forecast_cost / estimated_budget) * 100
            )
            actual_usage = round(
                (actual_cost / estimated_budget) * 100
            )
        else:
            forecast_usage = 0
            actual_usage = 0

        confidence_score = data_quality_score

        if completion_rate > 0:
            confidence_score += 10

        confidence_score = min(confidence_score, 95)

        recommendation = "Continue normal financial monitoring."

        if forecast_status == "Over Budget":
            recommendation = (
                "Review cost drivers, validate forecast assumptions and agree financial controls."
            )
        elif forecast_status == "Under Budget":
            recommendation = (
                "Forecast is currently below budget. Confirm whether scope or costs are fully captured."
            )
        elif forecast_status == "Insufficient Data":
            recommendation = (
                "Add budget, actual cost and task progress data before relying on the forecast."
            )

        total_budget_value += estimated_budget
        total_actual_value += actual_cost
        total_forecast_value += forecast_cost

        forecasts.append({
            "project_name": project["name"],
            "estimated_budget": estimated_budget,
            "actual_cost": actual_cost,
            "stored_forecast_cost": stored_forecast_cost,
            "forecast_cost": forecast_cost,
            "variance": variance,
            "forecast_status": forecast_status,
            "forecast_usage": forecast_usage,
            "actual_usage": actual_usage,
            "completion_rate": completion_rate,
            "overdue_tasks": overdue_tasks,
            "blocked_tasks": blocked_tasks,
            "confidence_score": confidence_score,
            "forecast_method": forecast_method,
            "recommendation": recommendation,
            "data_quality_score": data_quality_score,
            "data_quality_flags": data_quality_flags
        })

    if total_budget_value > 0:
        portfolio_forecast_usage = round(
            (total_forecast_value / total_budget_value) * 100
        )
        portfolio_actual_usage = round(
            (total_actual_value / total_budget_value) * 100
        )
    else:
        portfolio_forecast_usage = 0
        portfolio_actual_usage = 0

    executive_summary = (
        f"AI reviewed {len(forecasts)} project budget forecast(s). "
        f"{over_budget_count} are forecast over budget, "
        f"{under_budget_count} are forecast under budget, "
        f"and {insufficient_data_count} have insufficient data."
    )

    model_notes = [
        "Budget forecasting uses approved budget, actual cost, completion rate, stored forecast cost, overdue work and blocked work.",
        "Forecast cost no longer simply repeats actual cost where progress data exists.",
        "Projects with missing budget, cost or task data are marked as Insufficient Data.",
        "Confidence score is based on data quality and progress evidence.",
        "Current forecasting is rule-based and will later support EAC, CPI and earned value methods."
    ]

    pipe_cleaning_notes = [
        "Add Earned Value Management.",
        "Add Estimate At Completion history.",
        "Add Cost Performance Index.",
        "Add budget burn trends.",
        "Add cashflow forecasting.",
        "Add financial risk forecasting.",
        "Add forecast confidence trend.",
        "Add monthly forecast snapshots."
    ]

    conn.close()

    return render_template(
        "ai_budget_forecasting.html",
        forecasts=forecasts,
        over_budget_count=over_budget_count,
        under_budget_count=under_budget_count,
        on_budget_count=on_budget_count,
        insufficient_data_count=insufficient_data_count,
        total_budget_value=total_budget_value,
        total_actual_value=total_actual_value,
        total_forecast_value=total_forecast_value,
        portfolio_forecast_usage=portfolio_forecast_usage,
        portfolio_actual_usage=portfolio_actual_usage,
        executive_summary=executive_summary,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )


@app.route("/ai-schedule-forecasting")
def ai_schedule_forecasting():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    forecasts = []

    on_track_count = 0
    minor_delay_count = 0
    high_delay_count = 0
    insufficient_data_count = 0

    for project in projects:

        project_id = project["id"]

        cursor.execute("""
            SELECT COUNT(*) AS total_tasks
            FROM tasks
            WHERE project_id = %s
        """, (
            project_id,
        ))

        total_tasks = cursor.fetchone()["total_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS completed_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Completed'
        """, (
            project_id,
        ))

        completed_tasks = cursor.fetchone()["completed_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS overdue_tasks
            FROM tasks
            WHERE project_id = %s
            AND due_date IS NOT NULL
            AND due_date != ''
            AND due_date < %s
            AND status != 'Completed'
        """, (
            project_id,
            str(date.today())
        ))

        overdue_tasks = cursor.fetchone()["overdue_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS blocked_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Blocked'
        """, (
            project_id,
        ))

        blocked_tasks = cursor.fetchone()["blocked_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS undated_tasks
            FROM tasks
            WHERE project_id = %s
            AND (due_date IS NULL OR due_date = '')
            AND status != 'Completed'
        """, (
            project_id,
        ))

        undated_tasks = cursor.fetchone()["undated_tasks"]

        if total_tasks > 0:
            completion_rate = round(
                (completed_tasks / total_tasks) * 100
            )
        else:
            completion_rate = 0

        data_quality_flags = []

        if total_tasks == 0:
            data_quality_flags.append("No tasks linked")

        if undated_tasks > 0:
            data_quality_flags.append(
                f"{undated_tasks} open task(s) missing due dates"
            )

        data_quality_score = 100

        if total_tasks == 0:
            data_quality_score -= 50

        if undated_tasks > 0 and total_tasks > 0:
            data_quality_score -= min(
                30,
                round((undated_tasks / total_tasks) * 100)
            )

        data_quality_score = max(0, data_quality_score)

        delay_risk = 0

        delay_risk += overdue_tasks * 20
        delay_risk += blocked_tasks * 15
        delay_risk += undated_tasks * 5

        if total_tasks > 0 and completion_rate < 30:
            delay_risk += 25
        elif total_tasks > 0 and completion_rate < 60:
            delay_risk += 10

        delay_risk = min(delay_risk, 100)

        if total_tasks == 0:
            forecast = "Insufficient Data"
            recommendation = (
                "Add tasks and due dates before schedule forecasting can be trusted."
            )
            insufficient_data_count += 1

        elif delay_risk >= 70:
            forecast = "High Delay Risk"
            recommendation = (
                "Review project plan immediately, confirm blockers, reset due dates and escalate delivery risk."
            )
            high_delay_count += 1

        elif delay_risk >= 35:
            forecast = "Minor Delay Risk"
            recommendation = (
                "Monitor schedule closely, review overdue or blocked work and update delivery dates."
            )
            minor_delay_count += 1

        else:
            forecast = "On Track"
            recommendation = (
                "Current schedule indicators are acceptable. Continue routine monitoring."
            )
            on_track_count += 1

        confidence_score = data_quality_score

        if total_tasks > 0:
            confidence_score += 10

        confidence_score = min(confidence_score, 95)

        forecast_explanation = (
            f"Delay risk uses completion rate ({completion_rate}%), "
            f"overdue tasks ({overdue_tasks}), blocked tasks ({blocked_tasks}) "
            f"and open tasks missing due dates ({undated_tasks})."
        )

        forecasts.append({
            "project_name": project["name"],
            "status": project["status"],
            "completion_rate": completion_rate,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "overdue_tasks": overdue_tasks,
            "blocked_tasks": blocked_tasks,
            "undated_tasks": undated_tasks,
            "delay_risk": delay_risk,
            "forecast": forecast,
            "recommendation": recommendation,
            "confidence_score": confidence_score,
            "data_quality_score": data_quality_score,
            "data_quality_flags": data_quality_flags,
            "forecast_explanation": forecast_explanation
        })

    forecasts = sorted(
        forecasts,
        key=lambda item: item["delay_risk"],
        reverse=True
    )

    executive_summary = (
        f"AI reviewed {len(forecasts)} project schedule forecast(s). "
        f"{high_delay_count} have high delay risk, "
        f"{minor_delay_count} have minor delay risk, "
        f"{on_track_count} are on track and "
        f"{insufficient_data_count} have insufficient schedule data."
    )

    model_notes = [
        "Schedule forecast uses completion rate, overdue tasks, blocked tasks and missing due dates.",
        "Projects with no tasks are marked as Insufficient Data.",
        "High Delay Risk is no longer assigned without supporting delay indicators.",
        "Confidence score is based on available task and due-date data.",
        "Current model is rule-based and will later support SPI, critical path and trend forecasting."
    ]

    pipe_cleaning_notes = [
        "Add milestone forecasting.",
        "Add critical path analysis.",
        "Add Schedule Performance Index.",
        "Add delivery trend forecasting.",
        "Add deadline confidence score.",
        "Add forecast timeline charts.",
        "Add schedule risk history.",
        "Add baseline versus actual finish tracking."
    ]

    conn.close()

    return render_template(
        "ai_schedule_forecasting.html",
        forecasts=forecasts,
        on_track_count=on_track_count,
        minor_delay_count=minor_delay_count,
        high_delay_count=high_delay_count,
        insufficient_data_count=insufficient_data_count,
        executive_summary=executive_summary,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )

@app.route("/ai-workload-balancer")
def ai_workload_balancer():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (LOWER(name), LOWER(role))
            *
        FROM team_members
        WHERE user_id = %s
        ORDER BY LOWER(name), LOWER(role), id DESC
    """, (
        session["user_id"],
    ))

    team_members = cursor.fetchall()

    workload_data = []

    overloaded_members = []
    available_members = []
    balanced_members = []

    duplicate_warning = False

    cursor.execute("""
        SELECT
            LOWER(name) AS member_name,
            LOWER(role) AS member_role,
            COUNT(*) AS duplicate_count
        FROM team_members
        WHERE user_id = %s
        GROUP BY LOWER(name), LOWER(role)
        HAVING COUNT(*) > 1
    """, (
        session["user_id"],
    ))

    duplicate_records = cursor.fetchall()

    if duplicate_records:
        duplicate_warning = True

    for member in team_members:

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
                LOWER(tasks.assigned_to) = LOWER(%s)
                OR task_team_members.team_member_id = %s
            )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        active_tasks = cursor.fetchone()["active_tasks"]

        capacity_limit = int(member.get("capacity_limit") or 10)

        if capacity_limit <= 0:
            capacity_limit = 10

        utilisation = min(
            100,
            round((active_tasks / capacity_limit) * 100)
        )

        if utilisation >= 85:
            workload_status = "Overloaded"
        elif utilisation >= 50:
            workload_status = "Balanced"
        else:
            workload_status = "Available"

        workload_record = {
            "id": member["id"],
            "name": member["name"],
            "role": member["role"],
            "active_tasks": active_tasks,
            "capacity_limit": capacity_limit,
            "utilisation": utilisation,
            "workload_status": workload_status,
            "recommendation": "",
            "recommended_receiver": "Not identified yet",
            "balancing_reason": "",
            "confidence_score": 75
        }

        if workload_status == "Overloaded":
            overloaded_members.append(workload_record)
        elif workload_status == "Available":
            available_members.append(workload_record)
        else:
            balanced_members.append(workload_record)

        workload_data.append(workload_record)

    for item in workload_data:

        if item["workload_status"] == "Overloaded":

            if available_members:

                receiver = sorted(
                    available_members,
                    key=lambda x: x["utilisation"]
                )[0]

                item["recommended_receiver"] = receiver["name"]

                item["recommendation"] = (
                    f"Reassign suitable work to {receiver['name']} "
                    f"because they currently have {receiver['utilisation']}% utilisation."
                )

                item["balancing_reason"] = (
                    "Recommendation is based on lowest available utilisation."
                )

            else:

                item["recommendation"] = (
                    "No clearly available receiver found. Review workload manually or consider additional resource."
                )

                item["balancing_reason"] = (
                    "All visible resources are already balanced or overloaded."
                )

        elif item["workload_status"] == "Available":

            item["recommendation"] = (
                "This team member has spare capacity and may be able to receive suitable work."
            )

            item["balancing_reason"] = (
                "Utilisation is below 50%."
            )

        else:

            item["recommendation"] = (
                "Workload is currently balanced. Continue monitoring."
            )

            item["balancing_reason"] = (
                "Utilisation is between 50% and 84%."
            )

    workload_data = sorted(
        workload_data,
        key=lambda x: x["utilisation"],
        reverse=True
    )

    total_resources = len(workload_data)
    overloaded_count = len(overloaded_members)
    available_count = len(available_members)
    balanced_count = len(balanced_members)

    if total_resources > 0:
        average_utilisation = round(
            sum(item["utilisation"] for item in workload_data)
            / total_resources
        )
    else:
        average_utilisation = 0

    executive_summary = (
        f"AI reviewed {total_resources} unique resource(s). "
        f"{overloaded_count} are overloaded, "
        f"{balanced_count} are balanced and "
        f"{available_count} have spare capacity."
    )

    model_notes = [
        "Workload balancing uses active open tasks and resource capacity limits.",
        "Duplicate team member records are deduplicated by name and role.",
        "Overloaded resources are matched to the lowest-utilised available resource where possible.",
        "Recommendations are no longer identical for every person.",
        "Current logic is rule-based and will later support skill matching and workload simulations."
    ]

    pipe_cleaning_notes = [
        "Skill-based balancing.",
        "Project-specific balancing.",
        "Capacity forecasting.",
        "Availability forecasting.",
        "Vacation awareness.",
        "Resource succession planning.",
        "Contractor recommendations.",
        "Work transfer simulation."
    ]

    conn.close()

    return render_template(
        "ai_workload_balancer.html",
        workload_data=workload_data,
        overloaded_count=overloaded_count,
        available_count=available_count,
        balanced_count=balanced_count,
        total_resources=total_resources,
        average_utilisation=average_utilisation,
        duplicate_warning=duplicate_warning,
        duplicate_records=duplicate_records,
        executive_summary=executive_summary,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )

@app.route("/ai-resource-optimisation")
def ai_resource_optimisation():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (LOWER(name), LOWER(role))
            *
        FROM team_members
        WHERE user_id = %s
        ORDER BY LOWER(name), LOWER(role), id DESC
    """, (
        session["user_id"],
    ))

    team_members = cursor.fetchall()

    cursor.execute("""
        SELECT
            LOWER(name) AS member_name,
            LOWER(role) AS member_role,
            COUNT(*) AS duplicate_count
        FROM team_members
        WHERE user_id = %s
        GROUP BY LOWER(name), LOWER(role)
        HAVING COUNT(*) > 1
    """, (
        session["user_id"],
    ))

    duplicate_records = cursor.fetchall()
    duplicate_warning = True if duplicate_records else False

    optimisation_data = []

    overloaded_resources = []
    available_resources = []
    balanced_resources = []

    for member in team_members:

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
                LOWER(tasks.assigned_to) = LOWER(%s)
                OR task_team_members.team_member_id = %s
            )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        active_tasks = cursor.fetchone()["active_tasks"]

        capacity_limit = int(member.get("capacity_limit") or 10)

        if capacity_limit <= 0:
            capacity_limit = 10

        utilisation = min(
            100,
            round((active_tasks / capacity_limit) * 100)
        )

        skills = (
            member.get("skills")
            or member.get("skillset")
            or member.get("role")
            or "No skills recorded"
        )

        availability_status = (
            member.get("availability")
            or member.get("status")
            or "Available"
        )

        if utilisation >= 85:
            optimisation = "Reduce workload"
            resource_status = "Overloaded"
        elif utilisation >= 50:
            optimisation = "Maintain"
            resource_status = "Balanced"
        else:
            optimisation = "Increase workload"
            resource_status = "Available"

        record = {
            "id": member["id"],
            "name": member["name"],
            "role": member["role"],
            "skills": skills,
            "availability_status": availability_status,
            "active_tasks": active_tasks,
            "capacity_limit": capacity_limit,
            "utilisation": utilisation,
            "resource_status": resource_status,
            "optimisation": optimisation,
            "action": "",
            "recommended_match": "Not identified yet",
            "optimisation_reason": "",
            "confidence_score": 75
        }

        if resource_status == "Overloaded":
            overloaded_resources.append(record)
        elif resource_status == "Available":
            available_resources.append(record)
        else:
            balanced_resources.append(record)

        optimisation_data.append(record)

    for item in optimisation_data:

        if item["resource_status"] == "Overloaded":

            matching_candidates = sorted(
                available_resources,
                key=lambda x: x["utilisation"]
            )

            if matching_candidates:

                receiver = matching_candidates[0]

                item["recommended_match"] = receiver["name"]

                item["action"] = (
                    f"Move suitable work from {item['name']} to {receiver['name']}."
                )

                item["optimisation_reason"] = (
                    f"{item['name']} is at {item['utilisation']}% utilisation, "
                    f"while {receiver['name']} is at {receiver['utilisation']}%."
                )

            else:

                item["action"] = (
                    "No available resource found. Consider reducing scope, extending timeline or adding resource."
                )

                item["optimisation_reason"] = (
                    "All visible resources are balanced or overloaded."
                )

        elif item["resource_status"] == "Available":

            item["action"] = (
                "This resource can receive additional suitable work."
            )

            item["optimisation_reason"] = (
                "Utilisation is below 50%."
            )

        else:

            item["action"] = (
                "Maintain current allocation and monitor workload."
            )

            item["optimisation_reason"] = (
                "Utilisation is within a balanced range."
            )

    optimisation_data = sorted(
        optimisation_data,
        key=lambda item: item["utilisation"],
        reverse=True
    )

    total_resources = len(optimisation_data)
    overloaded_count = len(overloaded_resources)
    available_count = len(available_resources)
    balanced_count = len(balanced_resources)

    if total_resources > 0:
        average_utilisation = round(
            sum(item["utilisation"] for item in optimisation_data)
            / total_resources
        )
    else:
        average_utilisation = 0

    executive_summary = (
        f"AI reviewed {total_resources} unique resource(s). "
        f"{overloaded_count} require workload reduction, "
        f"{available_count} can receive more work and "
        f"{balanced_count} should maintain current allocation."
    )

    model_notes = [
        "Resource optimisation deduplicates team members by name and role.",
        "Utilisation is calculated using open task count against capacity limit.",
        "Overloaded resources are matched to the lowest-utilised available resource.",
        "Recommendations are no longer identical for every resource.",
        "Current optimisation is rule-based and will later support skill matching and simulations."
    ]

    pipe_cleaning_notes = [
        "Add skill-based allocation.",
        "Add project matching.",
        "Add resource availability forecasting.",
        "Add capacity optimisation.",
        "Add AI workload simulations.",
        "Add resource transfer suggestions.",
        "Add hiring recommendations.",
        "Add contractor recommendations."
    ]

    conn.close()

    return render_template(
        "ai_resource_optimisation.html",
        optimisation_data=optimisation_data,
        total_resources=total_resources,
        overloaded_count=overloaded_count,
        available_count=available_count,
        balanced_count=balanced_count,
        average_utilisation=average_utilisation,
        duplicate_warning=duplicate_warning,
        duplicate_records=duplicate_records,
        executive_summary=executive_summary,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )


@app.route("/ai-portfolio-health-predictor")
def ai_portfolio_health_predictor():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT COUNT(*) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS total_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
    """, (
        session["user_id"],
    ))

    total_tasks = cursor.fetchone()["total_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS completed_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Completed'
    """, (
        session["user_id"],
    ))

    completed_tasks = cursor.fetchone()["completed_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS overdue_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.due_date IS NOT NULL
        AND tasks.due_date != ''
        AND tasks.due_date < %s
        AND tasks.status != 'Completed'
    """, (
        session["user_id"],
        str(date.today())
    ))

    overdue_tasks = cursor.fetchone()["overdue_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS blocked_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Blocked'
    """, (
        session["user_id"],
    ))

    blocked_tasks = cursor.fetchone()["blocked_tasks"]

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

    cursor.execute("""
        SELECT
            COALESCE(SUM(budget_amount), 0) AS total_budget,
            COALESCE(SUM(actual_cost), 0) AS total_actual,
            COALESCE(SUM(forecast_cost), 0) AS total_forecast
        FROM budgets
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    budget_data = cursor.fetchone()

    total_budget = float(budget_data["total_budget"] or 0)
    total_actual = float(budget_data["total_actual"] or 0)
    total_forecast = float(budget_data["total_forecast"] or 0)

    conn.close()

    if total_tasks > 0:
        completion_rate = round(
            (completed_tasks / total_tasks) * 100
        )
    else:
        completion_rate = 0

    if total_budget > 0:
        budget_usage = round((total_actual / total_budget) * 100)
        forecast_usage = round((total_forecast / total_budget) * 100)
    else:
        budget_usage = 0
        forecast_usage = 0

    data_quality_flags = []

    if total_projects == 0:
        data_quality_flags.append("No projects recorded")

    if total_tasks == 0:
        data_quality_flags.append("No tasks recorded")

    if total_budget == 0:
        data_quality_flags.append("No budget data recorded")

    data_quality_score = 100

    if total_projects == 0:
        data_quality_score -= 30

    if total_tasks == 0:
        data_quality_score -= 35

    if total_budget == 0:
        data_quality_score -= 20

    data_quality_score = max(0, data_quality_score)

    delivery_pressure = min(
        100,
        (overdue_tasks * 8)
        + (blocked_tasks * 10)
        + max(0, 50 - completion_rate)
    )

    governance_pressure = min(
        100,
        (open_risks * 6)
        + (open_issues * 5)
    )

    financial_pressure = max(
        budget_usage,
        forecast_usage
    )

    portfolio_score = max(
        0,
        min(
            100,
            100
            - round(delivery_pressure * 0.35)
            - round(governance_pressure * 0.35)
            - round(financial_pressure * 0.30)
            + round(completion_rate * 0.20)
        )
    )

    if data_quality_score < 50:
        prediction = "Insufficient Data"
        recommendation = (
            "Add project tasks, budget records and governance data before relying on portfolio prediction."
        )

    elif portfolio_score >= 75:
        prediction = "Healthy"
        recommendation = (
            "Portfolio performance is strong. Continue current governance rhythm."
        )

    elif portfolio_score >= 50:
        prediction = "Watch"
        recommendation = (
            "Portfolio requires monitoring. Review risks, issues, blocked work and budget pressure."
        )

    else:
        prediction = "At Risk"
        recommendation = (
            "Portfolio requires intervention. Escalate major delivery, risk and budget concerns."
        )

    confidence_score = data_quality_score

    if total_projects > 0:
        confidence_score += 5

    if total_tasks > 0:
        confidence_score += 5

    confidence_score = min(confidence_score, 95)

    executive_summary = (
        f"AI portfolio predictor reviewed {total_projects} project(s), "
        f"{total_tasks} task(s), {open_risks} open risk(s), "
        f"{open_issues} open issue(s), and forecast portfolio health at {portfolio_score}%."
    )

    score_explanation = (
        f"Portfolio score uses delivery pressure ({delivery_pressure}%), "
        f"governance pressure ({governance_pressure}%), financial pressure ({financial_pressure}%), "
        f"and completion rate ({completion_rate}%)."
    )

    model_notes = [
        "Portfolio health uses delivery pressure, governance pressure, financial pressure and completion rate.",
        "A 0% or unrealistic portfolio score is avoided by separating data quality from health prediction.",
        "Projects with missing task or budget data are flagged as Insufficient Data.",
        "Confidence score is based on portfolio data completeness.",
        "Current model is rule-based and will later support scenarios and predictive modelling."
    ]

    pipe_cleaning_notes = [
        "Add health trends.",
        "Add future forecasting.",
        "Add portfolio scenarios.",
        "Add predictive modelling.",
        "Add financial forecasting.",
        "Add risk forecasting.",
        "Add executive alerts.",
        "Add confidence scoring history."
    ]

    return render_template(
        "ai_portfolio_health_predictor.html",
        total_projects=total_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        completion_rate=completion_rate,
        overdue_tasks=overdue_tasks,
        blocked_tasks=blocked_tasks,
        open_risks=open_risks,
        open_issues=open_issues,
        total_budget=total_budget,
        total_actual=total_actual,
        total_forecast=total_forecast,
        budget_usage=budget_usage,
        forecast_usage=forecast_usage,
        delivery_pressure=delivery_pressure,
        governance_pressure=governance_pressure,
        financial_pressure=financial_pressure,
        data_quality_score=data_quality_score,
        data_quality_flags=data_quality_flags,
        portfolio_score=portfolio_score,
        prediction=prediction,
        recommendation=recommendation,
        confidence_score=confidence_score,
        executive_summary=executive_summary,
        score_explanation=score_explanation,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )


@app.route("/ai-project-summary-generator")
def ai_project_summary_generator():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    summaries = []

    strong_count = 0
    monitor_count = 0
    attention_count = 0
    insufficient_data_count = 0

    for project in projects:

        project_id = project["id"]

        cursor.execute("""
            SELECT COUNT(*) AS total_tasks
            FROM tasks
            WHERE project_id = %s
        """, (
            project_id,
        ))
        total_tasks = cursor.fetchone()["total_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS completed_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Completed'
        """, (
            project_id,
        ))
        completed_tasks = cursor.fetchone()["completed_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS overdue_tasks
            FROM tasks
            WHERE project_id = %s
            AND due_date IS NOT NULL
            AND due_date != ''
            AND due_date < %s
            AND status != 'Completed'
        """, (
            project_id,
            str(date.today())
        ))
        overdue_tasks = cursor.fetchone()["overdue_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS blocked_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Blocked'
        """, (
            project_id,
        ))
        blocked_tasks = cursor.fetchone()["blocked_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS open_risks
            FROM risks
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project_id,
        ))
        open_risks = cursor.fetchone()["open_risks"]

        cursor.execute("""
            SELECT COUNT(*) AS open_issues
            FROM issues
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project_id,
        ))
        open_issues = cursor.fetchone()["open_issues"]

        cursor.execute("""
            SELECT
                COALESCE(SUM(budget_amount), 0) AS total_budget,
                COALESCE(SUM(actual_cost), 0) AS actual_cost,
                COALESCE(SUM(forecast_cost), 0) AS forecast_cost
            FROM budgets
            WHERE project_id = %s
            AND user_id = %s
        """, (
            project_id,
            session["user_id"]
        ))

        budget_data = cursor.fetchone()

        total_budget = float(budget_data["total_budget"] or 0)
        actual_cost = float(budget_data["actual_cost"] or 0)
        forecast_cost = float(budget_data["forecast_cost"] or 0)

        if total_tasks > 0:
            completion_rate = round(
                (completed_tasks / total_tasks) * 100
            )
        else:
            completion_rate = 0

        if total_budget > 0:
            budget_usage = round(
                (actual_cost / total_budget) * 100
            )
            forecast_usage = round(
                (forecast_cost / total_budget) * 100
            )
        else:
            budget_usage = 0
            forecast_usage = 0

        data_quality_flags = []

        if total_tasks == 0:
            data_quality_flags.append("No tasks linked")

        if total_budget == 0:
            data_quality_flags.append("No budget data")

        if open_risks == 0:
            data_quality_flags.append("No open risks recorded")

        if open_issues == 0:
            data_quality_flags.append("No open issues recorded")

        if total_tasks == 0:
            summary_status = "Insufficient Data"
            insufficient_data_count += 1

            summary = (
                f"{project['name']} does not yet have enough delivery data for a reliable summary. "
                "Add tasks, due dates, risks, issues and budget records to generate a stronger executive summary."
            )

        elif overdue_tasks > 0 or blocked_tasks > 0:
            summary_status = "Attention Required"
            attention_count += 1

            summary = (
                f"{project['name']} requires delivery attention. "
                f"The project has {overdue_tasks} overdue task(s), {blocked_tasks} blocked task(s), "
                f"{open_risks} open risk(s), and {open_issues} open issue(s). "
                "Management should review blockers, ownership and delivery dates."
            )

        elif open_risks > 0 or open_issues > 0:
            summary_status = "Monitor"
            monitor_count += 1

            summary = (
                f"{project['name']} is progressing at {completion_rate}% completion, "
                f"with {open_risks} open risk(s) and {open_issues} open issue(s). "
                "Governance items should be reviewed in the next project meeting."
            )

        elif completion_rate >= 75:
            summary_status = "Strong"
            strong_count += 1

            summary = (
                f"{project['name']} is performing strongly with {completion_rate}% completion "
                "and no major open delivery or governance concerns currently recorded."
            )

        else:
            summary_status = "Monitor"
            monitor_count += 1

            summary = (
                f"{project['name']} is stable but should continue to be monitored. "
                f"Current completion is {completion_rate}% with {total_tasks} task(s) recorded."
            )

        highlights = []

        if completion_rate >= 75:
            highlights.append("Strong completion progress")

        if overdue_tasks == 0 and total_tasks > 0:
            highlights.append("No overdue tasks")

        if blocked_tasks == 0 and total_tasks > 0:
            highlights.append("No blocked tasks")

        concerns = []

        if overdue_tasks > 0:
            concerns.append(f"{overdue_tasks} overdue task(s)")

        if blocked_tasks > 0:
            concerns.append(f"{blocked_tasks} blocked task(s)")

        if open_risks > 0:
            concerns.append(f"{open_risks} open risk(s)")

        if open_issues > 0:
            concerns.append(f"{open_issues} open issue(s)")

        if forecast_usage > 100:
            concerns.append("Forecast cost exceeds budget")

        confidence_score = 65

        if total_tasks > 0:
            confidence_score += 15

        if total_budget > 0:
            confidence_score += 10

        if open_risks > 0 or open_issues > 0:
            confidence_score += 5

        confidence_score = min(confidence_score, 95)

        summaries.append({
            "project_name": project["name"],
            "status": project["status"],
            "completion_rate": completion_rate,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "overdue_tasks": overdue_tasks,
            "blocked_tasks": blocked_tasks,
            "open_risks": open_risks,
            "open_issues": open_issues,
            "total_budget": total_budget,
            "actual_cost": actual_cost,
            "forecast_cost": forecast_cost,
            "budget_usage": budget_usage,
            "forecast_usage": forecast_usage,
            "summary_status": summary_status,
            "summary": summary,
            "highlights": highlights,
            "concerns": concerns,
            "data_quality_flags": data_quality_flags,
            "confidence_score": confidence_score
        })

    executive_summary = (
        f"AI generated {len(summaries)} project summary record(s). "
        f"{strong_count} are strong, {monitor_count} require monitoring, "
        f"{attention_count} require attention and {insufficient_data_count} have insufficient data."
    )

    model_notes = [
        "Project summaries use completion rate, overdue work, blockers, risks, issues and budget signals.",
        "Projects with no tasks are marked as Insufficient Data instead of receiving a generic stable summary.",
        "Summaries now include highlights, concerns and data-quality flags.",
        "Confidence score is based on available delivery, governance and budget data.",
        "Current summaries are rule-based and will later support richer narrative generation."
    ]

    pipe_cleaning_notes = [
        "Add narrative summaries.",
        "Add project highlights.",
        "Add milestone summaries.",
        "Add risk summaries.",
        "Add budget summaries.",
        "Add stakeholder summaries.",
        "Add export to PDF.",
        "Add board-ready reporting."
    ]

    conn.close()

    return render_template(
        "ai_project_summary_generator.html",
        summaries=summaries,
        strong_count=strong_count,
        monitor_count=monitor_count,
        attention_count=attention_count,
        insufficient_data_count=insufficient_data_count,
        executive_summary=executive_summary,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )


@app.route("/ai-pm-copilot")
def ai_pm_copilot():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("AI", "view"):
        return "Access denied"

    if not can_use_ai_features():

        return """
        <h2>AI Feature Locked</h2>

        <p>
            AI features are only available on the Professional
            and Enterprise plans.
        </p>

        <p>
            Please upgrade your plan to use AI intelligence features.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT COUNT(*) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS total_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
    """, (
        session["user_id"],
    ))

    total_tasks = cursor.fetchone()["total_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS completed_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Completed'
    """, (
        session["user_id"],
    ))

    completed_tasks = cursor.fetchone()["completed_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS overdue_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status != 'Completed'
        AND tasks.due_date IS NOT NULL
        AND tasks.due_date != ''
        AND tasks.due_date < %s
    """, (
        session["user_id"],
        str(date.today())
    ))

    overdue_tasks = cursor.fetchone()["overdue_tasks"]

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

    cursor.execute("""
        SELECT COUNT(*) AS blocked_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status = 'Blocked'
    """, (
        session["user_id"],
    ))

    blocked_tasks = cursor.fetchone()["blocked_tasks"]

    cursor.execute("""
        SELECT COUNT(*) AS pending_changes
        FROM changes
        WHERE user_id = %s
        AND status != 'Approved'
    """, (
        session["user_id"],
    ))

    pending_changes = cursor.fetchone()["pending_changes"]

    cursor.execute("""
        SELECT
            COALESCE(SUM(budget_amount), 0) AS total_budget,
            COALESCE(SUM(actual_cost), 0) AS total_actual,
            COALESCE(SUM(forecast_cost), 0) AS total_forecast
        FROM budgets
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    budget_data = cursor.fetchone()

    conn.close()

    total_budget = float(budget_data["total_budget"] or 0)
    total_actual = float(budget_data["total_actual"] or 0)
    total_forecast = float(budget_data["total_forecast"] or 0)

    if total_tasks > 0:
        completion_rate = round(
            (completed_tasks / total_tasks) * 100
        )
    else:
        completion_rate = 0

    if total_budget > 0:
        budget_usage = round((total_actual / total_budget) * 100)
        forecast_usage = round((total_forecast / total_budget) * 100)
    else:
        budget_usage = 0
        forecast_usage = 0

    recommendations = []
    action_items = []

    urgency_score = 0

    if overdue_tasks > 0:
        urgency_score += overdue_tasks * 8

        recommendations.append(
            f"Review {overdue_tasks} overdue task(s) immediately."
        )

        action_items.append({
            "area": "Delivery",
            "priority": "High",
            "action": f"Review and re-plan {overdue_tasks} overdue task(s).",
            "mode": "Delivery Mode"
        })

    if blocked_tasks > 0:
        urgency_score += blocked_tasks * 10

        recommendations.append(
            f"Escalate {blocked_tasks} blocked task(s)."
        )

        action_items.append({
            "area": "Delivery",
            "priority": "High",
            "action": f"Escalate blockers affecting {blocked_tasks} task(s).",
            "mode": "Governance Mode"
        })

    if open_risks > 0:
        urgency_score += open_risks * 5

        recommendations.append(
            f"Review {open_risks} open risk(s)."
        )

        action_items.append({
            "area": "Risk",
            "priority": "Medium",
            "action": f"Review mitigation ownership for {open_risks} open risk(s).",
            "mode": "Governance Mode"
        })

    if open_issues > 0:
        urgency_score += open_issues * 5

        recommendations.append(
            f"Review {open_issues} open issue(s)."
        )

        action_items.append({
            "area": "Issue",
            "priority": "Medium",
            "action": f"Confirm resolution plans for {open_issues} open issue(s).",
            "mode": "Governance Mode"
        })

    if pending_changes > 0:
        urgency_score += pending_changes * 3

        recommendations.append(
            f"Review {pending_changes} pending change request(s)."
        )

        action_items.append({
            "area": "Change",
            "priority": "Medium",
            "action": f"Check decision status for {pending_changes} pending change request(s).",
            "mode": "Governance Mode"
        })

    if budget_usage > 90:
        urgency_score += 15

        recommendations.append(
            f"Budget usage is high at {budget_usage}%. Review financial controls."
        )

        action_items.append({
            "area": "Finance",
            "priority": "High",
            "action": f"Review budget exposure because actual usage is {budget_usage}%.",
            "mode": "Finance Mode"
        })

    if forecast_usage > 90:
        urgency_score += 15

        recommendations.append(
            f"Forecast usage is high at {forecast_usage}%. Review forecast assumptions."
        )

        action_items.append({
            "area": "Finance",
            "priority": "High",
            "action": f"Review forecast exposure because forecast usage is {forecast_usage}%.",
            "mode": "Finance Mode"
        })

    urgency_score = min(urgency_score, 100)

    if not recommendations:
        recommendations.append(
            "Portfolio currently appears healthy based on current delivery, risk, issue and budget indicators."
        )

        action_items.append({
            "area": "Portfolio",
            "priority": "Low",
            "action": "Continue routine governance monitoring.",
            "mode": "Executive Mode"
        })

    if urgency_score >= 70:
        copilot_status = "Immediate Attention"
    elif urgency_score >= 35:
        copilot_status = "Monitor Closely"
    else:
        copilot_status = "Stable"

    confidence_score = 70

    if total_projects > 0:
        confidence_score += 5

    if total_tasks > 0:
        confidence_score += 10

    if total_budget > 0:
        confidence_score += 5

    confidence_score = min(confidence_score, 95)

    executive_summary = (
        f"AI PM Copilot reviewed {total_projects} project(s), {total_tasks} task(s), "
        f"{open_risks} risk(s), {open_issues} issue(s), and {pending_changes} change(s). "
        f"Current copilot status is {copilot_status} with urgency score {urgency_score}%."
    )

    model_notes = [
        "Copilot urgency score uses overdue tasks, blockers, risks, issues, changes and budget pressure.",
        "Recommendations are converted into action items with priority and operating mode.",
        "Copilot is an action centre, while AI Assistant remains the question-and-answer interface.",
        "Confidence score is based on project, task and budget data availability.",
        "Current model is rule-based and will later support one-click actions and conversational execution."
    ]

    pipe_cleaning_notes = [
        "Add conversational copilot.",
        "Add action tracking.",
        "Add decision support.",
        "Add executive mode.",
        "Add governance mode.",
        "Add resource mode.",
        "Add portfolio mode.",
        "Add one-click actions."
    ]

    return render_template(
        "ai_pm_copilot.html",
        total_projects=total_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        completion_rate=completion_rate,
        overdue_tasks=overdue_tasks,
        open_risks=open_risks,
        open_issues=open_issues,
        blocked_tasks=blocked_tasks,
        pending_changes=pending_changes,
        total_budget=total_budget,
        total_actual=total_actual,
        total_forecast=total_forecast,
        budget_usage=budget_usage,
        forecast_usage=forecast_usage,
        recommendations=recommendations,
        action_items=action_items,
        urgency_score=urgency_score,
        copilot_status=copilot_status,
        confidence_score=confidence_score,
        executive_summary=executive_summary,
        model_notes=model_notes,
        pipe_cleaning_notes=pipe_cleaning_notes
    )



@app.route("/audit-logs")
def audit_logs():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Audit Logs", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM audit_logs
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    logs = cursor.fetchall()

    conn.close()

    return render_template(
        "audit_logs.html",
        logs=logs
    )


def add_audit_log(
    user_id,
    action,
    module,
    details
):

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO audit_logs
        (
            user_id,
            action,
            module,
            details,
            created_at
        )
        VALUES (%s,%s,%s,%s,%s)
    """, (
        user_id,
        action,
        module,
        details,
        str(datetime.now())
    ))

    conn.commit()
    conn.close()


@app.route("/user-roles")
def user_roles():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (user_roles.user_id, user_roles.role)
            user_roles.*,
            users.username,
            users.email
        FROM user_roles
        LEFT JOIN users
        ON user_roles.user_id = users.id
        ORDER BY user_roles.user_id, user_roles.role, user_roles.id DESC
    """)

    roles = cursor.fetchall()

    total_roles = len(roles)

    admin_count = len([
        role for role in roles
        if role["role"] == "Admin"
    ])

    project_manager_count = len([
        role for role in roles
        if role["role"] == "Project Manager"
    ])

    coordinator_count = len([
        role for role in roles
        if role["role"] == "Project Coordinator"
    ])

    viewer_count = len([
        role for role in roles
        if role["role"] == "Viewer"
    ])

    role_summary = {}

    for role in roles:

        role_name = role["role"] or "Unknown"

        if role_name not in role_summary:
            role_summary[role_name] = 0

        role_summary[role_name] += 1

    role_health_score = 100

    if total_roles == 0:
        role_health_score -= 40

    if admin_count == 0:
        role_health_score -= 25

    if viewer_count == 0:
        role_health_score -= 10

    role_health_score = max(0, role_health_score)

    conn.close()

    return render_template(
        "user_roles.html",
        roles=roles,
        total_roles=total_roles,
        admin_count=admin_count,
        project_manager_count=project_manager_count,
        coordinator_count=coordinator_count,
        viewer_count=viewer_count,
        role_summary=role_summary,
        role_health_score=role_health_score
    )


@app.route("/add-user-role", methods=["GET", "POST"])
def add_user_role():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM users
        ORDER BY username ASC
    """)

    users = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            SELECT id
            FROM user_roles
            WHERE user_id = %s
            AND role = %s
            LIMIT 1
        """, (
            request.form.get("user_id"),
            request.form.get("role")
        ))

        existing_role = cursor.fetchone()

        if existing_role:
            conn.close()
            return redirect("/user-roles")

        cursor.execute("""
            INSERT INTO user_roles
            (
                user_id,
                role,
                role_description,
                parent_role,
                role_owner,
                role_template,
                custom_role,
                created_at,
                updated_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form.get("user_id"),
            request.form.get("role"),
            request.form.get("role_description"),
            request.form.get("parent_role"),
            request.form.get("role_owner"),
            request.form.get("role_template"),
            True if request.form.get("custom_role") == "Yes" else False,
            str(datetime.now()),
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

        return redirect("/user-roles")

    conn.close()

    return render_template(
        "add_user_role.html",
        users=users
    )

@app.route("/edit-user-role/<int:id>", methods=["GET", "POST"])
def edit_user_role(id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM user_roles
        WHERE id = %s
    """, (
        id,
    ))

    role = cursor.fetchone()

    if not role:
        conn.close()
        return redirect("/user-roles")

    cursor.execute("""
        SELECT *
        FROM users
        ORDER BY username ASC
    """)

    users = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            UPDATE user_roles
            SET
                user_id = %s,
                role = %s,
                role_description = %s,
                parent_role = %s,
                role_owner = %s,
                role_template = %s,
                custom_role = %s,
                updated_at = %s
            WHERE id = %s
        """, (
            request.form.get("user_id"),
            request.form.get("role"),
            request.form.get("role_description"),
            request.form.get("parent_role"),
            request.form.get("role_owner"),
            request.form.get("role_template"),
            True if request.form.get("custom_role") == "Yes" else False,
            str(datetime.now()),
            id
        ))

        conn.commit()
        conn.close()

        return redirect("/user-roles")

    conn.close()

    return render_template(
        "edit_user_role.html",
        role=role,
        users=users
    )


@app.route("/delete-user-role/<int:id>")
def delete_user_role(id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM user_roles
        WHERE id = %s
    """, (
        id,
    ))

    conn.commit()
    conn.close()

    return redirect("/user-roles")


@app.route("/permissions")
def permissions():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (role, module)
            *
        FROM permissions
        ORDER BY role, module, id DESC
    """)

    permissions = cursor.fetchall()

    total_permissions = len(permissions)

    admin_permissions = len([
        permission for permission in permissions
        if permission["role"] == "Admin"
    ])

    manager_permissions = len([
        permission for permission in permissions
        if permission["role"] in ["Manager", "Project Manager"]
    ])

    viewer_permissions = len([
        permission for permission in permissions
        if permission["role"] == "Viewer"
    ])

    high_risk_permissions = len([
        permission for permission in permissions
        if permission["risk_level"] == "High"
    ])

    module_summary = {}

    role_summary = {}

    for permission in permissions:

        module = permission["module"] or "Unknown"
        role = permission["role"] or "Unknown"

        if module not in module_summary:
            module_summary[module] = 0

        if role not in role_summary:
            role_summary[role] = 0

        module_summary[module] += 1
        role_summary[role] += 1

    permission_health_score = 100

    if total_permissions == 0:
        permission_health_score -= 40

    if admin_permissions == 0:
        permission_health_score -= 20

    if high_risk_permissions > 0:
        permission_health_score -= 10

    permission_health_score = max(0, permission_health_score)

    conn.close()

    return render_template(
        "permissions.html",
        permissions=permissions,
        total_permissions=total_permissions,
        admin_permissions=admin_permissions,
        manager_permissions=manager_permissions,
        viewer_permissions=viewer_permissions,
        high_risk_permissions=high_risk_permissions,
        module_summary=module_summary,
        role_summary=role_summary,
        permission_health_score=permission_health_score
    )


@app.route("/add-permission", methods=["GET", "POST"])
def add_permission():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()

        cursor = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        cursor.execute("""
            SELECT id
            FROM permissions
            WHERE role = %s
            AND module = %s
            LIMIT 1
        """, (
            request.form.get("role"),
            request.form.get("module")
        ))

        existing_permission = cursor.fetchone()

        if existing_permission:
            conn.close()
            return redirect("/permissions")

        cursor.execute("""
            INSERT INTO permissions
            (
                role,
                module,
                can_view,
                can_create,
                can_edit,
                can_delete,
                permission_category,
                permission_template,
                inherits_from,
                risk_level,
                permission_notes,
                last_reviewed_date,
                created_at,
                updated_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form.get("role"),
            request.form.get("module"),
            request.form.get("can_view") == "on",
            request.form.get("can_create") == "on",
            request.form.get("can_edit") == "on",
            request.form.get("can_delete") == "on",
            request.form.get("permission_category"),
            request.form.get("permission_template"),
            request.form.get("inherits_from"),
            request.form.get("risk_level"),
            request.form.get("permission_notes"),
            request.form.get("last_reviewed_date"),
            str(datetime.now()),
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

        return redirect("/permissions")

    return render_template(
        "add_permission.html"
    )


@app.route("/edit-permission/<int:id>", methods=["GET", "POST"])
def edit_permission(id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM permissions
        WHERE id = %s
    """, (
        id,
    ))

    permission = cursor.fetchone()

    if not permission:
        conn.close()
        return redirect("/permissions")

    if request.method == "POST":

        cursor.execute("""
            UPDATE permissions
            SET
                role = %s,
                module = %s,
                can_view = %s,
                can_create = %s,
                can_edit = %s,
                can_delete = %s,
                permission_category = %s,
                permission_template = %s,
                inherits_from = %s,
                risk_level = %s,
                permission_notes = %s,
                last_reviewed_date = %s,
                updated_at = %s
            WHERE id = %s
        """, (
            request.form.get("role"),
            request.form.get("module"),
            request.form.get("can_view") == "on",
            request.form.get("can_create") == "on",
            request.form.get("can_edit") == "on",
            request.form.get("can_delete") == "on",
            request.form.get("permission_category"),
            request.form.get("permission_template"),
            request.form.get("inherits_from"),
            request.form.get("risk_level"),
            request.form.get("permission_notes"),
            request.form.get("last_reviewed_date"),
            str(datetime.now()),
            id
        ))

        conn.commit()
        conn.close()

        return redirect("/permissions")

    conn.close()

    return render_template(
        "edit_permission.html",
        permission=permission
    )


@app.route("/delete-permission/<int:id>")
def delete_permission(id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM permissions
        WHERE id = %s
    """, (
        id,
    ))

    conn.commit()
    conn.close()

    return redirect("/permissions")


@app.route("/admin-dashboard")
def admin_dashboard():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT COUNT(DISTINCT id) AS total_users FROM users")
    total_users = cursor.fetchone()["total_users"]

    cursor.execute("SELECT COUNT(DISTINCT id) AS total_projects FROM projects")
    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("SELECT COUNT(DISTINCT id) AS total_tasks FROM tasks")
    total_tasks = cursor.fetchone()["total_tasks"]

    cursor.execute("SELECT COUNT(DISTINCT id) AS total_risks FROM risks")
    total_risks = cursor.fetchone()["total_risks"]

    cursor.execute("SELECT COUNT(DISTINCT id) AS total_issues FROM issues")
    total_issues = cursor.fetchone()["total_issues"]

    cursor.execute("SELECT COUNT(DISTINCT role) AS total_roles FROM user_roles")
    total_roles = cursor.fetchone()["total_roles"]

    cursor.execute("""
        SELECT COUNT(DISTINCT role || '-' || module) AS total_permissions
        FROM permissions
    """)
    total_permissions = cursor.fetchone()["total_permissions"]

    cursor.execute("SELECT COUNT(DISTINCT id) AS total_activities FROM activities")
    total_activities = cursor.fetchone()["total_activities"]

    cursor.execute("""
        SELECT COUNT(DISTINCT id) AS active_users
        FROM users
        WHERE id IN (
            SELECT DISTINCT user_id
            FROM activities
        )
    """)
    active_users = cursor.fetchone()["active_users"]

    cursor.execute("""
        SELECT COUNT(DISTINCT id) AS organisations_count
        FROM organisations
    """)
    organisations_count = cursor.fetchone()["organisations_count"]

    cursor.execute("""
        SELECT COUNT(DISTINCT id) AS workspaces_count
        FROM workspaces
    """)
    workspaces_count = cursor.fetchone()["workspaces_count"]

    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) AS last_30_day_logins
        FROM activities
        WHERE created_at >= %s
    """, (
        str(date.today() - timedelta(days=30)),
    ))
    last_30_day_logins = cursor.fetchone()["last_30_day_logins"]

    admin_health_score = 100

    if total_users == 0:
        admin_health_score -= 30

    if total_roles == 0:
        admin_health_score -= 20

    if total_permissions == 0:
        admin_health_score -= 20

    if total_activities == 0:
        admin_health_score -= 15

    admin_health_score = max(0, admin_health_score)

    if admin_health_score >= 80:
        admin_health_status = "Healthy"
    elif admin_health_score >= 60:
        admin_health_status = "Monitor"
    else:
        admin_health_status = "Needs Attention"

    cursor.execute("""
        SELECT *
        FROM audit_logs
        ORDER BY id DESC
        LIMIT 10
    """)
    recent_logs = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM activities
        ORDER BY id DESC
        LIMIT 10
    """)
    recent_activities = cursor.fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_projects=total_projects,
        total_tasks=total_tasks,
        total_risks=total_risks,
        total_issues=total_issues,
        total_roles=total_roles,
        total_permissions=total_permissions,
        total_activities=total_activities,
        active_users=active_users,
        organisations_count=organisations_count,
        workspaces_count=workspaces_count,
        last_30_day_logins=last_30_day_logins,
        admin_health_score=admin_health_score,
        admin_health_status=admin_health_status,
        recent_logs=recent_logs,
        recent_activities=recent_activities
    )
@app.route("/admin-reset-password/<int:user_id>")
def admin_reset_password(user_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    reset_token = str(uuid.uuid4())

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        UPDATE users
        SET
            reset_token = %s,
            reset_token_created_at = %s
        WHERE id = %s
        RETURNING id, username, email, reset_token
    """, (
        reset_token,
        str(datetime.now()),
        user_id
    ))

    updated_user = cursor.fetchone()

    conn.commit()
    conn.close()

    if not updated_user:
        return "User not found"

    create_activity(
        f"Password reset token generated for {updated_user['username']}",
        user_id=session["user_id"],
        activity_type="Security",
        module="Admin",
        severity="Medium"
    )

    return f"""
    <h2>Password Reset Token Generated</h2>

    <p><strong>User:</strong> {updated_user['username']}</p>

    <p><strong>Email:</strong> {updated_user['email'] or 'No email recorded'}</p>

    <p><strong>Token:</strong> {updated_user['reset_token']}</p>

    <p>
        <a href="/reset-password/{updated_user['reset_token']}">
            Open Reset Password Page
        </a>
    </p>

    <p>
        <a href="/user-management">
            Back to User Management
        </a>
    </p>
    """


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM users
        WHERE reset_token = %s
    """, (
        token,
    ))

    user = cursor.fetchone()

    if not user:
        conn.close()
        return "Invalid reset token"

    token_created_at = user.get("reset_token_created_at")

    if token_created_at:

        try:
            token_time = datetime.fromisoformat(str(token_created_at))
            expiry_time = token_time + timedelta(hours=24)

            if datetime.now() > expiry_time:
                cursor.execute("""
                    UPDATE users
                    SET
                        reset_token = NULL,
                        reset_token_created_at = NULL
                    WHERE id = %s
                """, (
                    user["id"],
                ))

                conn.commit()
                conn.close()

                return "Reset token has expired"

        except Exception:
            pass

    if request.method == "POST":

        new_password = generate_password_hash(
            request.form["password"]
        )

        cursor.execute("""
            UPDATE users
            SET
                password = %s,
                reset_token = NULL,
                reset_token_created_at = NULL,
                password_reset_date = %s
            WHERE id = %s
        """, (
            new_password,
            str(date.today()),
            user["id"]
        ))

        conn.commit()
        conn.close()

        return redirect("/login")

    conn.close()

    return render_template(
        "reset_password.html",
        user=user
    )


@app.route("/email-notifications")
def email_notifications():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (recipient_email, subject, message)
            *
        FROM email_notifications
        WHERE user_id = %s
        ORDER BY recipient_email, subject, message, id DESC
    """, (
        session["user_id"],
    ))

    notifications = cursor.fetchall()

    total_notifications = len(notifications)

    draft_count = len([
        item for item in notifications
        if item["status"] == "Draft"
    ])

    queued_count = len([
        item for item in notifications
        if item["status"] == "Queued"
    ])

    sent_count = len([
        item for item in notifications
        if item["status"] == "Sent"
    ])

    failed_count = len([
        item for item in notifications
        if item["status"] == "Failed"
    ])

    conn.close()

    return render_template(
        "email_notifications.html",
        notifications=notifications,
        total_notifications=total_notifications,
        draft_count=draft_count,
        queued_count=queued_count,
        sent_count=sent_count,
        failed_count=failed_count
    )


@app.route("/add-email-notification", methods=["GET", "POST"])
def add_email_notification():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()

        cursor = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        cursor.execute("""
            SELECT id
            FROM email_notifications
            WHERE user_id = %s
            AND recipient_email = %s
            AND subject = %s
            AND status IN ('Draft', 'Queued')
            LIMIT 1
        """, (
            session["user_id"],
            request.form.get("recipient_email"),
            request.form.get("subject")
        ))

        existing_email = cursor.fetchone()

        if existing_email:
            conn.close()
            return redirect("/email-notifications")

        cursor.execute("""
            INSERT INTO email_notifications
            (
                user_id,
                recipient_email,
                subject,
                message,
                status,
                email_template,
                notification_type,
                scheduled_date,
                priority,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("recipient_email"),
            request.form.get("subject"),
            request.form.get("message"),
            request.form.get("status"),
            request.form.get("email_template"),
            request.form.get("notification_type"),
            request.form.get("scheduled_date"),
            request.form.get("priority"),
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

        return redirect("/email-notifications")

    return render_template(
        "add_email_notification.html"
    )



@app.route("/user-management")
def user_management():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (users.id)
            users.id,
            users.username,
            users.email,
            users.avatar_initials,
            users.status,
            users.organisation,
            users.last_login,
            users.password_reset_date,
            users.login_count,
            users.failed_login_count,
            users.mfa_enabled,
            users.created_at,
            user_roles.role
        FROM users
        LEFT JOIN user_roles
        ON users.id = user_roles.user_id
        ORDER BY users.id DESC, user_roles.id DESC
    """)

    users = cursor.fetchall()

    total_users = len(users)

    active_users = len([
        user for user in users
        if user["status"] == "Active"
    ])

    inactive_users = len([
        user for user in users
        if user["status"] == "Inactive"
    ])

    admin_users = len([
        user for user in users
        if user["role"] == "Admin"
    ])

    mfa_enabled_count = len([
        user for user in users
        if user["mfa_enabled"] == "Yes"
    ])

    conn.close()

    return render_template(
        "user_management.html",
        users=users,
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        admin_users=admin_users,
        mfa_enabled_count=mfa_enabled_count
    )

@app.route("/edit-user/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM users
        WHERE id = %s
    """, (user_id,))

    user = cursor.fetchone()

    if not user:
        conn.close()
        return redirect("/user-management")

    if request.method == "POST":

        cursor.execute("""
            UPDATE users
            SET
                username = %s,
                email = %s,
                avatar_initials = %s,
                status = %s,
                organisation = %s,
                mfa_enabled = %s,
                password_reset_date = %s
            WHERE id = %s
        """, (
            request.form.get("username"),
            request.form.get("email"),
            request.form.get("avatar_initials"),
            request.form.get("status"),
            request.form.get("organisation"),
            request.form.get("mfa_enabled"),
            request.form.get("password_reset_date"),
            user_id
        ))

        conn.commit()
        conn.close()

        return redirect("/user-management")

    conn.close()

    return render_template(
        "edit_user.html",
        user=user
    )

@app.route("/delete-user/<int:user_id>")
def delete_user(user_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM users
        WHERE id = %s
    """, (
        user_id,
    ))

    conn.commit()
    conn.close()

    return redirect("/user-management")


@app.route("/user-invitations")
def user_invitations():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            user_invitations.*,
            organisations.organisation_name,
            workspaces.workspace_name
        FROM user_invitations
        LEFT JOIN organisations
        ON user_invitations.organisation_id = organisations.id
        LEFT JOIN workspaces
        ON user_invitations.workspace_id = workspaces.id
        ORDER BY user_invitations.id DESC
    """)

    invitations = cursor.fetchall()

    today = str(date.today())

    pending_count = 0
    accepted_count = 0
    expired_count = 0
    revoked_count = 0

    invitation_data = []

    for invitation in invitations:

        status = invitation["status"] or "Pending"

        if (
            invitation["expiry_date"]
            and invitation["expiry_date"] < today
            and status == "Pending"
        ):
            status = "Expired"

        if status == "Pending":
            pending_count += 1
        elif status == "Accepted":
            accepted_count += 1
        elif status == "Expired":
            expired_count += 1
        elif status == "Revoked":
            revoked_count += 1

        invitation_data.append({
            "invitation": invitation,
            "display_status": status
        })

    total_invitations = len(invitation_data)

    conn.close()

    return render_template(
        "user_invitations.html",
        invitation_data=invitation_data,
        total_invitations=total_invitations,
        pending_count=pending_count,
        accepted_count=accepted_count,
        expired_count=expired_count,
        revoked_count=revoked_count
    )


@app.route("/add-user-invitation", methods=["GET", "POST"])
def add_user_invitation():

    if "user_id" not in session:
        return redirect("/login")

    if not can_invite_user():

        return """
        <h2>User Limit Reached</h2>

        <p>
            You have reached the maximum number of users
            allowed by your subscription plan.
        </p>

        <p>
            Please upgrade your plan to invite more users.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM workspaces
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    workspaces = cursor.fetchall()

    if request.method == "POST":

        invited_email = request.form.get("invited_email", "").strip().lower()

        cursor.execute("""
            SELECT id
            FROM users
            WHERE LOWER(email) = %s
            LIMIT 1
        """, (
            invited_email,
        ))

        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return redirect("/user-invitations")

        cursor.execute("""
            SELECT id
            FROM user_invitations
            WHERE LOWER(invited_email) = %s
            AND status = 'Pending'
            LIMIT 1
        """, (
            invited_email,
        ))

        existing_invitation = cursor.fetchone()

        if existing_invitation:
            conn.close()
            return redirect("/user-invitations")

        invitation_token = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO user_invitations
            (
                organisation_id,
                workspace_id,
                invited_email,
                role,
                status,
                invitation_token,
                invited_by,
                expiry_date,
                resend_count,
                last_reminder_sent,
                invitation_notes,
                created_at
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form.get("organisation_id"),
            request.form.get("workspace_id"),
            invited_email,
            request.form.get("role"),
            request.form.get("status") or "Pending",
            invitation_token,
            session["user_id"],
            request.form.get("expiry_date"),
            0,
            request.form.get("last_reminder_sent"),
            request.form.get("invitation_notes"),
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

        return redirect("/user-invitations")

    conn.close()

    return render_template(
        "add_user_invitation.html",
        organisations=organisations,
        workspaces=workspaces
    )

@app.route("/edit-user-invitation/<int:invitation_id>", methods=["GET", "POST"])
def edit_user_invitation(invitation_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM user_invitations
        WHERE id = %s
    """, (
        invitation_id,
    ))

    invitation = cursor.fetchone()

    if not invitation:
        conn.close()
        return redirect("/user-invitations")

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM workspaces
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    workspaces = cursor.fetchall()

    if request.method == "POST":

        status = request.form.get("status")

        accepted_at = invitation["accepted_at"]
        revoked_at = invitation["revoked_at"]

        if status == "Accepted" and not accepted_at:
            accepted_at = str(datetime.now())

        if status == "Revoked" and not revoked_at:
            revoked_at = str(datetime.now())

        cursor.execute("""
            UPDATE user_invitations
            SET
                organisation_id = %s,
                workspace_id = %s,
                invited_email = %s,
                role = %s,
                status = %s,
                expiry_date = %s,
                last_reminder_sent = %s,
                invitation_notes = %s,
                accepted_at = %s,
                revoked_at = %s
            WHERE id = %s
        """, (
            request.form.get("organisation_id"),
            request.form.get("workspace_id"),
            request.form.get("invited_email"),
            request.form.get("role"),
            status,
            request.form.get("expiry_date"),
            request.form.get("last_reminder_sent"),
            request.form.get("invitation_notes"),
            accepted_at,
            revoked_at,
            invitation_id
        ))

        conn.commit()
        conn.close()

        return redirect("/user-invitations")

    conn.close()

    return render_template(
        "edit_user_invitation.html",
        invitation=invitation,
        organisations=organisations,
        workspaces=workspaces
    )


@app.route("/revoke-user-invitation/<int:invitation_id>")
def revoke_user_invitation(invitation_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE user_invitations
        SET
            status = 'Revoked',
            revoked_at = %s
        WHERE id = %s
    """, (
        str(datetime.now()),
        invitation_id
    ))

    conn.commit()
    conn.close()

    return redirect("/user-invitations")


@app.route("/resend-user-invitation/<int:invitation_id>")
def resend_user_invitation(invitation_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE user_invitations
        SET
            resend_count = COALESCE(resend_count, 0) + 1,
            last_reminder_sent = %s
        WHERE id = %s
    """, (
        str(datetime.now()),
        invitation_id
    ))

    conn.commit()
    conn.close()

    return redirect("/user-invitations")




@app.route("/alerts")
def alerts():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    today = str(date.today())
    user_id = session["user_id"]

    cursor.execute("""
        SELECT
            tasks.*,
            projects.name AS project_name
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.due_date < %s
        AND tasks.status != 'Completed'
        ORDER BY tasks.due_date ASC
    """, (
        user_id,
        today
    ))

    overdue_tasks = cursor.fetchall()

    for task in overdue_tasks:
        task["owner"] = task["assigned_to"] or "Unassigned"
        task["severity"] = "Critical"
        task["severity_class"] = "red-card"

    cursor.execute("""
        SELECT
            risks.*,
            projects.name AS project_name
        FROM risks
        LEFT JOIN projects
        ON risks.project_id = projects.id
        WHERE risks.user_id = %s
        AND risks.severity_score >= 6
        AND risks.status != 'Closed'
        ORDER BY risks.severity_score DESC
    """, (
        user_id,
    ))

    high_risks = cursor.fetchall()

    for risk in high_risks:

        risk["owner"] = risk.get("owner") or "Project Manager"

        if risk["severity_score"] >= 8:
            risk["severity"] = "Critical"
            risk["severity_class"] = "red-card"
        elif risk["severity_score"] >= 6:
            risk["severity"] = "High"
            risk["severity_class"] = "amber-card"
        elif risk["severity_score"] >= 4:
            risk["severity"] = "Medium"
            risk["severity_class"] = "blue-card"
        else:
            risk["severity"] = "Low"
            risk["severity_class"] = "green-card"

    cursor.execute("""
        SELECT
            approvals.*,
            projects.name AS project_name
        FROM approvals
        LEFT JOIN projects
        ON approvals.project_id = projects.id
        WHERE approvals.user_id = %s
        AND approvals.status = 'Pending Approval'
        ORDER BY approvals.submitted_date ASC
    """, (
        user_id,
    ))

    pending_approvals = cursor.fetchall()

    for approval in pending_approvals:
        approval["owner"] = approval.get("submitted_by") or "Project Manager"
        approval["severity"] = "Medium"
        approval["severity_class"] = "blue-card"

    conn.close()

    return render_template(
        "alerts.html",
        overdue_tasks=overdue_tasks,
        high_risks=high_risks,
        pending_approvals=pending_approvals
    )



@app.route("/organisations")
def organisations():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    total_organisations = len(organisations)

    active_count = len([
        org for org in organisations
        if org["account_status"] == "Active"
    ])

    suspended_count = len([
        org for org in organisations
        if org["account_status"] == "Suspended"
    ])

    trial_count = len([
        org for org in organisations
        if org["subscription_status"] == "Trial"
    ])

    paid_count = len([
        org for org in organisations
        if org["subscription_status"] == "Paid"
    ])

    expired_count = len([
        org for org in organisations
        if org["subscription_status"] == "Expired"
    ])

    conn.close()

    return render_template(
        "organisations.html",
        organisations=organisations,
        total_organisations=total_organisations,
        active_count=active_count,
        suspended_count=suspended_count,
        trial_count=trial_count,
        paid_count=paid_count,
        expired_count=expired_count
    )


@app.route("/add-organisation", methods=["GET", "POST"])
def add_organisation():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()
        cursor = conn.cursor()

        trial_start_date = date.today()
        trial_end_date = date.today() + timedelta(days=14)

        subscription_status = request.form.get("subscription_status") or "Trial"

        cursor.execute("""
            INSERT INTO organisations
            (
                user_id,
                organisation_name,
                industry,
                plan,
                status,
                account_status,
                subscription_status,
                organisation_owner,
                contact_email,
                organisation_size,
                region,
                trial_start_date,
                trial_end_date,
                created_at,
                updated_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("organisation_name"),
            request.form.get("industry"),
            request.form.get("plan"),
            request.form.get("account_status"),
            request.form.get("account_status"),
            subscription_status,
            request.form.get("organisation_owner"),
            request.form.get("contact_email"),
            request.form.get("organisation_size"),
            request.form.get("region"),
            str(trial_start_date),
            str(trial_end_date),
            str(date.today()),
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

        return redirect("/organisations")

    return render_template("add_organisation.html")


@app.route("/edit-organisation/<int:organisation_id>", methods=["GET", "POST"])
def edit_organisation(organisation_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE id = %s
        AND user_id = %s
    """, (
        organisation_id,
        session["user_id"]
    ))

    organisation = cursor.fetchone()

    if not organisation:
        conn.close()
        return redirect("/organisations")

    if request.method == "POST":

        cursor.execute("""
            UPDATE organisations
            SET
                organisation_name = %s,
                industry = %s,
                plan = %s,
                status = %s,
                account_status = %s,
                subscription_status = %s,
                organisation_owner = %s,
                contact_email = %s,
                organisation_size = %s,
                region = %s,
                trial_start_date = %s,
                trial_end_date = %s,
                updated_at = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("organisation_name"),
            request.form.get("industry"),
            request.form.get("plan"),
            request.form.get("account_status"),
            request.form.get("account_status"),
            request.form.get("subscription_status"),
            request.form.get("organisation_owner"),
            request.form.get("contact_email"),
            request.form.get("organisation_size"),
            request.form.get("region"),
            request.form.get("trial_start_date"),
            request.form.get("trial_end_date"),
            str(datetime.now()),
            organisation_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        return redirect("/organisations")

    conn.close()

    return render_template(
        "edit_organisation.html",
        organisation=organisation
    )


@app.route("/delete-organisation/<int:organisation_id>")
def delete_organisation(organisation_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "delete"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM organisations
        WHERE id = %s
        AND user_id = %s
    """, (
        organisation_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/organisations")


@app.route("/organisation-switcher")
def organisation_switcher():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    current_organisation_id = session.get("organisation_id")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (organisation_name)
            *
        FROM organisations
        WHERE user_id = %s
        ORDER BY organisation_name, id DESC
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    total_organisations = len(organisations)

    current_organisation = None

    for organisation in organisations:
        if current_organisation_id and organisation["id"] == current_organisation_id:
            current_organisation = organisation

    conn.close()

    return render_template(
        "organisation_switcher.html",
        organisations=organisations,
        current_organisation_id=current_organisation_id,
        current_organisation=current_organisation,
        total_organisations=total_organisations
    )


@app.route("/switch-organisation/<int:organisation_id>")
def switch_organisation(organisation_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE id = %s
        AND user_id = %s
    """, (
        organisation_id,
        session["user_id"]
    ))

    organisation = cursor.fetchone()

    conn.close()

    if organisation:

        session["organisation_id"] = organisation_id
        session["organisation_name"] = organisation["organisation_name"]

        session.pop("workspace_id", None)
        session.pop("workspace_name", None)

        create_activity(
            f"Switched organisation to {organisation['organisation_name']}",
            user_id=session["user_id"],
            activity_type="Switch",
            module="Organisation",
            severity="Low"
        )

    return redirect("/organisation-switcher")

@app.route("/workspaces")
def workspaces():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (workspaces.workspace_name, workspaces.organisation_id)
            workspaces.*,
            organisations.organisation_name
        FROM workspaces
        LEFT JOIN organisations
        ON workspaces.organisation_id = organisations.id
        WHERE workspaces.user_id = %s
        ORDER BY workspaces.workspace_name, workspaces.organisation_id, workspaces.id DESC
    """, (
        session["user_id"],
    ))

    workspaces = cursor.fetchall()

    total_workspaces = len(workspaces)

    active_count = len([
        workspace for workspace in workspaces
        if workspace["status"] == "Active"
    ])

    project_workspace_count = len([
        workspace for workspace in workspaces
        if workspace["workspace_type"] == "Project"
    ])

    pmo_workspace_count = len([
        workspace for workspace in workspaces
        if workspace["workspace_type"] == "PMO"
    ])

    finance_workspace_count = len([
        workspace for workspace in workspaces
        if workspace["workspace_type"] == "Finance"
    ])

    conn.close()

    return render_template(
        "workspaces.html",
        workspaces=workspaces,
        total_workspaces=total_workspaces,
        active_count=active_count,
        project_workspace_count=project_workspace_count,
        pmo_workspace_count=pmo_workspace_count,
        finance_workspace_count=finance_workspace_count
    )


@app.route("/add-workspace", methods=["GET", "POST"])
def add_workspace():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if not can_create_workspace():

        return """
        <h2>Workspace Limit Reached</h2>

        <p>
            You have reached the maximum number of workspaces
            allowed by your subscription plan.
        </p>

        <p>
            Please upgrade your plan to create more workspaces.
        </p>

        <a href="/subscription-status">
            View Subscription
        </a>
        """

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY organisation_name
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            SELECT id
            FROM workspaces
            WHERE user_id = %s
            AND organisation_id = %s
            AND LOWER(TRIM(workspace_name)) = LOWER(TRIM(%s))
            LIMIT 1
        """, (
            session["user_id"],
            request.form.get("organisation_id"),
            request.form.get("workspace_name")
        ))

        existing_workspace = cursor.fetchone()

        if existing_workspace:
            conn.close()
            return redirect("/workspaces")

        cursor.execute("""
            INSERT INTO workspaces
            (
                user_id,
                organisation_id,
                workspace_name,
                workspace_type,
                owner,
                status,
                workspace_description,
                workspace_health_score,
                created_at,
                updated_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("organisation_id"),
            request.form.get("workspace_name"),
            request.form.get("workspace_type"),
            request.form.get("owner"),
            request.form.get("status"),
            request.form.get("workspace_description"),
            int(request.form.get("workspace_health_score") or 80),
            str(date.today()),
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

        return redirect("/workspaces")

    conn.close()

    return render_template(
        "add_workspace.html",
        organisations=organisations
    )


@app.route("/switch-workspace/<int:workspace_id>")
def switch_workspace(workspace_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM workspaces
        WHERE id = %s
        AND user_id = %s
    """, (
        workspace_id,
        session["user_id"]
    ))

    workspace = cursor.fetchone()

    conn.close()

    if workspace:

        session["workspace_id"] = workspace_id
        session["workspace_name"] = workspace["workspace_name"]
        session["organisation_id"] = workspace["organisation_id"]

        create_activity(
            f"Switched workspace to {workspace['workspace_name']}",
            user_id=session["user_id"],
            activity_type="Switch",
            module="Workspace",
            severity="Low"
        )

    return redirect("/workspace-switcher")


@app.route("/workspace-switcher")
def workspace_switcher():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    current_workspace_id = session.get("workspace_id")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (workspaces.workspace_name, workspaces.organisation_id)
            workspaces.*,
            organisations.organisation_name
        FROM workspaces
        LEFT JOIN organisations
        ON workspaces.organisation_id = organisations.id
        WHERE workspaces.user_id = %s
        ORDER BY workspaces.workspace_name, workspaces.organisation_id, workspaces.id DESC
    """, (
        session["user_id"],
    ))

    workspaces = cursor.fetchall()

    current_workspace = None

    for workspace in workspaces:
        if current_workspace_id and workspace["id"] == current_workspace_id:
            current_workspace = workspace

    conn.close()

    return render_template(
        "workspace_switcher.html",
        workspaces=workspaces,
        current_workspace_id=current_workspace_id,
        current_workspace=current_workspace,
        total_workspaces=len(workspaces)
    )


@app.route("/workspace-roles")
def workspace_roles():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (
            user_roles.user_id,
            user_roles.organisation_id,
            user_roles.workspace_id,
            user_roles.role
        )
            user_roles.*,
            users.username,
            users.email,
            organisations.organisation_name,
            workspaces.workspace_name
        FROM user_roles
        LEFT JOIN users
        ON user_roles.user_id = users.id
        LEFT JOIN organisations
        ON user_roles.organisation_id = organisations.id
        LEFT JOIN workspaces
        ON user_roles.workspace_id = workspaces.id
        WHERE user_roles.workspace_id IS NOT NULL
        ORDER BY
            user_roles.user_id,
            user_roles.organisation_id,
            user_roles.workspace_id,
            user_roles.role,
            user_roles.id DESC
    """)

    roles = cursor.fetchall()

    total_roles = len(roles)

    admin_count = len([
        role for role in roles
        if role["role"] == "Admin"
    ])

    manager_count = len([
        role for role in roles
        if role["role"] == "Manager"
    ])

    team_member_count = len([
        role for role in roles
        if role["role"] == "Team Member"
    ])

    viewer_count = len([
        role for role in roles
        if role["role"] == "Viewer"
    ])

    conn.close()

    return render_template(
        "workspace_roles.html",
        roles=roles,
        total_roles=total_roles,
        admin_count=admin_count,
        manager_count=manager_count,
        team_member_count=team_member_count,
        viewer_count=viewer_count
    )


@app.route("/add-workspace-role", methods=["GET", "POST"])
def add_workspace_role():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM users
        ORDER BY username
    """)

    users = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY organisation_name
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM workspaces
        WHERE user_id = %s
        ORDER BY workspace_name
    """, (
        session["user_id"],
    ))

    workspaces = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            SELECT id
            FROM user_roles
            WHERE user_id = %s
            AND role = %s
            AND organisation_id = %s
            AND workspace_id = %s
            LIMIT 1
        """, (
            request.form.get("user_id"),
            request.form.get("role"),
            request.form.get("organisation_id"),
            request.form.get("workspace_id")
        ))

        existing_role = cursor.fetchone()

        if existing_role:
            conn.close()
            return redirect("/workspace-roles")

        cursor.execute("""
            INSERT INTO user_roles
            (
                user_id,
                role,
                organisation_id,
                workspace_id,
                created_at,
                updated_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            request.form.get("user_id"),
            request.form.get("role"),
            request.form.get("organisation_id"),
            request.form.get("workspace_id"),
            str(datetime.now()),
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

        return redirect("/workspace-roles")

    conn.close()

    return render_template(
        "add_workspace_role.html",
        users=users,
        organisations=organisations,
        workspaces=workspaces
    )


@app.route("/edit-workspace-role/<int:role_id>", methods=["GET", "POST"])
def edit_workspace_role(role_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM user_roles
        WHERE id = %s
    """, (
        role_id,
    ))

    role = cursor.fetchone()

    if not role:
        conn.close()
        return redirect("/workspace-roles")

    cursor.execute("""
        SELECT *
        FROM users
        ORDER BY username
    """)

    users = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY organisation_name
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM workspaces
        WHERE user_id = %s
        ORDER BY workspace_name
    """, (
        session["user_id"],
    ))

    workspaces = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            SELECT id
            FROM user_roles
            WHERE user_id = %s
            AND role = %s
            AND organisation_id = %s
            AND workspace_id = %s
            AND id != %s
            LIMIT 1
        """, (
            request.form.get("user_id"),
            request.form.get("role"),
            request.form.get("organisation_id"),
            request.form.get("workspace_id"),
            role_id
        ))

        existing_role = cursor.fetchone()

        if existing_role:
            conn.close()
            return redirect("/workspace-roles")

        cursor.execute("""
            UPDATE user_roles
            SET
                user_id = %s,
                role = %s,
                organisation_id = %s,
                workspace_id = %s,
                updated_at = %s
            WHERE id = %s
        """, (
            request.form.get("user_id"),
            request.form.get("role"),
            request.form.get("organisation_id"),
            request.form.get("workspace_id"),
            str(datetime.now()),
            role_id
        ))

        conn.commit()
        conn.close()

        return redirect("/workspace-roles")

    conn.close()

    return render_template(
        "edit_workspace_role.html",
        role=role,
        users=users,
        organisations=organisations,
        workspaces=workspaces
    )


@app.route("/delete-workspace-role/<int:role_id>")
def delete_workspace_role(role_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "delete"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM user_roles
        WHERE id = %s
    """, (
        role_id,
    ))

    conn.commit()
    conn.close()

    return redirect("/workspace-roles")


@app.route("/subscription-plans")
def subscription_plans():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT DISTINCT ON (plan_name)
            *
        FROM subscription_plans
        WHERE user_id = %s
        ORDER BY plan_name, id DESC
    """, (session["user_id"],))

    plans = cursor.fetchall()

    total_plans = len(plans)
    active_plans = len([p for p in plans if p["status"] == "Active"])
    free_plans = len([p for p in plans if p["price"] == 0 or str(p["price"]) == "0"])

    conn.close()

    return render_template(
        "subscription_plans.html",
        plans=plans,
        total_plans=total_plans,
        active_plans=active_plans,
        free_plans=free_plans
    )


@app.route("/add-subscription-plan", methods=["GET", "POST"])
def add_subscription_plan():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT id
            FROM subscription_plans
            WHERE user_id = %s
            AND LOWER(plan_name) = LOWER(%s)
            LIMIT 1
        """, (
            session["user_id"],
            request.form.get("plan_name")
        ))

        existing_plan = cursor.fetchone()

        if existing_plan:
            conn.close()
            return redirect("/subscription-plans")

        cursor.execute("""
            INSERT INTO subscription_plans
            (
                user_id,
                plan_name,
                price,
                billing_cycle,
                max_projects,
                max_users,
                features,
                status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("plan_name"),
            request.form.get("price"),
            request.form.get("billing_cycle"),
            request.form.get("max_projects"),
            request.form.get("max_users"),
            request.form.get("features"),
            request.form.get("status"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/subscription-plans")

    return render_template("add_subscription_plan.html")


@app.route("/customer-subscriptions")
def customer_subscriptions():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT DISTINCT ON (customer_subscriptions.organisation_id)
            customer_subscriptions.*,
            organisations.organisation_name,
            organisations.subscription_status,
            organisations.plan AS organisation_plan,
            subscription_plans.plan_name
        FROM customer_subscriptions
        LEFT JOIN organisations
        ON customer_subscriptions.organisation_id = organisations.id
        LEFT JOIN subscription_plans
        ON customer_subscriptions.plan_id = subscription_plans.id
        WHERE customer_subscriptions.user_id = %s
        ORDER BY customer_subscriptions.organisation_id, customer_subscriptions.id DESC
    """, (
        session["user_id"],
    ))

    subscriptions = cursor.fetchall()

    total_subscriptions = len(subscriptions)
    active_subscriptions = len([s for s in subscriptions if s["status"] == "Active"])
    trial_subscriptions = len([s for s in subscriptions if s["status"] == "Trial"])
    expired_subscriptions = len([s for s in subscriptions if s["status"] == "Expired"])

    conn.close()

    return render_template(
        "customer_subscriptions.html",
        subscriptions=subscriptions,
        total_subscriptions=total_subscriptions,
        active_subscriptions=active_subscriptions,
        trial_subscriptions=trial_subscriptions,
        expired_subscriptions=expired_subscriptions
    )


@app.route("/add-customer-subscription", methods=["GET", "POST"])
def add_customer_subscription():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY organisation_name
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT ON (plan_name)
            *
        FROM subscription_plans
        WHERE user_id = %s
        ORDER BY plan_name, id DESC
    """, (
        session["user_id"],
    ))

    plans = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            SELECT id
            FROM customer_subscriptions
            WHERE user_id = %s
            AND organisation_id = %s
            LIMIT 1
        """, (
            session["user_id"],
            request.form.get("organisation_id")
        ))

        existing_subscription = cursor.fetchone()

        if existing_subscription:
            conn.close()
            return redirect("/customer-subscriptions")

        cursor.execute("""
            INSERT INTO customer_subscriptions
            (
                user_id,
                organisation_id,
                plan_id,
                start_date,
                end_date,
                status,
                payment_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("organisation_id"),
            request.form.get("plan_id"),
            request.form.get("start_date"),
            request.form.get("end_date"),
            request.form.get("status"),
            request.form.get("payment_status"),
            str(date.today())
        ))

        cursor.execute("""
            SELECT plan_name
            FROM subscription_plans
            WHERE id = %s
        """, (
            request.form.get("plan_id"),
        ))

        selected_plan = cursor.fetchone()

        if selected_plan:

            subscription_status = request.form.get("status")

            if subscription_status == "Active":
                organisation_subscription_status = "Paid"
            elif subscription_status == "Trial":
                organisation_subscription_status = "Trial"
            else:
                organisation_subscription_status = "Expired"

            cursor.execute("""
                UPDATE organisations
                SET
                    plan = %s,
                    subscription_status = %s
                WHERE id = %s
                AND user_id = %s
            """, (
                selected_plan["plan_name"],
                organisation_subscription_status,
                request.form.get("organisation_id"),
                session["user_id"]
            ))

        conn.commit()
        conn.close()

        return redirect("/customer-subscriptions")

    conn.close()

    return render_template(
        "add_customer_subscription.html",
        organisations=organisations,
        plans=plans
    )


@app.route("/subscription-status")
def subscription_status():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    today = date.today()

    trial_count = 0
    paid_count = 0
    expired_count = 0

    for organisation in organisations:

        days_remaining = 0

        if organisation["trial_end_date"]:

            try:
                trial_end = datetime.strptime(
                    str(organisation["trial_end_date"]),
                    "%Y-%m-%d"
                ).date()

                days_remaining = (trial_end - today).days

            except:
                days_remaining = 0

        organisation["days_remaining"] = days_remaining

        if organisation["subscription_status"] == "Trial":
            trial_count += 1
        elif organisation["subscription_status"] == "Paid":
            paid_count += 1
        elif organisation["subscription_status"] == "Expired":
            expired_count += 1

    conn.close()

    return render_template(
        "subscription_status.html",
        organisations=organisations,
        trial_count=trial_count,
        paid_count=paid_count,
        expired_count=expired_count
    )


@app.route("/upgrade-plan/<int:organisation_id>")
def upgrade_plan(organisation_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    return render_template(
        "upgrade_plan.html",
        organisation_id=organisation_id
    )


@app.route("/process-upgrade/<int:organisation_id>/<plan>")
def process_upgrade(organisation_id, plan):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "edit"):
        return "Access denied"

    allowed_plans = [
        "Free",
        "Basic",
        "Professional",
        "Enterprise"
    ]

    if plan not in allowed_plans:
        return "Invalid plan"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE organisations
        SET
            plan = %s,
            subscription_status = %s,
            account_status = %s,
            updated_at = %s
        WHERE id = %s
        AND user_id = %s
    """, (
        plan,
        "Paid",
        "Active",
        str(datetime.now()),
        organisation_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/subscription-status")


@app.route("/plan-limits")
def plan_limits():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    plan_data = []

    for organisation in organisations:

        limits = get_plan_limits(
            organisation["plan"]
        )

        max_projects = limits["max_projects"]
        max_users = limits["max_users"]
        max_workspaces = limits["max_workspaces"]

        plan_data.append({
            "organisation": organisation,
            "max_projects": "Unlimited" if max_projects == 9999 else max_projects,
            "max_users": "Unlimited" if max_users == 9999 else max_users,
            "max_workspaces": "Unlimited" if max_workspaces == 9999 else max_workspaces,
            "ai_enabled": limits["ai_enabled"]
        })

    conn.close()

    return render_template(
        "plan_limits.html",
        plan_data=plan_data
    )


@app.route("/billing-history")
def billing_history():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (billing_history.id)
            billing_history.*,
            organisations.organisation_name,
            invoices.invoice_number
        FROM billing_history
        LEFT JOIN organisations
        ON billing_history.organisation_id = organisations.id
        LEFT JOIN invoices
        ON billing_history.invoice_id = invoices.id
        WHERE billing_history.user_id = %s
        ORDER BY billing_history.id DESC
    """, (
        session["user_id"],
    ))

    billing_records = cursor.fetchall()

    total_records = len(billing_records)
    total_amount = 0
    paid_amount = 0
    failed_amount = 0
    refunded_amount = 0
    active_cycles = 0

    for record in billing_records:

        amount = float(record["amount"] or 0)
        refund_amount = float(record["refund_amount"] or 0)

        total_amount += amount
        refunded_amount += refund_amount

        if record["status"] == "Paid":
            paid_amount += amount

        if record["status"] == "Failed":
            failed_amount += amount

        if record["billing_cycle"]:
            active_cycles += 1

    conn.close()

    return render_template(
        "billing_history.html",
        billing_records=billing_records,
        total_records=total_records,
        total_amount=total_amount,
        paid_amount=paid_amount,
        failed_amount=failed_amount,
        refunded_amount=refunded_amount,
        active_cycles=active_cycles
    )


@app.route("/add-billing-history", methods=["GET", "POST"])
def add_billing_history():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY organisation_name
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM invoices
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    invoices = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO billing_history
            (
                user_id,
                organisation_id,
                invoice_id,
                plan,
                amount,
                status,
                reference_number,
                billing_date,
                payment_gateway,
                transaction_id,
                billing_cycle,
                renewal_date,
                refund_amount,
                chargeback_status,
                stripe_payment_reference,
                billing_notes,
                created_at
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("organisation_id"),
            request.form.get("invoice_id") or None,
            request.form.get("plan"),
            request.form.get("amount") or 0,
            request.form.get("status"),
            request.form.get("reference_number"),
            request.form.get("billing_date"),
            request.form.get("payment_gateway"),
            request.form.get("transaction_id"),
            request.form.get("billing_cycle"),
            request.form.get("renewal_date"),
            request.form.get("refund_amount") or 0,
            request.form.get("chargeback_status"),
            request.form.get("stripe_payment_reference"),
            request.form.get("billing_notes"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/billing-history")

    conn.close()

    return render_template(
        "add_billing_history.html",
        organisations=organisations,
        invoices=invoices
    )

@app.route("/invoices")
def invoices():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (invoices.id)
            invoices.*,
            organisations.organisation_name
        FROM invoices
        LEFT JOIN organisations
        ON invoices.organisation_id = organisations.id
        WHERE invoices.user_id = %s
        ORDER BY invoices.id DESC
    """, (
        session["user_id"],
    ))

    invoices_list = cursor.fetchall()

    total_invoices = len(invoices_list)
    total_amount = 0
    paid_amount = 0
    unpaid_amount = 0
    overdue_count = 0
    paid_count = 0
    pending_count = 0

    today = str(date.today())

    for invoice in invoices_list:

        amount = float(invoice["amount"] or 0)
        total_amount += amount

        if invoice["status"] == "Paid":
            paid_amount += amount
            paid_count += 1
        else:
            unpaid_amount += amount
            pending_count += 1

        if (
            invoice["due_date"]
            and invoice["due_date"] < today
            and invoice["status"] != "Paid"
        ):
            overdue_count += 1

    conn.close()

    return render_template(
        "invoices.html",
        invoices_list=invoices_list,
        total_invoices=total_invoices,
        total_amount=total_amount,
        paid_amount=paid_amount,
        unpaid_amount=unpaid_amount,
        overdue_count=overdue_count,
        paid_count=paid_count,
        pending_count=pending_count
    )


@app.route("/add-invoice", methods=["GET", "POST"])
def add_invoice():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY organisation_name
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            SELECT COUNT(*) AS invoice_count
            FROM invoices
            WHERE user_id = %s
        """, (
            session["user_id"],
        ))

        invoice_count = cursor.fetchone()["invoice_count"] + 1

        invoice_number = request.form.get("invoice_number")

        if not invoice_number:
            invoice_number = f"INV-{session['user_id']}-{str(invoice_count).zfill(3)}"

        amount = float(request.form.get("amount") or 0)
        vat_amount = float(request.form.get("vat_amount") or 0)

        cursor.execute("""
            INSERT INTO invoices
            (
                user_id,
                organisation_id,
                invoice_number,
                plan,
                amount,
                status,
                invoice_date,
                due_date,
                payment_date,
                vat_amount,
                currency,
                invoice_notes,
                payment_terms,
                stripe_invoice_reference,
                invoice_attachment_url,
                created_at
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            session["user_id"],
            request.form.get("organisation_id"),
            invoice_number,
            request.form.get("plan"),
            amount,
            request.form.get("status"),
            request.form.get("invoice_date"),
            request.form.get("due_date"),
            request.form.get("payment_date"),
            vat_amount,
            request.form.get("currency") or "GBP",
            request.form.get("invoice_notes"),
            request.form.get("payment_terms"),
            request.form.get("stripe_invoice_reference"),
            request.form.get("invoice_attachment_url"),
            str(date.today())
        ))

        invoice_id = cursor.fetchone()["id"]

        cursor.execute("""
            INSERT INTO invoice_history
            (
                invoice_id,
                user_id,
                action,
                previous_status,
                new_status,
                amount,
                notes,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            invoice_id,
            session["user_id"],
            "Invoice created",
            "",
            request.form.get("status"),
            amount,
            "Initial invoice created",
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/invoices")

    conn.close()

    return render_template(
        "add_invoice.html",
        organisations=organisations
    )


@app.route("/edit-invoice/<int:invoice_id>", methods=["GET", "POST"])
def edit_invoice(invoice_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM invoices
        WHERE id = %s
        AND user_id = %s
    """, (
        invoice_id,
        session["user_id"]
    ))

    invoice = cursor.fetchone()

    if not invoice:
        conn.close()
        return redirect("/invoices")

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY organisation_name
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    if request.method == "POST":

        previous_status = invoice["status"]
        amount = float(request.form.get("amount") or 0)
        vat_amount = float(request.form.get("vat_amount") or 0)

        cursor.execute("""
            UPDATE invoices
            SET
                organisation_id = %s,
                invoice_number = %s,
                plan = %s,
                amount = %s,
                status = %s,
                invoice_date = %s,
                due_date = %s,
                payment_date = %s,
                vat_amount = %s,
                currency = %s,
                invoice_notes = %s,
                payment_terms = %s,
                stripe_invoice_reference = %s,
                invoice_attachment_url = %s
            WHERE id = %s
            AND user_id = %s
        """, (
            request.form.get("organisation_id"),
            request.form.get("invoice_number"),
            request.form.get("plan"),
            amount,
            request.form.get("status"),
            request.form.get("invoice_date"),
            request.form.get("due_date"),
            request.form.get("payment_date"),
            vat_amount,
            request.form.get("currency") or "GBP",
            request.form.get("invoice_notes"),
            request.form.get("payment_terms"),
            request.form.get("stripe_invoice_reference"),
            request.form.get("invoice_attachment_url"),
            invoice_id,
            session["user_id"]
        ))

        cursor.execute("""
            INSERT INTO invoice_history
            (
                invoice_id,
                user_id,
                action,
                previous_status,
                new_status,
                amount,
                notes,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            invoice_id,
            session["user_id"],
            "Invoice updated",
            previous_status,
            request.form.get("status"),
            amount,
            request.form.get("invoice_notes"),
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/invoices")

    conn.close()

    return render_template(
        "edit_invoice.html",
        invoice=invoice,
        organisations=organisations
    )


@app.route("/delete-invoice/<int:invoice_id>")
def delete_invoice(invoice_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM invoices
        WHERE id = %s
        AND user_id = %s
    """, (
        invoice_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/invoices")


@app.route("/invoice-history/<int:invoice_id>")
def invoice_history(invoice_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM invoice_history
        WHERE invoice_id = %s
        ORDER BY id DESC
    """, (
        invoice_id,
    ))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "invoice_history.html",
        history=history
    )

@app.route("/notification-settings")
def notification_settings():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (notification_type, channel)
            *
        FROM notification_settings
        WHERE user_id = %s
        ORDER BY notification_type, channel, id DESC
    """, (
        session["user_id"],
    ))

    settings = cursor.fetchall()

    total_settings = len(settings)

    enabled_count = len([
        setting for setting in settings
        if str(setting["enabled"]) == "Yes"
    ])

    disabled_count = len([
        setting for setting in settings
        if str(setting["enabled"]) == "No"
    ])

    approval_alerts = len([
        setting for setting in settings
        if setting["notification_category"] == "Approval"
    ])

    billing_alerts = len([
        setting for setting in settings
        if setting["notification_category"] == "Billing"
    ])

    ai_alerts = len([
        setting for setting in settings
        if setting["notification_category"] == "AI"
    ])

    conn.close()

    return render_template(
        "notification_settings.html",
        settings=settings,
        total_settings=total_settings,
        enabled_count=enabled_count,
        disabled_count=disabled_count,
        approval_alerts=approval_alerts,
        billing_alerts=billing_alerts,
        ai_alerts=ai_alerts
    )


@app.route("/add-notification-setting", methods=["GET", "POST"])
def add_notification_setting():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()

        cursor = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        cursor.execute("""
            SELECT id
            FROM notification_settings
            WHERE user_id = %s
            AND notification_type = %s
            AND channel = %s
            LIMIT 1
        """, (
            session["user_id"],
            request.form.get("notification_type"),
            request.form.get("channel")
        ))

        existing_setting = cursor.fetchone()

        if existing_setting:
            conn.close()
            return redirect("/notification-settings")

        cursor.execute("""
            INSERT INTO notification_settings
            (
                user_id,
                notification_type,
                notification_category,
                channel,
                enabled,
                frequency,
                priority,
                description,
                created_at,
                updated_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form.get("notification_type"),
            request.form.get("notification_category"),
            request.form.get("channel"),
            request.form.get("enabled"),
            request.form.get("frequency"),
            request.form.get("priority"),
            request.form.get("description"),
            str(date.today()),
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

        return redirect("/notification-settings")

    return render_template("add_notification_setting.html")



@app.route("/usage-analytics")
def usage_analytics():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT COUNT(DISTINCT id) AS total_organisations
        FROM organisations
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_organisations = cursor.fetchone()["total_organisations"]

    cursor.execute("""
        SELECT COUNT(DISTINCT id) AS total_workspaces
        FROM workspaces
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_workspaces = cursor.fetchone()["total_workspaces"]

    cursor.execute("""
        SELECT COUNT(DISTINCT id) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("""
        SELECT COUNT(DISTINCT invited_email) AS invited_users
        FROM user_invitations
        WHERE invited_by = %s
    """, (
        session["user_id"],
    ))

    invited_users = cursor.fetchone()["invited_users"]

    cursor.execute("""
        SELECT COUNT(DISTINCT id) AS registered_users
        FROM users
    """)

    registered_users = cursor.fetchone()["registered_users"]

    cursor.execute("""
        SELECT COALESCE(SUM(usage_count), 0) AS total_ai_usage
        FROM ai_usage
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_ai_usage = cursor.fetchone()["total_ai_usage"]

    cursor.execute("""
        SELECT COUNT(DISTINCT organisation_id) AS organisations_using_ai
        FROM ai_usage
        WHERE user_id = %s
        AND organisation_id IS NOT NULL
    """, (
        session["user_id"],
    ))

    organisations_using_ai = cursor.fetchone()["organisations_using_ai"]

    cursor.execute("""
        SELECT COUNT(DISTINCT workspace_id) AS workspaces_using_ai
        FROM ai_usage
        WHERE user_id = %s
        AND workspace_id IS NOT NULL
    """, (
        session["user_id"],
    ))

    workspaces_using_ai = cursor.fetchone()["workspaces_using_ai"]

    if total_projects > 0:
        project_usage_ratio = round(
            (total_projects / max(total_organisations, 1)) ,
            2
        )
    else:
        project_usage_ratio = 0

    if total_workspaces > 0:
        workspace_usage_score = min(
            round((total_projects / total_workspaces) * 100),
            100
        )
    else:
        workspace_usage_score = 0

    usage_health_score = 100

    if total_organisations == 0:
        usage_health_score -= 25

    if total_workspaces == 0:
        usage_health_score -= 25

    if total_projects == 0:
        usage_health_score -= 25

    if total_ai_usage == 0:
        usage_health_score -= 10

    usage_health_score = max(0, usage_health_score)

    if usage_health_score >= 80:
        usage_health_status = "Healthy"
    elif usage_health_score >= 50:
        usage_health_status = "Monitor"
    else:
        usage_health_status = "Needs Attention"

    conn.close()

    return render_template(
        "usage_analytics.html",
        total_organisations=total_organisations,
        total_workspaces=total_workspaces,
        total_projects=total_projects,
        invited_users=invited_users,
        registered_users=registered_users,
        total_ai_usage=total_ai_usage,
        organisations_using_ai=organisations_using_ai,
        workspaces_using_ai=workspaces_using_ai,
        project_usage_ratio=project_usage_ratio,
        workspace_usage_score=workspace_usage_score,
        usage_health_score=usage_health_score,
        usage_health_status=usage_health_status
    )


@app.route("/billing-dashboard")
def billing_dashboard():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            customer_subscriptions.*,
            organisations.organisation_name,
            subscription_plans.plan_name,
            subscription_plans.price
        FROM customer_subscriptions
        LEFT JOIN organisations
        ON customer_subscriptions.organisation_id = organisations.id
        LEFT JOIN subscription_plans
        ON customer_subscriptions.plan_id = subscription_plans.id
        WHERE customer_subscriptions.user_id = %s
        ORDER BY customer_subscriptions.id DESC
    """, (
        session["user_id"],
    ))

    subscriptions = cursor.fetchall()

    total_revenue = 0

    for sub in subscriptions:
        if sub["payment_status"] == "Paid" and sub["price"]:
            total_revenue += sub["price"]

    active_subscriptions = [
        sub for sub in subscriptions
        if sub["status"] == "Active"
    ]

    unpaid_subscriptions = [
        sub for sub in subscriptions
        if sub["payment_status"] == "Unpaid"
    ]

    conn.close()

    return render_template(
        "billing_dashboard.html",
        subscriptions=subscriptions,
        total_revenue=total_revenue,
        active_subscriptions=active_subscriptions,
        unpaid_subscriptions=unpaid_subscriptions
    )


@app.route("/portfolio-board")
def portfolio_board():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (projects.id)
            projects.*
        FROM projects
        WHERE projects.user_id = %s
        AND COALESCE(projects.is_archived, FALSE) = FALSE
        AND COALESCE(projects.portfolio_archived, FALSE) = FALSE
        ORDER BY projects.id DESC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    portfolio_projects = []

    total_budget = 0
    total_actual = 0
    total_open_risks = 0
    total_open_issues = 0
    total_completion = 0
    total_health_score = 0

    green_projects = 0
    amber_projects = 0
    red_projects = 0

    for project in projects:

        project_id = project["id"]

        estimated_budget = float(project["estimated_budget"] or 0)
        actual_cost = float(project["actual_cost"] or 0)

        total_budget += estimated_budget
        total_actual += actual_cost

        cursor.execute("""
            SELECT COUNT(*) AS total_tasks
            FROM tasks
            WHERE project_id = %s
        """, (
            project_id,
        ))

        total_tasks = cursor.fetchone()["total_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS completed_tasks
            FROM tasks
            WHERE project_id = %s
            AND status = 'Completed'
        """, (
            project_id,
        ))

        completed_tasks = cursor.fetchone()["completed_tasks"]

        cursor.execute("""
            SELECT COUNT(*) AS open_risks
            FROM risks
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project_id,
        ))

        open_risks = cursor.fetchone()["open_risks"]

        cursor.execute("""
            SELECT COUNT(*) AS open_issues
            FROM issues
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project_id,
        ))

        open_issues = cursor.fetchone()["open_issues"]

        total_open_risks += open_risks
        total_open_issues += open_issues

        if total_tasks > 0:
            completion_rate = round((completed_tasks / total_tasks) * 100)
        else:
            completion_rate = 0

        total_completion += completion_rate

        budget_pressure = 0

        if estimated_budget > 0:
            budget_used_percent = round((actual_cost / estimated_budget) * 100)

            if budget_used_percent > 100:
                budget_pressure = 25
            elif budget_used_percent > 80:
                budget_pressure = 10
        else:
            budget_used_percent = 0

        health_score = (
            100
            - (open_risks * 10)
            - (open_issues * 5)
            - budget_pressure
        )

        health_score = max(0, min(100, health_score))

        total_health_score += health_score

        if health_score >= 80:
            health_status = "Green"
            green_projects += 1
        elif health_score >= 50:
            health_status = "Amber"
            amber_projects += 1
        else:
            health_status = "Red"
            red_projects += 1

        if health_score >= 80:
            trend_status = "Stable"
        elif open_risks > 2 or open_issues > 2:
            trend_status = "Needs Attention"
        elif budget_used_percent > 90:
            trend_status = "Financial Pressure"
        else:
            trend_status = "Monitor"

        portfolio_projects.append({
            "id": project["id"],
            "name": project["name"],
            "status": project["status"],
            "completion_rate": completion_rate,
            "open_risks": open_risks,
            "open_issues": open_issues,
            "budget": estimated_budget,
            "actual_cost": actual_cost,
            "budget_used_percent": budget_used_percent,
            "health_score": health_score,
            "health_status": health_status,
            "trend_status": trend_status,
            "portfolio_sponsor": project.get("portfolio_sponsor"),
            "portfolio_manager": project.get("portfolio_manager"),
            "strategic_objective": project.get("strategic_objective"),
            "expected_benefits": project.get("expected_benefits"),
            "benefits_status": project.get("benefits_status")
        })

    total_projects = len(projects)

    if total_projects > 0:
        average_completion = round(total_completion / total_projects)
        average_health_score = round(total_health_score / total_projects)
    else:
        average_completion = 0
        average_health_score = 0

    if average_health_score >= 80:
        portfolio_status = "Healthy"
    elif average_health_score >= 50:
        portfolio_status = "At Risk"
    else:
        portfolio_status = "Critical"

    budget_variance = total_budget - total_actual

    cursor.execute("""
        INSERT INTO portfolio_performance_history
        (
            user_id,
            total_projects,
            total_budget,
            total_actual,
            total_open_risks,
            total_open_issues,
            average_completion,
            average_health_score,
            portfolio_status
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        session["user_id"],
        total_projects,
        total_budget,
        total_actual,
        total_open_risks,
        total_open_issues,
        average_completion,
        average_health_score,
        portfolio_status
    ))

    conn.commit()

    cursor.execute("""
        SELECT *
        FROM portfolio_performance_history
        WHERE user_id = %s
        ORDER BY id DESC
        LIMIT 2
    """, (
        session["user_id"],
    ))

    history = cursor.fetchall()

    portfolio_trend = "Stable"

    if len(history) >= 2:

        latest = history[0]
        previous = history[1]

        if latest["average_health_score"] > previous["average_health_score"]:
            portfolio_trend = "Improving"
        elif latest["average_health_score"] < previous["average_health_score"]:
            portfolio_trend = "Declining"

    executive_alerts = []

    if red_projects > 0:
        executive_alerts.append(f"{red_projects} project(s) are in red health status.")

    if total_open_risks > 0:
        executive_alerts.append(f"{total_open_risks} open portfolio risk(s) require monitoring.")

    if total_open_issues > 0:
        executive_alerts.append(f"{total_open_issues} open issue(s) require resolution.")

    if total_actual > total_budget and total_budget > 0:
        executive_alerts.append("Portfolio actual cost is above budget.")

    if not executive_alerts:
        executive_alerts.append("Portfolio is currently stable with no major executive alerts.")

    conn.close()

    return render_template(
        "portfolio_board.html",
        portfolio_projects=portfolio_projects,
        total_projects=total_projects,
        total_budget=total_budget,
        total_actual=total_actual,
        budget_variance=budget_variance,
        total_open_risks=total_open_risks,
        total_open_issues=total_open_issues,
        average_completion=average_completion,
        average_health_score=average_health_score,
        portfolio_status=portfolio_status,
        portfolio_trend=portfolio_trend,
        green_projects=green_projects,
        amber_projects=amber_projects,
        red_projects=red_projects,
        executive_alerts=executive_alerts
    )


@app.route("/portfolio-roadmap")
def portfolio_roadmap():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT DISTINCT ON (projects.id)
            projects.*
        FROM projects
        WHERE projects.user_id = %s
        AND COALESCE(projects.is_archived, FALSE) = FALSE
        AND COALESCE(projects.portfolio_archived, FALSE) = FALSE
        ORDER BY
            projects.id,
            CASE
                WHEN projects.start_date IS NULL OR projects.start_date = ''
                THEN '9999-12-31'
                ELSE projects.start_date
            END ASC
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    roadmap_items = []

    on_track_count = 0
    at_risk_count = 0
    delayed_count = 0
    completed_count = 0

    total_progress = 0
    milestone_count = 0
    dependency_count = 0

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
            progress = 100 if project["status"] == "Completed" else 0

        total_progress += progress

        roadmap_status = project.get("roadmap_status") or "On Track"

        if project["status"] == "Completed":
            roadmap_status = "Completed"

        elif project["end_date"] and project["end_date"] < str(date.today()) and progress < 100:
            roadmap_status = "Delayed"

        elif progress < 40 and project["status"] == "In Progress":
            roadmap_status = "At Risk"

        if roadmap_status == "On Track":
            on_track_count += 1
        elif roadmap_status == "At Risk":
            at_risk_count += 1
        elif roadmap_status == "Delayed":
            delayed_count += 1
        elif roadmap_status == "Completed":
            completed_count += 1

        if project.get("roadmap_milestone"):
            milestone_count += 1

        if project.get("roadmap_dependency"):
            dependency_count += 1

        baseline_variance = "No baseline"

        if project.get("baseline_end_date") and project.get("end_date"):
            if project["end_date"] > project["baseline_end_date"]:
                baseline_variance = "Behind Baseline"
            elif project["end_date"] < project["baseline_end_date"]:
                baseline_variance = "Ahead of Baseline"
            else:
                baseline_variance = "On Baseline"

        roadmap_items.append({
            "project_id": project["id"],
            "project_name": project["name"],
            "programme": project.get("programme"),
            "portfolio": project.get("portfolio"),
            "status": project["status"],
            "start_date": project["start_date"],
            "end_date": project["end_date"],
            "baseline_start_date": project.get("baseline_start_date"),
            "baseline_end_date": project.get("baseline_end_date"),
            "progress": progress,
            "roadmap_status": roadmap_status,
            "roadmap_milestone": project.get("roadmap_milestone"),
            "roadmap_dependency": project.get("roadmap_dependency"),
            "strategic_initiative": project.get("strategic_initiative"),
            "baseline_variance": baseline_variance
        })

        cursor.execute("""
            INSERT INTO portfolio_roadmap_history
            (
                user_id,
                project_id,
                project_name,
                start_date,
                end_date,
                baseline_start_date,
                baseline_end_date,
                progress,
                roadmap_status
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            project["id"],
            project["name"],
            project["start_date"],
            project["end_date"],
            project.get("baseline_start_date"),
            project.get("baseline_end_date"),
            progress,
            roadmap_status
        ))

    total_projects = len(projects)

    if total_projects > 0:
        average_progress = round(total_progress / total_projects)
    else:
        average_progress = 0

    conn.commit()
    conn.close()

    return render_template(
        "portfolio_roadmap.html",
        roadmap_items=roadmap_items,
        total_projects=total_projects,
        average_progress=average_progress,
        on_track_count=on_track_count,
        at_risk_count=at_risk_count,
        delayed_count=delayed_count,
        completed_count=completed_count,
        milestone_count=milestone_count,
        dependency_count=dependency_count
    )

@app.route("/portfolio-kanban")
def portfolio_kanban():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Projects", "view"):
        return "Access denied"

    selected_portfolio = request.args.get("portfolio", "")
    selected_programme = request.args.get("programme", "")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    query = """
        SELECT DISTINCT ON (projects.id)
            projects.*
        FROM projects
        WHERE projects.user_id = %s
        AND COALESCE(projects.is_archived, FALSE) = FALSE
        AND COALESCE(projects.portfolio_archived, FALSE) = FALSE
    """

    params = [session["user_id"]]

    if selected_portfolio:
        query += " AND projects.portfolio = %s"
        params.append(selected_portfolio)

    if selected_programme:
        query += " AND projects.programme = %s"
        params.append(selected_programme)

    query += " ORDER BY projects.id DESC"

    cursor.execute(query, tuple(params))

    projects = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT portfolio
        FROM projects
        WHERE user_id = %s
        AND portfolio IS NOT NULL
        AND portfolio != ''
        ORDER BY portfolio
    """, (
        session["user_id"],
    ))

    portfolios = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT programme
        FROM projects
        WHERE user_id = %s
        AND programme IS NOT NULL
        AND programme != ''
        ORDER BY programme
    """, (
        session["user_id"],
    ))

    programmes = cursor.fetchall()

    grouped_projects = {
        "Planning": [],
        "In Progress": [],
        "At Risk": [],
        "On Hold": [],
        "Completed": [],
        "Cancelled": []
    }

    total_projects = len(projects)
    planning_count = 0
    in_progress_count = 0
    at_risk_count = 0
    on_hold_count = 0
    completed_count = 0
    cancelled_count = 0

    for project in projects:

        cursor.execute("""
            SELECT COUNT(*) AS open_risks
            FROM risks
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project["id"],
        ))

        open_risks = cursor.fetchone()["open_risks"]

        cursor.execute("""
            SELECT COUNT(*) AS open_issues
            FROM issues
            WHERE project_id = %s
            AND status != 'Closed'
        """, (
            project["id"],
        ))

        open_issues = cursor.fetchone()["open_issues"]

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
            completion_rate = round((completed_tasks / total_tasks) * 100)
        else:
            completion_rate = 100 if project["status"] == "Completed" else 0

        project_status = project["status"] or "Planning"

        if project_status in grouped_projects:
            portfolio_stage = project_status
        else:
            portfolio_stage = "Planning"

        project_card = {
            "id": project["id"],
            "name": project["name"],
            "status": project_status,
            "portfolio_stage": portfolio_stage,
            "programme": project.get("programme"),
            "portfolio": project.get("portfolio"),
            "completion_rate": completion_rate,
            "open_risks": open_risks,
            "open_issues": open_issues,
            "portfolio_manager": project.get("portfolio_manager"),
            "portfolio_sponsor": project.get("portfolio_sponsor"),
            "strategic_objective": project.get("strategic_objective")
        }

        grouped_projects[portfolio_stage].append(project_card)

        if portfolio_stage == "Planning":
            planning_count += 1
        elif portfolio_stage == "In Progress":
            in_progress_count += 1
        elif portfolio_stage == "At Risk":
            at_risk_count += 1
        elif portfolio_stage == "On Hold":
            on_hold_count += 1
        elif portfolio_stage == "Completed":
            completed_count += 1
        elif portfolio_stage == "Cancelled":
            cancelled_count += 1

    workflow_alerts = []

    if at_risk_count > 0:
        workflow_alerts.append(f"{at_risk_count} project(s) require portfolio attention.")

    if on_hold_count > 0:
        workflow_alerts.append(f"{on_hold_count} project(s) are currently on hold.")

    if cancelled_count > 0:
        workflow_alerts.append(f"{cancelled_count} project(s) are cancelled and should be reviewed.")

    if not workflow_alerts:
        workflow_alerts.append("Portfolio workflow is currently stable.")

    conn.close()

    return render_template(
        "portfolio_kanban.html",
        grouped_projects=grouped_projects,
        total_projects=total_projects,
        planning_count=planning_count,
        in_progress_count=in_progress_count,
        at_risk_count=at_risk_count,
        on_hold_count=on_hold_count,
        completed_count=completed_count,
        cancelled_count=cancelled_count,
        workflow_alerts=workflow_alerts,
        portfolios=portfolios,
        programmes=programmes,
        selected_portfolio=selected_portfolio,
        selected_programme=selected_programme
    )


@app.route("/update-portfolio-kanban-stage", methods=["POST"])
def update_portfolio_kanban_stage():

    if "user_id" not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    if not has_permission("Projects", "edit"):
        return jsonify({"success": False, "message": "Access denied"}), 403

    data = request.get_json()

    project_id = data.get("project_id")
    new_status = data.get("new_status")

    allowed_statuses = [
        "Planning",
        "In Progress",
        "At Risk",
        "On Hold",
        "Completed",
        "Cancelled"
    ]

    if not project_id or new_status not in allowed_statuses:
        return jsonify({"success": False, "message": "Invalid request"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE projects
        SET status = %s
        WHERE id = %s
        AND user_id = %s
    """, (
        new_status,
        project_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return jsonify({"success": True})



@app.route("/seed-linkedin-demo")
def seed_linkedin_demo():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = session["user_id"]
    today = str(date.today())

    # Remove previous LinkedIn demo data

    cursor.execute("""
                   DELETE
                   FROM tasks
                   WHERE project_id IN (SELECT id
                                        FROM projects
                                        WHERE user_id = %s)
                   """, (user_id,))

    cursor.execute("DELETE FROM risks WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM issues WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM benefits WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM assumptions WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM dependencies WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM approvals WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM stage_gates WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM governance_reviews WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM budgets WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM projects WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM clients WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM team_members WHERE user_id = %s", (user_id,))

    # =====================
    # CLIENTS
    # =====================

    clients = [
        ("Northbridge NHS Trust", "Healthcare", "pmoffice@northbridge-nhs.co.uk", "02070001001", "Active", "Hospital digital transformation and operational command centre programme.", 850000),
        ("MetroLink Transport Authority", "Transport", "delivery@metrolink-demo.co.uk", "02070001002", "Active", "Smart highway and transport infrastructure delivery.", 1200000),
        ("Apex Retail Group", "Retail", "projects@apexretail-demo.com", "02070001003", "Active", "CRM, e-commerce and customer portal transformation.", 450000),
        ("Sterling Finance", "Financial Services", "change@sterlingfinance-demo.com", "02070001004", "Active", "Compliance data, reporting and governance transformation.", 700000),
        ("CloudCore Solutions", "Technology", "pmo@cloudcore-demo.com", "02070001005", "Lead", "SaaS, AI and enterprise platform implementation.", 500000)
    ]

    client_ids = {}

    for client in clients:
        cursor.execute("""
            INSERT INTO clients
            (user_id, name, company, email, phone, status, notes, estimated_value, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            user_id,
            client[0],
            client[1],
            client[2],
            client[3],
            client[4],
            client[5],
            client[6],
            today
        ))

        client_ids[client[0]] = cursor.fetchone()[0]

    # =====================
    # TEAM MEMBERS
    # =====================

    team_members = [
        ("Sarah Johnson", "Senior Project Manager", "sarah.johnson@demo.com", "07100000001", "PRINCE2, Agile, Governance, Stakeholder Management", "Active"),
        ("Michael Brown", "Programme Manager", "michael.brown@demo.com", "07100000002", "Programme Delivery, Portfolio Governance, Steering Committees", "Active"),
        ("Emma Smith", "Business Analyst", "emma.smith@demo.com", "07100000003", "Requirements, Process Mapping, UAT", "Active"),
        ("Daniel Green", "Software Developer", "daniel.green@demo.com", "07100000004", "Python, Flask, APIs, SaaS Platforms", "Active"),
        ("Olivia Harris", "Frontend Developer", "olivia.harris@demo.com", "07100000005", "UI, JavaScript, Dashboards, Accessibility", "Active"),
        ("David Wilson", "PMO Analyst", "david.wilson@demo.com", "07100000006", "Reporting, RAID, Benefits, Excel", "Active"),
        ("Grace Hall", "Finance Manager", "grace.hall@demo.com", "07100000007", "Budgets, Forecasting, Cost Control", "Active"),
        ("Henry Allen", "Resource Manager", "henry.allen@demo.com", "07100000008", "Capacity Planning, Allocation, Workforce Planning", "Active")
    ]

    for member in team_members:
        cursor.execute("""
            INSERT INTO team_members
            (user_id, name, role, email, phone, skills, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            member[0],
            member[1],
            member[2],
            member[3],
            member[4],
            member[5],
            today
        ))

    # =====================
    # PROJECTS + BUDGETS
    # =====================

    projects = [
        ("AI PM Tracker SaaS Platform",
         "Enterprise AI project management platform with dashboards, governance, SaaS controls and reporting.",
         "In Progress", "2026-05-01", "2026-09-30", 75000, 28000, "CloudCore Solutions"),
        ("Hospital Digital Command Centre",
         "Real-time operational dashboard for hospital capacity, staffing and service performance.", "In Progress",
         "2026-06-01", "2026-12-20", 850000, 410000, "Northbridge NHS Trust"),
        ("Smart Highway Upgrade", "Road infrastructure upgrade with smart traffic monitoring and delivery governance.",
         "In Progress", "2026-06-15", "2027-02-28", 1200000, 560000, "MetroLink Transport Authority"),
        ("Retail CRM Migration", "Migration from legacy CRM to a cloud-based customer platform.", "Completed",
         "2026-05-20", "2026-09-20", 160000, 82000, "Apex Retail Group"),
        ("Customer Self-Service Portal",
         "Customer account portal with case tracking, billing visibility and support workflows.", "Planning",
         "2026-07-01", "2026-12-01", 120000, 18000, "Apex Retail Group"),
        ("Financial Compliance Data Hub",
         "Centralised reporting and compliance data platform for regulatory reporting.", "In Progress", "2026-06-10",
         "2027-01-15", 400000, 175000, "Sterling Finance"),
        ("Learning Management Platform", "Digital learning platform with staff training, assessments and reporting.",
         "In Progress", "2026-05-15", "2026-09-30", 180000, 76000, "Northbridge NHS Trust"),
        ("Warehouse Optimisation Programme", "Inventory, fulfilment and warehouse process optimisation.", "In Progress",
         "2026-06-20", "2026-12-15", 280000, 118000, "Apex Retail Group")
    ]

    project_ids = {}

    for project in projects:
        cursor.execute("""
            INSERT INTO projects
            (user_id, name, description, status, start_date, end_date, estimated_budget, actual_cost, created_at, client_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            user_id,
            project[0],
            project[1],
            project[2],
            project[3],
            project[4],
            project[5],
            project[6],
            today,
            client_ids[project[7]]
        ))

        project_id = cursor.fetchone()[0]
        project_ids[project[0]] = project_id

        cursor.execute("""
            INSERT INTO budgets
            (user_id, project_id, budget_amount, actual_cost, forecast_cost, approved_by, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_id,
            project[5],
            project[6],
            project[6] + 25000,
            "Grace Hall",
            "Active",
            today
        ))

    # =====================
    # TASKS
    # =====================

    task_data = {
        "AI PM Tracker SaaS Platform": [
            ("Complete Executive Dashboard QA", "Validate dashboard formulas and executive recommendations.",
             "Sarah Johnson", "High", "Completed", "2026-06-05"),
            ("Prepare LinkedIn Demo Screenshots", "Create realistic demo portfolio screenshots.", "Sarah Johnson",
             "Medium", "Completed", "2026-06-02"),
            ("Fix Usage Analytics Error", "Resolve the SaaS usage analytics internal server error.", "Daniel Green",
             "High", "Completed", "2026-06-12"),
            ("Validate Permission Enforcement", "Check organisation and workspace access controls.", "David Wilson",
             "High", "In Progress", "2026-06-18"),
            ("Complete SaaS Billing Workflow Review", "Review subscriptions, invoices and billing history.",
             "Grace Hall", "Medium", "In Progress", "2026-06-20")
        ],

        "Hospital Digital Command Centre": [
            ("Capture Ward Capacity Requirements", "Document reporting requirements from operational teams.",
             "Emma Smith", "High", "Completed", "2026-06-08"),
            ("Design Executive Capacity Dashboard", "Create leadership view for hospital capacity.", "Olivia Harris",
             "Medium", "Completed", "2026-06-25"),
            ("Integrate Staffing Data Feed", "Connect staffing data feed into command dashboard.", "Daniel Green",
             "High", "In Progress", "2026-06-20"),
            ("Run Clinical UAT Workshop", "Validate dashboard with hospital leads.", "Sarah Johnson", "High",
             "In Progress", "2026-07-02"),
            ("Prepare Go-Live Readiness Report", "Summarise risks, issues and deployment readiness.", "David Wilson",
             "Medium", "Pending", "2026-07-10")
        ],

        "Smart Highway Upgrade": [
            ("Confirm Sensor Installation Locations", "Validate roadside monitoring points.", "Michael Brown", "High",
             "Completed", "2026-06-15"),
            ("Complete Civil Works Schedule", "Finalise lane closure and construction phasing.", "Emma Smith", "Medium",
             "Completed", "2026-06-28"),
            ("Procure Monitoring Devices", "Complete procurement for traffic monitoring hardware.", "Sarah Johnson",
             "High", "Blocked", "2026-06-22"),
            ("Integrate Traffic Data Platform", "Connect sensor data to reporting dashboard.", "Daniel Green", "High",
             "In Progress", "2026-07-12"),
            ("Complete Safety Assurance Review", "Review operational safety controls.", "David Wilson", "High",
             "Pending", "2026-07-18")
        ],

        "Retail CRM Migration": [
            ("Complete Data Mapping", "Map legacy CRM data to target platform.", "Emma Smith", "High", "Completed",
             "2026-06-07"),
            ("Clean Duplicate Customer Records", "Remove duplicate and incomplete records.", "David Wilson", "High",
             "Completed", "2026-06-18"),
            ("Build Migration Scripts", "Develop repeatable customer migration scripts.", "Daniel Green", "High",
             "In Progress", "2026-06-24"),
            ("Run Sales Team UAT", "Validate CRM workflows with sales users.", "Sarah Johnson", "Medium", "In Progress",
             "2026-07-04"),
            ("Prepare Go-Live Checklist", "Confirm cutover and support plan.", "Michael Brown", "Medium", "Pending",
             "2026-07-12")
        ],
    }

    for project_name, tasks in task_data.items():
        for task in tasks:
            cursor.execute("""
                INSERT INTO tasks
                (project_id, title, description, assigned_to, priority, status, due_date, created_at, estimated_hours, actual_hours, hourly_rate)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                project_ids[project_name],
                task[0],
                task[1],
                task[2],
                task[3],
                task[4],
                task[5],
                today,
                24,
                12 if task[4] == "Completed" else 8,
                75
            ))

    # =====================
    # GOVERNANCE
    # =====================

    risks = [
        ("Smart Highway Upgrade",
         "Procurement Delay",
         "Monitoring devices may arrive later than planned.",
         "High",
         "High",
         8,
         "Escalate supplier plan and agree contingency.",
         "Sarah Johnson"),

        ("Hospital Digital Command Centre",
         "Data Feed Instability",
         "Operational data feeds may not refresh consistently.",
         "Medium",
         "High",
         7,
         "Add monitoring and fallback reporting.",
         "Daniel Green"),

        ("Retail CRM Migration",
         "Data Quality Risk",
         "Legacy customer records contain duplicates.",
         "Medium",
         "Medium",
         5,
         "Complete data cleansing before migration.",
         "David Wilson"),

        ("Financial Compliance Data Hub",
         "Regulatory Reporting Risk",
         "Reporting rules may change during delivery.",
         "Medium",
         "Medium",
         4,
         "Schedule fortnightly compliance reviews.",
         "Michael Brown"),

        ("AI PM Tracker SaaS Platform",
         "Permission Enforcement Risk",
         "Organisation and workspace permissions require final validation.",
         "Low",
         "Medium",
         3,
         "Run security and access review.",
         "David Wilson")
    ]

    for risk in risks:
        cursor.execute("""
            INSERT INTO risks
            (user_id, project_id, title, description, probability, impact, severity_score, mitigation, owner, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[risk[0]],
            risk[1],
            risk[2],
            risk[3],
            risk[4],
            risk[5],
            risk[6],
            risk[7],
            "Open",
            today
        ))

    issues = [
        (
            "Smart Highway Upgrade",
            "Supplier Lead Time Extension",
            "Supplier confirmed a two-week delay.",
            "High",
            "Sarah Johnson",
            "Open",
            "Escalation raised with procurement."
        ),

        (
            "Retail CRM Migration",
            "Duplicate Customer Records",
            "Migration rehearsal found duplicate records.",
            "Medium",
            "David Wilson",
            "Open",
            "Data cleansing in progress."
        ),

        (
            "AI PM Tracker SaaS Platform",
            "Usage Analytics Page Error",
            "Usage analytics route requires debugging.",
            "Medium",
            "Daniel Green",
            "Open",
            "Route and query review required."
        ),

        (
            "Hospital Digital Command Centre",
            "Late User Acceptance Testing",
            "Business users were unavailable for planned UAT sessions.",
            "Medium",
            "Sarah Johnson",
            "Open",
            "Reschedule workshops and secure stakeholder attendance."
        ),

        (
            "AI PM Tracker SaaS Platform",
            "API Authentication Failure",
            "Authentication errors identified during integration testing.",
            "High",
            "Daniel Green",
            "Open",
            "Review token configuration and API security settings."
        )
    ]

    for issue in issues:
        cursor.execute("""
            INSERT INTO issues
            (user_id, project_id, title, description, priority, owner, status, resolution, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[issue[0]],
            issue[1],
            issue[2],
            issue[3],
            issue[4],
            issue[5],
            issue[6],
            today
        ))

    for project_name in list(project_ids.keys())[:5]:
        cursor.execute("""
            INSERT INTO changes
            (user_id, project_id, title, description, impact, requested_by, approval_status, implementation_plan, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[project_name],
            "Dashboard Reporting Enhancement",
            "Request to improve executive reporting visibility.",
            "Medium impact on reporting scope.",
            "Project Sponsor",
            "Pending",
            "Review through change control board.",
            today
        ))

        assumption_templates = [
            (
                "Stakeholders Available for Review",
                "Key stakeholders will be available for scheduled review sessions and approvals.",
                "Sarah Johnson"
            ),
            (
                "Supplier Delivery on Schedule",
                "Third-party supplier will deliver agreed components according to plan.",
                "Michael Brown"
            ),
            (
                "Budget Approval Maintained",
                "Approved project funding will remain available throughout delivery.",
                "Grace Hall"
            ),
            (
                "Resources Remain Available",
                "Project resources will remain allocated for the duration of delivery.",
                "Henry Allen"
            ),
            (
                "Infrastructure Supports Deployment",
                "Existing infrastructure capacity will support planned deployment activities.",
                "Daniel Green"
            )
        ]

        dependency_templates = [
            (
                "Identity Provider Integration",
                "Delivery depends on identity provider configuration being completed.",
                "Daniel Green",
                "2026-07-05"
            ),
            (
                "Third Party API Availability",
                "Delivery depends on external API availability during integration testing.",
                "Daniel Green",
                "2026-07-10"
            ),
            (
                "Security Approval",
                "Release depends on security review and approval.",
                "David Wilson",
                "2026-07-15"
            ),
            (
                "Infrastructure Provisioning",
                "Deployment depends on infrastructure environments being available.",
                "Michael Brown",
                "2026-07-20"
            ),
            (
                "Production Release Window",
                "Go-live depends on an agreed production release window.",
                "Sarah Johnson",
                "2026-07-25"
            )
        ]

        project_index = list(project_ids.keys()).index(project_name)

        assumption = assumption_templates[project_index]
        dependency = dependency_templates[project_index]

        cursor.execute("""
                       INSERT INTO assumptions
                           (user_id, project_id, title, description, owner, status, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       """, (
                           user_id,
                           project_ids[project_name],
                           assumption[0],
                           assumption[1],
                           assumption[2],
                           "Open",
                           today
                       ))

        cursor.execute("""
                       INSERT INTO dependencies
                       (user_id, project_id, title, description, owner, status, target_date, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       """, (
                           user_id,
                           project_ids[project_name],
                           dependency[0],
                           dependency[1],
                           dependency[2],
                           "Open",
                           dependency[3],
                           today
                       ))

        cursor.execute("""
            INSERT INTO stakeholders
            (user_id, project_id, name, role, influence, interest, communication_plan, owner, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[project_name],
            "Executive Sponsor",
            "Sponsor",
            "High",
            "High",
            "Monthly steering update and exception reporting.",
            "Sarah Johnson",
            "Active",
            today
        ))

        cursor.execute("""
            INSERT INTO decisions
            (user_id, project_id, title, decision_maker, impact, reason, status, decision_date, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[project_name],
            "Approve Delivery Approach",
            "Project Board",
            "Medium",
            "Delivery approach approved to maintain programme momentum.",
            "Approved",
            today,
            today
        ))

        cursor.execute("""
            INSERT INTO actions
            (user_id, project_id, title, description, owner, priority, status, due_date, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[project_name],
            "Update Governance Pack",
            "Refresh governance pack for next steering review.",
            "David Wilson",
            "High",
            "Open",
            "2026-07-10",
            today
        ))

        cursor.execute("""
            INSERT INTO lessons
            (user_id, project_id, title, what_happened, what_went_well, what_went_wrong, recommendation, owner, created_at, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[project_name],
            "Early Stakeholder Alignment",
            "Stakeholder input was needed earlier than planned.",
            "Weekly communication improved decision speed.",
            "Initial requirement assumptions needed more validation.",
            "Run discovery workshops before delivery starts.",
            "Project Manager",
            today,
            "Open"
        ))

        cursor.execute("""
            INSERT INTO stage_gates
            (user_id, project_id, stage_name, status, reviewer, comments, review_date, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[project_name],
            "Delivery Readiness Gate",
            "Approved",
            "Programme Manager",
            "Project can proceed with controlled monitoring.",
            today,
            today
        ))

        cursor.execute("""
            INSERT INTO approvals
            (user_id, project_id, item_type, item_id, submitted_by, approver, status, submitted_date, decision_date, comments)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[project_name],
            "Change Request",
            project_ids[project_name],
            "Project Manager",
            "Programme Manager",
            "Pending Approval",
            date.today(),
            None,
            "Awaiting governance review."
        ))

        cursor.execute("""
            INSERT INTO governance_reviews
            (user_id, project_id, review_name, review_type, review_date, outcome, decision, actions, owner, next_review_date, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[project_name],
            "Monthly Governance Review",
            "Monthly Review",
            date.today(),
            "Project reviewed against risk, budget and delivery indicators.",
            "Continue with controlled delivery.",
            "Update RAID actions before next review.",
            "Project Manager",
            date.today(),
            "Scheduled",
            today
        ))

    benefits = [
        ("AI PM Tracker SaaS Platform",
         "Improve PMO Reporting Speed",
         "Reduce manual dashboard preparation time.",
         "30% faster reporting cycle",
         "Weekly reporting effort comparison",
         "PMO Lead",
         "Realised",
         "2026-09-30"),

        ("Hospital Digital Command Centre",
         "Improve Operational Visibility",
         "Provide live hospital capacity view.",
         "Faster operational decisions",
         "Monthly operational review",
         "Operations Director",
         "Realised",
         "2026-12-20"),

        ("Retail CRM Migration",
         "Improve Customer Data Quality",
         "Create a single accurate customer view.",
         "20% reduction in duplicate records",
         "CRM data quality score",
         "CRM Owner",
         "Tracking",
         "2026-09-20")
    ]

    for benefit in benefits:
        cursor.execute("""
            INSERT INTO benefits
            (user_id, project_id, title, description, expected_value, measurement_method, owner, status, target_date, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[benefit[0]],
            benefit[1],
            benefit[2],
            benefit[3],
            benefit[4],
            benefit[5],
            benefit[6],
            benefit[7],
            today
        ))

    # =====================
    # PORTFOLIO / PROGRAMME
    # =====================

    cursor.execute("""
        INSERT INTO programmes
        (user_id, programme_name, description, sponsor, manager, status, start_date, end_date, budget, benefits, risks, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        user_id,
        "Enterprise Digital Transformation Programme",
        "Portfolio of digital, SaaS, CRM and reporting projects.",
        "Chief Transformation Officer",
        "Michael Brown",
        "In Progress",
        "2026-05-01",
        "2027-06-30",
        3500000,
        "Improved reporting, better governance and reduced manual effort.",
        "Supplier delays, permission controls and data quality.",
        today
    ))

    for i, project_name in enumerate(project_ids.keys()):
        business_value = 9 - (i % 3)
        strategic_alignment = 8 - (i % 2)
        risk_score = 4 + (i % 4)
        cost_score = 6 + (i % 3)
        priority_score = business_value + strategic_alignment - risk_score + cost_score

        cursor.execute("""
            INSERT INTO project_prioritisation
            (user_id, project_id, business_value_score, strategic_alignment_score, risk_score, cost_score, priority_score, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            project_ids[project_name],
            business_value,
            strategic_alignment,
            risk_score,
            cost_score,
            priority_score,
            today
        ))

    cursor.execute("""
        INSERT INTO portfolio_health
        (user_id, health_score, risk_exposure, financial_health, performance_score, trend, commentary, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        user_id,
        74,
        38,
        82,
        71,
        "Stable",
        "Portfolio is progressing with controlled risk exposure and strong financial discipline.",
        today
    ))

    # =====================
    # ADMIN / SAAS
    # =====================

    roles = ["Admin", "Project Manager", "PMO", "Executive", "Team Member"]

    for role in roles:
        cursor.execute("""
            INSERT INTO user_roles
            (user_id, role, created_at)
            VALUES (%s,%s,%s)
        """, (user_id, role, today))

    permissions = [
        ("Admin", "Projects", True, True, True, True),
        ("Admin", "Governance", True, True, True, True),
        ("Admin", "Finance", True, True, True, True),
        ("Admin", "Reports", True, True, True, True),
        ("Project Manager", "Projects", True, True, True, False),
        ("Project Manager", "Governance", True, True, True, False),
        ("PMO", "Reports", True, True, True, False),
        ("Executive", "Portfolio", True, False, False, False),
        ("Team Member", "Tasks", True, False, True, False)
    ]

    for permission in permissions:
        cursor.execute("""
            INSERT INTO permissions
            (role, module, can_view, can_create, can_edit, can_delete)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, permission)

    cursor.execute("""
        INSERT INTO organisations
        (user_id, organisation_name, industry, plan, status, created_at, trial_start_date, trial_end_date, subscription_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        user_id,
        "AI PM Tracker Demo Organisation",
        "Technology",
        "Professional",
        "Active",
        today,
        today,
        "2026-06-16",
        "Trial"
    ))

    organisation_id = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO workspaces
        (user_id, organisation_id, workspace_name, workspace_type, owner, status, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        user_id,
        organisation_id,
        "PMO Delivery Workspace",
        "Portfolio Office",
        "Workspace Admin",
        "Active",
        today
    ))

    workspace_id = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO user_roles
        (user_id, role, organisation_id, workspace_id, created_at)
        VALUES (%s,%s,%s,%s,%s)
    """, (
        user_id,
        "Admin",
        organisation_id,
        workspace_id,
        today
    ))

    plans = [
        ("Free", 0, "Monthly", 3, 1, "Basic project tracking", "Active"),
        ("Professional", 49, "Monthly", 50, 10, "AI dashboards, governance and reporting", "Active"),
        ("Enterprise", 99, "Monthly", 9999, 9999, "Unlimited usage, premium support and enterprise governance", "Active")
    ]

    plan_ids = {}

    for plan in plans:
        cursor.execute("""
            INSERT INTO subscription_plans
            (user_id, plan_name, price, billing_cycle, max_projects, max_users, features, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            user_id,
            plan[0],
            plan[1],
            plan[2],
            plan[3],
            plan[4],
            plan[5],
            plan[6],
            today
        ))

        plan_ids[plan[0]] = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO customer_subscriptions
        (user_id, organisation_id, plan_id, start_date, end_date, status, payment_status, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        user_id,
        organisation_id,
        plan_ids["Professional"],
        date.today(),
        date.today(),
        "Trial",
        "Pending",
        today
    ))

    cursor.execute("""
        INSERT INTO billing_history
        (user_id, organisation_id, plan, amount, status, reference_number, billing_date, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        user_id,
        organisation_id,
        "Professional",
        49,
        "Trial",
        "BILL-DEMO-001",
        today,
        today
    ))

    cursor.execute("""
        INSERT INTO invoices
        (user_id, organisation_id, invoice_number, plan, amount, status, invoice_date, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        user_id,
        organisation_id,
        "INV-DEMO-001",
        "Professional",
        49,
        "Draft",
        today,
        today
    ))

    cursor.execute("""
        INSERT INTO user_invitations
        (organisation_id, workspace_id, invited_email, role, status, invitation_token, invited_by, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        organisation_id,
        workspace_id,
        "new.user@demo-company.com",
        "Project Manager",
        "Pending",
        f"linkedin-demo-token-{user_id}",
        user_id,
        today
    ))

    notifications = [
        ("Risk Alerts", "Email", "Yes", "Immediate"),
        ("Issue Alerts", "Email", "Yes", "Immediate"),
        ("Governance Reviews", "Email", "Yes", "Weekly"),
        ("AI Insights", "Dashboard", "Yes", "Daily")
    ]

    for notification in notifications:
        cursor.execute("""
            INSERT INTO notification_settings
            (user_id, notification_type, channel, enabled, frequency, created_at)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            notification[0],
            notification[1],
            notification[2],
            notification[3],
            today
        ))

    cursor.execute("""
        INSERT INTO email_notifications
        (user_id, recipient_email, subject, message, status, created_at)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (
        user_id,
        "sponsor@demo-company.com",
        "Executive Portfolio Update",
        "Your weekly AI PM Tracker portfolio report is ready.",
        "Draft",
        today
    ))

    audit_entries = [
        ("Create Project", "Projects", "AI PM Tracker SaaS Platform created"),
        ("Update Dashboard", "Reports", "Executive dashboard formulas improved"),
        ("Review Governance", "Governance", "Monthly governance review scheduled"),
        ("Create Subscription", "SaaS", "Professional trial subscription created")
    ]

    for entry in audit_entries:
        cursor.execute("""
            INSERT INTO audit_logs
            (user_id, action, module, details, created_at)
            VALUES (%s,%s,%s,%s,%s)
        """, (
            user_id,
            entry[0],
            entry[1],
            entry[2],
            today
        ))

    conn.commit()
    conn.close()

    return "LinkedIn-ready AI PM Tracker demo data added successfully"



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )