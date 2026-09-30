// src/pages/methodist/GroupDocuments.jsx
import { useState, useEffect } from 'react';
import { fetchGroups, fetchDirections, generateSchedule } from '../../api/groups';
import api from '../../api/config'; // <-- ДОБАВЛЕНО: для POST запроса завершения
import GroupFilters from './components/GroupFilters';
import styles from './GroupDocuments.module.css';

const GroupDocuments = () => {
    const [groups, setGroups] = useState([]);
    const [directions, setDirections] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState({
        status: 'in_progress,completed',
        direction: 'all',
        year: new Date().getFullYear().toString(),
        search: '',
    });

    useEffect(() => {
        fetchDirections()
            .then(res => setDirections(res.data))
            .catch(err => console.error('Ошибка загрузки направлений:', err));
    }, []);

    // Вынесли логику загрузки в отдельную функцию для повторного использования
    const loadGroups = () => {
        setLoading(true);
        const params = new URLSearchParams();
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
        const isConfirmed = window.confirm(
            `⚠️ ВНИМАНИЕ!\n\nЭто действие УДАЛИТ текущее расписание группы "${groupName}" и создаст новое на основе модуля.\n\nПродолжить?`
        );
        if (!isConfirmed) return;

        try {
            const res = await generateSchedule(groupId);
            if (res.data.success) {
                alert(`✅ Успех!\n${res.data.message}`);
                loadGroups(); // Обновляем список после изменения
            } else {
                alert(`❌ Ошибка:\n${res.data.error}`);
            }
        } catch (err) {
            alert('Ошибка сети при попытке сгенерировать расписание.');
        }
    };

    // 🔑 НОВАЯ ФУНКЦИЯ: Финальное завершение группы методистом
    const handleFinalizeGroup = async (groupId, groupName) => {
        const isConfirmed = window.confirm(
            `🏁 ФИНАЛЬНОЕ ЗАВЕРШЕНИЕ ГРУППЫ\n\n` +
            `Вы уверены, что хотите закрыть группу "${groupName}"?\n\n` +
            `Система проверит:\n` +
            `• Все ли студенты ознакомились с инструктажем\n` +
            `• Все ли инструкторы завершили занятия\n` +
            `• Выставлены ли все итоговые оценки\n\n` +
            `После этого группа перейдет в статус "Завершена" и исчезнет из активных списков.`
        );
        if (!isConfirmed) return;

        try {
            const res = await api.post(`/api/execution/methodist/groups/${groupId}/complete/`);
            alert(`✅ Успех!\n${res.data.message}`);
            loadGroups(); // Перезагружаем список, группа исчезнет из "in_progress" или изменит бейдж
        } catch (err) {
            if (err.response?.status === 400 && err.response?.data?.missing_items) {
                alert('❌ Невозможно завершить группу:\n\n• ' + err.response.data.missing_items.join('\n• '));
            } else {
                alert(err.response?.data?.error || 'Ошибка сети при попытке завершить группу.');
            }
        }
    };

    const backendUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

    return (
        <div className={styles.container}>
            <h1>Документы и управление группами</h1>
            <p className={styles.subtitle}>Выберите группу для работы с документами, расписанием или финального закрытия</p>

            <GroupFilters
                filters={filters}
                directions={directions}
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
                            {/* Шапка карточки */}
                            <div className={styles.cardHeader}>
                                <h3 className={styles.groupNumber}>{group.assigned_number}</h3>
                                <span className={`${styles.badge} ${styles[`status_${group.status}`]}`}>
                                    {group.status_display}
                                </span>
                            </div>

                            {/* Тело карточки */}
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
                            </div>

                            {/* Подвал карточки с кнопками */}
                            <div className={styles.cardActions}>
                                <button
                                    className={`${styles.btn} ${styles.btnPrimary}`}
                                    onClick={() => window.open(`${backendUrl}/docs/dashboard/${group.id}/`, '_blank')}
                                >
                                    📋 Документы
                                </button>
                                <button
                                    className={`${styles.btn} ${styles.btnWarning}`}
                                    onClick={() => handleGenerateSchedule(group.id, group.assigned_number)}
                                >
                                    ⚙️ Расписание
                                </button>
                                <button
                                    className={`${styles.btn} ${styles.btnSecondary}`}
                                    onClick={() => window.open(`${backendUrl}/docs/grades/${group.id}/`, '_blank')}
                                >
                                    📖 Журнал
                                </button>
                                
                                {/* 🔑 КНОПКА ФИНАЛЬНОГО ЗАВЕРШЕНИЯ (только для in_progress) */}
                                {group.status === 'in_progress' && (
                                    <button
                                        className={`${styles.btn} ${styles.btnSuccess}`}
                                        onClick={() => handleFinalizeGroup(group.id, group.assigned_number)}
                                        title="Финальная проверка и закрытие группы"
                                    >
                                        🏁 Завершить
                                    </button>
                                )}
                                
                                <button
                                    className={`${styles.btn} ${styles.btnOutline}`}
                                    onClick={() => window.open(`${backendUrl}/admin/execution/group/${group.id}/change/`, '_blank')}
                                >
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