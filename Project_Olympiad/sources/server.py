import random
from flask import Flask, Response, request, make_response, jsonify, render_template, redirect, send_from_directory, send_file, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import json
from flask import send_file
import math, markdown
from collections import Counter, deque
import os
import threading, time
import sqlite3  # Добавляем модуль для работы с SQLite
import secrets
from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from threading import Thread
import markdown
from markdown.extensions.toc import TocExtension
import markdown_katex
from queue import Queue, Empty


# Определяем блокировку для синхронизации доступа к очереди запросов
queue_lock = threading.Lock()
path = os.path.dirname(os.path.abspath(__name__))
request_queue = deque()
app = Flask(__name__)
CORS(app)
app.config.from_object(__name__)
# Конфигурация для загрузки аватарок
UPLOAD_FOLDER = 'sources/static/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # Global limit 5MB to allow chat attachments
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Storage for messenger attachments
MESSAGE_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(MESSAGE_UPLOAD_FOLDER, exist_ok=True)

# Конфигурация
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.path.join(BASE_DIR, '..', 'tasks')
SUBMISSIONS_DIR = os.path.join(BASE_DIR, '..', 'submissions')
TEMPLATES_DIR = os.path.join(BASE_DIR, '..', 'templates')
DB_PATH = os.path.join(BASE_DIR,'Data_BD', 'olympiad.db')
LEARNING_DIR = os.path.join(BASE_DIR, '..', 'learning')
os.makedirs(LEARNING_DIR, exist_ok=True)

# Создаем необходимые директории
os.makedirs(TASKS_DIR, exist_ok=True)
os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
app.static_folder = 'static'
name_task = dict()
# name_task[0] = 'A + B = ?'
# name_task[1] = 'День Рождения у Илхома ?'
# name_task[2] = 'Полёт Мухамммада'
# name_task[3] = 'Багаж Мухаммада'
# name_task[4] = 'Традиционные блюда Таджикистана'
# name_task[5] = 'Поиск кратчайшего пути между городами Таджикистана'
# name_task[6] = 'Поиск самого богатого потомка'
# name_task[7] = 'Путешествие по лесу'
# SMTP_USER = os.environ.get("SMTP_USER")
# SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
     # Обновляем таблицу пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        username TEXT,
        email TEXT UNIQUE,
        email_verified BOOLEAN DEFAULT 0,
        rating INTEGER DEFAULT 0,
        register_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        avatar_url TEXT
    )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temp_users (
            login TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

    # Таблица временных токенов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS auth_tokens (
        token TEXT PRIMARY KEY,
        user_login TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_login) REFERENCES users(login)
    )
    ''')

    # Таблица кодов подтверждения email
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS email_codes (
        email TEXT PRIMARY KEY,
        code TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')


    # Таблица друзей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS friends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_login TEXT NOT NULL,
        friend_login TEXT NOT NULL,
        status TEXT NOT NULL, -- 'requested', 'accepted', 'rejected'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_login) REFERENCES users(login),
        FOREIGN KEY (friend_login) REFERENCES users(login)
    )
    ''')

    # Таблица отправленных решений
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_login TEXT NOT NULL,
        task_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        code TEXT NOT NULL,
        verdict TEXT,
        execution_time INTEGER,  -- ДОБАВЛЕНО
        memory_kb INTEGER,       -- ДОБАВЛЕНО
        programming_lang TEXT,   -- ДОБАВЛЕНО
        FOREIGN KEY (user_login) REFERENCES users(login)
    )
    ''')
    
    # Таблица последних номеров отправок
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS counters (
        name TEXT PRIMARY KEY,
        value INTEGER NOT NULL
    )
    ''')
    
    # Таблица названий задач
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS task_names (
        task_id INTEGER NOT NULL,
        language TEXT NOT NULL,
        title TEXT NOT NULL,
        PRIMARY KEY (task_id, language)
    )
    ''')
    

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS login_attempts (
        email TEXT PRIMARY KEY,
        attempts INTEGER DEFAULT 0,
        last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS code_attempts (
        email TEXT PRIMARY KEY,
        attempts INTEGER DEFAULT 0,
        last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_login TEXT NOT NULL,
        receiver_login TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'sent',  -- sent, delivered, read
        request_id TEXT UNIQUE,
        deleted_for_sender BOOLEAN DEFAULT 0,
        deleted_for_receiver BOOLEAN DEFAULT 0,
        file_path TEXT,
        file_size INTEGER,
        mime_type TEXT
    )
    ''')
    
    # Создаем таблицу заблокированных пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS blocked_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blocker_login TEXT NOT NULL,
        blocked_login TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    # Добавляем индекс для быстрого поиска сообщений
    db_query(
        "CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages "
        "(sender_login, receiver_login, timestamp)",
        commit=True
    )
    # Проверяем и инициализируем счетчик отправок
    cursor.execute('SELECT value FROM counters WHERE name = "submission"')
    if cursor.fetchone() is None:
        cursor.execute('INSERT INTO counters (name, value) VALUES ("submission", 0)')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_request_id ON messages(request_id)')
    
    # Проверяем, есть ли уже данные в task_names
    cursor.execute('SELECT COUNT(*) FROM task_names')
    if cursor.fetchone()[0] == 0:
        # Заполняем начальные данные только если таблица пуста
        initial_data = [
            (1, 'russian', 'A + B = ?'),
            (2, 'russian', 'День Рождения у Илхома ?'),
            (3, 'russian', 'Полёт Мухаммада'),
            (4, 'russian', 'Багаж Мухаммада'),
            (5, 'russian', 'Традиционные блюда Таджикистана'),
            (6, 'russian', 'Поиск кратчайшего пути между городами Таджикистана'),
            (7, 'russian', 'Поиск самого богатого потомка'),
            (8, 'russian', 'Путешествие по лесу'),
            
            (1, 'english', 'A + B = ?'),
            (2, 'english', 'Ilhom\'s Birthday?'),
            (3, 'english', 'Muhammad\'s Flight'),
            (4, 'english', 'Muhammad\'s Luggage'),
            (5, 'english', 'Traditional Dishes of Tajikistan'),
            (6, 'english', 'Finding the Shortest Path between Cities of Tajikistan'),
            (7, 'english', 'Finding the Richest Descendant'),
            (8, 'english', 'Journey through the Forest'),
            
            (1, 'tajik', 'A + B = ?'),
            (2, 'tajik', 'Зодрӯзи Илҳом?'),
            (3, 'tajik', 'Парвози Муҳаммад'),
            (4, 'tajik', 'Багажи Муҳаммад'),
            (5, 'tajik', 'Таомҳои анъанавии Тоҷикистон'),
            (6, 'tajik', 'Ёфтани роҳи кӯтоҳтарин байни шаҳрҳои Тоҷикистон'),
            (7, 'tajik', 'Ҷустуҷӯи фарзанди бойтарин'),
            (8, 'tajik', 'Сафари байнаи ҷангал')
        ]
        cursor.executemany('INSERT INTO task_names (task_id, language, title) VALUES (?, ?, ?)', initial_data)
    
    conn.commit()
    conn.close()

# Функции для работы с базой данных
def db_query(query, args=(), commit=False, fetchone=False, fetchall=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, args)
    result = None
    if commit:
        conn.commit()
    if fetchone:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()
    conn.close()
    return result

