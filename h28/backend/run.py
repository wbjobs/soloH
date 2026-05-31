import os
from app import create_app, socketio
from config import config

env = os.getenv('FLASK_ENV', 'default')
app = create_app(config[env])

if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = config[env].DEBUG
    
    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        allow_unsafe_werkzeug=True
    )
