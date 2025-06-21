from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session
from routes.auth import login_required
import db
import pandas as pd
import io
from datetime import datetime, date

multa_bp = Blueprint('multa', __name__, url_prefix='/multa')

@multa_bp.route('/listar')
@login_required(perfis=['funcionario'])
def listar():
    filtro_nome = request.args.get('nome', '').strip()
    filtro_livro = request.args.get('livro', '').strip()

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    # Atualiza valor e dias de atraso das multas não quitadas
    cursor.execute("""
        SELECT m.id_multa, m.quitada, m.fk_Emprestimo_id_emprestimo,
               e.data_prevista_devolucao, e.data_real_devolucao
        FROM Multa m
        JOIN Emprestimo e ON m.fk_Emprestimo_id_emprestimo = e.id_emprestimo
    """)
    multas_para_atualizar = cursor.fetchall()

    for multa in multas_para_atualizar:
        if multa['quitada']:
            continue

        devolucao_real = multa['data_real_devolucao']
        devolucao_prevista = multa['data_prevista_devolucao']

        if devolucao_real:
            dias_atraso = (devolucao_real - devolucao_prevista).days
        else:
            dias_atraso = (date.today() - devolucao_prevista).days

        dias_atraso = max(0, dias_atraso)
        valor = dias_atraso * 2.00

        cursor.execute("""
            UPDATE Multa SET dias_atraso = %s, valor = %s
            WHERE id_multa = %s
        """, (dias_atraso, valor, multa['id_multa']))

    conn.commit()

    if session.pop('sucesso_multas', False):
        flash("Multas geradas com sucesso!", "success")

    query = """
        SELECT m.id_multa, m.valor, m.dias_atraso, m.quitada,
               u.nome AS nome_usuario,
               l.titulo AS titulo_livro,
               e.data_retirada, e.data_prevista_devolucao, e.data_real_devolucao
        FROM Multa m
        JOIN Emprestimo e ON m.fk_Emprestimo_id_emprestimo = e.id_emprestimo
        JOIN Usuario u ON e.fk_Usuario_id_usuario = u.id_usuario
        JOIN Livro l ON e.fk_Livro_id_livro = l.id_livro
        WHERE 1=1
    """

    params = []

    if filtro_nome:
        query += " AND u.nome LIKE %s"
        params.append(f"%{filtro_nome}%")

    if filtro_livro:
        query += " AND l.titulo LIKE %s"
        params.append(f"%{filtro_livro}%")

    query += " ORDER BY m.id_multa DESC"

    cursor.execute(query, params)
    multas = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('multa/multa_listar.html', multas=multas, filtro_nome=filtro_nome, filtro_livro=filtro_livro)

