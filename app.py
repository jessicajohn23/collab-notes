from flask import Flask, render_template, redirect, url_for
from flask_socketio import SocketIO, join_room, emit
from model import db, Note
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-secret-key-change-this'
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Track number of users viewing each note
active_users = {}  # note_id: count

# Home: list + create notes
@app.route('/')
def index():
    notes = Note.query.order_by(Note.updated_at.desc()).all()
    return render_template('index.html', notes=notes)

@app.route('/create', methods=['POST'])
def create():
    note = Note()
    db.session.add(note)
    db.session.commit()
    return redirect(url_for('note_page', note_id=note.id))

# Note editor page
@app.route('/note/<note_id>')
def note_page(note_id):
    note = Note.query.get_or_404(note_id)
    return render_template('note.html', note=note)

@app.route('/delete/<note_id>', methods=['POST'])
def delete(note_id):
    note = Note.query.get_or_404(note_id)
    db.session.delete(note)
    db.session.commit()
    return redirect(url_for('index'))

# WebSocket events

@socketio.on('join')
def on_join(data):
    note_id = data['note_id']
    join_room(note_id)
    active_users[note_id] = active_users.get(note_id, 0) + 1
    emit('user_count', {'count': active_users[note_id]}, room=note_id)

@socketio.on('leave')
def on_leave(data):
    note_id = data['note_id']
    active_users[note_id] = max(0, active_users.get(note_id, 1) - 1)
    emit('user_count', {'count': active_users[note_id]}, room=note_id)

@socketio.on('content_change')
def on_content_change(data):
    note_id = data['note_id']
    content = data['content']

    # Save to database
    note = Note.query.get(note_id)
    if note:
        note.content = content
        note.updated_at = datetime.utcnow()
        db.session.commit()

    # Broadcast to others in the room (not back to sender)
    emit('content_update', {'content': content}, room=note_id, include_self=False)

@socketio.on('title_change')
def on_title_change(data):
    note_id = data['note_id']
    title = data['title']

    note = Note.query.get(note_id)
    if note:
        note.title = title
        db.session.commit()

    emit('title_update', {'title': title}, room=note_id, include_self=False)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)