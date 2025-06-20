from flask import Blueprint, render_template, session, request, redirect, url_for, flash, send_file
from routes.auth import login_required
import db
import mysql.connector  # necessário para capturar IntegrityError
import pandas as pd
import io

usuario_bp = Blueprint('usuario', __name__, url_prefix='/usuario')

@usuario_bp.route('/dashboard')
@login_required(perfis=['aluno', 'professor'])  # só alunos ou professores podem acessar
def dashboard():
    nome = session['usuario'].get('nome')
    return render_template('usuario_dashboard.html', nome=nome)

@usuario_bp.route('/')
@login_required(perfis=['funcionario'])
def listar():
    filtro_nome = request.args.get('nome', '').strip()
    filtro_email = request.args.get('email', '').strip()
    filtro_perfil = request.args.get('perfil', '').strip()

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT * FROM Usuario
        WHERE (%s = '' OR nome LIKE %s)
          AND (%s = '' OR email LIKE %s)
          AND (%s = '' OR perfil LIKE %s)
        ORDER BY nome
    """
    params = (
        filtro_nome, f'%{filtro_nome}%',
        filtro_email, f'%{filtro_email}%',
        filtro_perfil, f'%{filtro_perfil}%'
    )

    cursor.execute(query, params)
    usuarios = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('usuario/usuarios_listar.html', usuarios=usuarios,
                           filtro_nome=filtro_nome,
                           filtro_email=filtro_email,
                           filtro_perfil=filtro_perfil)


@usuario_bp.route('/exportar-excel')
@login_required(perfis=['funcionario'])
def exportar_excel():
    filtro_nome = request.args.get('nome', '').strip()
    filtro_email = request.args.get('email', '').strip()
    filtro_perfil = request.args.get('perfil', '').strip()

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT id_usuario AS ID, nome AS Nome, email AS Email, perfil AS Perfil
        FROM Usuario
        WHERE (%s = '' OR nome LIKE %s)
          AND (%s = '' OR email LIKE %s)
          AND (%s = '' OR perfil LIKE %s)
        ORDER BY nome
    """
    params = (
        filtro_nome, f'%{filtro_nome}%',
        filtro_email, f'%{filtro_email}%',
        filtro_perfil, f'%{filtro_perfil}%'
    )

    cursor.execute(query, params)
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(resultados)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Usuários')
    output.seek(0)

    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='usuarios.xlsx')

@usuario_bp.route('/cadastrar', methods=['GET', 'POST'])
@login_required(perfis=['funcionario'])
def cadastrar():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        perfil = request.form['perfil']
        if not nome or not email or not perfil:
            flash("Todos os campos são obrigatórios", "danger")
        else:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Usuario (nome, email, perfil) VALUES (%s, %s, %s)",
                (nome, email, perfil)
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("Usuário cadastrado com sucesso!", "success")
            return redirect(url_for('usuario.listar'))
    return render_template('usuario/usuario_cadastrar.html')

@usuario_bp.route('/editar/<int:id_usuario>', methods=['GET', 'POST'])
@login_required(perfis=['funcionario'])
def editar(id_usuario):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM Usuario WHERE id_usuario = %s", (id_usuario,))
    usuario = cursor.fetchone()

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        perfil = request.form['perfil']

        cursor.execute("""
            UPDATE Usuario SET nome = %s, email = %s, perfil = %s
            WHERE id_usuario = %s
        """, (nome, email, perfil, id_usuario))
        conn.commit()
        flash("Usuário atualizado com sucesso!", "success")
        return redirect(url_for('usuario.listar'))

    cursor.close()
    conn.close()
    return render_template('usuario/usuario_editar.html', usuario=usuario)

@usuario_bp.route('/deletar/<int:id_usuario>', methods=['POST'])
@login_required(perfis=['funcionario'])
def deletar(id_usuario):
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Usuario WHERE id_usuario = %s", (id_usuario,))
        conn.commit()
        flash("Usuário deletado com sucesso!", "success")
    except mysql.connector.errors.IntegrityError:
        conn.rollback()
        flash("Este usuário não pode ser deletado pois possui empréstimos vinculados.", "danger")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('usuario.listar'))
