from flask import Blueprint, render_template, session
from routes.auth import login_required  # importando o decorator
import db

funcionario_bp = Blueprint('funcionario', __name__, url_prefix='/funcionario')

@funcionario_bp.route('/dashboard')
@login_required(perfis=['funcionario'])  # só permite acesso a funcionários
def dashboard():
    nome = session['usuario'].get('nome')
    return render_template('painel_funcionario.html', nome=nome)
