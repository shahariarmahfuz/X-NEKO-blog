import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from sqlalchemy import func
from sqlalchemy.inspection import inspect
from datetime import datetime, timedelta

db = SQLAlchemy()
login_manager = LoginManager()
login_view = 'auth.login'

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # কনফিগারেশন
    app.config['SECRET_KEY'] = 'a-very-secret-key-that-should-be-changed'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://xneko_qqv7_user:895ROq5Yq0WMIDYZb4ygBhmjNKbJel6H@dpg-d1sgf4mmcj7s73dm37l0-a.singapore-postgres.render.com/xneko_qqv7'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from .models import User, Category, Notification, Post

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ব্লুপ্রিন্ট রেজিস্টার করা
    from .main import main_bp
    app.register_blueprint(main_bp)
    from .auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    from .admin import admin_bp
    app.register_blueprint(admin_bp)
    from .notifications import notif_bp
    app.register_blueprint(notif_bp)

    @app.context_processor
    def inject_data():
        top_categories = []
        try:
            inspector = inspect(db.engine)
            if inspector.has_table('post') and inspector.has_table('category'):
                top_categories_query = db.session.query(Category, func.count(Post.id).label('post_count'))\
                                    .join(Post.categories)\
                                    .group_by(Category.id)\
                                    .order_by(func.count(Post.id).desc())\
                                    .limit(5).all()
                top_categories = [category for category, count in top_categories_query]
        except Exception as e:
            print(f"Could not query top categories: {e}")

        current_year = datetime.utcnow().year
        unread_notifications_count = 0
        if current_user.is_authenticated:
            try:
                inspector = inspect(db.engine)
                if inspector.has_table('notification'):
                     unread_notifications_count = Notification.query.filter_by(recipient_id=current_user.id, is_read=False).count()
            except Exception as e:
                print(f"Could not query notifications: {e}")

        return dict(
            unread_notifications_count=unread_notifications_count, 
            top_categories=top_categories, 
            current_year=current_year
        )

    with app.app_context():
        db.create_all()

        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', email='admin@example.com', role='Admin', full_name='Admin User')
            admin_user.set_password('admin')
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin user created.")

        if Category.query.count() == 0:
            default_categories = ['লাইফস্টাইল', 'ইতিহাস', 'প্রযুক্তি', 'ভ্রমণ', 'স্বাস্থ্য']
            for cat_name in default_categories:
                category = Category(name=cat_name)
                db.session.add(category)
            db.session.commit()
            print("Default categories created.")

    return app