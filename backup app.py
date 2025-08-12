from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager
from datetime import datetime
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
import mistune


# --- KONFIGURASI APLIKASI ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'bimaAPPDSC' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/dsc_prod_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)

# Inisialisasi ekstensi
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# --- MODEL DATABASE ---
class HomePageContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), default='ahli', nullable=False)

    def __init__(self, username, password, role='ahli'):
        self.username = username
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        self.role = role

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
class RemajaPutri(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    points = db.Column(db.Integer, default=0) # <-- TAMBAHKAN BARIS INI
    fcm_token = db.Column(db.String(255), nullable=True, unique=True)
    logs = db.relationship('DailyLog', backref='pemilik', lazy=True)

    def __init__(self, username, password):
        self.username = username
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class DailyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.Date, nullable=False) # Hapus default dari sini
    minum_ttd = db.Column(db.Boolean, default=False)
    catatan_makan = db.Column(db.String(200), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('remaja_putri.id'), nullable=False)
    
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    video_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.Text, nullable=True) # Jawaban bisa kosong pada awalnya
    status = db.Column(db.String(50), default='Belum Dijawab', nullable=False)
    answered_by = db.Column(db.String(80), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('remaja_putri.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Tabel untuk mendefinisikan semua lencana yang tersedia
class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon_name = db.Column(db.String(100), nullable=False) # Nama ikon dari Material Icons

# Tabel untuk mencatat lencana mana yang sudah dimiliki oleh user (Many-to-Many)
class UserBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('remaja_putri.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

# Model untuk kategori/topik di dalam forum
class ForumTopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)

# Model untuk postingan utama/thread dalam sebuah topik
class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('remaja_putri.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topic.id'), nullable=False)
    
    # Relasi untuk mendapatkan nama user dan jumlah balasan
    user = db.relationship('RemajaPutri', backref='forum_posts')
    replies = db.relationship('ForumReply', backref='post', lazy='dynamic', cascade="all, delete-orphan")

# Model untuk balasan dalam sebuah postingan
class ForumReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('remaja_putri.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    
    # Relasi untuk mendapatkan nama user
    user = db.relationship('RemajaPutri', backref='forum_replies')

# --- API ENDPOINTS (RUTE) ---
@app.route('/')
def index():
    content = HomePageContent.query.get(1)
    markdown_content = ""
    # Jika ada konten, proses teksnya dari Markdown ke HTML
    if content and content.content:
        markdown_content = mistune.html(content.content)

    return render_template('index.html', content=content, markdown_content=markdown_content)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"msg": "Username dan password dibutuhkan"}), 400
    if RemajaPutri.query.filter_by(username=username).first():
        return jsonify({"msg": "Username sudah digunakan"}), 400
    new_user = RemajaPutri(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"msg": "Registrasi berhasil!"}), 201

@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = RemajaPutri.query.filter_by(username=username).first()

    if user and user.check_password(password):
        access_token = create_access_token(identity=str(user.id))
        return jsonify(access_token=access_token)

    return jsonify({"msg": "Username atau password salah"}), 401

@app.route('/log', methods=['POST'])
@jwt_required()
def add_log():
    # 1. Dapatkan ID pengguna dari token
    current_user_id = get_jwt_identity()
    data = request.get_json()
    today_date = datetime.utcnow().date()

    # 2. Ambil objek pengguna dari database TERLEBIH DAHULU
    user = RemajaPutri.query.get(int(current_user_id))
    if not user:
        return jsonify({"msg": "Pengguna tidak ditemukan."}), 404

    # 3. Cek apakah log untuk hari ini sudah ada
    today_log = DailyLog.query.filter_by(user_id=user.id, tanggal=today_date).first()
    if today_log:
        return jsonify({"msg": "Log untuk hari ini sudah ada"}), 400

    # 4. Jika belum ada, buat log baru
    new_log = DailyLog(
        tanggal=today_date,
        minum_ttd=data.get('minum_ttd', False),
        catatan_makan=data.get('catatan_makan', ''),
        user_id=user.id
    )
    db.session.add(new_log)

    # 5. Tambahkan poin ke pengguna (sekarang aman)
    if user.points is None: # Pengaman tambahan jika poin somehow NULL
        user.points = 0
    user.points += 10

    # 6. Cek dan berikan lencana jika perlu
    log_count = DailyLog.query.filter_by(user_id=user.id).count() + 1
    if log_count == 1:
        badge_id_to_award = 1 # ID untuk lencana 'Pejuang Gizi'
        has_badge = UserBadge.query.filter_by(user_id=user.id, badge_id=badge_id_to_award).first()
        if not has_badge:
            new_user_badge = UserBadge(user_id=user.id, badge_id=badge_id_to_award)
            db.session.add(new_user_badge)

    # 7. Simpan semua perubahan ke database
    db.session.commit()

    return jsonify({"msg": "Log berhasil ditambahkan dan Anda mendapatkan 10 poin!"}), 201

