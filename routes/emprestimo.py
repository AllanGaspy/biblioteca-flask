from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
import db
from datetime import date, datetime
from routes.auth import login_required
import pandas as pd
import io

emprestimo_bp = Blueprint('emprestimo', __name__, url_prefix='/emprestimos')

MAX_EMPRESTIMOS_ATIVOS = 5

def montar_filtros():
    filtro_usuario = request.args.get('filtro_usuario', '').strip()
    filtro_livro = request.args.get('filtro_livro', '').strip()
    filtro_categoria = request.args.get('filtro_categoria', '').strip()

    like_usuario = f"%{filtro_usuario}%"
    like_livro = f"%{filtro_livro}%"
    like_categoria = f"%{filtro_categoria}%"

    return filtro_usuario, filtro_livro, filtro_categoria, like_usuario, like_livro, like_categoria


@emprestimo_bp.route('/')
@login_required(perfis=['funcionario'])
def listar():
    filtro_usuario, filtro_livro, filtro_categoria, like_usuario, like_livro, like_categoria = montar_filtros()

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
    WHERE u.nome LIKE %s AND l.titulo LIKE %s
      AND (%s = '' OR c.nome LIKE %s)
    ORDER BY e.data_retirada DESC
    """

    cursor.execute(query, (like_usuario, like_livro, filtro_categoria, like_categoria))
    emprestimos = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('emprestimo/emprestimos_listar.html',
                           emprestimos=emprestimos,
                           filtro_usuario=filtro_usuario,
                           filtro_livro=filtro_livro,
                           filtro_categoria=filtro_categoria)


@emprestimo_bp.route('/exportar-excel')
@login_required(perfis=['funcionario'])
def exportar_excel():
    filtro_usuario, filtro_livro, filtro_categoria, like_usuario, like_livro, like_categoria = montar_filtros()

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
    WHERE u.nome LIKE %s AND l.titulo LIKE %s
      AND (%s = '' OR c.nome LIKE %s)
    ORDER BY e.data_retirada DESC
    """

    cursor.execute(query, (like_usuario, like_livro, filtro_categoria, like_categoria))
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

    form_data = None

    if request.method == 'POST':
        form_data = request.form
        data_retirada = form_data.get('data_retirada', '').strip()
        data_prevista = form_data.get('data_prevista_devolucao', '').strip()
        id_usuario = form_data.get('id_usuario', '').strip()
        id_livro = form_data.get('id_livro', '').strip()

        # Validação dos campos obrigatórios
        if not all([data_retirada, data_prevista, id_usuario, id_livro]):
            flash("Todos os campos são obrigatórios.", "danger")
            cursor.close()
            conn.close()
            return render_template('emprestimo/emprestimo_cadastrar.html',
                                   usuarios=usuarios, livros=livros, form_data=form_data)

        # VERIFICAR SE USUÁRIO TEM EMPRÉSTIMOS ATIVOS (sem devolução)
        cursor.execute("""
            SELECT COUNT(*) AS qtd_ativos
            FROM Emprestimo
            WHERE fk_Usuario_id_usuario = %s
              AND (data_real_devolucao IS NULL OR data_real_devolucao = '')
        """, (id_usuario,))
        resultado_ativos = cursor.fetchone()
        if resultado_ativos['qtd_ativos'] >= MAX_EMPRESTIMOS_ATIVOS:
            flash(f"Este usuário já possui {MAX_EMPRESTIMOS_ATIVOS} empréstimos ativos sem devolução.", "danger")
            cursor.close()
            conn.close()
            return render_template('emprestimo/emprestimo_cadastrar.html',
                                   usuarios=usuarios, livros=livros, form_data=form_data)

        # Verificar multas pendentes
        cursor.execute("""
            SELECT COUNT(*) AS qtd_multas
            FROM Multa m
            JOIN Emprestimo e ON m.fk_Emprestimo_id_emprestimo = e.id_emprestimo
            WHERE e.fk_Usuario_id_usuario = %s AND m.quitada = FALSE
        """, (id_usuario,))
        resultado = cursor.fetchone()
        if resultado['qtd_multas'] > 0:
            flash("Este usuário possui multas não quitadas e não pode fazer novos empréstimos.", "danger")
            cursor.close()
            conn.close()
            return render_template('emprestimo/emprestimo_cadastrar.html',
                                   usuarios=usuarios, livros=livros, form_data=form_data)

        # Validação das datas
        try:
            dt_retirada = datetime.strptime(data_retirada, '%Y-%m-%d').date()
            dt_prevista = datetime.strptime(data_prevista, '%Y-%m-%d').date()
        except ValueError:
            flash("Formato de data inválido.", "danger")
            cursor.close()
            conn.close()
            return render_template('emprestimo/emprestimo_cadastrar.html',
                                   usuarios=usuarios, livros=livros, form_data=form_data)

        hoje = date.today()
        if dt_retirada > hoje:
            flash("A data de retirada não pode ser maior que hoje.", "danger")
        elif dt_prevista < dt_retirada:
            flash("A data prevista de devolução não pode ser menor que a data de retirada.", "danger")
        else:
            cursor.execute("SELECT num_copias_disponiveis FROM Livro WHERE id_livro = %s", (id_livro,))
            livro = cursor.fetchone()
            if not livro or livro['num_copias_disponiveis'] <= 0:
                flash("Este livro não possui cópias disponíveis para empréstimo.", "danger")
            else:
                try:
                    cursor.execute("""
                        INSERT INTO Emprestimo (data_retirada, data_prevista_devolucao, fk_Usuario_id_usuario, fk_Livro_id_livro)
                        VALUES (%s, %s, %s, %s)
                    """, (dt_retirada, dt_prevista, id_usuario, id_livro))

                    novo_num_copias = max(livro['num_copias_disponiveis'] - 1, 0)
                    cursor.execute("UPDATE Livro SET num_copias_disponiveis = %s WHERE id_livro = %s", (novo_num_copias, id_livro))

                    conn.commit()
                    flash("Empréstimo cadastrado com sucesso!", "success")
                    cursor.close()
                    conn.close()
                    return redirect(url_for('emprestimo.listar'))

                except Exception as e:
                    conn.rollback()
                    flash(f"Erro ao cadastrar empréstimo: {str(e)}", "danger")

    cursor.close()
    conn.close()
    return render_template('emprestimo/emprestimo_cadastrar.html',
                           usuarios=usuarios, livros=livros, form_data=form_data)


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
        cursor.close()
        conn.close()
        return redirect(url_for('emprestimo.listar'))

    cursor.execute("SELECT id_usuario, nome FROM Usuario")
    usuarios = cursor.fetchall()

    cursor.execute("SELECT id_livro, titulo FROM Livro")
    livros = cursor.fetchall()

    if request.method == 'POST':
        form_data = request.form
        data_retirada = form_data.get('data_retirada', '').strip()
        data_prevista = form_data.get('data_prevista_devolucao', '').strip()
        data_real = form_data.get('data_real_devolucao', '').strip()
        id_usuario = form_data.get('id_usuario', '').strip()
        id_livro = form_data.get('id_livro', '').strip()

        # Validação das datas
        try:
            dt_retirada = datetime.strptime(data_retirada, '%Y-%m-%d').date()
            dt_prevista = datetime.strptime(data_prevista, '%Y-%m-%d').date()
            dt_real = datetime.strptime(data_real, '%Y-%m-%d').date() if data_real else None
        except ValueError:
            flash("Formato de data inválido.", "danger")
            cursor.close()
            conn.close()
            return render_template('emprestimo/emprestimo_editar.html',
                                   emprestimo=emprestimo, usuarios=usuarios, livros=livros)

        hoje = date.today()
        if dt_retirada > hoje:
            flash("A data de retirada não pode ser maior que hoje.", "danger")
        elif dt_prevista < dt_retirada:
            flash("A data prevista de devolução não pode ser menor que a data de retirada.", "danger")
        elif dt_real and dt_real < dt_retirada:
            flash("A data real de devolução não pode ser menor que a data de retirada.", "danger")
        else:
            # Busca dados antigos do empréstimo para ajustes
            cursor.execute("SELECT fk_Livro_id_livro, fk_Usuario_id_usuario, data_real_devolucao FROM Emprestimo WHERE id_emprestimo = %s", (id,))
            antigo = cursor.fetchone()
            livro_antigo_id = antigo['fk_Livro_id_livro']
            usuario_antigo_id = antigo['fk_Usuario_id_usuario']
            data_real_antiga = antigo['data_real_devolucao']

            # Verificar multas se usuário for alterado
            if str(usuario_antigo_id) != str(id_usuario):
                # VERIFICAR SE USUÁRIO NOVO TEM EMPRÉSTIMOS ATIVOS (sem devolução)
                cursor.execute("""
                    SELECT COUNT(*) AS qtd_ativos
                    FROM Emprestimo
                    WHERE fk_Usuario_id_usuario = %s
                      AND (data_real_devolucao IS NULL OR data_real_devolucao = '')
                """, (id_usuario,))
                resultado_ativos = cursor.fetchone()
                if resultado_ativos['qtd_ativos'] >= MAX_EMPRESTIMOS_ATIVOS:
                    flash(f"Este usuário já possui {MAX_EMPRESTIMOS_ATIVOS} empréstimos ativos sem devolução.", "danger")
                    cursor.close()
                    conn.close()
                    return render_template('emprestimo/emprestimo_editar.html',
                                           emprestimo=emprestimo, usuarios=usuarios, livros=livros)

                cursor.execute("""
                    SELECT COUNT(*) AS qtd_multas
                    FROM Multa m
                    JOIN Emprestimo e ON m.fk_Emprestimo_id_emprestimo = e.id_emprestimo
                    WHERE e.fk_Usuario_id_usuario = %s AND m.quitada = FALSE
                """, (id_usuario,))
                resultado = cursor.fetchone()
                if resultado['qtd_multas'] > 0:
                    flash("Este usuário possui multas não quitadas e não pode ter empréstimos ativos.", "danger")
                    cursor.close()
                    conn.close()
                    return render_template('emprestimo/emprestimo_editar.html',
                                           emprestimo=emprestimo, usuarios=usuarios, livros=livros)

            # Ajustar cópias se livro foi alterado
            if str(livro_antigo_id) != str(id_livro):
                # Incrementa cópias livro antigo
                cursor.execute("SELECT num_copias_disponiveis FROM Livro WHERE id_livro = %s", (livro_antigo_id,))
                livro_antigo = cursor.fetchone()
                novo_num_antigo = livro_antigo['num_copias_disponiveis'] + 1
                cursor.execute("UPDATE Livro SET num_copias_disponiveis = %s WHERE id_livro = %s", (novo_num_antigo, livro_antigo_id))

                # Decrementa cópias livro novo
                cursor.execute("SELECT num_copias_disponiveis FROM Livro WHERE id_livro = %s", (id_livro,))
                livro_novo = cursor.fetchone()
                if livro_novo['num_copias_disponiveis'] <= 0:
                    flash("O livro selecionado não possui cópias disponíveis para empréstimo.", "danger")
                    cursor.close()
                    conn.close()
                    return render_template('emprestimo/emprestimo_editar.html',
                                           emprestimo=emprestimo, usuarios=usuarios, livros=livros)

                novo_num_novo = max(livro_novo['num_copias_disponiveis'] - 1, 0)
                cursor.execute("UPDATE Livro SET num_copias_disponiveis = %s WHERE id_livro = %s", (novo_num_novo, id_livro))

            else:
                # Se data_real foi adicionada ou removida, ajustar num_copias
                if (data_real_antiga is None or data_real_antiga == '') and dt_real is not None:
                    cursor.execute("SELECT num_copias_disponiveis FROM Livro WHERE id_livro = %s", (id_livro,))
                    livro_atual = cursor.fetchone()
                    novo_num_copias = livro_atual['num_copias_disponiveis'] + 1
                    cursor.execute("UPDATE Livro SET num_copias_disponiveis = %s WHERE id_livro = %s", (novo_num_copias, id_livro))

                elif data_real_antiga is not None and dt_real is None:
                    cursor.execute("SELECT num_copias_disponiveis FROM Livro WHERE id_livro = %s", (id_livro,))
                    livro_atual = cursor.fetchone()
                    novo_num_copias = max(livro_atual['num_copias_disponiveis'] - 1, 0)
                    cursor.execute("UPDATE Livro SET num_copias_disponiveis = %s WHERE id_livro = %s", (novo_num_copias, id_livro))

            # Atualizar empréstimo
            cursor.execute("""
                UPDATE Emprestimo
                SET data_retirada = %s, data_prevista_devolucao = %s, data_real_devolucao = %s,
                    fk_Usuario_id_usuario = %s, fk_Livro_id_livro = %s
                WHERE id_emprestimo = %s
            """, (dt_retirada, dt_prevista, dt_real, id_usuario, id_livro, id))

            conn.commit()
            flash("Empréstimo atualizado com sucesso!", "success")

            # Atualizar multa se existir
            cursor.execute("SELECT id_multa FROM Multa WHERE fk_Emprestimo_id_emprestimo = %s", (id,))
            multa = cursor.fetchone()

            if multa:
                dias_atraso = 0
                valor_multa = 0.0
                if dt_real and dt_prevista and dt_real > dt_prevista:
                    dias_atraso = (dt_real - dt_prevista).days
                    valor_multa = dias_atraso * 2.50

                cursor.execute("""
                    UPDATE Multa SET dias_atraso = %s, valor = %s
                    WHERE fk_Emprestimo_id_emprestimo = %s
                """, (dias_atraso, valor_multa, id))
                conn.commit()

            cursor.close()
            conn.close()
            return redirect(url_for('emprestimo.listar'))

    cursor.close()
    conn.close()
    return render_template('emprestimo/emprestimo_editar.html',
                           emprestimo=emprestimo, usuarios=usuarios, livros=livros)


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
    cursor.execute("SELECT num_copias_disponiveis FROM Livro WHERE id_livro = %s", (id_livro,))
    livro = cursor.fetchone()
    cursor.close()
    conn.close()
    if livro:
        return jsonify({'num_copias_disponiveis': livro['num_copias_disponiveis']})
    else:
        return jsonify({'num_copias_disponiveis': 0})
