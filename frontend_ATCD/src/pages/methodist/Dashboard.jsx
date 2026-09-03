import { useGroups } from './hooks/useGroups';
import GroupFilters from './components/GroupFilters';
import GroupCard from './components/GroupCard';
import styles from './Dashboard.module.css';

const Dashboard = () => {
    const {
        groups,
        directions,
        loading,
        filters,
        pagination,
        updateFilter,
        goToPage,
    } = useGroups();

    // Разделяем группы на активные и завершенные для удобного отображения
    const activeGroups = groups.filter(g => g.status === 'in_progress' || g.status === 'enrolling');
    const completedGroups = groups.filter(g => g.status === 'completed');

    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <h1>Панель управления методиста</h1>
                <p style={{ color: '#666' }}>Управление группами, документами и отчетностью</p>
            </div>

            <GroupFilters
                filters={filters}
                directions={directions}
                onFilterChange={updateFilter}
            />

            {loading ? (
                <div className={styles.loading}>Загрузка данных...</div>
            ) : (
                <>
                    {activeGroups.length > 0 && (
                        <>
                            <h2 className={styles.sectionTitle}>
                                Активные группы ({activeGroups.length})
                            </h2>
                            <div className={styles.grid}>
                                {activeGroups.map(group => (
                                    <GroupCard key={group.id} group={group} />
                                ))}
                            </div>
                        </>
                    )}

                    {completedGroups.length > 0 && (
                        <>
                            <h2 className={styles.sectionTitle}>
                                Завершенные группы ({completedGroups.length})
                            </h2>
                            <div className={styles.grid}>
                                {completedGroups.map(group => (
                                    <GroupCard key={group.id} group={group} />
                                ))}
                            </div>
                        </>
                    )}

                    {groups.length === 0 && (
                        <div className={styles.empty}>
                            Группы не найдены. Попробуйте изменить фильтры.
                        </div>
                    )}

                    {/* Простая пагинация */}
                    {pagination.total_pages > 1 && (
                        <div className={styles.pagination}>
                            <button 
                                className={styles.pageBtn}
                                disabled={pagination.page === 1}
                                onClick={() => goToPage(pagination.page - 1)}
                            >
                                ← Назад
                            </button>
                            <span style={{ alignSelf: 'center', padding: '0 10px' }}>
                                Страница {pagination.page} из {pagination.total_pages}
                            </span>
                            <button 
                                className={styles.pageBtn}
                                disabled={pagination.page === pagination.total_pages}
                                onClick={() => goToPage(pagination.page + 1)}
                            >
                                Вперед →
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default Dashboard;