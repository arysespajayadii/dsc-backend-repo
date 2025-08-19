from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager
from datetime import datetime
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from scipy import stats, linalg
import os
import mistune
from sqlalchemy import func


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
    points = db.Column(db.Integer, default=0) 
    fcm_token = db.Column(db.String(255), nullable=True, unique=True)
    profile_image_filename = db.Column(db.String(255), nullable=True)
    # --- JADWAL MINUM TTD ---
    # Menyimpan hari dalam seminggu (0=Senin, 1=Selasa, dst.)
    # Disimpan sebagai string yang dipisahkan koma, misal: "0" atau "0,3"
    jadwal_ttd = db.Column(db.String(20), default='0', nullable=False) # Default: Setiap Senin
    tanggal_lahir = db.Column(db.Date, nullable=True) 
    jenis_kelamin = db.Column(db.String(1), nullable=True) 
    logs = db.relationship('DailyLog', backref='pemilik', lazy=True)

    def __init__(self, username, password):
        self.username = username
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

# Di app.py, ganti class DailyLog yang lama dengan ini:

class DailyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.Date, nullable=False)
    # Kolom 'minum_ttd' tidak lagi diperlukan, digantikan oleh 'status'
    # minum_ttd = db.Column(db.Boolean, default=False) 
    
    # --- KOLOM BARU ---
    dosis = db.Column(db.String(50), nullable=True) # 
    status = db.Column(db.String(50), default='Belum dicatat', nullable=False) # Contoh: 'Diminum', 'Lupa', 'Ditunda'
    jam_konsumsi = db.Column(db.Time, nullable=True)
    efek_samping = db.Column(db.Text, nullable=True)
    alasan_lupa = db.Column(db.Text, nullable=True)
    # ------------------

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
    
# Model untuk Log Asupan Gizi Harian
class NutritionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.Date, nullable=False, unique=True) # Hanya satu log per hari
    user_id = db.Column(db.Integer, db.ForeignKey('remaja_putri.id'), nullable=False)
    
    # Komponen "Piring Makanku"
    karbohidrat = db.Column(db.Boolean, default=False)
    lauk_hewani = db.Column(db.Boolean, default=False)
    lauk_nabati = db.Column(db.Boolean, default=False)
    sayur = db.Column(db.Boolean, default=False)
    buah = db.Column(db.Boolean, default=False)
    
    # Komponen Tambahan
    camilan_manis = db.Column(db.Integer, default=0) # Untuk menghitung berapa kali
    minuman_manis = db.Column(db.Integer, default=0)
    
# Model untuk Skrining Kesehatan Berkala
class HealthScreening(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('remaja_putri.id'), nullable=False)
    tanggal_skrining = db.Column(db.Date, nullable=False)
    
    # Data Antropometri
    berat_badan = db.Column(db.Float, nullable=True) # dalam kg
    tinggi_badan = db.Column(db.Float, nullable=True) # dalam cm
    imt = db.Column(db.Float, nullable=True) # Indeks Massa Tubuh (dihitung otomatis)
    bmi_zscore = db.Column(db.Float, nullable=True)
    
    # Data Lainnya
    kadar_hb = db.Column(db.Float, nullable=True) # dalam g/dL
    riwayat_haid = db.Column(db.String(255), nullable=True) # Teks singkat

# Model untuk menghubungkan Artikel dengan Kuis
class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), unique=True, nullable=False)
    questions = db.relationship('QuizQuestion', backref='quiz', lazy=True, cascade="all, delete-orphan")

# Model untuk satu pertanyaan dalam sebuah kuis
class QuizQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    question_text = db.Column(db.String(500), nullable=False)
    choices = db.relationship('QuizChoice', backref='question', lazy=True, cascade="all, delete-orphan")

# Model untuk pilihan jawaban dalam sebuah pertanyaan
class QuizChoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('quiz_question.id'), nullable=False)
    choice_text = db.Column(db.String(200), nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)

