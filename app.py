import os
import hashlib
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session

# ── Load .env if present ──────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL")  # Set this for Supabase/PostgreSQL
USE_POSTGRES  = bool(DATABASE_URL)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fitcore_dbms_secret_2024")

# ── DB abstraction: returns a connection + cursor factory ─────
def get_db():
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect("fitness.db")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

def fetchall(cursor):
    """Return list of dict-like rows regardless of DB backend."""
    if USE_POSTGRES:
        return cursor.fetchall()
    return cursor.fetchall()

def placeholder():
    """SQL parameter placeholder: %s for postgres, ? for sqlite."""
    return "%s" if USE_POSTGRES else "?"

PH = None  # set after app context

def ph():
    return "%s" if USE_POSTGRES else "?"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ── Schema + seed ─────────────────────────────────────────────
def init_db():
    conn = get_db()
    c = conn.cursor()
    P = ph()

    if USE_POSTGRES:
        c.execute('''CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            age INTEGER,
            height REAL,
            weight REAL,
            fitness_level TEXT DEFAULT 'Beginner',
            goal TEXT DEFAULT 'General Fitness',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS workouts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            exercise_name TEXT NOT NULL,
            duration INTEGER,
            calories_burned REAL,
            workout_date DATE,
            notes TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS nutrition (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            meal_name TEXT NOT NULL,
            calories REAL,
            protein REAL,
            carbs REAL,
            fats REAL,
            meal_date DATE
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS goals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            goal_type TEXT NOT NULL,
            target_value REAL,
            current_value REAL DEFAULT 0,
            deadline DATE,
            status TEXT DEFAULT 'Active'
        )''')
    else:
        c.execute('''CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            age INTEGER,
            height REAL,
            weight REAL,
            fitness_level TEXT DEFAULT 'Beginner',
            goal TEXT DEFAULT 'General Fitness',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            duration INTEGER,
            calories_burned REAL,
            workout_date TEXT,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES accounts(id) ON DELETE CASCADE
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS nutrition (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            meal_name TEXT NOT NULL,
            calories REAL,
            protein REAL,
            carbs REAL,
            fats REAL,
            meal_date TEXT,
            FOREIGN KEY (user_id) REFERENCES accounts(id) ON DELETE CASCADE
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            goal_type TEXT NOT NULL,
            target_value REAL,
            current_value REAL DEFAULT 0,
            deadline TEXT,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (user_id) REFERENCES accounts(id) ON DELETE CASCADE
        )''')

    # Seed default owner + sample member
    c.execute(f"SELECT COUNT(*) FROM accounts WHERE role='owner'")
    if c.fetchone()[0] == 0:
        c.execute(f"INSERT INTO accounts (name, email, password, role) VALUES ({P},{P},{P},{P})",
                  ('Gym Owner', 'owner@fitcore.com', hash_password('owner123'), 'owner'))
        c.execute(f"INSERT INTO accounts (name,email,password,role,age,height,weight,fitness_level,goal) VALUES ({P},{P},{P},{P},{P},{P},{P},{P},{P})",
                  ('Alex Johnson','alex@example.com',hash_password('alex123'),'member',25,175,78,'Intermediate','Weight Loss'))
        # Get the new member's id
        if USE_POSTGRES:
            c.execute("SELECT id FROM accounts WHERE email=%s", ('alex@example.com',))
        else:
            c.execute("SELECT id FROM accounts WHERE email=?", ('alex@example.com',))
        uid = c.fetchone()[0]
        c.execute(f"INSERT INTO workouts (user_id,exercise_name,duration,calories_burned,workout_date,notes) VALUES ({P},{P},{P},{P},{P},{P})",
                  (uid,'Running',45,450,'2024-01-15','Morning run'))
        c.execute(f"INSERT INTO nutrition (user_id,meal_name,calories,protein,carbs,fats,meal_date) VALUES ({P},{P},{P},{P},{P},{P},{P})",
                  (uid,'Grilled Chicken & Rice',520,42,55,8,'2024-01-15'))
        c.execute(f"INSERT INTO goals (user_id,goal_type,target_value,current_value,deadline,status) VALUES ({P},{P},{P},{P},{P},{P})",
                  (uid,'Target Weight (kg)',70,78,'2024-06-01','Active'))

    conn.commit()
    conn.close()

