// src/pages/methodist/GroupDocuments.jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchGroups, fetchDirections, generateSchedule } from '../../api/groups';
import api from '../../api/config';
import GroupFilters from './components/GroupFilters';
import styles from './GroupDocuments.module.css';

const GroupDocuments = () => {
    const [groups, setGroups] = useState([]);
    const [directions, setDirections] = useState([]);
    const [curators, setCurators] = useState([]); 
    const [loading, setLoading] = useState(true);
    
    const [filters, setFilters] = useState({
        curator: 'all', 
        status: 'in_progress,completed',
        direction: 'all',
        year: new Date().getFullYear().toString(),
        search: '',
    });
    
    const navigate = useNavigate();

    useEffect(() => {
        // 1. Загружаем направления
        fetchDirections()
            .then(res => setDirections(res.data))
            .catch(err => console.error('Ошибка загрузки направлений:', err));

        // 2. Загружаем ТОЛЬКО активных кураторов
        api.get('/api/docs/active-curators/') 
            .then(res => setCurators(res.data))
            .catch(err => console.error('Ошибка загрузки кураторов:', err));
    }, []);

    const loadGroups = () => {
        setLoading(true);
        const params = new URLSearchParams();
        
        if (filters.curator && filters.curator !== 'all') {
            params.append('curator', filters.curator);
        }
        if (filters.status) params.append('status', filters.status);
        if (filters.direction && filters.direction !== 'all') params.append('direction', filters.direction);
        if (filters.year) params.append('year', filters.year);
        if (filters.search) params.append('search', filters.search);

        fetchGroups(Object.fromEntries(params))
            .then(res => setGroups(res.data.results))
            .catch(err => console.error('Ошибка загрузки групп:', err))
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        loadGroups();
    }, [filters]);

    const updateFilter = (key, value) => setFilters(prev => ({ ...prev, [key]: value }));

    const handleGenerateSchedule = async (groupId, groupName) => {
        const isConfirmed = window.confirm(`⚠️ ВНИМАНИЕ!\n\nЭто действие УДАЛИТ текущее расписание группы "${groupName}" и создаст новое на основе модуля.\n\nПродолжить?`);
        if (!isConfirmed) return;
        try {
            const res = await generateSchedule(groupId);
            if (res.data.success) {
                alert(`✅ Успех!\n${res.data.message}`);
                loadGroups();
            } else {
                alert(`❌ Ошибка:\n${res.data.error}`);
            }
        } catch (err) {
            alert('Ошибка сети при попытке сгенерировать расписание.');
        }
    };

    const handleFinalizeGroup = async (group) => {
        const action = group.status === 'completed' ? 'Подтвердить выдачу документов' : 'Завершить группу и подтвердить выдачу документов';
        if (!window.confirm(`${action} для группы «${group.assigned_number}»?`)) return;
        try {
            const { data } = await api.post(`/api/execution/methodist/groups/${group.id}/complete/`);
            alert(data.message);
            loadGroups();
        } catch (err) {
            const { error, missing_items: missingItems } = err.response?.data || {};
            alert([error, ...(missingItems || [])].filter(Boolean).join('\n') || 'Не удалось подтвердить выдачу документов.');
        }
    };

    return (
        <div className={styles.container}>
            <h1>Документы и управление группами</h1>
            <p className={styles.subtitle}>Выберите группу для работы с документами, расписанием или финального закрытия</p>

            <GroupFilters
                filters={filters}
                directions={directions}
                curators={curators} 
                onFilterChange={updateFilter}
            />

            {loading ? (
                <div className={styles.loading}>Загрузка групп...</div>
            ) : groups.length === 0 ? (
                <div className={styles.empty}>Группы по заданным фильтрам не найдены</div>
            ) : (
                <div className={styles.grid}>
                    {groups.map(group => (
                        <div key={group.id} className={styles.card}>
                            <div className={styles.cardHeader}>
                                <h3 className={styles.groupNumber}>{group.assigned_number}</h3>
                                <span className={`${styles.badge} ${styles[`status_${group.status}`] || ''}`}>
                                    {group.status_display}
                                </span>
                            </div>

                            <div className={styles.cardBody}>
                                <div className={styles.moduleTitle}>{group.module_title}</div>
                                <div className={styles.infoRow}>
                                    <span className={styles.directionBadge}>{group.direction_display}</span>
                                </div>
                                <div className={styles.infoRow}>
                                    <span>📅 {group.start_date} — {group.end_date}</span>
                                </div>
                                <div className={styles.infoRow}>
                                    <span>👥 Слушателей: <strong>{group.students_count}</strong></span>
                                </div>
                                {group.curator && (
                                    <div className={styles.infoRow}>
                                        <span>👤 Куратор: <strong>{group.curator}</strong></span>
                                    </div>
                                )}
                            </div>

                            <div className={styles.cardActions}>
                                <button 
                                    className={`${styles.btn} ${styles.btnPrimary}`} 
                                    onClick={() => navigate(`/groups/${group.id}/documents`)}
                                >
                                    Документы
                                </button>
                                
                                {/* 🔥 НОВАЯ КНОПКА: Редактирование группы (вместо Аудита ПЭП) */}
                                <button 
                                    className={`${styles.btn} ${styles.btnOutline}`} 
                                    onClick={() => navigate(`/groups/${group.id}/edit`)}
                                    title="Исправить данные группы, состав или список слушателей"
                                >
                                    Изменить
                                </button>
                                
                                <button 
                                    className={`${styles.btn} ${styles.btnWarning}`} 
                                    onClick={() => handleGenerateSchedule(group.id, group.assigned_number)}
                                    title="Автоматически создать расписание на основе модуля"
                                >
                                    Авторасписание
                                </button>

                                <button 
                                    className={`${styles.btn} ${styles.btnSecondary}`} 
                                    onClick={() => navigate(`/groups/${group.id}/grades`)} 
                                    title="Открыть журнал оценок"
                                >
                                    Журнал
                                </button>

                                <button 
                                    className={`${styles.btn} ${styles.btnInfo}`} 
                                    onClick={() => navigate(`/groups/${group.id}/schedule`)}
                                    title="Вручную изменить даты, время, аудитории и преподавателей"
                                >
                                    Расписание
                                </button>

                                {(group.status === 'in_progress' || (group.status === 'completed' && group.has_unsigned_documents)) && (
                                    <button 
                                        className={`${styles.btn} ${styles.btnSuccess}`} 
                                        onClick={() => handleFinalizeGroup(group)}
                                    >
                                        {group.status === 'completed' ? 'Подтвердить выдачу' : 'Завершить'}
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default GroupDocuments;