@multa_bp.route('/gerar')
@login_required(perfis=['funcionario'])
def gerar_multas():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT e.id_emprestimo, e.data_prevista_devolucao, e.data_real_devolucao
        FROM Emprestimo e
        WHERE (
            (e.data_real_devolucao IS NULL AND e.data_prevista_devolucao < CURDATE())
            OR (e.data_real_devolucao IS NOT NULL AND e.data_real_devolucao > e.data_prevista_devolucao)
        )
        AND NOT EXISTS (
            SELECT 1 FROM Multa m WHERE m.fk_Emprestimo_id_emprestimo = e.id_emprestimo
        )
    """)
    emprestimos = cursor.fetchall()

    for emp in emprestimos:
        if emp['data_real_devolucao']:
            dias_atraso = (emp['data_real_devolucao'] - emp['data_prevista_devolucao']).days
        else:
            dias_atraso = (date.today() - emp['data_prevista_devolucao']).days

        if dias_atraso > 0:
            valor = dias_atraso * 2.00
            cursor.execute("""
                INSERT INTO Multa (valor, dias_atraso, fk_Emprestimo_id_emprestimo, quitada)
                VALUES (%s, %s, %s, FALSE)
            """, (valor, dias_atraso, emp['id_emprestimo']))

    conn.commit()
    cursor.close()
    conn.close()

    session['sucesso_multas'] = True
    return redirect(url_for('multa.listar'))

@multa_bp.route('/editar/<int:id_multa>', methods=['GET', 'POST'])
@login_required(perfis=['funcionario'])
def editar(id_multa):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM Multa WHERE id_multa = %s", (id_multa,))
    multa = cursor.fetchone()

    if not multa:
        flash("Multa não encontrada.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('multa.listar'))

    if request.method == 'POST':
        quitada = request.form.get('quitar')  # 'sim' ou 'nao'
        quitada_bool = quitada == 'sim'

        try:
            if quitada_bool:
                # Marca a multa como quitada
                cursor.execute("UPDATE Multa SET quitada = TRUE WHERE id_multa = %s", (id_multa,))

                # Atualiza data_real_devolucao se estiver NULL e atualiza cópias do livro
                cursor.execute("SELECT fk_Emprestimo_id_emprestimo FROM Multa WHERE id_multa = %s", (id_multa,))
                multa_rel = cursor.fetchone()
                if multa_rel:
                    emprestimo_id = multa_rel['fk_Emprestimo_id_emprestimo']
                    cursor.execute("SELECT data_real_devolucao, fk_Livro_id_livro FROM Emprestimo WHERE id_emprestimo = %s", (emprestimo_id,))
                    emprestimo = cursor.fetchone()
                    if emprestimo and emprestimo['data_real_devolucao'] is None:
                        data_hoje = date.today()
                        cursor.execute("UPDATE Emprestimo SET data_real_devolucao = %s WHERE id_emprestimo = %s", (data_hoje, emprestimo_id))

                        # Atualiza o número de cópias disponíveis do livro (+1)
                        livro_id = emprestimo['fk_Livro_id_livro']
                        cursor.execute("SELECT num_copias_disponiveis FROM Livro WHERE id_livro = %s", (livro_id,))
                        livro = cursor.fetchone()
                        if livro:
                            novo_num = livro['num_copias_disponiveis'] + 1
                            cursor.execute("UPDATE Livro SET num_copias_disponiveis = %s WHERE id_livro = %s", (novo_num, livro_id))

            else:
                # Marca multa como não quitada
                cursor.execute("UPDATE Multa SET quitada = FALSE WHERE id_multa = %s", (id_multa,))

            conn.commit()
            flash("Multa atualizada com sucesso!", "success")
            cursor.close()
            conn.close()
            return redirect(url_for('multa.listar'))

        except Exception as e:
            conn.rollback()
            flash(f"Erro ao atualizar multa: {str(e)}", "danger")

    cursor.close()
    conn.close()
    return render_template('multa/multa_editar.html', multa=multa)

@multa_bp.route('/quitar/<int:id_multa>', methods=['POST'])
@login_required(perfis=['funcionario'])
def quitar(id_multa):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Marca a multa como quitada
        cursor.execute("UPDATE Multa SET quitada = TRUE WHERE id_multa = %s", (id_multa,))

        # Busca o id do empréstimo relacionado à multa
        cursor.execute("SELECT fk_Emprestimo_id_emprestimo FROM Multa WHERE id_multa = %s", (id_multa,))
        multa = cursor.fetchone()

        if multa:
            emprestimo_id = multa['fk_Emprestimo_id_emprestimo']

            # Verifica se o empréstimo já foi devolvido
            cursor.execute("SELECT data_real_devolucao, fk_Livro_id_livro FROM Emprestimo WHERE id_emprestimo = %s", (emprestimo_id,))
            emprestimo = cursor.fetchone()

            if emprestimo and emprestimo['data_real_devolucao'] is None:
                data_hoje = date.today()
                cursor.execute("UPDATE Emprestimo SET data_real_devolucao = %s WHERE id_emprestimo = %s", (data_hoje, emprestimo_id))

                # Atualiza o número de cópias disponíveis do livro (+1)
                livro_id = emprestimo['fk_Livro_id_livro']
                cursor.execute("SELECT num_copias_disponiveis FROM Livro WHERE id_livro = %s", (livro_id,))
                livro = cursor.fetchone()
                if livro:
                    novo_num = livro['num_copias_disponiveis'] + 1
                    cursor.execute("UPDATE Livro SET num_copias_disponiveis = %s WHERE id_livro = %s", (novo_num, livro_id))

        conn.commit()
        flash("Multa marcada como quitada com sucesso!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Erro ao quitar multa: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('multa.listar'))

@multa_bp.route('/exportar-excel')
@login_required(perfis=['funcionario'])
def exportar_excel():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT m.id_multa AS ID,
               u.nome AS Usuario,
               l.titulo AS Livro,
               m.valor AS Valor,
               m.dias_atraso AS Dias_Atraso,
               CASE WHEN m.quitada THEN 'Sim' ELSE 'Não' END AS Quitada,
               e.data_retirada AS Data_Retirada,
               e.data_prevista_devolucao AS Data_Prevista,
               e.data_real_devolucao AS Data_Devolucao
        FROM Multa m
        JOIN Emprestimo e ON m.fk_Emprestimo_id_emprestimo = e.id_emprestimo
        JOIN Usuario u ON e.fk_Usuario_id_usuario = u.id_usuario
        JOIN Livro l ON e.fk_Livro_id_livro = l.id_livro
        ORDER BY m.id_multa DESC
    """)
    dados = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(dados)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Multas Detalhadas')
    output.seek(0)

    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='relatorio_multas_detalhado.xlsx')
