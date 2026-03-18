import configparser

import mysql
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from mysql.connector import Error

from models import db, Player, Team, Season, Auction, AuctionParticipation, Match, Innings, MatchPerformance, \
    team_players, PlayerSeasonRegistration
import cloudinary.uploader
from config import cloudinary
import os
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)
# app.config['SECRET_KEY'] = 'your-secret-key-here'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cricket_tournament.db'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#
# db.init_app(app)
app.config['SECRET_KEY'] = 'your-secret-key-here'
# Read database config from ini file
config = configparser.ConfigParser()
config.read("db_config.ini")

# Build connection string for SQLAlchemy using mysql-connector
db_config = config["mysql"]
ssl_ca_path = db_config.get("ssl_ca", "")
# Base connection string
database_uri = (
    f"mysql+mysqlconnector://{db_config['user']}:{db_config['password']}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
)

# Add SSL parameters if ca.pem exists
import os
if ssl_ca_path and os.path.exists(ssl_ca_path):
    database_uri += f"?ssl_ca={ssl_ca_path}&ssl_verify_identity=true"

app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}

# Initialize SQLAlchemy
from models import db
db.init_app(app)

# Test connection using your existing method
def test_connection():
    try:
        connection = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            port=int(db_config['port']),
            ssl_ca=ssl_ca_path if os.path.exists(ssl_ca_path) else None
        )
        if connection.is_connected():
            print("✅ MySQL connected successfully (mysql.connector)")
            connection.close()
        return True
    except Error as e:
        print("❌ Error while connecting to MySQL:", e)
        return False

# Test connection on startup
with app.app_context():
    if test_connection():
        print("✅ SQLAlchemy will use mysql+mysqlconnector driver")
    else:
        print("⚠️ Database connection failed, but continuing...")


@app.route('/')
def index():
    stats = {
        'total_players': Player.query.count(),
        'total_teams': Team.query.count(),
        'total_matches': Match.query.count(),
        'active_season': Season.query.filter_by(is_active=True).first()
    }
    recent_matches = Match.query.order_by(Match.match_date.desc()).limit(5).all()
    return render_template('index.html', stats=stats, matches=recent_matches)


# Player Management Routes
@app.route('/players')
def players():
    all_players = Player.query.all()

    # Get active season for registration status
    active_season = Season.query.filter_by(is_active=True).first()

    # Create stats object with active season
    stats = {
        'active_season': active_season
    }

    return render_template('players.html', players=all_players, stats=stats)


