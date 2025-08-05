from flask_login import UserMixin
from app import db

date_time_assoc_table = db.Table('date_time_assoc_table',
                                 db.Column('datetime_slot_id', db.ForeignKey('datetime_slots.id')),
                                 db.Column('poll_vote_id', db.ForeignKey('poll_votes.id')))


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    def __str__(self):
        return self.name


class DateTimeSlot(db.Model):
    __tablename__ = 'datetime_slots'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column(db.DateTime(timezone=True), nullable=False)
    end = db.Column(db.DateTime(timezone=True), nullable=False)
    poll_votes = db.relationship('PollVote', secondary=date_time_assoc_table, backref=db.backref('datetime_slots'))
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'))

    def __str__(self):
        return f'{self.start.strftime("%Y-%m-%d %H:%M")} to {self.end.strftime("%Y-%m-%d %H:%M")}'


class Poll(db.Model):
    __tablename__ = 'polls'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(), nullable=False, info={'label': 'Title'})
    start_date = db.Column(db.Date(), nullable=False, info={'label': 'Start Date'})
    desc = db.Column(db.Text(), info={'label': 'Description'})
    end_date = db.Column(db.Date(), nullable=False, info={'label': 'End Date'})
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator = db.relationship('User', backref=db.backref('polls'))
    created_at = db.Column(db.DateTime(timezone=True))
    modified_at = db.Column(db.DateTime(timezone=True))
    closed_at = db.Column(db.DateTime(timezone=True))

    def __str__(self):
        return f'{self.title}'

    @property
    def date_span(self):
        return f'{self.start_date.strftime("%d/%m/%Y")} to {self.end_date.strftime("%d/%m/%Y")}'

    @property
    def voted(self):
        return [i for i in self.invitations if i.voted_at]


class PollMessage(db.Model):
    __tablename__ = 'poll_messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message = db.Column(db.String(), info={'label': 'Message'})
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'), nullable=False)
    poll = db.relationship(Poll, backref=db.backref('messages'))
    voter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    voter = db.relationship(User, backref=db.backref('messages'))
    created_at = db.Column(db.DateTime(timezone=True))


class PollVote(db.Model):
    __tablename__ = 'poll_votes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'), nullable=False)
    voter = db.relationship(User, backref=db.backref('votes'))
    poll = db.relationship(Poll, backref=db.backref('invitations', lazy='dynamic'))
    last_notified = db.Column(db.DateTime(timezone=True))  # update this every time the notification is sent
    voted_at = db.Column(db.DateTime(timezone=True))
    num_notifications = db.Column(db.Integer(), default=0)
    role = db.Column(db.String(), info={'label': 'Role',
                                        'choices': [(r, r) for r in ['committee', 'chairman']]})