@app.route('/get_login')
def get_login():
    login = request.cookies.get("saved_name")
    return jsonify({"login": login})


@app.route('/logout')
def logout():
    login = request.cookies.get("saved_name")
    token = request.cookies.get("auth_token")
    
    if login and token:
        db_query(
            "DELETE FROM auth_tokens WHERE token = ? AND user_login = ?",
            (token, login),
            commit=True
        )
    
    response = make_response(jsonify({"result": "Вы вышли из системы"}))
    response.set_cookie("saved_name", "", expires=0)
    response.set_cookie("auth_token", "", expires=0)
    return response


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<path:image_name>')
def get_image(image_name):
    return send_from_directory(path + '/', image_name)

@app.route('/get_news')
def get_newss():
    file_path = path + '/text_news/text_news.txt'
    with open(file_path, 'r',  encoding='utf-8') as ss:
        news = ss.readlines()
    return jsonify(news)

@app.route('/get_info_user')
def get_info_userr():
    login = request.cookies.get("saved_name")
    if not login:
        return jsonify({})
    
    # Получаем информацию о пользователе
    user = db_query(
        "SELECT username FROM users WHERE login = ?",
        (login,),
        fetchone=True
    )
    
    if not user:
        return jsonify({})
    
    # Считаем решенные задачи
    solved = db_query(
        "SELECT COUNT(DISTINCT task_id) FROM submissions WHERE user_login = ? AND verdict = 'Accepted'",
        (login,),
        fetchone=True
    )
    
    solved_count = solved[0] if solved else 0
    
    return jsonify({
        'name': user[0],
        "login": login,
        'count': solved_count
    })

@app.route('/get_tasks', methods=['GET'])
def get_tasks():
    # 1) Получаем параметры пагинации page и limit
    try:
        page  = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 3))
    except ValueError:
        return jsonify({'error': 'Invalid pagination parameters'}), 400

    language = request.args.get('language', 'russian')

    # 2) Общее количество задач в БД для данной локали
    total = db_query(
        "SELECT COUNT(DISTINCT task_id) FROM task_names WHERE language = ?",
        (language,),
        fetchone=True
    )[0]

    # 3) Смещение
    offset = (page - 1) * limit

    # 4) Выборка нужного среза задач
    rows = db_query(
        """
        SELECT task_id, title
        FROM task_names
        WHERE language = ?
        GROUP BY task_id
        ORDER BY task_id
        LIMIT ? OFFSET ?
        """,
        (language, limit, offset),
        fetchall=True
    )

    tasks = [{'id': row[0], 'title': row[1]} for row in rows]

    # 5) Отдаём задачи + мета-информацию
    return jsonify({
        'tasks': tasks,
        'total': total,
        'page': page,
        'limit': limit
    })


def get_task_name(task_id, language='russian'):
    result = db_query(
        "SELECT title FROM task_names WHERE task_id = ? AND language = ?",
        (task_id, language),
        fetchone=True
    )
    return result[0] if result else f"Task {task_id}"

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    tasks = []
    for task_dir in os.listdir(TASKS_DIR):
        if task_dir.startswith('task_'):
            task_id = task_dir.split('_')[1]
            meta_path = os.path.join(TASKS_DIR, task_dir, 'meta.json')
            
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                tasks.append({
                    'id': task_id,
                    'title': meta['title']
                })
    
    return jsonify(tasks)

@app.route('/api/task/<int:task_id>/meta')
def get_task_meta(task_id):
    try:
        with open(f'{TASKS_DIR}/{task_id}/meta.json', 'r', encoding='utf-8') as f:
            meta = json.load(f)
        return jsonify(meta)
    except FileNotFoundError:
        return jsonify({'error': 'Task not found'}), 404
    
@app.route('/api/task/<int:task_id>/description/<lang>')
def get_task_description(task_id, lang):
    try:
        with open(f'{TASKS_DIR}/{task_id}/condition.{lang}.md', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Преобразуем markdown в HTML
        html = markdown.markdown(content, extensions=[
            'fenced_code', 'tables', 'mdx_math'
        ])
        
        # Обработка математических выражений для MathJax
        html = html.replace('$$', '$$$$')  # Экранирование для MathJax
        
        return jsonify({'html': html})
    except FileNotFoundError:
        return jsonify({'error': 'Description not found'}), 404

@app.route('/api/task/<int:task_id>/examples')
def get_task_examples(task_id):
    examples = []
    examples_dir = f'{TASKS_DIR}/{task_id}/examples'
    
    if os.path.exists(examples_dir):
        files = os.listdir(examples_dir)
        in_files = sorted([f for f in files if f.endswith('.in')])
        
        for in_file in in_files:
            example_id = in_file.split('.')[0]
            out_file = f'{example_id}.out'
            
            if out_file in files:
                with open(f'{examples_dir}/{in_file}', 'r') as f:
                    input_data = f.read()
                with open(f'{examples_dir}/{out_file}', 'r') as f:
                    output_data = f.read()
                
                examples.append({
                    'id': example_id,
                    'input_url': f'/api/task/{task_id}/example/{example_id}/input',
                    'output_url': f'/api/task/{task_id}/example/{example_id}/output'
                })
    
    return jsonify(examples)

@app.route('/api/task/<int:task_id>/example/<example_id>/input')
def get_example_input(task_id, example_id):
    try:
        with open(f'{TASKS_DIR}/{task_id}/examples/{example_id}.in', 'r') as f:
            return f.read(), 200, {'Content-Type': 'text/plain'}
    except FileNotFoundError:
        return 'Not found', 404
    
@app.route('/api/task/<int:task_id>/example/<example_name>/output', methods=['GET'])
def get_example_output(task_id, example_name):
    task_dir = os.path.join(TASKS_DIR, f'task_{task_id}')
    output_path = os.path.join(task_dir, 'output', f'{example_name}.txt')
    
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    else:
        return jsonify({'error': 'Output example not found'}), 404

@app.route('/api/task/<int:task_id>/solutions', methods=['GET'])
def list_solutions(task_id):
    task_dir = os.path.join(TASKS_DIR, f'task_{task_id}')
    solutions_dir = os.path.join(task_dir, 'solutions')
    
    solutions = []
    if os.path.exists(solutions_dir):
        for file in os.listdir(solutions_dir):
            if file.endswith('.tex'):
                lang = os.path.splitext(file)[0]
                solutions.append(lang)
    
    return jsonify(solutions)

@app.route('/api/task/<int:task_id>/solution/<language>', methods=['GET'])
def get_task_solution(task_id, language):
    task_dir = os.path.join(TASKS_DIR, f'task_{task_id}')
    file_path = os.path.join(task_dir, 'solutions', f'{language}.tex')
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    else:
        return jsonify({'error': 'Solution not found'}), 404

# API для отправки решений (обновлено)
@app.route('/api/submit', methods=['POST'])
def submit_solution():
    task_id = request.form.get('task_id')
    programming_lang = request.form.get('lang')
    code = request.form.get('code')
    login = request.cookies.get("saved_name")

    if not code:
        return jsonify({'success': False, 'error': 'Code not provided'})
    
    # Сохраняем в БД
    db_query(
        "INSERT INTO submissions (user_login, task_id, timestamp, code, programming_lang, verdict, execution_time, memory_kb) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (login, task_id, datetime.now().isoformat(), code, programming_lang, 
         "Accepted",  # В реальной системе здесь будет результат проверки
         random.randint(10, 500),  # Пример времени выполнения
         random.randint(100, 5000)  # Пример использования памяти
        ),
        commit=True
    )
    
    # Получаем ID посылки
    submission_id = db_query(
        "SELECT last_insert_rowid()",
        fetchone=True
    )[0]
    
    return jsonify({
        'success': True, 
        'submission_id': submission_id,
        'message': 'Solution submitted for testing'
    })