@app.route('/player/add', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        # Handle file upload
        image_url = None
        if 'player_image' in request.files:
            file = request.files['player_image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                    file.save(tmp.name)
                    tmp_path = tmp.name
                try:
                    upload_result = cloudinary.uploader.upload(
                        tmp_path,
                        folder="cricket_players",
                        public_id=f"player_{int(datetime.utcnow().timestamp())}",
                        overwrite=True
                    )
                    image_url = upload_result.get('secure_url')
                finally:
                    os.unlink(tmp_path)

        # Use .get() for all fields to avoid KeyError
        # Required fields - validate they exist
        name = request.form.get('name')
        age = request.form.get('age')
        role = request.form.get('role')

        # Validate required fields
        if not name or not age or not role:
            flash('Name, Age, and Role are required fields!', 'error')
            return redirect(url_for('add_player'))

        # Optional fields - use .get() with default values
        batting_style = request.form.get('batting_style', '')
        bowling_style = request.form.get('bowling_style', '')
        jersey = request.form.get('jersey', '')
        jerseynumber = request.form.get('jerseynumber', '')

        # Create player with base price 200
        player = Player(
            name=name,
            age=int(age),
            role=role,
            batting_style=batting_style,
            bowling_style=bowling_style,
            jersey=jersey,
            jerseynumber=jerseynumber,
            base_price=200,  # Fixed base price
            image_url=image_url
        )
        db.session.add(player)
        db.session.commit()

        # Automatically register for active season if exists
        active_season = Season.query.filter_by(is_active=True).first()
        if active_season:
            registration = PlayerSeasonRegistration(
                player_id=player.id,
                season_id=active_season.id,
                status='registered'
            )
            db.session.add(registration)
            db.session.commit()
            flash(f'Player {name} added and registered for season {active_season.name}!', 'success')
        else:
            flash(f'Player {name} added successfully! (No active season to register for)', 'success')

        return redirect(url_for('players'))

    return render_template('add_player.html')


@app.route('/player/register_for_season/<int:player_id>', methods=['POST'])
def register_player_for_season(player_id):
    player = Player.query.get_or_404(player_id)
    season_id = request.form.get('season_id')
    is_ajax = request.form.get('ajax', False)

    if not season_id:
        if is_ajax:
            return jsonify({'success': False, 'message': 'No season selected'})
        flash('Please select a season', 'error')
        return redirect(url_for('players'))

    season = Season.query.get(season_id)
    if not season:
        if is_ajax:
            return jsonify({'success': False, 'message': 'Season not found'})
        flash('Season not found', 'error')
        return redirect(url_for('players'))

    # Check if already registered for this season
    existing = PlayerSeasonRegistration.query.filter_by(
        player_id=player_id,
        season_id=season_id
    ).first()

    if existing:
        if is_ajax:
            return jsonify({'success': False, 'message': f'Player already registered for {season.name}'})
        flash(f'Player {player.name} is already registered for season {season.name}', 'warning')
    else:
        registration = PlayerSeasonRegistration(
            player_id=player_id,
            season_id=season_id,
            status='registered'
        )
        db.session.add(registration)
        db.session.commit()

        if is_ajax:
            return jsonify({
                'success': True,
                'message': f'Player {player.name} registered for {season.name}'
            })
        flash(f'Player {player.name} registered for season {season.name} successfully!', 'success')

    if is_ajax:
        return jsonify({'success': False, 'message': 'Unknown error'})

    return redirect(url_for('players'))


@app.route('/player/bulk_register_for_season', methods=['POST'])
def bulk_register_players_for_season():
    season_id = request.form.get('season_id')
    player_ids = request.form.getlist('player_ids[]')

    if not season_id or not player_ids:
        flash('Please select season and players', 'error')
        return redirect(url_for('players'))

    season = Season.query.get(season_id)
    registered_count = 0
    skipped_count = 0

    for player_id in player_ids:
        # Check if already registered
        existing = PlayerSeasonRegistration.query.filter_by(
            player_id=player_id,
            season_id=season_id
        ).first()

        if not existing:
            registration = PlayerSeasonRegistration(
                player_id=player_id,
                season_id=season_id,
                status='registered'
            )
            db.session.add(registration)
            registered_count += 1
        else:
            skipped_count += 1

    db.session.commit()
    flash(
        f'Registered {registered_count} players for season {season.name} (Skipped {skipped_count} already registered)',
        'success')

    return redirect(url_for('players'))


@app.route('/player/edit/<int:id>', methods=['GET', 'POST'])
def edit_player(id):
    player = Player.query.get_or_404(id)
    if request.method == 'POST':
        # Handle file upload if new image is provided
        if 'player_image' in request.files:
            file = request.files['player_image']
            if file and file.filename:
                # Secure the filename and save temporarily
                filename = secure_filename(file.filename)

                # Create a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                    file.save(tmp.name)
                    tmp_path = tmp.name

                try:
                    # Upload to Cloudinary
                    upload_result = cloudinary.uploader.upload(
                        tmp_path,
                        folder="cricket_players",
                        public_id=f"player_{player.id}_{int(datetime.utcnow().timestamp())}",
                        overwrite=True
                    )
                    player.image_url = upload_result.get('secure_url')
                finally:
                    # Clean up temporary file
                    os.unlink(tmp_path)

        player.name = request.form['name']
        player.age = int(request.form['age'])
        player.role = request.form['role']
        player.batting_style = request.form.get('batting_style')
        player.bowling_style = request.form.get('bowling_style')
        player.email = request.form['email']
        player.phone = request.form['phone']

        # Convert base_price from lakhs to actual amount
        base_price_lakhs = float(request.form['base_price'])
        player.base_price = base_price_lakhs * 100000

        db.session.commit()
        flash('Player updated successfully!', 'success')
        return redirect(url_for('players'))

    # Convert base_price from actual to lakhs for display
    player.base_price_lakhs = player.base_price / 100000 if player.base_price else 1
    return render_template('edit_player.html', player=player)


@app.route('/player/delete/<int:id>')
def delete_player(id):
    player = Player.query.get_or_404(id)
    db.session.delete(player)
    db.session.commit()
    flash('Player deleted successfully!', 'success')
    return redirect(url_for('players'))


# Team Management Routes
@app.route('/teams')
def teams():
    all_teams = Team.query.all()
    return render_template('teams.html', teams=all_teams)


@app.route('/team/add', methods=['GET', 'POST'])
def add_team():
    if request.method == 'POST':
        # Handle file upload for team logo
        logo_url = None
        if 'team_logo' in request.files:
            file = request.files['team_logo']
            if file and file.filename:
                # Secure the filename and save temporarily
                filename = secure_filename(file.filename)

                # Create a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                    file.save(tmp.name)
                    tmp_path = tmp.name

                try:
                    # Upload to Cloudinary
                    upload_result = cloudinary.uploader.upload(
                        tmp_path,
                        folder="team_logos",
                        public_id=f"team_{int(datetime.utcnow().timestamp())}",
                        overwrite=True
                    )
                    logo_url = upload_result.get('secure_url')
                finally:
                    # Clean up temporary file
                    os.unlink(tmp_path)

        team = Team(
            name=request.form['name'],
            short_name=request.form['short_name'],
            owner=request.form['owner'],
            coach=request.form['coach'],
            total_budget=float(request.form['total_budget']),  # Now in rupees directly
            logo_url=logo_url
        )
        db.session.add(team)
        db.session.commit()
        flash('Team added successfully!', 'success')
        return redirect(url_for('teams'))
    return render_template('add_team.html')


@app.route('/team/view/<int:id>')
def view_team(id):
    team = Team.query.get_or_404(id)
    players = team.players.all()  # Use .all() to execute the query and get a list
    return render_template('view_team.html', team=team, players=players)


# Season Management Routes
@app.route('/seasons')
def seasons():
    all_seasons = Season.query.all()
    return render_template('seasons.html', seasons=all_seasons)


@app.route('/season/add', methods=['GET', 'POST'])
def add_season():
    if request.method == 'POST':
        season = Season(
            name=request.form['name'],
            start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d'),
            end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d')
        )
        db.session.add(season)
        db.session.commit()
        flash('Season added successfully!', 'success')
        return redirect(url_for('seasons'))
    return render_template('add_season.html')


@app.route('/season/activate/<int:id>')
def activate_season(id):
    # Deactivate all seasons first
    Season.query.update({Season.is_active: False})
    season = Season.query.get_or_404(id)
    season.is_active = True
    db.session.commit()
    flash(f'Season {season.name} activated!', 'success')
    return redirect(url_for('seasons'))


# Auction Management Routes
@app.route('/auctions')
def auctions():
    all_auctions = Auction.query.all()
    return render_template('auctions.html', auctions=all_auctions)


@app.route('/auction/create', methods=['GET', 'POST'])
def create_auction():
    seasons = Season.query.all()
    teams = Team.query.all()

    if request.method == 'POST':
        season_id = request.form['season_id']
        auction = Auction(
            season_id=season_id,
            name=request.form['name'],
            auction_date=datetime.strptime(request.form['auction_date'], '%Y-%m-%d')
        )
        db.session.add(auction)
        db.session.commit()

        # Get selected players
        player_ids = request.form.getlist('player_ids[]')

        for player_id in player_ids:
            if player_id:
                # Create auction participation
                participation = AuctionParticipation(
                    auction_id=auction.id,
                    player_id=player_id,
                    status='pending'
                )
                db.session.add(participation)

                # Update season registration status
                season_reg = PlayerSeasonRegistration.query.filter_by(
                    player_id=player_id,
                    season_id=season_id
                ).first()

                if season_reg:
                    season_reg.status = 'in_auction'

        db.session.commit()
        flash('Auction created successfully!', 'success')
        return redirect(url_for('auctions'))

    # Get current active season for default selection
    active_season = Season.query.filter_by(is_active=True).first()

    return render_template('create_auction.html', seasons=seasons, teams=teams, active_season=active_season)


@app.route('/api/add_player_to_auction', methods=['POST'])
def add_player_to_auction():
    try:
        data = request.json
        auction_id = data.get('auction_id')
        player_id = data.get('player_id')

        print(f"Adding player {player_id} to auction {auction_id}")  # Debug log

        if not auction_id or not player_id:
            return jsonify({'success': False, 'message': 'Missing auction_id or player_id'})

        # Check if auction exists
        auction = Auction.query.get(auction_id)
        if not auction:
            return jsonify({'success': False, 'message': 'Auction not found'})

        # Check if player exists
        player = Player.query.get(player_id)
        if not player:
            return jsonify({'success': False, 'message': 'Player not found'})

        # Check if player is registered for this season
        season_reg = PlayerSeasonRegistration.query.filter_by(
            player_id=player_id,
            season_id=auction.season_id
        ).first()

        if not season_reg:
            return jsonify({'success': False, 'message': 'Player not registered for this season'})

        # Check if player already in auction
        existing = AuctionParticipation.query.filter_by(
            auction_id=auction_id,
            player_id=player_id
        ).first()

        if existing:
            return jsonify({'success': False, 'message': 'Player already in auction'})

        # Create new participation
        participation = AuctionParticipation(
            auction_id=auction_id,
            player_id=player_id,
            status='pending'
        )
        db.session.add(participation)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Player {player.name} added to auction successfully'
        })

    except Exception as e:
        print(f"Error in add_player_to_auction: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})
@app.route('/auction/conduct/<int:id>')
def conduct_auction(id):
    auction = Auction.query.get_or_404(id)

    # Get the season ID from the auction
    season_id = auction.season_id

    # Get all players registered for this season with status 'registered'
    # Join with Player table to get player details
    registrations = db.session.query(Player, PlayerSeasonRegistration).join(
        Player, Player.id == PlayerSeasonRegistration.player_id
    ).filter(
        PlayerSeasonRegistration.season_id == season_id,
        PlayerSeasonRegistration.status == 'registered'
    ).all()

    # Extract player objects from registrations
    players = [reg[0] for reg in registrations]  # reg[0] is the Player object

    teams = Team.query.all()

    return render_template(
        'conduct_auction.html',
        auction=auction,
        players=players,  # Only registered players for this season
        teams=teams
    )


@app.route('/api/search_auction_player', methods=['POST'])
def search_auction_player():
    try:
        data = request.json
        auction_id = data.get('auction_id')
        player_id = data.get('player_id')
        player_name = data.get('player_name')

        if not auction_id:
            return jsonify({'success': False, 'message': 'No auction ID provided'})

        # Get the auction to find its season
        auction = Auction.query.get(auction_id)
        if not auction:
            return jsonify({'success': False, 'message': 'Auction not found'})

        season_id = auction.season_id

        # Base query for players registered for this season
        query = db.session.query(Player).join(
            PlayerSeasonRegistration,
            Player.id == PlayerSeasonRegistration.player_id
        ).filter(
            PlayerSeasonRegistration.season_id == season_id,
            PlayerSeasonRegistration.status == 'registered'
        )

        # Apply search filters
        if player_id:
            query = query.filter(Player.id == player_id)
        elif player_name:
            query = query.filter(Player.name.ilike(f'%{player_name}%'))
        else:
            return jsonify({'success': False, 'message': 'No search criteria provided'})

        # Execute query
        players = query.limit(10).all()

        # Format response
        players_list = []
        for player in players:
            # Check if player is already in this auction
            participation = AuctionParticipation.query.filter_by(
                auction_id=auction_id,
                player_id=player.id
            ).first()

            players_list.append({
                'id': player.id,
                'name': player.name,
                'age': player.age,
                'role': player.role,
                'batting_style': player.batting_style,
                'bowling_style': player.bowling_style,
                'image_url': player.image_url,
                'base_price': player.base_price,
                'base_price_formatted': f"₹{player.base_price:,.0f}",
                'in_auction': participation is not None,
                'participation_id': participation.id if participation else None,
                'participation_status': participation.status if participation else None
            })

        return jsonify({
            'success': True,
            'players': players_list,
            'season_name': auction.season.name
        })

    except Exception as e:
        print("Error in search_auction_player:", str(e))
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})

