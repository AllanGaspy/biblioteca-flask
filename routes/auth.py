# routes/auth.py

from flask import Blueprint, render_template, request, redirect, session, url_for, flash
import db
from functools import wraps

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/")
def index():
    return redirect(url_for("auth.login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Usuario WHERE email = %s", (email,))
        usuario = cursor.fetchone()
        cursor.close()
        conn.close()

        if usuario:
            session["usuario"] = {
                "id": usuario["id_usuario"],
                "nome": usuario["nome"],
                "perfil": usuario["perfil"]
            }
            # Redirecionamento com base no perfil
            if usuario["perfil"] == "funcionario":
                return redirect(url_for("funcionario.dashboard"))
            elif usuario["perfil"] in ("aluno", "professor"):
                return redirect(url_for("usuario.dashboard"))
            else:
                flash("Perfil desconhecido.")
                return redirect(url_for("auth.login"))

        else:
            flash("Usuário não encontrado.")
            return render_template("login.html")

    return render_template("login.html")

@auth_bp.route("/logout", methods=['POST'])
def logout():
    session.clear()
    flash('Você saiu com sucesso.', 'success')
    return redirect(url_for("auth.login"))

def login_required(perfis=None):
    """
    Decorator para proteger rotas que exigem login.
    'perfis' é uma lista de perfis permitidos, ex: ['funcionario'] ou ['aluno', 'professor'].
    Se não passar perfis, só exige que esteja logado.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'usuario' not in session:
                flash("Você precisa estar logado para acessar essa página.", "danger")
                return redirect(url_for("auth.login"))
            if perfis and session['usuario'].get('perfil') not in perfis:
                flash("Você não tem permissão para acessar essa página.", "danger")
                # Redirecionar para dashboard correspondente ao perfil ou login
                perfil = session['usuario'].get('perfil')
                if perfil == 'funcionario':
                    return redirect(url_for('funcionario.dashboard'))
                elif perfil in ('aluno', 'professor'):
                    return redirect(url_for('usuario.dashboard'))
                else:
                    return redirect(url_for('auth.login'))
            return func(*args, **kwargs)
        return wrapper
    return decorator