@app.route('/api/submission/<int:submission_id>', methods=['GET'])
def get_submission_code(submission_id):
    row = db_query(
        "SELECT code, programming_lang FROM submissions WHERE id = ?",
        (submission_id,),
        fetchone=True
    )
    if not row:
        return jsonify({'error': 'Submission not found'}), 404

    return jsonify({
        'code': row[0],
        'language': row[1]
    })


@app.route('/get_code')
def get_code():
    sid = request.args.get('submission_id')
    row = db_query("SELECT code FROM submissions WHERE id=?", (sid,), fetchone=True)
    return jsonify({'code': row[0] if row else ''})

@app.route('/api/task/<int:task_id>/submissions', methods=['GET'])
def get_user_submissions(task_id):
    login = request.cookies.get("saved_name")
    if not login:
        return jsonify([])

    # Получаем последние 5 посылок пользователя по данной задаче
    rows = db_query(
        "SELECT id, timestamp, programming_lang, verdict, execution_time, memory_kb "
        "FROM submissions "
        "WHERE user_login = ? AND task_id = ? "
        "ORDER BY timestamp DESC LIMIT 5",
        (login, task_id)
    )

    submissions = []
    for row in rows:
        submissions.append({
            'id': row[0],
            'timestamp': row[1],
            'lang': row[2],
            'verdict': row[3],
            'time': row[4],
            'memory': row[5]
        })

    return jsonify(submissions)

# Маршрут для шаблона задачи
@app.route('/sources/task', methods=['GET'])
def task_page():
    return send_file(os.path.join(TEMPLATES_DIR, 'task.html'))

@app.route('/api/profile')
def get_profile():
    login = request.args.get('login')
    if not login:
        return jsonify({'error': 'Login parameter is required'}), 400
    
    try:
        user = db_query(
            '''
            SELECT 
                login, 
                username, 
                avatar_url, 
                rating,
                register_date,
                last_active
            FROM users 
            WHERE login = ?
            ''',
            (login,),
            fetchone=True
        )
        print(user)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        def format_db_date(date_str):
            try:
                if not date_str:
                    return "N/A"
                # Парсим строку из SQLite
                dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                return dt.strftime('%d.%m.%Y %H:%M')
            except Exception as e:
                print(f"Error formatting date: {e}")
                return "N/A"
        
        register_date = format_db_date(user[4])
        last_active = format_db_date(user[5])
        
        # Получаем статистику
        solved = db_query(
            'SELECT COUNT(DISTINCT task_id) FROM submissions WHERE user_login = ? AND verdict = "Accepted"',
            (login,),
            fetchone=True
        )[0] or 0
        
        friends_count = db_query(
            'SELECT COUNT(*) FROM friends WHERE user_login = ? AND status = "accepted"',
            (login,),
            fetchone=True
        )[0] or 0
        
        submissions_count = db_query(
            'SELECT COUNT(*) FROM submissions WHERE user_login = ?',
            (login,),
            fetchone=True
        )[0] or 0
        
        return jsonify({
            'login': user[0],
            'username': user[1],
            'avatar_url': user[2] or '/static/default_avatar.png',
            'rating': user[3],
            'register_date': register_date,
            'last_active': last_active,
            'solved_problems': solved,
            'friends_count': friends_count,
            'submissions_count': submissions_count
        })
        
    except Exception as e:
        print(f"Error in get_profile: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
# API для установки языка
@app.route('/api/set_language', methods=['POST'])
def set_language():
    data = request.get_json()
    language = data.get('language', 'russian')
    
    if language not in ['russian', 'english', 'tajik']:
        return jsonify({'success': False, 'error': 'Invalid language'})
    
    resp = make_response(jsonify({'success': True}))
    resp.set_cookie('language', language, max_age=30*24*60*60)
    return resp
    
@app.route('/sources/profile')
def profile():
    return send_file(os.path.join(TEMPLATES_DIR, 'profile.html'))
# API для загрузки аватара
@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'avatar' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{request.cookies.get('saved_name')}_{int(time.time())}.{file.filename.rsplit('.', 1)[1].lower()}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        print(filepath)
        file.save(filepath)
        
        # Обновляем аватар в базе
        db_query(
            'UPDATE users SET avatar_url = ? WHERE login = ?',
            (f'/static/avatars/{filename}', request.cookies.get('saved_name')),
            commit=True
        )
        
        return jsonify({
            'success': True, 
            'avatar_url': f'/static/avatars/{filename}'
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

# API для изменения пароля (с проверкой текущего)
@app.route('/change_password', methods=['POST'])
def change_password():
    data = request.get_json()
    login = request.cookies.get('saved_name')
    
    if not login:
        return jsonify({'error': 'Not authenticated'}), 401
        
    # Проверяем текущий пароль
    user = db_query(
        'SELECT password FROM users WHERE login = ?',
        (login,),
        fetchone=True
    )
    
    if not user or not check_password_hash(user[0], data['currentPassword']):
        return jsonify({'error': 'Invalid current password'}), 401
        
    # Обновляем пароль
    hashed_password = generate_password_hash(data['newPassword'])
    db_query(
        'UPDATE users SET password = ? WHERE login = ?',
        (hashed_password, login),
        commit=True
    )
    
    return jsonify({'success': True, 'message': 'Password updated successfully'})

# API для изменения имени пользователя
@app.route('/change_name', methods=['POST'])
def change_name():
    data = request.get_json()
    login = request.cookies.get('saved_name')
    
    if not login:
        return jsonify({'error': 'Not authenticated'}), 401
        
    new_name = data.get('newUserName')
    if not new_name or len(new_name) < 3:
        return jsonify({'error': 'Invalid name'}), 400
        
    db_query(
        'UPDATE users SET username = ? WHERE login = ?',
        (new_name, login),
        commit=True
    )
    
    return jsonify({'success': True, 'message': 'Name updated successfully'})

# API для добавления в друзья (односторонняя подписка)
@app.route('/friends_add', methods=['POST'])
def add_friend():
    data = request.get_json()
    user_login = request.cookies.get('saved_name')
    friend_login = data.get('friend_login')
    
    if not user_login or not friend_login:
        return jsonify({'error': 'Missing parameters'}), 400
        
    # Проверяем, не пытается ли пользователь добавить самого себя
    if user_login == friend_login:
        return jsonify({'error': 'Cannot add yourself'}), 400
        
    # Проверяем, не добавлен ли уже
    existing = db_query(
        'SELECT * FROM friends WHERE user_login = ? AND friend_login = ?',
        (user_login, friend_login),
        fetchone=True
    )
    
    if existing:
        return jsonify({'error': 'Already in friends'}), 400
        
    # Добавляем запись о дружбе (только в одном направлении)
    db_query(
        'INSERT INTO friends (user_login, friend_login, status) VALUES (?, ?, ?)',
        (user_login, friend_login, 'accepted'),
        commit=True
    )
    
    return jsonify({'success': True})

# API для удаления из друзей
@app.route('/friends_remove', methods=['POST'])
def remove_friend():
    data = request.get_json()
    user_login = request.cookies.get('saved_name')
    friend_login = data.get('friend_login')
    
    if not user_login or not friend_login:
        return jsonify({'error': 'Missing parameters'}), 400
        
    db_query(
        'DELETE FROM friends WHERE user_login = ? AND friend_login = ?',
        (user_login, friend_login),
        commit=True
    )
    
    return jsonify({'success': True})

# API для проверки статуса дружбы (односторонняя)
@app.route('/friends_status')
def friends_status():
    user = request.args.get('user')
    friend = request.args.get('friend')
    
    if not user or not friend:
        return jsonify({'error': 'Both user and friend parameters are required'}), 400
    
    status = db_query(
        'SELECT 1 FROM friends WHERE user_login = ? AND friend_login = ? AND status = "accepted"',
        (user, friend),
        fetchone=True
    )
    
    return jsonify({'is_friend': bool(status)})

# API для получения списка друзей (тех, на кого подписан пользователь)
@app.route('/friends')
def get_friends():
    login = request.args.get('login')
    if not login:
        return jsonify({'error': 'Login parameter is required'}), 400
        
    rows = db_query(
        '''
        SELECT u.login, u.username, u.avatar_url 
        FROM friends f
        JOIN users u ON f.friend_login = u.login
        WHERE f.user_login = ? AND f.status = 'accepted'
        ''',
        (login,),
        fetchall=True
    )
    
    # Преобразуем в список словарей
    friends = []
    for row in rows:
        friends.append({
            'login': row[0],
            'username': row[1],
            'avatar_url': row[2]
        })
    
    return jsonify(friends)
    
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/get_packages')
def get_packages():
    # Получаем параметры запроса
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 5))
    search = request.args.get('search', '').strip()
    tab = request.args.get('tab', 'all')
    
    # Получаем язык из куки
    language = request.cookies.get('language', 'russian')
    if language not in ['russian', 'english', 'tajik']:
        language = 'russian'

    # Получаем логин пользователя
    login = request.cookies.get("saved_name", "")
    offset = (page - 1) * limit
    
    # Базовый SQL-запрос
    base_query = """
        SELECT 
            s.id, s.user_login, s.task_id, s.timestamp,
            s.verdict, s.execution_time, s.memory_kb,
            s.programming_lang, COALESCE(t.title, 'Task ' || s.task_id) as title,
            COUNT(*) OVER() as total
        FROM submissions s
        LEFT JOIN task_names t 
            ON s.task_id = t.task_id AND t.language = ?
    """
    params = [language]
    conditions = []
    
    # Фильтрация по вкладкам
    if tab == 'mine' and login:
        conditions.append("s.user_login = ?")
        params.append(login)
    elif tab == 'friends' and login:
        # Получаем список друзей одним запросом
        friend_logins = [
            row[0] for row in db_query(
                "SELECT friend_login FROM friends WHERE user_login = ?",
                (login,),
                fetchall=True
            )
        ]
        if friend_logins:
            placeholders = ','.join(['?'] * len(friend_logins))
            conditions.append(f"s.user_login IN ({placeholders})")
            params.extend(friend_logins)
        else:
            # Если нет друзей - возвращаем пустой результат
            return jsonify({'total': 0, 'packages': []})
    
    # Фильтрация по поиску
    if search:
        search_condition = " OR ".join([
            "t.title LIKE ?",
            "s.user_login LIKE ?",
            "s.verdict LIKE ?",
            "s.programming_lang LIKE ?"
        ])
        conditions.append(f"({search_condition})")
        search_term = f"%{search}%"
        params.extend([search_term] * 4)
    
    # Собираем все условия
    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)
    
    # Добавляем сортировку и пагинацию
    base_query += " ORDER BY s.timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    # Выполняем запрос
    rows = db_query(base_query, params, fetchall=True)
    
    # Форматируем результат
    packages = []
    total = rows[0][9] if rows else 0
    
    for row in rows:
        packages.append({
            'id': row[0],
            'user': row[1],
            'task_id': row[2],
            'timestamp': row[3],
            'verdict': row[4],
            'time': row[5] or 0,
            'memory': row[6] or 0,
            'language': row[7],
            'name': row[8]
        })
    
    return jsonify({'total': total, 'packages': packages})

