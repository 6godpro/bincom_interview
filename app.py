from flask import Flask, flash, redirect, render_template, request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import dotenv
import os

dotenv.load_dotenv()

HOST=os.getenv('DB_HOST')
USER=os.getenv('DB_USER')
PASSWORD=os.getenv('DB_PASSWORD')
DB=os.getenv('DB')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

def create_connection():
    engine = create_engine(f"mysql+mysqldb://{USER}:{PASSWORD}@{HOST}/{DB}", pool_pre_ping=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    return session


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/polling_unit/')
@app.route('/polling_unit/<int:id>/')
def polling_results(id=None):
    """Question 1."""
    if id is None:
        return render_template('new_pu.html')

    query = text('''SELECT party_abbreviation, SUM(party_score)
                     FROM announced_pu_results
                     WHERE polling_unit_uniqueid={}
                     GROUP BY party_abbreviation;
                 '''.format(id))
    session = create_connection()
    query_result = session.execute(query)
    results = []
    total_votes = 0
    for result in query_result.all():
        results.append({'party': result[0], 'votes': result[1]})
        total_votes += result[1]
    session.close()
    return render_template('polling_result.html', results=results, total_votes=total_votes, id=id)

@app.route('/lga/')
@app.route('/lga/<name>/')
def lga_result_details(name=None):
    """Question 2."""
    session = create_connection()
    if name is None:
        query = text('''SELECT lga_name FROM lga''')
        query_result = session.execute(query)
        results = [lga[0] for lga in query_result.all()]
        return render_template('lga.html', lgas=results, name=None)

    query = text('''SELECT party_abbreviation, SUM(party_score)
                    FROM announced_pu_results
                    WHERE polling_unit_uniqueid IN (
                        SELECT uniqueid FROM polling_unit 
                        WHERE lga_id = (
                            SELECT lga_id FROM lga
                            WHERE lga_name = "{}"
                        )
                    )
                    GROUP BY party_abbreviation;'''.format(name)
                 )
    query_result = session.execute(query)
    results = []
    total_votes = 0
    for result in query_result.all():
        results.append({'party': result[0], 'total_votes': result[1]})
        total_votes += result[1]
    session.close()
    return render_template('lga.html', results=results, total_votes=total_votes, name=name)

@app.route('/store_result', methods=['POST'])
def store_polling_unit_result():
    """Question 3."""
    if request.method == 'POST':
        session = create_connection()
        polling_unit_uniqueid = request.form['polling_unit_uniqueid']
        party_abbreviations = request.form.getlist('party_abbreviation[]')
        party_scores = request.form.getlist('party_score[]')
        entered_by_user = request.form['entered_by_user']
        date_entered = request.form['date_entered']
        user_ip_address = request.form['user_ip_address']

        inserts = 0
        VALID_PARTY_ABBR = ['CPP', 'LABOUR', 'ANPP', 'JP', 'CDC', 'PPA', 'ACN', 'DPP', 'PDP']
        for abv, score in zip(party_abbreviations, party_scores):
            abv = abv.upper()
            if abv in VALID_PARTY_ABBR and len(score):
                query = text('''INSERT INTO announced_pu_results 
                             (polling_unit_uniqueid, party_abbreviation,
                             party_score, entered_by_user, date_entered,
                             user_ip_address)
                             VALUES ({}, "{}", {}, "{}", "{}", "{}")'''.format(
                                 polling_unit_uniqueid, abv, score,
                                 entered_by_user, date_entered,
                                 user_ip_address
                            )
                )
                session.execute(query)
                inserts += 1
        if inserts == 0:
            session.close()
            return 'Requires at least a party and a score!'
        session.commit()
        session.close()
        flash('Stored Successfully!', 'success')
        return redirect('/polling_unit')

    return "Invalid request method."


if __name__ == "__main__":
    app.run()