# Helper: run a query and return rows as list of dicts
def query(sql, params=()):
    conn = get_db()
    if USE_POSTGRES:
        import psycopg2.extras
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conn.row_factory = __import__('sqlite3').Row
        c = conn.cursor()
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None

def execute(sql, params=()):
    conn = get_db()
    c = conn.cursor()
    c.execute(sql, params)
    conn.commit()
    conn.close()

def execute_returning(sql, params=()):
    """For INSERT ... RETURNING id (postgres) or lastrowid (sqlite)."""
    conn = get_db()
    c = conn.cursor()
    c.execute(sql, params)
    if USE_POSTGRES:
        row = c.fetchone()
        last_id = row[0] if row else None
    else:
        last_id = c.lastrowid
    conn.commit()
    conn.close()
    return last_id

# ── Auth decorators ────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('landing'))
        return f(*args, **kwargs)
    return decorated

def owner_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'owner':
            flash('Access denied.', 'error')
            return redirect(url_for('member_dashboard'))
        return f(*args, **kwargs)
    return decorated

P = ph()  # global placeholder

# ── Landing & Auth ─────────────────────────────────────────────
@app.route('/')
def landing():
    if 'user_id' in session:
        return redirect(url_for('owner_dashboard' if session['role'] == 'owner' else 'member_dashboard'))
    return render_template('landing.html')

@app.route('/login/<role>', methods=['GET','POST'])
def login(role):
    if request.method == 'POST':
        user = query_one(f"SELECT * FROM accounts WHERE email={P} AND password={P} AND role={P}",
                         (request.form['email'], hash_password(request.form['password']), role))
        if user:
            session['user_id']   = user['id']
            session['user_name'] = user['name']
            session['role']      = user['role']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('owner_dashboard' if role == 'owner' else 'member_dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html', role=role)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        existing = query_one(f"SELECT id FROM accounts WHERE email={P}", (request.form['email'],))
        if existing:
            flash('Email already registered.', 'error')
        else:
            execute(f"""INSERT INTO accounts (name,email,password,role,age,height,weight,fitness_level,goal)
                        VALUES ({P},{P},{P},{P},{P},{P},{P},{P},{P})""",
                    (request.form['name'], request.form['email'], hash_password(request.form['password']),
                     'member', request.form['age'], request.form['height'], request.form['weight'],
                     request.form['fitness_level'], request.form['goal']))
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login', role='member'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('landing'))

# ── OWNER DASHBOARD ────────────────────────────────────────────
@app.route('/owner/dashboard')
@login_required
@owner_required
def owner_dashboard():
    members       = query(f"SELECT * FROM accounts WHERE role='member' ORDER BY created_at DESC")
    total_members = len(members)
    total_workouts= query_one("SELECT COUNT(*) as c FROM workouts")['c']
    total_goals   = query_one(f"SELECT COUNT(*) as c FROM goals WHERE status='Active'")['c']
    total_calories= query_one("SELECT COALESCE(SUM(calories_burned),0) as c FROM workouts")['c']
    return render_template('owner_dashboard.html', members=members,
                           total_members=total_members, total_workouts=total_workouts,
                           total_goals=total_goals, total_calories=int(total_calories))

@app.route('/owner/member/<int:mid>')
@login_required
@owner_required
def owner_view_member(mid):
    member   = query_one(f"SELECT * FROM accounts WHERE id={P} AND role='member'", (mid,))
    workouts = query(f"SELECT * FROM workouts WHERE user_id={P} ORDER BY workout_date DESC", (mid,))
    nutrition= query(f"SELECT * FROM nutrition WHERE user_id={P} ORDER BY meal_date DESC", (mid,))
    goals    = query(f"SELECT * FROM goals WHERE user_id={P}", (mid,))
    bmi      = round(member['weight']/((member['height']/100)**2),1) if member and member['height'] and member['weight'] else None
    burned   = query_one(f"SELECT COALESCE(SUM(calories_burned),0) as c FROM workouts WHERE user_id={P}", (mid,))['c']
    consumed = query_one(f"SELECT COALESCE(SUM(calories),0) as c FROM nutrition WHERE user_id={P}", (mid,))['c']
    return render_template('owner_member_view.html', member=member, workouts=workouts,
                           nutrition=nutrition, goals=goals, bmi=bmi,
                           total_cal_burned=int(burned), total_cal_consumed=int(consumed))