@app.route('/api/update_activity', methods=['POST'])
def update_activity():
    if 'saved_name' in request.cookies:
        login = request.cookies.get('saved_name')
        try:
            now_local = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # локальное время сервера
            db_query(
                "UPDATE users SET last_active = ? WHERE login = ?",
                (now_local, login),
                commit=True
            )
        except Exception as e:
            print(f"Error updating last_active: {str(e)}")
            return jsonify({'status': 'error'}), 500
    return '', 204

def generate_token():
    return secrets.token_urlsafe(64)

def generate_email_code():
    return str(secrets.randbelow(1000000)).zfill(6)

def create_auth_token(login):
    token = generate_token()
    expires_at = datetime.now() + timedelta(days=1)
    
    db_query(
        "INSERT INTO auth_tokens (token, user_login, expires_at) VALUES (?, ?, ?)",
        (token, login, expires_at),
        commit=True
    )
    return token

def validate_credentials(login, token):
    """Основная функция проверки аутентификации"""
    if not login or not token:
        return False
        
    # Проверяем токен в базе
    token_data = db_query(
        "SELECT user_login, expires_at FROM auth_tokens WHERE token = ?",
        (token,),
        fetchone=True
    )
    
    if not token_data:
        return False
        
    token_login, expires_at = token_data
    
    # Убираем миллисекунды из строки времени
    clean_expires_at = expires_at.split('.')[0]  # <-- Исправление здесь
    
    # Проверяем соответствие логина и срока действия
    if token_login != login:
        return False
        
    if datetime.now() > datetime.strptime(clean_expires_at, '%Y-%m-%d %H:%M:%S'):  # <-- Используем очищенную строку
        db_query("DELETE FROM auth_tokens WHERE token = ?", (token,), commit=True)
        return False
        
    # Обновляем время активности
    db_query(
        "UPDATE users SET last_active = ? WHERE login = ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), login),  # <-- Форматируем время
        commit=True
    )
    
    return True
def protected_route(func):
    """Декоратор для защиты маршрутов"""
    def wrapper(*args, **kwargs):
        login = request.cookies.get("saved_name")
        token = request.cookies.get("auth_token")
        
        if not validate_credentials(login, token):
            return jsonify({"error": "Unauthorized"}), 401
            
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

def send_email(to_email, subject, body):
    global SMTP_USER, SMTP_PASSWORD
    # Конфигурация SMTP (замените на свои данные)
    SMTP_SERVER = "smtp.yandex.ru"
    SMTP_PORT = 465
    SMTP_USER = os.environ.get("SMTP_USER")  # Ваш email
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")  # Пароль приложения
    print(SMTP_USER)
   # print(SMTP_USER, SMTP_PASSWORD)
    # SMTP_USER = "your_email@yandex.ru"
    # SMTP_PASSWORD = "your_password"
    
    try:
        # Создаем сообщение
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        
        # Отправляем через SSL
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {str(e)}")
        return False

