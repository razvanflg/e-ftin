import os, re, secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "e-ftin-ro-secret-2026-razvan")
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
ALLOWED_EXT = {'png','jpg','jpeg','webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Trebuie sa te loghezi ca sa vezi dashboard-ul."

DB = 'eftin.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nume TEXT NOT NULL,
        telefon TEXT UNIQUE,
        email TEXT UNIQUE,
        parola_hash TEXT NOT NULL,
        poza TEXT,
        rol TEXT DEFAULT 'ambele',
        data_creare TEXT,
        rating REAL DEFAULT 5.0,
        colete_duse INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS rute_sofer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        de_unde TEXT,
        pana_unde TEXT,
        data_ruta TEXT,
        ora TEXT,
        locuri INTEGER DEFAULT 1,
        detalii TEXT,
        activa INTEGER DEFAULT 1,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS colete (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        de_unde TEXT,
        pana_unde TEXT,
        ce_contine TEXT,
        tip TEXT DEFAULT 'colet',
        greutate TEXT,
        telefon_contact TEXT,
        pret INTEGER,
        status TEXT DEFAULT 'postat',
        poza_predare TEXT,
        poza_livrare TEXT,
        sofer_id INTEGER,
        data_postare TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(sofer_id) REFERENCES users(id)
    )""")
    conn.commit()
    conn.close()

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
        self.row = row

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row)
    return None

def calc_pret(de_unde, pana_unde, tip):
    if tip == 'plic':
        return 12
    # Simplu: 10 lei + distanta estimata (mock). In realitate calculezi km.
    # Pentru v2: pret fix 10 lei, daca ruta > 50km -> pana la 30 lei. Facem random 16-24 pentru demo.
    # Mai tarziu conectezi API distanta.
    # Aici: daca contine cuvinte diferite, 16 lei, altfel 10.
    if de_unde.lower() != pana_unde.lower():
        return 16
    return 10

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

@app.route('/')
def index():
    conn = get_db()
    rute = conn.execute("SELECT r.*, u.nume, u.telefon, u.poza FROM rute_sofer r JOIN users u ON r.user_id=u.id WHERE r.activa=1 ORDER BY r.id DESC LIMIT 6").fetchall()
    colete = conn.execute("SELECT c.*, u.nume FROM colete c JOIN users u ON c.user_id=u.id WHERE c.status='postat' ORDER BY c.id DESC LIMIT 6").fetchall()
    conn.close()
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
        # normalize phone
        if telefon:
            telefon = re.sub(r'\D','',telefon)
            if telefon.startswith('0'):
                telefon = '+40' + telefon[1:]
            elif not telefon.startswith('+'):
                telefon = '+' + telefon
        conn = get_db()
        # check existing
        exists = conn.execute("SELECT id FROM users WHERE telefon=? OR email=?", (telefon, email)).fetchone()
        if exists:
            flash("Telefonul sau emailul exista deja.", "error")
            conn.close()
            return redirect(url_for('register'))
        parola_hash = generate_password_hash(parola)
        conn.execute("INSERT INTO users (nume, telefon, email, parola_hash, rol, data_creare) VALUES (?,?,?,?,?,?)",
                     (nume, telefon, email, parola_hash, rol, datetime.now().isoformat()))
        conn.commit()
        user_row = conn.execute("SELECT * FROM users WHERE telefon=? OR email=?", (telefon, email)).fetchone()
        conn.close()
        user = User(user_row)
        login_user(user)
        flash("Cont creat! Bine ai venit pe e-ftin.ro", "success")
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier','').strip()  # telefon sau email
        parola = request.form.get('parola','')
        conn = get_db()
        # cauta dupa telefon sau email
        # normalize daca pare telefon
        id_clean = identifier
        if '@' not in identifier:
            id_clean_digits = re.sub(r'\D','',identifier)
            # cauta si cu +40 si fara
            row = conn.execute("SELECT * FROM users WHERE telefon LIKE ? OR telefon LIKE ?", (f"%{id_clean_digits}%", f"%{identifier}%")).fetchone()
            if not row:
                row = conn.execute("SELECT * FROM users WHERE email=?", (identifier,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM users WHERE email=?", (identifier,)).fetchone()
            if not row:
                row = conn.execute("SELECT * FROM users WHERE telefon=?", (identifier,)).fetchone()
        conn.close()
        if row and check_password_hash(row['parola_hash'], parola):
            user = User(row)
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Date gresite. Verifica telefon/email si parola.", "error")
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
    # colete care se potrivesc pe rutele mele (matching simplu)
    matches_for_me = []
    for ruta in my_rute:
        if not ruta['activa']:
            continue
        # cauta colete unde de_unde contine cuvinte din ruta sau invers
        colete_match = conn.execute("SELECT c.*, u.nume, u.telefon FROM colete c JOIN users u ON c.user_id=u.id WHERE c.status='postat' AND c.user_id!=?", (current_user.id,)).fetchall()
        for colet in colete_match:
            # matching simplu: daca orasul de plecare al coletului apare in ruta soferului
            de = colet['de_unde'].lower()
            pana = colet['pana_unde'].lower()
            ruta_de = ruta['de_unde'].lower()
            ruta_pana = ruta['pana_unde'].lower()
            if (de in ruta_de or de in ruta_pana or ruta_de in de or ruta_pana in de or 
                pana in ruta_de or pana in ruta_pana or ruta_de in pana or ruta_pana in pana):
                matches_for_me.append({'ruta': ruta, 'colet': colet})
    # soferi care se potrivesc pe coletele mele
    soferi_for_my_colete = []
    for colet in my_colete:
        if colet['status'] != 'postat':
            continue
        rute_match = conn.execute("SELECT r.*, u.nume, u.telefon, u.poza FROM rute_sofer r JOIN users u ON r.user_id=u.id WHERE r.activa=1 AND r.user_id!=?", (current_user.id,)).fetchall()
        for ruta in rute_match:
            de = colet['de_unde'].lower()
            pana = colet['pana_unde'].lower()
            ruta_de = ruta['de_unde'].lower()
            ruta_pana = ruta['pana_unde'].lower()
            if (de in ruta_de or de in ruta_pana or ruta_de in de or 
                pana in ruta_de or pana in ruta_pana or ruta_pana in pana):
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
        # poza
        poza_path = None
        if 'poza' in request.files:
            file = request.files['poza']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"user_{current_user.id}_{secrets.token_hex(4)}.{file.filename.rsplit('.',1)[1].lower()}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                poza_path = f"uploads/{filename}"
        # update
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
        de_unde = request.form.get('de_unde','').strip()
        pana_unde = request.form.get('pana_unde','').strip()
        data_ruta = request.form.get('data_ruta','')
        ora = request.form.get('ora','')
        locuri = request.form.get('locuri','1')
        detalii = request.form.get('detalii','')
        conn = get_db()
        conn.execute("INSERT INTO rute_sofer (user_id, de_unde, pana_unde, data_ruta, ora, locuri, detalii) VALUES (?,?,?,?,?,?,?)",
                     (current_user.id, de_unde, pana_unde, data_ruta, ora, locuri, detalii))
        conn.commit()
        conn.close()
        flash("Ruta adaugata! Acum vezi coletele care se potrivesc in dashboard.", "success")
        return redirect(url_for('dashboard'))
    return render_template('sofer.html')

@app.route('/colet', methods=['GET','POST'])
@login_required
def colet():
    if request.method == 'POST':
        de_unde = request.form.get('de_unde','').strip()
        pana_unde = request.form.get('pana_unde','').strip()
        ce_contine = request.form.get('ce_contine','').strip()
        tip = request.form.get('tip','colet')
        greutate = request.form.get('greutate','')
        telefon_contact = request.form.get('telefon_contact','').strip()
        pret = calc_pret(de_unde, pana_unde, tip)
        if tip == 'colet':
            # 10 + 0.4/km capped 30 - simplificat
            pret = min(30, max(10, pret))
        conn = get_db()
        conn.execute("INSERT INTO colete (user_id, de_unde, pana_unde, ce_contine, tip, greutate, telefon_contact, pret, data_postare) VALUES (?,?,?,?,?,?,?,?,?)",
                     (current_user.id, de_unde, pana_unde, ce_contine, tip, greutate, telefon_contact, pret, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        flash(f"Colet postat! Pret: {pret} lei. Vezi soferi in dashboard.", "success")
        return redirect(url_for('dashboard'))
    return render_template('colet.html')

@app.route('/api/matches/<int:colet_id>')
@login_required
def api_matches(colet_id):
    conn = get_db()
    colet = conn.execute("SELECT * FROM colete WHERE id=?", (colet_id,)).fetchone()
    if not colet:
        conn.close()
        return jsonify([])
    rute = conn.execute("SELECT r.*, u.nume, u.telefon FROM rute_sofer r JOIN users u ON r.user_id=u.id WHERE r.activa=1").fetchall()
    matches = []
    for ruta in rute:
        de = colet['de_unde'].lower()
        pana = colet['pana_unde'].lower()
        if de in ruta['de_unde'].lower() or de in ruta['pana_unde'].lower() or pana in ruta['de_unde'].lower() or pana in ruta['pana_unde'].lower():
            matches.append({'ruta_id': ruta['id'], 'sofer': ruta['nume'], 'telefon': ruta['telefon'], 'de_unde': ruta['de_unde'], 'pana_unde': ruta['pana_unde']})
    conn.close()
    return jsonify(matches)

@app.route('/admin')
def admin():
    # admin simplu - doar daca esti logat si numele e Razvan
    if not current_user.is_authenticated or 'razvan' not in current_user.nume.lower():
        return "Nu ai acces", 403
    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    rute = conn.execute("SELECT r.*, u.nume FROM rute_sofer r JOIN users u ON r.user_id=u.id ORDER BY r.id DESC").fetchall()
    colete = conn.execute("SELECT c.*, u.nume FROM colete c JOIN users u ON c.user_id=u.id ORDER BY c.id DESC").fetchall()
    conn.close()
    return render_template('admin.html', users=users, rute=rute, colete=colete)

if __name__ == '__main__':
    app.run(debug=True)