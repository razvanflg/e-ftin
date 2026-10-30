import os, re, secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "e-ftin-ro-secret-2026-razvan")
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
ALLOWED_EXT = {'png','jpg','jpeg','webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'eftin.db')

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, nume TEXT NOT NULL, telefon TEXT, email TEXT, parola_hash TEXT NOT NULL, poza TEXT, rol TEXT DEFAULT 'ambele', data_creare TEXT, rating REAL DEFAULT 5.0, colete_duse INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS rute_sofer (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, de_unde TEXT, pana_unde TEXT, data_ruta TEXT, ora TEXT, locuri INTEGER DEFAULT 1, detalii TEXT, activa INTEGER DEFAULT 1)")
        c.execute("CREATE TABLE IF NOT EXISTS colete (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, de_unde TEXT, pana_unde TEXT, ce_contine TEXT, tip TEXT DEFAULT 'colet', greutate TEXT, telefon_contact TEXT, pret INTEGER, status TEXT DEFAULT 'postat', poza_predare TEXT, poza_livrare TEXT, sofer_id INTEGER, data_postare TEXT)")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB init error: {e}")

init_db()

class User(UserMixin):
    def __init__(self, row):
        self.id = row['id']
        self.nume = row['nume']
        self.telefon = row['telefon']
        self.email = row['email']
        self.poza = row['poza']
        self.rol = row['rol']
        self.rating = row['rating']
        self.colete_duse = row['colete_duse']

@login_manager.user_loader
def load_user(user_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        if row:
            return User(row)
    except:
        pass
    return None

def calc_pret(de_unde, pana_unde, tip):
    if tip == 'plic':
        return 12
    return 16 if de_unde.lower() != pana_unde.lower() else 10

def allowed_file(f):
    return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_EXT

@app.route('/')
def index():
    try:
        conn = get_db()
        rute = conn.execute("SELECT r.*, u.nume FROM rute_sofer r JOIN users u ON r.user_id=u.id WHERE r.activa=1 ORDER BY r.id DESC LIMIT 6").fetchall()
        colete = conn.execute("SELECT c.*, u.nume FROM colete c JOIN users u ON c.user_id=u.id WHERE c.status='postat' ORDER BY c.id DESC LIMIT 6").fetchall()
        conn.close()
    except:
        rute, colete = [], []
    return render_template('index.html', rute=rute, colete=colete)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        nume = request.form.get('nume','').strip()
        telefon = request.form.get('telefon','').strip()
        email = request.form.get('email','').strip() or None
        parola = request.form.get('parola','')
        rol = request.form.get('rol','ambele')
        if not nume or not parola or (not telefon and not email):
            flash("Completeaza numele, parola si telefon sau email.", "error")
            return redirect(url_for('register'))
        if telefon:
            telefon = re.sub(r'\D','',telefon)
        conn = get_db()
        try:
            exists = conn.execute("SELECT id FROM users WHERE telefon=? OR email=?", (telefon, email)).fetchone()
            if exists:
                flash("Telefonul sau emailul exista deja.", "error")
                conn.close()
                return redirect(url_for('register'))
            conn.execute("INSERT INTO users (nume, telefon, email, parola_hash, rol, data_creare) VALUES (?,?,?,?,?,?)",
                         (nume, telefon, email, generate_password_hash(parola), rol, datetime.now().isoformat()))
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE telefon=? OR email=?", (telefon, email)).fetchone()
            conn.close()
            login_user(User(row))
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Eroare: {e}", "error")
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier','').strip()
        parola = request.form.get('parola','')
        conn = get_db()
        try:
            if '@' not in identifier:
                digits = re.sub(r'\D','',identifier)
                row = conn.execute("SELECT * FROM users WHERE telefon LIKE ?", (f"%{digits}%",)).fetchone()
                if not row:
                    row = conn.execute("SELECT * FROM users WHERE email=?", (identifier,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM users WHERE email=?", (identifier,)).fetchone()
                if not row:
                    row = conn.execute("SELECT * FROM users WHERE telefon=?", (identifier,)).fetchone()
            conn.close()
            if row and check_password_hash(row['parola_hash'], parola):
                login_user(User(row))
                return redirect(url_for('dashboard'))
        except:
            pass
        flash("Date gresite.", "error")
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    my_rute = conn.execute("SELECT * FROM rute_sofer WHERE user_id=? ORDER BY id DESC", (current_user.id,)).fetchall()
    my_colete = conn.execute("SELECT * FROM colete WHERE user_id=? ORDER BY id DESC", (current_user.id,)).fetchall()
    matches_for_me = []
    for ruta in my_rute:
        if not ruta['activa']: continue
        cms = conn.execute("SELECT c.*, u.nume, u.telefon FROM colete c JOIN users u ON c.user_id=u.id WHERE c.status='postat' AND c.user_id!=?", (current_user.id,)).fetchall()
        for colet in cms:
            de, pana = colet['de_unde'].lower(), colet['pana_unde'].lower()
            rd, rp = ruta['de_unde'].lower(), ruta['pana_unde'].lower()
            if de in rd or de in rp or pana in rd or pana in rp or rd in de or rp in pana:
                matches_for_me.append({'ruta': ruta, 'colet': colet})
    soferi_for_my_colete = []
    for colet in my_colete:
        if colet['status'] != 'postat': continue
        rms = conn.execute("SELECT r.*, u.nume, u.telefon FROM rute_sofer r JOIN users u ON r.user_id=u.id WHERE r.activa=1 AND r.user_id!=?", (current_user.id,)).fetchall()
        for ruta in rms:
            de, pana = colet['de_unde'].lower(), colet['pana_unde'].lower()
            rd, rp = ruta['de_unde'].lower(), ruta['pana_unde'].lower()
            if de in rd or de in rp or pana in rd or pana in rp:
                soferi_for_my_colete.append({'colet': colet, 'ruta': ruta})
    conn.close()
    return render_template('dashboard.html', my_rute=my_rute, my_colete=my_colete, matches_for_me=matches_for_me, soferi_for_my_colete=soferi_for_my_colete)

@app.route('/profil', methods=['GET','POST'])
@login_required
def profil():
    conn = get_db()
    if request.method == 'POST':
        nume = request.form.get('nume','').strip()
        telefon = request.form.get('telefon','').strip()
        email = request.form.get('email','').strip() or None
        parola_noua = request.form.get('parola_noua','').strip()
        poza_path = None
        if 'poza' in request.files:
            f = request.files['poza']
            if f and f.filename and allowed_file(f.filename):
                fn = secure_filename(f"user_{current_user.id}_{secrets.token_hex(4)}.{f.filename.rsplit('.',1)[1].lower()}")
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                poza_path = f"uploads/{fn}"
        if poza_path:
            conn.execute("UPDATE users SET nume=?, telefon=?, email=?, poza=? WHERE id=?", (nume, telefon, email, poza_path, current_user.id))
        else:
            conn.execute("UPDATE users SET nume=?, telefon=?, email=? WHERE id=?", (nume, telefon, email, current_user.id))
        if parola_noua:
            conn.execute("UPDATE users SET parola_hash=? WHERE id=?", (generate_password_hash(parola_noua), current_user.id))
        conn.commit()
        conn.close()
        flash("Profil actualizat!", "success")
        return redirect(url_for('profil'))
    user_row = conn.execute("SELECT * FROM users WHERE id=?", (current_user.id,)).fetchone()
    conn.close()
    return render_template('profil.html', user=user_row)

@app.route('/sofer', methods=['GET','POST'])
@login_required
def sofer():
    if request.method == 'POST':
        conn = get_db()
        conn.execute("INSERT INTO rute_sofer (user_id, de_unde, pana_unde, data_ruta, ora, locuri, detalii) VALUES (?,?,?,?,?,?,?)",
                     (current_user.id, request.form.get('de_unde',''), request.form.get('pana_unde',''), request.form.get('data_ruta',''), request.form.get('ora',''), request.form.get('locuri','1'), request.form.get('detalii','')))
        conn.commit()
        conn.close()
        flash("Ruta adaugata!", "success")
        return redirect(url_for('dashboard'))
    return render_template('sofer.html')

@app.route('/colet', methods=['GET','POST'])
@login_required
def colet():
    if request.method == 'POST':
        pret = calc_pret(request.form.get('de_unde',''), request.form.get('pana_unde',''), request.form.get('tip','colet'))
        if request.form.get('tip','colet') == 'colet':
            pret = min(30, max(10, pret))
        conn = get_db()
        conn.execute("INSERT INTO colete (user_id, de_unde, pana_unde, ce_contine, tip, greutate, telefon_contact, pret, data_postare) VALUES (?,?,?,?,?,?,?,?,?)",
                     (current_user.id, request.form.get('de_unde',''), request.form.get('pana_unde',''), request.form.get('ce_contine',''), request.form.get('tip','colet'), request.form.get('greutate',''), request.form.get('telefon_contact',''), pret, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        flash(f"Colet postat! {pret} lei.", "success")
        return redirect(url_for('dashboard'))
    return render_template('colet.html')

@app.route('/admin')
def admin():
    if not current_user.is_authenticated or 'razvan' not in current_user.nume.lower():
        return "Nu ai acces", 403
    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    rute = conn.execute("SELECT r.*, u.nume FROM rute_sofer r JOIN users u ON r.user_id=u.id ORDER BY r.id DESC").fetchall()
    colete = conn.execute("SELECT c.*, u.nume FROM colete c JOIN users u ON c.user_id=u.id ORDER BY c.id DESC").fetchall()
    conn.close()
    return render_template('admin.html', users=users, rute=rute, colete=colete)

@app.errorhandler(500)
def err500(e):
    return f"<h1>500 - Eroare temporara</h1><p>{e}</p><p><a href='/'>Acasa</a></p>", 500

if __name__ == '__main__':
    app.run(debug=True)