@app.route('/api/update_auction_player', methods=['POST'])
def update_auction_player():
    try:
        data = request.json
        print("Received data:", data)  # Debug print

        participation_id = data.get('participation_id')
        team_id = data.get('team_id')
        sold_price = data.get('sold_price')

        # Validation
        if not participation_id:
            return jsonify({'success': False, 'message': 'No participation ID provided'})

        # Get participation
        participation = AuctionParticipation.query.get(participation_id)
        if not participation:
            return jsonify({'success': False, 'message': f'Participation {participation_id} not found'})

        print(f"Found participation: {participation.id}, player_id: {participation.player_id}")

        # Handle unsold
        if not team_id or not sold_price or sold_price <= 0:
            participation.status = 'unsold'
            player = Player.query.get(participation.player_id)
            if player:
                player.status = 'unregistered'
            db.session.commit()
            return jsonify({'success': True, 'message': 'Player marked as unsold'})

        # Handle sold
        team = Team.query.get(team_id)
        if not team:
            return jsonify({'success': False, 'message': 'Team not found'})

        # Convert sold_price to float if it's string
        try:
            sold_price = float(sold_price)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'Invalid sold price format'})

        # Check budget
        if team.spent_amount + sold_price > team.total_budget:
            return jsonify({
                'success': False,
                'message': f'Insufficient budget! Required: ₹{sold_price:,.0f}, Available: ₹{(team.total_budget - team.spent_amount):,.0f}'
            })

        # Update participation
        participation.status = 'sold'
        participation.team_id = team_id
        participation.sold_price = sold_price

        # Update team spent amount
        team.spent_amount += sold_price

        # Update player status
        player = Player.query.get(participation.player_id)
        if player:
            player.status = 'sold'

        # Add player to team for active season
        active_season = Season.query.filter_by(is_active=True).first()
        if active_season and player:
            # Check if player already in team
            if player not in team.players:
                team.players.append(player)
                print(f"Added player {player.name} to team {team.name}")

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Player sold to {team.name} for ₹{sold_price:,.0f}',
            'data': {
                'team_name': team.name,
                'sold_price': sold_price,
                'remaining_budget': team.total_budget - team.spent_amount
            }
        })

    except Exception as e:
        print("Error in update_auction_player:", str(e))
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})


