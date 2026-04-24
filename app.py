import os
import secrets
from flask import Flask, abort, jsonify, request, session
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, setup_database, Ingredient, Product, RecipeItem, SalesRecord, User
from predictor import StockPredictor


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db_path = os.path.join(app.instance_path, 'erp.sqlite')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{db_path}')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 8 * 1024 * 1024))
    app.config['KITCHEN_POLL_INTERVAL_MS'] = int(os.environ.get('KITCHEN_POLL_INTERVAL_MS', '15000'))
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config['REMEMBER_COOKIE_SAMESITE'] = os.environ.get('REMEMBER_COOKIE_SAMESITE', 'Lax')
    app.config['SESSION_COOKIE_SECURE'] = env_flag('SESSION_COOKIE_SECURE', not app.debug)
    app.config['REMEMBER_COOKIE_SECURE'] = env_flag('REMEMBER_COOKIE_SECURE', not app.debug)
    app.config['PREFERRED_URL_SCHEME'] = os.environ.get('PREFERRED_URL_SCHEME', 'https')

    if env_flag('TRUST_PROXY', True):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    # Initialize Database
    setup_database(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Initialize Predictor and attach it to the app instance
    app.predictor = StockPredictor(app.config['SQLALCHEMY_DATABASE_URI'])

    # Import and register Blueprints
    from routes.ui import ui_bp
    app.register_blueprint(ui_bp)

    from routes.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    @app.context_processor
    def inject_csrf_token():
        def csrf_token():
            token = session.get('_csrf_token')
            if not token:
                token = secrets.token_urlsafe(32)
                session['_csrf_token'] = token
            return token
        return {'csrf_token': csrf_token}

    @app.before_request
    def validate_csrf():
        if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return

        session_token = session.get('_csrf_token')
        request_token = request.headers.get('X-CSRF-Token')

        if not request_token:
            if request.is_json:
                payload = request.get_json(silent=True) or {}
                request_token = payload.get('_csrf_token')
            else:
                request_token = request.form.get('_csrf_token')

        if not session_token or not request_token or not secrets.compare_digest(session_token, request_token):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'CSRF validation failed'}), 400
            abort(400, description='CSRF validation failed')

    # --- CLI Commands ---
    @app.cli.command("seed")
    def seed_data():
        """Seeds the database with initial data."""
        print("Seeding database...")
        try:
            db.session.query(SalesRecord).delete()
            db.session.query(RecipeItem).delete()
            db.session.query(Product).delete()
            db.session.query(Ingredient).delete()
            db.session.commit()

            # Ingredients
            i1 = Ingredient(name='Coffee Beans', current_stock=10000, unit_of_measure='g')
            i2 = Ingredient(name='Milk', current_stock=20000, unit_of_measure='ml')
            i3 = Ingredient(name='Sugar', current_stock=5000, unit_of_measure='g')
            i4 = Ingredient(name='Water', current_stock=50000, unit_of_measure='ml')
            db.session.add_all([i1, i2, i3, i4])
            db.session.commit()

            # Products
            p1 = Product(name='Espresso', selling_price=2.50)
            p2 = Product(name='Latte', selling_price=3.50)
            p3 = Product(name='Cappuccino', selling_price=3.50)
            db.session.add_all([p1, p2, p3])
            db.session.commit()

            # Recipes
            r1 = RecipeItem(product_id=p1.id, ingredient_id=i1.id, quantity_needed=18)
            r2 = RecipeItem(product_id=p1.id, ingredient_id=i4.id, quantity_needed=60)
            r3 = RecipeItem(product_id=p2.id, ingredient_id=i1.id, quantity_needed=18)
            r4 = RecipeItem(product_id=p2.id, ingredient_id=i2.id, quantity_needed=250)
            r5 = RecipeItem(product_id=p3.id, ingredient_id=i1.id, quantity_needed=18)
            r6 = RecipeItem(product_id=p3.id, ingredient_id=i2.id, quantity_needed=150)
            db.session.add_all([r1, r2, r3, r4, r5, r6])

            db.session.commit()
            print("Database seeded successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error seeding database: {e}")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5053)
