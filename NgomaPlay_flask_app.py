NgomaPlay_flask_app.
""" NgomaPlay - Prototype Flask app Fichier unique pour démarrer le site musical décrit avec :

Pages : accueil, espace artiste, espace auditeur, page de lecture, panneau admin (créateur)

Base de données SQLite avec SQLAlchemy

Authentification basique avec Flask-Login

Upload de fichiers audio (mp3,wav)

Calcul simple des gains par écoute (configurable depuis le panneau du créateur)


INSTRUCTIONS D'INSTALLATION (terminal) :

1. Crée un virtualenv et active-le python3 -m venv venv source venv/bin/activate   # Mac/Linux venv\Scripts\activate    # Windows


2. Installe les dépendances pip install Flask Flask-SQLAlchemy Flask-Login python-dotenv


3. Lance l'application export FLASK_APP=NgomaPlay_flask_app.py export FLASK_ENV=development flask run --host=0.0.0.0 --port=5000 (ou) python NgomaPlay_flask_app.py



NOTE : Ceci est un prototype pour développement local. Pour production, pense à :

stocker les fichiers audio sur un stockage spécialisé (S3, Cloud Storage)

intégrer un vrai prestataire de paiement (Airtel Money / Moov Money / Stripe)

sécuriser l'authentification et les permissions

tests et audits légaux (droits d'auteur)


"""

from flask import Flask, render_template_string, request, redirect, url_for, flash, send_from_directory, abort from flask_sqlalchemy import SQLAlchemy from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user from werkzeug.utils import secure_filename from werkzeug.security import generate_password_hash, check_password_hash import os from datetime import datetime

----- Configuration -----

BASE_DIR = os.path.dirname(os.path.abspath(file)) UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads') os.makedirs(UPLOAD_FOLDER, exist_ok=True) ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg'}

app = Flask(name) app.config['SECRET_KEY'] = 'change_this_secret_in_production' app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'ngomaplay.db') app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app) login_manager = LoginManager(app) login_manager.login_view = 'login'

----- Models -----

class User(db.Model, UserMixin): id = db.Column(db.Integer, primary_key=True) username = db.Column(db.String(150), unique=True, nullable=False) email = db.Column(db.String(200), unique=True, nullable=True) password_hash = db.Column(db.String(200), nullable=False) is_artist = db.Column(db.Boolean, default=False) is_admin = db.Column(db.Boolean, default=False)  # Creator / admin created_at = db.Column(db.DateTime, default=datetime.utcnow)

def set_password(self, password):
    self.password_hash = generate_password_hash(password)

def check_password(self, password):
    return check_password_hash(self.password_hash, password)

class Track(db.Model): id = db.Column(db.Integer, primary_key=True) title = db.Column(db.String(300), nullable=False) filename = db.Column(db.String(300), nullable=False) cover = db.Column(db.String(300), nullable=True) description = db.Column(db.Text, nullable=True) artist_id = db.Column(db.Integer, db.ForeignKey('user.id')) plays = db.Column(db.Integer, default=0) revenue_cfa = db.Column(db.Integer, default=0)  # revenue in FCFA for artist created_at = db.Column(db.DateTime, default=datetime.utcnow)

artist = db.relationship('User', backref='tracks')

class Setting(db.Model): id = db.Column(db.Integer, primary_key=True) key = db.Column(db.String(100), unique=True) value = db.Column(db.String(200))

----- Utilities -----

@login_manager.user_loader def load_user(user_id): return User.query.get(int(user_id))

def allowed_file(filename): return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_setting(key, default=None): s = Setting.query.filter_by(key=key).first() return s.value if s else default

def set_setting(key, value): s = Setting.query.filter_by(key=key).first() if s: s.value = value else: s = Setting(key=key, value=value) db.session.add(s) db.session.commit()

----- Routes -----

@app.route('/') def index(): tracks = Track.query.order_by(Track.created_at.desc()).limit(20).all() return render_template_string(TEMPLATES['index'], tracks=tracks)