def send_confirmation_email(email, code):

    subject = "Код подтверждения для Tajik Fire"
    body = f"""
    Здравствуйте!
    
    Ваш код подтверждения для Tajik Fire: {code}
    
    Введите этот код в форме подтверждения на сайте.
    Код действителен в течение 3 минут.
    
    С уважением,
    Команда Tajik Fire
    """
    return send_email(email, subject, body)

@app.route('/resend_code', methods=['POST'])
def resend_code():
    data = request.get_json()
    email = data.get('email')

    attempt_record = db_query(
        "SELECT attempts, last_attempt FROM code_attempts WHERE email = ?",
        (email,),
        fetchone=True
    )
    print(attempt_record)
    if attempt_record:
        attempts, last_attempt_str = attempt_record
        if attempts >= 3:
            return jsonify({
                "result": "Превышено количество попыток. Попробуйте через час."
            }), 403
    try:
        attempts = attempt_record[0] + 1
    except:
        attempts = 1
    db_query(
        "INSERT OR REPLACE INTO code_attempts (email, attempts) VALUES (?, ?)",
        (email, attempts),
        commit=True
    ) 
    email = data.get('email')
    if not email:
        return jsonify({"result": "Укажите email"}), 400
    
    # Проверяем существование пользователя
    user = db_query(
        "SELECT login FROM temp_users WHERE email = ?",
        (email,),
        fetchone=True
    )
    if not user:
        return jsonify({"result": "Пользователь с таким email не найден"})
    
    # Генерируем новый код
    new_code = generate_email_code()
    
    # Обновляем код в базе
    db_query(
        "INSERT OR REPLACE INTO email_codes (email, code, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (email, new_code),
        commit=True
    )
    
    # Отправляем email
    if send_confirmation_email(email, new_code):
        return jsonify({"result": f"Новый код отправлен на {email}"})
    else:
        return jsonify({"result": "Ошибка отправки кода"}), 500

@app.route('/check_email_verified')
@protected_route
def check_email_verified():
    login = request.cookies.get("saved_name")
    
    verified = db_query(
        "SELECT email_verified FROM users WHERE login = ?",
        (login,),
        fetchone=True
    )
    
    if verified and verified[0]:
        return jsonify({"verified": True})
    return jsonify({"verified": False})

from threading import Thread
def cleanup_scheduler():
    """Фоновая задача для очистки устаревших токенов и кодов"""
    while True:
        try:
            db_query(
                "DELETE FROM login_attempts WHERE last_attempt < datetime('now', '-1 day')",
                commit=True
            )
            db_query(
                "DELETE FROM code_attempts WHERE last_attempt < datetime('now', '-1 day')",
                commit=True
            )
            
            # Удаляем просроченные токены
            db_query(
                "DELETE FROM auth_tokens WHERE expires_at < datetime('now')",
                commit=True
            )
            
            # Удаляем коды старше 10 минут
            db_query(
                "DELETE FROM email_codes WHERE created_at < datetime('now', '-10 minutes')",
                commit=True
            )
            
            db_query("DELETE FROM temp_users WHERE created_at < datetime('now', '-1 day')", commit=True)
            # Засыпаем на 1 час
            time.sleep(3600)

        except Exception as e:
            print(f"Ошибка в планировщике очистки: {e}")
            time.sleep(60)


@app.route('/register', methods=['POST'])
def register_user():
    lang = request.cookies.get("language")
    
    # Сообщения на разных языках
    messages = {
        'russian': {
            'required': 'Заполните все обязательные поля',
            'login_taken': 'Этот логин уже занят',
            'email_taken': 'Этот email уже зарегистрирован',
            'success': 'Регистрация успешна. Проверьте почту для подтверждения.'
        },
        'english': {
            'required': 'Please fill in all required fields',
            'login_taken': 'This login is already taken',
            'email_taken': 'This email is already registered',
            'success': 'Registration successful. Check your email for confirmation.'
        },
        'tajik': {
            'required': 'Ҳамаи майдонҳои ҳатмиро пур кунед',
            'login_taken': 'Ин логин аллакай истифода мешавад',
            'email_taken': 'Ин почтаи электронӣ аллакай бақайд шудааст',
            'success': 'Бақайдгирӣ бомуваффақият анҷом ёфт. Барои тасдиқ почтаи электронии худро санҷед.'
        }
    }
    
    data = request.get_json()
    if not data:
        return jsonify({"result": "Invalid data format"}), 400

    login = data.get('login')
    email = data.get('email')
    password = data.get('password')
    username = data.get('username', '')

    # Проверяем, занят ли логин или email
    existing_login = db_query("SELECT * FROM users WHERE login = ?", (login,), fetchone=True)
    if existing_login:
        return jsonify({"result": messages[lang]['login_taken']}), 400

    existing_email = db_query("SELECT * FROM users WHERE email = ?", (email,), fetchone=True)
    if existing_email:
        return jsonify({"result": messages[lang]['email_taken']}), 400

    # Сохраняем пользователя во временной таблице
    db_query(
        "INSERT OR REPLACE INTO temp_users (login, email, password, username) VALUES (?, ?, ?, ?)",
        (login, email, password, username),
        commit=True
    )

    # Генерируем и отправляем код подтверждения
    code = generate_email_code()
    db_query(
        "INSERT OR REPLACE INTO email_codes (email, code, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (email, code),
        commit=True
    )

    send_confirmation_email(email, code)

    return jsonify({"result": "Регистрация успешна. Проверьте почту для подтверждения."}), 200

