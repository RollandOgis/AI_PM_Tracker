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


def calculate_financial_health(budget_amount, actual_cost):

    budget_amount = float(budget_amount or 0)
    actual_cost = float(actual_cost or 0)

    if budget_amount <= 0:
        return 50

    usage = round((actual_cost / budget_amount) * 100)

    if usage <= 50:
        return 90

    elif usage <= 70:
        return 80

    elif usage <= 90:
        return 65

    elif usage <= 100:
        return 50

    else:
        return max(0, 50 - ((usage - 100) * 2))


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

    cursor.execute("""
        SELECT
            tasks.*,
            projects.name AS project_name
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        ORDER BY
            CASE
                WHEN tasks.due_date IS NULL OR tasks.due_date = '' THEN 1
                ELSE 0
            END,
            tasks.due_date ASC
    """, (
        session["user_id"],
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

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM projects
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

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

    cursor.execute("""
        SELECT *
        FROM risks
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    risks = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM issues
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    issues = cursor.fetchall()

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

        avatar_initials = request.form["avatar_initials"]

        cursor.execute("""
            UPDATE users
            SET avatar_initials = %s
            WHERE id = %s
        """, (
            avatar_initials,
            session["user_id"]
        ))

        conn.commit()

        session["avatar_initials"] = avatar_initials

        conn.close()

        return redirect("/")

    cursor.execute("""
        SELECT *
        FROM users
        WHERE id = %s
    """, (
        session["user_id"],
    ))

    user = cursor.fetchone()

    conn.close()

    return render_template(
        "profile.html",
        user=user
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

        username = request.form["username"]
        email = request.form.get("email", "")
        password = request.form["password"]

        hashed_password = generate_password_hash(password)
        avatar_initials = username[:2].upper()
        verification_token = str(uuid.uuid4())

        conn = get_db_connection()
        cursor = conn.cursor()

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
                    verification_token_created_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                username,
                email,
                hashed_password,
                avatar_initials,
                False,
                verification_token,
                str(datetime.now())
            ))

            conn.commit()
            conn.close()

            return f"""
            <h2>Account Created</h2>
            <p>Your account was created successfully.</p>
            <p><strong>Verification Token:</strong> {verification_token}</p>
            <p>
                <a href="/verify-email/{verification_token}">
                    Verify Email
                </a>
            </p>
            """

        except Exception as e:

            conn.close()
            error = f"Registration failed: {str(e)}"

    return render_template(
        "register.html",
        error=error
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
        return "Invalid verification token"

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

    return """
    <h2>Email Verified</h2>
    <p>Your email has been verified successfully.</p>
    <p><a href="/login">Go to Login</a></p>
    """


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()

        cursor = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        cursor.execute("""
            SELECT *
            FROM users
            WHERE username = %s
        """, (
            username,
        ))

        user = cursor.fetchone()

        conn.close()

        if user:

            stored_password = user["password"]

            if check_password_hash(stored_password, password) or stored_password == password:

                if user.get("email") and user.get("is_verified") is False:
                    return """
                    <h2>Email Not Verified</h2>
                    <p>Please verify your email before logging in.</p>
                    """

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
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    clients = cursor.fetchall()

    conn.close()

    return render_template(
        "clients.html",
        clients=clients
    )


@app.route("/add-client", methods=["GET", "POST"])
def add_client():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Clients", "create"):
        return "Access denied"

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
                user_id
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
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

        name = request.form.get("name", "")
        company = request.form.get("company", "")
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")
        status = request.form.get("status", "Lead")
        notes = request.form.get("notes", "")

        estimated_value = float(
            request.form.get("estimated_value", 0) or 0
        )

        cursor.execute("""
            UPDATE clients
            SET
                name = %s,
                company = %s,
                email = %s,
                phone = %s,
                status = %s,
                notes = %s,
                estimated_value = %s
            WHERE id = %s
            AND user_id = %s
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
            INSERT INTO activities
            (
                activity,
                created_at
            )
            VALUES (%s,%s)
        """, (
            activity_text,
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

    search = request.args.get("search", "")

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
        AND (
            tasks.title ILIKE %s
            OR projects.name ILIKE %s
            OR tasks.status ILIKE %s
            OR tasks.priority ILIKE %s
        )
        ORDER BY tasks.id DESC
    """, (
        session["user_id"],
        f"%{search}%",
        f"%{search}%",
        f"%{search}%",
        f"%{search}%"
    ))

    tasks = cursor.fetchall()

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

    if request.method == "POST":

        prompt = request.form.get("prompt", "")

        conn = get_db_connection()

        cursor = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

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
            SELECT COUNT(*) AS total_projects
            FROM projects
            WHERE user_id = %s
        """, (
            session["user_id"],
        ))

        total_projects = cursor.fetchone()["total_projects"]

        cursor.execute("""
            SELECT COUNT(*) AS over_budget_projects
            FROM projects
            WHERE user_id = %s
            AND estimated_budget > 0
            AND actual_cost > estimated_budget
        """, (
            session["user_id"],
        ))

        over_budget_projects = cursor.fetchone()["over_budget_projects"]

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

    if not has_permission("Team", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()

        cursor = conn.cursor()

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
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
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

    if not has_permission("Team", "edit"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

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
                status = %s
            WHERE id = %s
            AND user_id = %s
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

    create_activity(
        f"{session['username']} deleted a team member"
    )

    return redirect("/team")

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

        utilisation_data.append({
            "name": member["name"],
            "role": member["role"],
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "active_tasks": active_tasks,
            "blocked_tasks": blocked_tasks,
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

    if not has_permission("Budgets", "create"):
        return "Access denied"

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

        utilisation = min(
            total_tasks * 10,
            100
        )

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

    if not has_permission("Team", "view"):
        return "Access denied"

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

        current_utilisation = min(
            total_tasks * 10,
            100
        )

        forecasted_utilisation = min(
            current_utilisation + 15,
            100
        )

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

    if not has_permission("Team", "view"):
        return "Access denied"

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

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM programmes
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (
        session["user_id"],
    ))

    programmes = cursor.fetchall()

    conn.close()

    return render_template(
        "programmes.html",
        programmes=programmes
    )


@app.route("/add-programme", methods=["GET", "POST"])
def add_programme():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Programmes", "create"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

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

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

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
        DELETE FROM programmes
        WHERE id = %s
        AND user_id = %s
    """, (
        programme_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/programmes")


@app.route("/edit-programme/<int:programme_id>", methods=["GET", "POST"])
def edit_programme(programme_id):

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Programmes", "edit"):
        return "Access denied"

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

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
            request.form["programme_name"],
            request.form["description"],
            request.form["sponsor"],
            request.form["manager"],
            request.form["status"],
            request.form["start_date"],
            request.form["end_date"],
            request.form["budget"],
            request.form["benefits"],
            request.form["risks"],
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
        DELETE FROM programmes
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


@app.route("/executive-charts")
def executive_charts():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT COUNT(*) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (session["user_id"],))
    total_projects = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS total_risks
        FROM risks
        WHERE user_id = %s
    """, (session["user_id"],))
    total_risks = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS total_issues
        FROM issues
        WHERE user_id = %s
    """, (session["user_id"],))
    total_issues = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS total_changes
        FROM changes
        WHERE user_id = %s
    """, (session["user_id"],))
    total_changes = cursor.fetchone()

    cursor.execute("""
        SELECT *
        FROM portfolio_health
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (session["user_id"],))
    latest_health = cursor.fetchone()

    conn.close()

    return render_template(
        "executive_charts.html",
        total_projects=total_projects,
        total_risks=total_risks,
        total_issues=total_issues,
        total_changes=total_changes,
        latest_health=latest_health
    )


