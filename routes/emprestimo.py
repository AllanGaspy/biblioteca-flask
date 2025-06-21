from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
import db
from datetime import date, datetime
from routes.auth import login_required
import pandas as pd
import io

emprestimo_bp = Blueprint('emprestimo', __name__, url_prefix='/emprestimos')

@emprestimo_bp.route('/')
@login_required(perfis=['funcionario'])
def listar():
    filtro = request.args.get('filtro', '')
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT e.id_emprestimo, e.data_retirada, e.data_prevista_devolucao, e.data_real_devolucao,
       u.nome AS nome_usuario, u.perfil AS perfil_usuario,
       l.titulo AS titulo_livro, c.nome AS categoria
    FROM Emprestimo e
    JOIN Usuario u ON e.fk_Usuario_id_usuario = u.id_usuario
    JOIN Livro l ON e.fk_Livro_id_livro = l.id_livro
    LEFT JOIN Categoria c ON l.fk_Categoria_id_categoria = c.id_categoria
    WHERE u.nome LIKE %s OR l.titulo LIKE %s OR c.nome LIKE %s
    ORDER BY e.data_retirada DESC
    """

    like_filtro = f"%{filtro}%"
    cursor.execute(query, (like_filtro, like_filtro, like_filtro))
    emprestimos = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('emprestimo/emprestimos_listar.html', emprestimos=emprestimos, filtro=filtro)

@emprestimo_bp.route('/exportar-excel')
@login_required(perfis=['funcionario'])
def exportar_excel():
    filtro = request.args.get('filtro', '')
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT e.id_emprestimo AS ID, u.nome AS Usuário, u.perfil AS Perfil,
           l.titulo AS Livro, c.nome AS Categoria,
           e.data_retirada AS Retirada, e.data_prevista_devolucao AS "Prevista",
           e.data_real_devolucao AS "Devolução"
    FROM Emprestimo e
    JOIN Usuario u ON e.fk_Usuario_id_usuario = u.id_usuario
    JOIN Livro l ON e.fk_Livro_id_livro = l.id_livro
    LEFT JOIN Categoria c ON l.fk_Categoria_id_categoria = c.id_categoria
    WHERE u.nome LIKE %s OR l.titulo LIKE %s OR c.nome LIKE %s
    ORDER BY e.data_retirada DESC
    """

    like_filtro = f"%{filtro}%"
    cursor.execute(query, (like_filtro, like_filtro, like_filtro))
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(resultados)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Emprestimos')

    output.seek(0)
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='emprestimos.xlsx')

@emprestimo_bp.route('/cadastrar', methods=['GET', 'POST'])
@login_required(perfis=['funcionario'])
def cadastrar():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id_usuario, nome FROM Usuario")
    usuarios = cursor.fetchall()

    cursor.execute("SELECT id_livro, titulo, num_copias_disponiveis FROM Livro")
    livros = cursor.fetchall()

    if request.method == 'POST':
        data_retirada = request.form['data_retirada']
        data_prevista = request.form['data_prevista_devolucao']
        id_usuario = request.form['id_usuario']
        id_livro = request.form['id_livro']

        try:
            dt_retirada = datetime.strptime(data_retirada, '%Y-%m-%d').date()
            dt_prevista = datetime.strptime(data_prevista, '%Y-%m-%d').date()
        except ValueError:
            flash("Formato de data inválido.", "danger")
            return render_template(
                'emprestimo/emprestimo_cadastrar.html',
                usuarios=usuarios, livros=livros
            )

        hoje = date.today()
        if dt_retirada > hoje:
            flash("A data de retirada não pode ser maior que hoje.", "danger")
        elif dt_prevista < dt_retirada:
            flash("A data prevista de devolução não pode ser menor que a data de retirada.", "danger")
        else:
            # Busca o número atual de cópias disponíveis
            cursor.execute("SELECT num_copias_disponiveis FROM Livro WHERE id_livro = %s", (id_livro,))
            livro = cursor.fetchone()
            if not livro or livro['num_copias_disponiveis'] <= 0:
                flash("Este livro não possui cópias disponíveis para empréstimo.", "danger")
            else:
                # Insere o empréstimo
                cursor.execute("""
                    INSERT INTO Emprestimo (data_retirada, data_prevista_devolucao, fk_Usuario_id_usuario, fk_Livro_id_livro)
                    VALUES (%s, %s, %s, %s)
                """, (dt_retirada, dt_prevista, id_usuario, id_livro))
                
                # Atualiza as cópias disponíveis decrementando 1, mas não permitindo negativo
                novo_num_copias = livro['num_copias_disponiveis'] - 1
                if novo_num_copias < 0:
                    novo_num_copias = 0
                cursor.execute("""
                    UPDATE Livro SET num_copias_disponiveis = %s WHERE id_livro = %s
                """, (novo_num_copias, id_livro))

                conn.commit()
                flash("Empréstimo cadastrado com sucesso!", "success")
                return redirect(url_for('emprestimo.listar'))

    cursor.close()
    conn.close()
    return render_template(
        'emprestimo/emprestimo_cadastrar.html',
        usuarios=usuarios,
        livros=livros
    )

