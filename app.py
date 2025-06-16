from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import MySQLdb.cursors

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# Configure MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # Add your MySQL password if needed
app.config['MYSQL_DB'] = 'quiz_master_db'
mysql = MySQL(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_id, email, role):
        self.id = int(user_id)  # Ensure ID is an integer
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, email, role FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()
        cur.close()
        if user:
            return User(user_id=user[0], email=user[1], role=user[2])
    except Exception as e:
        print(f"Error in load_user: {e}")
    return None

@app.route('/')
def home():
    return render_template('index.html')

# ✅ User Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        qualification = request.form.get('qualification')
        dob = request.form.get('dob')

        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO users (fullname, email, password, qualification, dob, role) VALUES (%s, %s, %s, %s, %s, %s)", 
                        (fullname, email, password, qualification, dob, 'user'))
            mysql.connection.commit()
            cur.close()
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash("Error in registration", "danger")
            print(f"Error in register: {e}")
    
    return render_template('register.html')

# ✅ User Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, email, role FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()

        if user:
            login_user(User(user_id=user[0], email=user[1], role=user[2]))
            flash("Login successful!", "success")
            return redirect(url_for('user_dashboard' if user[2] != 'admin' else 'admin_dashboard'))
        else:
            flash("Invalid credentials", "danger")

    return render_template('login.html')

# ✅ User Dashboard (Updated)
@app.route('/user_dashboard')
@login_required
def user_dashboard():
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT s.id, s.subject_name 
            FROM subjects s
            JOIN chapters c ON s.id = c.subject_id
            JOIN questions q ON c.id = q.chapter_id
            GROUP BY s.id, s.subject_name
        """)
        subjects = cur.fetchall()
        cur.close()
        return render_template('user_dashboard.html', subjects=subjects)
    except Exception as e:
        flash("Error fetching subjects", "danger")
        print(f"Error in user_dashboard: {e}")
        return redirect(url_for('home'))

# ✅ Choose Subject Route
@app.route('/choose_subject', methods=['POST'])
@login_required
def choose_subject():
    subject_id = request.form.get('subject_id')
    if not subject_id:
        flash("Please select a subject.", "warning")
        return redirect(url_for('user_dashboard'))
    
    return redirect(url_for('select_chapter', subject_id=subject_id))

# ✅ Fetch Chapters for a Subject (AJAX Call)
@app.route('/get_chapters/<int:subject_id>')
@login_required
def get_chapters(subject_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, chapter_name FROM chapters WHERE subject_id = %s", (subject_id,))
        chapters = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]
        cur.close()
        return {'chapters': chapters}
    except Exception as e:
        print(f"❌ Error fetching chapters: {e}")
        return {'chapters': []}


# ✅ Select Chapter

@app.route('/select_chapter/<int:subject_id>')
@login_required
def select_chapter(subject_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, chapter_name FROM chapters WHERE subject_id = %s", (subject_id,))
        chapters = cur.fetchall()
        cur.close()

        if not chapters:
            flash("No chapters available for this subject.", "warning")
            return redirect(url_for('user_dashboard'))

        return render_template('select_chapter.html', chapters=chapters, subject_id=subject_id)

    except Exception as e:
        flash("Error fetching chapters", "danger")
        print(f"❌ Error in select_chapter: {e}")
        return redirect(url_for('user_dashboard'))


# ✅ Start Quiz

@app.route('/start_quiz/<int:chapter_id>')
@login_required
def start_quiz(chapter_id):
    try:
        print(f"🔍 Starting quiz for chapter_id: {chapter_id}")  # Debug print

        cur = mysql.connection.cursor()

        # Fetch chapter name and subject ID
        cur.execute("SELECT chapter_name, subject_id FROM chapters WHERE id = %s", (chapter_id,))
        chapter = cur.fetchone()

        if not chapter:
            flash("Chapter not found.", "danger")
            return redirect(url_for('user_dashboard'))

        chapter_name, subject_id = chapter  # Unpacking tuple

        # Fetch questions for the selected chapter
        cur.execute("""
            SELECT id, question_text, option_a, option_b, option_c, option_d 
            FROM questions 
            WHERE chapter_id = %s 
            LIMIT 10
        """, (chapter_id,))
        questions = cur.fetchall()

        print(f"✅ Fetched {len(questions)} questions for chapter_id {chapter_id}")  # Debug print

        cur.close()

        if not questions:
            flash("No questions available for this chapter.", "warning")
            return redirect(url_for('user_dashboard'))

        return render_template(
            'quiz.html', 
            questions=questions, 
            chapter_name=chapter_name, 
            chapter_id=chapter_id, 
            subject_id=subject_id
        )

    except Exception as e:
        flash("Error loading quiz", "danger")
        print(f"❌ Error in start_quiz: {e}")
        return redirect(url_for('user_dashboard'))



# ✅ Submit Quiz - Grading Across All Chapters
@app.route('/submit_quiz/<int:subject_id>/<int:chapter_id>', methods=['POST'])
@login_required
def submit_quiz(subject_id, chapter_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, correct_option FROM questions 
            WHERE chapter_id = %s
        """, (chapter_id,))
        correct_answers = {str(row[0]): row[1] for row in cur.fetchall()}
        cur.close()

        # Calculate user score
        user_score = sum(1 for q_id, correct in correct_answers.items() if request.form.get(q_id) == correct)

        # Store score in database
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO scores (user_id, subject_id, chapter_id, score) VALUES (%s, %s, %s, %s)",
                    (current_user.id, subject_id, chapter_id, user_score))
        mysql.connection.commit()
        cur.close()

        return render_template('score.html', score=user_score)

    except Exception as e:
        flash("Error submitting quiz", "danger")
        print(f"❌ Error in submit_quiz: {e}")
        return redirect(url_for('user_dashboard'))



