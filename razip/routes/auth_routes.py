from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from utils.validators import validate_register_form

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.get_by_email(email)
        if user and user.check_password(password):
            login_user(user, remember=remember)
            user.update_last_login()
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        data   = request.form
        errors = validate_register_form(data)

        if errors:
            for e in errors:
                flash(e, 'error')
        elif User.get_by_email(data['email'].strip().lower()):
            flash('An account with this email already exists.', 'error')
        else:
            user = User.create(
                first_name = data['first_name'].strip(),
                last_name  = data['last_name'].strip(),
                email      = data['email'].strip().lower(),
                password   = data['password']
            )
            login_user(user)
            flash('Account created! Welcome to ResumeAI.', 'success')
            return redirect(url_for('main.dashboard'))

    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))