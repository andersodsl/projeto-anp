DROP TABLE IF EXISTS posto, empresa, bandeira_sinonimo, bandeira, endereco, bairro, municipio, uf CASCADE;

CREATE TABLE uf (
    id SERIAL PRIMARY KEY,
    sigla CHAR(2) NOT NULL UNIQUE,
    nome VARCHAR(100) NOT NULL
);

CREATE TABLE municipio (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    uf_id INTEGER NOT NULL REFERENCES uf(id),
    UNIQUE (nome, uf_id)
);

CREATE TABLE bairro (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    municipio_id INTEGER NOT NULL REFERENCES municipio(id),
    UNIQUE (nome, municipio_id)
);

CREATE TABLE endereco (
    id SERIAL PRIMARY KEY,
    tipo_logradouro VARCHAR(50),
    logradouro VARCHAR(200),
    numero VARCHAR(30),
    sem_numero BOOLEAN NOT NULL DEFAULT FALSE,   
    complemento VARCHAR(150),
    cep CHAR(8),
    municipio_id INTEGER NOT NULL REFERENCES municipio(id),  
    bairro_id INTEGER REFERENCES bairro(id)                  
);

CREATE TABLE bandeira (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE bandeira_sinonimo (
    id SERIAL PRIMARY KEY,
    sinonimo VARCHAR(150) NOT NULL UNIQUE,
    bandeira_id INTEGER NOT NULL REFERENCES bandeira(id)
);

CREATE TABLE empresa (
    cnpj_raiz CHAR(8) PRIMARY KEY,
    razao_social VARCHAR(200) NOT NULL
);

CREATE TABLE posto (
    cnpj CHAR(14) PRIMARY KEY,
    cnpj_raiz CHAR(8) NOT NULL REFERENCES empresa(cnpj_raiz),
    codigo_isimp VARCHAR(50),
    autorizacao VARCHAR(50),
    tipo_autorizacao VARCHAR(100),
    data_publicacao DATE,
    data_vinculacao DATE,
    endereco_id INTEGER NOT NULL REFERENCES endereco(id),
    bandeira_original VARCHAR(150),            
    bandeira_id INTEGER REFERENCES bandeira(id),
    flag_inconsistente BOOLEAN DEFAULT FALSE,
    motivo_inconsistencia TEXT
);

CREATE INDEX idx_posto_bandeira ON posto(bandeira_id);
CREATE INDEX idx_posto_raiz ON posto(cnpj_raiz);
CREATE INDEX idx_endereco_municipio ON endereco(municipio_id);