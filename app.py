import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'e-ftin-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eftin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    parola = db.Column(db.String(200), nullable=False)
    nume = db.Column(db.String(80))
    telefon = db.Column(db.String(20))
    poza = db.Column(db.String(200), default='')

class RutaSofer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    plecare = db.Column(db.String(100), nullable=False)
    sosire = db.Column(db.String(100), nullable=False)
    traseu = db.Column(db.Text, default='')  # orașe intermediare
    data_ruta = db.Column(db.String(20))
    ora = db.Column(db.String(20))
    locuri = db.Column(db.Integer, default=3)
    detalii = db.Column(db.Text)
    activa = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='rute')

class Colet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    plecare = db.Column(db.String(100), nullable=False)
    sosire = db.Column(db.String(100), nullable=False)
    greutate = db.Column(db.Float)
    descriere = db.Column(db.Text)
    pret = db.Column(db.Float)
    status = db.Column(db.String(20), default='Caut sofer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='colete')

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ruta_id = db.Column(db.Integer, db.ForeignKey('ruta_sofer.id'))
    colet_id = db.Column(db.Integer, db.ForeignKey('colet.id'))
    status = db.Column(db.String(20), default='Nou')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ruta = db.relationship('RutaSofer', backref='meciuri')
    colet = db.relationship('Colet', backref='meciuri')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def calculeaza_pret(greutate):
    return 12 if greutate and greutate < 1 else 20

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def gaseste_matchuri():
    try:
        rute = RutaSofer.query.filter_by(activa=True).all()
        colete = Colet.query.filter_by(status='Caut sofer').all()
        count=0
        for ruta in rute:
            # lista orașe rută: plecare + traseu + sosire
            orase_ruta = [ruta.plecare.lower()] + [x.strip().lower() for x in (ruta.traseu or '').split(',') if x.strip()] + [ruta.sosire.lower()]
            for colet in colete:
                plecare_colet = colet.plecare.lower()
                sosire_colet = colet.sosire.lower()
                # match dacă plecarea și sosirea coletului sunt în traseul șoferului
                def in_traseu(city):
                    for o in orase_ruta:
                        if city[:4] in o or o[:4] in city:
                            return True
                    return False
                if in_traseu(plecare_colet) and in_traseu(sosire_colet):
                    if not Match.query.filter_by(ruta_id=ruta.id, colet_id=colet.id).first():
                        db.session.add(Match(ruta_id=ruta.id, colet_id=colet.id))
                        count+=1
        if count>0: db.session.commit()
    except: pass

@app.route('/')
def index():
    rute_active = RutaSofer.query.filter_by(activa=True).order_by(RutaSofer.created_at.desc()).limit(6).all()
    colete_active = Colet.query.filter_by(status='Caut sofer').order_by(Colet.created_at.desc()).limit(6).all()
    gaseste_matchuri()
    return render_template('index.html', rute=rute_active, colete=colete_active)
@app.route('/despre')
def despre(): return render_template('despre.html')
@app.route('/termeni')
def termeni(): return render_template('termeni.html')
@app.route('/confidentialitate')
def confidentialitate(): return render_template('confidentialitate.html')
@app.route('/contact')
def contact(): return render_template('contact.html')
@app.route('/ads.txt')
def ads_txt(): return Response("google.com, pub-3083295229846648, DIRECT, f08c47fec0942fa0", mimetype='text/plain')

@app.route('/profil', methods=['GET','POST'])
@login_required
def profil():
    if request.method=='POST':
        nume=request.form.get('nume'); telefon=request.form.get('telefon'); parola_noua=request.form.get('parola_noua')
        if nume: current_user.nume=nume
        if telefon: current_user.telefon=telefon
        if parola_noua: current_user.parola=generate_password_hash(parola_noua)
        if 'poza' in request.files:
            file=request.files['poza']
            if file and file.filename!='' and allowed_file(file.filename):
                filename=secure_filename(f"user_{current_user.id}_{file.filename}")
                filepath=os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                current_user.poza=f"/static/uploads/{filename}"
        db.session.commit()
        flash('Profil actualizat!','success')
        return redirect(url_for('profil'))
    return render_template('profil.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        email=request.form['email']; parola=request.form['parola']; nume=request.form['nume']; telefon=request.form['telefon']
        if User.query.filter_by(email=email).first():
            flash('Email deja folosit','error'); return redirect(url_for('register'))
        user=User(email=email, parola=generate_password_hash(parola), nume=nume, telefon=telefon)
        db.session.add(user); db.session.commit(); login_user(user); return redirect(url_for('dashboard'))
    return render_template('register.html')
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form['email']; parola=request.form['parola']
        user=User.query.filter_by(email=email).first()
        if user and check_password_hash(user.parola, parola):
            login_user(user); return redirect(url_for('dashboard'))
        flash('Date gresite','error')
    return render_template('login.html')
@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('index'))
@app.route('/dashboard')
@login_required
def dashboard():
    gaseste_matchuri()
    my_rute=RutaSofer.query.filter_by(user_id=current_user.id).order_by(RutaSofer.created_at.desc()).all()
    my_colete=Colet.query.filter_by(user_id=current_user.id).order_by(Colet.created_at.desc()).all()
    try: my_matches=Match.query.join(RutaSofer).join(Colet).filter((RutaSofer.user_id==current_user.id) | (Colet.user_id==current_user.id)).order_by(Match.created_at.desc()).all()
    except: my_matches=[]
    return render_template('dashboard.html', my_rute=my_rute, my_colete=my_colete, my_matches=my_matches)
@app.route('/sofer', methods=['GET','POST'])
@login_required
def sofer():
    if request.method=='POST':
        r=RutaSofer(user_id=current_user.id, plecare=request.form['plecare'], sosire=request.form['sosire'], traseu=request.form.get('traseu',''), data_ruta=request.form['data_ruta'], ora=request.form['ora'], locuri=request.form.get('locuri',3), detalii=request.form.get('detalii',''))
        db.session.add(r); db.session.commit(); gaseste_matchuri(); flash('Ruta adaugata!','success'); return redirect(url_for('dashboard'))
    return render_template('sofer.html')
@app.route('/colet', methods=['GET','POST'])
@login_required
def colet():
    if request.method=='POST':
        greutate=float(request.form.get('greutate',2) or 2); pret=calculeaza_pret(greutate)
        c=Colet(user_id=current_user.id, plecare=request.form['plecare'], sosire=request.form['sosire'], greutate=greutate, descriere=request.form.get('descriere',''), pret=pret)
        db.session.add(c); db.session.commit(); gaseste_matchuri(); flash(f'Colet adaugat! Pret: {pret} lei.','success'); return redirect(url_for('dashboard'))
    return render_template('colet.html')
@app.route('/match/<int:match_id>/contact')
@login_required
def match_contact(match_id):
    m=Match.query.get_or_404(match_id)
    if m.ruta.user_id!=current_user.id and m.colet.user_id!=current_user.id:
        flash('Nu ai acces','error'); return redirect(url_for('dashboard'))
    if m.ruta.user_id==current_user.id:
        other_phone=m.colet.user.telefon; other_name=m.colet.user.nume
        text=f"Salut {other_name}! Sunt sofer pe e-ftin.ro, ruta {m.ruta.plecare}->{m.ruta.sosire}. Am vazut coletul tau {m.colet.plecare}->{m.colet.sosire}. Mai e valabil?"
    else:
        other_phone=m.ruta.user.telefon; other_name=m.ruta.user.nume
        text=f"Salut {other_name}! Am colet {m.colet.plecare}->{m.colet.sosire} pe e-ftin.ro. Am vazut ruta ta {m.ruta.plecare}->{m.ruta.sosire}. Ma poti ajuta?"
    m.status='Contactat'; db.session.commit()
    import urllib.parse
    return redirect(f"https://wa.me/{other_phone.replace('+','').replace(' ','')}?text={urllib.parse.quote(text)}")
@app.route('/match/<int:match_id>/livrat', methods=['POST'])
@login_required
def match_livrat(match_id):
    m=Match.query.get_or_404(match_id); m.status='Livrat'; m.colet.status='Livrat'; db.session.commit(); flash('Marcat ca livrat!','success'); return redirect(url_for('dashboard'))
with app.app_context(): db.create_all()
if __name__=='__main__': app.run(debug=True)