@app.route('/register', methods=['GET','POST']) def register(): if request.method == 'POST': username = request.form['username'] email = request.form.get('email') password = request.form['password'] is_artist = True if request.form.get('is_artist') == 'on' else False if User.query.filter_by(username=username).first(): flash('Nom d'utilisateur déjà pris') return redirect(url_for('register')) u = User(username=username, email=email, is_artist=is_artist) u.set_password(password) db.session.add(u) db.session.commit() flash('Compte créé. Connecte-toi.') return redirect(url_for('login')) return render_template_string(TEMPLATES['register'])

@app.route('/login', methods=['GET','POST']) def login(): if request.method == 'POST': username = request.form['username'] password = request.form['password'] user = User.query.filter_by(username=username).first() if user and user.check_password(password): login_user(user) flash('Connecté') return redirect(url_for('index')) flash('Identifiants invalides') return redirect(url_for('login')) return render_template_string(TEMPLATES['login'])

@app.route('/logout') @login_required def logout(): logout_user() flash('Déconnecté') return redirect(url_for('index'))

@app.route('/artist/dashboard') @login_required def artist_dashboard(): if not current_user.is_artist: abort(403) return render_template_string(TEMPLATES['artist_dashboard'], user=current_user)

@app.route('/upload', methods=['GET','POST']) @login_required def upload(): if not current_user.is_artist: flash('Seuls les artistes peuvent uploader') return redirect(url_for('index')) if request.method == 'POST': title = request.form['title'] description = request.form.get('description') file = request.files.get('file') if not file or not allowed_file(file.filename): flash('Fichier audio invalide') return redirect(url_for('upload')) filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{file.filename}") path = os.path.join(app.config['UPLOAD_FOLDER'], filename) file.save(path) t = Track(title=title, filename=filename, description=description, artist_id=current_user.id) db.session.add(t) db.session.commit() flash('Piste uploadée') return redirect(url_for('artist_dashboard')) return render_template_string(TEMPLATES['upload'])

@app.route('/tracks/int:track_id/stream') def stream_track(track_id): t = Track.query.get_or_404(track_id) # incremente les plays et calcule le revenu per_play_fcfa = int(get_setting('per_play_fcfa', '5')) site_commission_percent = int(get_setting('site_commission_percent', '10')) artist_share = per_play_fcfa * (100 - site_commission_percent) // 100 t.plays += 1 t.revenue_cfa += artist_share db.session.commit() return send_from_directory(app.config['UPLOAD_FOLDER'], t.filename)

@app.route('/track/int:track_id') def show_track(track_id): t = Track.query.get_or_404(track_id) return render_template_string(TEMPLATES['track'], track=t)

Admin / Creator panel

@app.route('/admin') @login_required def admin_dashboard(): if not current_user.is_admin: abort(403) users_count = User.query.count() artists_count = User.query.filter_by(is_artist=True).count() total_tracks = Track.query.count() total_plays = db.session.query(db.func.sum(Track.plays)).scalar() or 0 total_revenue = db.session.query(db.func.sum(Track.revenue_cfa)).scalar() or 0 per_play = get_setting('per_play_fcfa', '5') commission = get_setting('site_commission_percent', '10') return render_template_string(TEMPLATES['admin_dashboard'], users_count=users_count, artists_count=artists_count, total_tracks=total_tracks, total_plays=total_plays, total_revenue=total_revenue, per_play=per_play, commission=commission)

@app.route('/admin/settings', methods=['POST']) @login_required def admin_settings(): if not current_user.is_admin: abort(403) per_play = request.form.get('per_play_fcfa') commission = request.form.get('site_commission_percent') if per_play: set_setting('per_play_fcfa', str(int(per_play))) if commission: set_setting('site_commission_percent', str(int(commission))) flash('Paramètres mis à jour') return redirect(url_for('admin_dashboard'))

Simple endpoint to download artist payouts report (CSV) - prototype

@app.route('/admin/payouts.csv') @login_required def admin_payouts(): if not current_user.is_admin: abort(403) artists = User.query.filter_by(is_artist=True).all() lines = ['artist_username;email;tracks;total_revenue_fcfa'] for a in artists: rev = sum([t.revenue_cfa for t in a.tracks]) lines.append(f"{a.username};{a.email or '-'};{len(a.tracks)};{rev}") return ('\n'.join(lines), 200, { 'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename="payouts.csv"' })

Route to serve uploaded covers (if any)

@app.route('/uploads/path:filename') def uploaded_file(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

----- Minimal templates stored in a dict (for prototype) -----

TEMPLATES = {} TEMPLATES['base'] = ''' <!doctype html>

<html>
<head>
  <meta charset="utf-8">
  <title>NgomaPlay - Prototype</title>
  <style>
    body{font-family:Arial,Helvetica,sans-serif;max-width:900px;margin:0 auto;padding:20px}
    header{display:flex;justify-content:space-between;align-items:center}
    nav a{margin-right:10px}
    .track{border-bottom:1px solid #ddd;padding:8px 0}
    .btn{display:inline-block;padding:6px 10px;border-radius:6px;background:#222;color:#fff;text-decoration:none}
  </style>
</head>
<body>
<header>
  <h1><a href="/">NgomaPlay</a></h1>
  <nav>
    {% if current_user.is_authenticated %}
      Bonjour {{ current_user.username }} |
      <a href="/logout">Déconnexion</a>
      {% if current_user.is_artist %} | <a href="/artist/dashboard">Mon Espace Artiste</a>{% endif %}
      {% if current_user.is_admin %} | <a href="/admin">Panneau Créateur</a>{% endif %}
    {% else %}
      <a href="/login">Se connecter</a> | <a href="/register">S'inscrire</a>
    {% endif %}
  </nav>
</header>
<hr>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>
    {% for m in messages %}
      <li>{{ m }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}{% block content %}{% endblock %}

<footer>
  <hr>
  <small>Prototype - NgomaPlay. Pour production, sécuriser et déployer correctement.</small>
</footer>
</body>
</html>
'''TEMPLATES['index'] = '''{% extends 'base' %}{% block content %}

<h2>Dernières musiques</h2>
{% for t in tracks %}
  <div class="track">
    <strong>{{ t.title }}</strong> — {{ t.artist.username }}<br>
    <a href="/track/{{ t.id }}">Ouvrir</a> • {{ t.plays }} écoutes
  </div>
{% else %}
  <p>Aucune piste pour le moment. Les artistes peuvent <a href="/register">créer un compte</a> et uploader.</p>
{% endfor %}
{% endblock %}'''TEMPLATES['register'] = '''{% extends 'base' %}{% block content %}

<h2>Créer un compte</h2>
<form method="post">
  <label>Nom d'utilisateur<br><input name="username" required></label><br>
  <label>Email (optionnel)<br><input name="email"></label><br>
  <label>Mot de passe<br><input name="password" type="password" required></label><br>
  <label><input type="checkbox" name="is_artist"> Je suis artiste</label><br>
  <button>Créer</button>
</form>
{% endblock %}'''TEMPLATES['login'] = '''{% extends 'base' %}{% block content %}

<h2>Se connecter</h2>
<form method="post">
  <label>Nom d'utilisateur<br><input name="username" required></label><br>
  <label>Mot de passe<br><input name="password" type="password" required></label><br>
  <button>Se connecter</button>
</form>
{% endblock %}'''TEMPLATES['artist_dashboard'] = '''{% extends 'base' %}{% block content %}

<h2>Mon Espace Artiste</h2>
<p><a href="/upload" class="btn">Uploader un nouveau son</a></p>
<h3>Mes pistes</h3>
<ul>
{% for t in user.tracks %}
  <li>{{ t.title }} — {{ t.plays }} écoutes — {{ t.revenue_cfa }} FCFA</li>
{% else %}
  <li>Aucune piste encore.</li>
{% endfor %}
</ul>
{% endblock %}'''TEMPLATES['upload'] = '''{% extends 'base' %}{% block content %}

<h2>Uploader une piste</h2>
<form method="post" enctype="multipart/form-data">
  <label>Titre<br><input name="title" required></label><br>
  <label>Description<br><textarea name="description"></textarea></label><br>
  <label>Fichier audio (mp3,wav,ogg)<br><input type="file" name="file" required></label><br>
  <button>Uploader</button>
</form>
{% endblock %}'''TEMPLATES['track'] = '''{% extends 'base' %}{% block content %}

<h2>{{ track.title }}</h2>
<p>Par {{ track.artist.username }} • {{ track.plays }} écoutes • Gains artist: {{ track.revenue_cfa }} FCFA</p>
<audio controls>
  <source src="/tracks/{{ track.id }}/stream" type="audio/mpeg">
  Ton navigateur ne supporte pas l'audio.
</audio>
{% endblock %}'''TEMPLATES['admin_dashboard'] = '''{% extends 'base' %}{% block content %}

<h2>Panneau du Créateur</h2>
<p>Utilisateurs : {{ users_count }} | Artistes : {{ artists_count }} | Pistes : {{ total_tracks }}</p>
<p>Total écoutes : {{ total_plays }} • Total reversé aux artistes : {{ total_revenue }} FCFA</p>
<h3>Paramètres</h3>
<form action="/admin/settings" method="post">
  <label>Montant par écoute (FCFA)<br><input name="per_play_fcfa" value="{{ per_play }}"></label><br>
  <label>Commission du site (%)<br><input name="site_commission_percent" value="{{ commission }}"></label><br>
  <button>Enregistrer</button>
</form>
<p><a href="/admin/payouts.csv">Télécharger rapport payouts</a></p>
{% endblock %}'''----- Initialization helper -----

def init_db(): db.create_all() # create default settings if not exists if not get_setting('per_play_fcfa'): set_setting('per_play_fcfa', '5') if not get_setting('site_commission_percent'): set_setting('site_commission_percent', '10') # create default admin user if none if User.query.filter_by(is_admin=True).count() == 0: admin = User(username='deniro_admin', email='you@yourmail', is_admin=True) admin.set_password('change-me') db.session.add(admin) db.session.commit() print('Admin created: deniro_admin / change-me (change immediately)')

When running directly

if name == 'main': init_db() app.run(debug=True, host='0.0.0.0', port=5000)