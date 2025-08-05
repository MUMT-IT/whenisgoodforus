from collections import defaultdict

from flask_admin.contrib.sqla import ModelView
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from flask import Flask, render_template, request, redirect, url_for, session
import calendar
import datetime
from zoneinfo import ZoneInfo

BKK_TZ = ZoneInfo('Asia/Bangkok')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'thisisasecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
admin = Admin(app)
login_manager = LoginManager(app)

from forms import *
from models import *

with app.app_context():
    db.create_all()

admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(DateTimeSlot, db.session))
admin.add_view(ModelView(Poll, db.session))
admin.add_view(ModelView(PollVote, db.session))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def index():
    polls = Poll.query
    users = User.query.all()
    return render_template('poll-list.html', polls=polls, users=users)


@app.route('/add-user', methods=['POST'])
def add_user():
    username = request.form.get('username')
    if not User.query.filter_by(name=username).first():
        user = User(name=username)
        db.session.add(user)
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/view/<int:poll_id>')
@login_required
def view_results(poll_id):
    vote_summary = defaultdict(list)
    for slot in DateTimeSlot.query.filter_by(poll_id=poll_id):
        for vote in slot.poll_votes:
            vote_summary[slot].append(vote.voter.name)
    return render_template('poll-results.html', votes=vote_summary)


@app.route('/messages/<int:poll_id>', methods=["GET", "POST"])
@login_required
def leave_message(poll_id):
    poll = Poll.query.get(poll_id)
    form = PollMessageForm()
    if form.validate_on_submit():
        message = PollMessage(poll_id=poll_id)
        form.populate_obj(message)
        message.voter_id = current_user.id
        message.created_at = datetime.datetime.now().astimezone(tz=BKK_TZ)
        db.session.add(message)
        db.session.commit()
        return redirect(url_for('index'))
    else:
        print(form.errors)
    return render_template('poll-message-form.html', poll=poll, form=form)


@app.route('/login')
def login():
    if current_user.is_authenticated:
        logout_user()

    user_id = request.args.get('user_id')
    user = User.query.get(user_id)
    login_user(user)
    return redirect(url_for('index'))


@app.route('/new', methods=['GET', 'POST'])
@login_required
def add_poll():
    form = PollForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            poll = Poll()
            form.populate_obj(poll)
            chair_invitation = PollVote(voter=form.chairman.data, poll=poll, role='chairman')
            db.session.add(chair_invitation)
            for user in form.invitees.data:
                invitation = PollVote(voter=user, poll=poll, role='committee')
                db.session.add(invitation)
                # TODO: send email to notify all invitees.
            poll.created_at = datetime.datetime.now().astimezone(tz=BKK_TZ)
            poll.creator_id = current_user.id
            db.session.add(poll)
            db.session.commit()
            return redirect(url_for('index'))
        else:
            return f'{form.errors}'
    return render_template('poll-setup-form.html', form=form)


@app.route('/edit/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def edit_poll(poll_id):
    poll = Poll.query.get(poll_id)
    form = PollForm(obj=poll)
    form.chairman.data = PollVote.query.filter_by(poll=poll, role='chairman').first().voter
    form.invitees.data = [inv.voter for inv in PollVote.query.filter_by(poll=poll)]

    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(poll)
            for user in form.invitees.data:
                # Check for new invitees.
                if not PollVote.query.filter_by(voter=user, poll=poll).first():
                    invitation = PollVote(voter=user, poll=poll)
                    db.session.add(invitation)
            # TODO: send email to notify all invitees.
            poll.modified_at = datetime.datetime.now().astimezone(tz=BKK_TZ)
            db.session.add(poll)
            db.session.commit()
            return redirect(url_for('index'))
        else:
            return f'{form.errors}'
    return render_template('poll-setup-form.html', form=form, poll_id=poll_id)


@app.route('/delete/<int:poll_id>')
@login_required
def delete_poll(poll_id):
    poll = Poll.query.get(poll_id)
    db.session.delete(poll)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/close/<int:poll_id>')
@login_required
def close_poll(poll_id):
    poll = Poll.query.get(poll_id)
    poll.closed_at = datetime.datetime.now().astimezone(tz=BKK_TZ)
    db.session.add(poll)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/vote/polls/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def vote_poll(poll_id):
    poll = Poll.query.get(poll_id)
    # If the user has already voted this poll
    vote = PollVote.query.filter_by(poll_id=poll_id, voter=current_user).first()
    form = PollVoteForm()
    if request.method == 'POST':
        if not vote:
            vote = PollVote(poll=poll, voter=current_user)
        else:
            vote.datetime_slots = []
        for _form_field in form.date_time_slots:
            for t in _form_field.time_slots.data:
                _start, _end = t.split('#')[1].split(' - ')
                _start = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _start
                _end = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _end
                _start_datetime = datetime.datetime.strptime(_start, '%Y-%m-%d %H:%M').astimezone(tz=BKK_TZ)
                _end_datetime = datetime.datetime.strptime(_end, '%Y-%m-%d %H:%M').astimezone(tz=BKK_TZ)
                ds = DateTimeSlot.query.filter_by(start=_start_datetime, end=_end_datetime, poll_id=poll_id).first()
                if not ds:
                    ds = DateTimeSlot(start=_start_datetime, end=_end_datetime, poll_id=poll_id)
                vote.datetime_slots.append(ds)
                db.session.add(ds)
        vote.voted_at = datetime.datetime.now().astimezone(tz=BKK_TZ)
        db.session.add(vote)
        db.session.commit()
        return redirect(url_for('index'))

    if request.method == 'GET':
        if vote:
            voted_time_slots = [t.start.strftime('%Y-%m-%d#%H:%M - ') + t.end.strftime('%H:%M')
                                for t in vote.datetime_slots]
        current = poll.start_date
        delta = datetime.timedelta(days=1)

        while current <= poll.end_date:
            if calendar.weekday(current.year, current.month, current.day) < 5:
                form.date_time_slots.append_entry({'date': current})
            current += delta
        for _form_field in form.date_time_slots:
            choices = [dt for dt in [(_form_field.date.data.strftime('%Y-%m-%d') + '#09:00 - 12:00', '09:00 - 12:00'),
                                     (_form_field.date.data.strftime('%Y-%m-%d') + '#13:00 - 16:00', '13:00 - 16:00')]]
            _form_field.time_slots.choices = choices
            _form_field.time_slots.data = []
            if vote:
                _form_field.time_slots.data = [t[0] for t in choices if t[0] in voted_time_slots]

        return render_template('poll-form.html', form=form, poll=poll)