# Model untuk mencatat hasil kuis pengguna
class UserQuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('remaja_putri.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False) # Skor (misal: 80, 100)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
# --- Level akun flutter ---
def get_user_level(points):
    """Menentukan level dan gelar pengguna berdasarkan poin."""
    if points >= 300:
        return "Ratu Anti-Anemia"
    elif points >= 100:
        return "Ksatria Sehat"
    else:
        return "Pemula Gizi"

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
    current_user_id = get_jwt_identity()
    data = request.get_json()
    today_date = datetime.utcnow().date()
    user = RemajaPutri.query.get(int(current_user_id))
    if not user:
        return jsonify({"msg": "Pengguna tidak ditemukan."}), 404

    # Ambil semua data baru dari request
    status = data.get('status')
    efek_samping = data.get('efek_samping')
    alasan_lupa = data.get('alasan_lupa')
    dosis = data.get('dosis')
    
    # Ambil dan konversi jam_konsumsi jika ada
    jam_konsumsi_str = data.get('jam_konsumsi')
    jam_konsumsi = None
    if jam_konsumsi_str:
        try:
            jam_konsumsi = datetime.strptime(jam_konsumsi_str, '%H:%M').time()
        except ValueError:
            # Abaikan jika formatnya salah
            pass

    today_log = DailyLog.query.filter_by(user_id=user.id, tanggal=today_date).first()

    if today_log:
        # --- LOGIKA UPDATE ---
        today_log.status = status
        today_log.jam_konsumsi = jam_konsumsi
        today_log.efek_samping = efek_samping
        today_log.alasan_lupa = alasan_lupa
        today_log.dosis = dosis 
        message = "Log hari ini berhasil diperbarui."
        status_code = 200
    else:
        # --- LOGIKA CREATE ---
        new_log = DailyLog(
            tanggal=today_date,
            status=status,
            jam_konsumsi=jam_konsumsi,
            efek_samping=efek_samping,
            alasan_lupa=alasan_lupa,
            dosis=dosis,
            user_id=user.id
        )
        db.session.add(new_log)
        
        # Poin hanya diberikan jika statusnya 'Diminum'
        if status == 'Diminum':
            if user.points is None: user.points = 0
            user.points += 10
        
        message = "Log berhasil ditambahkan!"
        status_code = 201
            
    db.session.commit()
    return jsonify({"msg": message}), status_code

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

# Endpoint untuk mendapatkan atau membuat log gizi hari ini
@app.route('/nutrition-log/today', methods=['GET'])
@jwt_required()
def get_today_nutrition_log():
    current_user_id = get_jwt_identity()
    today_date = datetime.utcnow().date()
    
    log = NutritionLog.query.filter_by(user_id=int(current_user_id), tanggal=today_date).first()
    
    if not log:
        # Jika belum ada log hari ini, buat yang baru dengan nilai default
        log = NutritionLog(user_id=int(current_user_id), tanggal=today_date)
        db.session.add(log)
        db.session.commit()
        
    return jsonify({
        'karbohidrat': log.karbohidrat, 'lauk_hewani': log.lauk_hewani,
        'lauk_nabati': log.lauk_nabati, 'sayur': log.sayur, 'buah': log.buah,
        'camilan_manis': log.camilan_manis, 'minuman_manis': log.minuman_manis
    })

@app.route('/screening', methods=['POST'])
@jwt_required()
def add_screening():
    current_user_id = get_jwt_identity()
    user = RemajaPutri.query.get(int(current_user_id))
    if not user:
        return jsonify({"msg": "Pengguna tidak ditemukan"}), 404
        
    data = request.get_json()
    berat_badan = data.get('berat_badan')
    tinggi_badan = data.get('tinggi_badan')
    imt = None
    bmi_zscore = None
    
    if berat_badan and tinggi_badan and user.tanggal_lahir:
        try:
            berat = float(berat_badan)
            tinggi_cm = float(tinggi_badan)
            tinggi_m = tinggi_cm / 100
            imt = round(berat / (tinggi_m * tinggi_m), 2)
            
            # Hitung umur dalam bulan
            today = datetime.utcnow().date()
            age_in_days = (today - user.tanggal_lahir).days
            age_in_months = age_in_days / 30.4375
            
            # Hitung z-score (asumsi jenis kelamin 'P' untuk perempuan)
            # Library pyzscore menggunakan indikator: 'bmi_for_age'
            # Sex: 1 untuk laki-laki, 2 untuk perempuan
            sex = 2 if user.jenis_kelamin == 'P' else 1
            bmi_zscore = round(zscore.get_zscore(
                indicator='bmi_for_age', 
                measurement=imt, 
                age_in_months=age_in_months, 
                sex=sex
            ), 2)

        except Exception as e:
            print(f"Error calculating z-score: {e}")
            imt = None
            bmi_zscore = None

    new_screening = HealthScreening(
        user_id=int(current_user_id),
        tanggal_skrining=datetime.utcnow().date(),
        berat_badan=berat_badan,
        tinggi_badan=tinggi_badan,
        imt=imt,
        bmi_zscore=bmi_zscore,
        kadar_hb=data.get('kadar_hb'),
        riwayat_haid=data.get('riwayat_haid')
    )
    db.session.add(new_screening)
    db.session.commit()
    
    return jsonify({"msg": "Data skrining berhasil disimpan!", "imt": imt, "zscore": bmi_zscore}), 201
# Endpoint untuk mengambil riwayat skrining pengguna
@app.route('/screening', methods=['GET'])
@jwt_required()
def get_screening_history():
    current_user_id = get_jwt_identity()
    history = HealthScreening.query.filter_by(user_id=int(current_user_id)).order_by(HealthScreening.tanggal_skrining.desc()).all()
    
    return jsonify([{
        'tanggal_skrining': record.tanggal_skrining.strftime('%d %B %Y'),
        'berat_badan': record.berat_badan,
        'tinggi_badan': record.tinggi_badan,
        'imt': record.imt,
        'kadar_hb': record.kadar_hb,
        'riwayat_haid': record.riwayat_haid
    } for record in history])
    
# Endpoint untuk memperbarui log gizi hari ini
@app.route('/nutrition-log/today', methods=['POST'])
@jwt_required()
def update_today_nutrition_log():
    current_user_id = get_jwt_identity()
    today_date = datetime.utcnow().date()
    data = request.get_json()
    
    log = NutritionLog.query.filter_by(user_id=int(current_user_id), tanggal=today_date).first()
    if not log:
        return jsonify({"msg": "Log tidak ditemukan"}), 404
        
    # Perbarui semua field dari data yang dikirim
    log.karbohidrat = data.get('karbohidrat', log.karbohidrat)
    log.lauk_hewani = data.get('lauk_hewani', log.lauk_hewani)
    log.lauk_nabati = data.get('lauk_nabati', log.lauk_nabati)
    log.sayur = data.get('sayur', log.sayur)
    log.buah = data.get('buah', log.buah)
    log.camilan_manis = data.get('camilan_manis', log.camilan_manis)
    log.minuman_manis = data.get('minuman_manis', log.minuman_manis)
    
    db.session.commit()
    return jsonify({"msg": "Log gizi berhasil diperbarui"}), 200

# Di app.py

# Endpoint untuk mengambil data kuis berdasarkan ID artikel
@app.route('/quiz/for-article/<int:article_id>', methods=['GET'])
@jwt_required()
def get_quiz_for_article(article_id):
    quiz = Quiz.query.filter_by(article_id=article_id).first()
    if not quiz:
        return jsonify({"msg": "Tidak ada kuis untuk artikel ini"}), 404

    questions_data = []
    for q in quiz.questions:
        choices_data = [{'id': c.id, 'text': c.choice_text} for c in q.choices]
        questions_data.append({'id': q.id, 'text': q.question_text, 'choices': choices_data})

    return jsonify({'quiz_id': quiz.id, 'questions': questions_data})

# Endpoint untuk pengguna mengirimkan jawaban kuis
@app.route('/quiz/submit/<int:quiz_id>', methods=['POST'])
@jwt_required()
def submit_quiz(quiz_id):
    current_user_id = get_jwt_identity()
    data = request.get_json() # Expected format: {'answers': { 'question_id': 'choice_id', ... }}
    answers = data.get('answers', {})
    
    correct_answers = 0
    total_questions = 0

    for question_id, choice_id in answers.items():
        total_questions += 1
        choice = QuizChoice.query.get(int(choice_id))
        if choice and choice.question_id == int(question_id) and choice.is_correct:
            correct_answers += 1

    score = 0
    if total_questions > 0:
        score = int((correct_answers / total_questions) * 100)

    # Simpan hasil kuis
    new_attempt = UserQuizAttempt(
        user_id=int(current_user_id),
        quiz_id=quiz_id,
        score=score
    )
    db.session.add(new_attempt)
    db.session.commit()

    return jsonify({"msg": "Kuis berhasil diselesaikan!", "score": score})

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
    user = RemajaPutri.query.get_or_404(int(current_user_id)) # Pastikan ID adalah integer
    
    # Panggil fungsi untuk mendapatkan level pengguna
    user_level = get_user_level(user.points or 0)

    profile_data = {
        'username': user.username,
        'points': user.points or 0,
        'join_date': user.created_at.strftime('%d %B %Y'),
        'profile_image_filename': user.profile_image_filename,
        'level_title': user_level # <-- KIRIM DATA LEVEL DI SINI
        # Kita tidak lagi mengirim 'badges'
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

@app.route('/admin/app-users')
@admin_login_required
def manage_app_users():
    # Hanya superadmin yang boleh mengakses
    if session.get('admin_role') != 'superadmin':
        flash("Anda tidak memiliki izin untuk mengakses halaman ini.")
        return redirect(url_for('admin_dashboard'))

    all_users = RemajaPutri.query.order_by(RemajaPutri.created_at.desc()).all()
    
    # Logika untuk mencari pengguna yang belum log hari ini
    today_date = datetime.utcnow().date()
    users_who_logged_today_ids = [
        log.user_id for log in DailyLog.query.filter_by(tanggal=today_date).all()
    ]
    
    users_not_logged_today = RemajaPutri.query.filter(
        RemajaPutri.id.notin_(users_who_logged_today_ids)
    ).all()

    return render_template(
        'manage_app_users.html', 
        all_users=all_users, 
        users_not_logged_today=users_not_logged_today
    )

# Endpoint untuk memproses reset password pengguna
@app.route('/admin/app-users/reset-password/<int:user_id>', methods=['POST'])
@admin_login_required
def reset_user_password(user_id):
    if session.get('admin_role') != 'superadmin':
        flash("Anda tidak memiliki izin untuk melakukan aksi ini.")
        return redirect(url_for('manage_app_users'))

    user = RemajaPutri.query.get_or_404(user_id)
    new_password = request.form.get('new_password')

    if not new_password or len(new_password) < 6:
        flash("Password baru harus memiliki minimal 6 karakter.")
        return redirect(url_for('manage_app_users'))

    # Hash password baru dan simpan
    user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()

    flash(f"Password untuk pengguna '{user.username}' telah berhasil direset.")
    return redirect(url_for('manage_app_users'))

@app.route('/admin/reset-admin-password/<int:admin_id>', methods=['POST'])
@admin_login_required
def reset_admin_password(admin_id):
    # Pastikan hanya superadmin yang bisa melakukan ini
    if session.get('admin_role') != 'superadmin':
        flash("Anda tidak memiliki izin untuk melakukan aksi ini.")
        return redirect(url_for('manage_users'))

    admin_to_reset = Admin.query.get_or_404(admin_id)
    new_password = request.form.get('new_password')

    if not new_password or len(new_password) < 6:
        flash("Password baru harus memiliki minimal 6 karakter.")
        return redirect(url_for('manage_users'))

    # Hash password baru dan perbarui di database
    admin_to_reset.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()

    flash(f"Password untuk '{admin_to_reset.username}' telah berhasil direset.")
    return redirect(url_for('manage_users'))

# Di app.py, di dalam bagian Admin Routes

# Halaman utama untuk mengelola kuis sebuah artikel
@app.route('/admin/quiz/manage/<int:article_id>')
@admin_login_required
def manage_quiz(article_id):
    article = Article.query.get_or_404(article_id)
    # Cek apakah artikel sudah punya kuis, jika belum, buatkan
    quiz = Quiz.query.filter_by(article_id=article.id).first()
    if not quiz:
        quiz = Quiz(article_id=article.id)
        db.session.add(quiz)
        db.session.commit()
    return render_template('manage_quiz.html', article=article, quiz=quiz)

# Endpoint untuk menambah pertanyaan baru ke kuis
@app.route('/admin/question/add/<int:quiz_id>', methods=['POST'])
@admin_login_required
def add_quiz_question(quiz_id):
    question_text = request.form.get('question_text')
    if question_text:
        new_question = QuizQuestion(quiz_id=quiz_id, question_text=question_text)
        db.session.add(new_question)
        db.session.commit()
        # Tambahkan 4 pilihan jawaban kosong untuk pertanyaan baru ini
        for _ in range(4):
            db.session.add(QuizChoice(question_id=new_question.id, choice_text=""))
        db.session.commit()
    quiz = Quiz.query.get_or_404(quiz_id)
    return redirect(url_for('manage_quiz', article_id=quiz.article_id))

# Endpoint untuk menyimpan/mengupdate pilihan jawaban
@app.route('/admin/choices/update/<int:question_id>', methods=['POST'])
@admin_login_required
def update_quiz_choices(question_id):
    question = QuizQuestion.query.get_or_404(question_id)
    correct_choice_id = request.form.get('is_correct')

    for choice in question.choices:
        choice.choice_text = request.form.get(f'choice_text_{choice.id}')
        choice.is_correct = (str(choice.id) == correct_choice_id)
    
    db.session.commit()
    return redirect(url_for('manage_quiz', article_id=question.quiz.article_id))

@app.route('/admin/reports')
@admin_login_required
def reports():
    # Laporan 1: Total Pengguna
    total_users = RemajaPutri.query.count()

    # Laporan 2: Kepatuhan TTD (30 hari terakhir)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    ttd_compliance = db.session.query(
        DailyLog.status, func.count(DailyLog.id)
    ).filter(DailyLog.tanggal >= thirty_days_ago).group_by(DailyLog.status).all()
    
    # Laporan 3: Rata-rata Skor Kuis
    quiz_performance = db.session.query(
        Article.title, func.avg(UserQuizAttempt.score).label('avg_score')
    ).join(Quiz, Quiz.article_id == Article.id).join(UserQuizAttempt, UserQuizAttempt.quiz_id == Quiz.id).group_by(Article.title).all()

    return render_template(
        'reports.html', 
        total_users=total_users, 
        ttd_compliance=dict(ttd_compliance),
        quiz_performance=quiz_performance
    )


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

@app.route('/profile-picture', methods=['POST'])
@jwt_required()
def upload_profile_picture():
    current_user_id = get_jwt_identity()
    user = RemajaPutri.query.get(int(current_user_id))
    if not user:
        return jsonify({"msg": "Pengguna tidak ditemukan"}), 404

    if 'profile_picture' not in request.files:
        return jsonify({"msg": "Tidak ada file gambar yang dikirim"}), 400

    file = request.files['profile_picture']
    if file.filename == '':
        return jsonify({"msg": "Tidak ada file yang dipilih"}), 400

    if file:
        # Buat nama file yang aman dan unik untuk menghindari konflik
        filename = secure_filename(f"user_{user.id}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Simpan nama file ke database
        user.profile_image_filename = filename
        db.session.commit()
        
        return jsonify({"msg": "Foto profil berhasil diperbarui!", "filename": filename}), 200
    
    return jsonify({"msg": "Gagal mengunggah file"}), 500
# --- PERBAIKAN KUNCI #1: HAPUS BLOK DI BAWAH INI ---
# Blok if __name__ == '__main__': tidak diperlukan dan bisa menyebabkan konflik
# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
#     app.run(debug=True)