@app.route('/api/get_participation_details', methods=['POST'])
def get_participation_details():
    try:
        data = request.json
        participation_id = data.get('participation_id')

        if not participation_id:
            return jsonify({'success': False, 'message': 'No participation ID provided'})

        participation = AuctionParticipation.query.get(participation_id)
        if not participation:
            return jsonify({'success': False, 'message': 'Participation not found'})

        response_data = {
            'success': True,
            'participation_id': participation.id,
            'status': participation.status,
            'sold_price': participation.sold_price,
            'sold_price_formatted': f"₹{participation.sold_price:,.0f}" if participation.sold_price else None
        }

        if participation.team:
            response_data['team_id'] = participation.team.id
            response_data['team_name'] = participation.team.name
            response_data['team_short_name'] = participation.team.short_name

        return jsonify(response_data)

    except Exception as e:
        print("Error in get_participation_details:", str(e))
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})
@app.route('/api/sell_player', methods=['POST'])
def sell_player():
    data = request.json
    participation = AuctionParticipation.query.get(data['participation_id'])
    team = Team.query.get(data['team_id'])
    sold_price = float(data['sold_price'])

    if team.spent_amount + sold_price <= team.total_budget:
        participation.status = 'sold'
        participation.team_id = team.id
        participation.sold_price = sold_price
        team.spent_amount += sold_price

        # Add player to team
        player = Player.query.get(participation.player_id)
        player.status = 'sold'

        # Get active season
        active_season = Season.query.filter_by(is_active=True).first()
        if active_season:
            # Using the association table directly
            stmt = team_players.insert().values(
                team_id=team.id,
                player_id=player.id,
                season_id=active_season.id,
                joined_date=datetime.utcnow()
            )
            db.session.execute(stmt)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Player sold successfully!'})
    else:
        return jsonify({'success': False, 'message': 'Insufficient budget!'})


