from flask import Flask, render_template, request, redirect, url_for, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import User, db, Evenement
from datetime import datetime
from firms import recuperer_incendies
from datetime import timedelta
from dotenv import load_dotenv
import os
import csv
import io
from sqlalchemy import func

load_dotenv()


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tracker.db'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db.init_app(app)

from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[]
)

derniere_maj = {"date": None, "heure": None}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

REGIONS = {
    "": "Toutes les régions",
    "europe": "Europe",
    "amerique_nord": "Amérique du Nord",
    "amerique_sud": "Amérique du Sud",
    "afrique": "Afrique",
    "asie": "Asie",
    "oceanie": "Océanie"
}

REGIONS_BBOX = {
    "europe": (34, -25, 72, 45),
    "amerique_nord": (5, -170, 75, -50),
    "amerique_sud": (-58, -82, 13, -34),
    "afrique": (-35, -18, 38, 52),
    "asie": (-10, 45, 55, 150),
    "oceanie": (-50, 110, 0, 180)
}

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        return render_template('login.html', erreur="Identifiants incorrects")
    return render_template('login.html', erreur=None)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/donnees')
def donnees():
    total = Evenement.query.count()
    dates_extremes = db.session.query(func.min(Evenement.date), func.max(Evenement.date)).first()

    date_debut = request.args.get('date_debut')
    date_fin = request.args.get('date_fin')
    intensite_min = request.args.get('intensite_min', type=float)
    intensite_max = request.args.get('intensite_max', type=float)
    frp_min = request.args.get('frp_min', type=float)
    frp_max = request.args.get('frp_max', type=float)
    zone = request.args.get('zone', '')
    confidence = request.args.get('confidence', '')
    daynight = request.args.get('daynight', '')
    satellite = request.args.get('satellite', '')
    par_page = request.args.get('par_page', default=200, type=int)
    page = request.args.get('page', default=1, type=int)
    pixel_max = request.args.get('pixel_max', type=float)

    query = Evenement.query

    if date_debut:
        query = query.filter(Evenement.date >= datetime.strptime(date_debut, '%Y-%m-%d').date())
    if date_fin:
        query = query.filter(Evenement.date <= datetime.strptime(date_fin, '%Y-%m-%d').date())
    if intensite_min:
        query = query.filter(Evenement.intensite >= intensite_min)
    if intensite_max:
        query = query.filter(Evenement.intensite <= intensite_max)
    if frp_min:
        query = query.filter(Evenement.frp >= frp_min)
    if frp_max:
        query = query.filter(Evenement.frp <= frp_max)
    if zone:
        query = query.filter(Evenement.region == zone)
    if confidence:
        query = query.filter(Evenement.confidence == confidence)
    if daynight:
        query = query.filter(Evenement.daynight == daynight)
    if satellite:
        query = query.filter(Evenement.satellite == satellite)
    if pixel_max:
        query = query.filter(Evenement.scan <= pixel_max, Evenement.track <= pixel_max)
    
    nb_filtres = query.count()
    nb_pages = max(1, (nb_filtres + par_page - 1) // par_page)
    page = min(max(page, 1), nb_pages)

    evenements = query.order_by(Evenement.date.desc()).offset((page - 1) * par_page).limit(par_page).all()

    base_params = {k: v for k, v in request.args.items() if k != 'page'}

    return render_template(
        'donnees.html',
        titre="Données — Détections thermiques",
        evenements=evenements,
        total=total,
        nb_filtres=nb_filtres,
        date_min=dates_extremes[0],
        date_max=dates_extremes[1],
        regions=REGIONS,
        filtres_actuels=request.args,
        page=page,
        nb_pages=nb_pages,
        base_params=base_params,
        derniere_maj=derniere_maj
    )

@app.route('/')
def home():
    return render_template('carte.html')

@app.route('/evenement/<int:id>')
def evenement(id):
    return f"Détail de l'événement numéro {id}"

@app.route('/nouveau', methods=['GET', 'POST'])
@login_required
def nouveau():
    if request.method == 'POST':
        nouvel_evenement = Evenement(
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            zone=request.form['zone'],
            type_evenement=request.form['type_evenement'],
            description=request.form['description']
        )
        db.session.add(nouvel_evenement)
        db.session.commit()
        return redirect(url_for('donnees'))
    return render_template('nouveau.html')

@app.route('/evenement/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer(id):
    evenement = Evenement.query.get_or_404(id)
    db.session.delete(evenement)
    db.session.commit()
    return redirect(url_for('donnees'))

@app.route('/evenement/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier(id):
    evenement = Evenement.query.get_or_404(id)
    if request.method == 'POST':
        evenement.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        evenement.zone = request.form['zone']
        evenement.type_evenement = request.form['type_evenement']
        evenement.description = request.form['description']
        db.session.commit()
        return redirect(url_for('donnees'))
    return render_template('modifier.html', evenement=evenement)

@app.route('/importer', methods=['GET', 'POST'])
@login_required
def importer():
    if request.method == 'POST':
        resultats, erreur = recuperer_incendies(zone="world", jours=5)

        if erreur:
            return render_template('importer.html', erreur=erreur, ajoutes=0)

        existants = db.session.query(
            Evenement.date, Evenement.latitude, Evenement.longitude
        ).all()
        set_existants = set(existants)

        nb_ajoutes = 0
        nouveaux_evenements = []
        for item in resultats:
            cle = (item['date'], item['latitude'], item['longitude'])
            if cle in set_existants:
                continue

            nouvel_evenement = Evenement(
                date=item['date'],
                heure=item['heure'],
                zone=item['zone'],
                region=item['region'],
                type_evenement="Incendie",
                description=f"Intensité détectée : {item['intensite']} K, FRP : {item['frp']} MW",
                latitude=item['latitude'],
                longitude=item['longitude'],
                intensite=item['intensite'],
                frp=item['frp'],
                satellite=item['satellite'],
                confidence=item['confidence'],
                daynight=item['daynight'],
                bright_ti5=item['bright_ti5'],
                scan=item['scan'],
                track=item['track'],
                version=item['version']
            )
            nouveaux_evenements.append(nouvel_evenement)
            set_existants.add(cle)
            nb_ajoutes += 1

        db.session.bulk_save_objects(nouveaux_evenements)
        db.session.commit()
        from datetime import datetime as dt
        derniere_maj["date"] = dt.now().strftime('%Y-%m-%d')
        derniere_maj["heure"] = dt.now().strftime('%H:%M')
        return render_template('importer.html', erreur=None, ajoutes=nb_ajoutes)

    return render_template('importer.html', erreur=None, ajoutes=None)

@app.route('/api/evenements')
def api_evenements():
    date_precise = request.args.get('date')

    if date_precise:
        date_cible = datetime.strptime(date_precise, '%Y-%m-%d').date()
        evenements = Evenement.query.filter(
            Evenement.latitude.isnot(None),
            Evenement.longitude.isnot(None),
            Evenement.date == date_cible
        ).all()
    else:
        jours = request.args.get('jours', default=1, type=int)
        date_limite = datetime.now().date() - timedelta(days=jours)
        evenements = Evenement.query.filter(
            Evenement.latitude.isnot(None),
            Evenement.longitude.isnot(None),
            Evenement.date >= date_limite
        ).all()

    data = []
    for e in evenements:
        data.append({
            "id": e.id,
            "latitude": e.latitude,
            "longitude": e.longitude,
            "intensite": e.intensite,
            "frp": e.frp,
            "date": e.date.strftime('%Y-%m-%d'),
            "description": e.description
        })

    return {"evenements": data}
@app.route('/export')
def export_csv():
    date_debut = request.args.get('date_debut')
    date_fin = request.args.get('date_fin')
    intensite_min = request.args.get('intensite_min', type=float)
    intensite_max = request.args.get('intensite_max', type=float)
    frp_min = request.args.get('frp_min', type=float)
    frp_max = request.args.get('frp_max', type=float)
    zone = request.args.get('zone', '')
    confidence = request.args.get('confidence', '')
    daynight = request.args.get('daynight', '')
    pixel_max = request.args.get('pixel_max', type=float)

    query = Evenement.query.filter(Evenement.latitude.isnot(None))

    if date_debut:
        query = query.filter(Evenement.date >= datetime.strptime(date_debut, '%Y-%m-%d').date())
    if date_fin:
        query = query.filter(Evenement.date <= datetime.strptime(date_fin, '%Y-%m-%d').date())
    if intensite_min:
        query = query.filter(Evenement.intensite >= intensite_min)
    if intensite_max:
        query = query.filter(Evenement.intensite <= intensite_max)
    if frp_min:
        query = query.filter(Evenement.frp >= frp_min)
    if frp_max:
        query = query.filter(Evenement.frp <= frp_max)
    if zone:
        query = query.filter(Evenement.region == zone)
    if confidence:
        query = query.filter(Evenement.confidence == confidence)
    if daynight:
        query = query.filter(Evenement.daynight == daynight)
    if pixel_max:
        query = query.filter(Evenement.scan <= pixel_max, Evenement.track <= pixel_max)

    evenements = query.all()

    sortie = io.StringIO()
    writer = csv.writer(sortie)
    writer.writerow([
        'date', 'heure', 'latitude', 'longitude', 'region',
        'temperature_kelvin', 'frp_mw', 'satellite', 'confidence',
        'daynight', 'bright_ti5', 'scan_km', 'track_km', 'version', 'description'
    ])
    for e in evenements:
        writer.writerow([
            e.date, e.heure, e.latitude, e.longitude, e.region,
            e.intensite, e.frp, e.satellite, e.confidence,
            e.daynight, e.bright_ti5, e.scan, e.track, e.version, e.description
        ])

    return Response(
        sortie.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=detections_thermiques.csv'}
    )

@app.route('/api/compter')
def api_compter():
    date_debut = request.args.get('date_debut')
    date_fin = request.args.get('date_fin')
    intensite_min = request.args.get('intensite_min', type=float)
    intensite_max = request.args.get('intensite_max', type=float)
    frp_min = request.args.get('frp_min', type=float)
    frp_max = request.args.get('frp_max', type=float)
    zone = request.args.get('zone', '')
    confidence = request.args.get('confidence', '')
    daynight = request.args.get('daynight', '')
    pixel_max = request.args.get('pixel_max', type=float)

    query = Evenement.query.filter(Evenement.latitude.isnot(None))

    if date_debut:
        query = query.filter(Evenement.date >= datetime.strptime(date_debut, '%Y-%m-%d').date())
    if date_fin:
        query = query.filter(Evenement.date <= datetime.strptime(date_fin, '%Y-%m-%d').date())
    if intensite_min:
        query = query.filter(Evenement.intensite >= intensite_min)
    if intensite_max:
        query = query.filter(Evenement.intensite <= intensite_max)
    if frp_min:
        query = query.filter(Evenement.frp >= frp_min)
    if frp_max:
        query = query.filter(Evenement.frp <= frp_max)
    if zone:
        query = query.filter(Evenement.region == zone)
    if confidence:
        query = query.filter(Evenement.confidence == confidence)
    if daynight:
        query = query.filter(Evenement.daynight == daynight)
    if pixel_max:
        query = query.filter(Evenement.scan <= pixel_max, Evenement.track <= pixel_max)

    return {"nombre": query.count()}

@app.route('/api/kpi')
def api_kpi():
    aujourd_hui = datetime.now().date()
    hier = aujourd_hui - timedelta(days=1)
    avant_hier = aujourd_hui - timedelta(days=2)

    total_jour = Evenement.query.filter(Evenement.date == aujourd_hui).count()
    total_hier = Evenement.query.filter(Evenement.date == hier).count()
    total_avant_hier = Evenement.query.filter(Evenement.date == avant_hier).count()

    frp_max_jour = db.session.query(func.max(Evenement.frp)).filter(Evenement.date == aujourd_hui).scalar()

    regions_actives_query = db.session.query(Evenement.region).filter(
        Evenement.date == aujourd_hui,
        Evenement.region.isnot(None)
    ).distinct().all()
    regions_actives_noms = [REGIONS.get(r[0], r[0]) for r in regions_actives_query if r[0] != 'autre']

    evolution = None
    if total_avant_hier > 0:
        evolution = round(((total_hier - total_avant_hier) / total_avant_hier) * 100)

    return {
        "total_jour": total_jour,
        "total_hier": total_hier,
        "frp_max_jour": round(frp_max_jour, 1) if frp_max_jour else None,
        "regions_actives": len(regions_actives_noms),
        "regions_actives_noms": regions_actives_noms,
        "evolution_pct": evolution
    }

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False') == 'True')

