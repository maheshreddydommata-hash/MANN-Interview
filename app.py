from flask import Flask, render_template, request, redirect, flash, session
import sqlite3
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from question_bank import question_bank
from hr_question_bank import hr_question_bank
from coding_question_bank import coding_question_bank
from full_mock_question_bank import full_mock_question_bank

app = Flask(__name__)
@app.route('/start')
def start():
    if request.cookies.get('visited') == 'yes':
        return redirect('/login')

    response = redirect('/register')
    response.set_cookie('visited', 'yes', max_age=60*60*24*365)
    return response
app.secret_key = "ai_interview_secret_key"


# Database connection
def get_db():
    return sqlite3.connect("users.db")


# Create database
def create_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# Connect to Ollama AI
def ask_ollama(prompt):

    url = "http://localhost:11434/api/generate"

    data = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "num_predict": 700,
            "temperature": 0.1,
            "num_ctx": 4096
        }
    }

    try:
        response = requests.post(
            url,
            json=data,
            timeout=600
        )

        response.raise_for_status()

        result = response.json()
        return result["response"]

    except requests.exceptions.RequestException as e:
        return "AI connection error: " + str(e)

# Homepage
@app.route('/')
def home():
    return render_template('index.html')

# Registration
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not name or not email or not password:
            flash("Please fill all fields.")
            return redirect('/register')

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect('/register')

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect('/register')

        conn = get_db()
        cursor = conn.cursor()

        try:
            hashed_password = generate_password_hash(password)

            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hashed_password)
            )

            conn.commit()
            flash("Registration successful! Please login.")

        except sqlite3.IntegrityError:
            flash("This email is already registered.")

        finally:
            conn.close()

        return redirect('/login')

    return render_template('register.html')


# Login
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, password FROM users WHERE email = ?",
            (email,)
        )

        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):

            session['user_id'] = user[0]
            session['user_name'] = user[1]

            return redirect('/dashboard')

        flash("Invalid email or password.")

    return render_template('login.html')


# Dashboard
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    return render_template('dashboard.html')


# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# Technical Interview Questions
questions = {
    "Python": "What is Python and what are its main features?",
    "Java": "What is the difference between JDK, JRE and JVM?",
    "SQL": "What is the difference between DELETE, DROP and TRUNCATE?"
}


@app.route('/technical', methods=['GET', 'POST'])
def technical():

    if 'user_id' not in session:
        return redirect('/login')

    subject = request.values.get('subject', 'Python')
    feedback = ""

    if request.method == 'POST':

        answer = request.form.get('answer', '').strip()

        if answer:
            feedback = "Your answer has been submitted successfully!"
        else:
            feedback = "Please enter your answer."

    question = questions.get(subject, questions['Python'])

    return render_template(
        'technical.html',
        question=question,
        feedback=feedback,
        selected_subject=subject
    )


# AI Mock Interview
@app.route('/mock-interview')
def mock_interview():

    if 'user_id' not in session:
        return redirect('/login')

    return render_template('mock_interview.html')


# Start Interview
@app.route('/start-interview', methods=['POST'])
def start_interview():

    if 'user_id' not in session:
        return redirect('/login')

    level = request.form.get('level')
    category = request.form.get('category')
    skill = request.form.get('skill')

    # Select question bank based on interview category
    if category == "Technical":
        selected_bank = question_bank
        skill_questions = selected_bank.get(skill)

        if not skill_questions:
            return "Selected technical skill was not found."

        level_questions = skill_questions.get(level)

    elif category == "HR":
        selected_bank = hr_question_bank
        level_questions = selected_bank.get(level)

    elif category == "Coding":
        selected_bank = coding_question_bank
        level_questions = selected_bank.get(level)

    elif category == "Full Mock Interview":
        selected_bank = full_mock_question_bank
        level_questions = selected_bank.get(level)

    else:
        return "Invalid interview category."

    if not level_questions:
        return "Selected level was not found."

    # Store interview details
    session['interview_questions'] = level_questions
    session['current_question'] = 0
    session['interview_answers'] = []

    session['level'] = level
    session['category'] = category
    session['skill'] = skill

    return render_template(
        'interview.html',
        level=level,
        category=category,
        skill=skill,
        question=level_questions[0]["question"],
        question_number=1,
        total_questions=len(level_questions)
    )