@app.route('/logs', methods=['GET'])
@jwt_required()
def get_logs():
    current_user_id = get_jwt_identity()
    try:
        logs = DailyLog.query.filter_by(user_id=current_user_id).order_by(DailyLog.tanggal.desc()).all()
        output = []
        for log in logs:
            if log and log.tanggal:
                log_data = {
                    'tanggal': log.tanggal.strftime('%Y-%m-%d'),
                    'minum_ttd': log.minum_ttd,
                    'catatan_makan': log.catatan_makan or ""
                }
                output.append(log_data)
        return jsonify({'logs': output})
    except Exception as e:
        print(f"!!! KRITIS: Terjadi error di get_logs: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"msg": "Terjadi error internal saat mengambil data log"}), 500

@app.route('/articles', methods=['GET'])
@jwt_required()
def get_articles():
    articles = Article.query.order_by(Article.created_at.desc()).all()
    output = []
    for article in articles:
        article_data = {
            'id': article.id,
            'title': article.title,
            'snippet': article.content[:100] + '...' if len(article.content) > 100 else article.content,
            # --- TAMBAHKAN DATA BARU INI ---
            'image_filename': article.image_filename 
        }
        output.append(article_data)
    return jsonify({'articles': output})

# Ganti fungsi get_article_detail yang lama dengan ini:
@app.route('/articles/<int:article_id>', methods=['GET'])
@jwt_required()
def get_article_detail(article_id):
    article = Article.query.get_or_404(article_id)
    article_data = {
        'id': article.id,
        'title': article.title,
        'content': article.content,
        'created_at': article.created_at.strftime('%Y-%m-%d') if article.created_at else None,
        'image_filename': article.image_filename,
        'video_url': article.video_url
    }
    return jsonify(article_data)

@app.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    current_user_id = get_jwt_identity()
    user = RemajaPutri.query.get_or_404(current_user_id)
    
    # Ambil semua lencana yang dimiliki oleh user ini
    user_badges = UserBadge.query.filter_by(user_id=user.id).all()
    badges_data = []
    for ub in user_badges:
        badge_info = Badge.query.get(ub.badge_id)
        if badge_info:
            badges_data.append({
                'name': badge_info.name,
                'description': badge_info.description,
                'icon_name': badge_info.icon_name
            })

    profile_data = {
        'username': user.username,
        'points': user.points,
        'join_date': user.created_at.strftime('%d %B %Y'),
        'badges': badges_data # <-- KIRIM DATA LENCANA DI SINI
    }
    return jsonify(profile_data)

@app.route('/questions', methods=['POST'])
@jwt_required()
def ask_question():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    question_text = data.get('question_text')
    if not question_text:
        return jsonify({"msg": "Teks pertanyaan tidak boleh kosong"}), 400

    new_question = Question(
        question_text=question_text,
        user_id=int(current_user_id) # Pastikan user_id adalah integer
    )
    db.session.add(new_question)
    db.session.commit()

    return jsonify({"msg": "Pertanyaan Anda telah berhasil dikirim!"}), 201


# Endpoint untuk pengguna melihat riwayat pertanyaan mereka
@app.route('/questions', methods=['GET'])
@jwt_required()
def get_my_questions():
    current_user_id = get_jwt_identity()
    
    questions = Question.query.filter_by(user_id=int(current_user_id)).order_by(Question.created_at.desc()).all()
    
    output = []
    for q in questions:
        question_data = {
            'id': q.id,
            'question_text': q.question_text,
            'answer_text': q.answer_text or "Belum ada jawaban.",
            'status': q.status,
            'created_at': q.created_at.strftime('%d %B %Y')
        }
        output.append(question_data)
        
    return jsonify({'questions': output})

# --- FORUM API ENDPOINTS ---

# Mendapatkan semua kategori/topik forum
@app.route('/forum/topics', methods=['GET'])
@jwt_required()
def get_forum_topics():
    topics = ForumTopic.query.all()
    return jsonify([{'id': topic.id, 'name': topic.name, 'description': topic.description} for topic in topics])

# Mendapatkan semua postingan dalam satu topik
@app.route('/forum/posts/in-topic/<int:topic_id>', methods=['GET'])
@jwt_required()
def get_posts_in_topic(topic_id):
    posts = ForumPost.query.filter_by(topic_id=topic_id).order_by(ForumPost.created_at.desc()).all()
    return jsonify([{
        'id': post.id,
        'title': post.title,
        'author': post.user.username,
        'reply_count': post.replies.count()
    } for post in posts])

# Mendapatkan detail satu postingan beserta semua balasannya
@app.route('/forum/post/<int:post_id>', methods=['GET'])
@jwt_required()
def get_post_details(post_id):
    post = ForumPost.query.get_or_404(post_id)
    replies = post.replies.order_by(ForumReply.created_at.asc()).all()
    
    post_data = {
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'author': post.user.username,
        'created_at': post.created_at.strftime('%d %B %Y'),
        'replies': [{
            'id': reply.id,
            'content': reply.content,
            'author': reply.user.username,
            'created_at': reply.created_at.strftime('%d %B %Y, %H:%M')
        } for reply in replies]
    }
    return jsonify(post_data)

# Membuat postingan baru
@app.route('/forum/posts', methods=['POST'])
@jwt_required()
def create_post():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    new_post = ForumPost(
        title=data['title'],
        content=data['content'],
        topic_id=data['topic_id'],
        user_id=int(current_user_id)
    )
    db.session.add(new_post)
    db.session.commit()
    return jsonify({'msg': 'Postingan berhasil dibuat!', 'post_id': new_post.id}), 201

# Menambah balasan baru
@app.route('/forum/reply/to-post/<int:post_id>', methods=['POST'])
@jwt_required()
def create_reply(post_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    new_reply = ForumReply(
        content=data['content'],
        post_id=post_id,
        user_id=int(current_user_id)
    )
    db.session.add(new_reply)
    db.session.commit()
    return jsonify({'msg': 'Balasan berhasil dikirim!'}), 201

# --- ADMIN AUTHENTICATION ---
# Decorator untuk memeriksa apakah admin sudah login
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ADMIN ARTICLE MANAGEMENT ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            session['admin_role'] = admin.role # <-- SIMPAN ROLE DI SESSION
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Username atau password salah.')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear() # Hapus semua data dari session
    return redirect(url_for('admin_login'))

# Halaman untuk menampilkan semua artikel dan link untuk mengelolanya
@app.route('/admin/articles')
@admin_login_required
def manage_articles():
    articles = Article.query.order_by(Article.created_at.desc()).all()
    return render_template('manage_articles.html', articles=articles)

# Halaman untuk membuat artikel baru (menampilkan form)
@app.route('/admin/articles/new', methods=['GET'])
@admin_login_required
def new_article_form():
    return render_template('article_form.html', form_title="Buat Artikel Baru", article=None)

# Endpoint untuk memproses data dari form artikel baru
# Di app.py

# Definisikan folder upload
UPLOAD_FOLDER = os.path.join(app.root_path, 'static/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Endpoint untuk memproses data dari form artikel baru
@app.route('/admin/articles/new', methods=['POST'])
@admin_login_required
def add_new_article():
    title = request.form.get('title')
    content = request.form.get('content')
    video_url = request.form.get('video_url')
    
    image_file = request.files.get('image_file')
    image_filename = None

    if image_file and image_file.filename != '':
        image_filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

    new_article = Article(
        title=title, 
        content=content, 
        video_url=video_url, 
        image_filename=image_filename
    )
    db.session.add(new_article)
    db.session.commit()
    return redirect(url_for('manage_articles'))

# Endpoint untuk memproses data dari form edit artikel
@app.route('/admin/articles/edit/<int:article_id>', methods=['POST'])
@admin_login_required
def update_article(article_id):
    article = Article.query.get_or_404(article_id)
    article.title = request.form.get('title')
    article.content = request.form.get('content')
    article.video_url = request.form.get('video_url')

    image_file = request.files.get('image_file')
    if image_file and image_file.filename != '':
        image_filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        article.image_filename = image_filename # Update nama file jika ada gambar baru

    db.session.commit()
    return redirect(url_for('manage_articles'))

# Halaman untuk mengedit artikel (menampilkan form dengan data lama)
@app.route('/admin/articles/edit/<int:article_id>', methods=['GET'])
@admin_login_required
def edit_article_form(article_id):
    article = Article.query.get_or_404(article_id)
    return render_template('article_form.html', form_title="Edit Artikel", article=article)

# Endpoint untuk menghapus artikel
@app.route('/admin/articles/delete/<int:article_id>', methods=['POST'])
@admin_login_required
def delete_article(article_id):
    article = Article.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    return redirect(url_for('manage_articles'))

@app.route('/admin/dashboard')
@admin_login_required
def admin_dashboard():
    # Untuk saat ini, kita tidak amankan. Di produksi, ini harus ada login admin.
    unanswered_questions = Question.query.filter_by(status='Belum Dijawab').order_by(Question.created_at.asc()).all()
    return render_template('admin_dashboard.html', questions=unanswered_questions)

# Halaman untuk melihat detail dan menjawab satu pertanyaan
@app.route('/admin/question/<int:question_id>', methods=['GET', 'POST'])
@admin_login_required
def answer_question(question_id):
    question = Question.query.get_or_404(question_id)
    if request.method == 'POST':
        answer_text = request.form.get('answer_text')
        if answer_text:
            question.answer_text = answer_text
            question.status = 'Dijawab'
            question.answered_by = session.get('admin_username') # <-- CATAT SIAPA YANG MENJAWAB
            db.session.commit()
            return redirect(url_for('admin_dashboard'))
    return render_template('answer_question.html', question=question)

@app.route('/admin/manage-users', methods=['GET', 'POST'])
@admin_login_required
def manage_users():
    # Hanya superadmin yang boleh mengakses halaman ini
    if session.get('admin_role') != 'superadmin':
        flash("Anda tidak memiliki izin untuk mengakses halaman ini.")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'ahli') # Default role adalah ahli
        if username and password:
            existing_user = Admin.query.filter_by(username=username).first()
            if not existing_user:
                new_admin = Admin(username=username, password=password, role=role)
                db.session.add(new_admin)
                db.session.commit()
                flash(f"Akun '{username}' berhasil dibuat.")
            else:
                flash(f"Username '{username}' sudah digunakan.")
        return redirect(url_for('manage_users'))

    users = Admin.query.all()
    return render_template('manage_users.html', users=users)

@app.route('/admin/homepage', methods=['GET', 'POST'])
@admin_login_required
def edit_homepage():
    # Cari konten dengan id=1, atau buat baru jika belum ada
    content = HomePageContent.query.get(1)
    if not content:
        content = HomePageContent(id=1, title="", content="")
        db.session.add(content)
        db.session.commit()

    if request.method == 'POST':
        content.title = request.form.get('title')
        content.content = request.form.get('content')

        image_file = request.files.get('image_file')
        if image_file and image_file.filename != '':
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
            content.image_filename = image_filename

        db.session.commit()
        flash("Konten halaman utama berhasil diperbarui.")
        return redirect(url_for('edit_homepage'))

    return render_template('edit_homepage.html', content=content)

@app.route('/update-fcm-token', methods=['POST'])
@jwt_required()
def update_fcm_token():
    current_user_id = get_jwt_identity()
    user = RemajaPutri.query.get(int(current_user_id))
    if not user:
        return jsonify({"msg": "Pengguna tidak ditemukan"}), 404

    data = request.get_json()
    fcm_token = data.get('fcm_token')
    if fcm_token:
        user.fcm_token = fcm_token
        db.session.commit()
        return jsonify({"msg": "FCM token berhasil diperbarui"}), 200
    
    return jsonify({"msg": "FCM token tidak ada"}), 400
# --- PERBAIKAN KUNCI #1: HAPUS BLOK DI BAWAH INI ---
# Blok if __name__ == '__main__': tidak diperlukan dan bisa menyebabkan konflik
# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
#     app.run(debug=True)