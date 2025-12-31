package repository

// В данном примере репозиторий не нужен, так как мы не используем БД
// Оставлен для соблюдения структуры проекта

type Repository struct{}

func NewRepository() *Repository {
    return &Repository{}
}