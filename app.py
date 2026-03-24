from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'yahya-portfolio-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///portfolio.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'يرجى تسجيل الدخول للوصول إلى النظام'

# ══════════════════════════════════════════════
# النماذج
# ══════════════════════════════════════════════

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    usage_count = db.Column(db.Integer, default=0)
    max_usage = db.Column(db.Integer, default=2)
    is_premium = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def remaining_uses(self):
        if self.is_premium:
            return 999
        return max(0, self.max_usage - self.usage_count)

    @property
    def can_use(self):
        return self.is_premium or self.usage_count < self.max_usage

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ══════════════════════════════════════════════
# المسارات
# ══════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            if not user.can_use:
                return redirect(url_for('trial_expired'))
            return redirect(url_for('dashboard'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if not current_user.can_use:
        return redirect(url_for('trial_expired'))
    return render_template('dashboard.html')

@app.route('/use-session', methods=['POST'])
@login_required
def use_session():
    if not current_user.can_use:
        return jsonify({'error': 'trial_expired'}), 403
    current_user.usage_count += 1
    db.session.commit()
    return jsonify({
        'remaining': current_user.remaining_uses,
        'can_use': current_user.can_use
    })

@app.route('/trial-expired')
@login_required
def trial_expired():
    return render_template('trial_expired.html')

# ══════════════════════════════════════════════
# التهيئة
# ══════════════════════════════════════════════

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='yahya').first():
            admin = User(username='yahya', is_premium=True)
            admin.set_password('Yahya@2024')
            db.session.add(admin)
        if not User.query.filter_by(username='demo').first():
            demo = User(username='demo', is_premium=False, max_usage=2)
            demo.set_password('demo123')
            db.session.add(demo)
        db.session.commit()
        print("✅ قاعدة البيانات جاهزة")

if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
