from ..auth.entities import User
from werkzeug.security import generate_password_hash, check_password_hash

def authenticate_user(username, password):
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        return user
    return None

def create_user(username, password, email):
    password_hash = generate_password_hash(password)
    new_user = User(username=username, password_hash=password_hash, email=email)
    # Assuming you have a db session object to commit the new user
    # db.session.add(new_user)
    # db.session.commit()
    return new_user