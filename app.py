import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'e-ftin-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eftin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELE ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    parola = db.Column(db.String(200), nullable=False)
    nume = db.Column(db.String(80))
    telefon = db.Column(db.String(20))
    rating_mediu = db.Column(db.Float, default=0.0)
    nr_recenzii = db.Column(db.Integer, default=0)

class RutaSofer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    plecare = db.Column(db.String(100), nullable=False)
    sosire = db.Column(db.String(100), nullable=False)
    data_ruta = db.Column(db.String(20))
    ora = db.Column(db.String(20))
    locuri = db.Column(db.Integer, default=3)
    pret_per_km = db.Column(db.Float, default=0.4)
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
    dimensiuni = db.Column(db.String(50))
    descriere = db.Column(db.Text)
    pret = db.Column(db.Float)
    status = db.Column(db.String(20), default='Caut sofer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='colete')

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ruta_id = db.Column(db.Integer, db.ForeignKey('ruta_sofer.id'))
    colet_id = db.Column(db.Integer, db.ForeignKey('colet.id'))
    status = db.Column(db.String(20), default='Nou') # Nou, Contactat, Livrat
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ruta = db.relationship('RutaSofer', backref='meciuri')
    colet = db.relationship('Colet', backref='meciuri')

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    de_la_user = db.Column(db.Integer, db.ForeignKey('user.id'))
    catre_user = db.Column(db.Integer, db.ForeignKey('user.id'))
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    stele = db.Column(db.Integer) # 1-5
    recenzie = db.Column(db.Text)
    rol = db.Column(db.String(20)) # sofer sau expeditor
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def calculeaza_pret(greutate, distanta_km=50):
    if greutate and greutate < 1: # plic
        return 12
    pret = 10 + (distanta_km * 0.4)
    return min(pret, 30)

def gaseste_matchuri():
    """Creeaza match automat cand plecare/sosire se potrivesc"""
    rute = RutaSofer.query.filter_by(activa=True).all()
    colete = Colet.query.filter_by(status='Caut sofer').all()
    count = 0
    for ruta in rute:
        for colet in colete:
            # match simplu: plecare contine sau sosire contine (case-insensitive)
            plecare_match = ruta.plecare.lower() in colet.plecare.lower() or colet.plecare.lower() in ruta.plecare.lower() or ruta.plecare.lower().split()[0] == colet.plecare.lower().split()[0]
            sosire_match = ruta.sosire.lower() in colet.sosire.lower() or colet.sosire.lower() in ruta.sosire.lower() or ruta.sosire.lower().split()[0] == colet.sosire.lower().split()[0]
            if plecare_match and sosire_match:
                exista = Match.query.filter_by(ruta_id=ruta.id, colet_id=colet.id).first()
                if not exista:
                    m = Match(ruta_id=ruta.id, colet_id=colet.id)
                    db.session.add(m)
                    count += 1
    if count>0:
        db.session.commit()
    return count

# --- RUTE ---
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
def ads_txt():
    return Response("google.com, pub-3083295229846648, DIRECT, f08c47fec0942fa0", mimetype='text/plain')

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
    # match-uri unde eu sunt sofer sau expeditor
    my_matches=Match.query.join(RutaSofer).join(Colet).filter((RutaSofer.user_id==current_user.id) | (Colet.user_id==current_user.id)).order_by(Match.created_at.desc()).all()
    return render_template('dashboard.html', my_rute=my_rute, my_colete=my_colete, my_matches=my_matches)

@app.route('/sofer', methods=['GET','POST'])
@login_required
def sofer():
    if request.method=='POST':
        plecare=request.form['plecare']; sosire=request.form['sosire']; data_ruta=request.form['data_ruta']; ora=request.form['ora']; locuri=request.form.get('locuri',3); detalii=request.form.get('detalii','')
        r=RutaSofer(user_id=current_user.id, plecare=plecare, sosire=sosire, data_ruta=data_ruta, ora=ora, locuri=locuri, detalii=detalii)
        db.session.add(r); db.session.commit(); gaseste_matchuri(); flash('Ruta adaugata! Am cautat colete care se potrivesc.','success'); return redirect(url_for('dashboard'))
    return render_template('sofer.html')

@app.route('/colet', methods=['GET','POST'])
@login_required
def colet():
    if request.method=='POST':
        plecare=request.form['plecare']; sosire=request.form['sosire']; greutate=float(request.form.get('greutate',2) or 2); descriere=request.form.get('descriere','')
        pret=calculeaza_pret(greutate)
        c=Colet(user_id=current_user.id, plecare=plecare, sosire=sosire, greutate=greutate, descriere=descriere, pret=pret)
        db.session.add(c); db.session.commit(); gaseste_matchuri(); flash(f'Colet adaugat! Pret: {pret} lei. Am cautat soferi!','success'); return redirect(url_for('dashboard'))
    return render_template('colet.html')

@app.route('/match/<int:match_id>/contact')
@login_required
def match_contact(match_id):
    m=Match.query.get_or_404(match_id)
    # verifica ca esti parte din match
    if m.ruta.user_id!=current_user.id and m.colet.user_id!=current_user.id:
        flash('Nu ai acces','error'); return redirect(url_for('dashboard'))
    # determina telefonul celuilalt
    if m.ruta.user_id==current_user.id:
        other_phone=m.colet.user.telefon
        other_name=m.colet.user.nume
        text=f"Salut {other_name}! Sunt sofer pe e-ftin.ro, ruta {m.ruta.plecare}->{m.ruta.sosire}. Am vazut coletul tau {m.colet.plecare}->{m.colet.sosire}. Mai e valabil?"
    else:
        other_phone=m.ruta.user.telefon
        other_name=m.ruta.user.nume
        text=f"Salut {other_name}! Am colet {m.colet.plecare}->{m.colet.sosire} pe e-ftin.ro. Am vazut ruta ta {m.ruta.plecare}->{m.ruta.sosire}. Ma poti ajuta?"
    m.status='Contactat'; db.session.commit()
    import urllib.parse
    wa_link=f"https://wa.me/{other_phone.replace('+','').replace(' ','')}?text={urllib.parse.quote(text)}"
    return redirect(wa_link)

@app.route('/match/<int:match_id>/livrat', methods=['POST'])
@login_required
def match_livrat(match_id):
    m=Match.query.get_or_404(match_id)
    m.status='Livrat'
    # update status colet
    m.colet.status='Livrat'
    db.session.commit()
    flash('Marcat ca livrat! Acum poti lasa rating.','success')
    return redirect(url_for('rating_page', match_id=match_id))

@app.route('/rating/<int:match_id>', methods=['GET','POST'])
@login_required
def rating_page(match_id):
    m=Match.query.get_or_404(match_id)
    if request.method=='POST':
        stele=int(request.form['stele']); recenzie=request.form.get('recenzie','')
        # catre cine dau rating?
        if m.ruta.user_id==current_user.id:
            catre=m.colet.user_id
            rol='expeditor'
        else:
            catre=m.ruta.user_id
            rol='sofer'
        r=Rating(de_la_user=current_user.id, catre_user=catre, match_id=match_id, stele=stele, recenzie=recenzie, rol=rol)
        db.session.add(r)
        # recalculeaza media
        toate=Rating.query.filter_by(catre_user=catre).all()
        media=sum([x.stele for x in toate]+[stele])/(len(toate)+1)
        user=User.query.get(catre)
        user.rating_mediu=media
        user.nr_recenzii=len(toate)+1
        db.session.commit()
        flash('Rating trimis! Multumim!','success')
        return redirect(url_for('dashboard'))
    return render_template('rating.html', match=m)

with app.app_context():
    db.create_all()

if __name__=='__main__':
    app.run(debug=True)
