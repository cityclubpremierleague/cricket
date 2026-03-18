from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Player(db.Model):
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(50), nullable=False)
    batting_style = db.Column(db.String(50))
    bowling_style = db.Column(db.String(50))
    jersey = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    base_price = db.Column(db.Float, default=200)  # Default 200 rupees
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Remove status field - we'll track via season_registrations

    # Relationships
    season_registrations = db.relationship('PlayerSeasonRegistration', back_populates='player', lazy='dynamic')
    auction_participations = db.relationship('AuctionParticipation', back_populates='player', lazy='dynamic')
    match_performances = db.relationship('MatchPerformance', back_populates='player', lazy='dynamic')


class PlayerSeasonRegistration(db.Model):
    __tablename__ = 'player_season_registrations'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=False)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='registered')  # registered, sold, unsold

    # Relationships
    player = db.relationship('Player', back_populates='season_registrations')
    season = db.relationship('Season')

    __table_args__ = (db.UniqueConstraint('player_id', 'season_id', name='unique_player_season'),)


class Team(db.Model):
    __tablename__ = 'teams'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    short_name = db.Column(db.String(10), unique=True, nullable=False)
    logo_url = db.Column(db.String(500))  # New field for team logo
    owner = db.Column(db.String(100))
    coach = db.Column(db.String(100))
    total_budget = db.Column(db.Float, default=100000)  # 10 thousand default
    spent_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    players = db.relationship('Player', secondary='team_players', backref=db.backref('teams_list', lazy='dynamic'),
                              lazy='dynamic')
    auctions = db.relationship('AuctionParticipation', back_populates='team', lazy='dynamic')
    home_matches = db.relationship('Match', foreign_keys='Match.team1_id', back_populates='team1_home', lazy='dynamic')
    away_matches = db.relationship('Match', foreign_keys='Match.team2_id', back_populates='team2_away', lazy='dynamic')
    toss_won_matches = db.relationship('Match', foreign_keys='Match.toss_winner_id', back_populates='toss_winner_team',
                                       lazy='dynamic')


class Season(db.Model):
    __tablename__ = 'seasons'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    auctions = db.relationship('Auction', back_populates='season', lazy='dynamic')
    matches = db.relationship('Match', back_populates='season', lazy='dynamic')


class Auction(db.Model):
    __tablename__ = 'auctions'

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    auction_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='upcoming')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    season = db.relationship('Season', back_populates='auctions')
    participations = db.relationship('AuctionParticipation', back_populates='auction', lazy='dynamic',
                                     cascade='all, delete-orphan')


class AuctionParticipation(db.Model):
    __tablename__ = 'auction_participations'

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(db.Integer, db.ForeignKey('auctions.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    sold_price = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')  # pending, sold, unsold
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    auction = db.relationship('Auction', back_populates='participations')
    player = db.relationship('Player', back_populates='auction_participations')
    team = db.relationship('Team', back_populates='auctions')


class Match(db.Model):
    __tablename__ = 'matches'

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=False)
    team1_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    team2_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    match_date = db.Column(db.DateTime, nullable=False)
    venue = db.Column(db.String(200))
    toss_winner_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    toss_decision = db.Column(db.String(10))  # bat, bowl
    status = db.Column(db.String(20), default='scheduled')  # scheduled, ongoing, completed
    result = db.Column(db.String(200))
    man_of_match_id = db.Column(db.Integer, db.ForeignKey('players.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships with unique back_populates names
    season = db.relationship('Season', back_populates='matches')
    team1_home = db.relationship('Team', foreign_keys=[team1_id], back_populates='home_matches')
    team2_away = db.relationship('Team', foreign_keys=[team2_id], back_populates='away_matches')
    toss_winner_team = db.relationship('Team', foreign_keys=[toss_winner_id], back_populates='toss_won_matches')
    man_of_match = db.relationship('Player', foreign_keys=[man_of_match_id])
    innings = db.relationship('Innings', back_populates='match', lazy='dynamic', cascade='all, delete-orphan')


class Innings(db.Model):
    __tablename__ = 'innings'

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    innings_number = db.Column(db.Integer, nullable=False)  # 1, 2
    total_runs = db.Column(db.Integer, default=0)
    total_wickets = db.Column(db.Integer, default=0)
    total_overs = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    match = db.relationship('Match', back_populates='innings')
    team = db.relationship('Team')
    performances = db.relationship('MatchPerformance', back_populates='innings', lazy='dynamic',
                                   cascade='all, delete-orphan')


class MatchPerformance(db.Model):
    __tablename__ = 'match_performances'

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    innings_id = db.Column(db.Integer, db.ForeignKey('innings.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)

    # Batting stats
    runs_scored = db.Column(db.Integer, default=0)
    balls_faced = db.Column(db.Integer, default=0)
    fours = db.Column(db.Integer, default=0)
    sixes = db.Column(db.Integer, default=0)
    batting_position = db.Column(db.Integer)
    is_out = db.Column(db.Boolean, default=False)
    out_type = db.Column(db.String(50))  # bowled, caught, lbw, run_out, stumped

    # Bowling stats
    overs_bowled = db.Column(db.Float, default=0)
    maidens = db.Column(db.Integer, default=0)
    runs_conceded = db.Column(db.Integer, default=0)
    wickets = db.Column(db.Integer, default=0)

    # Fielding stats
    catches = db.Column(db.Integer, default=0)
    stumpings = db.Column(db.Integer, default=0)
    run_outs = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    match = db.relationship('Match')
    innings = db.relationship('Innings', back_populates='performances')
    player = db.relationship('Player', back_populates='match_performances')
    team = db.relationship('Team')


# Association table for team players
team_players = db.Table('team_players',
                        db.Column('team_id', db.Integer, db.ForeignKey('teams.id'), primary_key=True),
                        db.Column('player_id', db.Integer, db.ForeignKey('players.id'), primary_key=True),
                        db.Column('season_id', db.Integer, db.ForeignKey('seasons.id')),
                        db.Column('joined_date', db.DateTime, default=datetime.utcnow)
                        )