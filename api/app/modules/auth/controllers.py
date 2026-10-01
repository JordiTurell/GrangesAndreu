from flask import request, jsonify
from ..auth.services import authenticate_user, create_user
from ..auth.entities import User

def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = authenticate_user(username, password)
    if user:
        return jsonify({'message': 'Login successful', 'user_id': user.id}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    # Check if user already exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'error': 'Username already exists'}), 400
    
    # Create new user
    new_user = create_user(username, password, email)
    return jsonify({'message': 'User created successfully', 'user_id': new_user.id}), 201