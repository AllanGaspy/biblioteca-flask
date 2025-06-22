from flask import Blueprint, render_template, session, request, redirect, url_for, flash, send_file, jsonify
from routes.auth import login_required
import db
import mysql.connector  # necessário para capturar IntegrityError
import pandas as pd
import io
from datetime import datetime


usuario_bp = Blueprint('usuario', __name__, url_prefix='/usuario')

# --- Dashboard para aluno ou professor ---
@usuario_bp.route('/dashboard')
@login_required(perfis=['aluno', 'professor'])  # só alunos ou professores podem acessar
def dashboard():
    nome = session['usuario'].get('nome')
    return render_template('dashboard_usuario/usuario_dashboard.html', nome=nome)

# --- Livros disponíveis (para aluno ou professor) ---
@usuario_bp.route('/livros')
@login_required(perfis=['aluno', 'professor'])
def livros_disponiveis():
    filtro_titulo = request.args.get('titulo', '').strip()
    filtro_categoria = request.args.get('categoria', '').strip()
    filtro_editora = request.args.get('editora', '').strip()
    filtro_idioma = request.args.get('idioma', '').strip()

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT
          l.id_livro,
          l.titulo,
          l.ano_publicacao,
          l.idioma,
          l.num_copias_disponiveis,
          c.nome AS categoria,
          e.nome AS editora
        FROM Livro l
        JOIN Categoria c ON l.fk_Categoria_id_categoria = c.id_categoria
        JOIN Editora e ON l.fk_Editora_id_editora = e.id_editora
        WHERE l.num_copias_disponiveis > 0
          AND (%s = '' OR l.titulo LIKE %s)
          AND (%s = '' OR c.nome LIKE %s)
          AND (%s = '' OR e.nome LIKE %s)
          AND (%s = '' OR l.idioma LIKE %s)
        ORDER BY l.titulo
    """

    params = (
        filtro_titulo, f'%{filtro_titulo}%',
        filtro_categoria, f'%{filtro_categoria}%',
        filtro_editora, f'%{filtro_editora}%',
        filtro_idioma, f'%{filtro_idioma}%'
    )

    cursor.execute(query, params)
    livros = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('dashboard_usuario/livros_disponiveis.html',
                           livros=livros,
                           filtro_titulo=filtro_titulo,
                           filtro_categoria=filtro_categoria,
                           filtro_editora=filtro_editora,
                           filtro_idioma=filtro_idioma)

# --- Detalhe dos livros clicado ---
@usuario_bp.route('/livros/<int:id_livro>')
@login_required(perfis=['aluno', 'professor'])
def detalhes_livro(id_livro):
    usuario = session.get('usuario')
    user_id = usuario['id']

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT l.*, c.nome AS categoria, e.nome AS editora
        FROM Livro l
        JOIN Categoria c ON l.fk_Categoria_id_categoria = c.id_categoria
        JOIN Editora e ON l.fk_Editora_id_editora = e.id_editora
        WHERE l.id_livro = %s
    """
    cursor.execute(query, (id_livro,))
    livro = cursor.fetchone()

    if not livro:
        cursor.close()
        conn.close()
        flash("Livro não encontrado", "danger")
        return redirect(url_for('usuario.livros_disponiveis'))

    # Verifica se o usuário já tem o livro emprestado (sem devolução)
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM Emprestimo
        WHERE fk_Usuario_id_usuario = %s AND fk_Livro_id_livro = %s AND data_real_devolucao IS NULL
    """, (user_id, id_livro))
    tem_emprestimo = cursor.fetchone()['total'] > 0

    # Verifica se o usuário já reservou o livro
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM Reserva
        WHERE fk_Usuario_id_usuario = %s AND fk_Livro_id_livro = %s
    """, (user_id, id_livro))
    tem_reserva = cursor.fetchone()['total'] > 0

    cursor.close()
    conn.close()

    pode_reservar = not (tem_emprestimo or tem_reserva)

    return render_template('dashboard_usuario/livro_detalhes.html', livro=livro, pode_reservar=pode_reservar)

# --- Reservar livro ---

