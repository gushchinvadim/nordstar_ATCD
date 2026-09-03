import styles from './GroupCard.module.css';

const GroupCard = ({ group }) => {
    // ГИБРИДНЫЙ ПОДХОД: при клике переходим на существующую Django-страницу
    // Берем URL бэкенда из .env (например, http://127.0.0.1:8000)
const backendUrl = import.meta.env.VITE_API_URL; 
const djangoDashboardUrl = `${backendUrl}/docs/dashboard/${group.id}/`;

    return (
        <div className={styles.card}>
            <div>
                <div className={styles.cardHeader}>
                    <h3 className={styles.groupNumber}>{group.assigned_number}</h3>
                    <span className={`${styles.statusBadge} ${styles[`status_${group.status}`]}`}>
                        {group.status_display}
                    </span>
                </div>
                
                <div className={styles.moduleInfo}>
                    <strong>{group.direction_display}</strong><br/>
                    {group.module_title}
                </div>

                <div className={styles.metaInfo}>
                    <span>📅 {group.start_date} – {group.end_date}</span>
                    <span>👥 Студентов: {group.students_count}</span>
                </div>
                {group.curator && (
                    <div className={styles.metaInfo}>
                        <span>👤 Куратор: {group.curator}</span>
                    </div>
                )}
            </div>

            <a href={djangoDashboardUrl} className={styles.btnOpen}>
                Открыть документы группы →
            </a>
        </div>
    );
};

export default GroupCard;