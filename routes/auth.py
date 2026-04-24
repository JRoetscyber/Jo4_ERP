from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('ui.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Please check your login details and try again.', 'error')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        return redirect(url_for('ui.index'))

    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('ui.index'))

    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user:
            flash('Email address already exists', 'error')
            return redirect(url_for('auth.signup'))

        new_user = User(email=email, username=username)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash('Signup successful! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('signup.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('ui.index'))

@auth_bp.route('/update_currency', methods=['POST'])
@login_required
def update_currency():
    new_currency = request.form.get('currency')
    if new_currency in ['ZAR', 'USD', 'EUR', 'GBP', 'JPY', 'AUD']:
        current_user.currency = new_currency
        db.session.commit()
        flash(f'Currency updated to {new_currency}', 'success')
    return redirect(request.referrer or url_for('ui.index'))
