from app import create_app
import traceback
import json

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 'hector'
        sess['_user_id'] = 'hector'
    
    print("Testing /api/noticias...")
    resp = client.get('/api/noticias?page=1')
    print("STATUS:", resp.status_code)
    try:
        print("JSON length:", len(resp.get_data()))
    except Exception as e:
        print("Error getting json:", traceback.format_exc())