@app.route('/owner/member/delete/<int:mid>')
@login_required
@owner_required
def owner_delete_member(mid):
    execute(f"DELETE FROM accounts WHERE id={P} AND role='member'", (mid,))
    flash('Member deleted.', 'success')
    return redirect(url_for('owner_dashboard'))

# ── MEMBER DASHBOARD ───────────────────────────────────────────
@app.route('/member/dashboard')
@login_required
def member_dashboard():
    uid      = session['user_id']
    user     = query_one(f"SELECT * FROM accounts WHERE id={P}", (uid,))
    workouts = query(f"SELECT * FROM workouts WHERE user_id={P} ORDER BY workout_date DESC LIMIT 5", (uid,))
    nutrition= query(f"SELECT * FROM nutrition WHERE user_id={P} ORDER BY meal_date DESC LIMIT 5", (uid,))
    goals    = query(f"SELECT * FROM goals WHERE user_id={P}", (uid,))
    bmi      = round(user['weight']/((user['height']/100)**2),1) if user['height'] and user['weight'] else None
    burned   = query_one(f"SELECT COALESCE(SUM(calories_burned),0) as c FROM workouts WHERE user_id={P}", (uid,))['c']
    consumed = query_one(f"SELECT COALESCE(SUM(calories),0) as c FROM nutrition WHERE user_id={P}", (uid,))['c']
    wcount   = query_one(f"SELECT COUNT(*) as c FROM workouts WHERE user_id={P}", (uid,))['c']
    return render_template('member_dashboard.html', user=user, workouts=workouts, nutrition=nutrition,
                           goals=goals, bmi=bmi, total_cal_burned=int(burned),
                           total_cal_consumed=int(consumed), workout_count=wcount)

# ── WORKOUTS CRUD ──────────────────────────────────────────────
@app.route('/member/workouts')
@login_required
def member_workouts():
    uid = session['user_id']
    workouts = query(f"SELECT * FROM workouts WHERE user_id={P} ORDER BY workout_date DESC", (uid,))
    return render_template('member_workouts.html', workouts=workouts)

@app.route('/member/workouts/add', methods=['POST'])
@login_required
def member_add_workout():
    uid = session['user_id']
    execute(f"INSERT INTO workouts (user_id,exercise_name,duration,calories_burned,workout_date,notes) VALUES ({P},{P},{P},{P},{P},{P})",
            (uid, request.form['exercise_name'], request.form['duration'],
             request.form['calories_burned'], request.form['workout_date'], request.form.get('notes','')))
    flash('Workout logged!', 'success')
    return redirect(url_for('member_workouts'))

@app.route('/member/workouts/edit/<int:wid>', methods=['GET','POST'])
@login_required
def member_edit_workout(wid):
    uid     = session['user_id']
    workout = query_one(f"SELECT * FROM workouts WHERE id={P} AND user_id={P}", (wid, uid))
    if not workout:
        flash('Not found.', 'error'); return redirect(url_for('member_workouts'))
    if request.method == 'POST':
        execute(f"UPDATE workouts SET exercise_name={P},duration={P},calories_burned={P},workout_date={P},notes={P} WHERE id={P} AND user_id={P}",
                (request.form['exercise_name'], request.form['duration'], request.form['calories_burned'],
                 request.form['workout_date'], request.form.get('notes',''), wid, uid))
        flash('Workout updated!', 'success')
        return redirect(url_for('member_workouts'))
    return render_template('member_workout_form.html', workout=workout)

@app.route('/member/workouts/delete/<int:wid>')
@login_required
def member_delete_workout(wid):
    uid = session['user_id']
    execute(f"DELETE FROM workouts WHERE id={P} AND user_id={P}", (wid, uid))
    flash('Workout deleted.', 'success')
    return redirect(url_for('member_workouts'))

# ── NUTRITION CRUD ─────────────────────────────────────────────
@app.route('/member/nutrition')
@login_required
def member_nutrition():
    uid   = session['user_id']
    meals = query(f"SELECT * FROM nutrition WHERE user_id={P} ORDER BY meal_date DESC", (uid,))
    return render_template('member_nutrition.html', meals=meals)