@app.route('/api/unsold_player', methods=['POST'])
def unsold_player():
    data = request.json
    participation = AuctionParticipation.query.get(data['participation_id'])
    participation.status = 'unsold'
    player = Player.query.get(participation.player_id)
    player.status = 'unregistered'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Player marked as unsold'})


# Match Management Routes
@app.route('/matches')
def matches():
    all_matches = Match.query.all()
    return render_template('matches.html', matches=all_matches)


@app.route('/match/schedule', methods=['GET', 'POST'])
def schedule_match():
    if request.method == 'POST':
        match = Match(
            season_id=request.form['season_id'],
            team1_id=request.form['team1_id'],
            team2_id=request.form['team2_id'],
            match_date=datetime.strptime(request.form['match_date'], '%Y-%m-%dT%H:%M'),
            venue=request.form['venue']
        )
        db.session.add(match)
        db.session.commit()
        flash('Match scheduled successfully!', 'success')
        return redirect(url_for('matches'))

    seasons = Season.query.all()
    teams = Team.query.all()
    return render_template('schedule_match.html', seasons=seasons, teams=teams)


@app.route('/match/scoreboard/<int:id>')
def match_scoreboard(id):
    match = Match.query.get_or_404(id)
    innings = Innings.query.filter_by(match_id=id).all()
    return render_template('match_scoreboard.html', match=match, innings=innings)


