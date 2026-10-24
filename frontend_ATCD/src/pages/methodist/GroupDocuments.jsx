// src/pages/methodist/GroupDocuments.jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchGroups, fetchDirections, generateSchedule } from '../../api/groups';
import api from '../../api/config'; // Твой настроенный axios
import GroupFilters from './components/GroupFilters';
import styles from './GroupDocuments.module.css';

const GroupDocuments = () => {
    const [groups, setGroups] = useState([]);
    const [directions, setDirections] = useState([]);
    const [curators, setCurators] = useState([]); // 🔥 НОВОЕ: список кураторов
    const [loading, setLoading] = useState(true);
    
    const [filters, setFilters] = useState({
        curator: 'all', // 🔥 НОВОЕ
        status: 'in_progress,completed',
        direction: 'all',
        year: new Date().getFullYear().toString(),
        search: '',
    });
    
    const navigate = useNavigate();
    const backendUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

useEffect(() => {
    // 1. Загружаем направления
    fetchDirections()
        .then(res => setDirections(res.data))
        .catch(err => console.error('Ошибка загрузки направлений:', err));

    // 2. 🔥 Загружаем ТОЛЬКО активных кураторов (тех, у кого есть группы)
    api.get('/api/docs/active-curators/') 
        .then(res => {
            setCurators(res.data); // Массив [{id: 1, full_name: "Иванов И.И."}, ...]
        })
        .catch(err => console.error('Ошибка загрузки кураторов:', err));
}, []);

    const loadGroups = () => {
        setLoading(true);
        const params = new URLSearchParams();
        
        // Фильтр по куратору
        if (filters.curator && filters.curator !== 'all') {
            params.append('curator', filters.curator);
        }
        // Остальные фильтры
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

    const handleFinalizeGroup = async (groupId, groupName) => {
        const isConfirmed = window.confirm(`🏁 ФИНАЛЬНОЕ ЗАВЕРШЕНИЕ ГРУППЫ\n\nВы уверены, что хотите закрыть группу "${groupName}"?\n\nСистема проверит:\n• Все ли студенты ознакомились с инструктажем\n• Все ли инструкторы завершили занятия\n• Выставлены ли все итоговые оценки\n\nПосле этого группа перейдет в статус "Завершена".`);
        if (!isConfirmed) return;
        try {
            const res = await api.post(`/api/execution/methodist/groups/${groupId}/complete/`);
            alert(`✅ Успех!\n${res.data.message}`);
            loadGroups();
        } catch (err) {
            if (err.response?.status === 400 && err.response?.data?.missing_items) {
                alert('❌ Невозможно завершить группу:\n\n• ' + err.response.data.missing_items.join('\n• '));
            } else {
                alert(err.response?.data?.error || 'Ошибка сети при попытке завершить группу.');
            }
        }
    };

    return (
        <div className={styles.container}>
            <h1>Документы и управление группами</h1>
            <p className={styles.subtitle}>Выберите группу для работы с документами, расписанием или финального закрытия</p>

            <GroupFilters
                filters={filters}
                directions={directions}
                curators={curators} // 🔥 НОВОЕ: передаем список кураторов
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
                                <span className={`${styles.badge} ${styles[`status_${group.status}`]}`}>
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

                                {/* ✅ Отображение куратора в карточке (как ты и просил) */}
                                {group.curator && (
                                    <div className={styles.infoRow}>
                                        <span>👤 Куратор: <strong>{group.curator}</strong></span>
                                    </div>
                                )}
                            </div>

                            <div className={styles.cardActions}>
                                <button className={`${styles.btn} ${styles.btnPrimary}`} onClick={() => window.open(`${backendUrl}/docs/dashboard/${group.id}/`, '_blank')}>
                                    📋 Документы
                                </button>
                                
                                <button className={`${styles.btn} ${styles.btnInfo}`} onClick={async () => {
                                    if (!window.confirm('Сгенерировать и сохранить выписку аудита ПЭП?')) return;
                                    try {
                                        const res = await api.post(`/docs/save-document/${group.id}/`, { document_type: 'audit_log' });
                                        if (res.data.success) alert(`✅ Аудит ПЭП сохранен!\nПуть: ${res.data.pdf_path}`);
                                        else alert(`❌ Ошибка: ${res.data.error}`);
                                    } catch (err) {
                                        alert(`❌ ${err.response?.data?.error || 'Ошибка сети'}`);
                                    }
                                }} title="Скачать выписку всех электронных подписей в группе">
                                    🛡️ Аудит ПЭП
                                </button>
                                
                                <button className={`${styles.btn} ${styles.btnWarning}`} onClick={() => handleGenerateSchedule(group.id, group.assigned_number)}>
                                    ⚙️ Расписание
                                </button>

                                <button className={`${styles.btn} ${styles.btnSecondary}`} onClick={() => navigate(`/groups/${group.id}/grades`)} title="Открыть журнал оценок">
                                    📖 Журнал
                                </button>

                                {group.status === 'in_progress' && (
                                    <button className={`${styles.btn} ${styles.btnSuccess}`} onClick={() => handleFinalizeGroup(group.id, group.assigned_number)}>
                                        🎬 Завершить группу
                                    </button>
                                )}
                                
                                <button className={`${styles.btn} ${styles.btnOutline}`} onClick={() => window.open(`${backendUrl}/admin/execution/group/${group.id}/change/`, '_blank')}>
                                    ✏️ Изменить
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default GroupDocuments;