@app.route('/member/nutrition/add', methods=['POST'])
@login_required
def member_add_nutrition():
    uid = session['user_id']
    execute(f"INSERT INTO nutrition (user_id,meal_name,calories,protein,carbs,fats,meal_date) VALUES ({P},{P},{P},{P},{P},{P},{P})",
            (uid, request.form['meal_name'], request.form['calories'], request.form['protein'],
             request.form['carbs'], request.form['fats'], request.form['meal_date']))
    flash('Meal logged!', 'success')
    return redirect(url_for('member_nutrition'))

@app.route('/member/nutrition/edit/<int:nid>', methods=['GET','POST'])
@login_required
def member_edit_nutrition(nid):
    uid  = session['user_id']
    meal = query_one(f"SELECT * FROM nutrition WHERE id={P} AND user_id={P}", (nid, uid))
    if not meal:
        flash('Not found.', 'error'); return redirect(url_for('member_nutrition'))
    if request.method == 'POST':
        execute(f"UPDATE nutrition SET meal_name={P},calories={P},protein={P},carbs={P},fats={P},meal_date={P} WHERE id={P} AND user_id={P}",
                (request.form['meal_name'], request.form['calories'], request.form['protein'],
                 request.form['carbs'], request.form['fats'], request.form['meal_date'], nid, uid))
        flash('Meal updated!', 'success')
        return redirect(url_for('member_nutrition'))
    return render_template('member_nutrition_form.html', meal=meal)

@app.route('/member/nutrition/delete/<int:nid>')
@login_required
def member_delete_nutrition(nid):
    uid = session['user_id']
    execute(f"DELETE FROM nutrition WHERE id={P} AND user_id={P}", (nid, uid))
    flash('Meal deleted.', 'success')
    return redirect(url_for('member_nutrition'))

# ── GOALS CRUD ─────────────────────────────────────────────────
@app.route('/member/goals')
@login_required
def member_goals():
    uid   = session['user_id']
    goals = query(f"SELECT * FROM goals WHERE user_id={P} ORDER BY deadline ASC", (uid,))
    return render_template('member_goals.html', goals=goals)

@app.route('/member/goals/add', methods=['POST'])
@login_required
def member_add_goal():
    uid = session['user_id']
    execute(f"INSERT INTO goals (user_id,goal_type,target_value,current_value,deadline,status) VALUES ({P},{P},{P},{P},{P},{P})",
            (uid, request.form['goal_type'], request.form['target_value'],
             request.form['current_value'], request.form['deadline'], request.form['status']))
    flash('Goal added!', 'success')
    return redirect(url_for('member_goals'))

@app.route('/member/goals/edit/<int:gid>', methods=['GET','POST'])
@login_required
def member_edit_goal(gid):
    uid  = session['user_id']
    goal = query_one(f"SELECT * FROM goals WHERE id={P} AND user_id={P}", (gid, uid))
    if not goal:
        flash('Not found.', 'error'); return redirect(url_for('member_goals'))
    if request.method == 'POST':
        execute(f"UPDATE goals SET goal_type={P},target_value={P},current_value={P},deadline={P},status={P} WHERE id={P} AND user_id={P}",
                (request.form['goal_type'], request.form['target_value'], request.form['current_value'],
                 request.form['deadline'], request.form['status'], gid, uid))
        flash('Goal updated!', 'success')
        return redirect(url_for('member_goals'))
    return render_template('member_goal_form.html', goal=goal)

@app.route('/member/goals/delete/<int:gid>')
@login_required
def member_delete_goal(gid):
    uid = session['user_id']
    execute(f"DELETE FROM goals WHERE id={P} AND user_id={P}", (gid, uid))
    flash('Goal deleted.', 'success')
    return redirect(url_for('member_goals'))

# ── PROFILE ────────────────────────────────────────────────────
@app.route('/member/profile', methods=['GET','POST'])
@login_required
def member_profile():
    uid  = session['user_id']
    if request.method == 'POST':
        execute(f"UPDATE accounts SET name={P},age={P},height={P},weight={P},fitness_level={P},goal={P} WHERE id={P}",
                (request.form['name'], request.form['age'], request.form['height'],
                 request.form['weight'], request.form['fitness_level'], request.form['goal'], uid))
        session['user_name'] = request.form['name']
        flash('Profile updated!', 'success')
    user = query_one(f"SELECT * FROM accounts WHERE id={P}", (uid,))
    return render_template('member_profile.html', user=user)

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    debug = not USE_POSTGRES
    app.run(host='0.0.0.0', port=port, debug=debug)
