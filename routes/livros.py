from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, send_file
from routes.auth import login_required  
import db
import datetime
import pandas as pd
import io

livros_bp = Blueprint('livros', __name__, url_prefix='/livros')

# Lista estática de países (defina sua lista completa aqui)
PAISES = [
    "Afeganistão", "África do Sul", "Albânia", "Alemanha", "Andorra", "Angola",
    "Antígua e Barbuda", "Arábia Saudita", "Argélia", "Argentina", "Armênia",
    "Austrália", "Áustria", "Azerbaijão", "Bahamas", "Bahrein", "Bangladesh",
    "Barbados", "Belarus", "Bélgica", "Belize", "Benin", "Butão", "Bolívia",
    "Bósnia e Herzegovina", "Botsuana", "Brasil", "Brunei", "Bulgária", "Burkina Faso",
    "Burundi", "Cabo Verde", "Camarões", "Camboja", "Canadá", "Catar", "Cazaquistão",
    "Chade", "Chile", "China", "Chipre", "Colômbia", "Comores", "Congo-Brazzaville",
    "Congo-Kinshasa", "Coreia do Norte", "Coreia do Sul", "Costa do Marfim", "Costa Rica",
    "Croácia", "Cuba", "Dinamarca", "Djibuti", "Dominica", "Egito", "El Salvador",
    "Emirados Árabes Unidos", "Equador", "Eritreia", "Eslováquia", "Eslovênia",
    "Espanha", "Estados Unidos", "Estônia", "Eswatini", "Etiópia", "Fiji",
    "Filipinas", "Finlândia", "França", "Gabão", "Gâmbia", "Gana", "Geórgia",
    "Granada", "Grécia", "Guatemala", "Guiné", "Guiné-Bissau", "Guiné Equatorial",
    "Haiti", "Honduras", "Hungria", "Iêmen", "Ilhas Marshall", "Índia", "Indonésia",
    "Irã", "Iraque", "Irlanda", "Islândia", "Israel", "Itália", "Jamaica", "Japão",
    "Jordânia", "Kiribati", "Kosovo", "Kuwait", "Laos", "Lesoto", "Letônia", "Líbano",
    "Libéria", "Líbia", "Liechtenstein", "Lituânia", "Luxemburgo", "Madagáscar",
    "Malásia", "Malaui", "Maldivas", "Mali", "Malta", "Marrocos", "Maurícia",
    "Mauritânia", "México", "Micronésia", "Moldávia", "Mônaco", "Mongólia",
    "Montenegro", "Moçambique", "Myanmar", "Namíbia", "Nauru", "Nepal", "Nicarágua",
    "Níger", "Nigéria", "Noruega", "Nova Zelândia", "Omã", "Países Baixos",
    "Palau", "Panamá", "Papua-Nova Guiné", "Paquistão", "Paraguai", "Peru",
    "Polônia", "Portugal", "Quênia", "Quirguistão", "Reino Unido", "República Centro-Africana",
    "República Dominicana", "República Tcheca", "Romênia", "Ruanda", "Rússia",
    "São Cristóvão e Nevis", "São Marino", "São Tomé e Príncipe", "São Vicente e Granadinas",
    "Seicheles", "Senegal", "Serra Leoa", "Sérvia", "Singapura", "Síria",
    "Somália", "Sri Lanka", "Sudão", "Sudão do Sul", "Suécia", "Suíça", "Suriname",
    "Tailândia", "Tajiquistão", "Tanzânia", "Timor-Leste", "Togo", "Tonga",
    "Trindade e Tobago", "Tunísia", "Turcomenistão", "Turquia", "Tuvalu",
    "Ucrânia", "Uganda", "Uruguai", "Uzbequistão", "Vanuatu", "Vaticano",
    "Venezuela", "Vietnã", "Zâmbia", "Zimbábue"
]


