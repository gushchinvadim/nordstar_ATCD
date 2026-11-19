// src/pages/methodist/components/GroupFilters.jsx
import styles from './GroupFilters.module.css';

const GroupFilters = ({ filters, directions, curators = [], onFilterChange }) => {
    const currentYear = new Date().getFullYear();
    const years = [currentYear, currentYear - 1, currentYear - 2];

    return (
        <div className={styles.container}>
            <label className={styles.filterGroup}>
                <span>Статус:</span>
                <select className={styles.field} value={filters.status} onChange={(e) => onFilterChange('status', e.target.value)}>
                    <option value="in_progress,completed">Обучение и завершённые</option>
                    <option value="draft,enrolling,in_progress">Все активные</option>
                    <option value="completed">Завершённые</option>
                    <option value="cancelled">Отменённые</option>
                    <option value="archived">Архивные</option>
                    <option value="draft,enrolling,in_progress,completed,cancelled,archived">Все статусы</option>
                </select>
            </label>
            {/* 🔥 НОВОЕ: Фильтр по Куратору */}
            <label className={styles.filterGroup}>
                <span>Куратор:</span>
                <select
                    className={styles.field}
                    value={filters.curator || 'all'}
                    onChange={(e) => onFilterChange('curator', e.target.value)}
                >
                    <option value="all">Все кураторы</option>
                    {curators.map(curator => (
                        <option key={curator.id} value={curator.id}>
                            {curator.full_name}
                        </option>
                    ))}
                </select>
            </label>

            <label className={styles.filterGroup}>
                <span>Направление:</span>
                <select
                    className={styles.field}
                    value={filters.direction}
                    onChange={(e) => onFilterChange('direction', e.target.value)}
                >
                    <option value="all">Все направления</option>
                    {directions.map((dir, index) => (
                        <option key={`${dir.code}-${index}`} value={dir.code}>
                            {dir.title}
                        </option>
                    ))}
                </select>
            </label>

            <label className={styles.filterGroup}>
                <span>Год начала:</span>
                <select
                    className={styles.field}
                    value={filters.year}
                    onChange={(e) => onFilterChange('year', e.target.value)}
                >
                    {years.map(year => (
                        <option key={year} value={year}>{year}</option>
                    ))}
                </select>
            </label>

            <label className={styles.filterGroup}>
                <span>Поиск:</span>
                <input
                    className={styles.field}
                    type="text"
                    placeholder="Номер группы или модуль..."
                    value={filters.search}
                    onChange={(e) => onFilterChange('search', e.target.value)}
                />
            </label>
        </div>
    );
};

export default GroupFilters;