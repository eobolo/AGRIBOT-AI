from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os
import random
import time
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config.from_pyfile('config.py')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/profile_pics' # For profile pictures

# Database configuration (always SQLite for ephemeral deployment)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.root_path, 'instance', 'site.db')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Quiz Questions
QUIZ_QUESTIONS = [
    {"id": 1, "question": "What is the capital of France?", "answer": "paris"},
    {"id": 2, "question": "Which planet is known as the Red Planet?", "answer": "mars"},
    {"id": 3, "question": "What is the largest ocean on Earth?", "answer": "pacific ocean"},
    {"id": 4, "question": "Who painted the Mona Lisa?", "answer": "leonardo da vinci"},
]

# Hugging Face API Endpoints
API_URL_NORMAL = os.environ.get('HF_API_URL_NORMAL')
API_URL_UPGRADED = os.environ.get('HF_API_URL_UPGRADED')
HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {os.environ.get('HF_API_TOKEN')}",
    "Content-Type": "application/json"
}

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    profile_picture = db.Column(db.String(255), default='default.jpg')
    is_upgraded = db.Column(db.Boolean, default=False)
    show_welcome_popup = db.Column(db.Boolean, default=True)
    conversations = db.relationship('Conversation', backref='user', lazy='dynamic', cascade="all, delete-orphan")

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    sender = db.Column(db.String(10), nullable=False) # 'user' or 'ai'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

@login_manager.user_loader
def load_user(user_id):
    # return User.query.get(int(user_id)) # Deprecated
    return db.session.get(User, int(user_id))

# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email address already exists', 'error')
            return redirect(url_for('signup'))

        new_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            show_welcome_popup=True
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again.', 'error')
            return redirect(url_for('login'))

        login_user(user, remember=remember)
        flash('Welcome back!', 'success')
        if user.show_welcome_popup:
            flash('show_welcome_popup', 'info')
        return redirect(url_for('chat'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/welcome')
@login_required
def welcome():
    return render_template('welcome_popup.html')

@app.route('/chat')
@login_required
def chat():
    conversations = current_user.conversations.order_by(Conversation.created_at.desc()).all()
    return render_template('chat.html', conversations=conversations, show_welcome_popup_on_load=current_user.show_welcome_popup)

@app.route('/chat/new', methods=['POST'])
@login_required
def new_chat():
    if current_user.conversations.count() >= 8:
        flash('You can only have up to 8 conversations.')
        return redirect(url_for('chat'))
    
    new_conversation = Conversation(user_id=current_user.id, title="New Chat")
    db.session.add(new_conversation)
    db.session.commit()
    return redirect(url_for('conversation', conversation_id=new_conversation.id))

@app.route('/chat/<int:conversation_id>')
@login_required
def conversation(conversation_id):
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
    messages = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.timestamp.asc()).all()
    conversations = current_user.conversations.order_by(Conversation.created_at.desc()).all()
    return render_template('chat.html', current_conversation=conversation, messages=messages, conversations=conversations)

@app.route('/chat/<int:conversation_id>/delete', methods=['POST'])
@login_required
def delete_conversation(conversation_id):
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
    db.session.delete(conversation)
    Message.query.filter_by(conversation_id=conversation.id).delete()
    db.session.commit()
    return jsonify({'message': 'Conversation deleted successfully.', 'category': 'success'})

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    user_input = request.form.get('user_input')
    conversation_id = request.form.get('conversation_id')

    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
    
    # Save user message
    user_message = Message(conversation_id=conversation.id, sender='user', content=user_input)
    db.session.add(user_message)
    db.session.commit()

    # Determine which API to use
    api_url = API_URL_UPGRADED if current_user.is_upgraded else API_URL_NORMAL
    
    ai_response_content = ""
    try:
        data = {"inputs": f"question: {user_input} context: agriculture </s>"}
        response = requests.post(api_url, headers=HEADERS, json=data)
        response.raise_for_status() # Raise an exception for HTTP errors
        ai_response_content = response.json()[0]['generated_text']
        # Extract only the answer part
        if "answer:" in ai_response_content:
            ai_response_content = ai_response_content.split("answer:", 1)[1].strip()
        
        # Add a full stop if the response doesn't end with punctuation
        if ai_response_content and not ai_response_content.strip().endswith( ('.', '!', '?') ):
            ai_response_content += '.'

    except requests.exceptions.RequestException as e:
        print(f"API call failed: {e}")
        ai_response_content = "Sorry, I'm having trouble connecting to the AI. Please try again later."

    ai_message = Message(conversation_id=conversation.id, sender='ai', content=ai_response_content)
    db.session.add(ai_message)
    db.session.commit()

    return jsonify({'ai_response': ai_response_content, 'conversation_id': conversation.id})

@app.route('/upgrade', methods=['GET', 'POST'])
@login_required
def upgrade():
    if current_user.is_upgraded:
        flash('You have already upgraded to the better model.')
        return redirect(url_for('settings')) # Redirect to settings if already upgraded

    selected_question = random.choice(QUIZ_QUESTIONS)

    if request.method == 'POST':
        # Simple quiz logic (for demonstration)
        user_answer = request.form.get('quiz_answer')
        question_id = int(request.form.get('question_id'))

        correct_answer = None
        for q in QUIZ_QUESTIONS:
            if q['id'] == question_id:
                correct_answer = q['answer']
                break

        if user_answer and correct_answer and user_answer.lower() == correct_answer.lower():
            current_user.is_upgraded = True
            db.session.commit()
            flash('Congratulations! You have been upgraded to the better AI model.')
            return redirect(url_for('settings'))
        else:
            flash('Incorrect answer. Please try again.')
    return render_template('upgrade.html', quiz_question=selected_question)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        # Handle profile picture update
        if 'profile_picture' in request.files and request.files['profile_picture'].filename != '':
            file = request.files['profile_picture']
            filename = secure_filename(file.filename)
            unique_filename = f"{current_user.id}_{int(time.time())}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            current_user.profile_picture = unique_filename
        
        # Handle welcome popup toggle (now part of the same form)
        current_user.show_welcome_popup = 'show_welcome_popup' in request.form
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', show_welcome_popup_setting=current_user.show_welcome_popup)

@app.route('/chat/<int:conversation_id>/rename', methods=['POST'])
@login_required
def rename_conversation(conversation_id):
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
    new_title = request.form.get('new_title')
    if new_title:
        conversation.title = new_title
        db.session.commit()
        return jsonify({'message': 'Conversation renamed successfully.', 'category': 'success', 'new_title': new_title})
    return jsonify({'message': 'Failed to rename conversation.', 'category': 'error'}), 400

@app.route('/chat/clear_all', methods=['POST'])
@login_required
def clear_all_conversations():
    conversations = Conversation.query.filter_by(user_id=current_user.id).all()
    for conv in conversations:
        Message.query.filter_by(conversation_id=conv.id).delete()
        db.session.delete(conv)
    db.session.commit()
    flash('All conversations cleared successfully.', 'success')
    return redirect(url_for('chat'))

# Initialize database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Create the profile_pics directory if it doesn't exist
    if not os.path.exists('static/profile_pics'):
        os.makedirs('static/profile_pics')
    app.run(debug=True) 