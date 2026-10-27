## Migrations com Alembic - Principais Comandos

Gerar nova migration a partir de mudanças nos models:
docker compose exec backend alembic revision --autogenerate -m "descrição da mudança"

Aplicar todas as migrations pendentes:
docker compose exec backend alembic upgrade head

Reverter a última migration:
docker compose exec backend alembic downgrade -1

Ver histórico de migrations:
docker compose exec backend alembic history