@app.route("/portfolio-trends")
def portfolio_trends():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM portfolio_health
        WHERE user_id = %s
        ORDER BY created_at ASC
    """, (session["user_id"],))

    trends = cursor.fetchall()
    conn.close()

    return render_template(
        "portfolio_trends.html",
        trends=trends
    )


@app.route("/financial-trends")
def financial_trends():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        SELECT
            budgets.*,
            projects.name AS project_name
        FROM budgets
        LEFT JOIN projects
        ON budgets.project_id = projects.id
        WHERE budgets.user_id = %s
        ORDER BY budgets.created_at ASC
    """, (session["user_id"],))

    budgets = cursor.fetchall()
    conn.close()

    return render_template(
        "financial_trends.html",
        budgets=budgets
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

    forecast_items = []

    total_budget = 0
    total_actual = 0
    total_forecast = 0

    for item in budgets:

        budget_amount = float(item["budget_amount"] or 0)
        actual_cost = float(item["actual_cost"] or 0)
        forecast_cost = float(item["forecast_cost"] or 0)

        total_budget += budget_amount
        total_actual += actual_cost
        total_forecast += forecast_cost

        variance = forecast_cost - actual_cost

        if actual_cost > forecast_cost:
            status = "Over Forecast"
        elif actual_cost == forecast_cost:
            status = "On Forecast"
        else:
            status = "Under Forecast"

        forecast_items.append({
            "project_name": item["project_name"],
            "budget_amount": budget_amount,
            "actual_cost": actual_cost,
            "forecast_cost": forecast_cost,
            "variance": variance,
            "status": status
        })

    conn.close()

    return render_template(
        "forecast_vs_actual.html",
        forecast_items=forecast_items,
        total_budget=total_budget,
        total_actual=total_actual,
        total_forecast=total_forecast
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
        SELECT
            projects.id,
            projects.name,
            projects.estimated_budget,
            projects.actual_cost
        FROM projects
        WHERE projects.user_id = %s
        ORDER BY projects.name
    """, (
        session["user_id"],
    ))

    projects = cursor.fetchall()

    profitability_data = []

    total_budget = 0
    total_actual = 0
    total_profit = 0

    for project in projects:

        budget = float(
            project["estimated_budget"] or 0
        )

        actual = float(
            project["actual_cost"] or 0
        )

        profit = budget - actual

        total_budget += budget
        total_actual += actual
        total_profit += profit

        if budget > 0:
            profitability_percent = round(
                (profit / budget) * 100
            )
        else:
            profitability_percent = 0

        if profitability_percent >= 30:
            status = "High Profit"
        elif profitability_percent >= 0:
            status = "Profitable"
        else:
            status = "Loss"

        profitability_data.append({
            "project_name": project["name"],
            "budget": budget,
            "actual": actual,
            "profit": profit,
            "profitability_percent": profitability_percent,
            "status": status
        })

    conn.close()

    return render_template(
        "profitability_dashboard.html",
        profitability_data=profitability_data,
        total_budget=total_budget,
        total_actual=total_actual,
        total_profit=total_profit
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
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    team_members = cursor.fetchall()

    allocation_data = []

    for member in team_members:

        cursor.execute("""
            SELECT
                tasks.title,
                tasks.status,
                tasks.priority,
                tasks.due_date,
                projects.name AS project_name
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
            ORDER BY tasks.due_date ASC
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

        utilisation = min(
            len(active_tasks) * 10,
            100
        )

        if utilisation >= 80:
            allocation_status = "Overallocated"
        elif utilisation >= 50:
            allocation_status = "Allocated"
        else:
            allocation_status = "Available"

        allocation_data.append({
            "member": member,
            "tasks": tasks,
            "active_tasks": len(active_tasks),
            "completed_tasks": len(completed_tasks),
            "utilisation": utilisation,
            "allocation_status": allocation_status
        })

    conn.close()

    return render_template(
        "resource_allocation.html",
        allocation_data=allocation_data
    )


@app.route("/portfolio-pdf-report")
def portfolio_pdf_report():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Reports", "view"):
        return "Access denied"

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
    total_projects = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS total_risks
        FROM risks
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))
    total_risks = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS total_issues
        FROM issues
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))
    total_issues = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS total_changes
        FROM changes
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))
    total_changes = cursor.fetchone()

    cursor.execute("""
        SELECT *
        FROM portfolio_health
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (
        session["user_id"],
    ))
    latest_health = cursor.fetchone()

    cursor.execute("""
        SELECT
            project_prioritisation.*,
            projects.name AS project_name
        FROM project_prioritisation
        LEFT JOIN projects
        ON project_prioritisation.project_id = projects.id
        WHERE project_prioritisation.user_id = %s
        ORDER BY project_prioritisation.priority_score DESC
        LIMIT 5
    """, (
        session["user_id"],
    ))
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
    pdf.drawString(50, y, f"Generated for User ID: {session['user_id']}")

    y -= 40

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Portfolio Summary")

    y -= 25

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Total Projects: {total_projects['total_projects']}")
    y -= 20
    pdf.drawString(50, y, f"Total Risks: {total_risks['total_risks']}")
    y -= 20
    pdf.drawString(50, y, f"Total Issues: {total_issues['total_issues']}")
    y -= 20
    pdf.drawString(50, y, f"Total Changes: {total_changes['total_changes']}")

    y -= 40

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Latest Portfolio Health")

    y -= 25

    pdf.setFont("Helvetica", 11)

    if latest_health:

        pdf.drawString(50, y, f"Health Score: {latest_health['health_score']}%")
        y -= 20
        pdf.drawString(50, y, f"Risk Exposure: {latest_health['risk_exposure']}%")
        y -= 20
        pdf.drawString(50, y, f"Financial Health: {latest_health['financial_health']}%")
        y -= 20
        pdf.drawString(50, y, f"Performance Score: {latest_health['performance_score']}%")
        y -= 20
        pdf.drawString(50, y, f"Trend: {latest_health['trend']}")

    else:

        pdf.drawString(50, y, "No portfolio health record found.")

    y -= 40

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

            project_name = item["project_name"] or "No Project"
            priority_score = item["priority_score"]

            pdf.drawString(
                50,
                y,
                f"#{rank} {project_name} - Priority Score: {priority_score}"
            )

            y -= 20
            rank += 1

    else:

        pdf.drawString(50, y, "No project prioritisation records found.")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=portfolio_report.pdf"

    return response


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
        ORDER BY risks.severity_score DESC
    """, (
        session["user_id"],
    ))

    risks = cursor.fetchall()

    ai_risks = []

    for risk in risks:

        severity = risk["severity_score"] or 0
        status = risk["status"] or ""

        if severity >= 8:
            ai_level = "Critical"
            recommendation = "Escalate immediately and create a mitigation action plan."
        elif severity >= 6:
            ai_level = "High"
            recommendation = "Review weekly and assign a clear mitigation owner."
        elif severity >= 3:
            ai_level = "Medium"
            recommendation = "Monitor regularly and update mitigation progress."
        else:
            ai_level = "Low"
            recommendation = "Keep under observation during normal project reviews."

        if status != "Closed" and severity >= 6:
            escalation_warning = "Escalation Recommended"
        else:
            escalation_warning = "No Escalation Required"

        ai_risks.append({
            "id": risk["id"],
            "title": risk["title"],
            "project_name": risk["project_name"],
            "owner": risk["owner"],
            "status": risk["status"],
            "severity_score": severity,
            "ai_level": ai_level,
            "escalation_warning": escalation_warning,
            "recommendation": recommendation
        })

    conn.close()

    return render_template(
        "ai_risk_engine.html",
        ai_risks=ai_risks
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
            completion_rate = round((completed_tasks / total_tasks) * 100)
        else:
            completion_rate = 0

        risk_points = (
            overdue_tasks * 2
            + blocked_tasks * 2
            + open_risks * 2
            + open_issues * 2
        )

        health_prediction = 100 - risk_points

        if health_prediction < 0:
            health_prediction = 0

        if health_prediction >= 75:
            ai_status = "Healthy"
            forecast = "Project is likely to stay on track."
        elif health_prediction >= 50:
            ai_status = "Watch"
            forecast = "Project may need management attention."
        else:
            ai_status = "At Risk"
            forecast = "Project has a high chance of delay or escalation."

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
            "health_prediction": health_prediction,
            "ai_status": ai_status,
            "forecast": forecast
        })

    conn.close()

    return render_template(
        "ai_project_intelligence.html",
        project_intelligence=project_intelligence
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

    for task in tasks:

        priority = task["priority"] or "Low"
        status = task["status"] or "Pending"
        due_date = task["due_date"]

        ai_priority_score = 0

        if priority == "High":
            ai_priority_score += 5
        elif priority == "Medium":
            ai_priority_score += 3
        else:
            ai_priority_score += 1

        if status == "Blocked":
            ai_priority_score += 4

        if due_date and str(due_date) < str(date.today()):
            ai_priority_score += 5

        if ai_priority_score >= 9:
            sprint_action = "Move into current sprint immediately."
            sprint_level = "Critical"
        elif ai_priority_score >= 6:
            sprint_action = "Prioritise in the next sprint."
            sprint_level = "High"
        elif ai_priority_score >= 3:
            sprint_action = "Schedule after high priority work."
            sprint_level = "Medium"
        else:
            sprint_action = "Keep in backlog for later planning."
            sprint_level = "Low"

        sprint_recommendations.append({
            "title": task["title"],
            "project_name": task["project_name"],
            "priority": priority,
            "status": status,
            "due_date": due_date,
            "assigned_to": task["assigned_to"],
            "ai_priority_score": ai_priority_score,
            "sprint_level": sprint_level,
            "sprint_action": sprint_action
        })

    conn.close()

    return render_template(
        "ai_sprint_management.html",
        sprint_recommendations=sprint_recommendations
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
    """, (
        session["user_id"],
    ))
    pending_changes = cursor.fetchone()["pending_changes"]

    cursor.execute("""
        SELECT *
        FROM portfolio_health
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (
        session["user_id"],
    ))
    latest_health = cursor.fetchone()

    cursor.execute("""
        SELECT
            project_prioritisation.*,
            projects.name AS project_name
        FROM project_prioritisation
        LEFT JOIN projects
        ON project_prioritisation.project_id = projects.id
        WHERE project_prioritisation.user_id = %s
        ORDER BY project_prioritisation.priority_score DESC
        LIMIT 3
    """, (
        session["user_id"],
    ))
    top_priorities = cursor.fetchall()

    conn.close()

    if latest_health:
        health_score = latest_health["health_score"]
        risk_exposure = latest_health["risk_exposure"]
        financial_health = latest_health["financial_health"]
        trend = latest_health["trend"]
    else:
        health_score = 0
        risk_exposure = 0
        financial_health = 0
        trend = "No data"

    if health_score >= 75 and open_risks <= 3 and open_issues <= 3:
        executive_summary = "Portfolio position is healthy. Current delivery indicators suggest the portfolio is broadly under control."
        board_recommendation = "Continue monitoring key projects and maintain the current governance rhythm."

    elif health_score >= 50:
        executive_summary = "Portfolio position requires attention. Some delivery or governance indicators suggest potential pressure."
        board_recommendation = "Review high-priority projects, open risks, issues and budget exposure in the next governance meeting."

    else:
        executive_summary = "Portfolio position is at risk. Current indicators suggest escalation may be required."
        board_recommendation = "Escalate portfolio health, review recovery plans and assign ownership for urgent corrective actions."

    return render_template(
        "ai_executive_assistant.html",
        total_projects=total_projects,
        open_risks=open_risks,
        open_issues=open_issues,
        pending_changes=pending_changes,
        health_score=health_score,
        risk_exposure=risk_exposure,
        financial_health=financial_health,
        trend=trend,
        top_priorities=top_priorities,
        executive_summary=executive_summary,
        board_recommendation=board_recommendation
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
            recommendation = "Immediate management attention is required."
        elif risk_score >= 40:
            prediction = "Medium Risk"
            recommendation = "Monitor closely and review delivery blockers."
        else:
            prediction = "Low Risk"
            recommendation = "Project currently appears stable."

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
            "recommendation": recommendation
        })

    conn.close()

    return render_template(
        "ai_predictive_risk_scoring.html",
        risk_predictions=risk_predictions
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

    for project in projects:

        estimated_budget = float(
            project["estimated_budget"] or 0
        )

        actual_cost = float(
            project["actual_cost"] or 0
        )

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
            completion_rate = (
                completed_tasks / total_tasks
            )
        else:
            completion_rate = 0

        if completion_rate > 0:
            forecast_cost = round(
                actual_cost / completion_rate,
                2
            )
        else:
            forecast_cost = actual_cost

        variance = round(
            forecast_cost - estimated_budget,
            2
        )

        if variance > 0:
            forecast_status = "Over Budget"
        elif variance < 0:
            forecast_status = "Under Budget"
        else:
            forecast_status = "On Budget"

        forecasts.append({

            "project_name": project["name"],
            "estimated_budget": estimated_budget,
            "actual_cost": actual_cost,
            "forecast_cost": forecast_cost,
            "variance": variance,
            "forecast_status": forecast_status

        })

    conn.close()

    return render_template(
        "ai_budget_forecasting.html",
        forecasts=forecasts
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

        cursor.execute("""
            SELECT COUNT(*) AS overdue_tasks
            FROM tasks
            WHERE project_id = %s
            AND due_date < %s
            AND status != 'Completed'
        """, (
            project["id"],
            str(date.today())
        ))

        overdue_tasks = cursor.fetchone()["overdue_tasks"]

        if total_tasks > 0:
            completion_rate = round(
                (completed_tasks / total_tasks) * 100
            )
        else:
            completion_rate = 0

        delay_risk = overdue_tasks * 10

        if completion_rate >= 80 and overdue_tasks == 0:
            forecast = "On Track"
        elif completion_rate >= 50:
            forecast = "Minor Delay Risk"
        else:
            forecast = "High Delay Risk"

        forecasts.append({

            "project_name": project["name"],
            "status": project["status"],
            "completion_rate": completion_rate,
            "overdue_tasks": overdue_tasks,
            "delay_risk": delay_risk,
            "forecast": forecast

        })

    conn.close()

    return render_template(
        "ai_schedule_forecasting.html",
        forecasts=forecasts
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
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    team_members = cursor.fetchall()

    workload_data = []

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
                tasks.assigned_to = %s
                OR task_team_members.team_member_id = %s
            )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        active_tasks = cursor.fetchone()["active_tasks"]

        utilisation = min(active_tasks * 10, 100)

        if utilisation >= 80:
            workload_status = "Overloaded"
            recommendation = "Reassign some tasks to available team members."

        elif utilisation >= 50:
            workload_status = "Balanced"
            recommendation = "Workload is manageable but should be monitored."

        else:
            workload_status = "Available"
            recommendation = "This team member can take on more work."

        workload_data.append({
            "name": member["name"],
            "role": member["role"],
            "active_tasks": active_tasks,
            "utilisation": utilisation,
            "workload_status": workload_status,
            "recommendation": recommendation
        })

    conn.close()

    return render_template(
        "ai_workload_balancer.html",
        workload_data=workload_data
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
        SELECT *
        FROM team_members
        WHERE user_id = %s
        ORDER BY name
    """, (
        session["user_id"],
    ))

    team_members = cursor.fetchall()

    optimisation_data = []

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
                tasks.assigned_to = %s
                OR task_team_members.team_member_id = %s
            )
        """, (
            session["user_id"],
            member["name"],
            member["id"]
        ))

        active_tasks = cursor.fetchone()["active_tasks"]

        utilisation = min(active_tasks * 10, 100)

        if utilisation >= 80:

            optimisation = "Reduce workload"
            action = "Move tasks away from this resource."

        elif utilisation >= 50:

            optimisation = "Maintain"
            action = "Current workload appears balanced."

        else:

            optimisation = "Increase workload"
            action = "Assign additional tasks to this resource."

        optimisation_data.append({

            "name": member["name"],
            "role": member["role"],
            "active_tasks": active_tasks,
            "utilisation": utilisation,
            "optimisation": optimisation,
            "action": action

        })

    conn.close()

    return render_template(
        "ai_resource_optimisation.html",
        optimisation_data=optimisation_data
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
            SUM(budget_amount) AS total_budget,
            SUM(actual_cost) AS total_actual
        FROM budgets
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    budget_data = cursor.fetchone()

    total_budget = float(budget_data["total_budget"] or 0)
    total_actual = float(budget_data["total_actual"] or 0)

    conn.close()

    if total_tasks > 0:
        completion_rate = round(
            (completed_tasks / total_tasks) * 100
        )
    else:
        completion_rate = 0

    portfolio_score = 100

    portfolio_score -= overdue_tasks * 8
    portfolio_score -= blocked_tasks * 8
    portfolio_score -= open_risks * 5
    portfolio_score -= open_issues * 4

    if total_budget > 0 and total_actual > total_budget:
        portfolio_score -= 15

    portfolio_score = max(
        0,
        min(100, portfolio_score)
    )

    if portfolio_score >= 75:
        prediction = "Healthy"
        recommendation = "Portfolio performance is strong. Continue current governance rhythm."

    elif portfolio_score >= 50:
        prediction = "Watch"
        recommendation = "Portfolio requires monitoring. Review risks, issues and budget pressure."

    else:
        prediction = "At Risk"
        recommendation = "Portfolio requires intervention. Escalate major delivery, risk and budget concerns."

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
        portfolio_score=portfolio_score,
        prediction=prediction,
        recommendation=recommendation
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

        if total_tasks > 0:
            completion_rate = round(
                (completed_tasks / total_tasks) * 100
            )
        else:
            completion_rate = 0

        if completion_rate >= 75 and open_risks == 0 and open_issues == 0:
            summary = "Project is performing well with strong delivery progress and no major governance concerns."
        elif overdue_tasks > 0 or blocked_tasks > 0:
            summary = "Project requires delivery attention due to overdue or blocked tasks."
        elif open_risks > 0 or open_issues > 0:
            summary = "Project has governance items that should be reviewed in the next project meeting."
        else:
            summary = "Project is stable but should continue to be monitored."

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
            "summary": summary
        })

    conn.close()

    return render_template(
        "ai_project_summary_generator.html",
        summaries=summaries
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
        SELECT COUNT(*) AS overdue_tasks
        FROM tasks
        JOIN projects
        ON tasks.project_id = projects.id
        WHERE projects.user_id = %s
        AND tasks.status != 'Completed'
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

    conn.close()

    recommendations = []

    if overdue_tasks > 0:
        recommendations.append(
            f"Review {overdue_tasks} overdue task(s) immediately."
        )

    if blocked_tasks > 0:
        recommendations.append(
            f"Escalate {blocked_tasks} blocked task(s)."
        )

    if open_risks > 0:
        recommendations.append(
            f"Review {open_risks} open risk(s)."
        )

    if open_issues > 0:
        recommendations.append(
            f"Review {open_issues} open issue(s)."
        )

    if not recommendations:
        recommendations.append(
            "Portfolio currently appears healthy."
        )

    return render_template(
        "ai_pm_copilot.html",
        total_projects=total_projects,
        overdue_tasks=overdue_tasks,
        open_risks=open_risks,
        open_issues=open_issues,
        blocked_tasks=blocked_tasks,
        recommendations=recommendations
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
        SELECT *
        FROM user_roles
        ORDER BY id DESC
    """)

    roles = cursor.fetchall()

    conn.close()

    return render_template(
        "user_roles.html",
        roles=roles
    )


@app.route("/add-user-role", methods=["GET", "POST"])
def add_user_role():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO user_roles
            (
                user_id,
                role,
                created_at
            )
            VALUES (%s,%s,%s)
        """, (
            request.form["user_id"],
            request.form["role"],
            str(datetime.now())
        ))

        conn.commit()
        conn.close()

        return redirect("/user-roles")

    return render_template(
        "add_user_role.html"
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
        SELECT *
        FROM permissions
        ORDER BY role, module
    """)

    permissions = cursor.fetchall()

    conn.close()

    return render_template(
        "permissions.html",
        permissions=permissions
    )


@app.route("/add-permission", methods=["GET", "POST"])
def add_permission():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO permissions
            (
                role,
                module,
                can_view,
                can_create,
                can_edit,
                can_delete
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            request.form["role"],
            request.form["module"],
            request.form.get("can_view") == "on",
            request.form.get("can_create") == "on",
            request.form.get("can_edit") == "on",
            request.form.get("can_delete") == "on"
        ))

        conn.commit()
        conn.close()

        return redirect("/permissions")

    return render_template(
        "add_permission.html"
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

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()["total_users"]

    cursor.execute("SELECT COUNT(*) AS total_projects FROM projects")
    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("SELECT COUNT(*) AS total_tasks FROM tasks")
    total_tasks = cursor.fetchone()["total_tasks"]

    cursor.execute("SELECT COUNT(*) AS total_risks FROM risks")
    total_risks = cursor.fetchone()["total_risks"]

    cursor.execute("SELECT COUNT(*) AS total_issues FROM issues")
    total_issues = cursor.fetchone()["total_issues"]

    cursor.execute("SELECT COUNT(*) AS total_roles FROM user_roles")
    total_roles = cursor.fetchone()["total_roles"]

    cursor.execute("SELECT COUNT(*) AS total_permissions FROM permissions")
    total_permissions = cursor.fetchone()["total_permissions"]

    cursor.execute("""
        SELECT *
        FROM audit_logs
        ORDER BY id DESC
        LIMIT 10
    """)

    recent_logs = cursor.fetchall()

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
        recent_logs=recent_logs
    )

@app.route("/admin-reset-password/<int:user_id>")
def admin_reset_password(user_id):

    if "user_id" not in session:
        return redirect("/login")

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
        RETURNING id, username, reset_token
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

    return f"""
    <h2>Password Reset Token Generated</h2>
    <p><strong>User:</strong> {updated_user['username']}</p>
    <p><strong>Token:</strong> {updated_user['reset_token']}</p>
    <p>
        <a href="/reset-password/{updated_user['reset_token']}">
            Open Reset Password Page
        </a>
    </p>
    """


@app.route(
    "/reset-password/<token>",
    methods=["GET", "POST"]
)
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

    if request.method == "POST":

        new_password = generate_password_hash(
            request.form["password"]
        )

        cursor.execute("""
            UPDATE users
            SET
                password = %s,
                reset_token = NULL,
                reset_token_created_at = NULL
            WHERE id = %s
        """, (
            new_password,
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
        SELECT *
        FROM email_notifications
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    notifications = cursor.fetchall()

    conn.close()

    return render_template(
        "email_notifications.html",
        notifications=notifications
    )


@app.route("/add-email-notification", methods=["GET", "POST"])
def add_email_notification():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO email_notifications
            (
                user_id,
                recipient_email,
                subject,
                message,
                status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form["recipient_email"],
            request.form["subject"],
            request.form["message"],
            "Draft",
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
        SELECT
            users.id,
            users.username,
            users.email,
            users.avatar_initials
        FROM users
        ORDER BY users.id DESC
    """)

    users = cursor.fetchall()

    conn.close()

    return render_template(
        "user_management.html",
        users=users
    )


@app.route("/user-invitations")
def user_invitations():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM user_invitations
        ORDER BY id DESC
    """)

    invitations = cursor.fetchall()

    conn.close()

    return render_template(
        "user_invitations.html",
        invitations=invitations
    )


@app.route(
    "/add-user-invitation",
    methods=["GET", "POST"]
)
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
                created_at
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (

            request.form["organisation_id"],
            request.form["workspace_id"],
            request.form["invited_email"],
            request.form["role"],
            "Pending",
            invitation_token,
            session["user_id"],
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
                avatar_initials = %s
            WHERE id = %s
        """, (
            request.form["username"],
            request.form["email"],
            request.form["avatar_initials"],
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

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM organisations
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    conn.close()

    return render_template(
        "organisations.html",
        organisations=organisations
    )


@app.route("/add-organisation", methods=["GET", "POST"])
def add_organisation():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        conn = get_db_connection()

        cursor = conn.cursor()

        trial_start_date = date.today()
        trial_end_date = date.today() + timedelta(days=14)

        cursor.execute("""
            INSERT INTO organisations
            (
                user_id,
                organisation_name,
                industry,
                plan,
                status,
                trial_start_date,
                trial_end_date,
                subscription_status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form["organisation_name"],
            request.form["industry"],
            request.form["plan"],
            request.form["status"],
            str(trial_start_date),
            str(trial_end_date),
            "Trial",
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/organisations")

    return render_template("add_organisation.html")

@app.route("/organisation-switcher")
def organisation_switcher():

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
        WHERE user_id = %s
        ORDER BY organisation_name
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    conn.close()

    return render_template(
        "organisation_switcher.html",
        organisations=organisations
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
        session.pop("workspace_id", None)

    return redirect("/")

@app.route(
    "/add-workspace-role",
    methods=["GET", "POST"]
)
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
        ORDER BY organisation_name
    """)

    organisations = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM workspaces
        ORDER BY workspace_name
    """)

    workspaces = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO user_roles
            (
                user_id,
                role,
                organisation_id,
                workspace_id,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s)
        """, (

            request.form["user_id"],
            request.form["role"],
            request.form["organisation_id"],
            request.form["workspace_id"],
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
        SELECT
            workspaces.*,
            organisations.organisation_name
        FROM workspaces
        LEFT JOIN organisations
        ON workspaces.organisation_id = organisations.id
        WHERE workspaces.user_id = %s
        ORDER BY workspaces.id DESC
    """, (
        session["user_id"],
    ))

    workspaces = cursor.fetchall()

    conn.close()

    return render_template(
        "workspaces.html",
        workspaces=workspaces
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
            INSERT INTO workspaces
            (
                user_id,
                organisation_id,
                workspace_name,
                workspace_type,
                owner,
                status,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form["organisation_id"],
            request.form["workspace_name"],
            request.form["workspace_type"],
            request.form["owner"],
            request.form["status"],
            str(date.today())
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

    return redirect("/")

@app.route("/workspace-switcher")
def workspace_switcher():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM workspaces
        WHERE user_id = %s
        ORDER BY workspace_name
    """, (
        session["user_id"],
    ))

    workspaces = cursor.fetchall()

    conn.close()

    return render_template(
        "workspace_switcher.html",
        workspaces=workspaces
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
        SELECT
            user_roles.*,
            users.username,
            organisations.organisation_name,
            workspaces.workspace_name
        FROM user_roles
        LEFT JOIN users
        ON user_roles.user_id = users.id
        LEFT JOIN organisations
        ON user_roles.organisation_id = organisations.id
        LEFT JOIN workspaces
        ON user_roles.workspace_id = workspaces.id
        ORDER BY user_roles.id DESC
    """)

    roles = cursor.fetchall()

    conn.close()

    return render_template(
        "workspace_roles.html",
        roles=roles
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
        ORDER BY organisation_name
    """)

    organisations = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM workspaces
        ORDER BY workspace_name
    """)

    workspaces = cursor.fetchall()

    if request.method == "POST":

        cursor.execute("""
            UPDATE user_roles
            SET
                user_id = %s,
                role = %s,
                organisation_id = %s,
                workspace_id = %s
            WHERE id = %s
        """, (
            request.form["user_id"],
            request.form["role"],
            request.form["organisation_id"],
            request.form["workspace_id"],
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

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT *
        FROM subscription_plans
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    plans = cursor.fetchall()

    conn.close()

    return render_template(
        "subscription_plans.html",
        plans=plans
    )

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
        return "Invalid or expired invitation"

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)
        avatar_initials = username[:2].upper()

        cursor.execute("""
            INSERT INTO users
            (
                username,
                email,
                password,
                avatar_initials
            )
            VALUES (%s,%s,%s,%s)
            RETURNING id
        """, (
            username,
            invitation["invited_email"],
            hashed_password,
            avatar_initials
        ))

        new_user = cursor.fetchone()
        new_user_id = new_user["id"]

        cursor.execute("""
                       INSERT INTO user_roles
                       (user_id,
                        role,
                        organisation_id,
                        workspace_id,
                        created_at)
                       VALUES (%s, %s, %s, %s, %s)
                       """, (
                           new_user_id,
                           invitation["role"],
                           invitation["organisation_id"],
                           invitation["workspace_id"],
                           str(datetime.now())
                       ))

        cursor.execute("""
            UPDATE user_invitations
            SET status = 'Accepted'
            WHERE id = %s
        """, (
            invitation["id"],
        ))

        conn.commit()
        conn.close()

        return redirect("/login")

    conn.close()

    return render_template(
        "accept_invitation.html",
        invitation=invitation
    )


@app.route("/add-subscription-plan", methods=["GET", "POST"])
def add_subscription_plan():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()

        cursor = conn.cursor()

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
            request.form["plan_name"],
            request.form["price"],
            request.form["billing_cycle"],
            request.form["max_projects"],
            request.form["max_users"],
            request.form["features"],
            request.form["status"],
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

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT
            customer_subscriptions.*,
            organisations.organisation_name,
            subscription_plans.plan_name
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

    conn.close()

    return render_template(
        "customer_subscriptions.html",
        subscriptions=subscriptions
    )


@app.route("/add-customer-subscription", methods=["GET", "POST"])
def add_customer_subscription():

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
        FROM organisations
        WHERE user_id = %s
        ORDER BY organisation_name
    """, (
        session["user_id"],
    ))

    organisations = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM subscription_plans
        WHERE user_id = %s
        ORDER BY plan_name
    """, (
        session["user_id"],
    ))

    plans = cursor.fetchall()

    if request.method == "POST":

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
            request.form["organisation_id"],
            request.form["plan_id"],
            request.form["start_date"],
            request.form["end_date"],
            request.form["status"],
            request.form["payment_status"],
            str(date.today())
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

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

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

    for organisation in organisations:

        days_remaining = 0

        if organisation["trial_end_date"]:

            try:

                trial_end = datetime.strptime(
                    organisation["trial_end_date"],
                    "%Y-%m-%d"
                ).date()

                days_remaining = (
                    trial_end - today
                ).days

            except:
                pass

        organisation["days_remaining"] = days_remaining

    conn.close()

    return render_template(
        "subscription_status.html",
        organisations=organisations
    )

@app.route("/upgrade-plan/<int:organisation_id>")
def upgrade_plan(organisation_id):

    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "upgrade_plan.html",
        organisation_id=organisation_id
    )

@app.route("/process-upgrade/<int:organisation_id>/<plan>")
def process_upgrade(organisation_id, plan):

    if "user_id" not in session:
        return redirect("/login")

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
            subscription_status = %s
        WHERE id = %s
        AND user_id = %s
    """, (
        plan,
        "Active",
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

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

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

        plan_data.append({
            "organisation": organisation,
            "max_projects": limits["max_projects"],
            "max_users": limits["max_users"],
            "max_workspaces": limits["max_workspaces"],
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
        SELECT
            billing_history.*,
            organisations.organisation_name
        FROM billing_history
        LEFT JOIN organisations
        ON billing_history.organisation_id = organisations.id
        WHERE billing_history.user_id = %s
        ORDER BY billing_date DESC
    """, (
        session["user_id"],
    ))

    billing_records = cursor.fetchall()

    conn.close()

    return render_template(
        "billing_history.html",
        billing_records=billing_records
    )

@app.route(
    "/add-billing-history",
    methods=["GET", "POST"]
)
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

    if request.method == "POST":

        cursor.execute("""
            INSERT INTO billing_history
            (
                user_id,
                organisation_id,
                plan,
                amount,
                status,
                reference_number,
                billing_date,
                created_at
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (

            session["user_id"],
            request.form["organisation_id"],
            request.form["plan"],
            request.form["amount"],
            request.form["status"],
            request.form["reference_number"],
            request.form["billing_date"],
            str(date.today())

        ))

        conn.commit()
        conn.close()

        return redirect("/billing-history")

    conn.close()

    return render_template(
        "add_billing_history.html",
        organisations=organisations
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
        SELECT
            invoices.*,
            organisations.organisation_name
        FROM invoices
        LEFT JOIN organisations
        ON invoices.organisation_id = organisations.id
        WHERE invoices.user_id = %s
        ORDER BY invoice_date DESC
    """, (
        session["user_id"],
    ))

    invoices_list = cursor.fetchall()

    conn.close()

    return render_template(
        "invoices.html",
        invoices_list=invoices_list
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
            INSERT INTO invoices
            (
                user_id,
                organisation_id,
                invoice_number,
                plan,
                amount,
                status,
                invoice_date,
                created_at
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form["organisation_id"],
            request.form["invoice_number"],
            request.form["plan"],
            request.form["amount"],
            request.form["status"],
            request.form["invoice_date"],
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
        SELECT *
        FROM notification_settings
        WHERE user_id = %s
        ORDER BY id DESC
    """, (
        session["user_id"],
    ))

    settings = cursor.fetchall()

    conn.close()

    return render_template(
        "notification_settings.html",
        settings=settings
    )


@app.route("/add-notification-setting", methods=["GET", "POST"])
def add_notification_setting():

    if "user_id" not in session:
        return redirect("/login")

    if not has_permission("Admin", "create"):
        return "Access denied"

    if request.method == "POST":

        conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO notification_settings
            (
                user_id,
                notification_type,
                channel,
                enabled,
                frequency,
                created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            request.form["notification_type"],
            request.form["channel"],
            request.form["enabled"],
            request.form["frequency"],
            str(date.today())
        ))

        conn.commit()
        conn.close()

        return redirect("/notification-settings")

    return render_template("add_notification_setting.html")

@app.route("/usage-analytics")
def usage_analytics():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cursor.execute("""
        SELECT COUNT(*) AS total_organisations
        FROM organisations
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_organisations = cursor.fetchone()["total_organisations"]

    cursor.execute("""
        SELECT COUNT(*) AS total_workspaces
        FROM workspaces
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_workspaces = cursor.fetchone()["total_workspaces"]

    cursor.execute("""
        SELECT COUNT(*) AS total_projects
        FROM projects
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_projects = cursor.fetchone()["total_projects"]

    cursor.execute("""
        SELECT COUNT(*) AS total_users
        FROM user_invitations
        WHERE invited_by = %s
    """, (
        session["user_id"],
    ))

    total_users = cursor.fetchone()["total_users"]

    cursor.execute("""
        SELECT COALESCE(SUM(usage_count),0) AS total_ai_usage
        FROM ai_usage
        WHERE user_id = %s
    """, (
        session["user_id"],
    ))

    total_ai_usage = cursor.fetchone()["total_ai_usage"]

    conn.close()

    return render_template(
        "usage_analytics.html",
        total_organisations=total_organisations,
        total_workspaces=total_workspaces,
        total_projects=total_projects,
        total_users=total_users,
        total_ai_usage=total_ai_usage
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

        if open_risks >= 3 or open_issues >= 3:
            portfolio_stage = "At Risk"
        elif project_status in grouped_projects:
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
        workflow_alerts=workflow_alerts
    )

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