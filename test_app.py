import pytest
import json
import os
os.environ['GROQ_API_KEY'] = 'test_key'

from app import app, init_db, get_db

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret'
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

def test_login_page_loads(client):
    response = client.get('/login')
    assert response.status_code == 200

def test_register_page_loads(client):
    response = client.get('/register')
    assert response.status_code == 200

def test_register_new_user(client):
    response = client.post('/register', data={
        'username': 'testuser',
        'email': 'test@test.com',
        'password': 'password123'
    }, follow_redirects=True)
    assert response.status_code == 200

def test_login_wrong_password(client):
    client.post('/register', data={
        'username': 'testuser2',
        'email': 'test2@test.com',
        'password': 'correctpass'
    })
    response = client.post('/login', data={
        'username': 'testuser2',
        'password': 'wrongpass'
    })
    assert b'Invalid' in response.data

def test_save_score_requires_login(client):
    response = client.post('/api/save_score',
        data=json.dumps({'memory_score': 8, 'reaction_time': 220, 'attention_score': 90}),
        content_type='application/json'
    )
    assert response.status_code == 401

def test_stats_endpoint(client):
    response = client.get('/api/stats')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'total_sessions' in data

def test_leaderboard_endpoint(client):
    response = client.get('/api/leaderboard')
    assert response.status_code == 200
    assert isinstance(json.loads(response.data), list)

def test_digital_twin_insufficient_data(client):
    response = client.get('/api/digital_twin/unknownuser')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'insufficient_data'
