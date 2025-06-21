from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from routes.auth import login_required
import db
import datetime
import pandas as pd
import io

reserva_bp = Blueprint('reserva', __name__, url_prefix='/reserva')

@reserva_bp.route('/listar')
@login_required(perfis=['funcionario'])
def listar():
    filtro_nome = request.args.get('nome', '').strip()
    filtro_livro = request.args.get('livro', '').strip()

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT r.id_reserva, r.data_reserva, r.ordem_fila, u.nome AS nome_usuario, l.titulo AS titulo_livro
        FROM Reserva r
        JOIN Usuario u ON r.fk_Usuario_id_usuario = u.id_usuario
        JOIN Livro l ON r.fk_Livro_id_livro = l.id_livro
        WHERE (%s = '' OR u.nome LIKE %s)
          AND (%s = '' OR l.titulo LIKE %s)
        ORDER BY r.data_reserva DESC, r.ordem_fila ASC
    """
    params = (
        filtro_nome, f'%{filtro_nome}%',
        filtro_livro, f'%{filtro_livro}%'
    )

    cursor.execute(query, params)
    reservas = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('reserva/reserva_listar.html', reservas=reservas,
                           filtro_nome=filtro_nome, filtro_livro=filtro_livro)


@reserva_bp.route('/exportar-excel')
@login_required(perfis=['funcionario'])
def exportar_excel():
    filtro_nome = request.args.get('nome', '').strip()
    filtro_livro = request.args.get('livro', '').strip()

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT r.id_reserva AS ID, r.data_reserva AS Data_Reserva, r.ordem_fila AS Ordem_Fila, 
               u.nome AS Usuario, l.titulo AS Livro
        FROM Reserva r
        JOIN Usuario u ON r.fk_Usuario_id_usuario = u.id_usuario
        JOIN Livro l ON r.fk_Livro_id_livro = l.id_livro
        WHERE (%s = '' OR u.nome LIKE %s)
          AND (%s = '' OR l.titulo LIKE %s)
        ORDER BY r.data_reserva DESC, r.ordem_fila ASC
    """
    params = (
        filtro_nome, f'%{filtro_nome}%',
        filtro_livro, f'%{filtro_livro}%'
    )

    cursor.execute(query, params)
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(resultados)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reservas')
    output.seek(0)

    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='reservas.xlsx')


@reserva_bp.route('/cadastrar', methods=['GET', 'POST'])
@login_required(perfis=['funcionario'])
def cadastrar():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id_usuario, nome FROM Usuario ORDER BY nome")
    usuarios = cursor.fetchall()

    cursor.execute("SELECT id_livro, titulo FROM Livro ORDER BY titulo")
    livros = cursor.fetchall()

    if request.method == 'POST':
        usuario_id = request.form.get('usuario')
        livro_id = request.form.get('livro')

        if not usuario_id or not livro_id:
            flash("Selecione o usuário e o livro.", "danger")
        else:
            try:
                # Verifica se usuário já tem reserva para esse livro
                cursor.execute("""
                    SELECT COUNT(*) AS total FROM Reserva 
                    WHERE fk_Usuario_id_usuario = %s AND fk_Livro_id_livro = %s
                """, (usuario_id, livro_id))
                if cursor.fetchone()['total'] > 0:
                    flash("Usuário já possui uma reserva para este livro.", "warning")
                    cursor.close()
                    conn.close()
                    return redirect(url_for('reserva.cadastrar'))

                # Verifica se usuário tem empréstimo ativo (sem data_real_devolucao) para este livro
                cursor.execute("""
                    SELECT COUNT(*) AS total FROM Emprestimo
                    WHERE fk_Usuario_id_usuario = %s
                      AND fk_Livro_id_livro = %s
                      AND data_real_devolucao IS NULL
                """, (usuario_id, livro_id))
                if cursor.fetchone()['total'] > 0:
                    flash("Usuário já possui este livro emprestado e não pode reservar.", "warning")
                    cursor.close()
                    conn.close()
                    return redirect(url_for('reserva.cadastrar'))

                # Data atual
                data_reserva = datetime.date.today()

                # Verificar quantas reservas já existem para este livro
                cursor.execute("SELECT COUNT(*) AS total FROM Reserva WHERE fk_Livro_id_livro = %s", (livro_id,))
                total_reservas = cursor.fetchone()['total']
                ordem_fila = total_reservas + 1

                # Inserir nova reserva
                cursor.execute("""
                    INSERT INTO Reserva (data_reserva, ordem_fila, fk_Usuario_id_usuario, fk_Livro_id_livro)
                    VALUES (%s, %s, %s, %s)
                """, (data_reserva, ordem_fila, usuario_id, livro_id))
                conn.commit()
                flash("Reserva cadastrada com sucesso!", "success")
                return redirect(url_for('reserva.listar'))
            except Exception as e:
                conn.rollback()
                flash(f"Erro ao cadastrar reserva: {str(e)}", "danger")

    cursor.close()
    conn.close()
    return render_template('reserva/reserva_cadastrar.html', usuarios=usuarios, livros=livros)

