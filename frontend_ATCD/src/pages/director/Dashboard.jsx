// src/pages/director/Dashboard.jsx
import React, { useState, useEffect } from 'react';
import styles from './Dashboard.module.css';
import api from '../../api/config';

const DirectorDashboard = () => {
    const [groups, setGroups] = useState([]);
    const [expandedGroup, setExpandedGroup] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchGroups();
    }, []);

    const fetchGroups = async () => {
        try {
            const response = await api.get('/api/execution/director/groups/');
            setGroups(response.data);
            setLoading(false);
        } catch (err) {
            console.error("Ошибка загрузки:", err);
            setError('Ошибка загрузки данных');
            setLoading(false);
        }
    };

    const handleApprove = async (groupId) => {
        try {
            await api.post(`/api/execution/director/groups/${groupId}/approve/`);
            await fetchGroups();
            alert('Расписание успешно утверждено!');
        } catch (err) {
            alert(err.response?.data?.error || 'Ошибка утверждения');
        }
    };

    const toggleGroup = (groupId) => {
        setExpandedGroup(expandedGroup === groupId ? null : groupId);
    };

    if (loading) return <div className={styles.loading}>Загрузка...</div>;
    if (error) return <div className={styles.error}>{error}</div>;

    return (
        <div className={styles.container}>
            <h1 className={styles.mainTitle}>Личный кабинет директора</h1>
            <h2 className={styles.subtitle}>Расписания групп для утверждения</h2>
            
            {groups.length === 0 ? (
                <div className={styles.emptyState}>
                    <p>Нет групп для утверждения</p>
                </div>
            ) : (
                groups.map(group => (
                    <div key={group.id} className={styles.groupCard}>
                        <div className={styles.groupHeader} onClick={() => toggleGroup(group.id)}>
                            <div className={styles.groupInfo}>
                                <h3>{group.module_title}</h3>
                                <span className={styles.groupCode}>{group.module_code}</span>
                            </div>
                            <div className={styles.groupMeta}>
                                <p className={styles.groupNumber}>Группа: {group.assigned_number}</p>
                                <p className={styles.status}>Статус: {group.status}</p>
                                <p className={styles.dates}>
                                    {group.start_date} — {group.end_date}
                                </p>
                            </div>
                            <button className={styles.expandButton}>
                                {expandedGroup === group.id ? '▲ Свернуть' : '▼ Открыть расписание'}
                            </button>
                        </div>

                        {expandedGroup === group.id && (
                            <div className={styles.scheduleBlock}>
                                {group.has_director_approval ? (
                                    <div className={styles.approved}>
                                        ✅ Расписание утверждено {new Date(group.director_approval_date).toLocaleString('ru-RU')}
                                    </div>
                                ) : (
                                    <button 
                                        className={styles.approveButton}
                                        onClick={() => handleApprove(group.id)}
                                    >
                                        Утвердить расписание
                                    </button>
                                )}

                                <div className={styles.scheduleList}>
                                    {group.schedule.map(item => (
                                        <div key={item.id} className={styles.scheduleItem}>
                                            <div className={styles.scheduleInfo}>
                                                <span className={styles.date}>{item.date}</span>
                                                <span className={styles.time}>{item.start_time} - {item.end_time}</span>
                                                <span className={styles.section}>{item.section_title}</span>
                                                {item.subsection_title && (
                                                    <span className={styles.subsection}>({item.subsection_title})</span>
                                                )}
                                            </div>
                                            <div className={styles.scheduleMeta}>
                                                <span className={styles.instructor}>👨‍🏫 {item.instructor_name || 'Не назначен'}</span>
                                                <span className={styles.location}>📍 {item.classroom_name || 'Не указано'}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ))
            )}
        </div>
    );
};

export default DirectorDashboard;