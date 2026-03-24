from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import io

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'yahya-portfolio-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///portfolio.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv', 'sav', 'doc', 'docx', 'pdf'}

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


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ══════════════════════════════════════════════
# المسارات العامة
# ══════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('templates/index.html')


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
    return render_template('templates/login.html')


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
    return render_template('templates/dashboard.html')


@app.route('/trial-expired')
@login_required
def trial_expired():
    return render_template('templates/trial_expired.html')


# ══════════════════════════════════════════════
# مسار التحليل الإحصائي الحقيقي
# ══════════════════════════════════════════════

@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    if not current_user.can_use:
        return jsonify({'error': 'trial_expired', 'message': 'انتهت النسخة التجريبية'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'no_file', 'message': 'لم يتم رفع أي ملف'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'empty_file', 'message': 'لم يتم اختيار ملف'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'invalid_type', 'message': 'نوع الملف غير مدعوم. الأنواع المدعومة: xlsx, csv, sav, doc, docx, pdf'}), 400

    analysis_type = request.form.get('analysis_type', 'full')

    try:
        from analyzer import run_full_analysis
        results, word_report, error = run_full_analysis(file, analysis_type)

        if error and results is None:
            return jsonify({'error': 'analysis_failed', 'message': error}), 500

        # زيادة عداد الاستخدام
        current_user.usage_count += 1
        db.session.commit()

        # تخزين تقرير Word
        report_key = None
        if word_report:
            report_key = f"report_{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            app.config.setdefault('REPORTS', {})[report_key] = word_report.getvalue()

        return jsonify({
            'success': True,
            'remaining': current_user.remaining_uses,
            'filename': file.filename,
            'n': results.get('n', 0),
            'columns': results.get('columns', []),
            'numeric_columns': results.get('numeric_columns', []),
            'report_key': report_key,
            'summary': build_summary(results),
            'tables': build_tables(results)
        })

    except Exception as e:
        import traceback
        return jsonify({
            'error': 'exception',
            'message': f'خطأ: {str(e)}',
            'details': traceback.format_exc()
        }), 500


@app.route('/download-report/<report_key>')
@login_required
def download_report(report_key):
    reports = app.config.get('REPORTS', {})
    if report_key not in reports:
        return 'التقرير غير موجود أو انتهت صلاحيته', 404
    return send_file(
        io.BytesIO(reports[report_key]),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=f'تقرير_التحليل_{datetime.now().strftime("%Y%m%d")}.docx'
    )


def build_summary(results):
    lines = []
    lines.append(f"✅ تم تحليل الملف بنجاح")
    lines.append(f"📊 عدد المشاهدات: {results.get('n', 0)}")
    lines.append(f"📋 عدد المتغيرات: {len(results.get('columns', []))}")
    lines.append(f"🔢 المتغيرات الكمية: {len(results.get('numeric_columns', []))}")
    lines.append("─" * 40)

    rel = results.get('reliability', {})
    if 'alpha' in rel:
        lines.append(f"🔬 ألفا كرونباخ: {rel['alpha']:.3f} — {rel['interpretation']}")

    desc = results.get('descriptive', {})
    if 'relative_weights' in desc:
        lines.append("─" * 40)
        lines.append("📈 الأوزان النسبية للمتغيرات:")
        for col, rw in list(desc['relative_weights'].items())[:5]:
            bar = '█' * int(rw / 10)
            lines.append(f"  {str(col)[:20]}: {rw:.1f}% {bar}")

    reg = results.get('regression', {})
    if 'models' in reg:
        lines.append("─" * 40)
        lines.append("📉 نتائج الانحدار:")
        for m in reg['models'][:3]:
            sig = "دالة **" if m['significant'] else "غير دالة"
            lines.append(f"  {str(m['iv'])[:15]} → R²={m['r2']:.3f} | p={m['p_value']:.4f} | {sig}")

    norm = results.get('normality', {})
    if norm and 'error' not in norm:
        normal_count = sum(1 for v in norm.values() if isinstance(v, dict) and v.get('normal', False))
        lines.append(f"📐 التوزيع الطبيعي: {normal_count}/{len(norm)} متغير طبيعي")

    lines.append("─" * 40)
    lines.append("📝 تقرير Word جاهز للتحميل ⬇️")
    return lines


def build_tables(results):
    tables = {}
    desc = results.get('descriptive', {})
    if 'descriptive' in desc and 'columns' in desc:
        rows = []
        d = desc['descriptive']
        rw = desc.get('relative_weights', {})
        for col in desc['columns'][:10]:
            cd = d.get(col, {})
            rows.append({
                'variable': str(col),
                'n': int(cd.get('count', 0)),
                'mean': f"{float(cd.get('mean', 0)):.3f}",
                'std': f"{float(cd.get('std', 0)):.3f}",
                'min': f"{float(cd.get('min', 0)):.3f}",
                'max': f"{float(cd.get('max', 0)):.3f}",
                'rw': f"{rw.get(col, 0):.1f}%"
            })
        tables['descriptive'] = rows
    rel = results.get('reliability', {})
    if 'alpha' in rel:
        tables['reliability'] = {k: str(v) for k, v in rel.items()}
    return tables


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
