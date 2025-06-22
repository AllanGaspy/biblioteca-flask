from flask import Blueprint, session, render_template, redirect, url_for
import db

home_bp = Blueprint("home", __name__)

@home_bp.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect(url_for("auth.login"))
    return render_template("dashboard.html", usuario=session["usuario"])

@home_bp.route("/livros")
def listar_livros():
    if "usuario" not in session:
        return redirect(url_for("auth.login"))

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_livro, titulo FROM Livro")
    livros = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("listar_livros.html", livros=livros)

@home_bp.route('/emprestimos')
def emprestimos_usuario():
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))
    
    usuario_id = session['usuario']['id']
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.id_emprestimo, l.titulo, e.data_emprestimo, e.data_devolucao
        FROM Emprestimo e
        JOIN Livro l ON e.fk_Livro_id_livro = l.id_livro
        WHERE e.fk_Usuario_id_usuario = %s
    """, (usuario_id,))
    emprestimos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('emprestimos_usuario.html', emprestimos=emprestimos)
