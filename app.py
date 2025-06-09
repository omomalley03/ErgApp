from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import json, os, uuid
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key'
login_manager = LoginManager(app)
login_manager.login_view = 'login'

USERS_FILE = 'users.json'
WORKOUTS_FILE = 'workouts.json'
GROUPS_FILE = 'groups.json'


# -------------------- User Class --------------------

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) if user_id in load_users() else None


# -------------------- Helpers --------------------

def load_users():
    if not os.path.exists(USERS_FILE) or os.stat(USERS_FILE).st_size == 0:
        return {}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)


def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def load_workouts():
    if not os.path.exists(WORKOUTS_FILE) or os.stat(WORKOUTS_FILE).st_size == 0:
        return {}
    with open(WORKOUTS_FILE, 'r') as f:
        return json.load(f)


def save_workouts(workouts):
    with open(WORKOUTS_FILE, 'w') as f:
        json.dump(workouts, f, indent=4)

def load_groups():
    if not os.path.exists(GROUPS_FILE) or os.stat(GROUPS_FILE).st_size == 0:
        return {}
    with open(GROUPS_FILE, 'r') as f:
        data = json.load(f)
        return data if isinstance(data, dict) else {}

def save_groups(groups):
    with open(GROUPS_FILE, 'w') as f:
        json.dump(groups, f, indent=2)

def get_user_groups(user_id):
    groups = load_groups()
    user_groups = []
    for group_id, group in groups.items():
        if user_id in group.get('members', []):
            user_groups.append((group_id, group.get('name', 'Unnamed Group')))
    return user_groups

def add_workout_to_group(group_id, workout_data):
    groups = load_groups()
    if group_id in groups and current_user.id in groups[group_id]['members']:
        groups[group_id]['workouts'].append(workout_data)
        save_groups(groups)
        return True
    return False


# -------------------- Routes --------------------

@app.route('/')
@login_required
def index():
    x = 1
    workouts = load_workouts().get(current_user.id, [])
    user_groups = get_user_groups(current_user.id)
    return render_template('index.html', workouts=workouts, user_groups=user_groups, username = current_user.id)



@app.route('/add', methods=['POST'])
@login_required

def add_workout():
    workout = {
        'date': request.form['date'],
        'duration': request.form['duration'],
        'distance_m': int(request.form['distance_m']),
        'avg_pace': request.form['avg_pace'],
        'stroke_rate': request.form['stroke_rate'],
        'notes': request.form['notes']
    }

    all_workouts = load_workouts()
    user_workouts = all_workouts.get(current_user.id, [])
    user_workouts.append(workout)
    all_workouts[current_user.id] = user_workouts
    save_workouts(all_workouts)
    return redirect('/')

    # Optional: sync to group if specified
    group_id = request.form.get('group_id')
    if group_id:
        workout_with_user = dict(workout)  # Copy workout data
        workout_with_user['user'] = current_user.id
        add_workout_to_group(group_id, workout_with_user)

    return redirect('/')




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = load_users()
        username = request.form['username']
        password = request.form['password']
        if username in users and check_password_hash(users[username], password):
            login_user(User(username))
            return redirect('/')
        return "Invalid credentials", 401
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        users = load_users()
        username = request.form['username']
        password = request.form['password']
        if username in users:
            return "User already exists", 400
        users[username] = generate_password_hash(password)
        save_users(users)
        return redirect('/login')
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')


@app.route('/create_group', methods=['GET', 'POST'])
@login_required
def create_group():
    if request.method == 'POST':
        group_name = request.form.get('group_name')
        if not group_name:
            flash("Group name is required.")
            return redirect(url_for('create_group'))

        groups = load_groups()
        new_id = str(uuid.uuid4())
        groups[new_id] = {
            'name': group_name,
            'members': [current_user.id],
            'workouts': []
        }
        save_groups(groups)
        flash(f"Group '{group_name}' created!")
        return redirect(url_for('groups_dashboard'))
    # GET
    return '''
    <form method="post">
        Group Name: <input name="group_name" type="text" required>
        <input type="submit" value="Create Group">
    </form>
    '''

@app.route('/join_group', methods=['GET', 'POST'])
@login_required
def join_group():
    if request.method == 'POST':
        group_id = request.form.get('group_id')
        groups = load_groups()
        if group_id not in groups:
            flash("Group ID not found.")
            return redirect(url_for('join_group'))
        if current_user.id in groups[group_id]['members']:
            flash("You are already a member of this group.")
            return redirect(url_for('groups_dashboard'))

        groups[group_id]['members'].append(current_user.id)
        save_groups(groups)
        flash("Joined group successfully!")
        return redirect(url_for('groups_dashboard'))

    # GET
    return '''
    <form method="post">
        Group ID: <input name="group_id" type="text" required>
        <input type="submit" value="Join Group">
    </form>
    '''


@app.route('/groups', methods=['GET', 'POST'])
@login_required
def groups_dashboard():

    # find the groups this user is a part of already
    groups = load_groups()
    user_groups = get_user_groups(current_user.id)

    # if a form is filled out to join a group
    if request.method == 'POST':
        group_id = request.form.get('group_id')
        groups = load_groups()
        if group_id not in groups:
            flash("Group ID not found.")
            return redirect(url_for('groups_dashboard'))
        if current_user.id in groups[group_id]['members']:
            flash("You are already a member of this group.")
            return redirect(url_for('groups_dashboard'))

        groups[group_id]['members'].append(current_user.id)
        save_groups(groups)
        flash("Joined group successfully!")
        return redirect(url_for('groups_dashboard'))

    return render_template('groups.html',user_groups=user_groups)



@app.route('/groups/<group_id>')
@login_required
def group_workouts(group_id):
    groups = load_groups()
    group = groups.get(group_id)
    if not group or current_user.id not in group['members']:
        return "Group not found or access denied", 404

    html = f"<h2>{group['name']} Workouts</h2><ul>"
    for w in group['workouts']:
        html += f"<li>{w['user']} - {w['date']} - {w['distance_m']}m - {w['duration']} - {w.get('notes','')}</li>"
    html += "</ul>"
    html += '<a href="/groups">Back to Groups</a>'
    return html

@app.route('/training-plan')
@login_required
def trainingplan():
    return render_template('training-plan.html',user=current_user.id)

if __name__ == '__main__':
    app.run(debug=True)