@reserva_bp.route('/fila/<int:id_livro>')
@login_required(perfis=['funcionario'])
def fila_livro(id_livro):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total FROM Reserva WHERE fk_Livro_id_livro = %s", (id_livro,))
    total = cursor.fetchone()['total']
    cursor.close()
    conn.close()
    return jsonify({'quantidade': total})


@reserva_bp.route('/editar/<int:id_reserva>', methods=['GET', 'POST'])
@login_required(perfis=['funcionario'])
def editar(id_reserva):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    # Buscar reserva com nome_usuario e titulo_livro para preencher inputs datalist
    cursor.execute("""
        SELECT r.*, u.nome AS nome_usuario, l.titulo AS titulo_livro
        FROM Reserva r
        JOIN Usuario u ON r.fk_Usuario_id_usuario = u.id_usuario
        JOIN Livro l ON r.fk_Livro_id_livro = l.id_livro
        WHERE r.id_reserva = %s
    """, (id_reserva,))
    reserva = cursor.fetchone()

    cursor.execute("SELECT id_usuario, nome FROM Usuario ORDER BY nome")
    usuarios = cursor.fetchall()

    cursor.execute("SELECT id_livro, titulo FROM Livro ORDER BY titulo")
    livros = cursor.fetchall()

    if not reserva:
        flash("Reserva não encontrada.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('reserva.listar'))

    if request.method == 'POST':
        data_reserva = request.form.get('data_reserva')
        ordem_fila = request.form.get('ordem_fila')
        usuario_id = request.form.get('usuario')
        livro_id = request.form.get('livro')

        if not data_reserva or not ordem_fila or not usuario_id or not livro_id:
            flash("Preencha todos os campos.", "danger")
        else:
            try:
                ordem_fila_int = int(ordem_fila)
                datetime.datetime.strptime(data_reserva, '%Y-%m-%d')

                # Atualizar reserva
                cursor.execute("""
                    UPDATE Reserva SET data_reserva=%s, ordem_fila=%s, fk_Usuario_id_usuario=%s, fk_Livro_id_livro=%s
                    WHERE id_reserva=%s
                """, (data_reserva, ordem_fila_int, usuario_id, livro_id, id_reserva))
                conn.commit()
                flash("Reserva atualizada com sucesso!", "success")
                return redirect(url_for('reserva.listar'))
            except Exception as e:
                conn.rollback()
                flash(f"Erro ao atualizar reserva: {str(e)}", "danger")

    cursor.close()
    conn.close()
    return render_template('reserva/reserva_editar.html', reserva=reserva, usuarios=usuarios, livros=livros)

@reserva_bp.route('/deletar/<int:id_reserva>', methods=['POST'])
@login_required(perfis=['funcionario'])
def deletar(id_reserva):
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Reserva WHERE id_reserva = %s", (id_reserva,))
        conn.commit()
        flash("Reserva deletada com sucesso!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao deletar reserva: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('reserva.listar'))
