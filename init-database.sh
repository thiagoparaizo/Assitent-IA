#!/bin/bash
set -e

# Conectar ao PostgreSQL usando psql e criar o segundo banco de dados
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE assistant;
    GRANT ALL PRIVILEGES ON DATABASE assistant TO postgres;
EOSQL

echo "Banco de dados assistant criado com sucesso!"