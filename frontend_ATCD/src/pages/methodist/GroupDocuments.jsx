import CancelGroupModal from '../../components/CancelGroupModal';
import CompletionDateModal from '../../components/CompletionDateModal';
// src/pages/methodist/GroupDocuments.jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchGroups, fetchDirections, generateSchedule } from '../../api/groups';
import api from '../../api/config';
import GroupFilters from './components/GroupFilters';
import styles from './GroupDocuments.module.css';

const GroupDocuments = () => {
    const [cancelGroup, setCancelGroup] = useState(null);
    const [completionGroup, setCompletionGroup] = useState(null);
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

    const [archivingId, setArchivingId] = useState(null);
    const [archiveError, setArchiveError] = useState('');
    async function handleArchiveGroup(group) {
        if (archivingId || !window.confirm(`Архивировать группу «${group.assigned_number}»? Сформированные файлы документов и отчётов будут удалены. Записи обучения останутся в БД; восстановление и повторная генерация доступны администратору.`)) return;
        setArchivingId(group.id); setArchiveError('');
        try {
            await api.post(`/api/execution/methodist/groups/${group.id}/archive/`, { confirm_delete_files: true });
            loadGroups();
        } catch (error) { setArchiveError(error.response?.data?.error || 'Не удалось архивировать группу. Повторите попытку.'); }
        finally { setArchivingId(null); }
    }

    const handleFinalizeGroup = (group) => setCompletionGroup(group);

    return (
        <div className={styles.container}>
            {cancelGroup && <CancelGroupModal group={cancelGroup} onClose={() => setCancelGroup(null)} onCancelled={() => { setCancelGroup(null); loadGroups(); }} />}
            {completionGroup && <CompletionDateModal group={completionGroup} onClose={() => setCompletionGroup(null)} onCompleted={() => { setCompletionGroup(null); loadGroups(); }} />}
            <h1>Документы и управление группами</h1>
            {archiveError && <p role="alert">{archiveError}</p>}
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
                                {group.status === 'cancelled' && <div>
                                    <p><strong>Дата отмены:</strong> {group.cancellation_date ? group.cancellation_date.split('-').reverse().join('.') : 'не указана (старая запись)'}</p>
                                    <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}><strong>Причина:</strong> {group.cancellation_reason || 'не указана (старая запись)'}</p>
                                </div>}
                                {group.curator && (
                                    <div className={styles.infoRow}>
                                        <span>👤 Куратор: <strong>{group.curator}</strong></span>
                                    </div>
                                )}
                            </div>

                            <div className={styles.cardActions}>
                                <button className={`${styles.btn} ${styles.btnOutline}`} onClick={() => navigate(`/groups/${group.id}/funding`)}>Финансирование</button>
                                <button 
                                    className={`${styles.btn} ${styles.btnPrimary}`} 
                                    onClick={() => navigate(`/groups/${group.id}/documents`)}
                                >
                                    Документы
                                </button>
                                
                                {group.status !== 'cancelled' && <>
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

                                </>}
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

                                {['draft', 'enrolling', 'in_progress'].includes(group.status) && <button className={`${styles.btn} ${styles.btnOutline}`} onClick={() => setCancelGroup(group)}>Отменить группу</button>}

                                {group.status === 'completed' && <button className={`${styles.btn} ${styles.btnOutline}`} disabled={archivingId !== null} onClick={() => handleArchiveGroup(group)}>
                                    {archivingId === group.id ? 'Архивирование…' : 'Архивировать'}
                                </button>}

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