
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'e-ftin-secret-2026'

DB = 'eftin.db'

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS soferi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nume TEXT,
        telefon TEXT,
        ruta TEXT,
        judete TEXT,
        locuri INTEGER,
        data TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS colete (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nume TEXT,
        telefon TEXT,
        de_unde TEXT,
        pana_unde TEXT,
        greutate TEXT,
        pret_estimativ TEXT,
        data TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

def whatsapp_link(telefon, mesaj):
    # curata telefonul, pastreaza doar cifre, adauga 40 daca nu are prefix
    tel = ''.join(filter(str.isdigit, telefon))
    if tel.startswith('0'):
        tel = '40' + tel[1:]
    if not tel.startswith('40'):
        tel = '40' + tel
    import urllib.parse
    return f"https://wa.me/{tel}?text={urllib.parse.quote(mesaj)}"

def calc_pret(de_unde, pana_unde, greutate):
    # Simplu: baza 10 lei + 0.4 lei/km estimat, plafon 25 lei, plic 12 lei
    try:
        g = float(greutate) if greutate else 2
    except:
        g = 2
    if g <= 0.5:
        return "12 lei (plic)"
    # estimam distanta medie 40km daca nu avem km reali
    dist = 40
    pret = 10 + dist*0.4
    if pret > 25:
        pret = 25
    return f"{pret:.0f} lei estimat"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/inscrie-sofer', methods=['GET','POST'])
def inscrie_sofer():
    if request.method == 'POST':
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("INSERT INTO soferi (nume, telefon, ruta, judete, locuri, data) VALUES (?,?,?,?,?,?)",
                  (request.form['nume'], request.form['telefon'], request.form['ruta'], request.form['judete'], request.form['locuri'], datetime.now().isoformat()))
        conn.commit()
        conn.close()
        flash('Te-ai inscris ca sofer e-ftin! Te contactam in 24h.')
        return redirect(url_for('index'))
    return render_template('sofer.html')

@app.route('/trimite-colet', methods=['GET','POST'])
def trimite_colet():
    pret = None
    if request.method == 'POST':
        pret = calc_pret(request.form['de_unde'], request.form['pana_unde'], request.form['greutate'])
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("INSERT INTO colete (nume, telefon, de_unde, pana_unde, greutate, pret_estimativ, data) VALUES (?,?,?,?,?,?,?)",
                  (request.form['nume'], request.form['telefon'], request.form['de_unde'], request.form['pana_unde'], request.form['greutate'], pret, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        flash(f'Cerere trimisa! Pret estimat: {pret}. Un sofer de pe ruta ta te va contacta.')
        return redirect(url_for('index'))
    return render_template('colet.html')

@app.route('/admin')
def admin():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    soferi = c.execute("SELECT * FROM soferi ORDER BY id DESC").fetchall()
    colete = c.execute("SELECT * FROM colete ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('admin.html', soferi=soferi, colete=colete)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