@app.route('/match/update_score/<int:id>', methods=['GET', 'POST'])
def update_score(id):
    match = Match.query.get_or_404(id)

    if request.method == 'POST':
        innings_number = int(request.form['innings_number'])
        team_id = int(request.form['team_id'])

        # Check if innings exists
        innings = Innings.query.filter_by(match_id=id, innings_number=innings_number).first()
        if not innings:
            innings = Innings(
                match_id=id,
                team_id=team_id,
                innings_number=innings_number
            )
            db.session.add(innings)
            db.session.commit()

        # Update match status
        match.status = 'ongoing'

        # Get all player indices from the form
        player_indices = request.form.getlist('player_index[]')

        for idx in player_indices:
            player_id = request.form.get(f'player_id_{idx}')
            if player_id:
                performance = MatchPerformance(
                    match_id=id,
                    innings_id=innings.id,
                    player_id=int(player_id),
                    team_id=team_id,
                    runs_scored=int(request.form.get(f'runs_scored_{idx}', 0)),
                    balls_faced=int(request.form.get(f'balls_faced_{idx}', 0)),
                    fours=int(request.form.get(f'fours_{idx}', 0)),
                    sixes=int(request.form.get(f'sixes_{idx}', 0)),
                    is_out=request.form.get(f'is_out_{idx}') == 'on',
                    out_type=request.form.get(f'out_type_{idx}'),
                    overs_bowled=float(request.form.get(f'overs_bowled_{idx}', 0)),
                    maidens=int(request.form.get(f'maidens_{idx}', 0)),
                    runs_conceded=int(request.form.get(f'runs_conceded_{idx}', 0)),
                    wickets=int(request.form.get(f'wickets_{idx}', 0)),
                    catches=int(request.form.get(f'catches_{idx}', 0)),
                    stumpings=int(request.form.get(f'stumpings_{idx}', 0)),
                    run_outs=int(request.form.get(f'run_outs_{idx}', 0))
                )
                db.session.add(performance)

        # Calculate innings totals
        performances = MatchPerformance.query.filter_by(innings_id=innings.id).all()
        innings.total_runs = sum(p.runs_scored for p in performances)
        innings.total_wickets = sum(1 for p in performances if p.is_out)
        innings.total_overs = max((p.overs_bowled for p in performances), default=0)

        db.session.commit()
        flash(f'Innings {innings_number} updated successfully!', 'success')
        return redirect(url_for('match_scoreboard', id=id))

    # GET request - show the update form
    teams = [match.team1_home, match.team2_away]  # Updated relationship names
    players_team1 = match.team1_home.players.all() if match.team1_home else []
    players_team2 = match.team2_away.players.all() if match.team2_away else []

    return render_template('update_score.html', match=match, teams=teams,
                           players_team1=players_team1, players_team2=players_team2)


@app.route('/match/complete/<int:id>', methods=['POST'])
def complete_match(id):
    match = Match.query.get_or_404(id)
    match.status = 'completed'
    match.result = request.form['result']
    match.man_of_match_id = request.form.get('man_of_match')
    db.session.commit()
    flash('Match completed successfully!', 'success')
    return redirect(url_for('match_scoreboard', id=id))


# API endpoint for player statistics
@app.route('/api/player_stats/<int:player_id>')
def player_stats(player_id):
    player = Player.query.get_or_404(player_id)
    performances = MatchPerformance.query.filter_by(player_id=player_id).all()

    # Calculate statistics
    total_runs = sum(p.runs_scored for p in performances)
    total_innings = len([p for p in performances if p.runs_scored > 0 or p.balls_faced > 0])
    total_wickets = sum(p.wickets for p in performances)
    total_balls_faced = sum(p.balls_faced for p in performances)
    total_overs_bowled = sum(p.overs_bowled for p in performances)
    total_runs_conceded = sum(p.runs_conceded for p in performances)

    batting_avg = total_runs / total_innings if total_innings > 0 else 0
    strike_rate = (total_runs / total_balls_faced) * 100 if total_balls_faced > 0 else 0
    bowling_avg = total_runs_conceded / total_wickets if total_wickets > 0 else 0
    economy = total_runs_conceded / total_overs_bowled if total_overs_bowled > 0 else 0

    return jsonify({
        'batting_avg': round(batting_avg, 2),
        'strike_rate': round(strike_rate, 2),
        'bowling_avg': round(bowling_avg, 2),
        'economy': round(economy, 2)
    })


# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
#     app.run(debug=True)

# Initialize DB tables when the app starts
with app.app_context():
    db.create_all()

# Only needed for local development
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)