@usuario_bp.route('/livros/<int:id_livro>/reservar', methods=['POST']) 
@login_required(perfis=['aluno', 'professor'])
def reservar_livro(id_livro):
    usuario = session.get('usuario')
    if not usuario or 'id' not in usuario:
        flash("Usuário não identificado na sessão.", "danger")
        return redirect(url_for('usuario.livros_disponiveis'))

    user_id = usuario['id']
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    # Verifica se o livro existe
    cursor.execute("SELECT * FROM Livro WHERE id_livro = %s", (id_livro,))
    livro = cursor.fetchone()
    if not livro:
        flash("Livro não encontrado.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('usuario.livros_disponiveis'))

    # Verifica se o usuário já tem esse livro emprestado (sem devolução ainda)
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM Emprestimo
        WHERE fk_Usuario_id_usuario = %s 
          AND fk_Livro_id_livro = %s
          AND data_real_devolucao IS NULL
    """, (user_id, id_livro))
    if cursor.fetchone()['total'] > 0:
        flash("Você não pode reservar este livro pois ele está emprestado para você no momento.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for('usuario.detalhes_livro', id_livro=id_livro))

    # Verifica se o usuário já tem reserva para o livro
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM Reserva
        WHERE fk_Usuario_id_usuario = %s AND fk_Livro_id_livro = %s
    """, (user_id, id_livro))
    if cursor.fetchone()['total'] > 0:
        flash("Você já possui uma reserva para este livro.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for('usuario.detalhes_livro', id_livro=id_livro))

    # Conta quantas reservas existem para o livro para definir a ordem da fila
    cursor.execute("SELECT COUNT(*) AS fila FROM Reserva WHERE fk_Livro_id_livro = %s", (id_livro,))
    ordem_fila = cursor.fetchone()['fila'] + 1

    # Insere a reserva
    data_reserva = datetime.today().date()
    cursor.execute("""
        INSERT INTO Reserva (data_reserva, ordem_fila, fk_Usuario_id_usuario, fk_Livro_id_livro)
        VALUES (%s, %s, %s, %s)
    """, (data_reserva, ordem_fila, user_id, id_livro))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Reserva realizada com sucesso!", "success")
    return redirect(url_for('usuario.minhas_reservas'))

@usuario_bp.route('/reservas')
@login_required(perfis=['aluno', 'professor'])
def minhas_reservas():
    user_id = session['usuario']['id']
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT r.*, l.titulo, c.nome AS categoria
        FROM Reserva r
        JOIN Livro l ON r.fk_Livro_id_livro = l.id_livro
        LEFT JOIN Categoria c ON l.fk_Categoria_id_categoria = c.id_categoria
        WHERE r.fk_Usuario_id_usuario = %s
        ORDER BY r.data_reserva DESC
    """
    cursor.execute(query, (user_id,))
    reservas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('dashboard_usuario/minhas_reservas.html', reservas=reservas)

@usuario_bp.route('/reservas/<int:id_reserva>/cancelar', methods=['POST'])
@login_required(perfis=['aluno', 'professor'])
def cancelar_reserva(id_reserva):
    user_id = session['usuario']['id']
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT fk_Usuario_id_usuario, fk_Livro_id_livro, ordem_fila FROM Reserva WHERE id_reserva = %s", (id_reserva,))
    reserva = cursor.fetchone()

    if not reserva or reserva['fk_Usuario_id_usuario'] != user_id:
        cursor.close()
        conn.close()
        flash("Reserva não encontrada ou acesso negado.", "danger")
        return redirect(url_for('usuario.minhas_reservas'))

    livro_id = reserva['fk_Livro_id_livro']
    ordem_fila_cancelada = reserva['ordem_fila']

    # Debug: print antes de deletar
    cursor.execute("SELECT id_reserva, ordem_fila FROM Reserva WHERE fk_Livro_id_livro = %s ORDER BY ordem_fila", (livro_id,))
    reservas_antes = cursor.fetchall()
    print("Antes do cancelamento:", reservas_antes)

    # Deleta a reserva
    cursor.execute("DELETE FROM Reserva WHERE id_reserva = %s", (id_reserva,))

    # Atualiza a ordem da fila
    cursor.execute("""
        UPDATE Reserva
        SET ordem_fila = ordem_fila - 1
        WHERE fk_Livro_id_livro = %s AND ordem_fila > %s
    """, (livro_id, ordem_fila_cancelada))

    # Debug: print depois de atualizar
    cursor.execute("SELECT id_reserva, ordem_fila FROM Reserva WHERE fk_Livro_id_livro = %s ORDER BY ordem_fila", (livro_id,))
    reservas_depois = cursor.fetchall()
    print("Depois do cancelamento:", reservas_depois)

    conn.commit()
    cursor.close()
    conn.close()

    flash("Reserva cancelada com sucesso e posições atualizadas!", "success")
    return redirect(url_for('usuario.minhas_reservas'))

from datetime import datetime

# --- Empréstimos do usuário logado ---
from datetime import datetime

@usuario_bp.route('/emprestimos')
@login_required(perfis=['aluno', 'professor'])
def meus_emprestimos():
    user_id = session['usuario']['id']
    
    # Recebe os filtros via query string (GET)
    filtro_titulo = request.args.get('titulo', '').strip()
    filtro_categoria = request.args.get('categoria', '').strip()
    filtro_status = request.args.get('status', '').strip().lower()  # ex: "em andamento", "atrasado", "devolvido"
    
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT e.*, l.titulo, c.nome AS categoria
        FROM Emprestimo e
        JOIN Livro l ON e.fk_Livro_id_livro = l.id_livro
        LEFT JOIN Categoria c ON l.fk_Categoria_id_categoria = c.id_categoria
        WHERE e.fk_Usuario_id_usuario = %s
          AND (%s = '' OR l.titulo LIKE %s)
          AND (%s = '' OR c.nome LIKE %s)
    """
    
    params = [
        user_id,
        filtro_titulo, f'%{filtro_titulo}%',
        filtro_categoria, f'%{filtro_categoria}%'
    ]

    # Filtrar por status: precisaremos montar o filtro dinamicamente
    if filtro_status:
        query += """
          AND (
            (%s = 'devolvido' AND e.data_real_devolucao IS NOT NULL)
            OR (%s = 'atrasado' AND e.data_real_devolucao IS NULL AND e.data_prevista_devolucao < CURDATE())
            OR (%s = 'em andamento' AND e.data_real_devolucao IS NULL AND e.data_prevista_devolucao >= CURDATE())
          )
        """
        params.extend([filtro_status, filtro_status, filtro_status])
    
    query += " ORDER BY e.data_retirada DESC"
    
    cursor.execute(query, params)
    emprestimos = cursor.fetchall()
    cursor.close()
    conn.close()

    now = datetime.today().date()

    return render_template(
        'dashboard_usuario/meus_emprestimos.html',
        emprestimos=emprestimos,
        now=now,
        filtro_titulo=filtro_titulo,
        filtro_categoria=filtro_categoria,
        filtro_status=filtro_status
    )

# --- Multas do usuário logado ---

@usuario_bp.route('/multas')
@login_required(perfis=['aluno', 'professor'])
def minhas_multas():
    user_id = session['usuario']['id']
    filtro_livro = request.args.get('livro', '').strip()
    filtro_quitada = request.args.get('quitada', '').strip().lower()

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT m.id_multa, m.valor, m.dias_atraso, m.quitada,
               e.id_emprestimo, e.data_retirada,
               l.titulo
        FROM Multa m
        JOIN Emprestimo e ON m.fk_Emprestimo_id_emprestimo = e.id_emprestimo
        JOIN Livro l ON e.fk_Livro_id_livro = l.id_livro
        WHERE e.fk_Usuario_id_usuario = %s
    """

    params = [user_id]

    if filtro_livro:
        query += " AND l.titulo LIKE %s"
        params.append(f"%{filtro_livro}%")

    if filtro_quitada == 'sim':
        query += " AND m.quitada = 1"
    elif filtro_quitada == 'nao':
        query += " AND m.quitada = 0"

    query += " ORDER BY m.quitada ASC, m.id_multa DESC"

    cursor.execute(query, params)
    multas = cursor.fetchall()

    # Converte data_retirada para datetime, se necessário
    for multa in multas:
        if 'data_retirada' in multa and multa['data_retirada']:
            if isinstance(multa['data_retirada'], str):
                try:
                    multa['data_retirada'] = datetime.strptime(multa['data_retirada'], '%Y-%m-%d')
                except ValueError:
                    multa['data_retirada'] = None

    cursor.close()
    conn.close()

    return render_template('dashboard_usuario/minhas_multas.html',
                           multas=multas,
                           filtro_livro=filtro_livro,
                           filtro_quitada=filtro_quitada)

# --- Rotas originais para administração (funcionários) ---
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

@usuario_bp.route('/verificar-multas/<int:id_usuario>')
@login_required(perfis=['funcionario'])
def verificar_multas(id_usuario):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT COUNT(*) AS qtd_multas
        FROM Multa m
        JOIN Emprestimo e ON m.fk_Emprestimo_id_emprestimo = e.id_emprestimo
        WHERE e.fk_Usuario_id_usuario = %s AND m.quitada = FALSE
    """
    cursor.execute(query, (id_usuario,))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()

    tem_multas = resultado['qtd_multas'] > 0
    return jsonify({'tem_multas': tem_multas})