@livros_bp.route('/cadastrar', methods=['GET', 'POST'])
@login_required(perfis=['funcionario'])  # só funcionários podem cadastrar livros
def cadastrar():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM Categoria")
    categorias = cursor.fetchall()

    cursor.execute("SELECT * FROM Editora")
    editoras = cursor.fetchall()

    ano_atual = datetime.datetime.now().year

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        subtitulo = request.form.get('subtitulo') or None
        ano_publicacao = request.form.get('ano_publicacao')
        idioma = request.form.get('idioma')
        resumo = request.form.get('resumo') or None
        num_copias = request.form.get('num_copias_disponiveis')

        nova_categoria = request.form.get('nova_categoria') or None
        categoria_id = request.form.get('categoria') if not nova_categoria else None

        nova_editora_nome = request.form.get('nova_editora_nome') or None
        editora_id = request.form.get('editora') if not nova_editora_nome else None
        nova_editora_cidade = request.form.get('nova_editora_cidade') or None
        nova_editora_pais = request.form.get('nova_editora_pais') or None

        # Validações principais
        if not titulo or not ano_publicacao or not idioma or not num_copias:
            flash("Preencha todos os campos obrigatórios.", "danger")
        elif not ano_publicacao.isdigit() or int(ano_publicacao) > ano_atual:
            flash(f"O ano da publicação deve ser um número inteiro menor ou igual a {ano_atual}.", "danger")
        elif not num_copias.isdigit() or int(num_copias) < 0:
            flash("Número de cópias deve ser um número inteiro positivo ou zero.", "danger")
        elif nova_editora_nome and (not nova_editora_cidade or not nova_editora_pais):
            flash("Preencha cidade e país para a nova editora.", "danger")
        else:
            try:
                # Verifica se já existe a categoria
                if nova_categoria:
                    cursor.execute("SELECT id_categoria FROM Categoria WHERE LOWER(nome) = LOWER(%s)", (nova_categoria,))
                    existente = cursor.fetchone()
                    if existente:
                        categoria_id = existente['id_categoria']
                    else:
                        cursor.execute("INSERT INTO Categoria (nome) VALUES (%s)", (nova_categoria,))
                        conn.commit()
                        categoria_id = cursor.lastrowid

                # Verifica se já existe a editora
                if nova_editora_nome:
                    cursor.execute("SELECT id_editora FROM Editora WHERE LOWER(nome) = LOWER(%s)", (nova_editora_nome,))
                    existente = cursor.fetchone()
                    if existente:
                        editora_id = existente['id_editora']
                    else:
                        cursor.execute(
                            "INSERT INTO Editora (nome, cidade, pais) VALUES (%s, %s, %s)",
                            (nova_editora_nome, nova_editora_cidade, nova_editora_pais)
                        )
                        conn.commit()
                        editora_id = cursor.lastrowid

                if not categoria_id:
                    flash("Informe uma categoria existente ou crie uma nova.", "danger")
                    raise ValueError("Categoria inválida")

                if not editora_id:
                    flash("Informe uma editora existente ou crie uma nova.", "danger")
                    raise ValueError("Editora inválida")

                cursor.execute("""
                    INSERT INTO Livro 
                    (titulo, subtitulo, ano_publicacao, idioma, resumo, num_copias_disponiveis, fk_Categoria_id_categoria, fk_Editora_id_editora)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    titulo, subtitulo, int(ano_publicacao), idioma, resumo,
                    int(num_copias), categoria_id, editora_id
                ))
                conn.commit()
                flash("Livro cadastrado com sucesso!", "success")
                return redirect(url_for('livros.listar'))

            except Exception as e:
                conn.rollback()
                flash(f"Erro ao cadastrar livro: {str(e)}", "danger")

    cursor.close()
    conn.close()
    return render_template(
        "livro/cadastrar_livro.html",
        categorias=categorias,
        editoras=editoras,
        current_year=ano_atual,
        paises=PAISES
    )

@livros_bp.route('/listar')
@login_required(perfis=['funcionario'])
def listar():
    filtro_titulo = request.args.get('titulo', '').strip()
    filtro_categoria = request.args.get('categoria', '').strip()
    filtro_editora = request.args.get('editora', '').strip()

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT l.id_livro, l.titulo, c.nome AS categoria, e.nome AS editora
        FROM Livro l
        JOIN Categoria c ON l.fk_Categoria_id_categoria = c.id_categoria
        JOIN Editora e ON l.fk_Editora_id_editora = e.id_editora
        WHERE (%s = '' OR l.titulo LIKE %s)
          AND (%s = '' OR c.nome LIKE %s)
          AND (%s = '' OR e.nome LIKE %s)
        ORDER BY l.titulo
    """

    params = (
        filtro_titulo, f'%{filtro_titulo}%',
        filtro_categoria, f'%{filtro_categoria}%',
        filtro_editora, f'%{filtro_editora}%'
    )

    cursor.execute(query, params)
    livros = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('livro/livros_listar.html', livros=livros,
                           filtro_titulo=filtro_titulo,
                           filtro_categoria=filtro_categoria,
                           filtro_editora=filtro_editora)


@livros_bp.route('/editar/<int:id_livro>', methods=['GET', 'POST'])
@login_required(perfis=['funcionario'])  # só funcionários podem editar
def editar(id_livro):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    # Consulta o livro junto com nome da categoria e editora
    cursor.execute("""
        SELECT l.*, c.nome AS nome_categoria, e.nome AS nome_editora
        FROM Livro l
        JOIN Categoria c ON l.fk_Categoria_id_categoria = c.id_categoria
        JOIN Editora e ON l.fk_Editora_id_editora = e.id_editora
        WHERE l.id_livro = %s
    """, (id_livro,))
    livro = cursor.fetchone()

    if not livro:
        cursor.close()
        conn.close()
        flash("Livro não encontrado.", "danger")
        return redirect(url_for('livros.listar'))

    cursor.execute("SELECT * FROM Categoria")
    categorias = cursor.fetchall()

    cursor.execute("SELECT * FROM Editora")
    editoras = cursor.fetchall()

    ano_atual = datetime.datetime.now().year

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        subtitulo = request.form.get('subtitulo') or None
        ano_publicacao = request.form.get('ano_publicacao')
        idioma = request.form.get('idioma')
        resumo = request.form.get('resumo') or None
        num_copias = request.form.get('num_copias_disponiveis')

        categoria_id = request.form.get('categoria') or None
        nova_categoria = request.form.get('nova_categoria') or None

        editora_id = request.form.get('editora') or None
        nova_editora_nome = request.form.get('nova_editora_nome') or None
        nova_editora_cidade = request.form.get('nova_editora_cidade') or None
        nova_editora_pais = request.form.get('nova_editora_pais') or None

        # Validações básicas
        if not titulo or not ano_publicacao or not idioma or not num_copias:
            flash("Preencha todos os campos obrigatórios.", "danger")
        elif not ano_publicacao.isdigit() or int(ano_publicacao) > ano_atual:
            flash(f"O ano da publicação deve ser um número inteiro menor ou igual a {ano_atual}.", "danger")
        elif not num_copias.isdigit() or int(num_copias) < 0:
            flash("Número de cópias deve ser um número inteiro positivo ou zero.", "danger")
        elif nova_editora_nome and (not nova_editora_cidade or not nova_editora_pais):
            flash("Preencha cidade e país para a nova editora.", "danger")
        else:
            try:
                # Tratar categoria
                if nova_categoria:
                    cursor.execute("SELECT id_categoria FROM Categoria WHERE LOWER(nome) = LOWER(%s)", (nova_categoria,))
                    existente = cursor.fetchone()
                    if existente:
                        categoria_id = existente['id_categoria']
                    else:
                        cursor.execute("INSERT INTO Categoria (nome) VALUES (%s)", (nova_categoria,))
                        conn.commit()
                        categoria_id = cursor.lastrowid

                # Tratar editora
                if nova_editora_nome:
                    cursor.execute("SELECT id_editora FROM Editora WHERE LOWER(nome) = LOWER(%s)", (nova_editora_nome,))
                    existente = cursor.fetchone()
                    if existente:
                        editora_id = existente['id_editora']
                    else:
                        cursor.execute(
                            "INSERT INTO Editora (nome, cidade, pais) VALUES (%s, %s, %s)",
                            (nova_editora_nome, nova_editora_cidade, nova_editora_pais)
                        )
                        conn.commit()
                        editora_id = cursor.lastrowid

                if not categoria_id:
                    flash("Informe uma categoria existente ou crie uma nova.", "danger")
                    raise ValueError("Categoria inválida")

                if not editora_id:
                    flash("Informe uma editora existente ou crie uma nova.", "danger")
                    raise ValueError("Editora inválida")

                cursor.execute("""
                    UPDATE Livro SET
                        titulo = %s,
                        subtitulo = %s,
                        ano_publicacao = %s,
                        idioma = %s,
                        resumo = %s,
                        num_copias_disponiveis = %s,
                        fk_Categoria_id_categoria = %s,
                        fk_Editora_id_editora = %s
                    WHERE id_livro = %s
                """, (
                    titulo,
                    subtitulo,
                    int(ano_publicacao),
                    idioma,
                    resumo,
                    int(num_copias),
                    categoria_id,
                    editora_id,
                    id_livro
                ))
                conn.commit()
                flash("Livro atualizado com sucesso!", "success")
                return redirect(url_for('livros.listar'))

            except Exception as e:
                conn.rollback()
                flash(f"Erro ao atualizar livro: {str(e)}", "danger")

    cursor.close()
    conn.close()

    return render_template(
        "livro/livro_editar.html",
        livro=livro,
        categorias=categorias,
        editoras=editoras,
        paises=PAISES,
        current_year=ano_atual
    )

@livros_bp.route('/deletar/<int:id_livro>', methods=['POST'])
@login_required(perfis=['funcionario'])  # Apenas funcionário pode deletar
def deletar(id_livro):
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        # Verifica se o livro existe
        cursor.execute("SELECT id_livro FROM Livro WHERE id_livro = %s", (id_livro,))
        livro = cursor.fetchone()

        if not livro:
            flash("Livro não encontrado.", "danger")
            return redirect(url_for('livros.listar'))

        # Deleta o livro
        cursor.execute("DELETE FROM Livro WHERE id_livro = %s", (id_livro,))
        conn.commit()
        flash("Livro deletado com sucesso!", "success")
    except Exception as e:
        conn.rollback()
        flash("Este livro não pode ser deletado pois está vinculado a empréstimos ou reservas.", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('livros.listar'))

@livros_bp.route('/exportar-excel')
@login_required(perfis=['funcionario'])
def exportar_excel():
    filtro_titulo = request.args.get('titulo', '').strip()
    filtro_categoria = request.args.get('categoria', '').strip()
    filtro_editora = request.args.get('editora', '').strip()

    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT l.id_livro AS ID, l.titulo AS Título, c.nome AS Categoria, e.nome AS Editora
        FROM Livro l
        JOIN Categoria c ON l.fk_Categoria_id_categoria = c.id_categoria
        JOIN Editora e ON l.fk_Editora_id_editora = e.id_editora
        WHERE (%s = '' OR l.titulo LIKE %s)
          AND (%s = '' OR c.nome LIKE %s)
          AND (%s = '' OR e.nome LIKE %s)
        ORDER BY l.titulo
    """
    params = (
        filtro_titulo, f'%{filtro_titulo}%',
        filtro_categoria, f'%{filtro_categoria}%',
        filtro_editora, f'%{filtro_editora}%'
    )

    cursor.execute(query, params)
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(resultados)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Livros')
    output.seek(0)

    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='livros.xlsx')