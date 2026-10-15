import styles from './GroupCard.module.css';
import { useNavigate } from 'react-router-dom';

const GroupCard = ({ group }) => {
    // ✅ ПРАВИЛЬНО: хук внутри компонента
    const navigate = useNavigate();
    const backendUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'; 
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

            {/* Если вы хотите, чтобы эта карточка тоже вела на новый фронтенд, раскомментируйте кнопку ниже и закомментируйте <a> */}
            {/* <button className={styles.btnOpen} onClick={() => navigate(`/groups/${group.id}/grades`)}>
                📖 Журнал оценок →
            </button> */}

            <a href={djangoDashboardUrl} className={styles.btnOpen} target="_blank" rel="noopener noreferrer">
                Открыть документы группы →
            </a>
        </div>
    );
};

export default GroupCard;