CREATE DATABASE IF NOT EXISTS biblioteca;
USE biblioteca;

CREATE TABLE Categoria (
  id_categoria INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(100) NOT NULL
);

CREATE TABLE Editora (
  id_editora INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  cidade VARCHAR(100) NOT NULL,
  pais VARCHAR(100) NOT NULL
);

CREATE TABLE Autor (
  id_autor INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  nacionalidade VARCHAR(100)
);

CREATE TABLE Usuario (
  id_usuario INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(150) NOT NULL,
  email VARCHAR(150) NOT NULL UNIQUE,
  telefone VARCHAR(20),
  perfil ENUM('aluno','professor','funcionario') NOT NULL
);

CREATE TABLE Funcionario (
  fk_Usuario_id_usuario INT PRIMARY KEY,
  numero_identificacao VARCHAR(50) NOT NULL,
  setor VARCHAR(100) NOT NULL,
  FOREIGN KEY (fk_Usuario_id_usuario) REFERENCES Usuario(id_usuario)
    ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE Livro (
  id_livro INT AUTO_INCREMENT PRIMARY KEY,
  titulo VARCHAR(150) NOT NULL,
  subtitulo VARCHAR(150),
  ano_publicacao INT NOT NULL,
  idioma VARCHAR(50) NOT NULL,
  resumo TEXT,
  num_copias_disponiveis INT NOT NULL,
  fk_Categoria_id_categoria INT NOT NULL,
  fk_Editora_id_editora INT NOT NULL,
  FOREIGN KEY (fk_Categoria_id_categoria) REFERENCES Categoria(id_categoria),
  FOREIGN KEY (fk_Editora_id_editora) REFERENCES Editora(id_editora)
);

CREATE TABLE Livro_Autor_Escrito_por (
  fk_Livro_id_livro INT NOT NULL,
  fk_Autor_id_autor INT NOT NULL,
  PRIMARY KEY (fk_Livro_id_livro, fk_Autor_id_autor),
  FOREIGN KEY (fk_Livro_id_livro) REFERENCES Livro(id_livro) ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (fk_Autor_id_autor) REFERENCES Autor(id_autor) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE Reserva (
  id_reserva INT AUTO_INCREMENT PRIMARY KEY,
  data_reserva DATE NOT NULL,
  ordem_fila INT NOT NULL,
  fk_Usuario_id_usuario INT NOT NULL,
  fk_Livro_id_livro INT NOT NULL,
  FOREIGN KEY (fk_Usuario_id_usuario) REFERENCES Usuario(id_usuario),
  FOREIGN KEY (fk_Livro_id_livro) REFERENCES Livro(id_livro)
);

CREATE TABLE Emprestimo (
  id_emprestimo INT AUTO_INCREMENT PRIMARY KEY,
  data_retirada DATE NOT NULL,
  data_prevista_devolucao DATE NOT NULL,
  data_real_devolucao DATE,
  fk_Usuario_id_usuario INT NOT NULL,
  fk_Livro_id_livro INT NOT NULL,
  FOREIGN KEY (fk_Usuario_id_usuario) REFERENCES Usuario(id_usuario),
  FOREIGN KEY (fk_Livro_id_livro) REFERENCES Livro(id_livro)
);

CREATE TABLE Multa (
  id_multa INT AUTO_INCREMENT PRIMARY KEY,
  valor DECIMAL(8,2) NOT NULL,
  dias_atraso INT NOT NULL,
  fk_Emprestimo_id_emprestimo INT NOT NULL,
  FOREIGN KEY (fk_Emprestimo_id_emprestimo) REFERENCES Emprestimo(id_emprestimo)
);

INSERT INTO Categoria (nome) VALUES
('Ficção Científica'),
('Literatura Brasileira'),
('Fantasia'),
('História'),
('Política'),
('Filosofia'),
('Romance'),
('Distopia'),
('Literatura Infantil'),
('Autoajuda');

INSERT INTO Editora (nome, cidade, pais) VALUES
('Editora Aleph', 'São Paulo', 'Brasil'),
('Rocco', 'São Paulo', 'Brasil'),
('Companhia das Letras', 'São Paulo', 'Brasil'),
('Martins Fontes', 'São Paulo', 'Brasil'),
('Record', 'Rio de Janeiro', 'Brasil'),
('Sextante', 'Rio de Janeiro', 'Brasil'),
('Intrínseca', 'Rio de Janeiro', 'Brasil'),
('Planeta', 'São Paulo', 'Brasil'),
('HarperCollins', 'Nova York', 'EUA'),
('Saraiva', 'São Paulo', 'Brasil');

INSERT INTO Autor (nome, nacionalidade) VALUES
('Isaac Asimov', 'Estados Unidos'),            
('Machado de Assis', 'Brasil'),                
('J.K. Rowling', 'Reino Unido'),               
('Yuval Noah Harari', 'Israel'),               
('George Orwell', 'Reino Unido'),              
('Augusto Cury', 'Brasil'),                    
('Paulo Coelho', 'Brasil'),                    
('Stephen King', 'Estados Unidos'),            
('J.R.R. Tolkien', 'Reino Unido'),             
('Clarice Lispector', 'Brasil');

-- Inserção de Usuários (10 registros)
INSERT INTO Usuario (nome, email, telefone, perfil) VALUES
('Ana Beatriz da Silva', 'ana.bsilva@gmail.com', '(21) 99784-1203', 'aluno'),
('Bruno Henrique Lima', 'bruno.lima@veigadealmeida.edu.br', '(21) 99876-4501', 'professor'),
('Carlos Eduardo Souza', 'carlos.edu.souza@gmail.com', '(21) 98765-3021', 'aluno'),
('Daniela Rocha Marques', 'daniela.rocha@veigadealmeida.edu.br', '(21) 99988-1122', 'funcionario'),
('Eduardo Alves Almeida', 'eduardo.almeida@yahoo.com', '(21) 98899-7765', 'aluno'),
('Fernanda Costa Castro', 'fernanda.castro@veigadealmeida.edu.br', '(21) 99655-8899', 'professor'),
('Gustavo Henrique Pinto', 'gustavo.pinto@veigadealmeida.edu.br', '(21) 99777-1234', 'funcionario'),
('Helena Moura Ribeiro', 'helena.moura@hotmail.com', '(21) 98541-1123', 'aluno'),
('Igor Luiz Matos', 'igor.matos@veigadealmeida.edu.br', '(21) 98700-2233', 'professor'),
('Julia Maria Ramos', 'julia.ramos@veigadealmeida.edu.br', '(21) 99601-9988', 'funcionario');

INSERT INTO Funcionario (numero_identificacao, setor, fk_Usuario_id_usuario) VALUES
('1001', 'Atendimento', 4),
('1002', 'Aquisicoes', 7),
('1003', 'TI', 10);

INSERT INTO Livro (titulo, subtitulo, ano_publicacao, idioma, resumo, num_copias_disponiveis, fk_Categoria_id_categoria, fk_Editora_id_editora) VALUES
('Fundação', 'Trilogia da Fundação', 1951, 'Português', 'Obra clássica de ficção científica de Isaac Asimov.', 5, 1, 1), 
('Dom Casmurro', NULL, 1899, 'Português', 'Romance de Machado de Assis sobre ciúme e traição.', 3, 2, 5), 
('Harry Potter e a Pedra Filosofal', NULL, 1997, 'Português', 'Primeiro livro da série Harry Potter.', 7, 3, 2), 
('A Revolução dos Bichos', NULL, 1945, 'Português', 'Uma sátira política escrita por George Orwell.', 4, 5, 3), 
('Sapiens', 'Uma breve história da humanidade', 2011, 'Português', 'História da humanidade segundo Yuval Harari.', 6, 4, 9), 
('O Vendedor de Sonhos', NULL, 2008, 'Português', 'Romance de Augusto Cury.', 8, 10, 6), 
('O Alquimista', NULL, 1988, 'Português', 'Romance de Paulo Coelho sobre busca pessoal.', 10, 10, 6), 
('It: A Coisa', NULL, 1986, 'Português', 'Romance de Stephen King.', 5, 7, 3), 
('O Senhor dos Anéis', NULL, 1954, 'Português', 'Fantasia épica de J.R.R. Tolkien.', 4, 3, 4), 
('A Hora da Estrela', NULL, 1977, 'Português', 'Romance de Clarice Lispector.', 6, 2, 5);

INSERT INTO Livro_Autor_Escrito_por (fk_Livro_id_livro, fk_Autor_id_autor) VALUES
(1, 1),  -- Fundação - Isaac Asimov
(2, 2),  -- Dom Casmurro - Machado de Assis
(3, 3),  -- Harry Potter e a Pedra Filosofal - J.K. Rowling
(4, 5),  -- A Revolução dos Bichos - George Orwell
(5, 4),  -- Sapiens - Yuval Noah Harari
(6, 6),  -- O Vendedor de Sonhos - Augusto Cury
(7, 7),  -- O Alquimista - Paulo Coelho
(8, 8),  -- It: A Coisa - Stephen King
(9, 9),  -- O Senhor dos Anéis - J.R.R. Tolkien
(10, 10);-- A Hora da Estrela - Clarice Lispector

INSERT INTO Reserva (data_reserva, ordem_fila, fk_Usuario_id_usuario, fk_Livro_id_livro) VALUES
('2025-06-01', 1, 2, 3),
('2025-06-02', 2, 5, 3),
('2025-06-03', 1, 3, 5),
('2025-06-04', 1, 1, 1),
('2025-06-05', 1, 4, 7),
('2025-06-06', 2, 6, 7),
('2025-06-07', 1, 7, 2),
('2025-06-08', 1, 8, 4),
('2025-06-09', 2, 9, 4),
('2025-06-10', 3, 10, 4);

INSERT INTO Emprestimo (data_retirada, data_prevista_devolucao, data_real_devolucao, fk_Usuario_id_usuario, fk_Livro_id_livro) VALUES
('2025-05-10', '2025-05-25', '2025-05-24', 1, 1),
('2025-05-12', '2025-05-27', '2025-05-30', 2, 2),
('2025-05-15', '2025-05-30', NULL, 3, 3),
('2025-05-20', '2025-06-04', '2025-06-04', 4, 4),
('2025-05-22', '2025-06-06', '2025-06-10', 5, 5),
('2025-05-25', '2025-06-09', NULL, 6, 6),
('2025-05-28', '2025-06-12', '2025-06-11', 7, 7),
('2025-06-01', '2025-06-16', NULL, 8, 8),
('2025-06-03', '2025-06-18', '2025-06-20', 9, 9),
('2025-06-05', '2025-06-20', NULL, 10, 10);

INSERT INTO Multa (valor, dias_atraso, fk_Emprestimo_id_emprestimo) VALUES
(6.00, 3, 2),
(8.00, 4, 5),
(4.00, 2, 9);

-- Acrescentar 7 usuários funcionários novos (além dos 3 já existentes)
INSERT INTO Usuario (nome, email, telefone, perfil) VALUES
('Lucas Fernandes', 'lucas.fernandes@veigadealmeida.edu.br', '(21) 99444-3322', 'funcionario'),
('Mariana Silva', 'mariana.silva@veigadealmeida.edu.br', '(21) 99222-7788', 'funcionario'),
('Pedro Souza', 'pedro.souza@veigadealmeida.edu.br', '(21) 99111-5566', 'funcionario'),
('Carla Mendes', 'carla.mendes@veigadealmeida.edu.br', '(21) 99888-7744', 'funcionario'),
('Ricardo Lima', 'ricardo.lima@veigadealmeida.edu.br', '(21) 99777-8899', 'funcionario'),
('Paula Gonçalves', 'paula.goncalves@veigadealmeida.edu.br', '(21) 99666-4455', 'funcionario'),
('Felipe Rocha', 'felipe.rocha@veigadealmeida.edu.br', '(21) 99555-2233', 'funcionario');

-- Inserir os 7 funcionários vinculados aos usuários acima

INSERT INTO Funcionario (fk_Usuario_id_usuario, numero_identificacao, setor) VALUES
(11, '1004', 'Biblioteca'),
(12, '1005', 'Biblioteca'),
(13, '1006', 'TI'),
(14, '1007', 'TI'),
(15, '1008', 'Atendimento'),
(16, '1009', 'Atendimento'),
(17, '1010', 'Manutenção');

-- Inserir mais 7 multas, associadas a empréstimos existentes 

INSERT INTO Emprestimo (id_emprestimo, data_retirada, data_prevista_devolucao, data_real_devolucao, fk_Usuario_id_usuario, fk_Livro_id_livro) VALUES
(11, '2025-06-12', '2025-06-27', '2025-06-29', 2, 2),
(12, '2025-06-13', '2025-06-28', '2025-06-29', 3, 3),
(13, '2025-06-14', '2025-06-29', '2025-07-03', 4, 4),
(14, '2025-06-15', '2025-06-30', '2025-07-05', 5, 5),
(15, '2025-06-16', '2025-07-01', '2025-07-06', 6, 6),
(16, '2025-06-17', '2025-07-02', '2025-07-03', 7, 7),
(17, '2025-06-18', '2025-07-03', '2025-07-05', 8, 8),
(18, '2025-06-19', '2025-07-04', '2025-07-05', 9, 9),
(19, '2025-06-20', '2025-07-05', '2025-07-09', 10, 10),
(20, '2025-06-21', '2025-07-06', '2025-07-08', 1, 1);

INSERT INTO Multa (id_multa, valor, dias_atraso, fk_Emprestimo_id_emprestimo) VALUES
(5, 4.00, 2, 11),
(6, 2.00, 1, 12),
(7, 8.00, 4, 13),
(8, 10.00, 5, 14),
(9, 10.00, 5, 15),
(10, 2.00, 1, 16),
(11, 4.00, 2, 17),
(12, 2.00, 1, 18),
(13, 8.00, 4, 19),
(14, 4.00, 2, 20);

ALTER TABLE Multa ADD COLUMN quitada BOOLEAN NOT NULL DEFAULT FALSE;