@app.route('/confirm_email', methods=['POST'])
def confirm_email():
    data = request.get_json()
    
    if not data:
        return jsonify({"result": "Invalid data format"}), 400

    email = data.get('email')
    code = data.get('code')
    
    # Проверяем блокировку по попыткам ввода кода
    attempt_record = db_query(
        "SELECT attempts, last_attempt FROM code_attempts WHERE email = ?",
        (email,),
        fetchone=True
    )

    print(attempt_record)
    if attempt_record:
        attempts, last_attempt_str = attempt_record
        last_attempt = datetime.strptime(last_attempt_str, '%Y-%m-%d %H:%M:%S')
        current_time = datetime.now()
        
        if attempts >= 3:
            return jsonify({
                "result": "Превышено количество попыток. Попробуйте через 15 минуть."
            }), 403
            
        elif attempts >= 3 or (current_time - last_attempt).total_seconds() >= 900 :
            db_query(
                "DELETE FROM code_attempts WHERE email = ?",
                (email,),
                commit=True
            )
            attempt_record = None

    if not all([email, code]):
        return jsonify({"result": "Заполните все поля"}), 400
    
    # Ищем последний актуальный код для email
    record = db_query(
        "SELECT code, created_at FROM email_codes WHERE email = ? ORDER BY created_at DESC LIMIT 1",
        (email,),
        fetchone=True
    )

    if not record:
        # Увеличиваем счетчик попыток, если код не найден
        if attempt_record:
            new_attempts = attempts + 1
            db_query(
                "UPDATE code_attempts SET attempts = ?, last_attempt = CURRENT_TIMESTAMP WHERE email = ?",
                (new_attempts, email),
                commit=True
            )
        else:
            db_query(
                "INSERT INTO code_attempts (email, attempts) VALUES (?, 1)",
                (email,),
                commit=True
            )
        return jsonify({"result": "Код подтверждения не найден"}), 400

    stored_code, created_at = record
    created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    
    # Проверяем срок действия кода
    if (datetime.now(timezone.utc) - created_at).total_seconds() > 300:
        # Увеличиваем счетчик попыток для просроченного кода
        if attempt_record:
            new_attempts = attempts + 1
            db_query(
                "UPDATE code_attempts SET attempts = ?, last_attempt = CURRENT_TIMESTAMP WHERE email = ?",
                (new_attempts, email),
                commit=True
            )
        else:
            db_query(
                "INSERT INTO code_attempts (email, attempts) VALUES (?, 1)",
                (email,),
                commit=True
            )
        return jsonify({"result": "Срок действия кода истёк"}), 400

    # Проверяем совпадение кода
    if stored_code != code:
        # Увеличиваем счетчик попыток для неверного кода
        if attempt_record:
            new_attempts = attempts + 1
            db_query(
                "UPDATE code_attempts SET attempts = ?, last_attempt = CURRENT_TIMESTAMP WHERE email = ?",
                (new_attempts, email),
                commit=True
            )
        else:
            db_query(
                "INSERT INTO code_attempts (email, attempts) VALUES (?, 1)",
                (email,),
                commit=True
            )
        return jsonify({"result": "Неверный код подтверждения"}), 400
    
    # Если код верный - сбрасываем счетчик
    if attempt_record:
        db_query(
            "DELETE FROM code_attempts WHERE email = ?",
            (email,),
            commit=True
        )


    # Получаем данные пользователя из временной таблицы
    temp_user = db_query("SELECT * FROM temp_users WHERE email = ?", (email,), fetchone=True)
    if not temp_user:
        return jsonify({"result": "Пользователь не найден"}), 400
    login, email, password, username, register_date = temp_user

    # Переносим пользователя в основную таблицу
    db_query(
        "INSERT INTO users (login, email, password, username, register_date, email_verified) VALUES (?, ?, ?, ?, ?, 1)",
        (login, email, password, username, register_date),
        commit=True
    )

    # Удаляем из временного хранилища
    db_query("DELETE FROM temp_users WHERE email = ?", (email,), commit=True)

    # Удаляем использованные коды
    db_query("DELETE FROM email_codes WHERE email = ?", (email,), commit=True)

    # Генерируем токен
    token = create_auth_token(login)

    response = jsonify({"result": "Email успешно подтверждён!"})
    response.set_cookie("auth_token", token, max_age=86400, httponly=True, secure=True)
    return response

@app.route('/login', methods=["POST"])
def login_user():
    # Получаем данные из JSON
    data = request.get_json()
    if not data:
        return jsonify({"result": "Invalid data format"}), 400
        
    email = data.get('email')
    password = data.get('password')
    
    # Проверяем блокировку по попыткам входа
    attempt_record = db_query(
        "SELECT attempts, last_attempt FROM login_attempts WHERE email = ?",
        (email,),
        fetchone=True
    )
    
    if attempt_record:
        attempts, last_attempt_str = attempt_record
        last_attempt = datetime.strptime(last_attempt_str, '%Y-%m-%d %H:%M:%S')
        current_time = datetime.now()
        
        # Если превышено количество попыток и не прошло 1 часа
        if attempts >= 3:
            return jsonify({
                "result": "Превышено количество попыток. Попробуйте через час."
            }), 403
            
        # Если прошло больше часа - сбрасываем счетчик
        elif attempts >= 3 or (current_time - last_attempt).total_seconds() >= 3600:
            db_query(
                "DELETE FROM login_attempts WHERE email = ?",
                (email,),
                commit=True
            )
            attempt_record = None
    else:
        db_query(
                "INSERT OR REPLACE INTO login_attempts (email, attempts) VALUES (?, 1)",
                (email,),
                commit=True
            )
    if not email or not password:
        return jsonify({"result": "Заполните все поля"}), 400
    
    # Проверяем пользователя по email
    user = db_query(
        "SELECT email, password, email_verified, login FROM users WHERE email = ?",
        (email,),
        fetchone=True
    )
    
    # Если пользователь не найден или пароль неверный - увеличиваем счетчик
    if not user or user[1] != password:
        # Обновляем счетчик попыток
        if attempt_record:
            new_attempts = attempts + 1
            db_query(
                "UPDATE login_attempts SET attempts = ?, last_attempt = CURRENT_TIMESTAMP WHERE email = ?",
                (new_attempts, email),
                commit=True
            )
        else:
            db_query(
                "INSERT INTO login_attempts (email, attempts) VALUES (?, 1)",
                (email,),
                commit=True
            )
            
        return jsonify({"result": "Неверный email или пароль"}), 400
    
    stored_email, stored_password, email_verified, login = user
    
    # Проверяем подтверждение email
    if not email_verified:
        return jsonify({
            "result": "Email не подтверждён",
            "requiresConfirmation": True
        }), 400
    
    # Если вход успешный - сбрасываем счетчик
    if attempt_record:
        db_query(
            "DELETE FROM login_attempts WHERE email = ?",
            (email,),
            commit=True
        )
    
    # Создаем токен аутентификации
    token = create_auth_token(login)
    
    response = jsonify({"result": "Вы успешно вошли!"})
    response.set_cookie("saved_name", login, max_age=86400)
    response.set_cookie("auth_token", token, max_age=86400, httponly=True)
    return response

# Добавляем константу
LEARNING_DIR = os.path.join(BASE_DIR, '..', 'learning')
os.makedirs(LEARNING_DIR, exist_ok=True)

def get_all_topics():
    topics = []
    for topic_dir in os.listdir(LEARNING_DIR):
        if os.path.isdir(os.path.join(LEARNING_DIR, topic_dir)):
            meta_path = os.path.join(LEARNING_DIR, topic_dir, 'meta.json')
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    topic = json.load(f)
                    topic['id'] = topic_dir
                    topics.append(topic)
    return topics

@app.route('/learning')
def learning_page():
    return send_file(os.path.join(TEMPLATES_DIR, 'learning.html'))

@app.route('/api/learning/topics')
def get_learning_topics():
    # Параметры запроса
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    search = request.args.get('search', '').strip()
    difficulty = int(request.args.get('difficulty', 0))
    category = request.args.get('category', 'all')
    progress = request.args.get('progress', 'all')
    lang = request.args.get('lang', 'ru')
    
    # Фильтрация тем
    filtered_topics = []
    for topic in get_all_topics():
        # Применяем фильтры
        if search and search.lower() not in topic['titles'].get(lang, '').lower():
            continue
        if difficulty > 0 and topic['difficulty'] != difficulty:
            continue
        if category != 'all' and category not in topic['categories']:
            continue
            
        # Добавляем тему с переводом
        filtered_topics.append({
            'id': topic['id'],
            'title': topic['titles'].get(lang, topic['titles']['en']),
            'description': topic['descriptions'].get(lang, topic['descriptions']['en']),
            'difficulty': topic['difficulty'],
            'category': topic['categories'][0] if topic['categories'] else 'General',
            'progress': random.randint(0, 100)  # Заглушка, в реальном приложении брать из БД
        })
    
    # Пагинация
    total = len(filtered_topics)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = filtered_topics[start:end]
    
    return jsonify({
        'topics': paginated,
        'total': total
    })