# Submit Interview Answer
@app.route('/submit-answer', methods=['POST'])
def submit_answer():

    if 'user_id' not in session:
        return redirect('/login')

    answer = request.form.get('answer', '').strip()

    if not answer:
        return "Please enter your answer."

    interview_questions = session.get('interview_questions', [])
    current_index = session.get('current_question', 0)
    answers = session.get('interview_answers', [])

    if not interview_questions or current_index >= len(interview_questions):
        return redirect('/dashboard')

    # Store candidate answer
    answers.append({
        "question": interview_questions[current_index]["question"],
        "answer": answer
    })

    session['interview_answers'] = answers

    current_index += 1
    session['current_question'] = current_index

    # Display next question
    if current_index < len(interview_questions):

        return render_template(
            'interview.html',
            level=session.get('level'),
            category=session.get('category'),
            skill=session.get('skill'),
            question=interview_questions[current_index]["question"],
            question_number=current_index + 1,
            total_questions=len(interview_questions)
        )

    # Prepare all questions and answers for AI evaluation
    qa_text = "\n\n".join(
        f"Question: {item['question']}\nCandidate Answer: {item['answer']}"
        for item in answers
    )

    total_possible = len(interview_questions) * 10

    # Optimized AI evaluation prompt
    category = session.get('category')
    skill = session.get('skill')
    level = session.get('level')

    prompt = f"""
You are an experienced professional interviewer.

Interview category: {category}
Skill: {skill}
Level: {level}

Evaluate all candidate answers carefully and independently.

RULES:
1. Give each answer a fair score from 0 to 10.
2. Do not give marks for incorrect or irrelevant answers.
3. Identify mistakes and missing concepts.
4. Provide a correct AI model answer for every question.
5. Keep explanations clear and concise.
6. For HR questions, provide a professional sample answer.
7. For coding questions, provide correct code and a short explanation.
8. Never invent the candidate's personal experiences.

For EACH question, use this format:

QUESTION:
[Original question]

CANDIDATE ANSWER:
[Candidate answer]

EVALUATION:
[Correct, Partially Correct, or Incorrect, with a short reason]

SCORE:
[Marks out of 10]

AI MODEL ANSWER:
[Correct answer in approximately 2-4 sentences.
For coding, include a suitable code solution.]

MISTAKES:
[Important mistakes or None]

MISSING CONCEPTS:
[Important missing points or None]

After evaluating all questions, provide:

FINAL INTERVIEW REPORT:

TOTAL SCORE:
[Sum of all marks out of {total_possible}]

PERCENTAGE:
[Percentage]

STRENGTHS:
[Candidate's strong areas]

WEAKNESSES:
[Areas requiring improvement]

TOPICS TO IMPROVE:
[Recommended study topics]

INTERVIEW TIPS:
[Practical advice]

Candidate Questions and Answers:

{qa_text}
"""
    # Fast AI evaluation prompt
    category = session.get('category')
    skill = session.get('skill')
    level = session.get('level')

    prompt = f"""
You are a professional interviewer.

Category: {category}
Skill: {skill}
Level: {level}

Evaluate all candidate answers fairly.

For every question:
1. Give a score from 0 to 10.
2. Mark Correct, Partially Correct, or Incorrect.
3. Explain the score briefly in one sentence.
4. Give a correct AI model answer in 2-4 sentences.
5. List mistakes briefly.
6. List missing concepts briefly.

Special rules:
- HR: Give a professional sample answer. Never invent candidate experiences.
- Coding: Give correct code and a short explanation.
- Technical: Give an accurate technical explanation.
- Full Mock: Apply the appropriate evaluation to each question.

After all questions, provide:
- Total score out of {total_possible}
- Percentage
- Two strengths
- Two weaknesses
- Three topics to improve
- Two practical interview tips

Keep the complete evaluation concise.
Do not skip any question.
Do not invent answers or give automatic full marks.

Candidate answers:

{qa_text}
"""
# Get AI evaluation
    feedback = ask_ollama(prompt)

    # Prepare candidate answers for display
    answers_summary = "\n\n".join(
        f"Question: {item['question']}\n\nYour Answer: {item['answer']}"
        for item in answers
    )

    # Display final result
    return render_template(
        'result.html',
        answer=answers_summary,
        feedback=feedback
    )
# Run Application
if __name__ == '__main__':
    create_database()
    app.run(debug=True)