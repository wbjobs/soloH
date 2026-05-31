import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from werkzeug.security import generate_password_hash

from .config import Config
from .models.models import db, User, ReferenceGenome
from .routes.auth_routes import auth_bp
from .routes.upload_routes import upload_bp
from .routes.analysis_routes import analysis_bp
from .routes.task_routes import task_bp
from .routes.result_routes import result_bp
from .routes.reference_routes import reference_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    Config.ensure_directories()
    
    db.init_app(app)
    JWTManager(app)
    
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config['CORS_ORIGINS'],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(task_bp, url_prefix='/api/tasks')
    app.register_blueprint(result_bp, url_prefix='/api/results')
    app.register_blueprint(reference_bp, url_prefix='/api/reference')
    
    @app.route('/api/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'message': 'GWAS Analysis API is running'
        })
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error', 'message': str(error)}), 500
    
    with app.app_context():
        db.create_all()
        _init_reference_genomes()
        _init_demo_user()
    
    return app

def _init_reference_genomes():
    default_genomes = [
        {
            'id': 'B73_v5',
            'name': 'B73',
            'species': 'Zea mays',
            'version': 'v5',
            'description': '玉米标准参考基因组，最广泛使用的自交系 (AGPv5)',
            'fasta_path': './data/reference/maize/B73_v5/genome.fasta',
            'gff_path': './data/reference/maize/B73_v5/annotation.gff3'
        },
        {
            'id': 'Mo17_v1',
            'name': 'Mo17',
            'species': 'Zea mays',
            'version': 'v1',
            'description': '重要的玉米自交系，与B73杂交产生著名杂交种',
            'fasta_path': './data/reference/maize/Mo17_v1/genome.fasta',
            'gff_path': './data/reference/maize/Mo17_v1/annotation.gff3'
        },
        {
            'id': 'W22_v2',
            'name': 'W22',
            'species': 'Zea mays',
            'version': 'v2',
            'description': '常用的实验品系，遗传背景清晰',
            'fasta_path': './data/reference/maize/W22_v2/genome.fasta',
            'gff_path': './data/reference/maize/W22_v2/annotation.gff3'
        },
        {
            'id': 'PH207_v1',
            'name': 'PH207',
            'species': 'Zea mays',
            'version': 'v1',
            'description': '玉米父本系，重要的育种材料',
            'fasta_path': './data/reference/maize/PH207_v1/genome.fasta',
            'gff_path': './data/reference/maize/PH207_v1/annotation.gff3'
        },
        {
            'id': 'B97_v1',
            'name': 'B97',
            'species': 'Zea mays',
            'version': 'v1',
            'description': '耐旱自交系，抗逆性研究的重要材料',
            'fasta_path': './data/reference/maize/B97_v1/genome.fasta',
            'gff_path': './data/reference/maize/B97_v1/annotation.gff3'
        }
    ]
    
    for genome_data in default_genomes:
        if not ReferenceGenome.query.get(genome_data['id']):
            genome = ReferenceGenome(**genome_data)
            db.session.add(genome)
    
    db.session.commit()

def _init_demo_user():
    if not User.query.filter_by(email='demo@gwas.com').first():
        demo_user = User(
            email='demo@gwas.com',
            password_hash=generate_password_hash('demo123456'),
            name='Demo User'
        )
        db.session.add(demo_user)
        db.session.commit()

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