@app.route('/api/learning/topic/<topic_id>/theory')
def get_topic_theory(topic_id):
    lang = request.args.get('lang', 'ru')
    safe_topic_id = secure_filename(topic_id)
    theory_path = os.path.join(LEARNING_DIR, safe_topic_id, f'theory_{lang}.md')
    
    if not os.path.exists(theory_path):
        # Пробуем английский как запасной
        en_theory_path = os.path.join(LEARNING_DIR, safe_topic_id, 'theory_en.md')
        if os.path.exists(en_theory_path):
            theory_path = en_theory_path
        else:
            return jsonify({'error': 'Theory not found'}), 404
    
    try:
        with open(theory_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Конвертируем Markdown в HTML с поддержкой математики
        html_content = markdown.markdown(
            content,
            extensions=[
                'fenced_code',
                'tables',
                TocExtension(baselevel=2),
                markdown_katex.KatexExtension(insert_fonts_css=False)
            ]
        )
        
        return jsonify({'content': html_content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/learning/topic/<topic_id>/problems')
def get_topic_problems(topic_id):
    lang = request.args.get('lang', 'ru')
    safe_topic_id = secure_filename(topic_id)
    problems_path = os.path.join(LEARNING_DIR, safe_topic_id, 'problems.json')
    
    if not os.path.exists(problems_path):
        return jsonify({'error': 'Problems not found'}), 404
    
    try:
        with open(problems_path, 'r', encoding='utf-8') as f:
            problems = json.load(f)
        
        # Применяем перевод
        for problem in problems:
            problem['title'] = problem['titles'].get(lang, problem['titles']['en'])
            problem['description'] = problem['descriptions'].get(lang, problem['descriptions']['en'])
        
        return jsonify(problems)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/learning/topic/<topic_id>/resources')
def get_topic_resources(topic_id):
    # Заглушка - в реальном приложении брать из meta.json
    return jsonify([
        {
            "title": "Official Documentation",
            "description": "Complete reference and guides",
            "url": "https://example.com/docs",
            "icon": "fas fa-book"
        },
        {
            "title": "Video Tutorial",
            "description": "Step-by-step video explanation",
            "url": "https://example.com/tutorial",
            "icon": "fas fa-video"
        },
        {
            "title": "Practice Platform",
            "description": "Online judge with practice problems",
            "url": "https://example.com/practice",
            "icon": "fas fa-laptop-code"
        }
    ])

@app.route('/api/learning/user/stats')
@protected_route
def get_user_stats():
    login = request.cookies.get("saved_name")
    
    # Заглушка - в реальном приложении брать из БД
    return jsonify({
        'completed': random.randint(5, 20),
        'bookmarked': random.randint(3, 15),
        'solved': random.randint(10, 50)
    })

@app.route('/api/learning/topic/<topic_id>/meta')
def get_topic_meta(topic_id):
    safe_topic_id = secure_filename(topic_id)
    meta_path = os.path.join(LEARNING_DIR, safe_topic_id, 'meta.json')
    
    if not os.path.exists(meta_path):
        return jsonify({'error': 'Metadata not found'}), 404
    
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        
        lang = request.args.get('lang', 'ru')
        return jsonify({
            'title': meta['titles'].get(lang, meta['titles']['en']),
            'difficulty': meta['difficulty'],
            'time_estimate': meta['time_estimate'].get(lang, meta['time_estimate']['en']),
            'author': meta['author'].get(lang, meta['author']['en'])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================
# Messenger: helpers & SSE
# ==========================

# Очереди событий для SSE по пользователям
event_queues = {}
event_lock = threading.Lock()

def get_event_queue(login):
    with event_lock:
        if login not in event_queues:
            event_queues[login] = Queue()
        return event_queues[login]

def notify_user(login, payload):
    try:
        q = get_event_queue(login)
        q.put(payload)
    except Exception as e:
        print(f"notify_user error for {login}: {e}")

def users_are_blocked(sender_login, receiver_login):
    blocked_a = db_query(
        'SELECT 1 FROM blocked_users WHERE blocker_login = ? AND blocked_login = ?',
        (receiver_login, sender_login),
        fetchone=True
    )
    blocked_b = db_query(
        'SELECT 1 FROM blocked_users WHERE blocker_login = ? AND blocked_login = ?',
        (sender_login, receiver_login),
        fetchone=True
    )
    return bool(blocked_a or blocked_b)

def format_message_row_for(login_viewer, row):
    message_id, sender_login, receiver_login, text, ts, status, request_id, del_sender, del_receiver, file_path, file_size, mime_type = row
    if login_viewer == sender_login and del_sender:
        return None
    if login_viewer == receiver_login and del_receiver:
        return None
    is_file = file_path is not None
    file_url = None
    if is_file:
        file_url = f"/static/uploads/{os.path.basename(file_path)}"
    return {
        'id': message_id,
        'request_id': request_id,
        'sender': sender_login,
        'text': text,
        'time': ts,
        'status': status,
        'is_file': is_file,
        'file_url': file_url,
        'mime_type': mime_type
    }

@app.route('/api/messenger/events')
def messenger_events():
    login = request.cookies.get('saved_name')
    token = request.cookies.get('auth_token')
    if not validate_credentials(login, token):
        return jsonify({'error': 'Unauthorized'}), 401

    def event_stream(user_login):
        q = get_event_queue(user_login)
        yield f"data: {json.dumps({'heartbeat': True})}\n\n"
        while True:
            try:
                payload = q.get(timeout=25)
                yield f"data: {json.dumps(payload)}\n\n"
            except Empty:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"

    headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    }
    return Response(event_stream(login), headers=headers)

# =============================
# Messenger: core API endpoints
# =============================

@app.route('/api/messenger/send', methods=['POST'])
@protected_route
def messenger_send():
    sender_login = request.cookies.get('saved_name')
    receiver_login = request.form.get('receiver')
    text = (request.form.get('message') or '').strip()
    request_id = request.form.get('request_id')
    file = request.files.get('file')

    if not receiver_login or (not text and not file):
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    if users_are_blocked(sender_login, receiver_login):
        return jsonify({'success': False, 'error': 'User blocked'}), 403

    if file:
        file.stream.seek(0, os.SEEK_END)
        size_bytes = file.stream.tell()
        file.stream.seek(0)
        if size_bytes > 5 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'File too large'}), 400

        count_today = db_query(
            "SELECT COUNT(*) FROM messages WHERE sender_login = ? AND file_path IS NOT NULL AND date(timestamp) = date('now')",
            (sender_login,),
            fetchone=True
        )[0]
        if count_today >= 5:
            return jsonify({'success': False, 'error': 'Daily file limit reached'}), 429

    if request_id:
        existing = db_query('SELECT id FROM messages WHERE request_id = ?', (request_id,), fetchone=True)
        if existing:
            return jsonify({'success': True, 'duplicate': True, 'message_id': existing[0]})

    saved_path = None
    mime_type = None
    file_size = None
    if file:
        filename = secure_filename(file.filename)
        unique_name = f"{sender_login}_{int(time.time())}_{filename}"
        saved_path = os.path.join(MESSAGE_UPLOAD_FOLDER, unique_name)
        file.save(saved_path)
        mime_type = file.mimetype
        file_size = os.path.getsize(saved_path)

    db_query(
        'INSERT INTO messages (sender_login, receiver_login, message, status, request_id, file_path, file_size, mime_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (sender_login, receiver_login, text if text else (file.filename if file else ''), 'sent', request_id, saved_path, file_size, mime_type),
        commit=True
    )
    new_id = db_query('SELECT last_insert_rowid()', fetchone=True)[0]

    notify_user(receiver_login, {'new_messages': True})
    return jsonify({'success': True, 'message_id': new_id, 'duplicate': False})


@app.route('/api/messenger/messages')
@protected_route
def messenger_messages():
    login = request.cookies.get('saved_name')
    friend = request.args.get('friend')
    if not friend:
        return jsonify({'messages': []})

    last_id = request.args.get('last_id', type=int)
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=50, type=int)
    offset = (page - 1) * limit

    params = [login, friend, friend, login]
    base = (
        "SELECT id, sender_login, receiver_login, message, timestamp, status, request_id, "
        "deleted_for_sender, deleted_for_receiver, file_path, file_size, mime_type "
        "FROM messages WHERE ((sender_login = ? AND receiver_login = ?) OR (sender_login = ? AND receiver_login = ?))"
    )

    if last_id is not None:
        query = base + " AND id > ? ORDER BY id DESC"
        params.append(last_id)
    else:
        query = base + " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    rows = db_query(query, tuple(params), fetchall=True) or []

    if rows:
        ids_to_deliver = [r[0] for r in rows if r[2] == login and r[5] == 'sent']
        if ids_to_deliver:
            placeholders = ','.join(['?'] * len(ids_to_deliver))
            db_query(f"UPDATE messages SET status = 'delivered' WHERE id IN ({placeholders})", tuple(ids_to_deliver), commit=True)

    msgs = []
    for r in rows:
        m = format_message_row_for(login, r)
        if m:
            msgs.append(m)
    return jsonify({'messages': msgs})


@app.route('/api/messenger/mark_read', methods=['POST'])
@protected_route
def messenger_mark_read():
    login = request.cookies.get('saved_name')
    data = request.get_json() or {}
    friend = data.get('friend')
    if not friend:
        return jsonify({'success': False}), 400
    db_query("UPDATE messages SET status = 'read' WHERE receiver_login = ? AND sender_login = ? AND status != 'read'", (login, friend), commit=True)
    notify_user(friend, {'new_messages': True})
    return jsonify({'success': True})


@app.route('/api/messenger/delete', methods=['POST'])
@protected_route
def messenger_delete():
    login = request.cookies.get('saved_name')
    data = request.get_json() or {}
    message_id = data.get('id')
    for_all = bool(data.get('for_all'))
    if not message_id:
        return jsonify({'success': False}), 400

    row = db_query('SELECT sender_login, receiver_login FROM messages WHERE id = ?', (message_id,), fetchone=True)
    if not row:
        return jsonify({'success': False}), 404
    sender_login, receiver_login = row

    if for_all:
        if login != sender_login:
            return jsonify({'success': False, 'error': 'Forbidden'}), 403
        db_query('UPDATE messages SET deleted_for_sender = 1, deleted_for_receiver = 1 WHERE id = ?', (message_id,), commit=True)
        notify_user(receiver_login, {'new_messages': True})
    else:
        if login == sender_login:
            db_query('UPDATE messages SET deleted_for_sender = 1 WHERE id = ?', (message_id,), commit=True)
        elif login == receiver_login:
            db_query('UPDATE messages SET deleted_for_receiver = 1 WHERE id = ?', (message_id,), commit=True)
        else:
            return jsonify({'success': False, 'error': 'Forbidden'}), 403
    return jsonify({'success': True})


@app.route('/api/messenger/block', methods=['POST'])
@protected_route
def messenger_block():
    login = request.cookies.get('saved_name')
    data = request.get_json() or {}
    friend = data.get('friend')
    if not friend:
        return jsonify({'success': False}), 400
    exists = db_query('SELECT 1 FROM blocked_users WHERE blocker_login = ? AND blocked_login = ?', (login, friend), fetchone=True)
    if not exists:
        db_query('INSERT INTO blocked_users (blocker_login, blocked_login) VALUES (?, ?)', (login, friend), commit=True)
    return jsonify({'success': True})


@app.route('/api/messenger/search')
@protected_route
def messenger_search():
    login = request.cookies.get('saved_name')
    q = (request.args.get('q') or '').strip()
    if len(q) < 3:
        return jsonify({'users': []})
    rows = db_query("SELECT login, username, COALESCE(avatar_url, '/static/default_avatar.png') FROM users WHERE (login LIKE ? OR username LIKE ?) AND login != ? LIMIT 20", (f"%{q}%", f"%{q}%", login), fetchall=True) or []
    users = [{'login': r[0], 'username': r[1] or r[0], 'avatar': r[2]} for r in rows]
    return jsonify({'users': users})


@app.route('/api/messenger/friends')
@protected_route
def messenger_friends():
    login = request.cookies.get('saved_name')
    rows = db_query(
        '''
        SELECT DISTINCT u.login, COALESCE(u.username, u.login) AS username, COALESCE(u.avatar_url, '/static/default_avatar.png') AS avatar, u.last_active
        FROM users u
        WHERE u.login IN (
            SELECT friend_login FROM friends WHERE user_login = ? AND status = 'accepted'
            UNION
            SELECT user_login FROM friends WHERE friend_login = ? AND status = 'accepted'
        )
        ''',
        (login, login),
        fetchall=True
    ) or []

    def last_message_for(friend_login):
        r = db_query(
            '''
            SELECT id, sender_login, receiver_login, message, timestamp, status, request_id, deleted_for_sender, deleted_for_receiver, file_path, file_size, mime_type
            FROM messages
            WHERE ((sender_login = ? AND receiver_login = ?) OR (sender_login = ? AND receiver_login = ?))
            ORDER BY id DESC LIMIT 1
            ''',
            (login, friend_login, friend_login, login),
            fetchone=True
        )
        if not r:
            return '', 0
        formatted = format_message_row_for(login, r)
        if not formatted:
            return '', 0
        if formatted['is_file']:
            return f"Файл: {formatted['text']}", 0
        return formatted['text'], 0

    def unread_count_for(friend_login):
        c = db_query("SELECT COUNT(*) FROM messages WHERE receiver_login = ? AND sender_login = ? AND status != 'read' AND (deleted_for_receiver = 0)", (login, friend_login), fetchone=True)
        return c[0] if c else 0

    friends = []
    for r in rows:
        friend_login, username, avatar, last_active = r
        last_message, _ = last_message_for(friend_login)
        friends.append({'login': friend_login, 'username': username, 'avatar': avatar, 'last_active': last_active, 'last_message': last_message, 'unread_count': unread_count_for(friend_login)})

    requests = []
    return jsonify({'friends': friends, 'requests': requests})


@app.route('/api/call/offer', methods=['POST'])
@protected_route
def call_offer():
    login = request.cookies.get('saved_name')
    data = request.get_json() or {}
    to_user = data.get('to')
    offer = data.get('offer')
    if not to_user or not offer:
        return jsonify({'success': False}), 400
    if users_are_blocked(login, to_user):
        return jsonify({'success': False, 'error': 'User blocked'}), 403
    notify_user(to_user, {'call_offer': {'from': login, 'offer': offer}})
    return jsonify({'success': True})


@app.route('/sources/messenger')
def messenger_page():
    return send_file(os.path.join(BASE_DIR, 'messenger.html'))

if __name__ == '__main__':
    init_db()
    cleaner_thread = Thread(target=cleanup_scheduler, daemon=True)
    cleaner_thread.start()
    # Запускаем Flask приложение
    app.run(host='0.0.0.0', port=80)
