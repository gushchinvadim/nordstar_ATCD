// src/pages/methodist/components/GroupFilters.jsx
import styles from './GroupFilters.module.css';

const GroupFilters = ({ filters, directions, curators = [], onFilterChange }) => {
    const currentYear = new Date().getFullYear();
    const years = [currentYear, currentYear - 1, currentYear - 2];

    return (
        <div className={styles.container}>
            {/* 🔥 НОВОЕ: Фильтр по Куратору */}
            <div className={styles.filterGroup}>
                <label>Куратор:</label>
                <select
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
            </div>

            <div className={styles.filterGroup}>
                <label>Направление:</label>
                <select
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
            </div>

            <div className={styles.filterGroup}>
                <label>Год начала:</label>
                <select
                    value={filters.year}
                    onChange={(e) => onFilterChange('year', e.target.value)}
                >
                    {years.map(year => (
                        <option key={year} value={year}>{year}</option>
                    ))}
                </select>
            </div>

            <div className={styles.filterGroup}>
                <label>Поиск:</label>
                <input
                    type="text"
                    placeholder="Номер группы или модуль..."
                    value={filters.search}
                    onChange={(e) => onFilterChange('search', e.target.value)}
                />
            </div>
        </div>
    );
};

export default GroupFilters;