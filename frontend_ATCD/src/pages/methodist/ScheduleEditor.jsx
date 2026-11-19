// src/pages/methodist/ScheduleEditor.jsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../api/config';
import styles from './ScheduleEditor.module.css';

const STATUS_CHOICES = [
    { value: 'planned', label: 'Запланировано' },
    { value: 'in_progress', label: 'Идёт' },
    { value: 'completed', label: 'Завершено' },
    { value: 'cancelled', label: 'Отменено' },
];

const ScheduleEditor = () => {
    const { groupId } = useParams();
    const navigate = useNavigate();
    
    // 🔥 ВСЕ ХУКИ ДОЛЖНЫ БЫТЬ ЗДЕСЬ, ВНУТРИ КОМПОНЕНТА
    const [groupInfo, setGroupInfo] = useState(null);
    const readOnly = groupInfo?.status === 'cancelled';
    const [items, setItems] = useState([]);
    const [dropdowns, setDropdowns] = useState({ instructors: [], classrooms: [], sections: [] });
    const [loading, setLoading] = useState(true);
    const [savingId, setSavingId] = useState(null);
    const [editingCell, setEditingCell] = useState(null);
    const [eligibilityError, setEligibilityError] = useState('');
    const [newDate, setNewDate] = useState('');
    const [lastSaved, setLastSaved] = useState(null);

    useEffect(() => {
        loadData();
    }, [groupId]);

    const loadData = async () => {
        setLoading(true);
        try {
            // Загружаем информацию о группе + расписание + справочники
            const [groupRes, scheduleRes, dropdownsRes] = await Promise.all([
                api.get(`/api/docs/group/${groupId}/`),
                api.get(`/api/docs/groups/${groupId}/schedule/`),
                api.get(`/api/docs/groups/${groupId}/schedule/dropdowns/`)
            ]);
            
            setGroupInfo(groupRes.data);
            setItems(scheduleRes.data);
            setDropdowns(dropdownsRes.data);
            setLastSaved(new Date());
        } catch (err) {
            console.error('Ошибка загрузки:', err);
            alert('Не удалось загрузить расписание');
        } finally {
            setLoading(false);
        }
    };

    const handleCellClick = async (itemId, field) => {
        if (readOnly || savingId !== null) return;
        setEligibilityError('');
        if (field === 'instructor') {
            const item = items.find((row) => row.id === itemId);
            setSavingId(itemId);
            try {
                const { data } = await api.get(`/api/docs/groups/${groupId}/schedule/dropdowns/`, {
                    params: { section_id: item.section?.id, date: item.date,
                        ...(item.session_type === 'sdo' && item.deadline ? { deadline: item.deadline } : {}) },
                });
                setDropdowns((previous) => ({ ...previous, instructors: data.instructors }));
                setEligibilityError(data.eligibility_error || (data.instructors.length ? '' : 'Нет преподавателей с подтверждённым допуском на выбранную дату. Проверьте сведения в разделе «Преподаватели».'));
                setEditingCell({ id: itemId, field });
            } catch (error) {
                setEligibilityError(error.response?.data?.error || 'Не удалось проверить допуски преподавателей. Повторите попытку.');
            } finally { setSavingId(null); }
        } else { setEditingCell({ id: itemId, field }); }
    };

    const handleSave = async (itemId, field, value) => {
        setEditingCell(null);
        setSavingId(itemId);
        
        // 🔥 Оптимистичное обновление UI (для мгновенного отклика)
        setItems(prev => prev.map(item => {
            if (item.id !== itemId) return item;
            
            // Формируем правильное значение для отображения
            let updatedItem = { ...item, [field]: value };
            
            if (field === 'instructor') {
                updatedItem.instructor = value ? { id: value.id, name: value.full_name } : null;
            } else if (field === 'classroom') {
                updatedItem.classroom = value ? { id: value.id, title: value.title, audience: value.audience } : null;
            } else if (field === 'section') {
                updatedItem.section = value ? { id: value.id, title: value.title } : null;
            }
            
            return updatedItem;
        }));

        try {
            const payload = {};
            if (field === 'instructor') payload.instructor = value ? value.id : null;
            else if (field === 'classroom') payload.classroom = value ? value.id : null;
            else if (field === 'section') payload.section = value ? value.id : null;
            else payload[field] = value;

            const response = await api.patch(`/api/docs/schedule/item/${itemId}/update/`, payload);
            if (field === 'section') {
                await loadData();
            } else if (response.data.success) {
                setLastSaved(new Date());
            }
        } catch (err) {
            console.error('Ошибка сохранения:', err);
            alert(err.response?.data?.errors?.instructor?.join(' ') || err.response?.data?.error || 'Не удалось сохранить изменения. Попробуйте еще раз.');
            loadData(); // Откат при ошибке
        } finally {
            setSavingId(null);
        }
    };

    const handleDelete = async (itemId) => {
        if (!window.confirm('Удалить это занятие из расписания?')) return;
        try {
            await api.delete(`/api/docs/schedule/item/${itemId}/delete/`);
            setItems(prev => prev.filter(item => item.id !== itemId));
            setLastSaved(new Date());
        } catch (err) {
            alert('Ошибка при удалении');
        }
    };

    const handleAdd = async (event) => {
        event.preventDefault();
        if (!newDate || !dropdowns.sections.length) return;
        
        try {
            const res = await api.post(`/api/docs/groups/${groupId}/schedule/create/`, {
                date: newDate,
                section: dropdowns.sections[0]?.id,
                status: 'planned'
            });
            if (res.data.success) {
                setNewDate('');
                await loadData();
            }
        } catch (err) {
            alert('Ошибка при создании занятия');
        }
    };

    const renderEditableCell = (item, field, displayValue) => {
        const isEditing = editingCell?.id === item.id && editingCell?.field === field;
        const isSaving = savingId === item.id;

        if (isSaving) return <span className={styles.saving}>💾</span>;

        if (isEditing) {
            if (field === 'instructor') {
                return (
                    <select 
                        className={styles.editSelect}
                        autoFocus
                        defaultValue={item.instructor?.id || ''}
                        onBlur={(e) => {
                            if (e.target.value === String(item.instructor?.id || '')) { setEditingCell(null); return; }
                            const selected = dropdowns.instructors.find(i => i.id === parseInt(e.target.value));
                            handleSave(item.id, field, selected || null);
                        }}
                    >
                        <option value="">— Не назначен —</option>
                        {item.instructor && !dropdowns.instructors.some((row) => row.id === item.instructor.id) && <option value={item.instructor.id} disabled>{item.instructor.name} — текущий, допуск требует проверки</option>}
                        {dropdowns.instructors.map(inst => (
                            <option key={inst.id} value={inst.id}>{inst.full_name}</option>
                        ))}
                    </select>
                );
            }
            if (field === 'classroom') {
                return (
                    <select 
                        className={styles.editSelect}
                        autoFocus
                        defaultValue={item.classroom?.id || ''}
                        onBlur={(e) => {
                            const selected = dropdowns.classrooms.find(c => c.id === parseInt(e.target.value));
                            handleSave(item.id, field, selected || null);
                        }}
                    >
                        <option value="">— Не назначена —</option>
                        {dropdowns.classrooms.map(cls => (
                            <option key={cls.id} value={cls.id}>{cls.label}</option>
                        ))}
                    </select>
                );
            }
            if (field === 'section') {
                return (
                    <select 
                        className={styles.editSelect}
                        autoFocus
                        defaultValue={item.section?.id || ''}
                        onBlur={(e) => {
                            const selected = dropdowns.sections.find(s => s.id === parseInt(e.target.value));
                            handleSave(item.id, field, selected || null);
                        }}
                    >
                        <option value="">— Не выбран —</option>
                        {dropdowns.sections.map(sec => (
                            <option key={sec.id} value={sec.id}>{sec.title}</option>
                        ))}
                    </select>
                );
            }
            if (field === 'status') {
                return (
                    <select 
                        className={styles.editSelect}
                        autoFocus
                        defaultValue={item.status}
                        onBlur={(e) => handleSave(item.id, field, e.target.value)}
                    >
                        {STATUS_CHOICES.map(s => (
                            <option key={s.value} value={s.value}>{s.label}</option>
                        ))}
                    </select>
                );
            }
            if (field === 'notes') {
                return (
                    <input
                        className={styles.editInput}
                        aria-label="Примечание"
                        autoFocus
                        defaultValue={item.notes ?? ''}
                        onBlur={(event) => handleSave(item.id, field, event.target.value)}
                        onKeyDown={(event) => { if (event.key === 'Enter') event.target.blur(); }}
                    />
                );
            }
            if (field === 'date' || field === 'deadline' || field === 'start_time' || field === 'end_time') {
                return (
                    <input 
                        type={field.includes('time') ? 'time' : 'date'}
                        className={styles.editInput}
                        autoFocus
                        defaultValue={item[field]}
                        onBlur={(e) => handleSave(item.id, field, e.target.value || null)}
                        onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); }}
                    />
                );
            }
        }

        return (
            <button type="button" className={styles.editableText} onClick={() => handleCellClick(item.id, field)} disabled={readOnly || savingId !== null}>
                {displayValue || <span className={styles.placeholder}>Указать</span>}
            </button>
        );
    };

    const getStatusLabel = (status) => STATUS_CHOICES.find(s => s.value === status)?.label || status;

    if (loading) return <div className={styles.loading}>Загрузка расписания...</div>;

    return (
        <div className={styles.container}>
            {eligibilityError && <p role="alert">{eligibilityError}</p>}
            {readOnly && <p role="status">Группа отменена. Расписание доступно только для просмотра.</p>}
            <div className={styles.header}>
                <button className={styles.backBtn} onClick={() => navigate(`/groups/${groupId}/documents`)}>
                    ← Назад к документам группы
                </button>
                
                <h1>📅 {readOnly ? 'Расписание отменённой группы' : 'Редактирование расписания'}</h1>
                
                {/* 🔥 ИНФОРМАЦИЯ О ГРУППЕ */}
                {groupInfo && (
                    <div className={styles.groupInfo}>
                        <span className={styles.groupNumber}>{groupInfo.assigned_number}</span>
                        <span className={styles.groupSeparator}>•</span>
                        <span className={styles.groupModule}>{groupInfo.module?.title || groupInfo.module_code}</span>
                        {groupInfo.curator && (
                            <>
                                <span className={styles.groupSeparator}>•</span>
                                <span className={styles.groupCurator}>Куратор: {groupInfo.curator}</span>
                            </>
                        )}
                    </div>
                )}
                
                <p className={styles.hint}>💡 Кликните на ячейку для редактирования. Сохранение происходит автоматически при потере фокуса.</p>
                
                {/* ПАНЕЛЬ СТАТУСА */}
                <div className={styles.saveBar}>
                    {savingId !== null ? (
                        <span className={styles.unsavedIndicator}>
                            Сохраняем изменение…
                        </span>
                    ) : lastSaved ? (
                        <span className={styles.lastSaved}>
                            ✅ Все изменения сохранены (последнее: {lastSaved.toLocaleTimeString()})
                        </span>
                    ) : null}
                    
                    <button 
                        className={styles.refreshBtn} 
                        onClick={loadData} disabled={savingId !== null}
                        title="Сверить текущее расписание с сервером"
                    >
                        🔄 Проверить сохранение
                    </button>
                </div>

                <form className={styles.addForm} onSubmit={handleAdd}>
                    <label>
                        Дата нового занятия
                        <input className={styles.editInput} type="date" value={newDate}
                            onChange={(event) => setNewDate(event.target.value)} required />
                    </label>
                    <button className={styles.addBtn} type="submit" disabled={readOnly || !dropdowns.sections.length || savingId !== null}>
                        + Добавить занятие
                    </button>
                </form>
            </div>

            <div className={styles.tableWrapper} role="region" aria-label="Таблица расписания" tabIndex={0}>
                <table role="table" className={styles.table}>
                    <thead role="rowgroup">
                        <tr role="row">
                            <th role="columnheader">Дата</th>
                            <th role="columnheader">Дедлайн</th>
                            <th role="columnheader">Начало</th>
                            <th role="columnheader">Конец</th>
                            <th role="columnheader">Раздел</th>
                            <th role="columnheader">Тип</th>
                            <th role="columnheader">Статус</th>
                            <th role="columnheader">Инструктор</th>
                            <th role="columnheader">Аудитория</th>
                            <th role="columnheader">Примечание</th>
                            <th role="columnheader"></th>
                        </tr>
                    </thead>
                    <tbody role="rowgroup">
                        {items.map(item => (
                            <tr role="row" key={item.id} className={styles.row}>
                                <td role="cell" data-label="Дата">{renderEditableCell(item, 'date', item.date)}</td>
                                <td role="cell" data-label="Дедлайн">{renderEditableCell(item, 'deadline', item.deadline)}</td>
                                <td role="cell" data-label="Начало">{renderEditableCell(item, 'start_time', item.start_time)}</td>
                                <td role="cell" data-label="Конец">{renderEditableCell(item, 'end_time', item.end_time)}</td>
                                <td role="cell" data-label="Раздел" data-wide="">{renderEditableCell(item, 'section', item.section?.title)}</td>
                                <td role="cell" data-label="Тип"><span className={`${styles.badge} ${styles[item.session_type] || ''}`}>{item.session_type}</span></td>
                                <td role="cell" data-label="Статус">{renderEditableCell(item, 'status', getStatusLabel(item.status))}</td>
                                <td role="cell" data-label="Инструктор" data-wide="">{renderEditableCell(item, 'instructor', item.instructor?.name)}</td>
                                <td role="cell" data-label="Аудитория" data-wide="">{renderEditableCell(item, 'classroom', item.classroom ? `${item.classroom.title} (${item.classroom.audience})` : '')}</td>
                                <td role="cell" data-label="Примечание" data-wide="">{renderEditableCell(item, 'notes', item.notes)}</td>
                                <td role="cell" data-wide="">
                                    <button disabled={readOnly} className={styles.deleteBtn} onClick={() => handleDelete(item.id)} title="Удалить занятие" aria-label="Удалить занятие">
                                        🗑
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default ScheduleEditor;