# ✅ View Scores
@app.route('/view_scores')
@login_required
def view_scores():
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT s.id, c.chapter_name, s.score 
            FROM scores s 
            JOIN chapters c ON s.chapter_id = c.id 
            WHERE s.user_id = %s
        """, (current_user.id,))
        scores = cur.fetchall()
        cur.close()
        return render_template('view_scores.html', scores=scores)
    except Exception as e:
        flash("Error fetching scores", "danger")
        print(f"Error in view_scores: {e}")
        return redirect(url_for('user_dashboard'))



# ✅ Admin Dashboard
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash("Access Denied!", "danger")
        return redirect(url_for('home'))  
    return render_template('admin_dashboard.html')

# ✅ Add and Delete Subject
@app.route('/add_subject', methods=['GET', 'POST'])
def add_subject():
    if current_user.role != 'admin':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if request.method == 'POST':
        subject_name = request.form['subject_name']
        cursor.execute("INSERT INTO subjects (subject_name) VALUES (%s)", (subject_name,))
        mysql.connection.commit()
        flash('Subject added successfully!', 'success')

    cursor.execute("SELECT * FROM subjects")  # Fetch all subjects
    subjects = cursor.fetchall()
    cursor.close()

    return render_template('add_subject.html', subjects=subjects)



@app.route('/delete_subject/<int:subject_id>', methods=['POST'])
def delete_subject(subject_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("DELETE FROM subjects WHERE id = %s", (subject_id,))
    mysql.connection.commit()
    cursor.close()

    flash('Subject deleted successfully!', 'success')
    return redirect(url_for('add_subject'))  


# ✅ Add and Delete Chapter

@app.route('/add_chapter', methods=['GET', 'POST'])
@login_required
def add_chapter():
    if current_user.role != 'admin':
        flash("Access Denied!", "danger")
        return redirect(url_for('home'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    selected_subject_id = request.args.get('subject_id')

    if request.method == 'POST':
        if 'chapter_name' in request.form:
            chapter_name = request.form['chapter_name']
            subject_id = request.form['subject_id']

            cursor.execute("INSERT INTO chapters (chapter_name, subject_id) VALUES (%s, %s)", (chapter_name, subject_id))
            mysql.connection.commit()
            flash('Chapter added successfully!', 'success')

            return redirect(url_for('add_chapter', subject_id=subject_id))

        elif 'delete_chapter_id' in request.form:
            # Delete chapter
            chapter_id = request.form['delete_chapter_id']
            cursor.execute("DELETE FROM chapters WHERE id = %s", (chapter_id,))
            mysql.connection.commit()
            flash('Chapter deleted successfully!', 'success')

            return redirect(url_for('add_chapter', subject_id=selected_subject_id))

    # Fetch subjects
    cursor.execute("SELECT id, subject_name FROM subjects")
    subjects = cursor.fetchall()

    # Fetch chapters based on selected subject
    chapters = []
    if selected_subject_id:
        cursor.execute("SELECT id, chapter_name FROM chapters WHERE subject_id = %s", (selected_subject_id,))
        chapters = cursor.fetchall()

    cursor.close()
    return render_template('add_chapter.html', subjects=subjects, chapters=chapters, selected_subject_id=selected_subject_id)






# ✅ Manage Chapter
@app.route('/manage_chapters', methods=['GET', 'POST'])
@login_required
def manage_chapters():
    if current_user.role != 'admin':
        flash("Access Denied!", "danger")
        return redirect(url_for('home'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    selected_subject_id = request.args.get('subject_id')

    if request.method == 'POST':
        if 'edit_chapter_id' in request.form:
            # Update chapter name
            chapter_id = request.form['edit_chapter_id']
            new_chapter_name = request.form['new_chapter_name']
            cursor.execute("UPDATE chapters SET chapter_name = %s WHERE id = %s", (new_chapter_name, chapter_id))
            mysql.connection.commit()
            flash('Chapter updated successfully!', 'success')

        elif 'delete_chapter_id' in request.form:
            # Delete chapter
            chapter_id = request.form['delete_chapter_id']
            cursor.execute("DELETE FROM chapters WHERE id = %s", (chapter_id,))
            mysql.connection.commit()
            flash('Chapter deleted successfully!', 'success')

            # Redirect to the same subject to keep the selection
            return redirect(url_for('manage_chapters', subject_id=selected_subject_id))

    # Fetch subjects and chapters
    cursor.execute("SELECT id, subject_name FROM subjects")
    subjects = cursor.fetchall()

    chapters = []
    if selected_subject_id:
        cursor.execute("SELECT id, chapter_name FROM chapters WHERE subject_id = %s", (selected_subject_id,))
        chapters = cursor.fetchall()

    cursor.close()
    return render_template('manage_chapters.html', subjects=subjects, chapters=chapters, selected_subject_id=selected_subject_id)


# ✅ Add Question

@app.route('/add_question', methods=['GET', 'POST'])
@login_required
def add_question():
    if current_user.role != 'admin':
        flash("Access Denied!", "danger")
        return redirect(url_for('home'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)  # ✅ Fix cursor

    if request.method == 'POST':
        question_text = request.form['question_text']
        chapter_id = request.form['chapter_id']
        option_a = request.form['option_a']
        option_b = request.form['option_b']
        option_c = request.form['option_c']
        option_d = request.form['option_d']
        correct_option = request.form['correct_option']

        cursor.execute(
            "INSERT INTO questions (question_text, chapter_id, option_a, option_b, option_c, option_d, correct_option) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (question_text, chapter_id, option_a, option_b, option_c, option_d, correct_option)
        )
        mysql.connection.commit()
        flash('Question added successfully!', 'success')
        return redirect(url_for('add_question'))

    # Fetch subjects and chapters
    cursor.execute("SELECT id, subject_name FROM subjects")
    subjects = cursor.fetchall()

    cursor.execute("SELECT c.id, c.chapter_name, s.subject_name FROM chapters c JOIN subjects s ON c.subject_id = s.id")
    chapters = cursor.fetchall()

    cursor.close()
    return render_template('add_question.html', subjects=subjects, chapters=chapters)



# ✅ Manage Question

@app.route('/manage_question', methods=['GET', 'POST'])
@login_required
def manage_question():
    if current_user.role != 'admin':
        flash("Access Denied!", "danger")
        return redirect(url_for('home'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch subjects
    cursor.execute("SELECT id, subject_name FROM subjects")
    subjects = cursor.fetchall()

    selected_subject_id = request.args.get('subject_id')
    selected_chapter_id = request.args.get('chapter_id')
    questions = []

    # Fetch chapters if subject is selected
    if selected_subject_id:
        cursor.execute("SELECT id, chapter_name FROM chapters WHERE subject_id = %s", (selected_subject_id,))
        chapters = cursor.fetchall()
    else:
        chapters = []

    # Fetch questions if chapter is selected
    if selected_chapter_id:
        cursor.execute("SELECT * FROM questions WHERE chapter_id = %s", (selected_chapter_id,))
        questions = cursor.fetchall()

    cursor.close()
    return render_template('manage_question.html', subjects=subjects, chapters=chapters, questions=questions, selected_subject_id=selected_subject_id, selected_chapter_id=selected_chapter_id)



@app.route('/edit_question', methods=['POST'])
@login_required
def edit_question():
    if current_user.role != 'admin':
        flash("Access Denied!", "danger")
        return redirect(url_for('home'))

    question_id = request.form.get('question_id')
    question_text = request.form.get('question_text')
    option_a = request.form.get('option_a')
    option_b = request.form.get('option_b')
    option_c = request.form.get('option_c')
    option_d = request.form.get('option_d')
    correct_option = request.form.get('correct_option')

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE questions 
            SET question_text=%s, option_a=%s, option_b=%s, option_c=%s, option_d=%s, correct_option=%s
            WHERE id=%s
        """, (question_text, option_a, option_b, option_c, option_d, correct_option, question_id))
        mysql.connection.commit()
        flash("Question updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating question: {e}", "danger")

    return redirect(url_for('manage_question'))




@app.route('/delete_question/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    if current_user.role != 'admin':
        flash("Access Denied!", "danger")
        return redirect(url_for('home'))

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM questions WHERE id = %s", (question_id,))
        mysql.connection.commit()
        flash("Question deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting question: {e}", "danger")

    return redirect(url_for('manage_question'))





# ✅ Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    print("Starting Flask App...")  # Helps check if Flask is running
    app.run(debug=True, use_reloader=False) 