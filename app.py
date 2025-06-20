from flask import Flask
from routes.auth import auth_bp
from routes.home import home_bp
from routes.funcionario import funcionario_bp  
from routes.usuario import usuario_bp
from routes.livros import livros_bp 
from routes.emprestimo import emprestimo_bp 
from routes.reserva import reserva_bp
from routes.multa import multa_bp

from flask import render_template, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "chave-secreta"

app.register_blueprint(auth_bp)
app.register_blueprint(home_bp)
app.register_blueprint(funcionario_bp)
app.register_blueprint(usuario_bp)   
app.register_blueprint(livros_bp)
app.register_blueprint(emprestimo_bp)
app.register_blueprint(reserva_bp)
app.register_blueprint(multa_bp)

@app.route('/funcionario')
def painel_funcionario():
    if 'usuario' not in session:
        flash('Você precisa estar logado para acessar essa página.', 'danger')
        return redirect(url_for('auth.login'))

    if session['usuario'].get('perfil') != 'funcionario':
        flash('Acesso permitido apenas para funcionários.', 'danger')
        return redirect(url_for('home.dashboard'))

    return render_template('painel_funcionario.html')


if __name__ == "__main__":
    app.run(debug=True)