@emprestimo_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required(perfis=['funcionario'])
def editar(id):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT e.*, u.nome AS nome_usuario, l.titulo AS titulo_livro
        FROM Emprestimo e
        JOIN Usuario u ON e.fk_Usuario_id_usuario = u.id_usuario
        JOIN Livro l ON e.fk_Livro_id_livro = l.id_livro
        WHERE e.id_emprestimo = %s
    """, (id,))
    emprestimo = cursor.fetchone()

    if not emprestimo:
        flash("Empréstimo não encontrado!", "danger")
        return redirect(url_for('emprestimo.listar'))

    cursor.execute("SELECT id_usuario, nome FROM Usuario")
    usuarios = cursor.fetchall()

    cursor.execute("SELECT id_livro, titulo FROM Livro")
    livros = cursor.fetchall()

    if request.method == 'POST':
        data_retirada = request.form['data_retirada']
        data_prevista = request.form['data_prevista_devolucao']
        data_real = request.form['data_real_devolucao']
        id_usuario = request.form['id_usuario']
        id_livro = request.form['id_livro']

        try:
            dt_retirada = datetime.strptime(data_retirada, '%Y-%m-%d').date()
            dt_prevista = datetime.strptime(data_prevista, '%Y-%m-%d').date()
            dt_real = datetime.strptime(data_real, '%Y-%m-%d').date() if data_real else None
        except ValueError:
            flash("Formato de data inválido.", "danger")
            return render_template(
                'emprestimo/emprestimo_editar.html',
                emprestimo=emprestimo, usuarios=usuarios, livros=livros
            )

        hoje = date.today()
        if dt_retirada > hoje:
            flash("A data de retirada não pode ser maior que hoje.", "danger")
        elif dt_prevista < dt_retirada:
            flash("A data prevista de devolução não pode ser menor que a data de retirada.", "danger")
        elif dt_real and dt_real < dt_retirada:
            flash("A data real de devolução não pode ser menor que a data de retirada.", "danger")
        else:
            cursor.execute("""
                UPDATE Emprestimo
                SET data_retirada = %s, data_prevista_devolucao = %s, data_real_devolucao = %s,
                    fk_Usuario_id_usuario = %s, fk_Livro_id_livro = %s
                WHERE id_emprestimo = %s
            """, (dt_retirada, dt_prevista, dt_real or None, id_usuario, id_livro, id))
            conn.commit()
            flash("Empréstimo atualizado com sucesso!", "success")
            return redirect(url_for('emprestimo.listar'))

    cursor.close()
    conn.close()
    return render_template('emprestimo/emprestimo_editar.html', emprestimo=emprestimo, usuarios=usuarios, livros=livros)

@emprestimo_bp.route('/deletar/<int:id>', methods=['POST'])
@login_required(perfis=['funcionario'])
def deletar(id):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Emprestimo WHERE id_emprestimo = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Empréstimo deletado com sucesso!", "success")
    return redirect(url_for('emprestimo.listar'))

@emprestimo_bp.route('/verificar-copias/<int:id_livro>')
@login_required(perfis=['funcionario'])
def verificar_copias(id_livro):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT num_copias_disponiveis AS copias FROM Livro WHERE id_livro = %s", (id_livro,))
    dados = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({'num_copias_disponiveis': dados['copias'] if dados else 0})
